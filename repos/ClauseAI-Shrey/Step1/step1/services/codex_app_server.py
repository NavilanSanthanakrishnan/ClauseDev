from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import websockets

from step1.config import get_settings
from step1.models import WorkflowEvent, WorkflowPendingApproval, WorkflowSession
from step1.services.workflow_store import WorkflowStore, utc_now_iso


SessionPublisher = Callable[[WorkflowSession, bool], Awaitable[None]]


def _clean_stage_marker(text: str) -> tuple[str, str | None]:
    cleaned = text.strip()
    markers = {
        "[Stage: Step 3]": "step3",
        "[Stage: Step 4]": "step4",
        "[Stage: Step 5]": "step5",
        "[Stage: Done]": "done",
    }
    for marker, stage in markers.items():
        if cleaned.startswith(marker):
            cleaned = cleaned[len(marker) :].strip()
            return cleaned, stage
    return cleaned, None


def _event(event_id: str, kind: str, title: str, body: str = "", phase: str = "", **metadata: Any) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=event_id,
        kind=kind,
        title=title,
        body=body,
        phase=phase,
        created_at=utc_now_iso(),
        metadata=metadata,
    )


def _stage_rank(stage: str | None) -> int:
    order = {
        "step3": 1,
        "step4": 2,
        "step5": 3,
        "done": 4,
    }
    return order.get(stage or "", 0)


class CodexAppServerProcess:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.process: asyncio.subprocess.Process | None = None
        self._stdout_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._started_here = False

    async def start(self) -> None:
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
            self.settings.codex_app_server_ws_url,
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
            except Exception as exc:  # pragma: no cover - startup retry path
                last_error = exc
            await asyncio.sleep(0.2)
        raise RuntimeError(f"codex app-server did not become ready: {last_error}")

    async def stop(self) -> None:
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
            except asyncio.TimeoutError:  # pragma: no cover - defensive shutdown path
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
            response = await client.get(self.settings.codex_app_server_health_url)
            return response.status_code == 200


