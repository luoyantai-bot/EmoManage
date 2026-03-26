# ===========================================
# Activity Model
# ===========================================
"""
Activity - 活动模型

用于管理B端商家发布的健康促进活动，如：
- 颂钵冥想
- 八段锦课程
- 中医体质调理讲座
- 瑜伽放松课
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.activity_push_record import ActivityPushRecord


class Activity(Base, TimestampMixin):
    """
    活动表
    
    管理B端商家发布的各类健康促进活动，支持智能匹配目标用户。
    
    Attributes:
        id: UUID主键
        tenant_id: 所属租户ID
        title: 活动标题
        description: 活动描述
        activity_type: 活动类型
        start_time: 开始时间
        end_time: 结束时间
        location: 活动地点
        max_participants: 最大参与人数
        target_tags: 目标用户标签
        status: 活动状态
    """
    __tablename__ = "activities"
    __table_args__ = {"comment": "活动表"}
    
    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="活动ID"
    )
    
    # 外键
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="租户ID"
    )
    
    # 基本信息
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="活动标题"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="活动描述"
    )
    
    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
        index=True,
        comment="活动类型: singing_bowl/meditation/yoga/tcm_workshop/other"
    )
    
    # 时间地点
    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="开始时间"
    )
    
    end_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="结束时间"
    )
    
    location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="活动地点"
    )
    
    # 参与设置
    max_participants: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="最大参与人数"
    )
    
    current_participants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="当前报名人数"
    )
    
    # 目标标签
    target_tags: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="""
        目标用户标签列表
        可选值:
        - high_stress: 高压力
        - extreme_stress: 极高压力
        - anxiety: 焦虑倾向
        - high_anxiety: 高焦虑
        - low_hrv: 低心率变异性
        - fatigue: 疲劳
        - yin_deficiency: 阴虚质
        - yang_deficiency: 阳虚质
        - qi_stagnation: 气郁质
        - blood_stasis: 血瘀质
        - poor_posture: 姿态不佳
        """
    )
    
    # 状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="状态: draft/published/ongoing/completed/cancelled"
    )
    
    # 关联关系
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="activities"
    )
    
    push_records: Mapped[List["ActivityPushRecord"]] = relationship(
        "ActivityPushRecord",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # 类型标签映射
    TYPE_LABELS = {
        "singing_bowl": "颂钵冥想",
        "meditation": "正念冥想",
        "yoga": "瑜伽课程",
        "tcm_workshop": "中医调理",
        "other": "其他活动"
    }
    
    @property
    def type_label(self) -> str:
        """获取活动类型中文标签"""
        return self.TYPE_LABELS.get(self.activity_type, self.activity_type)
    
    def __repr__(self) -> str:
        return f"<Activity(id={self.id}, title='{self.title}', type='{self.activity_type}')>"
