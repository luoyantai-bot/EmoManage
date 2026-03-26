# ===========================================
# SQLAlchemy ORM Models Package
# ===========================================
"""
Database model definitions.

Contains:
- Tenant: Tenant/merchant table
- User: User table
- Device: Device table
- MeasurementRecord: Measurement record table
- AlertRecord: Alert record table
- RawDeviceData: Raw device data table
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, Float, Integer, Text, JSON, ForeignKey, func, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    """SQLAlchemy base class"""
    pass


class TimestampMixin:
    """
    Timestamp mixin class.
    Provides created_at and updated_at fields for all models.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="Creation time"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Update time"
    )


# Import all models
from app.models.tenant import Tenant
from app.models.user import User
from app.models.device import Device
from app.models.measurement import MeasurementRecord
from app.models.alert import AlertRecord
from app.models.raw_data import RawDeviceData

__all__ = [
    "Base",
    "TimestampMixin",
    "Tenant",
    "User",
    "Device",
    "MeasurementRecord",
    "AlertRecord",
    "RawDeviceData",
]
