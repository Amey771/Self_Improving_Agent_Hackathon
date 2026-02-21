import difflib
import subprocess
from pathlib import Path


class FixAgent:
    """
    Generates a unified-diff patch for a target file and applies it
    safely via ``git apply --3way``.

    The ``--3way`` flag tells git to fall back to a 3-way merge when
    context lines don't match exactly, which prevents the common
    "patch does not apply" RuntimeError.
    """

    def generate_patch(self, target_file: str, old_snippet: str, new_snippet: str) -> str:
        """
        Build a minimal unified diff that replaces *old_snippet* with
        *new_snippet* inside *target_file*.

        Returns the patch text (suitable for ``git apply``).
        """
        path = Path(target_file)
        if not path.exists():
            raise FileNotFoundError(f"Target file not found: {target_file}")

        original = path.read_text()
        if old_snippet not in original:
            raise ValueError(
                f"The snippet to replace was not found in {target_file}.\n"
                "Make sure the old snippet matches the file exactly (including indentation)."
            )

        if original.count(old_snippet) > 1:
            raise ValueError(
                f"The snippet to replace appears multiple times in {target_file}. "
                "Provide a more specific snippet to uniquely identify the location."
            )

        patched = original.replace(old_snippet, new_snippet, 1)

        diff_lines = list(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=f"a/{target_file}",
                tofile=f"b/{target_file}",
            )
        )
        if not diff_lines:
            return ""
        return "".join(diff_lines)

    def apply_patch(self, patch_text: str, repo_root: str = ".") -> str:
        """
        Apply *patch_text* using ``git apply --3way``.

        ``--3way`` allows git to fall back to a 3-way merge when the
        patch context doesn't match exactly, avoiding the
        "patch does not apply" error.

        Returns a success message or raises RuntimeError with details.
        """
        if not patch_text.strip():
            return "Patch is empty – nothing to apply."

        try:
            result = subprocess.run(
                ["git", "apply", "--3way", "-"],
                input=patch_text,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
        except FileNotFoundError:
            raise RuntimeError("git is not available in this environment.")

        if result.returncode != 0:
            # If the file is not yet tracked by git, fall back to --no-index
            if "does not exist in index" in result.stderr:
                result = subprocess.run(
                    ["git", "apply", "--no-index", "-"],
                    input=patch_text,
                    capture_output=True,
                    text=True,
                    cwd=repo_root,
                )
            if result.returncode != 0:
                raise RuntimeError(
                    f"git apply failed:\n{result.stderr.strip()}"
                )

        return "Patch applied successfully."

    def fix_file(
        self,
        target_file: str,
        old_snippet: str,
        new_snippet: str,
        repo_root: str = ".",
    ) -> str:
        """
        Convenience method: generate a patch for *target_file* that
        replaces *old_snippet* with *new_snippet*, then apply it.

        Returns a summary string.
        """
        patch = self.generate_patch(target_file, old_snippet, new_snippet)
        if not patch:
            return "No changes detected – old and new snippets are identical."
        result = self.apply_patch(patch, repo_root=repo_root)
        return result
