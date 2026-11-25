/**
 * Executions List Page
 */

'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useExecutionStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, formatDuration, getStatusColor, cn } from '@/lib/utils';
import {
  ExecutionIcon,
  PlayIcon,
  RotateCcwIcon,
  XIcon,
  EyeIcon,
  FilterIcon,
  SearchIcon,
  ChevronDownIcon,
} from '@/components/ui/icons';

export default function ExecutionsPage() {
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization, organizations, setCurrentOrganization } = useOrganizationStore();
  const { executions = [], setExecutions, total = 0, filters, setFilters, resetFilters, isLoading = false, setLoading } = useExecutionStore();
  const queryClient = useQueryClient();

  // Fetch organizations
  const { data: orgsData } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Fetch executions
  const { data: executionsData, isLoading: executionsLoading, refetch } = useQuery({
    queryKey: ['executions', currentOrganization?.id, filters],
    queryFn: () => apiClient.getExecutions(currentOrganization!.id, {
      limit: filters.limit,
      skip: filters.skip,
      status: filters.status,
      workflow_id: filters.workflowId,
    }),
    enabled: isAuthenticated && !!currentOrganization,
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: (executionId: string) => apiClient.retryExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions', currentOrganization?.id, filters] });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (executionId: string) => apiClient.cancelExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions', currentOrganization?.id, filters] });
    },
  });

  // Compensate mutation
  const compensateMutation = useMutation({
    mutationFn: (executionId: string) => apiClient.compensateExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions', currentOrganization?.id, filters] });
    },
  });

  // Update stores
  React.useEffect(() => {
    if (orgsData && organizations.length === 0) {
      if (!currentOrganization && orgsData.length > 0) {
        setCurrentOrganization(orgsData[0]);
      }
    }
  }, [orgsData, currentOrganization, organizations.length, setCurrentOrganization]);

  React.useEffect(() => {
    if (executionsData) setExecutions(executionsData.items, executionsData.total);
  }, [executionsData, setExecutions]);

  React.useEffect(() => {
    setLoading(executionsLoading);
  }, [executionsLoading, setLoading]);

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Please sign in</h1>
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
          <Link href="/settings" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Manage Organizations
          </Link>
        </div>
      </MainLayout>
    );
  }

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'running', label: 'Running' },
    { value: 'completed', label: 'Completed' },
    { value: 'failed', label: 'Failed' },
    { value: 'compensating', label: 'Compensating' },
    { value: 'compensated', label: 'Compensated' },
    { value: 'cancelled', label: 'Cancelled' },
    { value: 'timed_out', label: 'Timed Out' },
  ];

  const handleRetry = (executionId: string) => {
    retryMutation.mutate(executionId);
  };

  const handleCancel = (executionId: string) => {
    if (confirm('Are you sure you want to cancel this execution?')) {
      cancelMutation.mutate(executionId);
    }
  };

  const handleCompensate = (executionId: string) => {
    if (confirm('Are you sure you want to trigger compensation for this execution?')) {
      compensateMutation.mutate(executionId);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Executions</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Monitor and manage workflow executions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              disabled={executionsLoading}
              className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
              aria-label="Refresh"
            >
              <RefreshIcon className={cn('w-5 h-5', executionsLoading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search executions..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div className="relative">
            <select
              value={filters.status || ''}
              onChange={(e) => setFilters({ status: e.target.value || undefined, skip: 0 })}
              className="appearance-none pr-10 pl-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronDownIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          </div>
          {filters.status && (
            <button
              onClick={() => setFilters({ status: undefined })}
              className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            >
              Clear filter
            </button>
          )}
        </div>

        {/* Executions Table */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
          {executions.length === 0 && !executionsLoading ? (
            <div className="text-center py-12">
              <ExecutionIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No executions found</h3>
              <p className="text-gray-500 dark:text-gray-400">Start a workflow to see executions here</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800/50">
                    <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="px-6 py-3 font-medium">Execution</th>
                      <th className="px-6 py-3 font-medium">Workflow</th>
                      <th className="px-6 py-3 font-medium">Status</th>
                      <th className="px-6 py-3 font-medium">Current Step</th>
                      <th className="px-6 py-3 font-medium">Duration</th>
                      <th className="px-6 py-3 font-medium">Started</th>
                      <th className="px-6 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {executions.map((execution) => (
                      <tr key={execution.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-6 py-4">
                          <div>
                            <p className="font-mono text-sm text-gray-900 dark:text-white">
                              {execution.id.slice(0, 8)}...
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              v{execution.version_id?.slice(0, 8) || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <p className="font-medium text-gray-900 dark:text-white truncate max-w-xs">
                            {execution.workflow?.name || 'Unknown'}
                          </p>
                        </td>
                        <td className="px-6 py-4">
                          <span className={cn('status-badge', execution.status)}>
                            {execution.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-sm text-gray-900 dark:text-white">
                            {execution.current_step || '-'}
                          </p>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-sm text-gray-900 dark:text-white">
                            {formatDuration(execution.step_executions?.[0]?.duration_ms || 0)}
                          </p>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {formatRelativeTime(execution.created_at)}
                          </p>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/executions/${execution.id}`}
                              className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                              title="View Details"
                            >
                              <EyeIcon className="w-4 h-4" />
                            </Link>
                            {['failed', 'timed_out'].includes(execution.status) && (
                              <button
                                onClick={() => handleRetry(execution.id)}
                                disabled={retryMutation.isPending}
                                className="p-2 text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30"
                                title="Retry"
                              >
                                <RotateCcwIcon className="w-4 h-4" />
                              </button>
                            )}
                            {['running', 'pending'].includes(execution.status) && (
                              <button
                                onClick={() => handleCancel(execution.id)}
                                disabled={cancelMutation.isPending}
                                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                                title="Cancel"
                              >
                                <XIcon className="w-4 h-4" />
                              </button>
                            )}
                            {['failed', 'compensating', 'partially_compensated'].includes(execution.status) && (
                              <button
                                onClick={() => handleCompensate(execution.id)}
                                disabled={compensateMutation.isPending}
                                className="p-2 text-orange-500 hover:text-orange-700 dark:text-orange-400 dark:hover:text-orange-300 rounded-lg hover:bg-orange-50 dark:hover:bg-orange-900/30"
                                title="Compensate"
                              >
                                <RotateCcwIcon className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {total > filters.limit && (
                <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Showing {filters.skip + 1} to {Math.min(filters.skip + filters.limit, total)} of {total} executions
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setFilters({ skip: Math.max(0, filters.skip - filters.limit) })}
                      disabled={filters.skip === 0}
                      className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronLeftIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setFilters({ skip: filters.skip + filters.limit })}
                      disabled={filters.skip + filters.limit >= total}
                      className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronRightIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </MainLayout>
  );
}

// Need to import RefreshIcon and ChevronLeftIcon
import { RefreshIcon, ChevronLeftIcon, ChevronRightIcon } from '@/components/ui/icons';