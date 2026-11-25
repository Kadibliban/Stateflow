/**
 * Execution Detail Page
 * Shows execution timeline with step-by-step visualization
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useExecutionStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, formatDuration, getStatusColor, cn } from '@/lib/utils';
import {
  ExecutionIcon,
  ChevronLeftIcon,
  PlayIcon,
  RotateCcwIcon,
  XIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  ZapIcon,
  GitBranchIcon,
  SettingsIcon,
  RotateCcwIcon as CompensationIcon,
  EyeIcon,
  RefreshIcon,
} from '@/components/ui/icons';

export default function ExecutionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const executionId = params.id as string;
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { currentExecution, setCurrentExecution, stepExecutions, setStepExecutions, compensationExecutions, setCompensationExecutions, events, setEvents } = useExecutionStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'timeline' | 'steps' | 'compensations' | 'events'>('timeline');

  // Fetch execution detail
  const { data: executionData, isLoading: executionLoading, refetch } = useQuery({
    queryKey: ['execution', currentOrganization?.id, executionId],
    queryFn: () => apiClient.getExecution(currentOrganization!.id, executionId),
    enabled: isAuthenticated && !!currentOrganization && !!executionId,
    refetchInterval: (data: any) => data?.status === 'running' ? 5000 : false,
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: () => apiClient.retryExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['execution', currentOrganization?.id, executionId] });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: () => apiClient.cancelExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['execution', currentOrganization?.id, executionId] });
    },
  });

  // Compensate mutation
  const compensateMutation = useMutation({
    mutationFn: () => apiClient.compensateExecution(currentOrganization!.id, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['execution', currentOrganization?.id, executionId] });
    },
  });

  // Update stores
  React.useEffect(() => {
    if (executionData) {
      setCurrentExecution(executionData);
      setStepExecutions(executionData.steps || []);
      setCompensationExecutions(executionData.compensations || []);
      setEvents(executionData.events || []);
    }
  }, [executionData, setCurrentExecution, setStepExecutions, setCompensationExecutions, setEvents]);

  if (!isAuthenticated || !currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Loading...</h1>
        </div>
      </MainLayout>
    );
  }

  if (executionLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent" />
        </div>
      </MainLayout>
    );
  }

  const execution = currentExecution?.execution;
  const steps = stepExecutions;
  const compensations = compensationExecutions;
  const executionEvents = events;

  if (!execution) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Execution not found</h1>
          <Link href="/executions" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Back to Executions
          </Link>
        </div>
      </MainLayout>
    );
  }

  const isRunning = ['pending', 'running', 'compensating'].includes(execution.status);
  const isFailed = ['failed', 'timed_out'].includes(execution.status);
  const isCompensating = ['compensating', 'partially_compensated'].includes(execution.status);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href="/executions"
              className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Execution {execution.id.slice(0, 8)}...
                </h1>
                <span className={cn('status-badge', execution.status)}>
                  {execution.status.replace('_', ' ')}
                </span>
              </div>
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                {execution.workflow?.name || 'Unknown Workflow'} • v{execution.version_id?.slice(0, 8) || 'N/A'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              disabled={executionLoading}
              className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <RefreshIcon className={cn('w-4 h-4', executionLoading && 'animate-spin')} />
            </button>
            {isFailed && (
              <button
                onClick={() => retryMutation.mutate()}
                disabled={retryMutation.isPending}
                className="inline-flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                <RotateCcwIcon className="w-4 h-4" />
                Retry
              </button>
            )}
            {isRunning && (
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                <XIcon className="w-4 h-4" />
                Cancel
              </button>
            )}
            {(isFailed || isCompensating) && (
              <button
                onClick={() => compensateMutation.mutate()}
                disabled={compensateMutation.isPending}
                className="inline-flex items-center gap-2 px-3 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
              >
                <CompensationIcon className="w-4 h-4" />
                Compensate
              </button>
            )}
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <SummaryCard
            label="Status"
            value={execution.status.replace('_', ' ')}
            icon={<ExecutionIcon className="w-5 h-5" />}
            color={getStatusColor(execution.status).replace('bg-', 'text-').replace('dark:bg-', 'dark:text-')}
          />
          <SummaryCard
            label="Duration"
            value={execution.started_at && execution.completed_at
              ? formatDuration(new Date(execution.completed_at).getTime() - new Date(execution.started_at).getTime())
              : execution.started_at
                ? formatDuration(Date.now() - new Date(execution.started_at).getTime())
                : 'Not started'}
            icon={<ClockIcon className="w-5 h-5" />}
          />
          <SummaryCard
            label="Steps"
            value={`${steps.filter(s => s.status === 'completed').length}/${steps.length}`}
            icon={<ZapIcon className="w-5 h-5" />}
          />
          <SummaryCard
            label="Compensations"
            value={compensations.length}
            icon={<CompensationIcon className="w-5 h-5" />}
          />
          <SummaryCard
            label="Retries"
            value={execution.retry_count}
            icon={<RotateCcwIcon className="w-5 h-5" />}
          />
        </div>

        {/* Tabs */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="flex gap-4 px-6" aria-label="Execution tabs">
              <TabButton active={activeTab === 'timeline'} onClick={() => setActiveTab('timeline')}>Timeline</TabButton>
              <TabButton active={activeTab === 'steps'} onClick={() => setActiveTab('steps')}>Steps ({steps.length})</TabButton>
              <TabButton active={activeTab === 'compensations'} onClick={() => setActiveTab('compensations')}>Compensations ({compensations.length})</TabButton>
              <TabButton active={activeTab === 'events'} onClick={() => setActiveTab('events')}>Events ({executionEvents.length})</TabButton>
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'timeline' && <TimelineTab execution={execution} steps={steps} compensations={compensations} />}
            {activeTab === 'steps' && <StepsTab steps={steps} />}
            {activeTab === 'compensations' && <CompensationsTab compensations={compensations} />}
            {activeTab === 'events' && <EventsTab events={executionEvents} />}
          </div>
        </div>

        {/* Context/Input/Output */}
        {(execution.context || execution.input_data || execution.output_data) && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Data</h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {execution.input_data && Object.keys(execution.input_data).length > 0 && (
                <DataPanel title="Input" data={execution.input_data} />
              )}
              {execution.output_data && Object.keys(execution.output_data).length > 0 && (
                <DataPanel title="Output" data={execution.output_data} />
              )}
              {execution.context && Object.keys(execution.context).length > 0 && (
                <DataPanel title="Context" data={execution.context} />
              )}
            </div>
          </div>
        )}

        {/* Error Details */}
        {execution.error && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-red-200 dark:border-red-800 p-6">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 mb-3">
              <AlertCircleIcon className="w-5 h-5" />
              <h2 className="text-lg font-semibold">Error</h2>
            </div>
            <p className="text-red-600 dark:text-red-400 mb-3">{execution.error}</p>
            {execution.error_details && Object.keys(execution.error_details).length > 0 && (
              <pre className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-sm overflow-auto max-h-64">
                {JSON.stringify(execution.error_details, null, 2)}
              </pre>
            )}
          </div>
        )}
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

