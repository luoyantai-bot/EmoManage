# ===========================================
# User Model
# ===========================================
"""
User model definition.

Users are end-users under a tenant who use smart cushions
for health monitoring. The system records their physiological
data and health reports.
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
    from app.models.alert import AlertRecord
    from app.models.activity_push_record import ActivityPushRecord


# Valid genders
GENDERS = ["male", "female", "other"]
GENDER_LABELS = {
    "male": "Male",
    "female": "Female",
    "other": "Other",
}


class User(Base, TimestampMixin):
    """
    User table.
    
    Attributes:
        id: UUID primary key, auto-generated
        tenant_id: Tenant ID (foreign key)
        name: User name
        gender: Gender (male/female/other)
        age: Age
        height: Height (cm)
        weight: Weight (kg)
        bmi: Body Mass Index (auto-calculated)
        phone: Contact phone
        created_at: Creation time
        updated_at: Update time
    """
    __tablename__ = "users"
    __table_args__ = {"comment": "User table"}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="User ID"
    )

    # Foreign key
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="User name"
    )
    
    gender: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="other",
        comment="Gender: male/female/other"
    )
    
    age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Age"
    )
    
    height: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Height (cm)"
    )
    
    weight: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Weight (kg)"
    )
    
    bmi: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="BMI (auto-calculated)"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Contact phone"
    )

    # Relationships
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
    
    alerts: Mapped[List["AlertRecord"]] = relationship(
        "AlertRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    activity_push_records: Mapped[List["ActivityPushRecord"]] = relationship(
        "ActivityPushRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', tenant_id={self.tenant_id})>"

    def calculate_bmi(self) -> Optional[float]:
        """
        Calculate BMI.
        
        BMI = weight(kg) / (height(m))^2
        
        Returns:
            BMI value, or None if height or weight is missing
        """
        if self.height and self.weight and self.height > 0:
            height_in_meters = self.height / 100  # cm to m
            return round(self.weight / (height_in_meters ** 2), 2)
        return None


@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def auto_calculate_bmi(mapper, connection, target):
    """
    Auto-calculate BMI before saving.
    Updates BMI when height or weight changes.
    """
    target.bmi = target.calculate_bmi()


@event.listens_for(User.gender, 'set')
def validate_gender(target, value, oldvalue, initiator):
    """Validate gender."""
    if value not in GENDERS:
        raise ValueError(f"Invalid gender: {value}, valid values: {GENDERS}")
    return value
