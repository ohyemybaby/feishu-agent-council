from app.modes import detect_mode
from app.schemas import TaskMode


def test_detect_quick_command() -> None:
    mode, question = detect_mode("/快答 这个项目值不值得做")
    assert mode == TaskMode.QUICK
    assert question == "这个项目值不值得做"


def test_detect_deep_natural_language() -> None:
    mode, question = detect_mode("帮我深度分析这个飞书 agent 项目")
    assert mode == TaskMode.DEEP
    assert "飞书 agent" in question


def test_short_question_defaults_to_quick() -> None:
    mode, _ = detect_mode("值不值得做？")
    assert mode == TaskMode.QUICK

