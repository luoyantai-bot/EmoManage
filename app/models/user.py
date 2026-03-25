# ===========================================
# 用户模型
# ===========================================
"""
User 模型定义

用户是租户下的终端用户，使用智能坐垫进行健康检测。
系统会记录用户的生理数据和健康报告。
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Float, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.measurement import MeasurementRecord


class User(Base, TimestampMixin):
    """
    用户表
    
    属性:
        id: UUID主键，自动生成
        tenant_id: 所属租户ID
        name: 用户姓名
        gender: 性别 (male/female/other)
        age: 年龄
        height: 身高(cm)
        weight: 体重(kg)
        bmi: 身体质量指数(自动计算)
        phone: 联系电话
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="用户ID"
    )

    # 外键关联
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="用户姓名"
    )
    
    gender: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="other",
        comment="性别: male/female/other"
    )
    
    age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="年龄"
    )
    
    height: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="身高(cm)"
    )
    
    weight: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="体重(kg)"
    )
    
    bmi: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="身体质量指数(自动计算)"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="联系电话"
    )

    # 关联关系
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users"
    )
    
    measurement_records: Mapped[List["MeasurementRecord"]] = relationship(
        "MeasurementRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', tenant_id={self.tenant_id})>"

    def calculate_bmi(self) -> Optional[float]:
        """
        计算BMI指数
        
        BMI = weight(kg) / (height(m))^2
        
        Returns:
            BMI值，如果身高或体重缺失则返回None
        """
        if self.height and self.weight and self.height > 0:
            height_in_meters = self.height / 100  # cm转m
            return round(self.weight / (height_in_meters ** 2), 2)
        return None


@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def auto_calculate_bmi(mapper, connection, target):
    """
    在保存前自动计算BMI
    当身高或体重发生变化时自动更新BMI值
    """
    target.bmi = target.calculate_bmi()


@event.listens_for(User.gender, 'set')
def validate_gender(target, value, oldvalue, initiator):
    """验证性别的有效性"""
    valid_genders = ["male", "female", "other"]
    if value not in valid_genders:
        raise ValueError(f"无效的性别: {value}，有效值为: {valid_genders}")
    return value
