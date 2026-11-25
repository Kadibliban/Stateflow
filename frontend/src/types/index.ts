/**
 * StateFlow Frontend Types
 * Matches the backend API schemas
 */

// Base types
export type UUID = string;
export type ISODateString = string;

// Enums
export enum WorkflowStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  DEPRECATED = 'deprecated',
  ARCHIVED = 'archived',
}

export enum StepType {
  ACTION = 'action',
  CONDITION = 'condition',
  PARALLEL = 'parallel',
  DELAY = 'delay',
  COMPENSATION = 'compensation',
}

export enum ExecutionStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  COMPENSATING = 'compensating',
  COMPENSATED = 'compensated',
  PARTIALLY_COMPENSATED = 'partially_compensated',
  CANCELLED = 'cancelled',
  TIMED_OUT = 'timed_out',
}

export enum StepStatus {
  PENDING = 'pending',
  WAITING = 'waiting',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
  COMPENSATING = 'compensating',
  COMPENSATED = 'compensated',
  COMPENSATION_FAILED = 'compensation_failed',
  RETRYING = 'retrying',
  CANCELLED = 'cancelled',
}

export enum MemberRole {
  OWNER = 'owner',
  ADMINISTRATOR = 'administrator',
  DEVELOPER = 'developer',
  VIEWER = 'viewer',
}

export enum OrganizationStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  SUSPENDED = 'suspended',
}

// Organization
export interface Organization {
  id: UUID;
  name: string;
  slug: string;
  description: string | null;
  status: OrganizationStatus;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface OrganizationMember {
  id: UUID;
  organization_id: UUID;
  user_id: UUID;
  role_id: UUID;
  role_name: MemberRole;
  is_active: boolean;
  joined_at: ISODateString;
  user?: User;
  role?: Role;
}

// User
export interface User {
  id: UUID;
  email: string;
  username: string;
  full_name: string | null;
  status: string;
  email_verified: boolean;
  is_superuser: boolean;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface Role {
  id: UUID;
  name: string;
  display_name: string;
  description: string | null;
  is_system: boolean;
}

export interface Permission {
  id: UUID;
  name: string;
  display_name: string;
  description: string | null;
}

// Workflow
export interface Workflow {
  id: UUID;
  organization_id: UUID;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  current_version: number;
  tags: string[];
  workflow_metadata: Record<string, any>;
  created_by: UUID;
  created_at: ISODateString;
  updated_at: ISODateString;
  activated_at: ISODateString | null;
  deprecated_at: ISODateString | null;
  organization?: Organization;
  versions?: WorkflowVersion[];
}

export interface WorkflowVersion {
  id: UUID;
  workflow_id: UUID;
  version_number: number;
  definition: Record<string, any>;
  steps: WorkflowStepDefinition[];
  connections: WorkflowConnection[];
  variables: Record<string, any>;
  created_by: UUID;
  created_at: ISODateString;
  changelog: string | null;
  steps_def?: WorkflowStep[];
}

export interface WorkflowStepDefinition {
  step_key: string;
  name: string;
  description: string | null;
  step_type: StepType;
  order: number;
  handler: string;
  config: Record<string, any>;
  input_mapping: Record<string, any>;
  output_mapping: Record<string, any>;
  timeout_seconds: number;
  retry_policy_id: UUID | null;
  compensation_handler: string | null;
  compensation_config: Record<string, any>;
  depends_on: string[];
  is_critical: boolean;
  continue_on_failure: boolean;
}

export interface WorkflowConnection {
  source: string;
  target: string;
  source_handle?: string;
  target_handle?: string;
}

export interface WorkflowStep {
  id: UUID;
  version_id: UUID;
  step_key: string;
  name: string;
  description: string | null;
  step_type: StepType;
  order: number;
  handler: string;
  config: Record<string, any>;
  input_mapping: Record<string, any>;
  output_mapping: Record<string, any>;
  timeout_seconds: number;
  retry_policy_id: UUID | null;
  compensation_handler: string | null;
  compensation_config: Record<string, any>;
  depends_on: string[];
  is_critical: boolean;
  continue_on_failure: boolean;
  created_at: ISODateString;
  updated_at: ISODateString;
  retry_policy?: RetryPolicy;
}

export interface RetryPolicy {
  id: UUID;
  name: string;
  max_attempts: number;
  base_delay_seconds: number;
  max_delay_seconds: number;
  exponential_base: number;
  retryable_errors: string[];
  non_retryable_errors: string[];
  created_at: ISODateString;
}

// Execution
export interface WorkflowExecution {
  id: UUID;
  workflow_id: UUID;
  version_id: UUID;
  organization_id: UUID;
  status: ExecutionStatus;
  idempotency_key: string | null;
  context: Record<string, any>;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error: string | null;
  error_details: Record<string, any>;
  current_step: string | null;
  completed_steps: string[];
  failed_step: string | null;
  retry_count: number;
  compensation_retry_count: number;
  started_at: ISODateString | null;
  completed_at: ISODateString | null;
  created_at: ISODateString;
  updated_at: ISODateString;
  triggered_by: UUID | null;
  correlation_id: string | null;
  workflow?: Workflow;
  version?: WorkflowVersion;
  step_executions?: StepExecution[];
  compensation_executions?: CompensationExecution[];
  events?: ExecutionEvent[];
}

export interface StepExecution {
  id: UUID;
  execution_id: UUID;
  step_def_id: UUID;
  step_key: string;
  status: StepStatus;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error: string | null;
  error_details: Record<string, any>;
  attempt: number;
  max_attempts: number;
  started_at: ISODateString | null;
  completed_at: ISODateString | null;
  next_retry_at: ISODateString | null;
  duration_ms: number | null;
  worker_id: string | null;
  idempotency_key: string | null;
  step_def?: WorkflowStep;
  compensation?: CompensationExecution;
}

export interface CompensationExecution {
  id: UUID;
  execution_id: UUID;
  step_execution_id: UUID;
  step_key: string;
  compensation_handler: string;
  compensation_config: Record<string, any>;
  status: StepStatus;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error: string | null;
  error_details: Record<string, any>;
  attempt: number;
  max_attempts: number;
  started_at: ISODateString | null;
  completed_at: ISODateString | null;
  next_retry_at: ISODateString | null;
  duration_ms: number | null;
  worker_id: string | null;
  idempotency_key: string | null;
  original_failure: string | null;
}

export interface ExecutionEvent {
  id: UUID;
  execution_id: UUID;
  step_execution_id: UUID | null;
  compensation_execution_id: UUID | null;
  event_type: string;
  event_data: Record<string, any>;
  message: string | null;
  severity: string;
  created_at: ISODateString;
  correlation_id: string | null;
}

// API Response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface ExecutionDetailResponse {
  execution: WorkflowExecution;
  steps: StepExecution[];
  compensations: CompensationExecution[];
  events?: ExecutionEvent[];
}

// Request types
export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  tags?: string[];
  workflow_metadata?: Record<string, any>;
}

