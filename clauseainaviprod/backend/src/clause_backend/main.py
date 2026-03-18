from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clause_backend import __version__
from clause_backend.api import router
from clause_backend.core.config import settings
from clause_backend.services.bootstrap import ensure_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "clause_backend.main:app",
        host="127.0.0.1",
        port=8001,
        reload=settings.debug,
    )
