/**
 * Workflow Version Detail Page
 * View a specific workflow version with steps, connections, and metadata
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  WorkflowIcon,
  ChevronLeftIcon,
  EditIcon,
  CopyIcon,
  TrashIcon,
  PlayIcon,
  RotateCcwIcon,
  DownloadIcon,
  ChevronRightIcon,
  PlusIcon,
  EyeIcon,
  SettingsIcon,
  GitBranchIcon,
  ZapIcon,
  ClockIcon,
  XIcon,
  CheckIcon,
  AlertCircleIcon,
} from '@/components/ui/icons';
import { WorkflowVersion, WorkflowStepDefinition, WorkflowConnection } from '@/types';

export default function VersionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const versionNumber = parseInt(params.version as string, 10);
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { versions, setVersions } = useWorkflowStore();
  const queryClient = useQueryClient();

  // Fetch version
  const { data: version, isLoading: versionLoading, refetch } = useQuery({
    queryKey: ['workflow-version', currentOrganization?.id, workflowId, versionNumber],
    queryFn: () => apiClient.getWorkflowVersion(currentOrganization!.id, workflowId, versionNumber),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId && !!versionNumber,
  });

  // Activate mutation
  const activateMutation = useMutation({
    mutationFn: () => apiClient.activateWorkflow(currentOrganization!.id, workflowId, versionNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', currentOrganization?.id, workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflow-versions', currentOrganization?.id, workflowId] });
      refetch();
    },
  });

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: () => apiClient.exportWorkflowVersion(currentOrganization!.id, workflowId, versionNumber),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow-${workflowId}-v${versionNumber}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });

  // Update stores
  useEffect(() => {
    if (version) {
      // Could update version in store if needed
    }
  }, [version]);

  if (!isAuthenticated || !currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Loading...</h1>
        </div>
      </MainLayout>
    );
  }

  if (versionLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent" />
        </div>
      </MainLayout>
    );
  }

  if (!version) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Version not found</h1>
          <Link href={`/workflows/${workflowId}`} className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Back to Workflow
          </Link>
        </div>
      </MainLayout>
    );
  }

  // Fetch parent workflow for context
  const { data: workflow } = useQuery({
    queryKey: ['workflow', currentOrganization?.id, workflowId],
    queryFn: () => apiClient.getWorkflow(currentOrganization!.id, workflowId),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId,
  });

  const steps = version.steps || [];
  const connections = version.connections || [];
  const isCurrentVersion = workflow?.current_version === version.version_number;

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href={`/workflows/${workflowId}`}
              className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <Link href={`/workflows/${workflowId}`} className="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                  {workflow?.name || 'Workflow'}
                </Link>
                <span className="text-gray-400">/</span>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">v{version.version_number}</h1>
                {isCurrentVersion && (
                  <span className={cn('status-badge', 'active')}>Active</span>
                )}
              </div>
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                {version.changelog || 'No changelog'} • {steps.length} steps • {connections.length} connections
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
              className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
              title="Export Version"
            >
              <DownloadIcon className="w-4 h-4" />
            </button>
            {!isCurrentVersion && (
              <button
                onClick={() => activateMutation.mutate()}
                disabled={activateMutation.isPending}
                className="inline-flex items-center gap-2 px-3 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
              >
                <CheckIcon className="w-4 h-4" />
                Activate
              </button>
            )}
            <Link
              href={`/workflows/${workflowId}/editor`}
              className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <EditIcon className="w-4 h-4" />
              Edit
            </Link>
          </div>
        </div>

        {/* Changelog */}
        {version.changelog && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Changelog</h3>
            <p className="text-gray-600 dark:text-gray-400">{version.changelog}</p>
          </div>
        )}

        {/* Info Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <InfoCard label="Version" value={`v${version.version_number}`} />
          <InfoCard label="Steps" value={steps.length} />
          <InfoCard label="Connections" value={connections.length} />
          <InfoCard label="Created" value={formatRelativeTime(version.created_at)} />
          <InfoCard label="Created By" value={version.created_by} />
          <InfoCard label="Status" value={isCurrentVersion ? 'Active' : 'Inactive'} badge={true} />
        </div>

        {/* Tabs */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="flex gap-4 px-6" aria-label="Version tabs">
              <TabButton active={true} onClick={() => {}}>
                Steps ({steps.length})
              </TabButton>
              <TabButton active={false} onClick={() => {}}>
                Connections ({connections.length})
              </TabButton>
              <TabButton active={false} onClick={() => {}}>
                Variables
              </TabButton>
              <TabButton active={false} onClick={() => {}}>
                Definition
              </TabButton>
            </nav>
          </div>

          <div className="p-6">
            {/* Steps Tab */}
            <div className="space-y-4">
              {steps.length === 0 ? (
                <div className="text-center py-12">
                  <GitBranchIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No steps in this version</h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-6">Use the Visual Editor to add steps to this workflow version</p>
                  <Link href={`/workflows/${workflowId}/editor`} className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
                    <PlusIcon className="w-4 h-4" />
                    Open Editor
                  </Link>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700">
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">#</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Step Key</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Name</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Type</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Handler</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Timeout</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Depends On</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Critical</th>
                        <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Continue on Failure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {steps.map((step, index) => (
                        <tr key={step.step_key} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                          <td className="p-3 text-sm text-gray-900 dark:text-white font-mono">{index + 1}</td>
                          <td className="p-3 text-sm font-mono text-gray-900 dark:text-white">{step.step_key}</td>
                          <td className="p-3 text-sm text-gray-900 dark:text-white">{step.name}</td>
                          <td className="p-3">
                            <span className={cn('px-2 py-0.5 text-xs rounded font-medium', getStepTypeColor(step.step_type))}>
                              {step.step_type}
                            </span>
                          </td>
                          <td className="p-3 text-sm font-mono text-gray-600 dark:text-gray-400 max-w-[200px] truncate">{step.handler}</td>
                          <td className="p-3 text-sm text-gray-600 dark:text-gray-400">{step.timeout_seconds}s</td>
                          <td className="p-3 text-sm text-gray-600 dark:text-gray-400">
                            {step.depends_on && step.depends_on.length > 0 ? (
                              <span className="font-mono">{step.depends_on.join(', ')}</span>
                            ) : (
                              <span className="text-gray-400 dark:text-gray-500">-</span>
                            )}
                          </td>
                          <td className="p-3 text-center">
                            {step.is_critical ? (
                              <CheckIcon className="w-4 h-4 text-green-500 mx-auto" />
                            ) : (
                              <XIcon className="w-4 h-4 text-gray-400 mx-auto" />
                            )}
                          </td>
                          <td className="p-3 text-center">
                            {step.continue_on_failure ? (
                              <CheckIcon className="w-4 h-4 text-green-500 mx-auto" />
                            ) : (
                              <XIcon className="w-4 h-4 text-gray-400 mx-auto" />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Connections */}
        {connections.length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <GitBranchIcon className="w-5 h-5" />
              Connections ({connections.length})
            </h3>
            <div className="space-y-2">
              {connections.map((conn, index) => (
                <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                  <span className="text-sm font-mono text-gray-900 dark:text-white px-2 py-1 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                    {conn.source}
                  </span>
                  <ChevronRightIcon className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-mono text-gray-900 dark:text-white px-2 py-1 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                    {conn.target}
                  </span>
                  {(conn.source_handle || conn.target_handle) && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {conn.source_handle ? `(${conn.source_handle})` : ''} → {conn.target_handle ? `(${conn.target_handle})` : ''}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Variables */}
        {version.variables && Object.keys(version.variables).length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <SettingsIcon className="w-5 h-5" />
              Variables
            </h3>
            <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-96 font-mono">
              {JSON.stringify(version.variables, null, 2)}
            </pre>
          </div>
        )}

        {/* Definition */}
        {version.definition && Object.keys(version.definition).length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <SettingsIcon className="w-5 h-5" />
              Definition
            </h3>
            <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-96 font-mono">
              {JSON.stringify(version.definition, null, 2)}
            </pre>
          </div>
        )}

        {/* Raw JSON Export */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <SettingsIcon className="w-5 h-5" />
              Raw Version Data
            </h3>
            <button
              onClick={() => navigator.clipboard.writeText(JSON.stringify(version, null, 2))}
              className="text-sm text-primary-500 hover:underline flex items-center gap-1"
            >
              <CopyIcon className="w-4 h-4" />
              Copy JSON
            </button>
          </div>
          <details className="group">
            <summary className="text-sm text-primary-500 hover:text-primary-600 cursor-pointer flex items-center gap-2">
              <ChevronRightIcon className={cn('w-4 h-4 transition-transform', 'group-open:rotate-90')} />
              Click to expand full version JSON
            </summary>
            <pre className="mt-4 bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-96 font-mono">
              {JSON.stringify(version, null, 2)}
            </pre>
          </details>
        </div>
      </div>
    </MainLayout>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'py-4 px-1 border-b-2 font-medium text-sm transition-colors',
        active
          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
          : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
      )}
    >
      {children}
    </button>
  );
}

function InfoCard({ label, value, badge }: { label: string; value: string | number; badge?: boolean }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
      {badge ? (
        <span className={cn('status-badge mt-1 inline-block', value)}>
          {value}
        </span>
      ) : (
        <p className="mt-1 font-medium text-gray-900 dark:text-white">{value}</p>
      )}
    </div>
  );
}

function getStepTypeColor(type: string): string {
  switch (type) {
    case 'action':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
    case 'condition':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300';
    case 'parallel':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300';
    case 'delay':
      return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
    case 'compensation':
      return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
  }
}