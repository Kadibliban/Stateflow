/**
 * StateFlow Zustand Stores
 * Global state management for the frontend
 */

import { create } from 'zustand';
import { persist, devtools } from 'zustand/middleware';
import {
  Workflow,
  WorkflowVersion,
  WorkflowStep,
  RetryPolicy,
  WorkflowExecution,
  StepExecution,
  CompensationExecution,
  ExecutionEvent,
  Organization,
  OrganizationMember,
  User,
  WorkerInfo,
  UUID,
  PaginatedResponse,
  ExecutionDetailResponse,
} from '@/types';

// ============================================
// Auth Store
// ============================================

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,

        setAuth: (user, accessToken, refreshToken) =>
          set({
            user,
            accessToken,
            refreshToken,
            isAuthenticated: true,
          }),

        clearAuth: () =>
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
          }),

        updateUser: (userData) =>
          set((state) => ({
            user: state.user ? { ...state.user, ...userData } : null,
          })),
      }),
      {
        name: 'auth-storage',
        partialize: (state) => ({
          accessToken: state.accessToken,
          refreshToken: state.refreshToken,
          user: state.user,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    { name: 'auth-store' }
  )
);

// ============================================
// Organization Store
// ============================================

interface OrganizationState {
  currentOrganization: Organization | null;
  organizations: Organization[];
  members: OrganizationMember[];
  isLoading: boolean;
  error: string | null;
  setCurrentOrganization: (org: Organization | null) => void;
  setOrganizations: (orgs: Organization[]) => void;
  addOrganization: (org: Organization) => void;
  updateOrganization: (org: Organization) => void;
  removeOrganization: (id: UUID) => void;
  setMembers: (members: OrganizationMember[]) => void;
  addMember: (member: OrganizationMember) => void;
  updateMember: (member: OrganizationMember) => void;
  removeMember: (memberId: UUID) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useOrganizationStore = create<OrganizationState>()(
  devtools(
    persist(
      (set) => ({
        currentOrganization: null,
        organizations: [],
        members: [],
        isLoading: false,
        error: null,

        setCurrentOrganization: (org) => set({ currentOrganization: org }),

        setOrganizations: (orgs) => set({ organizations: orgs }),

        addOrganization: (org) =>
          set((state) => ({ organizations: [...state.organizations, org] })),

        updateOrganization: (org) =>
          set((state) => ({
            organizations: state.organizations.map((o) => (o.id === org.id ? org : o)),
            currentOrganization: state.currentOrganization?.id === org.id ? org : state.currentOrganization,
          })),

        removeOrganization: (id) =>
          set((state) => ({
            organizations: state.organizations.filter((o) => o.id !== id),
            currentOrganization: state.currentOrganization?.id === id ? null : state.currentOrganization,
          })),

        setMembers: (members) => set({ members }),

        addMember: (member) =>
          set((state) => ({ members: [...state.members, member] })),

        updateMember: (member) =>
          set((state) => ({
            members: state.members.map((m) => (m.id === member.id ? member : m)),
          })),

        removeMember: (memberId) =>
          set((state) => ({
            members: state.members.filter((m) => m.id !== memberId),
          })),

        setLoading: (isLoading) => set({ isLoading }),

        setError: (error) => set({ error }),
      }),
      {
        name: 'organization-storage',
        partialize: (state) => ({
          currentOrganization: state.currentOrganization,
          organizations: state.organizations,
        }),
      }
    ),
    { name: 'organization-store' }
  )
);

// ============================================
// Workflow Store
// ============================================

interface WorkflowState {
  workflows: Workflow[];
  currentWorkflow: Workflow | null;
  versions: WorkflowVersion[];
  currentVersion: WorkflowVersion | null;
  steps: WorkflowStep[];
  retryPolicies: RetryPolicy[];
  isLoading: boolean;
  error: string | null;

  // Workflows
  setWorkflows: (workflows: Workflow[]) => void;
  addWorkflow: (workflow: Workflow) => void;
  updateWorkflow: (workflow: Workflow) => void;
  removeWorkflow: (id: UUID) => void;
  setCurrentWorkflow: (workflow: Workflow | null) => void;

  // Versions
  setVersions: (versions: WorkflowVersion[]) => void;
  addVersion: (version: WorkflowVersion) => void;
  setCurrentVersion: (version: WorkflowVersion | null) => void;

  // Steps
  setSteps: (steps: WorkflowStep[]) => void;
  addStep: (step: WorkflowStep) => void;
  updateStep: (step: WorkflowStep) => void;
  removeStep: (stepKey: string) => void;

  // Retry Policies
  setRetryPolicies: (policies: RetryPolicy[]) => void;
  addRetryPolicy: (policy: RetryPolicy) => void;
  updateRetryPolicy: (policy: RetryPolicy) => void;
  removeRetryPolicy: (id: UUID) => void;

  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearWorkflowData: () => void;
}

export const useWorkflowStore = create<WorkflowState>()(
  devtools(
    (set) => ({
      workflows: [],
      currentWorkflow: null,
      versions: [],
      currentVersion: null,
      steps: [],
      retryPolicies: [],
      isLoading: false,
      error: null,

      setWorkflows: (workflows) => set({ workflows }),

      addWorkflow: (workflow) =>
        set((state) => ({ workflows: [...state.workflows, workflow] })),

      updateWorkflow: (workflow) =>
        set((state) => ({
          workflows: state.workflows.map((w) => (w.id === workflow.id ? workflow : w)),
          currentWorkflow: state.currentWorkflow?.id === workflow.id ? workflow : state.currentWorkflow,
        })),

      removeWorkflow: (id) =>
        set((state) => ({
          workflows: state.workflows.filter((w) => w.id !== id),
          currentWorkflow: state.currentWorkflow?.id === id ? null : state.currentWorkflow,
        })),

      setCurrentWorkflow: (workflow) => set({ currentWorkflow: workflow }),

      setVersions: (versions) => set({ versions }),

      addVersion: (version) =>
        set((state) => ({ versions: [...state.versions, version] })),

      setCurrentVersion: (version) => set({ currentVersion: version }),

      setSteps: (steps) => set({ steps }),

      addStep: (step) =>
        set((state) => ({ steps: [...state.steps, step] })),

      updateStep: (step) =>
        set((state) => ({
          steps: state.steps.map((s) => (s.step_key === step.step_key ? step : s)),
        })),

      removeStep: (stepKey) =>
        set((state) => ({
          steps: state.steps.filter((s) => s.step_key !== stepKey),
        })),

      setRetryPolicies: (policies) => set({ retryPolicies: policies }),

      addRetryPolicy: (policy) =>
        set((state) => ({ retryPolicies: [...state.retryPolicies, policy] })),

      updateRetryPolicy: (policy) =>
        set((state) => ({
          retryPolicies: state.retryPolicies.map((p) => (p.id === policy.id ? policy : p)),
        })),

      removeRetryPolicy: (id) =>
        set((state) => ({
          retryPolicies: state.retryPolicies.filter((p) => p.id !== id),
        })),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      clearWorkflowData: () =>
        set({
          workflows: [],
          currentWorkflow: null,
          versions: [],
          currentVersion: null,
          steps: [],
          retryPolicies: [],
        }),
    }),
    { name: 'workflow-store' }
  )
);

// ============================================
// Execution Store
// ============================================

interface ExecutionState {
  executions: WorkflowExecution[];
  currentExecution: ExecutionDetailResponse | null;
  stepExecutions: StepExecution[];
  compensationExecutions: CompensationExecution[];
  events: ExecutionEvent[];
  isLoading: boolean;
  error: string | null;
  filters: {
    status?: string;
    workflowId?: UUID;
    skip: number;
    limit: number;
  };
  total: number;

  // Executions list
  setExecutions: (executions: WorkflowExecution[], total: number) => void;
  addExecution: (execution: WorkflowExecution) => void;
  updateExecution: (execution: WorkflowExecution) => void;
  removeExecution: (id: UUID) => void;

  // Current execution detail
  setCurrentExecution: (execution: ExecutionDetailResponse | null) => void;
  updateCurrentExecution: (execution: Partial<WorkflowExecution>) => void;

  // Step executions
  setStepExecutions: (steps: StepExecution[]) => void;
  updateStepExecution: (step: StepExecution) => void;

  // Compensation executions
  setCompensationExecutions: (comps: CompensationExecution[]) => void;
  updateCompensationExecution: (comp: CompensationExecution) => void;

  // Events
  setEvents: (events: ExecutionEvent[]) => void;
  addEvent: (event: ExecutionEvent) => void;

  // Filters
  setFilters: (filters: Partial<ExecutionState['filters']>) => void;
  resetFilters: () => void;

  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearExecutionData: () => void;
}

const defaultFilters = {
  status: undefined as string | undefined,
  workflowId: undefined as UUID | undefined,
  skip: 0,
  limit: 20,
};

export const useExecutionStore = create<ExecutionState>()(
  devtools(
    (set) => ({
      executions: [],
      currentExecution: null,
      stepExecutions: [],
      compensationExecutions: [],
      events: [],
      isLoading: false,
      error: null,
      filters: defaultFilters,
      total: 0,

      setExecutions: (executions, total) => set({ executions, total }),

      addExecution: (execution) =>
        set((state) => ({ executions: [execution, ...state.executions] })),

      updateExecution: (execution) =>
        set((state) => ({
          executions: state.executions.map((e) => (e.id === execution.id ? execution : e)),
          currentExecution:
            state.currentExecution?.execution.id === execution.id
              ? { ...state.currentExecution, execution }
              : state.currentExecution,
        })),

      removeExecution: (id) =>
        set((state) => ({
          executions: state.executions.filter((e) => e.id !== id),
        })),

      setCurrentExecution: (execution) => set({ currentExecution: execution }),

      updateCurrentExecution: (executionData) =>
        set((state) => ({
          currentExecution: state.currentExecution
            ? { ...state.currentExecution, execution: { ...state.currentExecution.execution, ...executionData } }
            : null,
        })),

      setStepExecutions: (steps) => set({ stepExecutions: steps }),

      updateStepExecution: (step) =>
        set((state) => ({
          stepExecutions: state.stepExecutions.map((s) => (s.id === step.id ? step : s)),
          currentExecution: state.currentExecution
            ? {
                ...state.currentExecution,
                steps: state.currentExecution.steps.map((s) => (s.id === step.id ? step : s)),
              }
            : state.currentExecution,
        })),

      setCompensationExecutions: (comps) => set({ compensationExecutions: comps }),

      updateCompensationExecution: (comp) =>
        set((state) => ({
          compensationExecutions: state.compensationExecutions.map((c) => (c.id === comp.id ? comp : c)),
          currentExecution: state.currentExecution
            ? {
                ...state.currentExecution,
                compensations: state.currentExecution.compensations.map((c) => (c.id === comp.id ? comp : c)),
              }
            : state.currentExecution,
        })),

      setEvents: (events) => set({ events }),

      addEvent: (event) =>
        set((state) => ({ events: [event, ...state.events] })),

      setFilters: (filters) =>
        set((state) => ({
          filters: { ...state.filters, ...filters },
        })),

      resetFilters: () => set({ filters: defaultFilters }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      clearExecutionData: () =>
        set({
          executions: [],
          currentExecution: null,
          stepExecutions: [],
          compensationExecutions: [],
          events: [],
          total: 0,
          filters: defaultFilters,
        }),
    }),
    { name: 'execution-store' }
  )
);

// ============================================
// Worker Store
// ============================================

interface WorkerState {
  workers: WorkerInfo[];
  selectedWorker: WorkerInfo | null;
  isLoading: boolean;
  error: string | null;

  setWorkers: (workers: WorkerInfo[]) => void;
  updateWorker: (worker: WorkerInfo) => void;
  setSelectedWorker: (worker: WorkerInfo | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearWorkerData: () => void;
}

export const useWorkerStore = create<WorkerState>()(
  devtools(
    (set) => ({
      workers: [],
      selectedWorker: null,
      isLoading: false,
      error: null,

      setWorkers: (workers) => set({ workers }),

      updateWorker: (worker) =>
        set((state) => ({
          workers: state.workers.map((w) => (w.worker_id === worker.worker_id ? worker : w)),
          selectedWorker: state.selectedWorker?.worker_id === worker.worker_id ? worker : state.selectedWorker,
        })),

      setSelectedWorker: (worker) => set({ selectedWorker: worker }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      clearWorkerData: () =>
        set({
          workers: [],
          selectedWorker: null,
        }),
    }),
    { name: 'worker-store' }
  )
);

// ============================================
// UI Store
// ============================================

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark' | 'system';
  notifications: Array<{
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    title: string;
    message?: string;
    duration?: number;
  }>;
  modals: Record<string, boolean>;

  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  addNotification: (notification: Omit<UIState['notifications'][0], 'id'>) => void;
  removeNotification: (id: string) => void;
  openModal: (modalId: string) => void;
  closeModal: (modalId: string) => void;
  closeAllModals: () => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        sidebarOpen: true,
        theme: 'system',
        notifications: [],
        modals: {},

        toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

        setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),

        setTheme: (theme) => set({ theme }),

        addNotification: (notification) =>
          set((state) => ({
            notifications: [
              ...state.notifications,
              { ...notification, id: Math.random().toString(36).substr(2, 9) },
            ],
          })),

        removeNotification: (id) =>
          set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
          })),

        openModal: (modalId) =>
          set((state) => ({
            modals: { ...state.modals, [modalId]: true },
          })),

        closeModal: (modalId) =>
          set((state) => {
            const newModals = { ...state.modals };
            delete newModals[modalId];
            return { modals: newModals };
          }),

        closeAllModals: () => set({ modals: {} }),
      }),
      {
        name: 'ui-storage',
        partialize: (state) => ({
          sidebarOpen: state.sidebarOpen,
          theme: state.theme,
        }),
      }
    ),
    { name: 'ui-store' }
  )
);

