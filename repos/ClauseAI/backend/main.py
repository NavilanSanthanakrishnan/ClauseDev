import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import ClientDisconnect
from app.core.config import (
    API_TITLE,
    API_VERSION,
    API_DESCRIPTION,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    CORS_ALLOW_ORIGINS,
    LOG_REQUEST_BODY_PREVIEW,
)
from app.core.logging_config import (
    clear_request_context,
    configure_logging,
    sanitize_headers,
    sanitize_payload,
    set_request_context,
)
from app.core.supabase_auth import authenticate_request
from typing import Dict, Any
from app.api import (
    auth,
    health,
    bill_extraction,
    title_description,
    bill_similarity,
    similar_bills_loader,
    bill_inspect,
    bill_analysis,
    conflict_analysis,
    stakeholder_analysis,
    user,
    workflow,
)

configure_logging()
logger = logging.getLogger("clauseai.api")

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limit_store: Dict[str, Dict[str, Any]] = {}

@app.middleware("http")
async def api_call_logger(request: Request, call_next):
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    client_ip = request.client.host if request.client else "unknown"
    context_token = set_request_context(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=client_ip,
    )

    try:
        request_body_bytes = await request.body()
    except ClientDisconnect:
        logger.warning(
            "Client disconnected while reading request body",
            extra={
                "event": "http_request_disconnected",
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
            },
        )
        clear_request_context(context_token)
        return JSONResponse(
            status_code=499,
            content={"detail": "Client disconnected before request body was read"}
        )

    async def receive():
        return {"type": "http.request", "body": request_body_bytes, "more_body": False}
    request._receive = receive

    request_body = None
    if LOG_REQUEST_BODY_PREVIEW:
        try:
            request_body = json.loads(request_body_bytes.decode("utf-8"))
        except Exception:
            request_body = request_body_bytes.decode("utf-8", errors="replace")

    if LOG_REQUEST_BODY_PREVIEW:
        logger.info(
            "Incoming API request",
            extra={
                "event": "http_request_started",
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "query_params": sanitize_payload(dict(request.query_params)),
                "headers": sanitize_headers(dict(request.headers)),
                "request_body": sanitize_payload(request_body),
            },
        )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception(
            "Unhandled API exception",
            extra={
                "event": "http_request_unhandled_exception",
                "duration_ms": duration_ms,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "query_params": sanitize_payload(dict(request.query_params)),
                "headers": sanitize_headers(dict(request.headers)),
                "request_body": sanitize_payload(request_body) if LOG_REQUEST_BODY_PREVIEW else None,
            },
        )
        clear_request_context(context_token)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    log_payload = {
        "event": "http_request_completed",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "query_params": sanitize_payload(dict(request.query_params)),
        "response_headers": sanitize_headers(dict(response.headers)),
    }
    if LOG_REQUEST_BODY_PREVIEW:
        log_payload["request_body"] = sanitize_payload(request_body)

    if response.status_code >= 500:
        logger.error("API request completed with server error", extra=log_payload)
    elif response.status_code >= 400:
        logger.warning("API request completed with client error", extra=log_payload)
    else:
        logger.info("API request completed", extra=log_payload)

    try:
        body = b""
        if response.body_iterator is not None:
            async for chunk in response.body_iterator:
                body += chunk
        else:
            body = response.body or b""

        headers = dict(response.headers)
        headers["X-Request-ID"] = request_id
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background
        )
    finally:
        clear_request_context(context_token)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    record = rate_limit_store.get(client_ip)

    if record is None or now - record["window_start"] > RATE_LIMIT_WINDOW_SECONDS:
        rate_limit_store[client_ip] = {"window_start": now, "count": 1}
    else:
        record["count"] += 1
        if record["count"] > RATE_LIMIT_REQUESTS:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "client_ip": client_ip,
                    "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
                    "max_requests": RATE_LIMIT_REQUESTS,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"}
            )

    return await call_next(request)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if (
        path == "/health"
        or path.startswith("/health/")
        or path == "/auth/status"
        or path.startswith("/docs")
        or path.startswith("/openapi")
        or path.startswith("/redoc")
    ):
        return await call_next(request)

    try:
        request.state.current_user = authenticate_request(request)
    except HTTPException as error:
        logger.warning(
            "Unauthorized request blocked",
            extra={
                "event": "auth_rejected",
                "path": path,
                "method": request.method,
                "client_ip": request.client.host if request.client else "unknown",
                "status_code": error.status_code,
            },
        )
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail},
        )

    return await call_next(request)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(bill_extraction.router, prefix="/api/bill_extraction", tags=["Bill Text Extraction"])
app.include_router(title_description.router, prefix="/api/title_description", tags=["Title/Description/Summary"])
app.include_router(bill_similarity.router, prefix="/api/bill_similarity", tags=["Bill Similarity"])
app.include_router(similar_bills_loader.router, prefix="/api/similar_bills_loader", tags=["Similar Bills Loading"])
app.include_router(bill_inspect.router, prefix="/api/bill_inspect", tags=["Bill Inspect"])
app.include_router(bill_analysis.router, prefix="/api/bill_analysis", tags=["Bill Analysis"])
app.include_router(conflict_analysis.router, prefix="/api/conflict_analysis", tags=["Legal Conflict Analysis"])
app.include_router(stakeholder_analysis.router, prefix="/api/stakeholder_analysis", tags=["Stakeholder Analysis"])
app.include_router(user.router, prefix="/api/user", tags=["User"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow"])

@app.get("/")
async def root():
    return {
        "message": "Legislative Bill Analysis API",
        "version": API_VERSION,
        "endpoints": {
            "health": "/health",
            "bill_extraction": "/api/bill_extraction/extract-text",
            "title_description": "/api/title_description/generate-metadata",
            "bill_similarity": "/api/bill_similarity/find-similar",
            "similar_bills_loader": "/api/similar_bills_loader/load-similar-bills",
            "bill_inspect": "/api/bill_inspect/inspect",
            "bill_analysis": "/api/bill_analysis/analyze-bill",
            "conflict_analysis": "/api/conflict_analysis/analyze-conflicts",
            "stakeholder_analysis": "/api/stakeholder_analysis/analyze-stakeholders",
            "user_profile": "/api/user/me",
            "workflow_current": "/api/workflow/current",
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)