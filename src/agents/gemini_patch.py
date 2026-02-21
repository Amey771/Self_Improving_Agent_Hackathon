from pathlib import Path
from src.integrations.gemini_client import GeminiClient

class GeminiPatchAgent:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def propose_patch_unified_diff(self, file_path: str, snippet: str, goal: str) -> str:
        """
        Returns a unified diff that can be applied with `git apply`.
        """
        file_name = Path(file_path).name

        prompt = f"""
You are a senior engineer. Create a minimal safe patch.

Goal: {goal}

File name: {file_name}

Context snippet (may be partial):
{snippet}

Rules:
- Output ONLY a unified diff that modifies {file_name}
- Do not add unrelated refactors
- Add input validation / guardrails
- Keep the patch as small as possible
- The diff must start with: --- a/{file_name} and +++ b/{file_name}

Now produce the unified diff:
"""
        return self.gemini.generate(prompt).strip()