// ============================================
// React Flow Store (for workflow editor)
// ============================================

import { Node, Edge } from 'reactflow';
import { WorkflowStepDefinition, WorkflowConnection } from '@/types';

interface ReactFlowState {
  nodes: Node[];
  edges: Edge[];
  selectedNode: Node | null;
  selectedEdge: Edge | null;
  isDirty: boolean;
  viewport: { x: number; y: number; zoom: number };

  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  addNode: (node: Node) => void;
  updateNode: (nodeId: string, data: Partial<Node>) => void;
  removeNode: (nodeId: string) => void;
  addEdge: (edge: Edge) => void;
  updateEdge: (edgeId: string, data: Partial<Edge>) => void;
  removeEdge: (edgeId: string) => void;
  setSelectedNode: (node: Node | null) => void;
  setSelectedEdge: (edge: Edge | null) => void;
  setDirty: (dirty: boolean) => void;
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;
  reset: () => void;
  importFromWorkflow: (steps: WorkflowStepDefinition[], connections: WorkflowConnection[]) => void;
  exportToWorkflow: () => { steps: WorkflowStepDefinition[]; connections: WorkflowConnection[] };
}

const nodeTypeColors: Record<string, string> = {
  action: '#3b82f6',
  condition: '#a855f7',
  parallel: '#f97316',
  delay: '#6b7280',
  compensation: '#ef4444',
};

