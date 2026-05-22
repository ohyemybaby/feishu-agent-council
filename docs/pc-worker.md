# PC Codex Worker

This mode lets Feishu send tasks to a Render queue, then a worker running on the user's PC claims tasks, runs local Codex CLI, and sends the result back to Feishu.

## 1. Render Environment

Set these variables in Render:

```text
PC_WORKER_ENABLED=true
WORKER_TOKEN=<a long random secret>
FEISHU_DRY_RUN=false
```

Keep `WORKER_TOKEN` private. The PC worker must use the same value.

When `PC_WORKER_ENABLED=true`, Feishu messages are not sent to GLM/DeepSeek. They are queued for the PC worker.

## 2. PC Prerequisites

On the PC:

```powershell
codex --help
codex login
```

Confirm `codex exec` works:

```powershell
codex exec --skip-git-repo-check "用一句中文回复：Codex worker ready"
```

## 3. Start the Worker

From this project folder:

```powershell
$env:WORKER_SERVER_URL="https://feishu-agent-council.onrender.com"
$env:WORKER_TOKEN="<same token as Render>"
$env:CODEX_WORKSPACE="C:\Users\william\Documents\Codex\pc-worker-workspace"
$env:WORKER_POLL_SECONDS="8"
python scripts/pc_worker.py
```

Keep this terminal open. When a Feishu message arrives, Render queues it and this worker claims it.

## 4. Test from Feishu

Send a private message to the bot:

```text
请用一句话说明你是否收到这条任务
```

Expected flow:

1. Bot replies that task was queued.
2. PC terminal prints `Claimed task`.
3. Codex runs locally.
4. Bot sends the final result back to Feishu.

## 5. Safety Notes

The worker runs Codex with:

```text
--sandbox workspace-write
--ask-for-approval never
```

It should only write inside `CODEX_WORKSPACE`. Do not point `CODEX_WORKSPACE` at sensitive folders for early testing.

