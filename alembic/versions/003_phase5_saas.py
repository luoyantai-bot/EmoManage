# ===========================================
# Alembic Migration: Phase 5 Tables
# ===========================================
"""Add intervention rules, logs, activities, and push records

Revision ID: 003_phase5_saas
Revises: 002_add_alert_raw_data
Create Date: 2025-03-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '003_phase5_saas'
down_revision = '002_add_alert_raw_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 5 tables"""
    
    # ===========================================
    # 1. Intervention Rules Table
    # ===========================================
    op.create_table(
        'intervention_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='10'),
        sa.Column('condition_config', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('action_config', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('ix_intervention_rules_tenant_id', 'intervention_rules', ['tenant_id'])
    op.create_index('ix_intervention_rules_is_active', 'intervention_rules', ['is_active'])
    
    # ===========================================
    # 2. Intervention Logs Table
    # ===========================================
    op.create_table(
        'intervention_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_id', UUID(as_uuid=True), sa.ForeignKey('intervention_rules.id', ondelete='SET NULL')),
        sa.Column('measurement_id', UUID(as_uuid=True), sa.ForeignKey('measurement_records.id', ondelete='SET NULL')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_code', sa.String(50), nullable=False),
        sa.Column('trigger_metrics', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('actions_executed', sa.JSON),
        sa.Column('status', sa.String(20), nullable=False, server_default='triggered'),
        sa.Column('webhook_response', sa.JSON),
        sa.Column('error_message', sa.String(500)),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('ix_intervention_logs_tenant_id', 'intervention_logs', ['tenant_id'])
    op.create_index('ix_intervention_logs_rule_id', 'intervention_logs', ['rule_id'])
    op.create_index('ix_intervention_logs_measurement_id', 'intervention_logs', ['measurement_id'])
    op.create_index('ix_intervention_logs_user_id', 'intervention_logs', ['user_id'])
    op.create_index('ix_intervention_logs_device_code', 'intervention_logs', ['device_code'])
    op.create_index('ix_intervention_logs_status', 'intervention_logs', ['status'])
    op.create_index('ix_intervention_logs_created_at', 'intervention_logs', ['created_at'])
    
    # ===========================================
    # 3. Activities Table
    # ===========================================
    op.create_table(
        'activities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('activity_type', sa.String(50), nullable=False, server_default='other'),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('end_time', sa.DateTime, nullable=False),
        sa.Column('location', sa.String(200)),
        sa.Column('max_participants', sa.Integer),
        sa.Column('current_participants', sa.Integer, nullable=False, server_default='0'),
        sa.Column('target_tags', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('ix_activities_tenant_id', 'activities', ['tenant_id'])
    op.create_index('ix_activities_activity_type', 'activities', ['activity_type'])
    op.create_index('ix_activities_start_time', 'activities', ['start_time'])
    op.create_index('ix_activities_status', 'activities', ['status'])
    
    # ===========================================
    # 4. Activity Push Records Table
    # ===========================================
    op.create_table(
        'activity_push_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('push_reason', sa.String(200), nullable=False),
        sa.Column('matched_tags', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('push_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('read_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('ix_activity_push_records_activity_id', 'activity_push_records', ['activity_id'])
    op.create_index('ix_activity_push_records_user_id', 'activity_push_records', ['user_id'])
    op.create_index('ix_activity_push_records_push_status', 'activity_push_records', ['push_status'])
    op.create_index('ix_activity_push_records_created_at', 'activity_push_records', ['created_at'])


def downgrade() -> None:
    """Remove Phase 5 tables"""
    
    # Drop tables in reverse order
    op.drop_index('ix_activity_push_records_created_at', 'activity_push_records')
    op.drop_index('ix_activity_push_records_push_status', 'activity_push_records')
    op.drop_index('ix_activity_push_records_user_id', 'activity_push_records')
    op.drop_index('ix_activity_push_records_activity_id', 'activity_push_records')
    op.drop_table('activity_push_records')
    
    op.drop_index('ix_activities_status', 'activities')
    op.drop_index('ix_activities_start_time', 'activities')
    op.drop_index('ix_activities_activity_type', 'activities')
    op.drop_index('ix_activities_tenant_id', 'activities')
    op.drop_table('activities')
    
    op.drop_index('ix_intervention_logs_created_at', 'intervention_logs')
    op.drop_index('ix_intervention_logs_status', 'intervention_logs')
    op.drop_index('ix_intervention_logs_device_code', 'intervention_logs')
    op.drop_index('ix_intervention_logs_user_id', 'intervention_logs')
    op.drop_index('ix_intervention_logs_measurement_id', 'intervention_logs')
    op.drop_index('ix_intervention_logs_rule_id', 'intervention_logs')
    op.drop_index('ix_intervention_logs_tenant_id', 'intervention_logs')
    op.drop_table('intervention_logs')
    
    op.drop_index('ix_intervention_rules_is_active', 'intervention_rules')
    op.drop_index('ix_intervention_rules_tenant_id', 'intervention_rules')
    op.drop_table('intervention_rules')
