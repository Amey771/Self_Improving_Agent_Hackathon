from src.integrations.gemini_client import GeminiClient

class LLMPatchAgent:
    def __init__(self):
        self.llm = GeminiClient()

    def suggest_patch(self, file_name: str, file_text: str, incident_summary: str, trace_hypothesis: str) -> str:
        prompt = f"""
You are a senior engineer. Fix the bug described below with a minimal safe patch.

Incident:
{incident_summary}

Hypothesis:
{trace_hypothesis}

Target file: {file_name}

Current file content:
{file_text}

Requirements:
- Return ONLY the updated full file content (no markdown, no explanations)
- Minimal change, no refactors
- Add guardrails to prevent division-by-zero
- Keep behavior same otherwise
"""
        return self.llm.generate(prompt)