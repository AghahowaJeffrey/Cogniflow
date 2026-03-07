import hashlib
import uuid
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import storage_service
from app.models.base import Document, Workflow, WorkflowStatus
from app.schemas.document import UploadResponse

router = APIRouter()
logger = structlog.get_logger()

ALLOWED_MIME_TYPES = ["application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/documents", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {MAX_FILE_SIZE / (1024 * 1024)}MB"
        )

    # Calculate checksum
    checksum = hashlib.sha256(file_content).hexdigest()
    
    # Generate storage key
    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    storage_key = f"uploads/{uuid.uuid4()}.{file_extension}"

    try:
        # Store in S3/MinIO
        await storage_service.upload_file(file_content, storage_key, file.content_type)
        
        # Create Document record
        new_doc = Document(
            filename=file.filename,
            content_type=file.content_type,
            storage_key=storage_key,
            size_bytes=file_size,
            checksum=checksum
        )
        db.add(new_doc)
        await db.flush()  # Get the ID

        # Create Workflow record
        new_workflow = Workflow(
            document_id=new_doc.id,
            status=WorkflowStatus.PENDING,
            current_stage="pending"
        )
        db.add(new_workflow)
        await db.commit()

        # Trigger background extraction
        from app.worker.tasks import extract_document_content
        extract_document_content.send(str(new_workflow.id))

        logger.info("Document uploaded and extraction enqueued", 
                    document_id=str(new_doc.id), 
                    workflow_id=str(new_workflow.id))

        return UploadResponse(
            document_id=new_doc.id,
            workflow_id=new_workflow.id,
            status=new_workflow.status
        )

    except Exception as e:
        await db.rollback()
        logger.error("Failed to upload document", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing document upload"
        )
