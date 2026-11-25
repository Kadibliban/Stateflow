/**
 * Workflow Editor Side Panel
 * Shows node configuration when a node is selected
 */

'use client';

import React from 'react';
import { Node } from 'reactflow';
import { cn } from '@/lib/utils';
import { XIcon, SaveIcon, TrashIcon, CopyIcon } from '../ui/icons';

interface SidePanelProps {
  node: Node | null;
  onClose: () => void;
  onUpdate: (data: any) => void;
}

export function SidePanel({ node, onClose, onUpdate }: SidePanelProps) {
  if (!node) return null;

  const [formData, setFormData] = React.useState({
    label: node.data.label || '',
    description: node.data.description || '',
    type: node.data.type || 'action',
    handler: node.data.handler || '',
    timeout_seconds: node.data.timeout_seconds || 300,
    is_critical: node.data.is_critical ?? true,
    continue_on_failure: node.data.continue_on_failure ?? false,
    config: JSON.stringify(node.data.config || {}, null, 2),
    compensation_handler: node.data.compensation_handler || '',
    compensation_config: JSON.stringify(node.data.compensation_config || {}, null, 2),
  });

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    onUpdate(formData);
    onClose();
  };

  const handleDelete = () => {
    if (confirm('Are you sure you want to delete this node?')) {
      // The parent will handle deletion via the store
      onClose();
    }
  };

  const nodeTypes = [
    { value: 'action', label: 'Action', icon: '⚡' },
    { value: 'condition', label: 'Condition', icon: '⟳' },
    { value: 'parallel', label: 'Parallel', icon: '⚙' },
    { value: 'delay', label: 'Delay', icon: '⏱' },
    { value: 'compensation', label: 'Compensation', icon: '↺' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-labelledby="panel-title">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="w-96 max-w-full bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
          <h2 id="panel-title" className="text-lg font-semibold text-gray-900 dark:text-white">
            Configure Node
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Close panel"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="flex-1 p-4 space-y-6 overflow-y-auto">
          {/* Basic Info */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-medium text-gray-900 dark:text-white">Basic Information</legend>

            <div>
              <label htmlFor="label" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Name *
              </label>
              <input
                id="label"
                type="text"
                value={formData.label}
                onChange={(e) => handleChange('label', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description
              </label>
              <textarea
                id="description"
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label htmlFor="type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Step Type
              </label>
              <select
                id="type"
                value={formData.type}
                onChange={(e) => handleChange('type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {nodeTypes.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.icon} {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="handler" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Handler *
              </label>
              <input
                id="handler"
                type="text"
                value={formData.handler}
                onChange={(e) => handleChange('handler', e.target.value)}
                placeholder="e.g., my_service.process_payment"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
          </fieldset>

          {/* Timeout & Retry */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-medium text-gray-900 dark:text-white">Execution Settings</legend>

            <div>
              <label htmlFor="timeout" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Timeout (seconds)
              </label>
              <input
                id="timeout"
                type="number"
                min="1"
                max="3600"
                value={formData.timeout_seconds}
                onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value) || 300)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_critical}
                  onChange={(e) => handleChange('is_critical', e.target.checked)}
                  className="w-4 h-4 text-primary-500 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Critical step</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.continue_on_failure}
                  onChange={(e) => handleChange('continue_on_failure', e.target.checked)}
                  className="w-4 h-4 text-primary-500 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Continue on failure</span>
              </label>
            </div>
          </fieldset>

          {/* Config */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-medium text-gray-900 dark:text-white">Configuration (JSON)</legend>
            <textarea
              value={formData.config}
              onChange={(e) => handleChange('config', e.target.value)}
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm"
              placeholder='{"key": "value"}'
            />
          </fieldset>

          {/* Compensation */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-medium text-gray-900 dark:text-white">Compensation</legend>

            <div>
              <label htmlFor="compensation_handler" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Compensation Handler
              </label>
              <input
                id="compensation_handler"
                type="text"
                value={formData.compensation_handler}
                onChange={(e) => handleChange('compensation_handler', e.target.value)}
                placeholder="e.g., my_service.refund_payment"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label htmlFor="compensation_config" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Compensation Config (JSON)
              </label>
              <textarea
                id="compensation_config"
                value={formData.compensation_config}
                onChange={(e) => handleChange('compensation_config', e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                placeholder='{"key": "value"}'
              />
            </div>
          </fieldset>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-800">
            <button
              type="button"
              onClick={handleDelete}
              className="flex items-center gap-2 px-3 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
            >
              <TrashIcon className="w-4 h-4" />
              Delete
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              <SaveIcon className="w-4 h-4" />
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