class CodexSessionBridge:
    def __init__(
        self,
        session: WorkflowSession,
        store: WorkflowStore,
        publish: SessionPublisher,
    ) -> None:
        self.settings = get_settings()
        self.session = session
        self.store = store
        self.publish = publish

        self.ws: Any | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self._session_lock = asyncio.Lock()
        self._request_seq = 0
        self._response_futures: dict[str, asyncio.Future[Any]] = {}
        self._server_request_ids: dict[str, Any] = {}
        self._live_agent_messages: dict[str, str] = {}
        self._staged_file_changes: dict[str, dict[str, Any]] = {}
        self._accepted_file_change_items: set[str] = set()
        self._stakeholder_file_change_items: set[str] = set()
        self._consecutive_auto_turn_completions = 0
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._turn_stage_at_start = session.current_stage
        self._turn_draft_version_at_start = session.current_draft_version
        self._turn_saw_file_change = False
        self._turn_highest_stage_rank = _stage_rank(session.current_stage)

    async def start(self) -> None:
        self.ws = await websockets.connect(self.settings.codex_app_server_ws_url, max_size=8_000_000)
        self.reader_task = asyncio.create_task(self._reader_loop())
        await self._request(
            "initialize",
            {
                "clientInfo": {"name": "clause-workflow", "version": "1.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        await self._notify("initialized")
        thread_response = await self._request(
            "thread/start",
            {
                "cwd": self.session.workspace_dir,
                "approvalPolicy": "on-request",
                "sandbox": "workspace-write",
                "personality": "pragmatic",
                "ephemeral": True,
                "model": self.settings.codex_model,
                "serviceName": "clausedev",
                "developerInstructions": self._developer_instructions(),
            },
        )
        async with self._session_lock:
            self.session.thread_id = thread_response["thread"]["id"]
            self.session.current_stage = "step3"
            self.session.status = "running"
        await self._commit(
            _event(
                "thread-started",
                "system",
                "Codex session started",
                body="A live Codex thread is attached to this workflow session.",
            )
        )
        await self.start_turn(self._initial_turn_prompt())

    async def stop(self) -> None:
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

    async def start_turn(self, message: str) -> None:
        response = await self._request(
            "turn/start",
            {
                "threadId": self.session.thread_id,
                "input": [{"type": "text", "text": message}],
                "cwd": self.session.workspace_dir,
                "approvalPolicy": "on-request",
                "sandboxPolicy": {
                    "type": "workspaceWrite",
                    "writableRoots": [self.session.workspace_dir],
                    "networkAccess": True,
                },
            },
        )
        async with self._session_lock:
            self.session.active_turn_id = response["turn"]["id"]
            self.session.status = "running"
            self.session.error_message = ""
            self.session.pending_approval = None
            self.session.current_diff = ""
            self.session.final_message = ""
            self.session.completion_summary = ""
            self._turn_stage_at_start = self.session.current_stage
            self._turn_draft_version_at_start = self.session.current_draft_version
            self._turn_saw_file_change = False
            self._turn_highest_stage_rank = _stage_rank(self.session.current_stage)
            stage_label = self.session.current_stage.upper() if self.session.current_stage else "CURRENT"
        await self._commit(
            _event(
                f"turn-start-{response['turn']['id']}",
                "system",
                "Codex loop running",
                body=f"Codex is continuing the structured bill-editing loop from {stage_label}.",
            )
        )

    async def steer(self, message: str) -> None:
        async with self._session_lock:
            if self.session.pending_approval:
                raise ValueError("Resolve the current diff approval before steering Codex.")
            thread_id = self.session.thread_id
            active_turn_id = self.session.active_turn_id
        if active_turn_id:
            await self._request(
                "turn/steer",
                {
                    "threadId": thread_id,
                    "expectedTurnId": active_turn_id,
                    "input": [{"type": "text", "text": message}],
                },
            )
        else:
            await self.start_turn(message)
        await self._commit(
            _event(
                f"user-steer-{utc_now_iso()}",
                "user",
                "User steer",
                body=message,
            )
        )

    async def approve_pending_diff(self, decision: str) -> None:
        async with self._session_lock:
            pending = self.session.pending_approval
            if not pending:
                raise ValueError("There is no pending diff to review.")
            raw_request_id = self._server_request_ids.get(pending.request_id)
            if raw_request_id is None:
                raise ValueError("The pending approval request is no longer active.")
            self.session.pending_approval = None
            self.session.status = "running"
            if decision == "accept":
                self._accepted_file_change_items.add(pending.item_id)
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": raw_request_id,
                "result": {"decision": decision},
            }
        )
        self._server_request_ids.pop(pending.request_id, None)
        await self._commit(
            _event(
                f"approval-{pending.request_id}",
                "approval",
                f"Diff {decision}",
                body=pending.diff,
                decision=decision,
                turn_id=pending.turn_id,
            )
        )

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        try:
            return await self._request_once(method, params)
        except RuntimeError as exc:
            compatible_params = self._compatible_params(method, params, str(exc))
            if compatible_params is None:
                raise
            await self._commit(
                _event(
                    f"compat-retry-{self._next_request_id()}",
                    "system",
                    "Retrying app-server request",
                    body=str(exc),
                    method=method,
                ),
                persist=False,
            )
            return await self._request_once(method, compatible_params)

    async def _request_once(self, method: str, params: dict[str, Any]) -> Any:
        request_id = self._next_request_id()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._response_futures[request_id] = future
        await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return await future

    def _compatible_params(self, method: str, params: dict[str, Any], error_text: str) -> dict[str, Any] | None:
        expected_kebab = "expected one of `read-only`, `workspace-write`, `danger-full-access`" in error_text
        expected_camel = (
            "expected one of `dangerFullAccess`, `readOnly`, `externalSandbox`, `workspaceWrite`" in error_text
        )

        if method == "thread/start" and "sandbox" in params:
            if expected_kebab and params.get("sandbox") != "workspace-write":
                updated = dict(params)
                updated["sandbox"] = "workspace-write"
                return updated
            if expected_camel and params.get("sandbox") != "workspaceWrite":
                updated = dict(params)
                updated["sandbox"] = "workspaceWrite"
                return updated

        if method == "turn/start" and isinstance(params.get("sandboxPolicy"), dict):
            sandbox_policy = dict(params["sandboxPolicy"])
            current = sandbox_policy.get("type")
            if expected_kebab and current != "workspace-write":
                sandbox_policy["type"] = "workspace-write"
                updated = dict(params)
                updated["sandboxPolicy"] = sandbox_policy
                return updated
            if expected_camel and current != "workspaceWrite":
                sandbox_policy["type"] = "workspaceWrite"
                updated = dict(params)
                updated["sandboxPolicy"] = sandbox_policy
                return updated

        return None

    async def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> None:
        if not self.ws:
            raise RuntimeError("Codex websocket is not connected.")
        async with self._send_lock:
            await self.ws.send(json.dumps(payload))

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
        except Exception as exc:
            async with self._session_lock:
                self.session.status = "error"
                self.session.error_message = str(exc)
            await self._commit(
                _event("bridge-error", "error", "Codex bridge error", body=str(exc)),
            )

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        if message["method"] != "item/fileChange/requestApproval":
            await self._commit(
                _event(
                    f"server-request-{message['id']}",
                    "error",
                    "Unhandled server request",
                    body=message["method"],
                    params=message.get("params", {}),
                ),
                persist=False,
            )
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": {"decision": "cancel"}})
            return

        params = message["params"]
        item_id = params["itemId"]
        request_id = str(message["id"])
        staged = self._staged_file_changes.get(item_id, {})
        allowed_path = self.store.draft_path(self.session.session_id).resolve()
        stakeholder_paths = {
            self.store.stakeholder_report_json_path(self.session.session_id).resolve(),
            self.store.stakeholder_report_md_path(self.session.session_id).resolve(),
        }
        staged_paths = [Path(path).resolve() for path in staged.get("file_paths", []) if path]
        if staged_paths and all(path == allowed_path for path in staged_paths):
            pending = WorkflowPendingApproval(
                request_id=request_id,
                item_id=item_id,
                turn_id=params["turnId"],
                diff=staged.get("diff", ""),
                reason=params.get("reason") or "",
                file_paths=staged.get("file_paths", []),
                created_at=utc_now_iso(),
            )
            async with self._session_lock:
                self._server_request_ids[request_id] = message["id"]
                self.session.pending_approval = pending
                self.session.status = "waiting_approval"
            await self._commit(
                _event(
                    f"approval-request-{request_id}",
                    "approval",
                    "Diff ready for review",
                    body=pending.diff,
                    turn_id=pending.turn_id,
                    files=pending.file_paths,
                )
            )
            self._consecutive_auto_turn_completions = 0
            return

        if staged_paths and all(path in stakeholder_paths for path in staged_paths):
            self._stakeholder_file_change_items.add(item_id)
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": {"decision": "accept"}})
            await self._commit(
                _event(
                    f"stakeholder-write-{request_id}",
                    "system",
                    "Stakeholder report write accepted",
                    body="Codex updated the Step 5 stakeholder analysis artifacts.",
                    files=[str(path) for path in staged_paths],
                ),
                persist=False,
            )
            return

        if staged_paths and any(path != allowed_path and path not in stakeholder_paths for path in staged_paths):
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": {"decision": "decline"}})
            await self._commit(
                _event(
                    f"approval-request-{request_id}",
                    "error",
                    "Blocked out-of-scope edit",
                    body="Codex attempted to edit a file outside `current_draft.txt` and the Step 5 stakeholder report files. The change was declined.",
                    files=[str(path) for path in staged_paths],
                )
            )
            return

        await self._send({"jsonrpc": "2.0", "id": message["id"], "result": {"decision": "decline"}})
        await self._commit(
            _event(
                f"approval-request-{request_id}",
                "error",
                "Unrecognized file change target",
                body="Codex proposed a file change that did not map cleanly to the draft or stakeholder report files.",
                files=[str(path) for path in staged_paths],
            )
        )

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        method = message["method"]
        params = message.get("params", {})

        if method.endswith("web_search_begin"):
            msg = params.get("msg", {})
            await self._commit(
                _event(
                    f"web-search-begin-{utc_now_iso()}",
                    "web",
                    "Web search",
                    body=str(msg.get("query") or "Codex started a web search."),
                ),
                persist=False,
            )
            return

        if method.endswith("web_search_end"):
            msg = params.get("msg", {})
            await self._commit(
                _event(
                    f"web-search-end-{utc_now_iso()}",
                    "web",
                    "Web search completed",
                    body=str(msg.get("query") or "Codex finished a web search."),
                ),
                persist=False,
            )
            return

        if method == "item/agentMessage/delta":
            item_id = params["itemId"]
            updated = self._live_agent_messages.get(item_id, "") + (params.get("delta") or "")
            self._live_agent_messages[item_id] = updated
            async with self._session_lock:
                self.session.latest_agent_message = updated
            await self.publish(self.session, False)
            return

        if method == "item/started":
            item = params.get("item", {})
            if item.get("type") == "fileChange":
                self._turn_saw_file_change = True
                changes = item.get("changes") or []
                diff = "\n".join(change.get("diff", "") for change in changes if change.get("diff")).strip()
                file_paths = [change.get("path", "") for change in changes if change.get("path")]
                self._staged_file_changes[item["id"]] = {"diff": diff, "file_paths": file_paths}
                await self._commit(
                    _event(
                        f"file-change-start-{item['id']}",
                        "system",
                        "Draft edit attempt started",
                        body=diff or "Codex started a draft file edit.",
                        files=file_paths,
                    ),
                    persist=False,
                )
            if item.get("type") == "commandExecution":
                await self._commit(
                    _event(
                        f"command-{item['id']}",
                        "command",
                        "Codex command",
                        body=item.get("command", ""),
                        command=item.get("command", ""),
                    ),
                    persist=False,
                )
            return

        if method == "item/completed":
            item = params.get("item", {})
            item_type = item.get("type")
            if item_type == "agentMessage":
                text = item.get("text", "").strip()
                cleaned_text, stage = _clean_stage_marker(text)
                async with self._session_lock:
                    if cleaned_text:
                        self.session.latest_agent_message = cleaned_text
                    if stage:
                        self.session.current_stage = stage
                        self._turn_highest_stage_rank = max(self._turn_highest_stage_rank, _stage_rank(stage))
                    if item.get("phase") == "final_answer":
                        self.session.final_message = cleaned_text
                        if stage == "done":
                            self.session.completion_summary = cleaned_text
                await self._commit(
                    _event(
                        f"agent-{item['id']}",
                        "agent",
                        "Codex update",
                        body=cleaned_text,
                        phase=item.get("phase", ""),
                    )
                )
                return
            if item_type == "fileChange":
                staged = self._staged_file_changes.pop(item.get("id", ""), {})
                staged_paths = [Path(path).resolve() for path in staged.get("file_paths", []) if path]
                draft_path = self.store.draft_path(self.session.session_id).resolve()
                stakeholder_paths = {
                    self.store.stakeholder_report_json_path(self.session.session_id).resolve(),
                    self.store.stakeholder_report_md_path(self.session.session_id).resolve(),
                }
                if item.get("id", "") in self._accepted_file_change_items:
                    self._accepted_file_change_items.discard(item.get("id", ""))
                    self._consecutive_auto_turn_completions = 0
                    await self._refresh_bill_from_disk()
                    await self._commit(
                        _event(
                            f"file-change-{item['id']}",
                            "diff",
                            "Bill updated",
                            body=staged.get("diff", ""),
                        )
                    )
                elif item.get("id", "") in self._stakeholder_file_change_items:
                    self._stakeholder_file_change_items.discard(item.get("id", ""))
                    self._consecutive_auto_turn_completions = 0
                    await self._refresh_stakeholder_report()
                    await self._commit(
                        _event(
                            f"stakeholder-file-change-{item['id']}",
                            "system",
                            "Stakeholder report updated",
                            body="Step 5 stakeholder analysis artifacts were refreshed from Codex output.",
                        )
                    )
                elif staged_paths and all(path == draft_path for path in staged_paths):
                    if await self._refresh_bill_from_disk():
                        self._consecutive_auto_turn_completions = 0
                        await self._commit(
                            _event(
                                f"file-change-{item['id']}",
                                "diff",
                                "Bill updated",
                                body=staged.get("diff", ""),
                                status=item.get("status", ""),
                            )
                        )
                        return
                    await self._commit(
                        _event(
                            f"file-change-failed-{item['id']}",
                            "error",
                            "Draft edit attempt failed",
                            body=staged.get("diff", "") or "Codex attempted a draft edit, but the draft file did not change.",
                            status=item.get("status", ""),
                        ),
                        persist=False,
                    )
                elif staged_paths and all(path in stakeholder_paths for path in staged_paths):
                    if await self._refresh_stakeholder_report():
                        self._consecutive_auto_turn_completions = 0
                        await self._commit(
                            _event(
                                f"stakeholder-file-change-{item['id']}",
                                "system",
                                "Stakeholder report updated",
                                body="Step 5 stakeholder analysis artifacts were refreshed from Codex output.",
                            )
                        )
                        return
                    await self._commit(
                        _event(
                            f"stakeholder-file-change-failed-{item['id']}",
                            "error",
                            "Stakeholder report write failed",
                            body="Codex reported a stakeholder report edit, but the files did not change on disk.",
                            status=item.get("status", ""),
                        ),
                        persist=False,
                    )
                else:
                    await self._commit(
                        _event(
                            f"file-change-failed-{item['id']}",
                            "error",
                            "Draft edit attempt failed",
                            body=staged.get("diff", "") or "Codex attempted a draft edit, but it did not reach approval.",
                            status=item.get("status", ""),
                        ),
                        persist=False,
                    )
                return
            return

        if method == "turn/diff/updated":
            async with self._session_lock:
                self.session.current_diff = params.get("diff", "")
                if self.session.pending_approval:
                    self.session.pending_approval.diff = self.session.current_diff or self.session.pending_approval.diff
            await self.publish(self.session, False)
            return

        if method == "turn/started":
            async with self._session_lock:
                self.session.active_turn_id = params["turn"]["id"]
                self.session.status = "running"
            await self.publish(self.session, False)
            return

        if method == "turn/completed":
            async with self._session_lock:
                stage = self.session.current_stage
                final_message = self.session.final_message
                has_pending_approval = self.session.pending_approval is not None
                draft_version = self.session.current_draft_version
                turn_stage_at_start = self._turn_stage_at_start
                turn_saw_file_change = self._turn_saw_file_change
                turn_highest_stage_rank = self._turn_highest_stage_rank
            invalid_done = (
                stage == "done"
                and not has_pending_approval
                and turn_stage_at_start in {"step3", "step4"}
                and turn_highest_stage_rank < _stage_rank("step5")
            )
            if invalid_done:
                async with self._session_lock:
                    self.session.current_stage = turn_stage_at_start
                    self.session.active_turn_id = ""
                    self.session.status = "running"
                    self.session.completion_summary = ""
                    self.session.final_message = ""
                await self._commit(
                    _event(
                        f"turn-invalid-done-{params['turn']['id']}",
                        "system",
                        "Continuing workflow",
                        body=(
                            "Codex tried to finish before the workflow reached Step 5. "
                            "Continuing from the current stage."
                        ),
                    )
                )
                self._spawn_background_task(
                    self.start_turn(self._forced_progress_prompt(turn_stage_at_start, turn_saw_file_change, draft_version)),
                    "retry-turn",
                )
                return
            async with self._session_lock:
                self.session.active_turn_id = ""
                if self.session.status != "error":
                    self.session.status = "completed"
                if stage == "done":
                    if not self.session.completion_summary:
                        self.session.completion_summary = final_message or "Codex finished the workflow."
                elif not self.session.completion_summary:
                    self.session.completion_summary = (
                        final_message or "Codex completed this turn before finalizing the workflow."
                    )
            await self._commit(
                _event(
                    f"turn-complete-{params['turn']['id']}",
                    "system",
                    "Codex turn completed" if stage != "done" else "Codex loop finished",
                    body=self.session.completion_summary,
                )
            )
            if stage != "done" and not has_pending_approval:
                self._consecutive_auto_turn_completions += 1
                if self._consecutive_auto_turn_completions <= 3:
                    self._spawn_background_task(
                        self.start_turn(self._continuation_turn_prompt(stage)),
                        "continue-turn",
                    )
                else:
                    async with self._session_lock:
                        self.session.status = "error"
                        self.session.error_message = (
                            "Codex ended multiple turns before finishing the workflow. Use feedback to resume manually."
                        )
                    await self._commit(
                        _event(
                            f"turn-stalled-{params['turn']['id']}",
                            "error",
                            "Codex stalled before finishing",
                            body=self.session.error_message,
                        )
                    )
            return

        if method == "error":
            body = json.dumps(params)
            async with self._session_lock:
                self.session.status = "error"
                self.session.error_message = body
            await self._commit(_event("codex-error", "error", "Codex error", body=body))
            return

    async def _refresh_bill_from_disk(self) -> bool:
        draft_path = self.store.draft_path(self.session.session_id)
        if not draft_path.is_file():
            return False
        updated_text = draft_path.read_text(encoding="utf-8")
        async with self._session_lock:
            if updated_text != self.session.current_draft_text:
                self.session.current_draft_text = updated_text
                self.session.current_draft_version += 1
                return True
        return False

    async def _refresh_stakeholder_report(self) -> bool:
        report = self.store.load_stakeholder_report(self.session.session_id)
        async with self._session_lock:
            if report != self.session.stakeholder_report:
                self.session.stakeholder_report = report
                return True
        return False

    async def _commit(self, event: WorkflowEvent | None = None, persist: bool = True) -> None:
        async with self._session_lock:
            if event:
                self.session.events.append(event)
                self.session.events = self.session.events[-120:]
            self.session.updated_at = utc_now_iso()
            session = self.session
        await self.publish(session, persist)

    def _next_request_id(self) -> str:
        self._request_seq += 1
        return f"client-{self._request_seq}"

    def _spawn_background_task(self, coroutine: Awaitable[None], label: str) -> None:
        task = asyncio.create_task(self._run_background_task(coroutine, label))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_background_task(self, coroutine: Awaitable[None], label: str) -> None:
        try:
            await coroutine
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with self._session_lock:
                self.session.status = "error"
                self.session.error_message = str(exc)
            await self._commit(
                _event(
                    f"{label}-error-{utc_now_iso()}",
                    "error",
                    "Background Codex action failed",
                    body=f"{label}: {exc}",
                )
            )

    def _developer_instructions(self) -> str:
        return "\n".join(
            [
                "You are ClauseDev's bill editing agent in a visible Codex loop.",
                "Work only in this session workspace.",
                "For draft changes, edit `current_draft.txt` directly with the file edit tool.",
                "Do not use any approval prompt tool.",
                "Edit only `current_draft.txt`, except in Step 5 when you may also update `context/stakeholder_report.json` and `context/stakeholder_report.md`.",
                "Read `current_draft.txt` in full before the first draft edit and after every accepted draft diff.",
                "Keep commentary minimal: at most one short sentence before the next concrete action.",
                "Do not narrate tentative plans or long analysis.",
                "Avoid redundant shell commands. Read only the smallest amount of workspace context needed for the next action.",
                "Prefer the smallest effective edit. Do not rewrite whole sections when a local fix will do.",
                "Some session modes auto-apply file edits without a separate approval prompt. If the file edit tool reports success, continue the workflow.",
                "Step 3: fix only basic drafting defects such as section titles, numbering, grammar, formatting, repeated text, and obvious cross-references.",
                "Step 3 should usually make 1 to 2 edits total unless the bill is clearly rougher or clearly cleaner.",
                "Do not alter policy substance in Step 3.",
                "Do not open source-bill files until Step 3 is complete.",
                "Step 4: use similar passed bills plus `context/similar_bill_summaries.md` to make only the highest-value 3 to 4 strengthening edits, unless fewer are justified.",
                "Only make a Step 4 edit when a similar bill clearly supports a better local formulation.",
                "Passed bills are templates. Failed bills are warning signals.",
                "Step 5: do tight stakeholder web research first, then overwrite `context/stakeholder_report.json` and `context/stakeholder_report.md` with completed contents before any Step 5 bill edit.",
                "In Step 5, 4 to 6 strong sources is usually enough. Stop searching once you have enough evidence to write the report.",
                "Do not reread the placeholder stakeholder report files before replacing them.",
                "Once you have enough evidence for Step 5, immediately overwrite both stakeholder report files in the same turn.",
                "Once you say you are writing the stakeholder report files, do not run more web searches or extra shell commands unless a critical source is still missing.",
                "Do not pause after announcing the stakeholder file write phase. Write both files immediately.",
                "If you identify a justified draft edit, make the actual file edit immediately instead of only describing it.",
                "Do not claim that you edited the draft unless you actually produced a file change.",
                "When you begin Step 3, start a short message with `[Stage: Step 3]`.",
                "When you begin Step 4, start a short message with `[Stage: Step 4]`.",
                "When you begin Step 5, start a short message with `[Stage: Step 5]`.",
                "When the whole workflow is complete, your final answer must begin with `[Stage: Done]`.",
            ]
        )

    def _initial_turn_prompt(self) -> str:
        return "\n".join(
            [
                "Run the ClauseDev workflow on this session's bill.",
                "Read only:",
                "- `current_draft.txt`",
                "- `context/operator_brief.md`",
                "",
                "Perform Step 3 first.",
                "If the bill has a clear Step 3 defect, edit `current_draft.txt` immediately with the smallest justified fix.",
                "If Step 3 needs no edit, say so briefly and move to Step 4.",
                "Do not open source-bill files until Step 3 is complete.",
                "Once Step 3 is complete, use `context/similar_bill_summaries.md`, `context/source_bills.json`, and the files under `context/source_bills/` for Step 4.",
                "For Step 4, make the actual file edit when you find the next justified improvement. Do not only describe it.",
                "Once Step 4 is complete, use web search plus the current bill to create the Step 5 stakeholder report in `context/stakeholder_report.json` and `context/stakeholder_report.md` before drafting any Step 5 edits.",
                "In Step 5, keep the evidence set tight, then overwrite both stakeholder report files directly in the same turn. Do not inspect the placeholder report files before writing them.",
                "As soon as Step 5 has enough evidence, stop searching and write both stakeholder report files immediately.",
                "Keep going until the full workflow reaches Step 5 and is actually done.",
                "If a file edit succeeds, continue unless the session explicitly shows a pending approval prompt.",
                "Do not edit any file except `current_draft.txt`, `context/stakeholder_report.json`, and `context/stakeholder_report.md`.",
            ]
        )

    def _continuation_turn_prompt(self, stage: str) -> str:
        prompts = {
            "step3": [
                "Continue the same ClauseDev workflow from Step 3.",
                "Read `current_draft.txt` in full again before deciding whether another minimal cleanup diff is necessary.",
                "Keep Step 3 to roughly 1 to 2 edits unless the bill quality clearly justifies more.",
                "If there is a clear Step 3 defect, make the actual file edit now instead of only describing it.",
                "If there is no clear localized drafting defect, end Step 3 immediately.",
                "If Step 3 is truly complete, move into Step 4 and continue the workflow without stopping.",
            ],
            "step4": [
                "Continue the same ClauseDev workflow from Step 4.",
                "Reread `current_draft.txt` before deciding whether another narrow source-supported Step 4 diff is warranted.",
                "Use `context/similar_bill_summaries.md` to choose the next similar bill to consult, then read only the source material needed for the next diff.",
                "Keep Step 4 to roughly 3 to 4 edits unless the bill quality clearly justifies fewer or more.",
                "If there is a justified Step 4 improvement, make the actual file edit now instead of only describing it.",
                "If there is no clearly superior local fix supported by source bills, end Step 4 immediately.",
                "If Step 4 is done, move directly into Step 5 and continue without stopping.",
            ],
            "step5": [
                "Continue the same ClauseDev workflow from Step 5.",
                "Read `current_draft.txt`.",
                "If the stakeholder report is not ready, gather only the missing evidence, then overwrite `context/stakeholder_report.json` and `context/stakeholder_report.md` immediately.",
                "Do not inspect the placeholder stakeholder report files before replacing them.",
                "Keep the Step 5 evidence set tight. Usually 4 to 6 strong sources is enough.",
                "As soon as you have enough Step 5 evidence, stop searching and overwrite both stakeholder report files in the same turn.",
                "After you start the stakeholder file write phase, do not run more web searches or extra shell commands unless a critical source is still missing.",
                "If the report is ready, continue with only the smallest justified stakeholder-driven bill edit and stop when no more are needed.",
                "If the report is ready and no meaningful stakeholder-driven edit is justified, finish immediately with `[Stage: Done]`.",
            ],
        }
        return "\n".join(
            prompts.get(
                stage,
                [
                    "Continue the same ClauseAI workflow.",
                    "Resume from the current state of the workspace and keep going until the bill is actually done.",
                ],
            )
        )

    def _forced_progress_prompt(self, stage: str, saw_file_change: bool, draft_version: int) -> str:
        if stage == "step3":
            if saw_file_change:
                return (
                    "Continue from Step 3 after the prior draft edit attempt. "
                    "Do not finish the workflow. If Step 3 is complete, move into Step 4."
                )
            return "\n".join(
                [
                    "You finished Step 3 without producing a file change and without reaching Step 5.",
                    "Do not end the workflow.",
                    "If the Step 3 defects you identified are real, edit `current_draft.txt` now with the smallest justified fix.",
                    "If Step 3 truly needs no edit, say that briefly and move into Step 4 in the same turn.",
                ]
            )
        return "\n".join(
            [
                "You finished Step 4 without reaching Step 5.",
                "Do not end the workflow.",
                "If there is a justified Step 4 improvement, edit `current_draft.txt` now.",
                "If Step 4 is complete, move directly into Step 5 in the same turn.",
            ]
        )
