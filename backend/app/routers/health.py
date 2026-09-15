"""Health endpoint."""

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..models import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, data_root=str(settings.data_root))
