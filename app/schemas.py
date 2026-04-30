from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskMode(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ProviderName(StrEnum):
    GLM = "glm"
    DEEPSEEK = "deepseek"
    MOCK = "mock"


class ModelUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ModelRunResult(BaseModel):
    provider: str
    role: str
    model: str
    content: str
    usage: ModelUsage = Field(default_factory=ModelUsage)
    latency_ms: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


class CouncilAnswer(BaseModel):
    conclusion: str
    best_ideas: list[str] = Field(default_factory=list)
    feasibility: str
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)

    def to_feishu_text(self) -> str:
        lines = [
            "结论：",
            self.conclusion.strip(),
            "",
            "最佳观点：",
        ]
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(self.best_ideas, start=1))
        lines.extend(["", "可行性：", self.feasibility.strip(), "", "主要风险："])
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(self.risks, start=1))
        if self.assumptions:
            lines.extend(["", "关键假设："])
            lines.extend(f"{idx}. {item}" for idx, item in enumerate(self.assumptions, start=1))
        lines.extend(["", "下一步："])
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(self.next_actions, start=1))
        return "\n".join(lines)


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: str
    message_id: str
    user_id: str
    text: str
    raw: dict[str, Any]

