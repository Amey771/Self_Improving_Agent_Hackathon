from pathlib import Path

def apply_full_file_patch(file_path: str, new_content: str) -> None:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not new_content or len(new_content.strip()) < 10:
        raise ValueError("LLM patch content looks empty/invalid")

    p.write_text(new_content, encoding="utf-8")