/**
 * Workflow Version Selector Component
 * Dropdown for selecting workflow version in the editor
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDownIcon, ChevronUpIcon, GitBranchIcon, CheckIcon } from '@/components/ui/icons';
import { WorkflowVersion } from '@/types';

interface VersionSelectorProps {
  versions: WorkflowVersion[];
  selectedVersion: number;
  onVersionChange: (version: number) => void;
  disabled?: boolean;
  className?: string;
}

export function VersionSelector({
  versions,
  selectedVersion,
  onVersionChange,
  disabled = false,
  className,
}: VersionSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const sortedVersions = [...versions].sort((a, b) => b.version_number - a.version_number);

  return (
    <div className={cn('relative', className)} ref={dropdownRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled || versions.length === 0}
        className={cn(
          'inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-sm font-medium transition-colors',
          disabled || versions.length === 0
            ? 'border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
            : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
        )}
        aria-label="Select workflow version"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <GitBranchIcon className="w-4 h-4" />
        <span>v{selectedVersion}</span>
        {isOpen ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
      </button>

      {isOpen && versions.length > 0 && (
        <div
          className="absolute right-0 top-full mt-1 z-50 w-56 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden"
          role="listbox"
          aria-label="Workflow versions"
        >
          {sortedVersions.map((version) => (
            <button
              key={version.id}
              onClick={() => {
                onVersionChange(version.version_number);
                setIsOpen(false);
              }}
              className={cn(
                'w-full px-3 py-2 text-left text-sm transition-colors',
                version.version_number === selectedVersion
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
              )}
              role="option"
              aria-selected={version.version_number === selectedVersion}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-gray-500 dark:text-gray-400">
                    v{version.version_number}
                  </span>
                  {version.version_number === selectedVersion && (
                    <CheckIcon className="w-4 h-4 text-primary-500" />
                  )}
                </div>
                {version.changelog && (
                  <span className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                    {version.changelog}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-1">
                <span>{version.steps?.length || 0} steps</span>
                <span>•</span>
                <span>{new Date(version.created_at).toLocaleDateString()}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {versions.length === 0 && (
        <div className="absolute right-0 top-full mt-1 z-50 w-56 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
            No versions available
          </p>
        </div>
      )}
    </div>
  );
}