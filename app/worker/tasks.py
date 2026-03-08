import asyncio
import io
import uuid
import structlog
import dramatiq
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.storage import storage_service
from app.models.base import Document, DocumentContent, Workflow, WorkflowStatus
from app.worker.broker import broker

logger = structlog.get_logger()

def async_to_sync(awaitable):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # This shouldn't happen in a basic worker but good to handle
        return loop.run_until_complete(awaitable)
    return asyncio.run(awaitable)

@dramatiq.actor
def extract_document_content(workflow_id: str):
    workflow_uuid = uuid.UUID(workflow_id)
    logger.info("Starting document extraction", workflow_id=workflow_id)

    async_to_sync(_extract_content(workflow_uuid))

async def _extract_content(workflow_uuid: uuid.UUID):
    async with SessionLocal() as db:
        # 1. Fetch workflow and document
        result = await db.execute(
            select(Workflow, Document).join(Document).where(Workflow.id == workflow_uuid)
        )
        row = result.first()
        if not row:
            logger.error("Workflow not found", workflow_id=str(workflow_uuid))
            return

        workflow, document = row

        # Update stage
        workflow.status = WorkflowStatus.EXTRACTING
        workflow.current_stage = "extracting"
        await db.commit()

        try:
            # 2. Get file from storage
            file_bytes = await storage_service.get_file(document.storage_key)
            
            # 3. Extract text using ExtractionService
            from app.services.extraction import extraction_service
            text = extraction_service.extract_text(file_bytes, document.content_type)

            # 4. Save content
            content = DocumentContent(
                document_id=document.id,
                extracted_text=text,
                text_length=len(text),
                extraction_status="completed"
            )
            db.add(content)
            
            # 5. Advance workflow
            workflow.status = WorkflowStatus.ANALYZING
            workflow.current_stage = "analyzing"
            await db.commit()

            logger.info("Document extraction completed", 
                        workflow_id=str(workflow_uuid), 
                        text_length=len(text))

            # Trigger next stage (AI Analysis)
            analyze_document.send(str(workflow_id))

        except Exception as e:
            # ... (rest of extraction error handling)
            await db.rollback()
            logger.error("Extraction failed", workflow_id=str(workflow_uuid), error=str(e))
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            await db.commit()

@dramatiq.actor
def analyze_document(workflow_id: str):
    workflow_uuid = uuid.UUID(workflow_id)
    logger.info("Starting AI analysis", workflow_id=workflow_id)

    async_to_sync(_analyze_content(workflow_uuid))

async def _analyze_content(workflow_uuid: uuid.UUID):
    from app.services.ai import ai_service
    from app.core.prompts import PROMPT_TEMPLATES
    from app.models.base import LLMRequest, AnalysisResult

    async with SessionLocal() as db:
        # 1. Fetch data
        result = await db.execute(
            select(Workflow, DocumentContent).join(DocumentContent, Workflow.document_id == DocumentContent.document_id).where(Workflow.id == workflow_uuid)
        )
        row = result.first()
        if not row:
            logger.error("Workflow or content not found", workflow_id=str(workflow_uuid))
            return

        workflow, content = row
        
        try:
            # 2. Call AI Service
            template = PROMPT_TEMPLATES["document_analysis"]["v1"]
            ai_data = await ai_service.analyze_text(content.extracted_text, template)
            
            # 3. Store LLMRequest metadata
            meta = ai_data["metadata"]
            llm_request = LLMRequest(
                workflow_id=workflow.id,
                provider=meta["provider"],
                model=meta["model"],
                prompt_template_version="v1",
                latency_ms=meta["latency_ms"],
                prompt_tokens=meta["prompt_tokens"],
                completion_tokens=meta["completion_tokens"],
                total_tokens=meta["total_tokens"],
                estimated_cost=meta["estimated_cost"]
            )
            db.add(llm_request)

            # 4. Advance workflow
            workflow.status = WorkflowStatus.VALIDATING
            workflow.current_stage = "validating"
            
            # Store raw result in AnalysisResult for next phase
            import json
            analysis_result = AnalysisResult(
                workflow_id=workflow.id,
                result_json=json.loads(ai_data["raw_result"]),
                schema_version="v1",
                validation_status="pending",
                evaluation_score=0.0
            )
            db.add(analysis_result)
            
            await db.commit()
            logger.info("AI analysis completed", workflow_id=str(workflow_uuid))

            # Trigger Validation stage
            validate_document.send(str(workflow_id))

        except Exception as e:
            # ... (rest of analysis error handling)
            await db.rollback()
            logger.error("AI Analysis failed", workflow_id=str(workflow_uuid), error=str(e))
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            await db.commit()

@dramatiq.actor
def validate_document(workflow_id: str):
    workflow_uuid = uuid.UUID(workflow_id)
    logger.info("Starting validation", workflow_id=workflow_id)

    async_to_sync(_validate_analysis(workflow_uuid))

async def _validate_analysis(workflow_uuid: uuid.UUID):
    from app.schemas.analysis import DocumentAnalysis
    from app.services.evaluation import evaluation_service
    from app.models.base import AnalysisResult

    async with SessionLocal() as db:
        result = await db.execute(
            select(Workflow, AnalysisResult).join(AnalysisResult).where(Workflow.id == workflow_uuid)
        )
        row = result.first()
        if not row:
            logger.error("Workflow or analysis result not found", workflow_id=str(workflow_uuid))
            return

        workflow, analysis_result = row
        workflow.status = WorkflowStatus.VALIDATING
        workflow.current_stage = "validating"
        await db.commit()

        try:
            # 1. Validate Schema
            analysis = DocumentAnalysis(**analysis_result.result_json)
            
            # 2. Evaluate/Score
            score = evaluation_service.calculate_score(analysis)
            
            # 3. Update Result
            analysis_result.validation_status = "validated"
            analysis_result.evaluation_score = score
            
            # 4. Finalize Workflow
            workflow.status = WorkflowStatus.COMPLETED
            workflow.current_stage = "completed"
            workflow.completed_at = datetime.now(timezone.utc)
            
            await db.commit()
            logger.info("Validation and evaluation completed", workflow_id=str(workflow_uuid), score=score)

        except Exception as e:
            await db.rollback()
            logger.error("Validation failed", workflow_id=str(workflow_uuid), error=str(e))
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = f"Validation Error: {str(e)}"
            await db.commit()
