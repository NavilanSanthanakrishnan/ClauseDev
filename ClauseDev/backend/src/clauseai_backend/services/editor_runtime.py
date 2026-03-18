from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import websockets
from websockets.exceptions import ConnectionClosed
from sqlalchemy import func, select

from clauseai_backend.core.config import settings
from clauseai_backend.db.session import UserSessionLocal
from clauseai_backend.models.editor import EditorSession, EditorSessionEvent
from clauseai_backend.models.projects import AnalysisArtifact, BillDraft, BillDraftVersion, Project, ProjectMetadata, Suggestion


STAGE_MARKERS = {
    "[Stage: Similar Bills]": "similar-bills",
    "[Stage: Legal]": "legal",
    "[Stage: Stakeholders]": "stakeholders",
    "[Stage: Done]": "done",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_stage_marker(text: str) -> tuple[str, str | None]:
    cleaned = text.strip()
    for marker, stage in STAGE_MARKERS.items():
        if cleaned.startswith(marker):
            return cleaned[len(marker) :].strip(), stage
    return cleaned, None


class CodexAppServerProcess:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self._stdout_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._started_here = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self.process and self.process.returncode is None:
                return
            try:
                if await self._is_ready():
                    return
            except Exception:
                pass

            self.process = await asyncio.create_subprocess_exec(
                "codex",
                "app-server",
                "--listen",
                settings.codex_app_server_ws_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._started_here = True
            self._stdout_task = asyncio.create_task(self._drain_stream(self.process.stdout))
            self._stderr_task = asyncio.create_task(self._drain_stream(self.process.stderr))

            last_error: Exception | None = None
            for _ in range(50):
                if self.process.returncode is not None:
                    raise RuntimeError("codex app-server exited during startup.")
                try:
                    if await self._is_ready():
                        return
                except Exception as exc:
                    last_error = exc
                await asyncio.sleep(0.2)
            raise RuntimeError(f"codex app-server did not become ready: {last_error}")

    async def stop(self) -> None:
        async with self._lock:
            if not self._started_here:
                return
            for task in (self._stdout_task, self._stderr_task):
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            if self.process and self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            self.process = None
            self._started_here = False

    async def _drain_stream(self, stream: asyncio.StreamReader | None) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                return

    async def _is_ready(self) -> bool:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(settings.codex_app_server_health_url)
            return response.status_code == 200


class EditorRuntimeManager:
    def __init__(self) -> None:
        self.app_server = CodexAppServerProcess()
        self.bridges: dict[str, EditorSessionBridge] = {}
        self._lock = asyncio.Lock()

    def recover_stale_sessions(self) -> None:
        with UserSessionLocal() as db:
            sessions = (
                db.execute(
                    select(EditorSession).where(EditorSession.status.in_(("starting", "running", "waiting_approval")))
                )
                .scalars()
                .all()
            )
            for item in sessions:
                item.status = "idle"
                item.active_turn_id = ""
                item.error_message = ""
                item.pending_approval = {}
                db.add(item)
            db.commit()

    async def shutdown(self) -> None:
        for bridge in list(self.bridges.values()):
            await bridge.stop()
        self.bridges.clear()
        await self.app_server.stop()

    async def start_or_resume(self, project_id: str, user_id: str) -> EditorSession:
        async with self._lock:
            active = self.bridges.get(project_id)
            if active and active.is_connected:
                return self.get_session(project_id, user_id)
            if active and not active.is_connected:
                self.bridges.pop(project_id, None)

            await self.app_server.start()
            bridge = EditorSessionBridge(project_id=project_id, user_id=user_id)
            self.bridges[project_id] = bridge
            try:
                await bridge.start()
            except Exception:
                self.bridges.pop(project_id, None)
                raise
            return self.get_session(project_id, user_id)

    async def steer(self, project_id: str, user_id: str, message: str) -> EditorSession:
        bridge = self._require_bridge(project_id)
        await bridge.steer(message)
        return self.get_session(project_id, user_id)

    async def approve(self, project_id: str, user_id: str, decision: str) -> EditorSession:
        bridge = self._require_bridge(project_id)
        await bridge.resolve_pending(decision)
        return self.get_session(project_id, user_id)

    def get_session(self, project_id: str, user_id: str) -> EditorSession:
        with UserSessionLocal() as db:
            session = self._owned_session(db, project_id, user_id)
            return session

    def find_session(self, project_id: str, user_id: str) -> EditorSession | None:
        with UserSessionLocal() as db:
            project = db.scalar(select(Project).where(Project.project_id == project_id, Project.user_id == user_id))
            if not project:
                raise ValueError("Project not found")
            return db.scalar(select(EditorSession).where(EditorSession.project_id == project_id))

    def list_events(self, project_id: str, user_id: str) -> list[EditorSessionEvent]:
        with UserSessionLocal() as db:
            project = db.scalar(select(Project).where(Project.project_id == project_id, Project.user_id == user_id))
            if not project:
                raise ValueError("Project not found")
            session = db.scalar(select(EditorSession).where(EditorSession.project_id == project_id))
            if not session:
                return []
            events = (
                db.execute(
                    select(EditorSessionEvent)
                    .where(EditorSessionEvent.session_id == session.session_id)
                    .order_by(EditorSessionEvent.created_at.asc())
                )
                .scalars()
                .all()
            )
            return events

    def _owned_session(self, db: Any, project_id: str, user_id: str) -> EditorSession:
        project = db.scalar(select(Project).where(Project.project_id == project_id, Project.user_id == user_id))
        if not project:
            raise ValueError("Project not found")
        session = db.scalar(select(EditorSession).where(EditorSession.project_id == project_id))
        if not session:
            raise ValueError("Editor session not started")
        return session

    def _require_bridge(self, project_id: str) -> "EditorSessionBridge":
        bridge = self.bridges.get(project_id)
        if not bridge:
            raise ValueError("Editor session is not active. Start it first.")
        if not bridge.is_connected:
            self.bridges.pop(project_id, None)
            raise ValueError("Editor session disconnected. Start it again.")
        return bridge


class EditorSessionBridge:
    def __init__(self, *, project_id: str, user_id: str) -> None:
        self.project_id = project_id
        self.user_id = user_id
        self.session_id = str(uuid4())
        self.workspace_dir = settings.storage_root.resolve() / project_id / "editor-workspace"
        self.context_dir = self.workspace_dir / "context"
        self.draft_path = self.workspace_dir / "current_draft.txt"
        self.ws: Any | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self._request_seq = 0
        self._response_futures: dict[str, asyncio.Future[Any]] = {}
        self._server_request_ids: dict[str, Any] = {}
        self._staged_file_changes: dict[str, dict[str, Any]] = {}
        self._accepted_file_change_items: set[str] = set()
        self._consecutive_auto_turn_completions = 0
        self._background_tasks: set[asyncio.Task[None]] = set()
        self.current_stage = "similar-bills"
        self._stopping = False

    @property
    def is_connected(self) -> bool:
        return bool(self.ws and not getattr(self.ws, "closed", False) and self.reader_task and not self.reader_task.done())

    async def start(self) -> None:
        self._prepare_workspace()
        self._ensure_editor_session_row()
        self.ws = await websockets.connect(settings.codex_app_server_ws_url, max_size=8_000_000)
        self.reader_task = asyncio.create_task(self._reader_loop())
        await self._request(
            "initialize",
            {
                "clientInfo": {"name": "clauseai-prod", "title": "ClauseAIProd", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        await self._notify("initialized")
        thread_response = await self._request(
            "thread/start",
            {
                "cwd": str(self.workspace_dir),
                "approvalPolicy": "on-request",
                "sandbox": "read-only",
                "personality": "pragmatic",
                "ephemeral": False,
                "model": settings.codex_model,
                "serviceName": "clauseai-prod",
                "developerInstructions": self._developer_instructions(),
            },
        )
        self._update_session(
            thread_id=str(thread_response["thread"]["id"]),
            active_turn_id="",
            status="running",
            current_stage="similar-bills",
            workspace_dir=str(self.workspace_dir),
            latest_agent_message="",
            final_message="",
            current_diff="",
            completion_summary="",
            error_message="",
            pending_approval={},
        )
        self._create_event("system", "Editor session started", "Codex is attached to the final drafting workspace.")
        await self.start_turn(self._initial_turn_prompt())

    async def stop(self) -> None:
        self._stopping = True
        for task in list(self._background_tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._background_tasks.clear()
        if self.reader_task:
            self.reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.reader_task
        if self.ws:
            await self.ws.close()
        self.ws = None

    async def start_turn(self, message: str) -> None:
        session = self._get_session_row()
        response = await self._request(
            "turn/start",
            {
                "threadId": session.thread_id,
                "input": [{"type": "text", "text": message}],
                "cwd": str(self.workspace_dir),
                "approvalPolicy": "on-request",
                "sandboxPolicy": {
                    "type": "readOnly",
                },
            },
        )
        self._update_session(
            active_turn_id=str(response["turn"]["id"]),
            status="running",
            error_message="",
            pending_approval={},
            current_diff="",
            final_message="",
        )
        self._create_event("system", "Codex loop running", f"Codex is continuing from {self.current_stage}.")

    async def steer(self, message: str) -> None:
        session = self._get_session_row()
        if session.pending_approval:
            raise ValueError("Resolve the pending draft diff before steering Codex.")
        if session.active_turn_id:
            await self._request(
                "turn/steer",
                {
                    "threadId": session.thread_id,
                    "expectedTurnId": session.active_turn_id,
                    "input": [{"type": "text", "text": message}],
                },
            )
        else:
            await self.start_turn(message)
        self._create_event("user", "User steer", message)

    async def resolve_pending(self, decision: str) -> None:
        session = self._get_session_row()
        pending = dict(session.pending_approval or {})
        if not pending:
            raise ValueError("There is no pending diff to review.")
        raw_request_id = self._server_request_ids.get(str(pending["request_id"]))
        if raw_request_id is None:
            raise ValueError("The pending approval request is no longer active.")
        if decision == "accept":
            self._accepted_file_change_items.add(str(pending["item_id"]))
        self._update_session(status="running", pending_approval={})
        await self._send({"id": raw_request_id, "result": {"decision": decision}})
        self._server_request_ids.pop(str(pending["request_id"]), None)
        self._create_event("approval", f"Diff {decision}", str(pending.get("diff") or ""), decision=decision)

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        try:
            return await self._request_once(method, params)
        except RuntimeError as exc:
            compatible = self._compatible_params(method, params, str(exc))
            if compatible is None:
                raise
            return await self._request_once(method, compatible)

    async def _request_once(self, method: str, params: dict[str, Any]) -> Any:
        request_id = self._next_request_id()
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._response_futures[request_id] = future
        await self._send({"id": request_id, "method": method, "params": params})
        return await future

    def _compatible_params(self, method: str, params: dict[str, Any], error_text: str) -> dict[str, Any] | None:
        expected_kebab = "expected one of `read-only`, `workspace-write`, `danger-full-access`" in error_text
        expected_camel = (
            "expected one of `dangerFullAccess`, `readOnly`, `externalSandbox`, `workspaceWrite`" in error_text
        )
        if method == "thread/start" and "sandbox" in params:
            updated = dict(params)
            if expected_kebab:
                updated["sandbox"] = self._normalize_sandbox_value(str(params["sandbox"]), expected_kebab=True)
                return updated
            if expected_camel:
                updated["sandbox"] = self._normalize_sandbox_value(str(params["sandbox"]), expected_kebab=False)
                return updated
        if method == "turn/start" and isinstance(params.get("sandboxPolicy"), dict):
            sandbox_policy = dict(params["sandboxPolicy"])
            updated = dict(params)
            if expected_kebab:
                sandbox_policy["type"] = self._normalize_sandbox_value(str(sandbox_policy.get("type") or ""), expected_kebab=True)
                updated["sandboxPolicy"] = sandbox_policy
                return updated
            if expected_camel:
                sandbox_policy["type"] = self._normalize_sandbox_value(str(sandbox_policy.get("type") or ""), expected_kebab=False)
                updated["sandboxPolicy"] = sandbox_policy
                return updated
        return None

    def _normalize_sandbox_value(self, value: str, *, expected_kebab: bool) -> str:
        normalized = value.strip()
        if normalized in {"read-only", "readOnly"}:
            return "read-only" if expected_kebab else "readOnly"
        if normalized in {"workspace-write", "workspaceWrite"}:
            return "workspace-write" if expected_kebab else "workspaceWrite"
        if normalized in {"danger-full-access", "dangerFullAccess"}:
            return "danger-full-access" if expected_kebab else "dangerFullAccess"
        return "read-only" if expected_kebab else "readOnly"

    async def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> None:
        if not self.ws:
            raise RuntimeError("Codex websocket is not connected.")
        async with self._send_lock:
            try:
                await self.ws.send(json.dumps(payload))
            except ConnectionClosed as exc:
                self._mark_connection_error(exc)
                raise RuntimeError("Codex websocket disconnected.") from exc

    async def _reader_loop(self) -> None:
        assert self.ws is not None
        try:
            async for raw in self.ws:
                message = json.loads(raw)
                if "result" in message and "id" in message:
                    future = self._response_futures.pop(str(message["id"]), None)
                    if future and not future.done():
                        future.set_result(message["result"])
                    continue
                if "error" in message and "id" in message:
                    future = self._response_futures.pop(str(message["id"]), None)
                    if future and not future.done():
                        future.set_exception(RuntimeError(str(message["error"])))
                    continue
                if "id" in message and "method" in message:
                    await self._handle_server_request(message)
                    continue
                if "method" in message:
                    await self._handle_notification(message)
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as exc:
            if not self._stopping:
                self._mark_connection_error(exc)
        except Exception as exc:
            if not self._stopping:
                self._update_session(status="error", error_message=str(exc))
                self._create_event("error", "Codex bridge error", str(exc))

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message["method"])
        if method == "item/commandExecution/requestApproval":
            await self._handle_command_approval_request(message)
            return

        if method != "item/fileChange/requestApproval":
            await self._send({"id": message["id"], "result": {"decision": "decline"}})
            self._create_event("error", "Unhandled server request", method)
            return

        params = message["params"]
        item_id = str(params["itemId"])
        request_id = str(message["id"])
        staged = self._staged_file_changes.get(item_id, {})
        staged_paths = [Path(path).resolve() for path in staged.get("file_paths", []) if path]
        allowed_path = self.draft_path.resolve()
        if staged_paths and all(path == allowed_path for path in staged_paths):
            pending = {
                "request_id": request_id,
                "item_id": item_id,
                "turn_id": str(params["turnId"]),
                "diff": staged.get("diff", ""),
                "reason": params.get("reason") or "",
                "file_paths": staged.get("file_paths", []),
                "created_at": _now().isoformat(),
            }
            self._server_request_ids[request_id] = message["id"]
            self._update_session(status="waiting_approval", pending_approval=pending)
            self._create_event("approval", "Draft diff ready", str(pending["diff"]), turn_id=pending["turn_id"])
            self._consecutive_auto_turn_completions = 0
            return

        await self._send({"id": message["id"], "result": {"decision": "decline"}})
        self._create_event(
            "error",
            "Blocked out-of-scope edit",
            "Codex attempted to edit a file outside current_draft.txt.",
            files=[str(path) for path in staged_paths],
        )

    async def _handle_command_approval_request(self, message: dict[str, Any]) -> None:
        params = message["params"]
        command = str(params.get("command") or "").strip()
        cwd = str(params.get("cwd") or "").strip()
        command_actions = list(params.get("commandActions") or [])
        decision = "accept" if self._command_is_safe(command, cwd, command_actions) else "decline"
        await self._send({"id": message["id"], "result": {"decision": decision}})
        self._create_event(
            "command",
            "Workspace command approval",
            command or "Codex requested a workspace command.",
            decision=decision,
            cwd=cwd,
            command_actions=command_actions,
        )

    def _command_is_safe(self, command: str, cwd: str, command_actions: list[dict[str, Any]]) -> bool:
        if command_actions and all(self._command_action_is_safe(action) for action in command_actions):
            return self._cwd_is_workspace(cwd)
        if not command:
            return False
        blocked_tokens = ("&&", "||", ";", "|", ">", "<", "$(", "`")
        if any(token in command for token in blocked_tokens):
            return False
        command_name = command.split()[0]
        if command_name in {"bash", "sh", "zsh"}:
            lowered = command.lower()
            read_only_fragments = ("cat ", "sed ", "head ", "tail ", "wc ", "rg ", "find ", "ls ", "pwd")
            if any(fragment in lowered for fragment in read_only_fragments):
                return self._cwd_is_workspace(cwd)
            return False
        allowed_commands = {"ls", "pwd", "cat", "sed", "head", "tail", "wc", "rg", "find"}
        if command_name not in allowed_commands:
            return False
        return self._cwd_is_workspace(cwd)

    def _command_action_is_safe(self, action: dict[str, Any]) -> bool:
        action_type = str(action.get("type") or "")
        path = action.get("path")
        if action_type == "listFiles":
            return self._path_is_within_workspace(path)
        if action_type == "read":
            return self._path_is_within_workspace(path)
        return False

    def _cwd_is_workspace(self, cwd: str) -> bool:
        if not cwd:
            return True
        try:
            return Path(cwd).resolve() == self.workspace_dir.resolve()
        except OSError:
            return False

    def _path_is_within_workspace(self, path: Any) -> bool:
        if not path:
            return True
        try:
            resolved = Path(str(path)).resolve()
        except OSError:
            return False
        workspace = self.workspace_dir.resolve()
        return resolved == workspace or workspace in resolved.parents

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        method = message["method"]
        params = message.get("params", {})

        if method == "item/agentMessage/delta":
            current = self._get_session_row().latest_agent_message
            self._update_session(latest_agent_message=current + str(params.get("delta") or ""))
            return

        if method == "item/started":
            item = params.get("item", {})
            item_type = item.get("type")
            if item_type == "fileChange":
                changes = item.get("changes") or []
                diff = "\n".join(change.get("diff", "") for change in changes if change.get("diff")).strip()
                file_paths = [change.get("path", "") for change in changes if change.get("path")]
                self._staged_file_changes[str(item["id"])] = {"diff": diff, "file_paths": file_paths}
                self._create_event("system", "Draft edit attempt started", diff or "Codex started a draft edit.")
            elif item_type == "commandExecution":
                self._create_event(
                    "command",
                    "Codex command",
                    str(item.get("command") or ""),
                    command=item.get("command") or "",
                )
            elif item_type == "webSearch":
                self._create_event("web", "Web search", str(item.get("query") or "Codex started a web search."))
            return

        if method == "item/completed":
            item = params.get("item", {})
            item_type = item.get("type")
            if item_type == "agentMessage":
                cleaned, stage = _clean_stage_marker(str(item.get("text") or ""))
                updates: dict[str, Any] = {}
                if cleaned:
                    updates["latest_agent_message"] = cleaned
                    if item.get("phase") == "final_answer":
                        updates["final_message"] = cleaned
                if stage:
                    self.current_stage = stage
                    updates["current_stage"] = stage
                    if stage == "done":
                        updates["completion_summary"] = cleaned or "Codex completed the drafting pass."
                if updates:
                    self._update_session(**updates)
                self._create_event("agent", "Codex update", cleaned, phase=str(item.get("phase") or ""))
                return
            if item_type == "fileChange":
                item_id = str(item.get("id") or "")
                staged = self._staged_file_changes.pop(item_id, {})
                if item_id in self._accepted_file_change_items:
                    self._accepted_file_change_items.discard(item_id)
                    if self._refresh_draft_from_disk():
                        self._update_session(current_diff="")
                        self._create_event("diff", "Bill updated", staged.get("diff", ""))
                        self._consecutive_auto_turn_completions = 0
                        return
                self._create_event(
                    "error",
                    "Draft edit attempt failed",
                    staged.get("diff", "") or "Codex attempted a draft edit, but the file did not change.",
                )
                return
            return

        if method == "turn/diff/updated":
            diff = str(params.get("diff") or "")
            session = self._get_session_row()
            pending = dict(session.pending_approval or {})
            if pending and not pending.get("diff"):
                pending["diff"] = diff
            self._update_session(current_diff=diff, pending_approval=pending)
            return

        if method == "turn/started":
            self._update_session(active_turn_id=str(params["turn"]["id"]), status="running")
            return

        if method == "turn/completed":
            session = self._get_session_row()
            if session.current_stage == "done":
                self._update_session(
                    active_turn_id="",
                    status="completed",
                    completion_summary=session.completion_summary or session.final_message or "Codex finished editing.",
                )
                self._create_event("system", "Codex loop finished", self._get_session_row().completion_summary)
                return

            self._update_session(
                active_turn_id="",
                status="waiting_approval" if session.pending_approval else "completed",
                completion_summary=session.final_message or session.completion_summary,
            )
            self._create_event("system", "Codex turn completed", session.final_message or "Codex completed this turn.")
            if not session.pending_approval:
                self._consecutive_auto_turn_completions += 1
                if self._consecutive_auto_turn_completions <= 3:
                    self._spawn_background_task(self.start_turn(self._continuation_turn_prompt()), "continue-turn")
                else:
                    self._update_session(
                        status="error",
                        error_message="Codex ended multiple turns before finishing. Restart or steer the editor session.",
                    )
                    self._create_event("error", "Codex stalled", self._get_session_row().error_message)
            return

        if method == "error":
            body = json.dumps(params)
            self._update_session(status="error", error_message=body)
            self._create_event("error", "Codex error", body)

    def _refresh_draft_from_disk(self) -> bool:
        if not self.draft_path.is_file():
            return False
        updated_text = self.draft_path.read_text(encoding="utf-8")
        with UserSessionLocal() as db:
            draft = db.scalar(select(BillDraft).where(BillDraft.project_id == self.project_id))
            project = db.get(Project, self.project_id)
            if not draft or not project:
                return False
            if updated_text == draft.current_text:
                return False
            draft.current_text = updated_text
            project.current_stage = "editor"
            project.status = "in_review"
            version_number = (
                db.execute(
                    select(func.max(BillDraftVersion.version_number)).where(BillDraftVersion.project_id == self.project_id)
                ).scalar_one()
                or 0
            )
            db.add(
                BillDraftVersion(
                    version_id=str(uuid4()),
                    draft_id=draft.draft_id,
                    project_id=self.project_id,
                    version_number=int(version_number) + 1,
                    source_kind="agent_edit",
                    content_text=updated_text,
                    change_summary={
                        "reason": f"Codex editor update during {self.current_stage}",
                        "editor_session_id": self.session_id,
                    },
                    created_by=self.user_id,
                )
            )
            db.add(draft)
            db.add(project)
            db.commit()
            return True

    def _ensure_editor_session_row(self) -> None:
        with UserSessionLocal() as db:
            project = db.scalar(select(Project).where(Project.project_id == self.project_id, Project.user_id == self.user_id))
            draft = db.scalar(select(BillDraft).where(BillDraft.project_id == self.project_id))
            if not project or not draft:
                raise ValueError("Project not found")
            existing = db.scalar(select(EditorSession).where(EditorSession.project_id == self.project_id))
            if existing:
                existing.session_id = self.session_id
                existing.thread_id = ""
                existing.active_turn_id = ""
                existing.status = "starting"
                existing.current_stage = "similar-bills"
                existing.workspace_dir = str(self.workspace_dir)
                existing.latest_agent_message = ""
                existing.final_message = ""
                existing.current_diff = ""
                existing.completion_summary = ""
                existing.error_message = ""
                existing.pending_approval = {}
                db.add(existing)
                db.execute(select(EditorSessionEvent).where(EditorSessionEvent.session_id == existing.session_id))
                db.query(EditorSessionEvent).filter(EditorSessionEvent.project_id == self.project_id).delete()
            else:
                db.add(
                    EditorSession(
                        session_id=self.session_id,
                        project_id=self.project_id,
                        thread_id="",
                        active_turn_id="",
                        status="starting",
                        current_stage="similar-bills",
                        workspace_dir=str(self.workspace_dir),
                        latest_agent_message="",
                        final_message="",
                        current_diff="",
                        completion_summary="",
                        error_message="",
                        pending_approval={},
                    )
                )
            project.current_stage = "editor"
            project.status = "in_review"
            db.add(project)
            db.commit()

    def _get_session_row(self) -> EditorSession:
        with UserSessionLocal() as db:
            session = db.scalar(select(EditorSession).where(EditorSession.project_id == self.project_id))
            if not session:
                raise RuntimeError("Editor session row is missing.")
            db.expunge(session)
            return session

    def _update_session(self, **fields: Any) -> None:
        with UserSessionLocal() as db:
            session = db.scalar(select(EditorSession).where(EditorSession.project_id == self.project_id))
            if not session:
                raise RuntimeError("Editor session row is missing.")
            for key, value in fields.items():
                setattr(session, key, value)
            db.add(session)
            db.commit()

    def _create_event(self, kind: str, title: str, body: str = "", phase: str = "", **metadata: Any) -> None:
        with UserSessionLocal() as db:
            event = EditorSessionEvent(
                event_id=str(uuid4()),
                session_id=self.session_id,
                project_id=self.project_id,
                kind=kind,
                title=title,
                body=body,
                phase=phase,
                metadata_json=metadata,
            )
            db.add(event)
            db.commit()

    def _prepare_workspace(self) -> None:
        with UserSessionLocal() as db:
            project = db.scalar(select(Project).where(Project.project_id == self.project_id, Project.user_id == self.user_id))
            draft = db.scalar(select(BillDraft).where(BillDraft.project_id == self.project_id))
            metadata = db.get(ProjectMetadata, self.project_id)
            artifacts = (
                db.execute(
                    select(AnalysisArtifact)
                    .where(
                        AnalysisArtifact.project_id == self.project_id,
                        AnalysisArtifact.stage_name.in_(("similar-bills", "legal", "stakeholders")),
                    )
                    .order_by(AnalysisArtifact.updated_at.desc())
                )
                .scalars()
                .all()
            )
            suggestions = (
                db.execute(
                    select(Suggestion)
                    .where(
                        Suggestion.project_id == self.project_id,
                        Suggestion.stage_name.in_(("similar-bills", "legal", "stakeholders")),
                    )
                    .order_by(Suggestion.created_at.asc())
                )
                .scalars()
                .all()
            )
            if not project or not draft:
                raise ValueError("Project not found")

            artifact_map: dict[str, AnalysisArtifact] = {}
            for item in artifacts:
                artifact_map.setdefault(item.stage_name, item)
            grouped_guidance: dict[str, list[dict[str, Any]]] = {"similar-bills": [], "legal": [], "stakeholders": []}
            for item in suggestions:
                grouped_guidance.setdefault(item.stage_name, []).append(
                    {
                        "title": item.title,
                        "rationale": item.rationale,
                        "source_refs": list(item.source_refs),
                        "status": item.status,
                    }
                )

            self.context_dir.mkdir(parents=True, exist_ok=True)
            self.draft_path.write_text(draft.current_text, encoding="utf-8")
            (self.context_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "project": {
                            "title": project.title,
                            "jurisdiction_type": project.jurisdiction_type,
                            "jurisdiction_name": project.jurisdiction_name,
                        },
                        "metadata": metadata.generated_json if metadata else {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (self.context_dir / "drafting-guidance.json").write_text(
                json.dumps(grouped_guidance, indent=2),
                encoding="utf-8",
            )
            (self.context_dir / "drafting-guidance.md").write_text(
                self._guidance_markdown(grouped_guidance),
                encoding="utf-8",
            )
            (self.context_dir / "operator_brief.md").write_text(
                self._operator_brief(project, metadata, grouped_guidance),
                encoding="utf-8",
            )
            for stage_name in ("similar-bills", "legal", "stakeholders"):
                artifact = artifact_map.get(stage_name)
                filename = f"{stage_name}-report.md"
                (self.context_dir / filename).write_text(
                    artifact.markdown_content if artifact else f"No saved {stage_name} report yet.\n",
                    encoding="utf-8",
                )

    def _guidance_markdown(self, grouped_guidance: dict[str, list[dict[str, Any]]]) -> str:
        lines = ["# Drafting Guidance", ""]
        for stage_name in ("similar-bills", "legal", "stakeholders"):
            lines.append(f"## {stage_name.replace('-', ' ').title()}")
            items = grouped_guidance.get(stage_name, [])
            if not items:
                lines.append("No saved guidance.")
                lines.append("")
                continue
            for item in items:
                lines.append(f"- {item['title']}: {item['rationale']}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _operator_brief(
        self,
        project: Project,
        metadata: ProjectMetadata | None,
        grouped_guidance: dict[str, list[dict[str, Any]]],
    ) -> str:
        return "\n".join(
            [
                "# ClauseAI Final Drafting Brief",
                "",
                f"Bill: {project.title}",
                f"Jurisdiction: {project.jurisdiction_name} ({project.jurisdiction_type})",
                "",
                "Apply analysis-informed edits in this strict order:",
                "1. Similar bills",
                "2. Legal conflicts",
                "3. Stakeholder opposition",
                "",
                "Files available:",
                "- `current_draft.txt`",
                "- `context/metadata.json`",
                "- `context/similar-bills-report.md`",
                "- `context/legal-report.md`",
                "- `context/stakeholders-report.md`",
                "- `context/drafting-guidance.json`",
                "- `context/drafting-guidance.md`",
                "",
                "Saved guidance counts:",
                f"- Similar bills: {len(grouped_guidance.get('similar-bills', []))}",
                f"- Legal: {len(grouped_guidance.get('legal', []))}",
                f"- Stakeholders: {len(grouped_guidance.get('stakeholders', []))}",
                "",
                "User-editability rules:",
                "- Only edit `current_draft.txt`.",
                "- Make one local draft change at a time.",
                "- Re-read the full draft after every accepted change.",
                "- Stop when there are no more justified edits.",
                "- Do not treat upstream guidance as pre-approved draft text. You must derive the actual edit yourself.",
                "",
                "Metadata summary:",
                json.dumps(metadata.generated_json if metadata else {}, indent=2),
            ]
        )

    def _developer_instructions(self) -> str:
        return "\n".join(
            [
                "You are ClauseAI's final drafting agent in a visible Codex loop.",
                "Work only in this workspace.",
                "Only edit `current_draft.txt`.",
                "Use the saved reports and drafting guidance that are supplied in the turn prompt.",
                "Apply the workflow in this order: similar bills guidance, then legal guidance, then stakeholder guidance.",
                "The upstream stages do not contain approved bill text. They only contain analysis and general drafting advice.",
                "You must infer the next justified bill edit from that guidance, then propose the diff for approval.",
                "Do not use shell commands to inspect the workspace. The current draft and the relevant stage context are already included in the turn prompt.",
                "Use the direct file-edit/apply_patch tool for `current_draft.txt`. Never call `exec_command` to run `apply_patch`.",
                "Do not use `exec_command` just to print a status message. Plain agent text is enough.",
                "Make one high-confidence local edit at a time.",
                "Start with the smallest justified edit for the current stage.",
                "Prefer a short insertion or a short wording change over a broad rewrite.",
                "If a patch fails, reduce scope and try a smaller patch with tighter context.",
                "Keep commentary minimal: at most one short sentence before the next concrete action.",
                "Do not claim a bill change unless you actually edit `current_draft.txt`.",
                "When you begin working from similar bills, start a message with `[Stage: Similar Bills]`.",
                "When you begin working from legal analysis, start a message with `[Stage: Legal]`.",
                "When you begin working from stakeholder analysis, start a message with `[Stage: Stakeholders]`.",
                "When all justified edits are complete, your final answer must begin with `[Stage: Done]`.",
            ]
        )

    def _initial_turn_prompt(self) -> str:
        return self._stage_prompt(
            "similar-bills",
            "Run the ClauseAI final drafting workflow on this bill. Start with the similar-bills stage.",
        )

    def _continuation_turn_prompt(self) -> str:
        prompts = {
            "similar-bills": self._stage_prompt(
                "similar-bills",
                "Continue the similar-bills stage. If there is no more justified edit for this stage, reply with a short transition message that begins with `[Stage: Legal]`.",
            ),
            "legal": self._stage_prompt(
                "legal",
                "Continue the legal stage. If there is no more justified edit for this stage, reply with a short transition message that begins with `[Stage: Stakeholders]`.",
            ),
            "stakeholders": self._stage_prompt(
                "stakeholders",
                "Continue the stakeholder stage. If there is no more justified edit for this stage, finish with a short message that begins with `[Stage: Done]`.",
            ),
        }
        return prompts.get(
            self.current_stage,
            self._stage_prompt(
                "stakeholders",
                "Resume from the current workspace state and complete the final drafting workflow.",
            ),
        )

    def _stage_prompt(self, stage_name: str, lead_instruction: str) -> str:
        draft_text = self.draft_path.read_text(encoding="utf-8") if self.draft_path.is_file() else ""
        report_path = self.context_dir / f"{stage_name}-report.md"
        report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else f"No saved {stage_name} report yet."
        guidance = self._guidance_for_stage(stage_name)
        return "\n".join(
            [
                lead_instruction,
                "",
                "Rules for this turn:",
                "- Do not use shell commands to inspect files.",
                "- The current draft and stage context are included below.",
                "- Use the direct file-edit/apply_patch tool on `current_draft.txt`; never shell-wrap `apply_patch` through `exec_command`.",
                "- Either make one focused edit to `current_draft.txt`, or send a short stage-transition/status message.",
                "- Do not batch multiple edits into one diff.",
                "- Prefer the smallest clean patch that advances this stage.",
                "",
                f"# Current Stage: {stage_name.replace('-', ' ').title()}",
                "",
                "## Current Draft",
                "```text",
                draft_text[: settings.max_draft_chars_for_model],
                "```",
                "",
                "## Stage Report",
                "```markdown",
                report_text[: settings.max_draft_chars_for_model],
                "```",
                "",
                "## General Drafting Guidance",
                guidance,
            ]
        ).strip()

    def _guidance_for_stage(self, stage_name: str) -> str:
        with UserSessionLocal() as db:
            suggestions = (
                db.execute(
                    select(Suggestion)
                    .where(Suggestion.project_id == self.project_id, Suggestion.stage_name == stage_name)
                    .order_by(Suggestion.created_at.asc())
                )
                .scalars()
                .all()
            )
        if not suggestions:
            return "- No saved guidance."
        lines: list[str] = []
        for suggestion in suggestions:
            lines.append(f"- {suggestion.title}: {suggestion.rationale}")
            for source in suggestion.source_refs:
                label = str(source.get("identifier") or source.get("citation") or source.get("name") or "").strip()
                if label:
                    lines.append(f"  Source: {label}")
        return "\n".join(lines)

    def _mark_connection_error(self, exc: Exception) -> None:
        self.ws = None
        self._update_session(status="error", error_message=str(exc))
        self._create_event("error", "Codex bridge error", str(exc))

    def _next_request_id(self) -> str:
        self._request_seq += 1
        return f"editor-{self._request_seq}"

    def _spawn_background_task(self, coroutine: Any, label: str) -> None:
        task = asyncio.create_task(self._run_background_task(coroutine, label))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_background_task(self, coroutine: Any, label: str) -> None:
        try:
            await coroutine
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._update_session(status="error", error_message=str(exc))
            self._create_event("error", "Background Codex action failed", f"{label}: {exc}")
