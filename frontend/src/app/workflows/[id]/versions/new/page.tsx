/**
 * Create Workflow Version Page
 * Create a new version from the current workflow state
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore, useReactFlowStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  ChevronLeftIcon,
  GitBranchIcon,
  PlusIcon,
  AlertCircleIcon,
  CheckIcon,
  XIcon,
  EyeIcon,
  SaveIcon,
  AlertTriangleIcon,
  SettingsIcon,
} from '@/components/ui/icons';
import { WorkflowVersion, WorkflowStepDefinition, WorkflowConnection } from '@/types';

export default function CreateVersionPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { workflows, versions, setVersions } = useWorkflowStore();
  const { nodes, edges, exportToWorkflow } = useReactFlowStore();
  const queryClient = useQueryClient();

  const [changelog, setChangelog] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<{
    steps: WorkflowStepDefinition[];
    connections: WorkflowConnection[];
  } | null>(null);

  // Fetch workflow
  const { data: workflow, isLoading: workflowLoading } = useQuery({
    queryKey: ['workflow', currentOrganization?.id, workflowId],
    queryFn: () => apiClient.getWorkflow(currentOrganization!.id, workflowId),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId,
  });

  // Fetch existing versions
  const { data: versionsData, isLoading: versionsLoading } = useQuery({
    queryKey: ['workflow-versions', currentOrganization?.id, workflowId],
    queryFn: () => apiClient.getWorkflowVersions(currentOrganization!.id, workflowId),
    enabled: isAuthenticated && !!currentOrganization && !!workflowId,
  });

  // Create version mutation
  const createVersionMutation = useMutation({
    mutationFn: (data: {
      definition: Record<string, any>;
      steps: WorkflowStepDefinition[];
      connections: WorkflowConnection[];
      variables: Record<string, any>;
      changelog: string;
    }) => apiClient.createWorkflowVersion(currentOrganization!.id, workflowId, data),
    onSuccess: async (newVersion) => {
      // Refresh versions list
      const versionsList = await apiClient.getWorkflowVersions(currentOrganization!.id, workflowId);
      setVersions(versionsList);
      router.push(`/workflows/${workflowId}/versions/${newVersion.version_number}`);
    },
    onError: (err: any) => {
      const message = err.response?.data?.detail || 'Failed to create version';
      setError(message);
    },
  });

  // Generate preview from editor state
  const generatePreview = () => {
    if (nodes.length === 0 && edges.length === 0) {
      // Try to get from current version
      if (versionsData && versionsData.length > 0) {
        const latestVersion = versionsData.reduce((latest, v) =>
          v.version_number > latest.version_number ? v : latest
        );
        setPreviewData({
          steps: latestVersion.steps || [],
          connections: latestVersion.connections || [],
        });
      }
      return;
    }

    const { steps, connections } = exportToWorkflow();
    setPreviewData({ steps, connections });
  };

  useEffect(() => {
    generatePreview();
  }, [nodes, edges, versionsData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentOrganization) return;
    if (!changelog.trim()) {
      setError('Changelog is required');
      return;
    }

    if (!previewData || (previewData.steps.length === 0 && previewData.connections.length === 0)) {
      setError('No workflow data to version. Please add steps in the Visual Editor first.');
      return;
    }

    setIsLoading(true);
    try {
      await createVersionMutation.mutateAsync({
        definition: {},
        steps: previewData.steps,
        connections: previewData.connections,
        variables: {},
        changelog: changelog.trim(),
      });
    } catch {
      // Error handled by mutation
    } finally {
      setIsLoading(false);
    }
  };

  const nextVersionNumber = (versionsData?.length || 0) + 1;

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
          <button onClick={() => router.push('/workflows')} className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Back to Workflows
          </button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push(`/workflows/${workflowId}`)}
            className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ChevronLeftIcon className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Create Version v{nextVersionNumber}</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              {workflow.name} • Snapshot current workflow state
            </p>
          </div>
        </div>

        {/* Warning if no data */}
        {(!previewData || (previewData.steps.length === 0 && previewData.connections.length === 0)) && (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <AlertTriangleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
              <div>
                <h3 className="font-medium text-yellow-800 dark:text-yellow-200">No workflow data to version</h3>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  The Visual Editor is empty. Add steps and connections in the editor, then return here to create a version.
                </p>
                <Link
                  href={`/workflows/${workflowId}/editor`}
                  className="inline-flex items-center gap-1 mt-2 text-sm text-yellow-800 dark:text-yellow-200 hover:underline"
                >
                  <EyeIcon className="w-4 h-4" />
                  Open Visual Editor
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Version Preview */}
        {previewData && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <GitBranchIcon className="w-5 h-5" />
              Version Preview (v{nextVersionNumber})
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <PreviewStat label="Steps" value={previewData.steps.length} icon={<GitBranchIcon className="w-5 h-5" />} />
              <PreviewStat label="Connections" value={previewData.connections.length} icon={<EyeIcon className="w-5 h-5" />} />
              <PreviewStat label="Version" value={nextVersionNumber} icon={<PlusIcon className="w-5 h-5" />} />
            </div>

            {previewData.steps.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Steps</h4>
                <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                  {previewData.steps.slice(0, 10).map((step) => (
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
                  {previewData.steps.length > 10 && (
                    <span className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400 rounded">
                      +{previewData.steps.length - 10} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {previewData.connections.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Connections</h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {previewData.connections.slice(0, 8).map((conn, index) => (
                    <div key={index} className="text-sm font-mono text-gray-600 dark:text-gray-400">
                      {conn.source} → {conn.target}
                    </div>
                  ))}
                  {previewData.connections.length > 8 && (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      +{previewData.connections.length - 8} more connections
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Changelog Form */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <AlertCircleIcon className="w-5 h-5" />
            Changelog (Required)
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Describe what changed in this version. This helps track the evolution of your workflow.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 flex items-center gap-2">
                <AlertCircleIcon className="w-5 h-5" />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div>
              <label htmlFor="changelog" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Changes
              </label>
              <textarea
                id="changelog"
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g., Added payment processing step, fixed timeout handling, updated retry policies"
                required
                disabled={isLoading}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Minimum 10 characters • {changelog.length}/500
              </p>
            </div>

            <div className="flex items-center gap-4 pt-4 border-t border-gray-200 dark:border-gray-800">
              <button
                type="submit"
                disabled={isLoading || !changelog.trim() || changelog.length < 10 || !previewData || previewData.steps.length === 0}
                className="inline-flex items-center gap-2 px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <SaveIcon className="w-5 h-5" />
                {isLoading ? 'Creating Version...' : 'Create Version'}
              </button>
              <button
                type="button"
                onClick={() => router.push(`/workflows/${workflowId}`)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>

        {/* Tips */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <AlertTriangleIcon className="w-5 h-5" />
            Best Practices
          </h3>
          <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-2 list-disc list-inside">
            <li>Use semantic versioning in changelogs: "Added feature X", "Fixed bug Y", "Refactored Z"</li>
            <li>Create versions before making breaking changes</li>
            <li>Each version is immutable - changes require a new version</li>
            <li>Only active versions can be executed</li>
            <li>Use the Visual Editor to design workflows before versioning</li>
          </ul>
        </div>
      </div>
    </MainLayout>
  );
}

function PreviewStat({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 text-center">
      <div className="text-gray-500 dark:text-gray-400 mb-1">{icon}</div>
      <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
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