from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from step1.config import get_settings
from step1.models import HealthResponse, SearchRequestOptions, WorkflowMetadataUpdateRequest, WorkflowSteerRequest
from step1.services.database import Database
from step1.services.workflow_service import WorkflowService


settings = get_settings()
database = Database(settings)
APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str((APP_DIR / "templates").resolve()))
STATIC_ASSET_VERSION = str(
    max(
        int((APP_DIR / "static" / "app.js").stat().st_mtime),
        int((APP_DIR / "static" / "styles.css").stat().st_mtime),
    )
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.open()
    app.state.database = database
    workflow_service = WorkflowService(database)
    await workflow_service.start()
    app.state.workflow_service = workflow_service
    yield
    await workflow_service.stop()
    database.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str((APP_DIR / "static").resolve())), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "asset_version": STATIC_ASSET_VERSION,
        },
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    missing_indexes = database.missing_indexes()
    if missing_indexes and settings.require_bootstrap_indexes:
        status = "degraded"
    else:
        status = "ok"
    return HealthResponse(status=status, database_ready=True, missing_indexes=missing_indexes)


@app.post("/api/workflow/upload")
async def upload_bill(
    file: UploadFile = File(...),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="File is too large.")

    try:
        workflow_service: WorkflowService = app.state.workflow_service
        session = await workflow_service.create_session(filename=file.filename, payload=payload)
        return session.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/metadata/generate")
async def generate_workflow_metadata(session_id: str) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.generate_metadata(session_id)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/metadata")
async def update_workflow_metadata(session_id: str, payload: WorkflowMetadataUpdateRequest) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.update_metadata(session_id, payload.profile)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/similar-bills/start")
async def start_similar_bill_search(session_id: str) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    options = SearchRequestOptions(final_result_limit=settings.final_result_limit)
    try:
        session = await workflow_service.start_similarity_search(session_id, options)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/search")
async def legacy_upload_alias(file: UploadFile = File(...)) -> dict:
    return await upload_bill(file)


@app.get("/api/workflow/{session_id}")
async def get_workflow_session(session_id: str) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.get_session(session_id)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/workflow/{session_id}/stream")
async def workflow_stream(session_id: str) -> StreamingResponse:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        stream = workflow_service.stream(session_id)
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/approve")
async def approve_pending_diff(session_id: str) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.approve_pending_diff(session_id)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/reject")
async def reject_pending_diff(session_id: str) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.reject_pending_diff(session_id)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/workflow/{session_id}/steer")
async def steer_workflow(session_id: str, payload: WorkflowSteerRequest) -> dict:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.steer(session_id, payload.message)
        return session.model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/workflow/{session_id}/draft", response_class=PlainTextResponse)
async def download_current_draft(session_id: str) -> PlainTextResponse:
    workflow_service: WorkflowService = app.state.workflow_service
    try:
        session = await workflow_service.get_session(session_id)
        filename = f"{Path(session.original_filename).stem}-current-draft.txt"
        return PlainTextResponse(
            content=session.current_draft_text,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
