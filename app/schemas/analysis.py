from typing import List, Literal
from pydantic import BaseModel, Field, field_validator

class KeyFact(BaseModel):
    label: str = Field(..., description="Short name for the fact")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0)

class Risk(BaseModel):
    description: str = Field(..., description="Description of the identified risk")
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(..., ge=0.0, le=1.0)

class DocumentAnalysis(BaseModel):
    title: str
    summary: str
    document_type: str
    key_facts: List[KeyFact]
    risks: List[Risk]
    recommended_action: str

    @field_validator("title", "summary", "document_type", "recommended_action")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v
