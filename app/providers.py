from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.config import settings
from app.schemas import ModelRunResult, ModelUsage


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, name: str, api_key: str, base_url: str, model: str) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def run(
        self,
        role: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float = 0.5,
        json_mode: bool = False,
    ) -> ModelRunResult:
        if settings.mock_providers or not self.api_key:
            return self._mock(role, user_prompt)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        latency_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code >= 400:
            raise ProviderError(f"{self.name} API error {response.status_code}: {response.text[:500]}")

        data = response.json()
        content = data["choices"][0]["message"].get("content", "")
        usage_data = data.get("usage") or {}
        usage = ModelUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
            total_tokens=int(usage_data.get("total_tokens") or 0),
        )
        return ModelRunResult(
            provider=self.name,
            role=role,
            model=self.model,
            content=content,
            usage=usage,
            latency_ms=latency_ms,
            raw=data,
        )

    def _mock(self, role: str, user_prompt: str) -> ModelRunResult:
        if role == "host_synthesizer":
            content = json.dumps(
                {
                    "conclusion": "建议继续做第一版 MVP，但先聚焦飞书里的脑暴决策和可读汇总。",
                    "best_ideas": [
                        "先验证飞书入口、多模型独立分析和主持人汇总这条主链路。",
                        "第一版只接 GLM 和 DeepSeek，降低成本和调试复杂度。",
                        "默认输出短结论，原始模型内容只做存档或调试查看。",
                    ],
                    "feasibility": "技术可行性高；成本和安全风险中等；推荐优先级 A-。",
                    "risks": [
                        "多模型输出过长会降低可读性。",
                        "深度模式如果默认开启，会浪费 token。",
                        "过早加入电脑操作能力会扩大权限风险。",
                    ],
                    "assumptions": [
                        "用户可以创建飞书自建应用并配置事件回调。",
                        "GLM 和 DeepSeek API key 后续可用。",
                    ],
                    "next_actions": [
                        "先用 mock 模式跑通本地接口。",
                        "配置飞书回调并完成 URL verification。",
                        "填入真实 API key 后测试标准模式和深度模式。",
                    ],
                },
                ensure_ascii=False,
            )
            return ModelRunResult(
                provider=self.name,
                role=role,
                model=self.model,
                content=content,
                usage=ModelUsage(
                    prompt_tokens=len(user_prompt) // 2,
                    completion_tokens=len(content) // 2,
                    total_tokens=(len(user_prompt) + len(content)) // 2,
                ),
            )

        content = (
            f"[mock:{self.name}:{role}] 核心判断：这个问题值得分析，但需要先缩小第一版范围。\n"
            "最佳观点：先验证飞书入口、多模型独立分析和可读汇总。\n"
            "风险：token 成本、输出过长、权限边界不清。\n"
            "下一步：做 MVP、记录反馈、再扩展执行能力。"
        )
        return ModelRunResult(
            provider=self.name,
            role=role,
            model=self.model,
            content=content,
            usage=ModelUsage(
                prompt_tokens=len(user_prompt) // 2,
                completion_tokens=len(content) // 2,
                total_tokens=(len(user_prompt) + len(content)) // 2,
            ),
        )


def get_providers() -> dict[str, OpenAICompatibleProvider]:
    return {
        "glm": OpenAICompatibleProvider(
            name="glm",
            api_key=settings.glm_api_key,
            base_url=settings.glm_base_url,
            model=settings.glm_model,
        ),
        "deepseek": OpenAICompatibleProvider(
            name="deepseek",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
    }


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
