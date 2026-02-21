import subprocess
from pathlib import Path

def apply_unified_diff(repo_path: str, diff_text: str) -> None:
    repo = Path(repo_path)
    proc = subprocess.run(
        ["git", "apply", "-"],
        input=diff_text.encode("utf-8"),
        cwd=str(repo),
        capture_output=True
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8")[:800])