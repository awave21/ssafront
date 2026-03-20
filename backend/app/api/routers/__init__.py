from fastapi import APIRouter

from app.api.routers.agents import router as agents_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.api_keys import router as api_keys_router
from app.api.routers.auth import router as auth_router
from app.api.routers.bindings import router as bindings_router
from app.api.routers.credentials import router as credentials_router
from app.api.routers.health import router as health_router
from app.api.routers.integrations import router as integrations_router
from app.api.routers.invitations import router as invitations_router
from app.api.routers.model_pricing import router as model_pricing_router
from app.api.routers.runs import router as runs_router
from app.api.routers.users import router as users_router
from app.api.routers.tools import router as tools_router
from app.api.routers.tenant_settings import router as tenant_settings_router
from app.api.routers.webhooks import router as webhooks_router
from app.api.routers.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(credentials_router, prefix="/credentials", tags=["credentials"])
api_router.include_router(invitations_router, prefix="/invitations", tags=["invitations"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(model_pricing_router, prefix="/model-pricing", tags=["model-pricing"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])
api_router.include_router(bindings_router, prefix="/agents", tags=["bindings"])
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
api_router.include_router(webhooks_router, tags=["webhooks"])
api_router.include_router(ws_router, tags=["websocket"])
api_router.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(tenant_settings_router, prefix="/tenant-settings", tags=["tenant-settings"])
