from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from clause_backend.core.config import settings
from clause_backend.db import get_connection


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_demo_user_and_projects() -> None:
    now = utc_now()
    password_hash = hash_password(settings.auth_dummy_password)
    with get_connection() as connection:
        row = connection.execute("select user_id from users where email = ?", (settings.auth_dummy_email,)).fetchone()
        if row:
            user_id = str(row["user_id"])
            connection.execute(
                """
                update users
                set password_hash = ?, display_name = ?, updated_at = ?
                where user_id = ?
                """,
                (password_hash, "Clause Demo", now, user_id),
            )
        else:
            user_id = f"user-{uuid4()}"
            connection.execute(
                """
                insert into users (user_id, email, password_hash, display_name, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (user_id, settings.auth_dummy_email, password_hash, "Clause Demo", now, now),
            )

        count = int(
            connection.execute("select count(*) from projects where owner_user_id = ?", (user_id,)).fetchone()[0]
        )
        if count:
            return

        demo_projects = [
            {
                "title": "Consumer Data Broker Accountability Act",
                "policy_goal": "Tighten consumer data broker obligations and phase in enforcement safely.",
                "jurisdiction": "California",
                "status": "Needs revision",
                "stage": "Research",
                "summary": "Privacy bill draft focused on registration, deletion rights, and agency enforcement.",
                "bill_text": (
                    "Section 1. A data broker operating in this state shall register annually, honor verified deletion requests, "
                    "and maintain a public compliance contact. Section 2. Enforcement begins on January 1, 2027."
                ),
            },
            {
                "title": "Wildfire Resilience Grant Program",
                "policy_goal": "Create a grant and coordination framework for wildfire risk reduction.",
                "jurisdiction": "United States",
                "status": "In drafting",
                "stage": "Draft",
                "summary": "Federal draft tying wildfire resilience funding to hazard reduction and local reporting.",
                "bill_text": (
                    "Section 1. The Secretary shall administer grants for hazardous fuels reduction and wildfire resilience "
                    "planning. Section 2. Eligible entities shall report annually on risk reduction outcomes."
                ),
            },
        ]

        for project in demo_projects:
            project_id = f"project-{uuid4()}"
            connection.execute(
                """
                insert into projects (
                    project_id,
                    owner_user_id,
                    title,
                    policy_goal,
                    jurisdiction,
                    status,
                    stage,
                    summary,
                    bill_text,
                    created_at,
                    updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    user_id,
                    project["title"],
                    project["policy_goal"],
                    project["jurisdiction"],
                    project["status"],
                    project["stage"],
                    project["summary"],
                    project["bill_text"],
                    now,
                    now,
                ),
            )


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("select * from users where lower(email) = lower(?) limit 1", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_session(session_token: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            select u.*
            from user_sessions s
            join users u on u.user_id = s.user_id
            where s.session_token = ?
              and s.expires_at > ?
            limit 1
            """,
            (session_token, utc_now()),
        ).fetchone()
    return dict(row) if row else None


def create_session(user_id: str) -> str:
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(24)
    expires_at = (now + timedelta(hours=settings.auth_session_hours)).isoformat()
    with get_connection() as connection:
        connection.execute("delete from user_sessions where user_id = ?", (user_id,))
        connection.execute(
            """
            insert into user_sessions (session_token, user_id, created_at, expires_at)
            values (?, ?, ?, ?)
            """,
            (token, user_id, now.isoformat(), expires_at),
        )
    return token


def delete_session(session_token: str) -> None:
    with get_connection() as connection:
        connection.execute("delete from user_sessions where session_token = ?", (session_token,))


def list_projects(owner_user_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            select *
            from projects
            where owner_user_id = ?
            order by updated_at desc
            """,
            (owner_user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_project(owner_user_id: str, title: str, policy_goal: str, jurisdiction: str | None) -> dict[str, Any]:
    now = utc_now()
    project_id = f"project-{uuid4()}"
    with get_connection() as connection:
        connection.execute(
            """
            insert into projects (
                project_id,
                owner_user_id,
                title,
                policy_goal,
                jurisdiction,
                status,
                stage,
                summary,
                bill_text,
                created_at,
                updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                owner_user_id,
                title,
                policy_goal,
                jurisdiction,
                "New",
                "Research",
                policy_goal,
                "",
                now,
                now,
            ),
        )
    project = get_project(project_id, owner_user_id)
    if not project:
        raise RuntimeError("Project creation failed.")
    return project


def get_project(project_id: str, owner_user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            select *
            from projects
            where project_id = ?
              and owner_user_id = ?
            limit 1
            """,
            (project_id, owner_user_id),
        ).fetchone()
    return dict(row) if row else None


def update_project(project_id: str, owner_user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    allowed_keys = {"title", "policy_goal", "jurisdiction", "status", "stage", "summary", "bill_text"}
    assignments = []
    params: list[Any] = []
    for key, value in updates.items():
        if key not in allowed_keys:
            continue
        assignments.append(f"{key} = ?")
        params.append(value)
    if not assignments:
        return get_project(project_id, owner_user_id)
    assignments.append("updated_at = ?")
    params.append(utc_now())
    params.extend([project_id, owner_user_id])
    with get_connection() as connection:
        connection.execute(
            f"""
            update projects
            set {", ".join(assignments)}
            where project_id = ?
              and owner_user_id = ?
            """,
            tuple(params),
        )
    return get_project(project_id, owner_user_id)


def upsert_project_insight(project_id: str, insight_type: str, payload: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            insert into project_insights (project_id, insight_type, payload_json, updated_at)
            values (?, ?, ?, ?)
            on conflict(project_id, insight_type)
            do update set payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """,
            (project_id, insight_type, json.dumps(payload), utc_now()),
        )


def list_project_insights(project_id: str) -> dict[str, dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "select insight_type, payload_json, updated_at from project_insights where project_id = ?",
            (project_id,),
        ).fetchall()
    payload: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload[str(row["insight_type"])] = {
            "payload": json.loads(row["payload_json"]),
            "updated_at": row["updated_at"],
        }
    return payload


def add_project_message(project_id: str, role: str, content: str, tool_trace: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    message = {
        "message_id": f"msg-{uuid4()}",
        "project_id": project_id,
        "role": role,
        "content": content,
        "tool_trace_json": json.dumps(tool_trace or []),
        "created_at": utc_now(),
    }
    with get_connection() as connection:
        connection.execute(
            """
            insert into project_messages (message_id, project_id, role, content, tool_trace_json, created_at)
            values (:message_id, :project_id, :role, :content, :tool_trace_json, :created_at)
            """,
            message,
        )
    return {
        "message_id": message["message_id"],
        "role": role,
        "content": content,
        "tool_trace": tool_trace or [],
        "created_at": message["created_at"],
    }


def list_project_messages(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            select message_id, role, content, tool_trace_json, created_at
            from project_messages
            where project_id = ?
            order by created_at asc
            """,
            (project_id,),
        ).fetchall()
    return [
        {
            "message_id": row["message_id"],
            "role": row["role"],
            "content": row["content"],
            "tool_trace": json.loads(row["tool_trace_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
