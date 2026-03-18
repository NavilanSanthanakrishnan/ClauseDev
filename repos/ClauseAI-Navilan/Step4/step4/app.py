from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from step4.config import get_settings
from step4.models import HealthResponse
from step4.services.conflict_analysis import ConflictAnalysisService
from step4.services.database import Database


settings = get_settings()
database = Database(settings)
APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str((APP_DIR / "templates").resolve()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.open()
    app.state.database = database
    app.state.conflict_service = ConflictAnalysisService(database)
    yield
    database.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str((APP_DIR / "static").resolve())), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    missing = database.missing_indexes()
    status = "degraded" if settings.require_bootstrap_indexes and any(missing.values()) else "ok"
    return HealthResponse(status=status, databases_ready=True, missing_indexes=missing)


@app.post("/api/analyze")
async def analyze_conflicts(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="File is too large.")

    try:
        service: ConflictAnalysisService = app.state.conflict_service
        result = await asyncio.to_thread(service.analyze, filename=file.filename, payload=payload)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
