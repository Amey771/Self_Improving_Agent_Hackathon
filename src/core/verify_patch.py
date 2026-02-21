from pathlib import Path

def verify_div0_guard_exists(file_path: str) -> bool:
    p = Path(file_path)
    if not p.exists():
        return False
    txt = p.read_text(encoding="utf-8", errors="ignore")
    return "if installments == 0" in txt and "Installments cannot be zero" in txt