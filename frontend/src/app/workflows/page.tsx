/**
 * Workflows List Page
 */

'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  WorkflowIcon,
  PlusIcon,
  SearchIcon,
  FilterIcon,
  MoreVerticalIcon,
  EditIcon,
  CopyIcon,
  TrashIcon,
  PlayIcon,
  EyeIcon,
} from '@/components/ui/icons';

export default function WorkflowsPage() {
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization, organizations, setCurrentOrganization } = useOrganizationStore();
  const { workflows = [], setWorkflows, isLoading = false, setLoading } = useWorkflowStore();
  const queryClient = useQueryClient();

  // Fetch organizations
  const { data: orgsData } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Fetch workflows
  const { data: workflowsData, isLoading: workflowsLoading, refetch } = useQuery({
    queryKey: ['workflows', currentOrganization?.id],
    queryFn: () => apiClient.getWorkflows(currentOrganization!.id, { limit: 50 }),
    enabled: isAuthenticated && !!currentOrganization,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (workflowId: string) => apiClient.deleteWorkflow(currentOrganization!.id, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', currentOrganization?.id] });
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
    if (workflowsData) setWorkflows(workflowsData.items);
  }, [workflowsData, setWorkflows]);

  React.useEffect(() => {
    setLoading(workflowsLoading);
  }, [workflowsLoading, setLoading]);

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

  const handleDelete = (workflowId: string, name: string) => {
    if (confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      deleteMutation.mutate(workflowId);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Workflows</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage your workflow definitions and versions
            </p>
          </div>
          <Link href="/workflows/new" className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            <PlusIcon className="w-4 h-4" />
            New Workflow
          </Link>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search workflows..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            <FilterIcon className="w-4 h-4" />
            Filters
          </button>
        </div>

        {/* Workflows Table */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
          {workflows.length === 0 ? (
            <div className="text-center py-12">
              <WorkflowIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No workflows yet</h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6">Create your first workflow to get started</p>
              <Link href="/workflows/new" className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
                <PlusIcon className="w-4 h-4" />
                Create Workflow
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800/50">
                  <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                    <th className="px-6 py-3 font-medium">Workflow</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Version</th>
                    <th className="px-6 py-3 font-medium">Current Version</th>
                    <th className="px-6 py-3 font-medium">Updated</th>
                    <th className="px-6 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {workflows.map((workflow) => (
                    <tr key={workflow.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">{workflow.name}</p>
                          {workflow.description && (
                            <p className="text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs">{workflow.description}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={cn('status-badge', workflow.status)}>
                          {workflow.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">
                        v{workflow.current_version}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                        {workflow.versions?.length || 0} versions
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                        {formatRelativeTime(workflow.updated_at)}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/workflows/${workflow.id}`}
                            className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                            title="View"
                          >
                            <EyeIcon className="w-4 h-4" />
                          </Link>
                          <Link
                            href={`/workflows/${workflow.id}/edit`}
                            className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                            title="Edit"
                          >
                            <EditIcon className="w-4 h-4" />
                          </Link>
                          <Link
                            href={`/workflows/${workflow.id}/editor`}
                            className="p-2 text-primary-500 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 rounded-lg hover:bg-primary-50 dark:hover:bg-primary-900/30"
                            title="Visual Editor"
                          >
                            <WorkflowIcon className="w-4 h-4" />
                          </Link>
                          <button
                            onClick={() => handleDelete(workflow.id, workflow.name)}
                            disabled={deleteMutation.isPending}
                            className="p-2 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                            title="Delete"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  );
}