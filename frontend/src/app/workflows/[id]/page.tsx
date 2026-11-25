/**
 * Workflow Detail Page
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, getStepTypeColor, cn } from '@/lib/utils';
import {
  WorkflowIcon,
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
  ChevronLeftIcon,
} from '@/components/ui/icons';

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { workflows, setWorkflows, versions, setVersions, currentVersion, setCurrentVersion } = useWorkflowStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'overview' | 'versions' | 'editor'>('overview');

  // Fetch workflow
  const { data: workflow, isLoading: workflowLoading } = useQuery({
    queryKey: ['workflow', currentOrganization?.id, workflowId],
    queryFn: () => apiClient.getWorkflow(currentOrganization!.id, workflowId),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId,
  });

  // Fetch versions
  const { data: versionsData, isLoading: versionsLoading } = useQuery({
    queryKey: ['workflow-versions', currentOrganization?.id, workflowId],
    queryFn: () => apiClient.getWorkflowVersions(currentOrganization!.id, workflowId),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId,
  });

  // Activate mutation
  const activateMutation = useMutation({
    mutationFn: (versionNumber: number) => apiClient.activateWorkflow(currentOrganization!.id, workflowId, versionNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', currentOrganization?.id, workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflow-versions', currentOrganization?.id, workflowId] });
    },
  });

  // Deprecate mutation
  const deprecateMutation = useMutation({
    mutationFn: () => apiClient.deprecateWorkflow(currentOrganization!.id, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', currentOrganization?.id, workflowId] });
    },
  });

  // Clone mutation
  const cloneMutation = useMutation({
    mutationFn: (name: string) => apiClient.cloneWorkflow(currentOrganization!.id, workflowId, name),
    onSuccess: (newWorkflow) => {
      router.push(`/workflows/${newWorkflow.id}`);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => apiClient.deleteWorkflow(currentOrganization!.id, workflowId),
    onSuccess: () => {
      router.push('/workflows');
    },
  });

  // Update stores
  React.useEffect(() => {
    if (workflow) {
      // Update workflow in store
    }
  }, [workflow]);

  React.useEffect(() => {
    if (versionsData) setVersions(versionsData);
  }, [versionsData, setVersions]);

  if (!isAuthenticated || !currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Loading...</h1>
        </div>
      </MainLayout>
    );
  }

  if (workflowLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent" />
        </div>
      </MainLayout>
    );
  }

  if (!workflow) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Workflow not found</h1>
          <Link href="/workflows" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Back to Workflows
          </Link>
        </div>
      </MainLayout>
    );
  }

  const handleDelete = () => {
    if (confirm(`Are you sure you want to delete "${workflow.name}"? This action cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  const handleClone = () => {
    const name = prompt('Enter a name for the cloned workflow:', `${workflow.name} (copy)`);
    if (name) {
      cloneMutation.mutate(name);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href="/workflows"
              className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{workflow.name}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={cn('status-badge', workflow.status)}>
                  {workflow.status}
                </span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  v{workflow.current_version} • {workflow.versions?.length || 0} versions
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/workflows/${workflow.id}/editor`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              <WorkflowIcon className="w-4 h-4" />
              Visual Editor
            </Link>
            <button
              onClick={handleClone}
              className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
              title="Clone"
            >
              <CopyIcon className="w-4 h-4" />
            </button>
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/30"
              title="Delete"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Description */}
        {workflow.description && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <p className="text-gray-600 dark:text-gray-400">{workflow.description}</p>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="flex gap-4 px-6" aria-label="Workflow tabs">
              <button
                onClick={() => setActiveTab('overview')}
                className={cn(
                  'py-4 px-1 border-b-2 font-medium text-sm transition-colors',
                  activeTab === 'overview'
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                )}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('versions')}
                className={cn(
                  'py-4 px-1 border-b-2 font-medium text-sm transition-colors',
                  activeTab === 'versions'
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                )}
              >
                Versions ({versions.length})
              </button>
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'overview' && <OverviewTab workflow={workflow} />}
            {activeTab === 'versions' && <VersionsTab workflow={workflow} versions={versions} onActivate={activateMutation.mutate} />}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

