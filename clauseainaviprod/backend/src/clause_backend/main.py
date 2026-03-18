from fastapi import FastAPI

from clause_backend import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="Clause API", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "clause_backend.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
    )

