/**
 * New Workflow Page
 */

'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { cn } from '@/lib/utils';
import {
  ChevronLeftIcon,
  PlusIcon,
  ZapIcon,
  GitBranchIcon,
  SettingsIcon,
  ClockIcon,
  RotateCcwIcon,
} from '@/components/ui/icons';

export default function NewWorkflowPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { currentOrganization, setCurrentOrganization, organizations } = useOrganizationStore();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    tags: '' as string,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch organizations
  const { data: orgsData, isLoading: orgsLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Auto-select first organization if none selected
  useEffect(() => {
    if (orgsData && organizations.length === 0 && !currentOrganization && orgsData.length > 0) {
      setCurrentOrganization(orgsData[0]);
    }
  }, [orgsData, currentOrganization, organizations.length, setCurrentOrganization]);

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; tags?: string[] }) =>
      apiClient.createWorkflow(currentOrganization!.id, data),
    onSuccess: (workflow) => {
      router.push(`/workflows/${workflow.id}`);
    },
    onError: (error: any) => {
      let message = 'Failed to create workflow';
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        // Handle FastAPI validation errors (array of error objects)
        if (Array.isArray(detail)) {
          message = detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ');
        } else if (typeof detail === 'string') {
          message = detail;
        } else if (detail.msg) {
          message = detail.msg;
        }
      }
      setErrors({ submit: message });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    // Validation
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    if (formData.name.length > 255) {
      newErrors.name = 'Name must be less than 255 characters';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    createMutation.mutate({
      name: formData.name.trim(),
      description: formData.description.trim() || undefined,
      tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
    });
  };

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Please sign in</h1>
        </div>
      </MainLayout>
    );
  }

  if (orgsLoading) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mx-auto" />
        </div>
      </MainLayout>
    );
  }

  if (!currentOrganization) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">No Organization Selected</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">Create or select an organization to get started</p>
          <Link href="/settings" className="inline-flex items-center px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600">
            Manage Organizations
          </Link>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <ChevronLeftIcon className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">New Workflow</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Create a new workflow definition</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-6">
          {/* Basic Info */}
          <fieldset>
            <legend className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Basic Information</legend>
            <div className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  placeholder="e.g., Order Processing Workflow"
                  className={cn(
                    'w-full px-3 py-2 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500',
                    errors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                  )}
                  maxLength={255}
                  required
                />
                {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
              </div>

              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  placeholder="Describe what this workflow does..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div>
                <label htmlFor="tags" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Tags (comma-separated)
                </label>
                <input
                  id="tags"
                  type="text"
                  value={formData.tags}
                  onChange={(e) => handleChange('tags', e.target.value)}
                  placeholder="e.g., order, payment, fulfillment"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Separate tags with commas</p>
              </div>
            </div>
          </fieldset>

          {/* Step Type Preview */}
          <fieldset>
            <legend className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Available Step Types</legend>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              After creating the workflow, you can add steps of these types in the visual editor.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <StepTypeCard icon={ZapIcon} color="blue" title="Action" description="Execute a task or service call" />
              <StepTypeCard icon={GitBranchIcon} color="purple" title="Condition" description="Branch based on a condition" />
              <StepTypeCard icon={SettingsIcon} color="orange" title="Parallel" description="Execute multiple steps in parallel" />
              <StepTypeCard icon={ClockIcon} color="gray" title="Delay" description="Wait for a specified duration" />
              <StepTypeCard icon={RotateCcwIcon} color="red" title="Compensation" description="Define rollback logic for a step" />
            </div>
          </fieldset>

          {/* Error Message */}
          {errors.submit && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400">
              {errors.submit}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-800">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Creating...
                </>
              ) : (
                <>
                  <PlusIcon className="w-4 h-4" />
                  Create Workflow
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </MainLayout>
  );
}

function StepTypeCard({ icon: Icon, color, title, description }: { icon: React.ComponentType<{ className?: string }>; color: string; title: string; description: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    orange: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
    gray: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    red: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  };

  return (
    <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-300 dark:hover:border-primary-700 transition-colors">
      <div className="flex items-center gap-3">
        <div className={cn('p-2 rounded-lg', colors[color] || colors.blue)}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-medium text-gray-900 dark:text-white">{title}</h4>
          <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
        </div>
      </div>
    </div>
  );
}