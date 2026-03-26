# ===========================================
# Tenant/Merchant Model
# ===========================================
"""
Tenant model definition.

Tenant is the core concept of the SaaS system. Each tenant represents
a merchant/institution using the system. Supports multiple merchant types:
traditional Chinese medicine clinics, hotels, wellness centers, etc.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.device import Device
    from app.models.alert import AlertRecord
    from app.models.intervention_rule import InterventionRule
    from app.models.intervention_log import InterventionLog
    from app.models.activity import Activity


# Valid tenant types
TENANT_TYPES = ["chinese_medicine", "hotel", "wellness_center"]
TENANT_TYPE_LABELS = {
    "chinese_medicine": "Traditional Chinese Medicine Clinic",
    "hotel": "Hotel",
    "wellness_center": "Wellness Center",
}


class Tenant(Base, TimestampMixin):
    """
    Tenant/Merchant table.
    
    Attributes:
        id: UUID primary key, auto-generated
        name: Merchant name, required
        type: Merchant type (chinese_medicine/hotel/wellness_center)
        contact_phone: Contact phone number
        address: Merchant address
        created_at: Creation time
        updated_at: Update time
    """
    __tablename__ = "tenants"
    __table_args__ = {"comment": "Tenant/Merchant table"}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Tenant ID"
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Merchant name"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="wellness_center",
        comment="Merchant type: chinese_medicine/hotel/wellness_center"
    )
    
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Contact phone"
    )
    
    address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Merchant address"
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    devices: Mapped[List["Device"]] = relationship(
        "Device",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    alerts: Mapped[List["AlertRecord"]] = relationship(
        "AlertRecord",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    intervention_rules: Mapped[List["InterventionRule"]] = relationship(
        "InterventionRule",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    intervention_logs: Mapped[List["InterventionLog"]] = relationship(
        "InterventionLog",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    activities: Mapped[List["Activity"]] = relationship(
        "Activity",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', type='{self.type}')>"


@event.listens_for(Tenant.type, 'set')
def validate_tenant_type(target, value, oldvalue, initiator):
    """Validate tenant type."""
    if value not in TENANT_TYPES:
        raise ValueError(f"Invalid tenant type: {value}, valid values: {TENANT_TYPES}")
    return value
