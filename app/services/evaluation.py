from app.schemas.analysis import DocumentAnalysis
import structlog

logger = structlog.get_logger()

class EvaluationService:
    @staticmethod
    def calculate_score(analysis: DocumentAnalysis) -> float:
        """Calculate an evaluation score (0.0 - 1.0) based on analysis quality."""
        try:
            # 1. Completeness Score (0.4 weight)
            # Basic check: are there key facts and risks?
            completeness = 0.0
            if analysis.key_facts:
                completeness += 0.5
            if analysis.risks:
                completeness += 0.5
            
            # 2. Confidence Score (0.6 weight)
            # Average of confidence scores across facts and risks
            all_confidences = [f.confidence for f in analysis.key_facts] + [r.confidence for r in analysis.risks]
            
            if not all_confidences:
                confidence_avg = 0.0
            else:
                confidence_avg = sum(all_confidences) / len(all_confidences)

            # Final weighted score
            score = (completeness * 0.4) + (confidence_avg * 0.6)
            
            return round(score, 2)
        except Exception as e:
            logger.error("Scoring failed", error=str(e))
            return 0.0

evaluation_service = EvaluationService()