export interface UpdateWorkflowRequest {
  name?: string;
  description?: string;
  tags?: string[];
  workflow_metadata?: Record<string, any>;
}

export interface CreateWorkflowVersionRequest {
  definition: Record<string, any>;
  steps: WorkflowStepDefinition[];
  connections: WorkflowConnection[];
  variables?: Record<string, any>;
  changelog?: string;
}

export interface CreateWorkflowStepRequest {
  step_key: string;
  name: string;
  description?: string;
  step_type: StepType;
  order: number;
  handler: string;
  config?: Record<string, any>;
  input_mapping?: Record<string, any>;
  output_mapping?: Record<string, any>;
  timeout_seconds?: number;
  retry_policy_id?: UUID;
  compensation_handler?: string;
  compensation_config?: Record<string, any>;
  depends_on?: string[];
  is_critical?: boolean;
  continue_on_failure?: boolean;
}

export interface StartExecutionRequest {
  input_data: Record<string, any>;
  idempotency_key?: string;
}

export interface CreateRetryPolicyRequest {
  name: string;
  max_attempts?: number;
  base_delay_seconds?: number;
  max_delay_seconds?: number;
  exponential_base?: number;
  retryable_errors?: string[];
  non_retryable_errors?: string[];
}

export interface CreateOrganizationRequest {
  name: string;
  slug: string;
  description?: string;
}

export interface InviteMemberRequest {
  email: string;
  role_name: MemberRole;
}

// Health
export interface HealthCheck {
  status: string;
  service: string;
  version: string;
  database: string;
}

export interface ReadyCheck {
  status: string;
  database: string;
}

// Worker
export interface WorkerHeartbeat {
  id: UUID;
  worker_id: string;
  status: string;
  last_heartbeat: ISODateString;
  metadata: Record<string, any>;
}

export interface WorkerInfo {
  worker_id: string;
  status: string;
  active_tasks: number;
  processed_tasks: number;
  failed_tasks: number;
  last_heartbeat: ISODateString;
  queues: string[];
}