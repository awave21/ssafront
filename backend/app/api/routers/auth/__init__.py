from fastapi import APIRouter

from app.api.routers.auth.sessions import router as sessions_router
from app.api.routers.auth.tokens import router as tokens_router

router = APIRouter()
router.include_router(tokens_router)
router.include_router(sessions_router)

__all__ = ["router"]
