from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db import Database
from app.feishu import FeishuClient
from app.orchestrator import AgentCouncil

app = FastAPI(title="Feishu Agent Council", version="0.1.0")
db = Database(settings.database_path)
feishu = FeishuClient()
council = AgentCouncil(db)


class AskRequest(BaseModel):
    question: str


class WorkerClaimRequest(BaseModel):
    worker_id: str = "pc-worker"


class WorkerResultRequest(BaseModel):
    task_id: int
    status: str
    result: str = ""
    error: str = ""


def require_worker_token(authorization: str | None) -> None:
    if not settings.worker_token:
        raise HTTPException(status_code=503, detail="WORKER_TOKEN is not configured")
    expected = f"Bearer {settings.worker_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid worker token")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mock_providers": settings.mock_providers,
        "feishu_dry_run": settings.feishu_dry_run,
        "pc_worker_enabled": settings.pc_worker_enabled,
    }


@app.get("/debug/config")
async def debug_config() -> dict[str, Any]:
    return {
        "mock_providers": settings.mock_providers,
        "feishu_dry_run": settings.feishu_dry_run,
        "pc_worker_enabled": settings.pc_worker_enabled,
        "worker_token_configured": bool(settings.worker_token),
        "glm_configured": bool(settings.glm_api_key),
        "deepseek_configured": bool(settings.deepseek_api_key),
        "glm_model": settings.glm_model,
        "deepseek_model": settings.deepseek_model,
        "database_path": str(settings.database_path),
    }


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, Any]:
    answer = await council.handle_question(request.question)
    return {"answer": answer.model_dump(), "text": answer.to_feishu_text()}


@app.post("/worker/claim")
async def worker_claim(
    request: WorkerClaimRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_worker_token(authorization)
    task = db.claim_worker_task(request.worker_id)
    if task is None:
        return {"task": None}
    return {
        "task": {
            "id": task["id"],
            "prompt": task["prompt"],
            "attempts": task["attempts"],
            "created_at": task["created_at"],
        }
    }


@app.post("/worker/result")
async def worker_result(
    request: WorkerResultRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_worker_token(authorization)
    if request.status == "completed":
        task = db.complete_worker_task(request.task_id, request.result)
        reply = f"PC Codex 完成任务 #{request.task_id}：\n\n{request.result}"
    else:
        task = db.fail_worker_task(request.task_id, request.error or request.result or "Unknown worker error")
        reply = f"PC Codex 执行任务 #{request.task_id} 失败：\n\n{request.error or request.result or 'Unknown worker error'}"

    if task is None:
        raise HTTPException(status_code=404, detail="Worker task not found")
    if task["feishu_chat_id"]:
        await feishu.send_text(task["feishu_chat_id"], reply[:9000])
    return {"ok": True}


@app.post("/webhooks/feishu")
async def feishu_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("type") == "url_verification" and "challenge" in payload:
        if not feishu.verify_token(payload):
            raise HTTPException(status_code=403, detail="Invalid Feishu verification token")
        return {"challenge": payload["challenge"]}

    if not feishu.verify_token(payload):
        raise HTTPException(status_code=403, detail="Invalid Feishu verification token")

    incoming = feishu.parse_incoming(payload)
    if incoming is None:
        return {"ok": True, "ignored": True}

    if settings.pc_worker_enabled:
        task_id = db.create_worker_task(
            feishu_chat_id=incoming.chat_id,
            feishu_message_id=incoming.message_id,
            user_id=incoming.user_id,
            prompt=incoming.text,
        )
        await feishu.send_text(
            incoming.chat_id,
            f"已收到任务 #{task_id}，正在等待你的 PC Codex worker 接单处理。完成后我会把结果发回来。",
        )
        return {"ok": True, "queued": True, "task_id": task_id}

    answer = await council.handle_question(
        incoming.text,
        source={"chat_id": incoming.chat_id, "message_id": incoming.message_id, "user_id": incoming.user_id},
    )
    await feishu.send_text(incoming.chat_id, answer.to_feishu_text())
    return {"ok": True}
