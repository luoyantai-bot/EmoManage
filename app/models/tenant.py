# ===========================================
# 租户/商家模型
# ===========================================
"""
Tenant 模型定义

租户是SaaS系统的核心概念，每个租户代表一个使用系统的商家/机构。
支持多种商家类型：中医馆、酒店、养生中心等。
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.device import Device


class Tenant(Base, TimestampMixin):
    """
    租户/商家表
    
    属性:
        id: UUID主键，自动生成
        name: 商家名称，必填
        type: 商家类型 (chinese_medicine/hotel/wellness_center)
        contact_phone: 联系电话
        address: 商家地址
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "tenants"
    __table_args__ = {"comment": "租户/商家表"}

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="租户ID"
    )

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="商家名称"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="wellness_center",
        comment="商家类型: chinese_medicine/hotel/wellness_center"
    )
    
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="联系电话"
    )
    
    address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="商家地址"
    )

    # 关联关系
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    devices: Mapped[List["Device"]] = relationship(
        "Device",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', type='{self.type}')>"


@event.listens_for(Tenant.type, 'set')
def validate_tenant_type(target, value, oldvalue, initiator):
    """验证商家类型的有效性"""
    valid_types = ["chinese_medicine", "hotel", "wellness_center"]
    if value not in valid_types:
        raise ValueError(f"无效的商家类型: {value}，有效值为: {valid_types}")
    return value
