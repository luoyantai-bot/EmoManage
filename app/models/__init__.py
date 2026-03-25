# ===========================================
# SQLAlchemy ORM 模型包
# ===========================================
"""
数据库模型定义

包含:
- Tenant: 租户/商家表
- User: 用户表
- Device: 设备表
- MeasurementRecord: 检测记录表
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Float, Integer, Text, JSON, ForeignKey, func, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


class TimestampMixin:
    """
    时间戳混入类
    为所有模型提供 created_at 和 updated_at 字段
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )


# 导入所有模型
from app.models.tenant import Tenant
from app.models.user import User
from app.models.device import Device
from app.models.measurement import MeasurementRecord

__all__ = ["Base", "TimestampMixin", "Tenant", "User", "Device", "MeasurementRecord"]