export const useReactFlowStore = create<ReactFlowState>()(
  devtools(
    (set, get) => ({
      nodes: [],
      edges: [],
      selectedNode: null,
      selectedEdge: null,
      isDirty: false,
      viewport: { x: 0, y: 0, zoom: 1 },

      setNodes: (nodes) => set({ nodes, isDirty: true }),

      setEdges: (edges) => set({ edges, isDirty: true }),

      addNode: (node) =>
        set((state) => ({
          nodes: [...state.nodes, node],
          isDirty: true,
        })),

      updateNode: (nodeId, data) =>
        set((state) => ({
          nodes: state.nodes.map((n) => (n.id === nodeId ? { ...n, ...data } : n)),
          selectedNode: state.selectedNode?.id === nodeId ? { ...state.selectedNode, ...data } : state.selectedNode,
          isDirty: true,
        })),

      removeNode: (nodeId) =>
        set((state) => ({
          nodes: state.nodes.filter((n) => n.id !== nodeId),
          edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
          selectedNode: state.selectedNode?.id === nodeId ? null : state.selectedNode,
          isDirty: true,
        })),

      addEdge: (edge) =>
        set((state) => ({
          edges: [...state.edges, edge],
          isDirty: true,
        })),

      updateEdge: (edgeId, data) =>
        set((state) => ({
          edges: state.edges.map((e) => (e.id === edgeId ? { ...e, ...data } : e)),
          selectedEdge: state.selectedEdge?.id === edgeId ? { ...state.selectedEdge, ...data } : state.selectedEdge,
          isDirty: true,
        })),

      removeEdge: (edgeId) =>
        set((state) => ({
          edges: state.edges.filter((e) => e.id !== edgeId),
          selectedEdge: state.selectedEdge?.id === edgeId ? null : state.selectedEdge,
          isDirty: true,
        })),

      setSelectedNode: (node) => set({ selectedNode: node }),

      setSelectedEdge: (edge) => set({ selectedEdge: edge }),

      setDirty: (isDirty) => set({ isDirty }),

      setViewport: (viewport) => set({ viewport }),

      reset: () =>
        set({
          nodes: [],
          edges: [],
          selectedNode: null,
          selectedEdge: null,
          isDirty: false,
          viewport: { x: 0, y: 0, zoom: 1 },
        }),

      importFromWorkflow: (steps, connections) => {
        const nodes: Node[] = steps.map((step) => ({
          id: step.step_key,
          type: 'workflowNode',
          position: { x: step.order * 250, y: 100 },
          data: {
            label: step.name,
            description: step.description,
            type: step.step_type,
            handler: step.handler,
            config: step.config,
            timeout_seconds: step.timeout_seconds,
            retry_policy_id: step.retry_policy_id,
            compensation_handler: step.compensation_handler,
            compensation_config: step.compensation_config,
            depends_on: step.depends_on,
            is_critical: step.is_critical,
            continue_on_failure: step.continue_on_failure,
          },
        }));

        const edges: Edge[] = connections.map((conn, index) => ({
          id: `edge-${index}`,
          source: conn.source,
          target: conn.target,
          sourceHandle: conn.source_handle,
          targetHandle: conn.target_handle,
          type: 'smoothstep',
          animated: true,
          style: { stroke: nodeTypeColors[steps.find((s) => s.step_key === conn.source)?.step_type || 'action'] || '#3b82f6' },
        }));

        set({ nodes, edges, isDirty: false });
      },

      exportToWorkflow: () => {
        const { nodes, edges } = get();
        const steps: WorkflowStepDefinition[] = nodes
          .filter((n) => n.type === 'workflowNode')
          .map((node, index) => ({
            step_key: node.id,
            name: node.data.label,
            description: node.data.description,
            step_type: node.data.type,
            order: index,
            handler: node.data.handler,
            config: node.data.config,
            input_mapping: {},
            output_mapping: {},
            timeout_seconds: node.data.timeout_seconds || 300,
            retry_policy_id: node.data.retry_policy_id,
            compensation_handler: node.data.compensation_handler,
            compensation_config: node.data.compensation_config,
            depends_on: node.data.depends_on || [],
            is_critical: node.data.is_critical ?? true,
            continue_on_failure: node.data.continue_on_failure ?? false,
          }));

        const connections: WorkflowConnection[] = edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          source_handle: edge.sourceHandle as string | undefined,
          target_handle: edge.targetHandle as string | undefined,
        }));

        return { steps, connections };
      },
    }),
    { name: 'reactflow-store' }
  )
);