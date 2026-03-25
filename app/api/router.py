# ===========================================
# API 总路由配置
# ===========================================
"""
统一注册所有API路由

所有路由统一使用 /api/v1 前缀
"""

from fastapi import APIRouter

from app.api.tenants import router as tenants_router
from app.api.users import router as users_router
from app.api.devices import router as devices_router
from app.api.measurements import router as measurements_router


# 创建总路由器
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(
    tenants_router,
    prefix="/tenants",
    tags=["租户管理"]
)

api_router.include_router(
    users_router,
    prefix="/users",
    tags=["用户管理"]
)

api_router.include_router(
    devices_router,
    prefix="/devices",
    tags=["设备管理"]
)

api_router.include_router(
    measurements_router,
    prefix="/measurements",
    tags=["检测记录管理"]
)
