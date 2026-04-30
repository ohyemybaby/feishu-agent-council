from __future__ import annotations

import asyncio
import json

from app.config import settings
from app.db import Database
from app.modes import detect_mode
from app.prompts import ANALYST_SYSTEM_PROMPT, SKEPTIC_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from app.prompts import analyst_prompt, critique_prompt, synthesis_prompt
from app.providers import get_providers, parse_json_object
from app.schemas import CouncilAnswer, ModelRunResult, TaskMode


class AgentCouncil:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.providers = get_providers()

    async def handle_question(self, text: str, source: dict[str, str] | None = None) -> CouncilAnswer:
        mode, cleaned_question = detect_mode(text)
        task_id = self.db.create_task(
            feishu_chat_id=(source or {}).get("chat_id", ""),
            feishu_message_id=(source or {}).get("message_id", ""),
            user_id=(source or {}).get("user_id", ""),
            task_type="brainstorming",
            mode=mode.value,
        )

        try:
            answer, runs = await self._run_council(cleaned_question, mode)
            for run in runs:
                self.db.create_model_run(task_id, run)
            self.db.create_final_answer(task_id, answer)
            self.db.complete_task(task_id, "completed")
            return answer
        except Exception:
            self.db.complete_task(task_id, "failed")
            raise

    async def _run_council(self, question: str, mode: TaskMode) -> tuple[CouncilAnswer, list[ModelRunResult]]:
        max_tokens = settings.deep_max_tokens if mode == TaskMode.DEEP else settings.default_max_tokens

        if mode == TaskMode.QUICK:
            glm = self.providers["glm"]
            analyst_runs = [
                await glm.run(
                    role="strategy_analyst",
                    system_prompt=ANALYST_SYSTEM_PROMPT,
                    user_prompt=analyst_prompt("strategy analyst", question),
                    max_tokens=max_tokens,
                    temperature=0.4,
                )
            ]
        else:
            analyst_runs = await asyncio.gather(
                self.providers["glm"].run(
                    role="strategy_analyst",
                    system_prompt=ANALYST_SYSTEM_PROMPT,
                    user_prompt=analyst_prompt("strategy analyst", question),
                    max_tokens=max_tokens,
                    temperature=0.5,
                ),
                self.providers["deepseek"].run(
                    role="engineering_analyst",
                    system_prompt=ANALYST_SYSTEM_PROMPT,
                    user_prompt=analyst_prompt("engineering analyst", question),
                    max_tokens=max_tokens,
                    temperature=0.4,
                ),
            )

        runs: list[ModelRunResult] = list(analyst_runs)
        model_outputs = self._format_runs(analyst_runs)
        critiques = ""

        if mode == TaskMode.DEEP:
            critic_run = await self.providers["deepseek"].run(
                role="skeptic",
                system_prompt=SKEPTIC_SYSTEM_PROMPT,
                user_prompt=critique_prompt(question, model_outputs),
                max_tokens=settings.default_max_tokens,
                temperature=0.3,
            )
            runs.append(critic_run)
            critiques = critic_run.content

        synthesis_run = await self.providers["glm"].run(
            role="host_synthesizer",
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            user_prompt=synthesis_prompt(question, mode.value, model_outputs, critiques),
            max_tokens=settings.default_max_tokens,
            temperature=0.2,
            json_mode=True,
        )
        runs.append(synthesis_run)

        answer = self._answer_from_synthesis(synthesis_run.content)
        return answer, runs

    @staticmethod
    def _format_runs(runs: list[ModelRunResult]) -> str:
        return "\n\n".join(
            f"Provider: {run.provider}\nRole: {run.role}\nOutput:\n{run.content}" for run in runs
        )

    @staticmethod
    def _answer_from_synthesis(content: str) -> CouncilAnswer:
        try:
            data = parse_json_object(content)
            return CouncilAnswer.model_validate(data)
        except Exception:
            return CouncilAnswer(
                conclusion="已完成多模型分析，但汇总器没有返回严格 JSON；以下是压缩后的原始结论。",
                best_ideas=[content[:700]],
                feasibility="需要人工复核。",
                risks=["结构化解析失败。", "建议检查模型输出格式或关闭 mock 后重新测试。"],
                assumptions=["模型输出可作为初步参考。"],
                next_actions=["检查日志。", "优化 synthesis prompt。"],
            )

