# ===========================================
# 设备模型
# ===========================================
"""
Device 模型定义

设备是智能坐垫硬件在系统中的映射，存储设备的基本信息和状态。
设备通过device_code（对应厂家的SN号）与厂家云平台关联。
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.measurement import MeasurementRecord


class Device(Base, TimestampMixin):
    """
    设备表
    
    属性:
        id: UUID主键，自动生成
        device_code: 设备编码(SN号)，唯一，如"TA0096400014"
        tenant_id: 所属租户ID
        status: 设备状态 (online/offline/in_use)
        device_type: 设备型号
        ble_mac: 蓝牙MAC地址
        wifi_mac: WiFi MAC地址
        firmware_version: 固件版本
        hardware_version: 硬件版本
        cloud_device_id: 厂家云平台设备ID
        last_online_at: 最后在线时间
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "devices"
    __table_args__ = {"comment": "设备表"}

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="设备ID"
    )

    # 设备编码（对应厂家的SN号）
    device_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="设备编码(SN号)，如TA0096400014"
    )

    # 外键关联
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )

    # 设备状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="offline",
        index=True,
        comment="设备状态: online/offline/in_use"
    )
    
    # 设备信息
    device_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="设备型号"
    )
    
    ble_mac: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="蓝牙MAC地址"
    )
    
    wifi_mac: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="WiFi MAC地址"
    )
    
    firmware_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="固件版本"
    )
    
    hardware_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="硬件版本"
    )
    
    # 厂家云平台关联
    cloud_device_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="厂家云平台设备ID"
    )
    
    # 状态追踪
    last_online_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="最后在线时间"
    )

    # 关联关系
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="devices"
    )
    
    measurement_records: Mapped[List["MeasurementRecord"]] = relationship(
        "MeasurementRecord",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, device_code='{self.device_code}', status='{self.status}')>"


@event.listens_for(Device.status, 'set')
def validate_device_status(target, value, oldvalue, initiator):
    """验证设备状态的有效性"""
    valid_statuses = ["online", "offline", "in_use"]
    if value not in valid_statuses:
        raise ValueError(f"无效的设备状态: {value}，有效值为: {valid_statuses}")
    return value
