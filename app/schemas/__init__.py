# ===========================================
# Pydantic Schemas 包
# ===========================================
"""
Pydantic 数据校验模型

包含:
- Tenant Schemas: 租户相关的输入输出模型
- User Schemas: 用户相关的输入输出模型
- Device Schemas: 设备相关的输入输出模型
- MeasurementRecord Schemas: 检测记录相关的输入输出模型
- Common Schemas: 通用响应模型
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ===========================================
# 通用响应模型
# ===========================================

T = TypeVar("T")


class BaseResponse(BaseModel):
    """
    统一API响应格式基类
    
    所有API返回都应该使用此格式
    """
    code: int = Field(default=200, description="状态码，200表示成功")
    msg: str = Field(default="success", description="响应消息")


class DataResponse(BaseResponse, Generic[T]):
    """
    单条数据响应
    
    用于返回单个对象的情况
    """
    data: T = Field(description="响应数据")


class ListResponse(BaseResponse, Generic[T]):
    """
    分页列表响应
    
    用于返回分页数据
    """
    data: "PageData[T]" = Field(description="分页数据")


class PageData(BaseModel, Generic[T]):
    """
    分页数据结构
    """
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页记录数")
    items: List[T] = Field(default_factory=list, description="数据列表")


# ===========================================
# 基础 Schema Mixin
# ===========================================

class TimestampMixin(BaseModel):
    """
    时间戳混入类
    为响应模型提供 created_at 和 updated_at 字段
    """
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class UUIDMixin(BaseModel):
    """
    UUID混入类
    为响应模型提供 id 字段
    """
    id: UUID = Field(description="唯一标识符")


# 导入所有 Schema
from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
)
from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementUpdate,
    MeasurementResponse,
    MeasurementListResponse,
)
from app.schemas.webhook import (
    RealtimeDataWebhook,
    ReportDataWebhook,
    WebhookResponse,
)

__all__ = [
    # 通用响应
    "BaseResponse",
    "DataResponse",
    "ListResponse",
    "PageData",
    # 混入类
    "TimestampMixin",
    "UUIDMixin",
    # Tenant Schemas
    "TenantCreate",
    "TenantUpdate",
    "TenantResponse",
    "TenantListResponse",
    # User Schemas
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    # Device Schemas
    "DeviceCreate",
    "DeviceUpdate",
    "DeviceResponse",
    "DeviceListResponse",
    # Measurement Schemas
    "MeasurementCreate",
    "MeasurementUpdate",
    "MeasurementResponse",
    "MeasurementListResponse",
    # Webhook Schemas
    "RealtimeDataWebhook",
    "ReportDataWebhook",
    "WebhookResponse",
]
