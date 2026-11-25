/**
 * StateFlow API Service Layer
 * Centralized Axios instance with interceptors for auth and error handling
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import {
  Workflow,
  WorkflowVersion,
  WorkflowStepDefinition,
  WorkflowConnection,
  WorkflowStep,
  RetryPolicy,
  WorkflowExecution,
  StepExecution,
  CompensationExecution,
  ExecutionEvent,
  PaginatedResponse,
  ExecutionDetailResponse,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  CreateWorkflowVersionRequest,
  CreateWorkflowStepRequest,
  StartExecutionRequest,
  CreateRetryPolicyRequest,
  CreateOrganizationRequest,
  InviteMemberRequest,
  Organization,
  OrganizationMember,
  User,
  HealthCheck,
  ReadyCheck,
  WorkerInfo,
  UUID,
} from '@/types';

// API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    this.setupInterceptors();
    this.loadTokensFromStorage();
  }

  private loadTokensFromStorage(): void {
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  private saveTokensToStorage(): void {
    if (typeof window !== 'undefined') {
      if (this.accessToken) {
        localStorage.setItem('access_token', this.accessToken);
      } else {
        localStorage.removeItem('access_token');
      }
      if (this.refreshToken) {
        localStorage.setItem('refresh_token', this.refreshToken);
      } else {
        localStorage.removeItem('refresh_token');
      }
    }
  }

  private setupInterceptors(): void {
    // Request interceptor - add auth header
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken && config.headers) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error: AxiosError) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // Handle 401 Unauthorized - try to refresh token
        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          originalRequest._retry = true;

          try {
            await this.refreshAccessToken();
            // Retry original request with new token
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${this.accessToken}`;
            }
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - logout user
            this.clearTokens();
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private async refreshAccessToken(): Promise<void> {
    if (!this.refreshToken) throw new Error('No refresh token available');

    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: this.refreshToken,
    });

    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token;
    this.saveTokensToStorage();
  }

  setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.saveTokensToStorage();
  }

  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    this.saveTokensToStorage();
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  // Generic request methods
  async get<T>(url: string, params?: Record<string, any>): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: { params?: Record<string, any> }): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: { params?: Record<string, any> }): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: { params?: Record<string, any> }): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: { params?: Record<string, any> }): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  // Health endpoints
  async healthCheck(): Promise<HealthCheck> {
    return this.get<HealthCheck>('/health');
  }

  async readyCheck(): Promise<ReadyCheck> {
    return this.get<ReadyCheck>('/health/ready');
  }

  // Organization endpoints
  async createOrganization(data: CreateOrganizationRequest): Promise<Organization> {
    return this.post<Organization>('/organizations', data);
  }

  async getOrganizations(): Promise<Organization[]> {
    return this.get<Organization[]>('/organizations');
  }

  async getOrganization(id: UUID): Promise<Organization> {
    return this.get<Organization>(`/organizations/${id}`);
  }

  async updateOrganization(id: UUID, data: Partial<CreateOrganizationRequest>): Promise<Organization> {
    return this.patch<Organization>(`/organizations/${id}`, data);
  }

  async deleteOrganization(id: UUID): Promise<void> {
    return this.delete<void>(`/organizations/${id}`);
  }

  async getOrganizationMembers(orgId: UUID): Promise<OrganizationMember[]> {
    return this.get<OrganizationMember[]>(`/organizations/${orgId}/members`);
  }

  async inviteMember(orgId: UUID, data: InviteMemberRequest): Promise<OrganizationMember> {
    return this.post<OrganizationMember>(`/organizations/${orgId}/members`, data);
  }

  async removeMember(orgId: UUID, memberId: UUID): Promise<void> {
    return this.delete<void>(`/organizations/${orgId}/members/${memberId}`);
  }

  async updateMemberRole(orgId: UUID, memberId: UUID, roleName: string): Promise<OrganizationMember> {
    return this.patch<OrganizationMember>(`/organizations/${orgId}/members/${memberId}`, { role_name: roleName });
  }

  // Workflow endpoints
  async createWorkflow(orgId: UUID, data: CreateWorkflowRequest): Promise<Workflow> {
    return this.post<Workflow>('/workflows', data, { params: { org_id: orgId } });
  }

  async getWorkflows(orgId: UUID, params?: { skip?: number; limit?: number; status?: string }): Promise<PaginatedResponse<Workflow>> {
    return this.get<PaginatedResponse<Workflow>>('/workflows', { ...params, org_id: orgId });
  }

  async getWorkflow(orgId: UUID, workflowId: UUID): Promise<Workflow> {
    return this.get<Workflow>(`/workflows/${workflowId}`, { params: { org_id: orgId } });
  }

  async updateWorkflow(orgId: UUID, workflowId: UUID, data: UpdateWorkflowRequest): Promise<Workflow> {
    return this.patch<Workflow>(`/workflows/${workflowId}`, data, { params: { org_id: orgId } });
  }

  async deleteWorkflow(orgId: UUID, workflowId: UUID): Promise<void> {
    return this.delete<void>(`/workflows/${workflowId}`, { params: { org_id: orgId } });
  }

  async cloneWorkflow(orgId: UUID, workflowId: UUID, name: string): Promise<Workflow> {
    return this.post<Workflow>(`/workflows/${workflowId}/clone`, { name }, { params: { org_id: orgId } });
  }

  async activateWorkflow(orgId: UUID, workflowId: UUID, versionNumber: number): Promise<Workflow> {
    return this.post<Workflow>(`/workflows/${workflowId}/activate`, { version: versionNumber }, { params: { org_id: orgId } });
  }

  async deprecateWorkflow(orgId: UUID, workflowId: UUID): Promise<Workflow> {
    return this.post<Workflow>(`/workflows/${workflowId}/deprecate`, {}, { params: { org_id: orgId } });
  }

  // Workflow Version endpoints
  async createWorkflowVersion(orgId: UUID, workflowId: UUID, data: CreateWorkflowVersionRequest): Promise<WorkflowVersion> {
    return this.post<WorkflowVersion>(`/workflows/${workflowId}/versions`, data, { params: { org_id: orgId } });
  }

  async getWorkflowVersions(orgId: UUID, workflowId: UUID): Promise<WorkflowVersion[]> {
    return this.get<WorkflowVersion[]>(`/workflows/${workflowId}/versions`, { params: { org_id: orgId } });
  }

  async getWorkflowVersion(orgId: UUID, workflowId: UUID, versionNumber: number): Promise<WorkflowVersion> {
    return this.get<WorkflowVersion>(`/workflows/${workflowId}/versions/${versionNumber}`, { params: { org_id: orgId } });
  }

  async exportWorkflowVersion(orgId: UUID, workflowId: UUID, versionNumber: number): Promise<Blob> {
    const response = await this.client.get(
      `/workflows/${workflowId}/versions/${versionNumber}/export`,
      { params: { org_id: orgId }, responseType: 'blob' }
    );
    return response.data;
  }

  // Workflow Step endpoints
  async createWorkflowStep(orgId: UUID, workflowId: UUID, versionNumber: number, data: CreateWorkflowStepRequest): Promise<WorkflowStep> {
    return this.post<WorkflowStep>(`/workflows/${workflowId}/versions/${versionNumber}/steps`, data, { params: { org_id: orgId } });
  }

  async getWorkflowSteps(orgId: UUID, workflowId: UUID, versionNumber: number): Promise<WorkflowStep[]> {
    return this.get<WorkflowStep[]>(`/workflows/${workflowId}/versions/${versionNumber}/steps`, { params: { org_id: orgId } });
  }

  async updateWorkflowStep(orgId: UUID, workflowId: UUID, versionNumber: number, stepKey: string, data: Partial<CreateWorkflowStepRequest>): Promise<WorkflowStep> {
    return this.patch<WorkflowStep>(`/workflows/${workflowId}/versions/${versionNumber}/steps/${stepKey}`, data, { params: { org_id: orgId } });
  }

  async deleteWorkflowStep(orgId: UUID, workflowId: UUID, versionNumber: number, stepKey: string): Promise<void> {
    return this.delete<void>(`/workflows/${workflowId}/versions/${versionNumber}/steps/${stepKey}`, { params: { org_id: orgId } });
  }

  // Retry Policy endpoints
  async createRetryPolicy(orgId: UUID, data: CreateRetryPolicyRequest): Promise<RetryPolicy> {
    return this.post<RetryPolicy>('/workflows/retry-policies', data, { params: { org_id: orgId } });
  }

  async getRetryPolicies(orgId: UUID): Promise<RetryPolicy[]> {
    return this.get<RetryPolicy[]>('/workflows/retry-policies', { params: { org_id: orgId } });
  }

  async getRetryPolicy(orgId: UUID, policyId: UUID): Promise<RetryPolicy> {
    return this.get<RetryPolicy>(`/workflows/retry-policies/${policyId}`, { params: { org_id: orgId } });
  }

  async updateRetryPolicy(orgId: UUID, policyId: UUID, data: Partial<CreateRetryPolicyRequest>): Promise<RetryPolicy> {
    return this.patch<RetryPolicy>(`/workflows/retry-policies/${policyId}`, data, { params: { org_id: orgId } });
  }

  async deleteRetryPolicy(orgId: UUID, policyId: UUID): Promise<void> {
    return this.delete<void>(`/workflows/retry-policies/${policyId}`, { params: { org_id: orgId } });
  }

  // Execution endpoints
  async startExecution(orgId: UUID, workflowId: UUID, data: StartExecutionRequest): Promise<WorkflowExecution> {
    return this.post<WorkflowExecution>('/executions', data, { params: { org_id: orgId } });
  }

  async getExecutions(orgId: UUID, params?: { skip?: number; limit?: number; status?: string; workflow_id?: UUID }): Promise<PaginatedResponse<WorkflowExecution>> {
    return this.get<PaginatedResponse<WorkflowExecution>>('/executions', { ...params, org_id: orgId });
  }

  async getExecution(orgId: UUID, executionId: UUID): Promise<ExecutionDetailResponse> {
    return this.get<ExecutionDetailResponse>(`/executions/${executionId}/detail`, { params: { org_id: orgId } });
  }

  async retryExecution(orgId: UUID, executionId: UUID): Promise<WorkflowExecution> {
    return this.post<WorkflowExecution>(`/executions/${executionId}/retry`, {}, { params: { org_id: orgId } });
  }

  async cancelExecution(orgId: UUID, executionId: UUID): Promise<WorkflowExecution> {
    return this.post<WorkflowExecution>(`/executions/${executionId}/cancel`, {}, { params: { org_id: orgId } });
  }

  async compensateExecution(orgId: UUID, executionId: UUID): Promise<WorkflowExecution> {
    return this.post<WorkflowExecution>(`/executions/${executionId}/compensate`, {}, { params: { org_id: orgId } });
  }

  // Step Execution endpoints
  async getStepExecutions(orgId: UUID, executionId: UUID): Promise<StepExecution[]> {
    return this.get<StepExecution[]>(`/executions/${executionId}/steps`, { params: { org_id: orgId } });
  }

  async getStepExecution(orgId: UUID, executionId: UUID, stepExecutionId: UUID): Promise<StepExecution> {
    return this.get<StepExecution>(`/executions/${executionId}/steps/${stepExecutionId}`, { params: { org_id: orgId } });
  }

  async retryStepExecution(orgId: UUID, executionId: UUID, stepExecutionId: UUID): Promise<StepExecution> {
    return this.post<StepExecution>(`/executions/${executionId}/steps/${stepExecutionId}/retry`, {}, { params: { org_id: orgId } });
  }

  // Compensation Execution endpoints
  async getCompensationExecutions(orgId: UUID, executionId: UUID): Promise<CompensationExecution[]> {
    return this.get<CompensationExecution[]>(`/executions/${executionId}/compensations`, { params: { org_id: orgId } });
  }

  async getCompensationExecution(orgId: UUID, executionId: UUID, compExecutionId: UUID): Promise<CompensationExecution> {
    return this.get<CompensationExecution>(`/executions/${executionId}/compensations/${compExecutionId}`, { params: { org_id: orgId } });
  }

  async retryCompensationExecution(orgId: UUID, executionId: UUID, compExecutionId: UUID): Promise<CompensationExecution> {
    return this.post<CompensationExecution>(`/executions/${executionId}/compensations/${compExecutionId}/retry`, {}, { params: { org_id: orgId } });
  }

  // Events
  async getExecutionEvents(orgId: UUID, executionId: UUID): Promise<ExecutionEvent[]> {
    return this.get<ExecutionEvent[]>(`/executions/${executionId}/events`, { params: { org_id: orgId } });
  }

  // Worker endpoints
  async getWorkers(orgId: UUID): Promise<WorkerInfo[]> {
    return this.get<WorkerInfo[]>('/workers', { params: { org_id: orgId } });
  }

  async getWorker(orgId: UUID, workerId: string): Promise<WorkerInfo> {
    return this.get<WorkerInfo>(`/workers/${workerId}`, { params: { org_id: orgId } });
  }

  // Metrics
  async getMetrics(): Promise<string> {
    const response = await this.client.get('/metrics', { responseType: 'text' });
    return response.data;
  }

  // User settings endpoints (not implemented in backend yet)
  // async getCurrentUser(): Promise<User> {
  //   return this.get<User>('/users/me');
  // }

  // async updateUser(data: Partial<User>): Promise<User> {
  //   return this.patch<User>('/users/me', data);
  // }

  // async changePassword(data: { current_password: string; new_password: string }): Promise<void> {
  //   return this.post<void>('/users/me/password', data);
  // }
}

// Export singleton instance
export const apiClient = new ApiClient();

// Export class for testing
export { ApiClient };