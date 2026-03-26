# ===========================================
# 告警记录模型
# ===========================================
"""
AlertRecord 模型定义

用于记录设备推送的各类告警事件，包括：
- SOS 告警
- 设备拔出
- 设备剪断
- 湿床告警
- 疑似生命异常
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, JSON, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.user import User
    from app.models.tenant import Tenant


# 告警类型枚举
ALERT_TYPES = {
    "5": ("sos", "SOS紧急呼叫"),
    "6": ("device_unplugged", "设备拔出"),
    "7": ("device_cut", "设备剪断"),
    "8": ("wet_bed", "湿床告警"),
    "9": ("life_abnormal", "疑似生命异常"),
}

# 告警状态枚举
ALERT_STATUSES = ["pending", "acknowledged", "resolved"]


class AlertRecord(Base, TimestampMixin):
    """
    告警记录表
    
    记录设备推送的所有告警事件，供后续处理和分析
    
    属性:
        id: UUID主键
        device_id: 设备ID
        user_id: 用户ID（可选，关联当前使用设备的用户）
        tenant_id: 租户ID
        alert_type: 告警类型 (sos/device_unplugged/device_cut/wet_bed/life_abnormal)
        alert_code: 告警代码（对应厂家的sosType值）
        message: 告警消息
        raw_data: 原始推送数据(JSON)
        status: 处理状态 (pending/acknowledged/resolved)
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "alert_records"
    __table_args__ = {"comment": "告警记录表"}

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="告警ID"
    )

    # 外键关联
    device_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="设备ID"
    )
    
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="用户ID"
    )
    
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="租户ID"
    )

    # 告警信息
    alert_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="告警类型: sos/device_unplugged/device_cut/wet_bed/life_abnormal"
    )
    
    alert_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="告警代码(对应sosType)"
    )
    
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="告警消息"
    )
    
    raw_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="原始推送数据"
    )

    # 处理状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="处理状态: pending/acknowledged/resolved"
    )

    # 关联关系
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="alerts"
    )
    
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="alerts"
    )
    
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="alerts"
    )

    def __repr__(self) -> str:
        return f"<AlertRecord(id={self.id}, type='{self.alert_type}', status='{self.status}')>"

    @staticmethod
    def get_alert_type(sos_type: str) -> tuple[str, str]:
        """
        根据厂家sosType获取告警类型和消息
        
        Args:
            sos_type: 厂家告警代码 (5/6/7/8/9)
        
        Returns:
            (alert_type, message) 元组
        """
        return ALERT_TYPES.get(sos_type, ("unknown", f"未知告警(代码:{sos_type})"))


@event.listens_for(AlertRecord.status, 'set')
def validate_alert_status(target, value, oldvalue, initiator):
    """验证告警状态的有效性"""
    if value not in ALERT_STATUSES:
        raise ValueError(f"无效的告警状态: {value}，有效值为: {ALERT_STATUSES}")
    return value
