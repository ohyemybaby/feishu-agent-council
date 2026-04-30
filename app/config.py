from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency safety
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().strip('"').strip("'").lower()
    return normalized in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_path: Path = Path(os.getenv("DATABASE_PATH", "./data/agent_council.sqlite3"))
    mock_providers: bool = _bool_env("MOCK_PROVIDERS", True)

    feishu_app_id: str = os.getenv("FEISHU_APP_ID", "")
    feishu_app_secret: str = os.getenv("FEISHU_APP_SECRET", "")
    feishu_verification_token: str = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
    feishu_dry_run: bool = _bool_env("FEISHU_DRY_RUN", True)

    glm_api_key: str = os.getenv("GLM_API_KEY", "")
    glm_base_url: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    glm_model: str = os.getenv("GLM_MODEL", "glm-5.1")

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    default_max_tokens: int = int(os.getenv("DEFAULT_MAX_TOKENS", "900"))
    deep_max_tokens: int = int(os.getenv("DEEP_MAX_TOKENS", "1200"))
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))


settings = Settings()
