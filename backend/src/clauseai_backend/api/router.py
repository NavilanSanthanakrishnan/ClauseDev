from fastapi import APIRouter

from clauseai_backend.api import auth, chat, editor, health, pipeline, projects, reference, settings, workflow_content

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(pipeline.router)
api_router.include_router(reference.router)
api_router.include_router(workflow_content.router)
api_router.include_router(editor.router)
api_router.include_router(settings.router)
api_router.include_router(chat.router)
