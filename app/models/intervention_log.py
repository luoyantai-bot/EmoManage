# ===========================================
# Intervention Log Model
# ===========================================
"""
InterventionLog - 干预执行日志模型

记录每次规则触发和执行的详细信息，用于追踪干预效果。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base

if TYPE_CHECKING:
    from app.models.intervention import InterventionRule
    from app.models.user import User
    from app.models.measurement import MeasurementRecord
    from app.models.tenant import Tenant


class InterventionLog(Base):
    """
    干预执行日志表
    
    记录每次规则触发的详细信息，包括触发指标快照、执行动作、执行结果等。
    
    Attributes:
        id: UUID主键
        rule_id: 关联的规则ID
        measurement_id: 触发的检测记录ID
        user_id: 用户ID
        tenant_id: 租户ID
        device_code: 触发的坐垫设备编码
        trigger_metrics: 触发时的指标快照
        actions_executed: 执行的动作列表
        status: 执行状态
        webhook_response: Webhook调用结果
        created_at: 创建时间
    """
    __tablename__ = "intervention_logs"
    __table_args__ = {"comment": "干预执行日志表"}
    
    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="日志ID"
    )
    
    # 外键
    rule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intervention_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="规则ID"
    )
    
    measurement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("measurement_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="检测记录ID"
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
    
    # 触发信息
    device_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="触发的坐垫设备编码"
    )
    
    trigger_metrics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="触发时的指标快照"
    )
    
    actions_executed: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="执行的动作列表"
    )
    
    # 状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="triggered",
        index=True,
        comment="状态: triggered/executed/failed/skipped"
    )
    
    webhook_response: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Webhook调用结果"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="错误信息（如有）"
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="创建时间"
    )
    
    # 关联关系
    rule: Mapped[Optional["InterventionRule"]] = relationship(
        "InterventionRule",
        back_populates="logs"
    )
    
    def __repr__(self) -> str:
        return f"<InterventionLog(id={self.id}, status='{self.status}', device='{self.device_code}')>"
