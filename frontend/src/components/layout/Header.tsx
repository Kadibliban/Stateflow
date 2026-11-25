/**
 * Header Component
 */

'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore, useOrganizationStore, useUIStore } from '@/lib/stores';
import { Sidebar } from './Sidebar';

export function Header() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const { currentOrganization } = useOrganizationStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  const pageTitle = getPageTitle(pathname);

  return (
    <header
      className={cn(
        'fixed top-0 right-0 h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 z-40 transition-all duration-300',
        sidebarOpen ? 'left-64' : 'left-20'
      )}
      role="banner"
    >
      <div className="flex items-center justify-between h-full px-4 sm:px-6">
        {/* Left side - Mobile menu button and page title */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="lg:hidden p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            <MenuIcon className="w-6 h-6" aria-hidden="true" />
          </button>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white hidden sm:block">
            {pageTitle}
          </h1>
        </div>

        {/* Right side - Organization selector and user menu */}
        <div className="flex items-center gap-4">
          {/* Organization Selector */}
          <OrganizationSelector />

          {/* Notifications */}
          <button
            className="relative p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Notifications"
          >
            <BellIcon className="w-5 h-5" aria-hidden="true" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" aria-hidden="true" />
          </button>

          {/* User Menu */}
          <UserMenu user={user} />
        </div>
      </div>
    </header>
  );
}

function getPageTitle(pathname: string): string {
  const titles: Record<string, string> = {
    '/dashboard': 'Dashboard',
    '/workflows': 'Workflows',
    '/workflows/new': 'New Workflow',
    '/executions': 'Executions',
    '/workers': 'Workers',
    '/settings': 'Settings',
  };

  // Check for dynamic routes
  for (const [path, title] of Object.entries(titles)) {
    if (pathname === path || pathname.startsWith(`${path}/`)) {
      return title;
    }
  }

  return 'StateFlow';
}

function OrganizationSelector() {
  const { currentOrganization, organizations, setCurrentOrganization } = useOrganizationStore();

  if (organizations.length === 0) return null;

  return (
    <div className="relative hidden sm:block">
      <button
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
        aria-haspopup="true"
        aria-expanded="false"
      >
        <BuildingIcon className="w-4 h-4" aria-hidden="true" />
        <span className="truncate max-w-[150px]">{currentOrganization?.name || 'Select Organization'}</span>
        <ChevronDownIcon className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );
}

function UserMenu({ user }: { user: any }) {
  return (
    <div className="relative">
      <button
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
        aria-haspopup="true"
        aria-expanded="false"
      >
        <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center text-white font-medium">
          {user?.full_name?.[0] || user?.email?.[0] || 'U'}
        </div>
        <span className="hidden md:block text-sm font-medium text-gray-700 dark:text-gray-300 max-w-[120px] truncate">
          {user?.full_name || user?.username}
        </span>
        <ChevronDownIcon className="w-4 h-4 text-gray-500" aria-hidden="true" />
      </button>
    </div>
  );
}

// Icons
function MenuIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function BellIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0018 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}

function BuildingIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}