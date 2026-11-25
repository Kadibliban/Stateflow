/**
 * Custom React Flow Node Components
 */

'use client';

import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { cn, getStepTypeColor } from '@/lib/utils';
import {
  PlayIcon,
  StopIcon,
  ZapIcon,
  GitBranchIcon,
  ClockIcon,
  RotateCcwIcon,
  SettingsIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  TrashIcon,
  CopyIcon,
} from '@/components/ui/icons';

// Base node wrapper with common styling
function NodeWrapper({
  children,
  isConnectable = true,
  className,
}: {
  children: React.ReactNode;
  isConnectable?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'workflow-node relative',
        'border-2 transition-all duration-200',
        isConnectable ? 'border-gray-200 dark:border-gray-700' : 'border-transparent',
        className
      )}
    >
      {children}
    </div>
  );
}

// Main Workflow Node
interface WorkflowNodeData {
  label: string;
  description?: string;
  type: string;
  handler: string;
  config?: Record<string, any>;
  timeout_seconds?: number;
  retry_policy_id?: string;
  compensation_handler?: string;
  compensation_config?: Record<string, any>;
  depends_on?: string[];
  is_critical?: boolean;
  continue_on_failure?: boolean;
  status?: string;
  isConnectable?: boolean;
}

export function WorkflowNode({ data, selected, id }: NodeProps<WorkflowNodeData>) {
  const { label, description, type, status = 'pending', isConnectable = true } = data;
  const [expanded, setExpanded] = React.useState(false);

  const typeIcon = getTypeIcon(type);
  const typeColor = getStepTypeColor(type);

  return (
    <NodeWrapper isConnectable={isConnectable} className={selected ? 'border-primary-500 shadow-lg' : ''}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={cn('workflow-node-type', type)}>
            {typeIcon}
          </div>
          <span className="workflow-node-label font-medium text-gray-900 dark:text-white truncate max-w-[140px]">
            {label}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className={cn('workflow-node-status', status)}>
            {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
            aria-label={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Description */}
      {description && (
        <p className="workflow-node-description mb-2">{description}</p>
      )}

      {/* Handler info */}
      <div className="workflow-node-content text-xs text-gray-500 dark:text-gray-400 space-y-1">
        <div className="flex items-center gap-1">
          <SettingsIcon className="w-3 h-3" />
          <span className="truncate max-w-[180px]">{data.handler}</span>
        </div>
        {data.timeout_seconds && (
          <div className="flex items-center gap-1">
            <ClockIcon className="w-3 h-3" />
            <span>Timeout: {data.timeout_seconds}s</span>
          </div>
        )}
        {data.retry_policy_id && (
          <div className="flex items-center gap-1">
            <RotateCcwIcon className="w-3 h-3" />
            <span>Retry policy attached</span>
          </div>
        )}
        {data.compensation_handler && (
          <div className="flex items-center gap-1">
            <RotateCcwIcon className="w-3 h-3" />
            <span>Compensation: {data.compensation_handler}</span>
          </div>
        )}
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 space-y-2 text-xs">
          {data.config && Object.keys(data.config).length > 0 && (
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300 mb-1">Config:</p>
              <pre className="bg-gray-100 dark:bg-gray-800 p-2 rounded text-[10px] overflow-auto max-h-24">
                {JSON.stringify(data.config, null, 2)}
              </pre>
            </div>
          )}
          {data.depends_on && data.depends_on.length > 0 && (
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300 mb-1">Dependencies:</p>
              <div className="flex flex-wrap gap-1">
                {data.depends_on.map((dep) => (
                  <span key={dep} className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300">
                    {dep}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <span className={cn('px-1.5 py-0.5 rounded', data.is_critical ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300')}>
              {data.is_critical ? 'Critical' : 'Non-critical'}
            </span>
            <span className={cn('px-1.5 py-0.5 rounded', data.continue_on_failure ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300')}>
              {data.continue_on_failure ? 'Continue on failure' : 'Stop on failure'}
            </span>
          </div>
        </div>
      )}

      {/* Handles */}
      {isConnectable && (
        <>
          <Handle
            type="target"
            position={Position.Left}
            className="w-3 h-3 bg-primary-500 border-2 border-white dark:border-gray-900"
            id="input"
          />
          <Handle
            type="source"
            position={Position.Right}
            className="w-3 h-3 bg-primary-500 border-2 border-white dark:border-gray-900"
            id="output"
          />
        </>
      )}
    </NodeWrapper>
  );
}

// Start Node (Entry Point)
interface StartNodeData {
  label: string;
}

export function StartNode({ data }: NodeProps<StartNodeData>) {
  return (
    <NodeWrapper isConnectable={false} className="bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700">
      <div className="flex items-center justify-center gap-2 p-3">
        <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
          <PlayIcon className="w-5 h-5 text-white" />
        </div>
        <span className="font-semibold text-green-800 dark:text-green-200">{data.label || 'Start'}</span>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-green-500 border-2 border-white dark:border-gray-900"
        id="output"
      />
    </NodeWrapper>
  );
}

// End Node (Exit Point)
interface EndNodeData {
  label: string;
}

export function EndNode({ data }: NodeProps<EndNodeData>) {
  return (
    <NodeWrapper isConnectable={false} className="bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700">
      <div className="flex items-center justify-center gap-2 p-3">
        <span className="font-semibold text-red-800 dark:text-red-200">{data.label || 'End'}</span>
        <div className="w-8 h-8 rounded-full bg-red-500 flex items-center justify-center">
          <StopIcon className="w-5 h-5 text-white" />
        </div>
      </div>
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-red-500 border-2 border-white dark:border-gray-900"
        id="input"
      />
    </NodeWrapper>
  );
}

// Helper function to get icon for step type
function getTypeIcon(type: string) {
  switch (type) {
    case 'action':
      return <ZapIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
    case 'condition':
      return <GitBranchIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />;
    case 'parallel':
      return <SettingsIcon className="w-4 h-4 text-orange-600 dark:text-orange-400" />;
    case 'delay':
      return <ClockIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />;
    case 'compensation':
      return <RotateCcwIcon className="w-4 h-4 text-red-600 dark:text-red-400" />;
    default:
      return <ZapIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />;
  }
}