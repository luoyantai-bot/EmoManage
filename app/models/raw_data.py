# ===========================================
# 设备原始数据模型
# ===========================================
"""
RawDeviceData 模型定义

用于持久化存储设备推送的原始实时数据，包括：
- 心率数据
- 呼吸数据
- 在床状态
- 睡眠状态
- 各类信号数据
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Index, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin


class RawDeviceData(Base):
    """
    设备原始数据表
    
    持久化存储从Webhook接收的所有实时数据，
    用于历史数据分析和备份
    
    属性:
        id: UUID主键
        device_code: 设备编码
        heart_rate: 心率(bpm)
        breathing: 呼吸频率(次/分钟)
        signal: 信号强度
        sos_type: SOS类型 (5=SOS, 6=拔出, 7=剪断, 8=湿床, 9=生命异常)
        bed_status: 在床状态 (1=在床, 0=离床)
        sleep_status: 睡眠状态 (0=离枕, 1=正常, 2=打鼾, 3=翻身, 4=呼吸暂停)
        snore: 鼾声强度
        raw_timestamp: 厂家时间戳字符串
        received_at: 我方接收时间
    """
    __tablename__ = "raw_device_data"
    __table_args__ = (
        Index("ix_raw_device_data_device_code_received_at", "device_code", "received_at"),
        {"comment": "设备原始数据表"}
    )

    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="数据ID"
    )

    # 设备标识
    device_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="设备编码(SN号)"
    )

    # 生理数据
    heart_rate: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="心率(bpm)"
    )
    
    breathing: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="呼吸频率(次/分钟)"
    )
    
    signal: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="信号强度"
    )

    # 状态数据
    sos_type: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="SOS类型: 5=SOS, 6=拔出, 7=剪断, 8=湿床, 9=生命异常"
    )
    
    bed_status: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="在床状态: 1=在床, 0=离床"
    )
    
    sleep_status: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="睡眠状态: 0=离枕, 1=正常, 2=打鼾, 3=翻身, 4=呼吸暂停"
    )
    
    snore: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="鼾声强度"
    )

    # 时间戳
    raw_timestamp: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="厂家时间戳"
    )
    
    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="接收时间"
    )

    def __repr__(self) -> str:
        return f"<RawDeviceData(id={self.id}, device_code='{self.device_code}', hr={self.heart_rate})>"

    @classmethod
    def from_webhook_data(cls, device_code: str, data: dict) -> "RawDeviceData":
        """
        从Webhook数据创建实例
        
        Args:
            device_code: 设备编码
            data: Webhook推送的原始数据
        
        Returns:
            RawDeviceData 实例
        """
        return cls(
            device_code=device_code,
            heart_rate=int(data.get("heartRate", 0) or 0) if data.get("heartRate") else None,
            breathing=int(data.get("breathing", 0) or 0) if data.get("breathing") else None,
            signal=int(data.get("signal", 0) or 0) if data.get("signal") else None,
            sos_type=data.get("sosType"),
            bed_status=data.get("bedStatus"),
            sleep_status=data.get("sleepStatus"),
            snore=int(data.get("snore", 0) or 0) if data.get("snore") else None,
            raw_timestamp=data.get("createTime"),
            received_at=datetime.utcnow()
        )
