from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clauseai_backend import __version__
from clauseai_backend.api import api_router
from clauseai_backend.bootstrap_user_db import ensure_user_db
from clauseai_backend.core.config import settings
from clauseai_backend.services.editor_runtime import EditorRuntimeManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_user_db()
    runtime = EditorRuntimeManager()
    runtime.recover_stale_sessions()
    app.state.editor_runtime = runtime
    yield
    await runtime.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_cors_origins) or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "clauseai_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
