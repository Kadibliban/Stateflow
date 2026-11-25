/**
 * Node Palette for Workflow Editor
 * Draggable node types for the workflow canvas
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import {
  ZapIcon,
  GitBranchIcon,
  SettingsIcon,
  ClockIcon,
  RotateCcwIcon,
  PlayIcon,
  StopIcon,
} from '../ui/icons';

interface NodePaletteProps {
  onDragStart: (nodeType: string, nodeData: any) => void;
}

const nodeTypes = [
  {
    type: 'action',
    label: 'Action',
    description: 'Execute a task or service call',
    icon: ZapIcon,
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    defaultData: {
      label: 'New Action',
      type: 'action',
      handler: '',
      config: {},
      timeout_seconds: 300,
      is_critical: true,
      continue_on_failure: false,
    },
  },
  {
    type: 'condition',
    label: 'Condition',
    description: 'Branch based on a condition',
    icon: GitBranchIcon,
    color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    defaultData: {
      label: 'New Condition',
      type: 'condition',
      handler: '',
      config: {},
      timeout_seconds: 60,
      is_critical: true,
      continue_on_failure: false,
    },
  },
  {
    type: 'parallel',
    label: 'Parallel',
    description: 'Execute multiple steps in parallel',
    icon: SettingsIcon,
    color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
    defaultData: {
      label: 'New Parallel',
      type: 'parallel',
      handler: '',
      config: {},
      timeout_seconds: 300,
      is_critical: true,
      continue_on_failure: false,
    },
  },
  {
    type: 'delay',
    label: 'Delay',
    description: 'Wait for a specified duration',
    icon: ClockIcon,
    color: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    defaultData: {
      label: 'New Delay',
      type: 'delay',
      handler: '',
      config: { duration_seconds: 60 },
      timeout_seconds: 3600,
      is_critical: false,
      continue_on_failure: true,
    },
  },
  {
    type: 'compensation',
    label: 'Compensation',
    description: 'Define rollback logic for a step',
    icon: RotateCcwIcon,
    color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    defaultData: {
      label: 'New Compensation',
      type: 'compensation',
      handler: '',
      config: {},
      timeout_seconds: 300,
      is_critical: true,
      continue_on_failure: false,
    },
  },
];

export function NodePalette({ onDragStart }: NodePaletteProps) {
  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 space-y-4">
      {/* Start/End Nodes */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 px-2">
          Flow Control
        </h3>
        <div className="space-y-2">
          <DraggableNodeItem
            type="start"
            label="Start"
            description="Workflow entry point"
            icon={PlayIcon}
            color="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
            defaultData={{
              label: 'Start',
              type: 'start',
            }}
            onDragStart={onDragStart}
          />
          <DraggableNodeItem
            type="end"
            label="End"
            description="Workflow exit point"
            icon={StopIcon}
            color="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
            defaultData={{
              label: 'End',
              type: 'end',
            }}
            onDragStart={onDragStart}
          />
        </div>
      </div>

      <div className="pt-4 border-t border-gray-200 dark:border-gray-800">
        <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 px-2">
          Step Types
        </h3>
        <div className="space-y-2">
          {nodeTypes.map((nodeType) => (
            <DraggableNodeItem
              key={nodeType.type}
              type={nodeType.type}
              label={nodeType.label}
              description={nodeType.description}
              icon={nodeType.icon}
              color={nodeType.color}
              defaultData={nodeType.defaultData}
              onDragStart={onDragStart}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface DraggableNodeItemProps {
  type: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  defaultData: any;
  onDragStart: (nodeType: string, nodeData: any) => void;
}

function DraggableNodeItem({
  type,
  label,
  description,
  icon: Icon,
  color,
  defaultData,
  onDragStart,
}: DraggableNodeItemProps) {
  const [isDragging, setIsDragging] = React.useState(false);

  const handleDragStart = (e: React.DragEvent) => {
    setIsDragging(true);
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('application/reactflow', JSON.stringify({ type, ...defaultData }));
    onDragStart(type, defaultData);
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 cursor-grab active:cursor-grabbing',
        'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900',
        'hover:border-primary-300 dark:hover:border-primary-700 hover:shadow-md',
        isDragging && 'opacity-50 rotate-2 scale-105'
      )}
      role="button"
      tabIndex={0}
      aria-label={`Add ${label} node`}
    >
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', color)}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 dark:text-white truncate">{label}</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{description}</p>
      </div>
    </div>
  );
}