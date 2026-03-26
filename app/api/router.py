# ===========================================
# API Router Configuration
# ===========================================
"""
Register all API routes

All routes use /api/v1 prefix
"""

from fastapi import APIRouter

from app.api.tenants import router as tenants_router
from app.api.users import router as users_router
from app.api.devices import router as devices_router
from app.api.measurements import router as measurements_router
from app.api.webhooks import router as webhooks_router
from app.api.realtime import router as realtime_router


# Create main router
api_router = APIRouter()

# Register module routes
api_router.include_router(
    tenants_router,
    prefix="/tenants",
    tags=["Tenant Management"]
)

api_router.include_router(
    users_router,
    prefix="/users",
    tags=["User Management"]
)

api_router.include_router(
    devices_router,
    prefix="/devices",
    tags=["Device Management"]
)

api_router.include_router(
    measurements_router,
    prefix="/measurements",
    tags=["Measurement Records"]
)

api_router.include_router(
    webhooks_router,
    prefix="/webhook",
    tags=["Webhooks"]
)

api_router.include_router(
    realtime_router,
    prefix="/realtime",
    tags=["Real-time Data"]
)
