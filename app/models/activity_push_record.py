# ===========================================
# Activity Push Record Model
# ===========================================
"""
ActivityPushRecord - 活动推送记录模型

记录活动推送给用户的历史，追踪推送状态和用户响应。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.user import User


class ActivityPushRecord(Base):
    """
    活动推送记录表
    
    记录每次活动推送给用户的详情，包括推送原因、推送状态等。
    
    Attributes:
        id: UUID主键
        activity_id: 关联的活动ID
        user_id: 推送目标用户ID
        push_reason: 推送原因
        push_status: 推送状态
        matched_tags: 匹配的用户标签
        read_at: 用户阅读时间
        created_at: 创建时间
    """
    __tablename__ = "activity_push_records"
    __table_args__ = {"comment": "活动推送记录表"}
    
    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="推送记录ID"
    )
    
    # 外键
    activity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="活动ID"
    )
    
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID"
    )
    
    # 推送信息
    push_reason: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="推送原因（如：用户压力指数>70，匹配高压力标签）"
    )
    
    matched_tags: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="匹配的用户标签"
    )
    
    # 推送状态
    push_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="推送状态: pending/sent/read"
    )
    
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="用户阅读时间"
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
    activity: Mapped["Activity"] = relationship(
        "Activity",
        back_populates="push_records"
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="activity_push_records"
    )
    
    def __repr__(self) -> str:
        return f"<ActivityPushRecord(id={self.id}, status='{self.push_status}')>"
