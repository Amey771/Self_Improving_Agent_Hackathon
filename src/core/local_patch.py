from pathlib import Path

def apply_replace_patch(file_path: str, old_text: str, new_text: str) -> None:
    """
    Simple safe patch: replace a known block with a new block.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = p.read_text(encoding="utf-8", errors="ignore")

    if old_text not in content:
        raise ValueError("Old text block not found in file. Patch not applied.")

    updated = content.replace(old_text, new_text, 1)
    p.write_text(updated, encoding="utf-8")