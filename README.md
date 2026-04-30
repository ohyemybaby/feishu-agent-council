# Feishu Agent Council

Feishu Agent Council is a local MVP for a Feishu-based multi-model assistant. The first phase focuses on brainstorming and decision analysis with GLM and DeepSeek.

## What Works Now

- FastAPI backend.
- `/ask` local test endpoint.
- Feishu event callback endpoint.
- Feishu URL verification response.
- Feishu text message reply client.
- GLM and DeepSeek OpenAI-compatible provider adapters.
- Quick, standard, and deep modes.
- SQLite task, model-run, and final-answer records.
- Mock provider mode for local testing without API keys.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
```

Edit `.env` and set real keys when ready.

For first local testing, keep:

```text
MOCK_PROVIDERS=true
FEISHU_DRY_RUN=true
```

## Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Local ask test:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/ask `
  -ContentType 'application/json' `
  -Body '{"question":"/深度 分析这个飞书多 Agent 项目值不值得做"}'
```

## Feishu Wiring

Create a Feishu internal app, enable bot capability, configure event subscription, and point the callback URL to:

```text
https://your-public-domain/webhooks/feishu
```

For local development, expose port `8000` using a tunnel such as `ngrok` or a cloud dev tunnel.

If local tunnels are blocked, deploy the service to Render Free. See:

```text
docs/deploy-render.md
```

Required environment variables for real Feishu sending:

```text
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_DRY_RUN=false
```

Required provider variables for real model calls:

```text
MOCK_PROVIDERS=false
GLM_API_KEY=
DEEPSEEK_API_KEY=
```

## Notes

- MVP does not execute local commands or modify files.
- Phase B will add read-only computer/code diagnostics with explicit confirmation for risky actions.
- Phase C will add CSV/Excel/Feishu Sheets analysis and forecasting.
