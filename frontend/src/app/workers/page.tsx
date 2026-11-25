/**
 * Workers Monitoring Page
 */

'use client';

import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore, useWorkerStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, getStatusColor, cn } from '@/lib/utils';
import {
  WorkerIcon,
  RefreshIcon,
  ActivityIcon,
  ServerIcon,
  DatabaseIcon,
  NetworkIcon,
  AlertCircleIcon,
  CheckCircleIcon,
} from '@/components/ui/icons';

export default function WorkersPage() {
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization, organizations, setCurrentOrganization } = useOrganizationStore();
  const { workers = [], setWorkers, selectedWorker, setSelectedWorker, isLoading = false, setLoading } = useWorkerStore();

  // Fetch organizations
  const { data: orgsData } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Fetch workers
  const { data: workersData, isLoading: workersLoading, refetch } = useQuery({
    queryKey: ['workers', currentOrganization?.id],
    queryFn: () => apiClient.getWorkers(currentOrganization!.id),
    enabled: isAuthenticated && !!currentOrganization,
    refetchInterval: 30000, // Refresh every 30 seconds
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
    if (workersData) setWorkers(workersData);
  }, [workersData, setWorkers]);

  React.useEffect(() => {
    setLoading(workersLoading);
  }, [workersLoading, setLoading]);

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Please sign in</h1>
        </div>
      </MainLayout>
    );
  }

  if (!currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Organization Selected</h1>
        </div>
      </MainLayout>
    );
  }

  // Calculate stats
  const healthyWorkers = workers.filter((w) => w.status === 'healthy').length;
  const busyWorkers = workers.filter((w) => w.status === 'busy').length;
  const offlineWorkers = workers.filter((w) => w.status === 'offline').length;
  const totalActiveTasks = workers.reduce((sum, w) => sum + w.active_tasks, 0);
  const totalProcessed = workers.reduce((sum, w) => sum + w.processed_tasks, 0);
  const totalFailed = workers.reduce((sum, w) => sum + w.failed_tasks, 0);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Workers</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Monitor worker health and performance
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={workersLoading}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <RefreshIcon className={cn('w-4 h-4', workersLoading && 'animate-spin')} />
            Refresh
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Workers"
            value={workers.length}
            icon={<WorkerIcon className="w-6 h-6 text-blue-500" />}
            color="blue"
          />
          <StatCard
            title="Healthy"
            value={healthyWorkers}
            icon={<CheckCircleIcon className="w-6 h-6 text-green-500" />}
            color="green"
          />
          <StatCard
            title="Busy"
            value={busyWorkers}
            icon={<ActivityIcon className="w-6 h-6 text-yellow-500" />}
            color="yellow"
          />
          <StatCard
            title="Offline"
            value={offlineWorkers}
            icon={<AlertCircleIcon className="w-6 h-6 text-red-500" />}
            color="red"
          />
          <StatCard
            title="Active Tasks"
            value={totalActiveTasks}
            icon={<ServerIcon className="w-6 h-6 text-purple-500" />}
            color="purple"
          />
        </div>

        {/* Throughput Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
          <StatCard
            title="Total Processed"
            value={totalProcessed.toLocaleString()}
            icon={<DatabaseIcon className="w-6 h-6 text-green-500" />}
            color="green"
            subtitle="All time"
          />
          <StatCard
            title="Total Failed"
            value={totalFailed.toLocaleString()}
            icon={<AlertCircleIcon className="w-6 h-6 text-red-500" />}
            color="red"
            subtitle="All time"
          />
        </div>

        {/* Workers Table */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
          {workers.length === 0 && !workersLoading ? (
            <div className="text-center py-12">
              <WorkerIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No workers found</h3>
              <p className="text-gray-500 dark:text-gray-400">Start workers to see them here</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800/50">
                  <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                    <th className="px-6 py-3 font-medium">Worker ID</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Active Tasks</th>
                    <th className="px-6 py-3 font-medium">Processed</th>
                    <th className="px-6 py-3 font-medium">Failed</th>
                    <th className="px-6 py-3 font-medium">Success Rate</th>
                    <th className="px-6 py-3 font-medium">Queues</th>
                    <th className="px-6 py-3 font-medium">Last Heartbeat</th>
                    <th className="px-6 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {workers.map((worker) => (
                    <tr
                      key={worker.worker_id}
                      className={cn(
                        'hover:bg-gray-50 dark:hover:bg-gray-800/50',
                        selectedWorker?.worker_id === worker.worker_id && 'bg-primary-50 dark:bg-primary-900/20'
                      )}
                      onClick={() => setSelectedWorker(worker)}
                    >
                      <td className="px-6 py-4">
                        <p className="font-mono text-sm font-medium text-gray-900 dark:text-white">
                          {worker.worker_id}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <span className={cn('status-badge', worker.status)}>
                          {worker.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-gray-900 dark:text-white">{worker.active_tasks}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-900 dark:text-white">{worker.processed_tasks.toLocaleString()}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-red-600 dark:text-red-400">{worker.failed_tasks.toLocaleString()}</span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-green-500 rounded-full transition-all duration-300"
                              style={{ width: `${worker.processed_tasks > 0 ? ((worker.processed_tasks / (worker.processed_tasks + worker.failed_tasks)) * 100) : 100}%` }}
                            />
                          </div>
                          <span className="text-sm text-gray-500 dark:text-gray-400 w-16 text-right">
                            {worker.processed_tasks + worker.failed_tasks > 0
                              ? `${((worker.processed_tasks / (worker.processed_tasks + worker.failed_tasks)) * 100).toFixed(1)}%`
                              : '100%'}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {worker.queues.map((queue) => (
                            <span key={queue} className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                              {queue}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {formatRelativeTime(worker.last_heartbeat)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedWorker(worker);
                          }}
                          className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                          title="View Details"
                        >
                          <EyeIcon className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Worker Detail Panel */}
        {selectedWorker && (
          <WorkerDetailPanel worker={selectedWorker} onClose={() => setSelectedWorker(null)} />
        )}
      </div>
    </MainLayout>
  );
}

function StatCard({
  title,
  value,
  icon,
  color,
  subtitle,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    green: 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    yellow: 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
    red: 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    purple: 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{subtitle}</p>}
        </div>
        <div className={cn('p-3 rounded-xl', colors[color] || colors.blue)}>
          {icon}
        </div>
      </div>
    </div>
  );
}

function WorkerDetailPanel({ worker, onClose }: { worker: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-labelledby="worker-detail-title">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} aria-hidden="true" />
      <div className="w-96 max-w-full bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
          <h2 id="worker-detail-title" className="text-lg font-semibold text-gray-900 dark:text-white">
            Worker Details
          </h2>
          <button onClick={onClose} className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <XIcon className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-6 overflow-y-auto">
          <div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Information</h3>
            <dl className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <dt className="text-gray-500 dark:text-gray-400">Worker ID</dt>
                <dd className="font-mono text-gray-900 dark:text-white">{worker.worker_id}</dd>
                <dt className="text-gray-500 dark:text-gray-400">Status</dt>
                <dd>
                  <span className={cn('status-badge', worker.status)}>{worker.status}</span>
                </dd>
                <dt className="text-gray-500 dark:text-gray-400">Active Tasks</dt>
                <dd className="font-mono text-gray-900 dark:text-white">{worker.active_tasks}</dd>
                <dt className="text-gray-500 dark:text-gray-400">Processed</dt>
                <dd className="text-gray-900 dark:text-white">{worker.processed_tasks.toLocaleString()}</dd>
                <dt className="text-gray-500 dark:text-gray-400">Failed</dt>
                <dd className="text-red-600 dark:text-red-400">{worker.failed_tasks.toLocaleString()}</dd>
                <dt className="text-gray-500 dark:text-gray-400">Success Rate</dt>
                <dd className="text-gray-900 dark:text-white">
                  {worker.processed_tasks + worker.failed_tasks > 0
                    ? `${((worker.processed_tasks / (worker.processed_tasks + worker.failed_tasks)) * 100).toFixed(1)}%`
                    : '100%'}
                </dd>
                <dt className="text-gray-500 dark:text-gray-400">Queues</dt>
                <dd>
                  <div className="flex flex-wrap gap-1">
                    {worker.queues.map((q: string) => (
                      <span key={q} className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                        {q}
                      </span>
                    ))}
                  </div>
                </dd>
                <dt className="text-gray-500 dark:text-gray-400">Last Heartbeat</dt>
                <dd className="text-gray-900 dark:text-white">{formatRelativeTime(worker.last_heartbeat)}</dd>
              </div>
            </dl>
          </div>

          {worker.metadata && Object.keys(worker.metadata).length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Metadata</h3>
              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg text-sm overflow-auto max-h-48">
                {JSON.stringify(worker.metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Need to import icons
import { XIcon, EyeIcon } from '@/components/ui/icons';