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
            
            # 3. Extract text based on content type
            text = ""
            if document.content_type == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text = "\n".join([page.get_text() for page in doc])
                doc.close()
            elif document.content_type == "text/plain":
                text = file_bytes.decode("utf-8")
            elif document.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc = DocxDocument(io.BytesIO(file_bytes))
                text = "\n".join([para.text for para in doc.paragraphs])
            else:
                raise ValueError(f"Unsupported content type: {document.content_type}")

            # Normalize whitespace
            text = " ".join(text.split())

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

            # TODO: Trigger next stage (AI Analysis)
            # analyze_document.send(str(workflow_id))

        except Exception as e:
            await db.rollback()
            logger.error("Extraction failed", workflow_id=str(workflow_uuid), error=str(e))
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            await db.commit()