function SummaryCard({ label, value, icon, color }: { label: string; value: string | number; icon: React.ReactNode; color?: string }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
          <p className={cn('mt-1 font-medium text-gray-900 dark:text-white', color)}>{value}</p>
        </div>
        <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400">
          {icon}
        </div>
      </div>
    </div>
  );
}

function TimelineTab({ execution, steps, compensations }: { execution: any; steps: any[]; compensations: any[] }) {
  // Combine steps and compensations into a single timeline
  const timelineItems = [
    ...steps.map((step) => ({
      ...step,
      type: 'step' as const,
      timestamp: step.started_at || step.created_at,
    })),
    ...compensations.map((comp) => ({
      ...comp,
      type: 'compensation' as const,
      timestamp: comp.started_at || comp.created_at,
    })),
  ].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  if (timelineItems.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        No timeline events yet
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {timelineItems.map((item, index) => (
        <TimelineItem
          key={`${item.type}-${item.id}`}
          item={item}
          index={index}
          isLast={index === timelineItems.length - 1}
        />
      ))}
    </div>
  );
}

function TimelineItem({ item, index, isLast }: { item: any; index: number; isLast: boolean }) {
  const statusColor = getStatusColor(item.status);
  const icon = getStepIcon(item.type || 'action');
  const isCompensation = item.type === 'compensation';

  return (
    <div className={cn('relative pl-6 pb-6 border-l-2', isLast ? 'border-l-transparent' : 'border-gray-200 dark:border-gray-700')}>
      <div className="flex items-start gap-4">
        <div className={cn('flex-shrink-0 w-8 h-8 rounded-full border-2 border-white dark:border-gray-900 flex items-center justify-center', statusColor.replace('bg-', 'bg-').replace('text-', 'text-'))}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h4 className="font-medium text-gray-900 dark:text-white">
                {isCompensation ? `Compensation: ${item.step_key}` : item.step_key}
              </h4>
              <span className={cn('status-badge text-xs', item.status)}>
                {item.status.replace('_', ' ')}
              </span>
            </div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {formatRelativeTime(item.timestamp)}
            </span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {isCompensation ? item.compensation_handler : item.handler}
          </p>
          {item.duration_ms && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Duration: {formatDuration(item.duration_ms)}
            </p>
          )}
          {item.error && (
            <p className="text-sm text-red-600 dark:text-red-400 mt-2">
              {item.error}
            </p>
          )}
          {item.output_data && Object.keys(item.output_data).length > 0 && (
            <details className="mt-2">
              <summary className="text-sm text-primary-500 hover:text-primary-600 cursor-pointer">
                View Output
              </summary>
              <pre className="mt-2 bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-auto max-h-32">
                {JSON.stringify(item.output_data, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function StepsTab({ steps }: { steps: any[] }) {
  if (steps.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        No steps yet
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {steps.map((step) => (
        <StepRow key={step.id} step={step} />
      ))}
    </div>
  );
}

function StepRow({ step }: { step: any }) {
  const statusColor = getStatusColor(step.status);
  const icon = getStepIcon(step.type || 'action');

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center gap-4">
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', statusColor.replace('bg-', 'bg-').replace('text-', 'text-'))}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-gray-900 dark:text-white">{step.step_key}</h4>
            <span className={cn('status-badge text-xs', step.status)}>
              {step.status.replace('_', ' ')}
            </span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{step.handler}</p>
          {step.duration_ms && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Duration: {formatDuration(step.duration_ms)}
            </p>
          )}
        </div>
        {step.output_data && Object.keys(step.output_data).length > 0 && (
          <details>
            <summary className="text-sm text-primary-500 hover:text-primary-600 cursor-pointer">
              View Output
            </summary>
            <pre className="mt-2 bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-auto max-h-32">
              {JSON.stringify(step.output_data, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

function CompensationsTab({ compensations }: { compensations: any[] }) {
  if (compensations.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        No compensations executed
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {compensations.map((comp) => (
        <CompensationRow key={comp.id} compensation={comp} />
      ))}
    </div>
  );
}

function CompensationRow({ compensation }: { compensation: any }) {
  const statusColor = getStatusColor(compensation.status);

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center gap-4">
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', statusColor.replace('bg-', 'bg-').replace('text-', 'text-'))}>
          <CompensationIcon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-gray-900 dark:text-white">Compensation: {compensation.step_key}</h4>
            <span className={cn('status-badge text-xs', compensation.status)}>
              {compensation.status.replace('_', ' ')}
            </span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{compensation.compensation_handler}</p>
          {compensation.duration_ms && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Duration: {formatDuration(compensation.duration_ms)}
            </p>
          )}
        </div>
        {compensation.output_data && Object.keys(compensation.output_data).length > 0 && (
          <details>
            <summary className="text-sm text-primary-500 hover:text-primary-600 cursor-pointer">
              View Output
            </summary>
            <pre className="mt-2 bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-auto max-h-32">
              {JSON.stringify(compensation.output_data, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

function EventsTab({ events }: { events: any[] }) {
  if (events.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        No events recorded
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <EventRow key={event.id} event={event} />
      ))}
    </div>
  );
}

function EventRow({ event }: { event: any }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{event.event_type}</span>
          <span className="text-sm text-gray-900 dark:text-white">{event.step_key || 'N/A'}</span>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatRelativeTime(event.created_at)}
        </span>
      </div>
      {event.payload && Object.keys(event.payload).length > 0 && (
        <details className="mt-2">
          <summary className="text-sm text-primary-500 hover:text-primary-600 cursor-pointer">
            View Payload
          </summary>
          <pre className="mt-2 bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-auto max-h-32">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function DataPanel({ title, data }: { title: string; data: any }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">{title}</h3>
      <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-64">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function getStepIcon(type: string) {
  switch (type) {
    case 'action':
      return <ZapIcon className="w-5 h-5" />;
    case 'condition':
      return <GitBranchIcon className="w-5 h-5" />;
    case 'parallel':
      return <SettingsIcon className="w-5 h-5" />;
    case 'delay':
      return <ClockIcon className="w-5 h-5" />;
    case 'compensation':
      return <CompensationIcon className="w-5 h-5" />;
    case 'start':
      return <PlayIcon className="w-5 h-5" />;
    default:
      return <ZapIcon className="w-5 h-5" />;
  }
}