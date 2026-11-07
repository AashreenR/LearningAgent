from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("learning_coach.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
                UNIQUE (plan_id, position)
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id, id);
            """
        )


def save_message(session_id: str, message: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO chat_messages (session_id, message_json) VALUES (?, ?)",
            (session_id, json.dumps(message)),
        )


def get_history(session_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT message_json FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [json.loads(row["message_json"]) for row in rows]


def create_plan(topic: str, steps: list[dict[str, str]]) -> dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute("INSERT INTO plans (topic) VALUES (?)", (topic,))
        plan_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO steps (plan_id, position, title, url)
            VALUES (?, ?, ?, ?)
            """,
            [
                (plan_id, position, step["title"], step["url"])
                for position, step in enumerate(steps, start=1)
            ],
        )
    return {"id": plan_id, "topic": topic, "steps": len(steps)}


def get_plans() -> list[dict[str, Any]]:
    with _connect() as connection:
        plans = connection.execute(
            "SELECT id, topic, created_at FROM plans ORDER BY id DESC"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for plan in plans:
            steps = connection.execute(
                """
                SELECT id, title, url, done, position
                FROM steps WHERE plan_id = ? ORDER BY position
                """,
                (plan["id"],),
            ).fetchall()
            result.append(
                {
                    "id": plan["id"],
                    "topic": plan["topic"],
                    "created_at": plan["created_at"],
                    "steps": [
                        {
                            "id": step["id"],
                            "title": step["title"],
                            "url": step["url"],
                            "done": bool(step["done"]),
                            "position": step["position"],
                        }
                        for step in steps
                    ],
                }
            )
    return result


def set_step_done(step_id: int, done: bool) -> dict[str, Any] | None:
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE steps SET done = ? WHERE id = ?", (int(done), step_id)
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT id, plan_id, title, url, done, position FROM steps WHERE id = ?",
            (step_id,),
        ).fetchone()
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "title": row["title"],
        "url": row["url"],
        "done": bool(row["done"]),
        "position": row["position"],
    }


def toggle_step(step_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT done FROM steps WHERE id = ?", (step_id,)
        ).fetchone()
        if row is None:
            return None
        done = not bool(row["done"])
    return set_step_done(step_id, done)