function OverviewTab({ workflow }: { workflow: any }) {
  return (
    <div className="space-y-6">
      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <Link
          href={`/workflows/${workflow.id}/execute`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600"
        >
          <PlayIcon className="w-4 h-4" />
          Execute
        </Link>
        <Link
          href={`/executions?workflow_id=${workflow.id}`}
          className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          <EyeIcon className="w-4 h-4" />
          View Executions
        </Link>
      </div>

      {/* Info Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <InfoCard label="Status" value={workflow.status} badge={true} />
        <InfoCard label="Current Version" value={`v${workflow.current_version}`} />
        <InfoCard label="Total Versions" value={workflow.versions?.length || 0} />
        <InfoCard label="Created" value={formatRelativeTime(workflow.created_at)} />
        <InfoCard label="Updated" value={formatRelativeTime(workflow.updated_at)} />
        <InfoCard label="Activated" value={workflow.activated_at ? formatRelativeTime(workflow.activated_at) : 'Never'} />
        {workflow.deprecated_at && (
          <InfoCard label="Deprecated" value={formatRelativeTime(workflow.deprecated_at)} />
        )}
        <InfoCard label="Organization" value={workflow.organization?.name || 'N/A'} />
      </div>

      {/* Tags */}
      {workflow.tags && workflow.tags.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {workflow.tags.map((tag: string) => (
              <span key={tag} className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      {workflow.workflow_metadata && Object.keys(workflow.workflow_metadata).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Metadata</h3>
          <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-64">
            {JSON.stringify(workflow.workflow_metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function VersionsTab({
  workflow,
  versions,
  onActivate,
}: {
  workflow: any;
  versions: any[];
  onActivate: (version: number) => void;
}) {
  if (versions.length === 0) {
    return (
      <div className="text-center py-12">
        <GitBranchIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No versions yet</h3>
        <p className="text-gray-500 dark:text-gray-400 mb-6">Create a version to start building your workflow</p>
        <Link href={`/workflows/${workflow.id}/versions/new`} className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
          <PlusIcon className="w-4 h-4" />
          Create Version
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {versions.map((version) => (
        <VersionCard
          key={version.id}
          version={version}
          isCurrent={version.version_number === workflow.current_version}
          onActivate={() => onActivate(version.version_number)}
        />
      ))}
    </div>
  );
}

function VersionCard({ version, isCurrent, onActivate }: { version: any; isCurrent: boolean; onActivate: () => void }) {
  return (
    <div className={cn(
      'p-4 rounded-lg border transition-colors',
      isCurrent
        ? 'border-primary-300 dark:border-primary-700 bg-primary-50 dark:bg-primary-900/20'
        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
    )}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className={cn('p-2 rounded-lg', isCurrent ? 'bg-primary-100 dark:bg-primary-900/30' : 'bg-gray-100 dark:bg-gray-800')}>
            <span className="text-2xl font-bold text-gray-900 dark:text-white">v{version.version_number}</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-gray-900 dark:text-white">Version {version.version_number}</h3>
              {isCurrent && (
                <span className="status-badge active">Active</span>
              )}
              {version.changelog && (
                <span className="text-xs text-gray-500 dark:text-gray-400">{version.changelog}</span>
              )}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Created {formatRelativeTime(version.created_at)} • {version.steps?.length || 0} steps
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isCurrent && (
            <button
              onClick={onActivate}
              className="px-3 py-1.5 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              Activate
            </button>
          )}
          <Link
            href={`/workflows/${version.workflow_id}/versions/${version.version_number}`}
            className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            title="View Version"
          >
            <EyeIcon className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Steps Preview */}
      {version.steps && version.steps.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex flex-wrap gap-2">
            {version.steps.slice(0, 5).map((step: any) => (
              <span
                key={step.step_key}
                className={cn(
                  'px-2 py-1 text-xs rounded font-medium',
                  getStepTypeColor(step.step_type)
                )}
              >
                {step.name}
              </span>
            ))}
            {version.steps.length > 5 && (
              <span className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400 rounded">
                +{version.steps.length - 5} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
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