# ===========================================
# Device Model
# ===========================================
"""
Device model definition.

Device is the mapping of smart cushion hardware in the system,
storing basic device information and status.
Device is linked to the manufacturer's cloud platform via device_code (SN number).
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
    from app.models.alert import AlertRecord


# Device statuses
DEVICE_STATUSES = ["online", "offline", "in_use"]
DEVICE_STATUS_LABELS = {
    "online": "Online",
    "offline": "Offline",
    "in_use": "In Use",
}


class Device(Base, TimestampMixin):
    """
    Device table.
    
    Attributes:
        id: UUID primary key, auto-generated
        device_code: Device code (SN), unique, e.g. "TA0096400014"
        tenant_id: Tenant ID (foreign key)
        status: Device status (online/offline/in_use)
        device_type: Device model
        ble_mac: Bluetooth MAC address
        wifi_mac: WiFi MAC address
        firmware_version: Firmware version
        hardware_version: Hardware version
        cloud_device_id: Manufacturer cloud platform device ID
        last_online_at: Last online time
        created_at: Creation time
        updated_at: Update time
    """
    __tablename__ = "devices"
    __table_args__ = {"comment": "Device table"}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Device ID"
    )

    # Device code (SN from manufacturer)
    device_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Device code (SN), e.g. TA0096400014"
    )

    # Foreign key
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )

    # Device status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="offline",
        index=True,
        comment="Device status: online/offline/in_use"
    )
    
    # Device info
    device_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Device model"
    )
    
    ble_mac: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Bluetooth MAC address"
    )
    
    wifi_mac: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="WiFi MAC address"
    )
    
    firmware_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Firmware version"
    )
    
    hardware_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Hardware version"
    )
    
    # Manufacturer cloud platform link
    cloud_device_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Manufacturer cloud device ID"
    )
    
    # Status tracking
    last_online_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last online time"
    )

    # Relationships
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
    
    alerts: Mapped[List["AlertRecord"]] = relationship(
        "AlertRecord",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, device_code='{self.device_code}', status='{self.status}')>"


@event.listens_for(Device.status, 'set')
def validate_device_status(target, value, oldvalue, initiator):
    """Validate device status."""
    if value not in DEVICE_STATUSES:
        raise ValueError(f"Invalid device status: {value}, valid values: {DEVICE_STATUSES}")
    return value
