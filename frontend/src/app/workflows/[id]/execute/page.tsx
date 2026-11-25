/**
 * Execute Workflow Page
 * Page for starting a workflow execution with input data
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkflowStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  WorkflowIcon,
  ChevronLeftIcon,
  PlayIcon,
  XIcon,
  EyeIcon,
  SettingsIcon,
  GitBranchIcon,
  ZapIcon,
  ClockIcon,
  CopyIcon,
  CheckIcon,
  AlertCircleIcon,
} from '@/components/ui/icons';

export default function ExecuteWorkflowPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { currentWorkflow, versions } = useWorkflowStore();
  const queryClient = useQueryClient();

  const [activeVersion, setActiveVersion] = useState<number>(1);
  const [inputData, setInputData] = useState<string>('{}');
  const [idempotencyKey, setIdempotencyKey] = useState<string>('');
  const [jsonError, setJsonError] = useState<string | null>(null);

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

  // Start execution mutation
  const startExecutionMutation = useMutation({
    mutationFn: (data: { input_data: Record<string, any>; idempotency_key?: string }) =>
      apiClient.startExecution(currentOrganization!.id, workflowId, data),
    onSuccess: (execution) => {
      queryClient.invalidateQueries({ queryKey: ['executions'] });
      router.push(`/executions/${execution.id}`);
    },
    onError: (err: any) => {
      const message = err.response?.data?.detail || 'Failed to start execution';
      setJsonError(message);
    },
  });

  // Validate JSON input
  const validateJson = (value: string) => {
    try {
      JSON.parse(value);
      setJsonError(null);
      return true;
    } catch {
      setJsonError('Invalid JSON format');
      return false;
    }
  };

  const handleInputChange = (value: string) => {
    setInputData(value);
    validateJson(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateJson(inputData)) return;
    if (!currentOrganization) return;

    let parsedInput: Record<string, any>;
    try {
      parsedInput = JSON.parse(inputData);
    } catch {
      setJsonError('Invalid JSON format');
      return;
    }

    startExecutionMutation.mutate({
      input_data: parsedInput,
      idempotency_key: idempotencyKey || undefined,
    });
  };

  // Update active version when versions load
  useEffect(() => {
    if (versionsData && versionsData.length > 0) {
      const latestVersion = Math.max(...versionsData.map(v => v.version_number));
      setActiveVersion(latestVersion);
    }
  }, [versionsData]);

  // Set default input data example based on workflow
  useEffect(() => {
    if (workflow && inputData === '{}') {
      // Provide a helpful example
      setInputData(JSON.stringify({
        // Example input data structure
        // Add your workflow input fields here
      }, null, 2));
    }
  }, [workflow]);

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

  const isActive = workflow.status === 'active';
  const activeVersionData = versionsData?.find(v => v.version_number === activeVersion);

  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href={`/workflows/${workflow.id}`}
              className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{workflow.name}</h1>
                <span className={cn('status-badge', workflow.status)}>
                  {workflow.status}
                </span>
              </div>
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                Execute workflow version
              </p>
            </div>
          </div>
          <Link
            href={`/workflows/${workflow.id}`}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <EyeIcon className="w-4 h-4" />
            View Details
          </Link>
        </div>

        {/* Warning if not active */}
        {!isActive && (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <AlertCircleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
              <div>
                <h3 className="font-medium text-yellow-800 dark:text-yellow-200">Workflow is not active</h3>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  Only active workflows can be executed. Activate the workflow from the Versions tab.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Version Selector & Configuration */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="border-b border-gray-200 dark:border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Execution Configuration</h2>
          </div>

          <div className="p-6 space-y-6">
            {/* Version Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Version to Execute
              </label>
              <div className="flex items-center gap-4 flex-wrap">
                <select
                  value={activeVersion}
                  onChange={(e) => setActiveVersion(parseInt(e.target.value))}
                  disabled={versionsLoading}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 min-w-[200px]"
                >
                  {versionsData?.map((version) => (
                    <option key={version.id} value={version.version_number}>
                      v{version.version_number} - {version.steps?.length || 0} steps
                      {version.changelog && ` - ${version.changelog}`}
                    </option>
                  ))}
                </select>
                {versionsLoading && <span className="text-sm text-gray-500 dark:text-gray-400">Loading versions...</span>}
              </div>
              {activeVersionData && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Created {formatRelativeTime(activeVersionData.created_at)} • {activeVersionData.steps?.length || 0} steps
                  {activeVersionData.changelog && ` • ${activeVersionData.changelog}`}
                </p>
              )}
            </div>

            {/* Workflow Info */}
            {activeVersionData && activeVersionData.steps && activeVersionData.steps.length > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-800 pt-6">
                <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Steps in this version</h3>
                <div className="flex flex-wrap gap-2">
                  {activeVersionData.steps.map((step: any) => (
                    <span
                      key={step.step_key}
                      className={cn(
                        'px-2 py-1 text-xs rounded font-medium',
                        getStepTypeColor(step.step_type)
                      )}
                    >
                      {step.name} ({step.step_type})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Input Data */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center justify-between">
                Input Data (JSON)
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(inputData)}
                  className="text-xs text-primary-500 hover:underline"
                >
                  <CopyIcon className="w-3 h-3 inline mr-1" />
                  Copy
                </button>
              </label>
              <textarea
                value={inputData}
                onChange={(e) => handleInputChange(e.target.value)}
                rows={12}
                className={cn(
                  'w-full px-3 py-2 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm',
                  jsonError ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                )}
                placeholder='{"key": "value"}'
                disabled={startExecutionMutation.isPending}
              />
              {jsonError && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400 flex items-center gap-1">
                  <AlertCircleIcon className="w-4 h-4" />
                  {jsonError}
                </p>
              )}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Enter JSON input data for the workflow execution
              </p>
            </div>

            {/* Idempotency Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Idempotency Key (optional)
              </label>
              <input
                type="text"
                value={idempotencyKey}
                onChange={(e) => setIdempotencyKey(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                placeholder="auto-generated if not provided"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Provide a unique key to ensure idempotent execution. Leave empty for auto-generation.
              </p>
            </div>

            {/* Execute Button */}
            <div className="flex items-center gap-4 pt-4 border-t border-gray-200 dark:border-gray-800">
              <button
                type="submit"
                form="execute-form"
                disabled={startExecutionMutation.isPending || !isActive || !!jsonError}
                className="inline-flex items-center gap-2 px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed text-lg"
              >
                <PlayIcon className="w-5 h-5" />
                {startExecutionMutation.isPending ? 'Starting...' : 'Execute Workflow'}
              </button>
              {!isActive && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Activate workflow to enable execution
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Quick Reference */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            Input Schema Reference
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            The workflow input accepts any valid JSON object. Structure your data based on your workflow's step requirements.
          </p>
          <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg font-mono text-sm overflow-auto">
            <pre>{JSON.stringify({
              // Example input structure
              // workflow_input_field: "value",
              // nested_object: {
              //   key: "value"
              // },
              // array_field: ["item1", "item2"]
            }, null, 2)}</pre>
          </div>
        </div>

        {/* Hidden form for submit */}
        <form id="execute-form" onSubmit={handleSubmit} className="hidden">
          <button type="submit" disabled={startExecutionMutation.isPending || !isActive || !!jsonError} />
        </form>
      </div>
    </MainLayout>
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