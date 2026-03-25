# Initial Migration - Create All Tables

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables"""
    
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(50), nullable=False, 
                  server_default='wellness_center'),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('gender', sa.String(10), nullable=False, 
                  server_default='other'),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('bmi', sa.Float(), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_code', sa.String(50), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, 
                  server_default='offline'),
        sa.Column('device_type', sa.String(100), nullable=True),
        sa.Column('ble_mac', sa.String(20), nullable=True),
        sa.Column('wifi_mac', sa.String(20), nullable=True),
        sa.Column('firmware_version', sa.String(20), nullable=True),
        sa.Column('hardware_version', sa.String(20), nullable=True),
        sa.Column('cloud_device_id', sa.Integer(), nullable=True),
        sa.Column('last_online_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_code'),
    )
    
    op.create_index('ix_devices_device_code', 'devices', ['device_code'])
    op.create_index('ix_devices_tenant_id', 'devices', ['tenant_id'])
    op.create_index('ix_devices_status', 'devices', ['status'])
    
    # Create measurement_records table
    op.create_table(
        'measurement_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, 
                  server_default='measuring'),
        sa.Column('raw_data_summary', postgresql.JSON(astext_type=sa.Text()), 
                  nullable=True),
        sa.Column('derived_metrics', postgresql.JSON(astext_type=sa.Text()), 
                  nullable=True),
        sa.Column('ai_analysis', sa.Text(), nullable=True),
        sa.Column('health_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), 
                  nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('ix_measurement_records_user_id', 'measurement_records', ['user_id'])
    op.create_index('ix_measurement_records_device_id', 'measurement_records', ['device_id'])
    op.create_index('ix_measurement_records_start_time', 'measurement_records', ['start_time'])
    op.create_index('ix_measurement_records_status', 'measurement_records', ['status'])


def downgrade() -> None:
    """Drop all tables"""
    
    op.drop_index('ix_measurement_records_status', 'measurement_records')
    op.drop_index('ix_measurement_records_start_time', 'measurement_records')
    op.drop_index('ix_measurement_records_device_id', 'measurement_records')
    op.drop_index('ix_measurement_records_user_id', 'measurement_records')
    op.drop_table('measurement_records')
    
    op.drop_index('ix_devices_status', 'devices')
    op.drop_index('ix_devices_tenant_id', 'devices')
    op.drop_index('ix_devices_device_code', 'devices')
    op.drop_table('devices')
    
    op.drop_index('ix_users_tenant_id', 'users')
    op.drop_table('users')
    
    op.drop_table('tenants')
