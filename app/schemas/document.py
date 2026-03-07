from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class DocumentBase(BaseModel):
    filename: str
    content_type: str
    size_bytes: int

class DocumentResponse(DocumentBase):
    id: UUID
    workflow_id: UUID
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UploadResponse(BaseModel):
    document_id: UUID
    workflow_id: UUID
    status: str
