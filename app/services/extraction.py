import io
import fitz  # PyMuPDF
from docx import Document as DocxDocument
import structlog

logger = structlog.get_logger()

class ExtractionService:
    @staticmethod
    def extract_text(file_bytes: bytes, content_type: str) -> str:
        """Extract text from bytes based on content type and normalize it."""
        try:
            text = ""
            if content_type == "application/pdf":
                text = ExtractionService._extract_from_pdf(file_bytes)
            elif content_type == "text/plain":
                text = file_bytes.decode("utf-8")
            elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                text = ExtractionService._extract_from_docx(file_bytes)
            else:
                logger.error("Unsupported content type for extraction", content_type=content_type)
                raise ValueError(f"Unsupported content type: {content_type}")

            return ExtractionService._normalize_text(text)
        except Exception as e:
            logger.error("Text extraction failed", content_type=content_type, error=str(e))
            raise

    @staticmethod
    def _extract_from_pdf(file_bytes: bytes) -> str:
        text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text

    @staticmethod
    def _extract_from_docx(file_bytes: bytes) -> str:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join([para.text for para in doc.paragraphs])

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Remove extra whitespace, newlines, and non-printable characters."""
        # Replace multiple whitespace/newlines with a single space
        normalized = " ".join(text.split())
        return normalized.strip()

extraction_service = ExtractionService()
