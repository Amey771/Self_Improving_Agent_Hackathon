from pathlib import Path
from dataclasses import dataclass

@dataclass
class PatchResult:
    file_path: str
    applied: bool
    message: str
    diff_preview: str


class FixAgent:
    """
    Minimal patcher for demo:
    - looks for 'taxed / installments' line
    - inserts a guard for installments == 0
    """

    def propose_and_apply_div0_guard(self, file_path: str, dry_run: bool = True) -> PatchResult:
        path = Path(file_path)
        if not path.exists():
            return PatchResult(str(file_path), False, "File not found", "")

        original = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        target_idx = None
        for i, line in enumerate(original):
            if "/ installments" in line or " /installments" in line or "taxed / installments" in line:
                target_idx = i
                break

        if target_idx is None:
            return PatchResult(str(file_path), False, "Could not find division line to patch", "")

        indent = original[target_idx].split("p")[0] if original[target_idx].lstrip() != original[target_idx] else ""
        # Better indent detection
        indent = original[target_idx][:len(original[target_idx]) - len(original[target_idx].lstrip())]

        guard_lines = [
            f"{indent}if installments == 0:",
            f"{indent}    raise ValueError(\"Installments cannot be zero\")",
            ""
        ]

        patched = original[:target_idx] + guard_lines + original[target_idx:]

        diff_preview = self._make_simple_diff(original, patched, path.name)

        if dry_run:
            return PatchResult(str(file_path), False, "Dry run: patch proposed (not applied)", diff_preview)

        path.write_text("\n".join(patched) + "\n", encoding="utf-8")
        return PatchResult(str(file_path), True, "Patch applied successfully", diff_preview)

    def _make_simple_diff(self, before, after, filename: str) -> str:
        # Simple readable diff (not full unified diff, but good for demo)
        out = [f"FILE: {filename}", "", "---- BEFORE (snippet) ----"]
        start = max(0, len(before) - 30)
        out += before[start:start + 30]
        out += ["", "---- AFTER (snippet) ----"]
        out += after[start:start + 35]
        return "\n".join(out)