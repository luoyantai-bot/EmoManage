# Add Alert and RawData Tables

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_alert_raw_data'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add alert_records and raw_device_data tables"""
    
    # Create alert_records table
    op.create_table(
        'alert_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_type', sa.String(20), nullable=False),
        sa.Column('alert_code', sa.String(10), nullable=False),
        sa.Column('message', sa.String(500), nullable=False),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create alert_records indexes
    op.create_index('ix_alert_records_device_id', 'alert_records', ['device_id'])
    op.create_index('ix_alert_records_user_id', 'alert_records', ['user_id'])
    op.create_index('ix_alert_records_tenant_id', 'alert_records', ['tenant_id'])
    op.create_index('ix_alert_records_alert_type', 'alert_records', ['alert_type'])
    op.create_index('ix_alert_records_status', 'alert_records', ['status'])
    
    # Create raw_device_data table
    op.create_table(
        'raw_device_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_code', sa.String(50), nullable=False),
        sa.Column('heart_rate', sa.Integer(), nullable=True),
        sa.Column('breathing', sa.Integer(), nullable=True),
        sa.Column('signal', sa.Integer(), nullable=True),
        sa.Column('sos_type', sa.String(10), nullable=True),
        sa.Column('bed_status', sa.String(10), nullable=True),
        sa.Column('sleep_status', sa.String(10), nullable=True),
        sa.Column('snore', sa.Integer(), nullable=True),
        sa.Column('raw_timestamp', sa.String(20), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create raw_device_data indexes
    op.create_index('ix_raw_device_data_device_code', 'raw_device_data', ['device_code'])
    op.create_index('ix_raw_device_data_received_at', 'raw_device_data', ['received_at'])
    op.create_index(
        'ix_raw_device_data_device_code_received_at',
        'raw_device_data',
        ['device_code', 'received_at']
    )


def downgrade() -> None:
    """Remove alert_records and raw_device_data tables"""
    
    # Drop raw_device_data table
    op.drop_index('ix_raw_device_data_device_code_received_at', 'raw_device_data')
    op.drop_index('ix_raw_device_data_received_at', 'raw_device_data')
    op.drop_index('ix_raw_device_data_device_code', 'raw_device_data')
    op.drop_table('raw_device_data')
    
    # Drop alert_records table
    op.drop_index('ix_alert_records_status', 'alert_records')
    op.drop_index('ix_alert_records_alert_type', 'alert_records')
    op.drop_index('ix_alert_records_tenant_id', 'alert_records')
    op.drop_index('ix_alert_records_user_id', 'alert_records')
    op.drop_index('ix_alert_records_device_id', 'alert_records')
    op.drop_table('alert_records')
