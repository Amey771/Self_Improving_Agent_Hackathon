def compute_metrics(before_text: str, after_text: str) -> dict:
    def count_guard(t: str) -> int:
        return t.count("if installments == 0")

    metrics = {
        "guard_count_before": count_guard(before_text),
        "guard_count_after": count_guard(after_text),
        "added_lines": max(0, len(after_text.splitlines()) - len(before_text.splitlines())),
    }
    metrics["duplicate_guard"] = metrics["guard_count_after"] > 1
    metrics["patch_applied"] = before_text != after_text
    return metrics