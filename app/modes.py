from __future__ import annotations

from app.schemas import TaskMode


def detect_mode(text: str) -> tuple[TaskMode, str]:
    stripped = text.strip()
    lowered = stripped.lower()

    triggers = {
        TaskMode.QUICK: ["/quick", "/快答", "/省token", "/save-token", "简单说", "简短"],
        TaskMode.DEEP: ["/deep", "/深度", "深度分析", "辩论", "debate", "deep analysis"],
        TaskMode.STANDARD: ["/standard", "/标准"],
    }

    for mode, words in triggers.items():
        for word in words:
            if lowered.startswith(word.lower()):
                return mode, stripped[len(word) :].strip(" ：:")
            if word.lower() in lowered and mode == TaskMode.DEEP:
                return mode, stripped

    if len(stripped) <= 80:
        return TaskMode.QUICK, stripped
    return TaskMode.STANDARD, stripped

