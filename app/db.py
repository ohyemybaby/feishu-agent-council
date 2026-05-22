from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.schemas import CouncilAnswer, ModelRunResult


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists tasks (
                    id integer primary key autoincrement,
                    feishu_chat_id text not null default '',
                    feishu_message_id text not null default '',
                    user_id text not null default '',
                    task_type text not null,
                    mode text not null,
                    status text not null,
                    created_at text not null default current_timestamp,
                    completed_at text
                );

                create table if not exists model_runs (
                    id integer primary key autoincrement,
                    task_id integer not null,
                    provider text not null,
                    role text not null,
                    model text not null,
                    prompt_tokens integer not null default 0,
                    completion_tokens integer not null default 0,
                    total_tokens integer not null default 0,
                    latency_ms integer not null default 0,
                    output_json text not null,
                    created_at text not null default current_timestamp,
                    foreign key(task_id) references tasks(id)
                );

                create table if not exists final_answers (
                    id integer primary key autoincrement,
                    task_id integer not null,
                    answer_text text not null,
                    answer_json text not null,
                    quality_score real,
                    created_at text not null default current_timestamp,
                    foreign key(task_id) references tasks(id)
                );

                create table if not exists worker_tasks (
                    id integer primary key autoincrement,
                    feishu_chat_id text not null default '',
                    feishu_message_id text not null default '',
                    user_id text not null default '',
                    prompt text not null,
                    status text not null,
                    result_text text not null default '',
                    error_text text not null default '',
                    attempts integer not null default 0,
                    claimed_by text not null default '',
                    claimed_at text,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp,
                    completed_at text
                );
                """
            )

    def create_task(
        self,
        feishu_chat_id: str,
        feishu_message_id: str,
        user_id: str,
        task_type: str,
        mode: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into tasks (feishu_chat_id, feishu_message_id, user_id, task_type, mode, status)
                values (?, ?, ?, ?, ?, 'running')
                """,
                (feishu_chat_id, feishu_message_id, user_id, task_type, mode),
            )
            return int(cursor.lastrowid)

    def complete_task(self, task_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "update tasks set status = ?, completed_at = current_timestamp where id = ?",
                (status, task_id),
            )

    def create_model_run(self, task_id: int, run: ModelRunResult) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into model_runs (
                    task_id, provider, role, model, prompt_tokens, completion_tokens,
                    total_tokens, latency_ms, output_json
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    run.provider,
                    run.role,
                    run.model,
                    run.usage.prompt_tokens,
                    run.usage.completion_tokens,
                    run.usage.total_tokens,
                    run.latency_ms,
                    run.model_dump_json(),
                ),
            )

    def create_final_answer(self, task_id: int, answer: CouncilAnswer) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into final_answers (task_id, answer_text, answer_json)
                values (?, ?, ?)
                """,
                (
                    task_id,
                    answer.to_feishu_text(),
                    json.dumps(answer.model_dump(), ensure_ascii=False),
                ),
            )

    def create_worker_task(
        self,
        feishu_chat_id: str,
        feishu_message_id: str,
        user_id: str,
        prompt: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into worker_tasks (feishu_chat_id, feishu_message_id, user_id, prompt, status)
                values (?, ?, ?, ?, 'pending')
                """,
                (feishu_chat_id, feishu_message_id, user_id, prompt),
            )
            return int(cursor.lastrowid)

    def claim_worker_task(self, worker_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select *
                from worker_tasks
                where status = 'pending'
                   or (status = 'claimed' and datetime(claimed_at, '+15 minutes') < current_timestamp)
                order by id
                limit 1
                """
            ).fetchone()
            if row is None:
                return None

            conn.execute(
                """
                update worker_tasks
                set status = 'claimed',
                    claimed_by = ?,
                    claimed_at = current_timestamp,
                    attempts = attempts + 1,
                    updated_at = current_timestamp
                where id = ?
                """,
                (worker_id, row["id"]),
            )
            updated = conn.execute("select * from worker_tasks where id = ?", (row["id"],)).fetchone()
            return dict(updated) if updated is not None else None

    def complete_worker_task(self, task_id: int, result_text: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            conn.execute(
                """
                update worker_tasks
                set status = 'completed',
                    result_text = ?,
                    error_text = '',
                    updated_at = current_timestamp,
                    completed_at = current_timestamp
                where id = ?
                """,
                (result_text, task_id),
            )
            row = conn.execute("select * from worker_tasks where id = ?", (task_id,)).fetchone()
            return dict(row) if row is not None else None

    def fail_worker_task(self, task_id: int, error_text: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            conn.execute(
                """
                update worker_tasks
                set status = 'failed',
                    error_text = ?,
                    updated_at = current_timestamp,
                    completed_at = current_timestamp
                where id = ?
                """,
                (error_text, task_id),
            )
            row = conn.execute("select * from worker_tasks where id = ?", (task_id,)).fetchone()
            return dict(row) if row is not None else None

    def get_worker_task(self, task_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from worker_tasks where id = ?", (task_id,)).fetchone()
            return dict(row) if row is not None else None
