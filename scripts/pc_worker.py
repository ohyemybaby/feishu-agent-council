from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx


SERVER_URL = os.getenv("WORKER_SERVER_URL", "https://feishu-agent-council.onrender.com").rstrip("/")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "")
WORKER_ID = os.getenv("WORKER_ID", "pc-codex-worker")
CODEX_WORKSPACE = Path(os.getenv("CODEX_WORKSPACE", os.getcwd()))
CODEX_MODEL = os.getenv("CODEX_MODEL", "")
CODEX_COMMAND = os.getenv("CODEX_COMMAND", "")
CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "1800"))
WORKER_POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "8"))


def headers() -> dict[str, str]:
    if not WORKER_TOKEN:
        raise RuntimeError("WORKER_TOKEN is required")
    return {"Authorization": f"Bearer {WORKER_TOKEN}"}


def claim_task() -> dict | None:
    response = httpx.post(
        f"{SERVER_URL}/worker/claim",
        json={"worker_id": WORKER_ID},
        headers=headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("task")


def post_result(task_id: int, status: str, result: str = "", error: str = "") -> None:
    response = httpx.post(
        f"{SERVER_URL}/worker/result",
        json={"task_id": task_id, "status": status, "result": result, "error": error},
        headers=headers(),
        timeout=60,
    )
    response.raise_for_status()


def run_codex(prompt: str) -> str:
    CODEX_WORKSPACE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as output_file:
        output_path = Path(output_file.name)

    worker_prompt = f"""You are running on the user's PC as a Feishu-triggered Codex worker.

Safety rules:
- Work only inside the configured workspace unless the user explicitly asks otherwise.
- Do not delete files, change system settings, install unknown scripts, push code, or expose secrets.
- If the task is risky or underspecified, explain what you need instead of taking risky action.
- End with a concise Chinese summary suitable for sending back to Feishu.

User task from Feishu:
{prompt}
"""

    codex_command = resolve_codex_command()
    command = [
        codex_command,
        "exec",
        "--cd",
        str(CODEX_WORKSPACE),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
    ]
    if CODEX_MODEL:
        command.extend(["--model", CODEX_MODEL])
    command.append(worker_prompt)

    completed = subprocess.run(
        command,
        cwd=CODEX_WORKSPACE,
        text=True,
        capture_output=True,
        timeout=CODEX_TIMEOUT_SECONDS,
    )

    final_message = output_path.read_text(encoding="utf-8", errors="replace").strip()
    output_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(details[-4000:] or f"codex exited with status {completed.returncode}")

    return final_message or (completed.stdout or "").strip() or "Codex finished, but did not return a final message."


def resolve_codex_command() -> str:
    if CODEX_COMMAND:
        command_path = Path(CODEX_COMMAND)
        if command_path.exists():
            return str(command_path)
        found = shutil.which(CODEX_COMMAND)
        if found:
            return found
        raise RuntimeError(f"CODEX_COMMAND not found: {CODEX_COMMAND}")

    candidates = [
        "codex.cmd",
        "codex.exe",
        "codex",
    ]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

    common_paths = [
        Path.home() / "AppData/Roaming/npm/codex.cmd",
        Path.home() / "AppData/Roaming/npm/codex",
    ]
    for candidate in common_paths:
        if candidate.exists():
            return str(candidate)

    raise RuntimeError(
        "Codex CLI was not found. Set CODEX_COMMAND to the full path of codex.cmd or codex.exe."
    )


def main() -> None:
    print(f"PC worker started. server={SERVER_URL} workspace={CODEX_WORKSPACE}")
    print(f"Codex command: {resolve_codex_command()}")
    while True:
        try:
            task = claim_task()
            if task is None:
                time.sleep(WORKER_POLL_SECONDS)
                continue

            task_id = int(task["id"])
            prompt = str(task["prompt"])
            print(f"Claimed task #{task_id}: {prompt[:120]}")
            try:
                result = run_codex(prompt)
                post_result(task_id, "completed", result=result)
                print(f"Completed task #{task_id}")
            except Exception as exc:
                post_result(task_id, "failed", error=str(exc))
                print(f"Failed task #{task_id}: {exc}")
        except KeyboardInterrupt:
            print("PC worker stopped.")
            break
        except Exception as exc:
            print(f"Worker loop error: {exc}")
            time.sleep(WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()
