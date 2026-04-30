from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.config import settings
from app.schemas import IncomingMessage


class FeishuClient:
    def __init__(self) -> None:
        self._tenant_token = ""
        self._tenant_token_expires_at = 0.0

    def verify_token(self, payload: dict[str, Any]) -> bool:
        expected = settings.feishu_verification_token
        if not expected:
            return True
        token = payload.get("token") or payload.get("header", {}).get("token")
        return token == expected

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        event = payload.get("event") or {}
        message = event.get("message") or {}
        chat_id = message.get("chat_id") or ""
        message_id = message.get("message_id") or ""
        sender = event.get("sender") or {}
        sender_id = sender.get("sender_id") or {}
        user_id = sender_id.get("user_id") or sender_id.get("open_id") or ""
        content_raw = message.get("content") or "{}"
        text = ""
        try:
            content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
            text = content.get("text") or ""
        except json.JSONDecodeError:
            text = str(content_raw)

        if not chat_id or not text:
            return None

        return IncomingMessage(
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            text=text,
            raw=payload,
        )

    async def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        if settings.feishu_dry_run:
            return {"dry_run": True, "chat_id": chat_id, "text": text}

        token = await self._get_tenant_access_token()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )

        data = response.json()
        if response.status_code >= 400 or data.get("code") not in (0, None):
            raise RuntimeError(f"Feishu send error: {response.status_code} {data}")
        return data

    async def _get_tenant_access_token(self) -> str:
        if self._tenant_token and time.time() < self._tenant_token_expires_at:
            return self._tenant_token

        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET are required when FEISHU_DRY_RUN=false")

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code") != 0:
            raise RuntimeError(f"Feishu token error: {response.status_code} {data}")

        self._tenant_token = data["tenant_access_token"]
        expire = int(data.get("expire") or 7200)
        self._tenant_token_expires_at = time.time() + max(expire - 120, 60)
        return self._tenant_token

