/**
 * Dashboard Page
 * Overview of workflows, executions, and workers
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore, useExecutionStore, useWorkerStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  WorkflowIcon,
  ExecutionIcon,
  WorkerIcon,
  SuccessIcon,
  WarningIcon,
  ErrorIcon,
  PendingIcon,
  ArrowRightIcon,
  PlusIcon,
} from '@/components/ui/icons';

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuthStore();
  const { currentOrganization, setCurrentOrganization, organizations } = useOrganizationStore();
  const { workflows = [], setWorkflows } = useWorkflowStore();
  const { executions = [], setExecutions, total: executionsTotal = 0 } = useExecutionStore();
  const { workers = [], setWorkers } = useWorkerStore();

  // Fetch organizations
  const { data: orgsData, isLoading: orgsLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Fetch workflows for current organization
  const { data: workflowsData, isLoading: workflowsLoading } = useQuery({
    queryKey: ['workflows', currentOrganization?.id],
    queryFn: () => apiClient.getWorkflows(currentOrganization!.id),
    enabled: isAuthenticated && !!currentOrganization,
  });

  // Fetch executions for current organization
  const { data: executionsData, isLoading: executionsLoading } = useQuery({
    queryKey: ['executions', currentOrganization?.id],
    queryFn: () => apiClient.getExecutions(currentOrganization!.id, { limit: 10 }),
    enabled: isAuthenticated && !!currentOrganization,
  });

  // Fetch workers for current organization
  const { data: workersData, isLoading: workersLoading } = useQuery({
    queryKey: ['workers', currentOrganization?.id],
    queryFn: () => apiClient.getWorkers(currentOrganization!.id),
    enabled: isAuthenticated && !!currentOrganization,
  });

  // Update stores when data changes
  React.useEffect(() => {
    if (orgsData) {
      organizations.length === 0 && orgsData.forEach((org) => {
        // We need to add organizations to store, but this is a simplified approach
      });
      if (!currentOrganization && orgsData.length > 0) {
        setCurrentOrganization(orgsData[0]);
      }
    }
  }, [orgsData, currentOrganization, organizations.length, setCurrentOrganization]);

  React.useEffect(() => {
    if (workflowsData) setWorkflows(workflowsData.items);
  }, [workflowsData, setWorkflows]);

  React.useEffect(() => {
    if (executionsData) setExecutions(executionsData.items, executionsData.total);
  }, [executionsData, setExecutions]);

  React.useEffect(() => {
    if (workersData) setWorkers(workersData);
  }, [workersData, setWorkers]);

  // Calculate stats
  const activeWorkflows = workflows.filter((w) => w.status === 'active').length;
  const runningExecutions = executions.filter((e) => e.status === 'running').length;
  const failedExecutions = executions.filter((e) => e.status === 'failed').length;
  const healthyWorkers = workers.filter((w) => w.status === 'healthy').length;

  const recentExecutions = executions.slice(0, 5);
  const recentWorkflows = workflows.slice(0, 5);

  if (orgsLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent" />
        </div>
      </MainLayout>
    );
  }

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Welcome to StateFlow</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">Please sign in to access your dashboard</p>
          <Link href="/login" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Sign In
          </Link>
        </div>
      </MainLayout>
    );
  }

  if (!currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Organization Selected</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">Select or create an organization to get started</p>
          <Link href="/settings" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Manage Organizations
          </Link>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Overview of your workflows, executions, and workers
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/workflows/new" className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
              <PlusIcon className="w-4 h-4" />
              New Workflow
            </Link>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Active Workflows"
            value={activeWorkflows}
            subtitle={`${workflows.length} total workflows`}
            icon={<WorkflowIcon className="w-6 h-6 text-blue-500" />}
            href="/workflows"
          />
          <StatCard
            title="Running Executions"
            value={runningExecutions}
            subtitle={`${executionsTotal} total executions`}
            icon={<ExecutionIcon className="w-6 h-6 text-green-500" />}
            href="/executions"
            trend={runningExecutions > 0 ? 'up' : 'neutral'}
          />
          <StatCard
            title="Failed Executions"
            value={failedExecutions}
            subtitle="Requires attention"
            icon={<ExecutionIcon className="w-6 h-6 text-red-500" />}
            href="/executions?status=failed"
            trend={failedExecutions > 0 ? 'up' : 'neutral'}
            trendColor="red"
          />
          <StatCard
            title="Healthy Workers"
            value={healthyWorkers}
            subtitle={`${workers.length} total workers`}
            icon={<WorkerIcon className="w-6 h-6 text-purple-500" />}
            href="/workers"
          />
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Executions */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Executions</h2>
                <Link href="/executions" className="text-sm text-primary-500 hover:text-primary-600">
                  View all
                  <ArrowRightIcon className="w-4 h-4 inline ml-1" />
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {recentExecutions.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  No executions yet
                </div>
              ) : (
                <div className="space-y-3">
                  {recentExecutions.map((execution) => (
                    <ExecutionRow key={execution.id} execution={execution} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Workflows */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Workflows</h2>
                <Link href="/workflows" className="text-sm text-primary-500 hover:text-primary-600">
                  View all
                  <ArrowRightIcon className="w-4 h-4 inline ml-1" />
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {recentWorkflows.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  No workflows yet
                  <br />
                  <Link href="/workflows/new" className="text-primary-500 hover:text-primary-600 mt-2 inline-block">
                    Create your first workflow
                  </Link>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentWorkflows.map((workflow) => (
                    <WorkflowRow key={workflow.id} workflow={workflow} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Worker Status */}
        {workers.length > 0 && (
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Worker Status</h2>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-3 font-medium">Worker ID</th>
                      <th className="pb-3 font-medium">Status</th>
                      <th className="pb-3 font-medium">Active Tasks</th>
                      <th className="pb-3 font-medium">Processed</th>
                      <th className="pb-3 font-medium">Failed</th>
                      <th className="pb-3 font-medium">Last Heartbeat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {workers.map((worker) => (
                      <tr key={worker.worker_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="py-3 text-sm font-mono text-gray-900 dark:text-white">{worker.worker_id}</td>
                        <td className="py-3">
                          <span className={cn('status-badge', worker.status)}>
                            {worker.status}
                          </span>
                        </td>
                        <td className="py-3 text-sm text-gray-900 dark:text-white">{worker.active_tasks}</td>
                        <td className="py-3 text-sm text-gray-900 dark:text-white">{worker.processed_tasks}</td>
                        <td className="py-3 text-sm text-gray-900 dark:text-white">{worker.failed_tasks}</td>
                        <td className="py-3 text-sm text-gray-500 dark:text-gray-400">
                          {formatRelativeTime(worker.last_heartbeat)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </MainLayout>
  );
}

// Components
function StatCard({
  title,
  value,
  subtitle,
  icon,
  href,
  trend = 'neutral',
  trendColor = 'green',
}: {
  title: string;
  value: number;
  subtitle: string;
  icon: React.ReactNode;
  href: string;
  trend?: 'up' | 'down' | 'neutral';
  trendColor?: 'green' | 'red';
}) {
  return (
    <Link href={href} className="card-hover group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{subtitle}</p>
        </div>
        <div className="p-3 bg-primary-50 dark:bg-primary-900/30 rounded-xl text-primary-500 dark:text-primary-400">
          {icon}
        </div>
      </div>
    </Link>
  );
}

function ExecutionRow({ execution }: { execution: any }) {
  return (
    <Link href={`/executions/${execution.id}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <div className={cn('w-2 h-2 rounded-full', getStatusColor(execution.status).replace('bg-', 'bg-').replace('text-', ''))} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
            {execution.workflow?.name || 'Unknown Workflow'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
            {execution.id.slice(0, 8)}...
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className={cn('status-badge text-xs', execution.status)}>
          {execution.status.replace('_', ' ')}
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatRelativeTime(execution.created_at)}
        </span>
      </div>
    </Link>
  );
}

function WorkflowRow({ workflow }: { workflow: any }) {
  return (
    <Link href={`/workflows/${workflow.id}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <div className={cn('w-2 h-2 rounded-full', getStatusColor(workflow.status).replace('bg-', 'bg-').replace('text-', ''))} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{workflow.name}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">v{workflow.current_version}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className={cn('status-badge text-xs', workflow.status)}>
          {workflow.status}
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatRelativeTime(workflow.updated_at)}
        </span>
      </div>
    </Link>
  );
}

// Card Components
function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm', className)}>
      {children}
    </div>
  );
}

function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">{children}</div>;
}

function CardContent({ children }: { children: React.ReactNode }) {
  return <div className="p-6">{children}</div>;
}