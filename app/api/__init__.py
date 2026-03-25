# ===========================================
# API 路由包
# ===========================================
"""
API 路由模块

包含:
- router: 总路由注册
- tenants: 租户管理路由
- users: 用户管理路由
- devices: 设备管理路由
- measurements: 检测记录管理路由
"""

from fastapi import APIRouter

from app.api.router import api_router

__all__ = ["api_router"]
