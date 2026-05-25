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
CODEX_WORKSPACE_ROOT = os.getenv("CODEX_WORKSPACE_ROOT", "")
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
    workspace, cleaned_prompt = resolve_workspace(prompt)
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as output_file:
        output_path = Path(output_file.name)

    worker_prompt = f"""立即执行下面这个来自飞书的用户任务。不要只回复 Ready，不要只表示你已理解。

当前工作目录就是允许操作的目录。你可以读取、创建和修改当前工作目录内的文件。

安全规则：
- 只在当前工作目录内工作，除非用户明确指定其他路径。
- 不要删除文件、修改系统设置、安装未知脚本、推送代码或暴露密钥。
- 如果任务有风险或信息不足，就说明原因和需要用户补充什么。
- 完成后用简洁中文总结你实际做了什么，并给出相关文件路径。

用户任务：
{cleaned_prompt}
"""

    codex_command = resolve_codex_command()
    command = [
        codex_command,
        "exec",
        "--cd",
        str(workspace),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
    ]
    if CODEX_MODEL:
        command.extend(["--model", CODEX_MODEL])
    command.append("-")

    print("Running Codex command:", " ".join(command[:-1]), "<prompt>")

    completed = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        input=worker_prompt,
        timeout=CODEX_TIMEOUT_SECONDS,
    )

    final_message = output_path.read_text(encoding="utf-8", errors="replace").strip()
    output_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(details[-4000:] or f"codex exited with status {completed.returncode}")

    return final_message or (completed.stdout or "").strip() or "Codex finished, but did not return a final message."


def resolve_workspace(prompt: str) -> tuple[Path, str]:
    base = workspace_base().resolve()
    cleaned_prompt = prompt.strip()

    project_prefixes = ["/project", "project:", "项目：", "项目:"]
    selected_project = ""
    for prefix in project_prefixes:
        if cleaned_prompt.lower().startswith(prefix.lower()):
            rest = cleaned_prompt[len(prefix) :].strip()
            if rest:
                parts = rest.split(maxsplit=1)
                selected_project = parts[0].strip().strip('"').strip("'")
                cleaned_prompt = parts[1].strip() if len(parts) > 1 else ""
            break

    if not selected_project:
        return base, cleaned_prompt

    if ":" in selected_project or selected_project.startswith(("\\", "/")):
        raise RuntimeError("Project must be a relative directory under the allowed workspace root.")

    candidate = (base / selected_project).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise RuntimeError("Project path escapes the allowed workspace root.")

    if not candidate.exists():
        raise RuntimeError(f"Project does not exist under workspace root: {selected_project}")
    if not candidate.is_dir():
        raise RuntimeError(f"Project is not a directory: {selected_project}")

    return candidate, cleaned_prompt


def workspace_base() -> Path:
    if CODEX_WORKSPACE_ROOT:
        return Path(CODEX_WORKSPACE_ROOT)
    return CODEX_WORKSPACE


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
    print(f"PC worker started. server={SERVER_URL} workspace={workspace_base()}")
    if CODEX_WORKSPACE_ROOT:
        print("Project routing enabled. Use: /project <subdir> <task>")
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
