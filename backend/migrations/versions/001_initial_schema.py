"""
Initial database schema for StateFlow.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-15 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', 'pending_verification', name='userstatus'),
                  default='pending_verification', nullable=False),
        sa.Column('is_superuser', sa.Boolean, default=False, nullable=False),
        sa.Column('email_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_system', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Permissions table
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('resource', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Role-Permission association table
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('jti', sa.String(36), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('revoked', sa.Boolean, default=False, nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
    )
    op.create_index('ix_refresh_tokens_user_expires', 'refresh_tokens', ['user_id', 'expires_at'])

    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', 'deleted', name='organizationstatus'),
                  default='active', nullable=False),
        sa.Column('settings', postgresql.JSONB, default={}, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Organization members table
    op.create_table(
        'organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('role_name', sa.Enum('owner', 'administrator', 'developer', 'viewer', name='memberrole'),
                  nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_user'),
    )
    op.create_index('ix_org_members_org_active', 'organization_members', ['organization_id', 'is_active'])

    # Retry policies table
    op.create_table(
        'retry_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('max_attempts', sa.Integer, default=3, nullable=False),
        sa.Column('base_delay_seconds', sa.Float, default=1.0, nullable=False),
        sa.Column('max_delay_seconds', sa.Float, default=60.0, nullable=False),
        sa.Column('exponential_base', sa.Float, default=2.0, nullable=False),
        sa.Column('retryable_errors', postgresql.JSONB, default=[], nullable=False),
        sa.Column('non_retryable_errors', postgresql.JSONB, default=[], nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Workflows table
    op.create_table(
        'workflows',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('draft', 'active', 'deprecated', 'archived', name='workflowstatus'),
                  default='draft', nullable=False),
        sa.Column('current_version', sa.Integer, default=1, nullable=False),
        sa.Column('tags', postgresql.JSONB, default=[], nullable=False),
        sa.Column('metadata', postgresql.JSONB, default={}, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('organization_id', 'name', name='uq_org_workflow_name'),
    )
    op.create_index('ix_workflows_org_status', 'workflows', ['organization_id', 'status'])

    # Workflow versions table
    op.create_table(
        'workflow_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('definition', postgresql.JSONB, nullable=False),
        sa.Column('steps', postgresql.JSONB, nullable=False),
        sa.Column('connections', postgresql.JSONB, default=[], nullable=False),
        sa.Column('variables', postgresql.JSONB, default={}, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('changelog', sa.Text, nullable=True),
        sa.UniqueConstraint('workflow_id', 'version_number', name='uq_workflow_version'),
    )
    op.create_index('ix_workflow_versions_workflow_created', 'workflow_versions', ['workflow_id', 'created_at'])

    # Workflow steps table
    op.create_table(
        'workflow_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('version_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_versions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('step_key', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('step_type', sa.Enum('action', 'condition', 'parallel', 'delay', 'compensation', name='steptype'),
                  default='action', nullable=False),
        sa.Column('order', sa.Integer, default=0, nullable=False),
        sa.Column('handler', sa.String(200), nullable=False),
        sa.Column('config', postgresql.JSONB, default={}, nullable=False),
        sa.Column('input_mapping', postgresql.JSONB, default={}, nullable=False),
        sa.Column('output_mapping', postgresql.JSONB, default={}, nullable=False),
        sa.Column('timeout_seconds', sa.Integer, default=300, nullable=False),
        sa.Column('retry_policy_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('retry_policies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('compensation_handler', sa.String(200), nullable=True),
        sa.Column('compensation_config', postgresql.JSONB, default={}, nullable=False),
        sa.Column('depends_on', postgresql.JSONB, default=[], nullable=False),
        sa.Column('is_critical', sa.Boolean, default=True, nullable=False),
        sa.Column('continue_on_failure', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('version_id', 'step_key', name='uq_version_step_key'),
    )
    op.create_index('ix_workflow_steps_version_order', 'workflow_steps', ['version_id', 'order'])

    # Workflow executions table
    op.create_table(
        'workflow_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflows.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('version_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_versions.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'compensating',
                  'compensated', 'partially_compensated', 'cancelled', 'timed_out', name='executionstatus'),
                  default='pending', nullable=False, index=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('context', postgresql.JSONB, default={}, nullable=False),
        sa.Column('input_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('output_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('error_details', postgresql.JSONB, default={}, nullable=False),
        sa.Column('current_step', sa.String(100), nullable=True),
        sa.Column('completed_steps', postgresql.JSONB, default=[], nullable=False),
        sa.Column('failed_step', sa.String(100), nullable=True),
        sa.Column('retry_count', sa.Integer, default=0, nullable=False),
        sa.Column('compensation_retry_count', sa.Integer, default=0, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('correlation_id', sa.String(36), nullable=True, index=True),
    )
    op.create_index('ix_executions_org_status_created', 'workflow_executions', ['organization_id', 'status', 'created_at'])
    op.create_index('ix_executions_workflow_status', 'workflow_executions', ['workflow_id', 'status'])

    # Step executions table
    op.create_table(
        'step_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('step_def_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_steps.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('step_key', sa.String(100), nullable=False),
        sa.Column('status', sa.Enum('pending', 'waiting', 'running', 'completed', 'failed', 'skipped',
                  'compensating', 'compensated', 'compensation_failed', 'retrying', 'cancelled', name='stepstatus'),
                  default='pending', nullable=False, index=True),
        sa.Column('input_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('output_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('error_details', postgresql.JSONB, default={}, nullable=False),
        sa.Column('attempt', sa.Integer, default=1, nullable=False),
        sa.Column('max_attempts', sa.Integer, default=3, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('worker_id', sa.String(100), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True, index=True),
    )
    op.create_index('ix_step_executions_execution_status', 'step_executions', ['execution_id', 'status'])
    op.create_index('ix_step_executions_step_def', 'step_executions', ['step_def_id'])
    op.create_index('ix_step_executions_retry', 'step_executions', ['next_retry_at', 'status'])

    # Compensation executions table
    op.create_table(
        'compensation_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('step_execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('step_executions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('step_key', sa.String(100), nullable=False),
        sa.Column('compensation_handler', sa.String(200), nullable=False),
        sa.Column('compensation_config', postgresql.JSONB, default={}, nullable=False),
        sa.Column('status', sa.Enum('pending', 'waiting', 'running', 'completed', 'failed', 'skipped',
                  'compensating', 'compensated', 'compensation_failed', 'retrying', 'cancelled', name='stepstatus'),
                  default='pending', nullable=False, index=True),
        sa.Column('input_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('output_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('error_details', postgresql.JSONB, default={}, nullable=False),
        sa.Column('attempt', sa.Integer, default=1, nullable=False),
        sa.Column('max_attempts', sa.Integer, default=3, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('worker_id', sa.String(100), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True, index=True),
        sa.Column('original_failure', sa.Text, nullable=True),
    )
    op.create_index('ix_compensation_executions_execution_status', 'compensation_executions', ['execution_id', 'status'])
    op.create_index('ix_compensation_executions_retry', 'compensation_executions', ['next_retry_at', 'status'])

    # Execution events table
    op.create_table(
        'execution_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('step_execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('step_executions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('compensation_execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('compensation_executions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('event_type', sa.Enum(
            'workflow_created', 'workflow_activated', 'workflow_deactivated', 'workflow_deprecated',
            'execution_started', 'execution_completed', 'execution_failed', 'execution_cancelled', 'execution_timed_out',
            'step_started', 'step_completed', 'step_failed', 'step_skipped', 'step_retrying', 'step_retry_exhausted',
            'compensation_started', 'compensation_completed', 'compensation_failed', 'compensation_retrying', 'compensation_retry_exhausted',
            'retry_scheduled', 'retry_executed',
            name='eventtype'), nullable=False, index=True),
        sa.Column('event_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('severity', sa.String(20), default='info', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
        sa.Column('correlation_id', sa.String(36), nullable=True, index=True),
    )
    op.create_index('ix_execution_events_execution_created', 'execution_events', ['execution_id', 'created_at'])
    op.create_index('ix_execution_events_type_created', 'execution_events', ['event_type', 'created_at'])

    # Outbox events table
    op.create_table(
        'outbox_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('aggregate_type', sa.String(100), nullable=False, index=True),
        sa.Column('aggregate_id', sa.String(36), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('headers', postgresql.JSONB, default={}, nullable=False),
        sa.Column('retry_count', sa.Integer, default=0, nullable=False),
        sa.Column('max_retries', sa.Integer, default=5, nullable=False),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('published', sa.Boolean, default=False, nullable=False, index=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True, index=True),
    )
    op.create_index('ix_outbox_unpublished', 'outbox_events', ['published', 'next_retry_at'])
    op.create_index('ix_outbox_aggregate', 'outbox_events', ['aggregate_type', 'aggregate_id'])

    # Idempotency records table
    op.create_table(
        'idempotency_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('idempotency_key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scope', sa.String(100), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('response_data', postgresql.JSONB, default={}, nullable=False),
        sa.Column('status_code', sa.Integer, default=200, nullable=False),
        sa.Column('completed', sa.Boolean, default=False, nullable=False),
        sa.Column('locked', sa.Boolean, default=False, nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.UniqueConstraint('scope', 'idempotency_key', name='uq_idempotency_scope_key'),
    )
    op.create_index('ix_idempotency_expires', 'idempotency_records', ['expires_at'])

    # Worker heartbeats table
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('worker_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('worker_type', sa.String(50), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('pid', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), default='healthy', nullable=False),
        sa.Column('capabilities', postgresql.JSONB, default=[], nullable=False),
        sa.Column('current_executions', sa.Integer, default=0, nullable=False),
        sa.Column('max_concurrency', sa.Integer, default=4, nullable=False),
        sa.Column('metadata', postgresql.JSONB, default={}, nullable=False),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_worker_heartbeat_status', 'worker_heartbeats', ['status', 'last_heartbeat_at'])

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=True, index=True),
        sa.Column('resource_id', sa.String(36), nullable=True, index=True),
        sa.Column('details', postgresql.JSONB, default={}, nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('correlation_id', sa.String(36), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
    )
    op.create_index('ix_audit_logs_org_created', 'audit_logs', ['organization_id', 'created_at'])
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('worker_heartbeats')
    op.drop_table('idempotency_records')
    op.drop_table('outbox_events')
    op.drop_table('execution_events')
    op.drop_table('compensation_executions')
    op.drop_table('step_executions')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_steps')
    op.drop_table('workflow_versions')
    op.drop_table('workflows')
    op.drop_table('retry_policies')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('refresh_tokens')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('users')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS userstatus")
    op.execute("DROP TYPE IF EXISTS organizationstatus")
    op.execute("DROP TYPE IF EXISTS memberrole")
    op.execute("DROP TYPE IF EXISTS workflowstatus")
    op.execute("DROP TYPE IF EXISTS steptype")
    op.execute("DROP TYPE IF EXISTS executionstatus")
    op.execute("DROP TYPE IF EXISTS stepstatus")
    op.execute("DROP TYPE IF EXISTS eventtype")