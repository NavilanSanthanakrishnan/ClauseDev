from fastapi import APIRouter

from app.models.responses import HealthResponse
from app.core.config import API_VERSION

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version=API_VERSION
    )