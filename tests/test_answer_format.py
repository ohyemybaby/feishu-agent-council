from app.schemas import CouncilAnswer


def test_feishu_text_contains_sections() -> None:
    answer = CouncilAnswer(
        conclusion="建议做。",
        best_ideas=["先做 MVP"],
        feasibility="高",
        risks=["成本失控"],
        assumptions=["有 API key"],
        next_actions=["接飞书"],
    )
    text = answer.to_feishu_text()
    assert "结论：" in text
    assert "最佳观点：" in text
    assert "下一步：" in text

