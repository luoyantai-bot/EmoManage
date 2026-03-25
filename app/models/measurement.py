# ===========================================
# 检测记录模型
# ===========================================
"""
MeasurementRecord 模型定义

检测记录是用户使用智能坐垫进行健康检测的完整记录。
包含原始数据、算法计算的衍生指标、以及AI生成的健康报告。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Text, JSON, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.device import Device


class MeasurementRecord(Base, TimestampMixin):
    """
    检测记录表
    
    属性:
        id: UUID主键，自动生成
        user_id: 用户ID
        device_id: 设备ID
        start_time: 检测开始时间
        end_time: 检测结束时间
        duration_minutes: 检测时长(分钟)
        status: 记录状态 (measuring/processing/completed/failed)
        raw_data_summary: 原始数据摘要(JSON)
        derived_metrics: 衍生指标(JSON)
        ai_analysis: AI分析报告(Markdown格式)
        health_score: 健康评分(0-100)
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "measurement_records"
    __table_args__ = {"comment": "检测记录表"}

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="记录ID"
    )

    # 外键关联
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID"
    )
    
    device_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="设备ID"
    )

    # 检测时间
    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="检测开始时间"
    )
    
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="检测结束时间"
    )
    
    duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="检测时长(分钟)"
    )

    # 记录状态
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="measuring",
        index=True,
        comment="记录状态: measuring/processing/completed/failed"
    )

    # 数据存储
    raw_data_summary: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="""
        原始数据摘要(JSON)
        包含:
        - heart_rate_avg: 平均心率
        - heart_rate_max: 最大心率
        - heart_rate_min: 最小心率
        - breathing_avg: 平均呼吸频率
        - breathing_max: 最大呼吸频率
        - breathing_min: 最小呼吸频率
        - sleep_duration: 睡眠时长
        - bed_status: 在床状态统计
        """
    )
    
    derived_metrics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="""
        衍生指标(JSON) - 由算法计算
        包含:
        - hrv: 心率变异性
        - stress_index: 压力指数(0-100)
        - relaxation_index: 放松指数(0-100)
        - sleep_quality: 睡眠质量评分
        - emotional_state: 情绪状态评估
        - fatigue_level: 疲劳程度
        """
    )
    
    ai_analysis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI分析报告(Markdown格式)"
    )

    # 评分
    health_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="健康评分(0-100)"
    )

    # 关联关系
    user: Mapped["User"] = relationship(
        "User",
        back_populates="measurement_records"
    )
    
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="measurement_records"
    )

    def __repr__(self) -> str:
        return f"<MeasurementRecord(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

    def calculate_duration(self) -> Optional[int]:
        """
        计算检测时长(分钟)
        
        Returns:
            检测时长(分钟)，如果开始或结束时间缺失则返回None
        """
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return None


@event.listens_for(MeasurementRecord, 'before_insert')
@event.listens_for(MeasurementRecord, 'before_update')
def auto_calculate_duration(mapper, connection, target):
    """
    在保存前自动计算检测时长
    当开始和结束时间都存在时自动计算
    """
    if target.start_time and target.end_time:
        target.duration_minutes = target.calculate_duration()


@event.listens_for(MeasurementRecord.status, 'set')
def validate_record_status(target, value, oldvalue, initiator):
    """验证记录状态的有效性"""
    valid_statuses = ["measuring", "processing", "completed", "failed"]
    if value not in valid_statuses:
        raise ValueError(f"无效的记录状态: {value}，有效值为: {valid_statuses}")
    return value


@event.listens_for(MeasurementRecord.health_score, 'set')
def validate_health_score(target, value, oldvalue, initiator):
    """验证健康评分范围"""
    if value is not None and (value < 0 or value > 100):
        raise ValueError(f"健康评分必须在0-100范围内，当前值: {value}")
    return value
