DOCUMENT_ANALYSIS_V1 = """
Extract structured information from the following document.
Return ONLY valid JSON according to the schema below.

Output Schema:
{
  "title": "string",
  "summary": "string",
  "document_type": "string",
  "key_facts": [
    {"label": "string", "value": "string", "confidence": float}
  ],
  "risks": [
    {"description": "string", "severity": "low|medium|high", "confidence": float}
  ],
  "recommended_action": "string"
}

Document Content:
{{text}}
"""

PROMPT_TEMPLATES = {
    "document_analysis": {
        "v1": DOCUMENT_ANALYSIS_V1
    }
}
