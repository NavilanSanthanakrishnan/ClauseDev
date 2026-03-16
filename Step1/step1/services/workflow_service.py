from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Any, AsyncIterator

from step1.models import (
    SearchRequestOptions,
    UploadedBillProfile,
    WorkflowEvent,
    WorkflowSession,
)
from step1.services.codex_app_server import CodexAppServerProcess, CodexSessionBridge
from step1.services.database import Database
from step1.services.similar_bills import SimilarBillService
from step1.services.workflow_context import WorkflowContextService
from step1.services.workflow_store import WorkflowStore, utc_now_iso


def _session_event(kind: str, title: str, body: str = "", phase: str = "", **metadata: Any) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=f"{kind}-{utc_now_iso()}",
        kind=kind,
        title=title,
        body=body,
        phase=phase,
        created_at=utc_now_iso(),
        metadata=metadata,
    )


def _profile_has_content(profile: UploadedBillProfile) -> bool:
    for value in profile.model_dump().values():
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


class WorkflowService:
    def __init__(self, db: Database) -> None:
        self.store = WorkflowStore()
        self.context_service = WorkflowContextService(db)
        self.search_service = SimilarBillService(db)
        self.app_server = CodexAppServerProcess()
        self.runners: dict[str, CodexSessionBridge] = {}
        self.sessions: dict[str, WorkflowSession] = {}
        self.subscribers: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self.session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.background_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        await self.app_server.start()

    async def stop(self) -> None:
        for task in list(self.background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.background_tasks.clear()
        for runner in list(self.runners.values()):
            await runner.stop()
        self.runners.clear()
        await self.app_server.stop()

    async def create_session(self, *, filename: str, payload: bytes) -> WorkflowSession:
        file_type, bill_text = await asyncio.to_thread(
            self.search_service.extract_bill,
            filename=filename,
            payload=payload,
        )
        session_id = self.store.create_session_dir()
        now = utc_now_iso()
        session = WorkflowSession(
            session_id=session_id,
            original_filename=filename,
            file_type=file_type,
            created_at=now,
            updated_at=now,
            current_draft_text=bill_text,
            workspace_dir=str(self.store.session_dir(session_id)),
            events=[
                _session_event(
                    "system",
                    "Bill loaded",
                    body="The uploaded bill is ready. Generate metadata to start the retrieval workflow.",
                    phase="upload",
                )
            ],
        )
        self.sessions[session_id] = session
        self.store.save(session)
        self.store.write_context_bundle(session)
        return session

    async def get_session(self, session_id: str) -> WorkflowSession:
        if session_id in self.sessions:
            return self.sessions[session_id]
        session = self.store.load(session_id)
        self.sessions[session_id] = session
        return session

    async def generate_metadata(self, session_id: str) -> WorkflowSession:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            if session.metadata_status == "generating":
                return session
            if session.thread_id:
                raise ValueError("Metadata generation is locked after the Codex editing loop starts.")
            session.current_stage = "metadata"
            session.status = "running"
            session.metadata_status = "generating"
            session.similarity_progress_message = ""
            session.events.append(
                _session_event(
                    "metadata",
                    "Generating metadata",
                    body="Codex is reading the uploaded bill and drafting retrieval metadata.",
                    phase="metadata",
                )
            )
        await self._publish_session(session, persist=True)
        self._spawn_background_task(self._generate_metadata_task(session_id), "generate-metadata")
        return session

    async def update_metadata(self, session_id: str, profile: UploadedBillProfile) -> WorkflowSession:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            if session.thread_id:
                raise ValueError("Metadata cannot be edited after the Codex editing loop starts.")
            session.profile = profile
            session.current_stage = "metadata"
            session.status = "waiting_user"
            session.metadata_status = "ready"
            session.events.append(
                _session_event(
                    "metadata",
                    "Metadata updated",
                    body="The metadata was saved. Start similar-bill search when ready.",
                    phase="metadata",
                )
            )
        self.store.write_context_bundle(session)
        await self._publish_session(session, persist=True)
        return session

    async def start_similarity_search(
        self,
        session_id: str,
        options: SearchRequestOptions | None = None,
    ) -> WorkflowSession:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            if session.thread_id:
                raise ValueError("This session already moved into the Codex editing loop.")
            if session.similarity_status == "running":
                return session
            if not _profile_has_content(session.profile):
                raise ValueError("Generate or enter metadata before searching for similar bills.")
            session.current_stage = "similarity"
            session.status = "running"
            session.metadata_status = "confirmed"
            session.similarity_status = "running"
            session.similarity_progress_message = "Building the similar-bill search plan from your metadata."
            session.search_timings = {}
            session.results = []
            session.source_bills = []
            session.events.append(
                _session_event(
                    "search",
                    "Similar bill search started",
                    body=session.similarity_progress_message,
                    phase="similarity",
                )
            )
        await self._publish_session(session, persist=True)
        self._spawn_background_task(
            self._run_similarity_search(session_id, options or SearchRequestOptions()),
            "similarity-search",
        )
        return session

    async def approve_pending_diff(self, session_id: str) -> WorkflowSession:
        runner = self._require_runner(session_id)
        await runner.approve_pending_diff("accept")
        return runner.session

    async def reject_pending_diff(self, session_id: str) -> WorkflowSession:
        runner = self._require_runner(session_id)
        await runner.approve_pending_diff("decline")
        return runner.session

    async def steer(self, session_id: str, message: str) -> WorkflowSession:
        runner = self._require_runner(session_id)
        await runner.steer(message)
        return runner.session

    async def stream(self, session_id: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self.subscribers[session_id].add(queue)
        session = await self.get_session(session_id)
        await queue.put(json.dumps(session.model_dump()))
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self.subscribers[session_id].discard(queue)

    async def _generate_metadata_task(self, session_id: str) -> None:
        try:
            session = await self.get_session(session_id)
            profile = await asyncio.to_thread(self.search_service.generate_profile, session.current_draft_text)
            async with self.session_locks[session_id]:
                session.profile = profile
                session.current_stage = "metadata"
                session.status = "waiting_user"
                session.metadata_status = "ready"
                session.metadata_last_generated_at = utc_now_iso()
                session.events.append(
                    _session_event(
                        "metadata",
                        "Metadata ready",
                        body="Review or edit the generated metadata, then start similar-bill search.",
                        phase="metadata",
                    )
                )
            self.store.write_context_bundle(session)
            await self._publish_session(session, persist=True)
        except Exception as exc:
            await self._mark_session_error(session_id, str(exc))

    async def _run_similarity_search(self, session_id: str, options: SearchRequestOptions) -> None:
        timings: dict[str, float] = {}
        warnings: list[str] = []
        try:
            session = await self.get_session(session_id)

            started = time.perf_counter()
            lexical_candidates = await asyncio.to_thread(
                self.search_service.repository.lexical_candidates,
                session.profile,
                options,
            )
            lexical_candidates = self.search_service.filter_uploaded_bill(session.current_draft_text, lexical_candidates)
            timings["lexical"] = round(time.perf_counter() - started, 3)

            async with self.session_locks[session_id]:
                session.search_timings = dict(timings)
                session.similarity_progress_message = (
                    f"Lexical retrieval complete. {len(lexical_candidates)} candidate bills found."
                )
                session.events.append(
                    _session_event(
                        "search",
                        "Lexical retrieval complete",
                        body=session.similarity_progress_message,
                        phase="similarity",
                        candidate_count=len(lexical_candidates),
                    )
                )
            await self._publish_session(session, persist=True)

            if not lexical_candidates:
                warnings.append("No lexical candidates were found in the OpenStates corpus.")
                async with self.session_locks[session_id]:
                    session.warnings = warnings
                    session.status = "waiting_user"
                    session.similarity_status = "ready"
                    session.similarity_last_completed_at = utc_now_iso()
                    session.similarity_progress_message = "No similar bills were found."
                self.store.write_context_bundle(session)
                await self._publish_session(session, persist=True)
                return

            semantic_candidates = lexical_candidates[: self.search_service.settings.semantic_input_limit]
            await asyncio.to_thread(self.search_service.repository.hydrate_candidate_texts, semantic_candidates)
            await asyncio.to_thread(self.search_service.apply_structured_context, semantic_candidates)

            started = time.perf_counter()
            reranked = await asyncio.to_thread(
                self.search_service.semantic_ranker.rerank,
                session.profile,
                semantic_candidates,
            )
            timings["semantic"] = round(time.perf_counter() - started, 3)
            interim_results = reranked[: options.final_result_limit]
            for candidate in interim_results:
                candidate.final_score = round(candidate.semantic_score, 4)
                candidate.match_reason = candidate.match_reason or candidate.structured_summary or "Semantic shortlist."
                candidate.match_dimensions = candidate.match_dimensions or ["semantic shortlist"]

            async with self.session_locks[session_id]:
                session.results = interim_results
                session.search_timings = dict(timings)
                session.similarity_progress_message = "Semantic reranking complete. Final Codex judging is running."
                session.events.append(
                    _session_event(
                        "search",
                        "Semantic reranking complete",
                        body=session.similarity_progress_message,
                        phase="similarity",
                    )
                )
            await self._publish_session(session, persist=True)

            llm_input = reranked[: self.search_service.settings.llm_rerank_input_limit]
            started = time.perf_counter()
            llm_response = await asyncio.to_thread(
                self.search_service.final_reranker.rerank,
                session.profile,
                llm_input,
            )
            timings["llm_rerank"] = round(time.perf_counter() - started, 3)

            results = await asyncio.to_thread(
                self.search_service.finalize_candidates,
                profile=session.profile,
                reranked=reranked,
                llm_response=llm_response,
                result_limit=options.final_result_limit,
            )
            source_bills = await asyncio.to_thread(self.context_service.prepare_source_bills, results)

            async with self.session_locks[session_id]:
                session.results = results
                session.source_bills = source_bills
                session.search_timings = dict(timings)
                session.similarity_status = "ready"
                session.similarity_last_completed_at = utc_now_iso()
                session.similarity_progress_message = "Similar bills are ready. Starting the Codex editing loop."
                session.events.append(
                    _session_event(
                        "search",
                        "Similar bills ready",
                        body=session.similarity_progress_message,
                        phase="similarity",
                        result_count=len(results),
                    )
                )
            self.store.write_context_bundle(session)
            await self._publish_session(session, persist=True)
            await self._start_codex_runner(session_id)
        except Exception as exc:
            await self._mark_similarity_error(session_id, warnings, str(exc))

    async def _start_codex_runner(self, session_id: str) -> None:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            if session_id in self.runners:
                return
        runner = CodexSessionBridge(session=session, store=self.store, publish=self._publish_session)
        self.runners[session_id] = runner
        await runner.start()

    async def _mark_similarity_error(self, session_id: str, warnings: list[str], message: str) -> None:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            session.status = "error"
            session.similarity_status = "error"
            session.error_message = message
            if warnings:
                session.warnings = warnings
            session.events.append(
                _session_event(
                    "error",
                    "Similar bill search failed",
                    body=message,
                    phase="similarity",
                )
            )
        await self._publish_session(session, persist=True)

    async def _mark_session_error(self, session_id: str, message: str) -> None:
        session = await self.get_session(session_id)
        async with self.session_locks[session_id]:
            session.status = "error"
            session.error_message = message
            session.events.append(_session_event("error", "Workflow error", body=message))
        await self._publish_session(session, persist=True)

    async def _publish_session(self, session: WorkflowSession, persist: bool) -> None:
        if persist:
            self.store.save(session)
        payload = json.dumps(session.model_dump())
        for queue in list(self.subscribers.get(session.session_id, set())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                await queue.put(payload)

    def _require_runner(self, session_id: str) -> CodexSessionBridge:
        runner = self.runners.get(session_id)
        if not runner:
            raise ValueError("This workflow session has not reached the live Codex editing loop yet.")
        return runner

    def _spawn_background_task(self, coroutine: Any, label: str) -> None:
        task = asyncio.create_task(self._run_background_task(coroutine, label))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _run_background_task(self, coroutine: Any, label: str) -> None:
        try:
            await coroutine
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"workflow background task failed ({label}): {exc}")
