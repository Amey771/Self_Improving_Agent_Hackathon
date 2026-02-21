from pathlib import Path
from src.core.local_patch import apply_replace_patch

class FixAgent:
    def apply_div0_guard_local(self, file_path: str) -> str:
        """
        Directly edits billing.py: inserts guard before division.
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()

        target_idx = None
        for i, line in enumerate(lines):
            if "taxed / installments" in line or "/ installments" in line:
                target_idx = i
                break

        if target_idx is None:
            raise ValueError("Could not find division line to patch")

        indent = lines[target_idx][:len(lines[target_idx]) - len(lines[target_idx].lstrip())]

        guard = [
            f"{indent}if installments == 0:",
            f"{indent}    raise ValueError(\"Installments cannot be zero\")",
            ""
        ]

        new_lines = lines[:target_idx] + guard + lines[target_idx:]
        p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return "Local patch applied: added installments == 0 guard."