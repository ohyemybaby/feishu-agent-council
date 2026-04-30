from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
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


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mock_providers": settings.mock_providers,
        "feishu_dry_run": settings.feishu_dry_run,
    }


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, Any]:
    answer = await council.handle_question(request.question)
    return {"answer": answer.model_dump(), "text": answer.to_feishu_text()}


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

    answer = await council.handle_question(
        incoming.text,
        source={"chat_id": incoming.chat_id, "message_id": incoming.message_id, "user_id": incoming.user_id},
    )
    await feishu.send_text(incoming.chat_id, answer.to_feishu_text())
    return {"ok": True}

