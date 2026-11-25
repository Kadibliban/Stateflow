/**
 * Workflow Editor Toolbar
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import {
  SaveIcon,
  UndoIcon,
  RedoIcon,
  ZoomInIcon,
  ZoomOutIcon,
  MaximizeIcon,
  MinimizeIcon,
  CheckIcon,
  AlertCircleIcon,
  PlusIcon,
  GitBranchIcon,
  ChevronDownIcon,
} from '@/components/ui/icons';
import { WorkflowVersion } from '@/types';

interface ToolbarProps {
  onSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  onCreateVersion: () => void;
  saved: boolean;
  dirty: boolean;
  isLoading: boolean;
  versions: WorkflowVersion[];
  selectedVersion: number;
  onVersionChange: (version: number) => void;
}

export function Toolbar({
  onSave,
  onUndo,
  onRedo,
  onZoomIn,
  onZoomOut,
  onFitView,
  onCreateVersion,
  saved,
  dirty,
  isLoading,
  versions,
  selectedVersion,
  onVersionChange,
}: ToolbarProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
      {/* Left: File actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onSave}
          disabled={saved || !dirty || isLoading}
          className={cn(
            'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            saved || !dirty || isLoading
              ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
              : 'bg-primary-500 text-white hover:bg-primary-600'
          )}
        >
          <SaveIcon className="w-4 h-4" />
          {isLoading ? 'Saving...' : saved ? 'Saved' : 'Save'}
        </button>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-2" />

        <button
          onClick={onUndo}
          disabled={true} // TODO: implement undo stack
          className={cn(
            'p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors',
            'opacity-50 cursor-not-allowed'
          )}
        >
          <UndoIcon className="w-4 h-4" />
        </button>

        <button
          onClick={onRedo}
          disabled={true} // TODO: implement redo stack
          className={cn(
            'p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors',
            'opacity-50 cursor-not-allowed'
          )}
        >
          <RedoIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Center: Version selector & Status */}
      <div className="flex items-center gap-4">
        {/* Version Selector */}
        <div className="relative">
          <button
            onClick={() => {}}
            className="inline-flex items-center gap-2 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            aria-label="Select version"
          >
            <GitBranchIcon className="w-4 h-4" />
            <span>v{selectedVersion}</span>
            <ChevronDownIcon className="w-4 h-4" />
          </button>
          {/* Version dropdown would go here - simplified for now */}
        </div>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-2" />

        <div className={cn(
          'inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium',
          dirty
            ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
            : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
        )}>
          {dirty ? (
            <>
              <AlertCircleIcon className="w-4 h-4" />
              Unsaved changes
            </>
          ) : (
            <>
              <CheckIcon className="w-4 h-4" />
              All changes saved
            </>
          )}
        </div>
      </div>

      {/* Right: View controls & Create Version */}
      <div className="flex items-center gap-2">
        <button
          onClick={onCreateVersion}
          disabled={isLoading}
          className={cn(
            'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            'bg-blue-500 text-white hover:bg-blue-600'
          )}
          aria-label="Create new version"
        >
          <PlusIcon className="w-4 h-4" />
          New Version
        </button>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-2" />

        <button
          onClick={onZoomOut}
          className="p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Zoom out"
        >
          <ZoomOutIcon className="w-4 h-4" />
        </button>

        <button
          onClick={onFitView}
          className="p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Fit view"
        >
          <MaximizeIcon className="w-4 h-4" />
        </button>

        <button
          onClick={onZoomIn}
          className="p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Zoom in"
        >
          <ZoomInIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}