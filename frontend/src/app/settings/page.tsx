/**
 * Settings Page
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAuthStore, useOrganizationStore } from '@/lib/stores';
import { MainLayout } from '@/components/layout/MainLayout';
import { formatRelativeTime, cn } from '@/lib/utils';
import {
  SettingsIcon,
  BuildingIcon,
  UserIcon,
  KeyIcon,
  BellIcon,
  PlusIcon,
  EditIcon,
  TrashIcon,
  ChevronRightIcon,
  CheckIcon,
  XIcon,
  MailIcon,
  ShieldIcon,
  AlertTriangleIcon,
  ArrowRightIcon,
  AlertCircleIcon,
  CheckCircleIcon,
} from '@/components/ui/icons';
import { MemberRole } from '@/types';

export default function SettingsPage() {
  const { user, isAuthenticated, updateUser, clearAuth } = useAuthStore();
  const { currentOrganization, organizations, setCurrentOrganization, setOrganizations } = useOrganizationStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'profile' | 'organizations' | 'security' | 'notifications'>('profile');
  const [orgForm, setOrgForm] = useState({ name: '', slug: '', description: '' });
  const [inviteForm, setInviteForm] = useState({ email: '', role_name: MemberRole.DEVELOPER });

  // Fetch organizations
  const { data: orgsData, refetch: refetchOrgs } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.getOrganizations(),
    enabled: isAuthenticated,
  });

  // Create organization mutation
  const [createOrgError, setCreateOrgError] = useState<string | null>(null);
  const createOrgMutation = useMutation({
    mutationFn: (data: { name: string; slug: string; description?: string }) => apiClient.createOrganization(data),
    onSuccess: () => {
      refetchOrgs();
      setOrgForm({ name: '', slug: '', description: '' });
      setCreateOrgError(null);
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || 'Failed to create organization';
      setCreateOrgError(message);
    },
  });

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: (data: { full_name?: string; email?: string }) => apiClient.patch('/users/me', data) as Promise<{ full_name?: string; email?: string }>,
    onSuccess: (updatedUser: { full_name?: string; email?: string }) => {
      updateUser(updatedUser);
    },
  });

  // Update organization mutation
  const updateOrgMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => apiClient.updateOrganization(id, data),
    onSuccess: (org) => {
      if (currentOrganization?.id === org.id) {
        setCurrentOrganization(org);
      }
      refetchOrgs();
    },
  });

  // Invite member mutation
  const [inviteError, setInviteError] = useState<string | null>(null);
  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; role_name: MemberRole }) => apiClient.inviteMember(currentOrganization!.id, data),
    onSuccess: () => {
      refetchOrgs();
      setInviteForm({ email: '', role_name: MemberRole.DEVELOPER });
      setInviteError(null);
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || 'Failed to invite member';
      setInviteError(message);
    },
  });

  // Update member role mutation
  const updateRoleMutation = useMutation({
    mutationFn: ({ memberId, roleName }: { memberId: string; roleName: string }) =>
      apiClient.updateMemberRole(currentOrganization!.id, memberId, roleName),
    onSuccess: () => refetchOrgs(),
  });

  // Remove member mutation
  const removeMemberMutation = useMutation({
    mutationFn: (memberId: string) => apiClient.removeMember(currentOrganization!.id, memberId),
    onSuccess: () => refetchOrgs(),
  });

  // Update stores
  React.useEffect(() => {
    if (orgsData && organizations.length === 0) {
      setOrganizations(orgsData);
      if (!currentOrganization && orgsData.length > 0) {
        setCurrentOrganization(orgsData[0]);
      }
    }
  }, [orgsData, organizations.length, currentOrganization, setOrganizations, setCurrentOrganization]);

  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Please sign in</h1>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Manage your account and organization settings</p>
        </div>

        {/* Tabs */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div className="border-b border-gray-200 dark:border-gray-800 p-6">
            <nav className="flex gap-6" aria-label="Settings tabs">
              <TabButton active={activeTab === 'profile'} onClick={() => setActiveTab('profile')}>
                <UserIcon className="w-4 h-4 inline mr-2" />
                Profile
              </TabButton>
              <TabButton active={activeTab === 'organizations'} onClick={() => setActiveTab('organizations')}>
                <BuildingIcon className="w-4 h-4 inline mr-2" />
                Organizations
              </TabButton>
              <TabButton active={activeTab === 'security'} onClick={() => setActiveTab('security')}>
                <ShieldIcon className="w-4 h-4 inline mr-2" />
                Security
              </TabButton>
              <TabButton active={activeTab === 'notifications'} onClick={() => setActiveTab('notifications')}>
                <BellIcon className="w-4 h-4 inline mr-2" />
                Notifications
              </TabButton>
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'profile' && <ProfileTab user={user} onUpdate={updateProfileMutation.mutate} isLoading={updateProfileMutation.isPending} />}
            {activeTab === 'organizations' && <OrganizationsTab
              organizations={organizations}
              currentOrganization={currentOrganization}
              orgForm={orgForm}
              setOrgForm={setOrgForm}
              inviteForm={inviteForm}
              setInviteForm={setInviteForm}
              onCreateOrg={createOrgMutation.mutate}
              onUpdateOrg={updateOrgMutation.mutate}
              onInvite={inviteMutation.mutate}
              onUpdateRole={updateRoleMutation.mutate}
              onRemoveMember={removeMemberMutation.mutate}
              onSwitchOrg={setCurrentOrganization}
              isCreating={createOrgMutation.isPending}
              isInviting={inviteMutation.isPending}
              createOrgError={createOrgError}
              inviteError={inviteError}
            />}
            {activeTab === 'security' && <SecurityTab />}
            {activeTab === 'notifications' && <NotificationsTab />}
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-red-200 dark:border-red-800 p-6">
          <h2 className="text-lg font-semibold text-red-600 dark:text-red-400 mb-4 flex items-center gap-2">
            <AlertTriangleIcon className="w-5 h-5" />
            Danger Zone
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Irreversible actions. Please be careful.
          </p>
          <button
            onClick={() => {
              if (confirm('Are you sure you want to sign out?')) {
                clearAuth();
                apiClient.clearTokens();
              }
            }}
            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
          >
            Sign Out
          </button>
        </div>
      </div>
    </MainLayout>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'py-2 px-1 border-b-2 font-medium text-sm transition-colors flex items-center',
        active
          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
          : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
      )}
    >
      {children}
    </button>
  );
}

function ProfileTab({ user, onUpdate, isLoading }: { user: any; onUpdate: (data: any) => void; isLoading: boolean }) {
  const [formData, setFormData] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-md">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Full Name</label>
        <input
          type="text"
          value={formData.full_name}
          onChange={(e) => setFormData(prev => ({ ...prev, full_name: e.target.value }))}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
        <input
          type="email"
          value={formData.email}
          onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
        <input
          type="text"
          value={user?.username || ''}
          disabled
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">User ID</label>
        <input
          type="text"
          value={user?.id || ''}
          disabled
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-sm"
        />
      </div>
      <button
        type="submit"
        disabled={isLoading}
        className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
      >
        {isLoading ? 'Saving...' : 'Save Changes'}
      </button>
    </form>
  );
}

function OrganizationsTab({
  organizations,
  currentOrganization,
  orgForm,
  setOrgForm,
  inviteForm,
  setInviteForm,
  onCreateOrg,
  onUpdateOrg,
  onInvite,
  onUpdateRole,
  onRemoveMember,
  onSwitchOrg,
  isCreating,
  isInviting,
  createOrgError,
  inviteError,
}: any) {
  const [editingOrgId, setEditingOrgId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', description: '' });
  const [members, setMembers] = useState<any[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);

  const handleCreateOrg = (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgForm.name.trim() || !orgForm.slug.trim()) return;
    onCreateOrg(orgForm);
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteForm.email.trim()) return;
    onInvite(inviteForm);
  };

  const handleEditOrg = (org: any) => {
    setEditingOrgId(org.id);
    setEditForm({ name: org.name, description: org.description || '' });
  };

  const handleSaveEdit = (org: any) => {
    onUpdateOrg({ id: org.id, data: editForm });
    setEditingOrgId(null);
  };

  const handleCancelEdit = () => {
    setEditingOrgId(null);
  };

  const handleSwitchOrg = (orgId: string) => {
    onSwitchOrg(orgId);
  };

  const loadMembers = async () => {
    if (!currentOrganization) return;
    setLoadingMembers(true);
    try {
      const data = await apiClient.getOrganizationMembers(currentOrganization.id);
      setMembers(data);
    } catch (err) {
      console.error('Failed to load members:', err);
    } finally {
      setLoadingMembers(false);
    }
  };

  const handleUpdateRole = async (memberId: string, roleName: string) => {
    if (!currentOrganization) return;
    try {
      await onUpdateRole({ memberId, roleName });
      loadMembers();
    } catch (err) {
      console.error('Failed to update role:', err);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    if (!currentOrganization) return;
    if (!confirm('Are you sure you want to remove this member?')) return;
    try {
      await onRemoveMember(memberId);
      loadMembers();
    } catch (err) {
      console.error('Failed to remove member:', err);
    }
  };

  // Load members when currentOrganization changes
  React.useEffect(() => {
    loadMembers();
  }, [currentOrganization?.id]);

  return (
    <div className="space-y-8">
      {/* Current Organization */}
      {currentOrganization && (
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
                <BuildingIcon className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">{currentOrganization.name}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{currentOrganization.slug}</p>
              </div>
            </div>
            {editingOrgId === currentOrganization.id ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white w-48"
                />
                <button onClick={() => handleSaveEdit(currentOrganization)} className="px-3 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 text-sm">Save</button>
                <button onClick={handleCancelEdit} className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm">Cancel</button>
              </div>
            ) : (
              <button onClick={() => handleEditOrg(currentOrganization)} className="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
                <EditIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Create New Organization */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <PlusIcon className="w-5 h-5" />
          Create Organization
        </h3>
        <form onSubmit={handleCreateOrg} className="space-y-4 max-w-md">
          {createOrgError && (
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 flex items-center gap-2">
              <AlertCircleIcon className="w-5 h-5" />
              <span className="text-sm">{createOrgError}</span>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
            <input
              type="text"
              value={orgForm.name}
              onChange={(e) => setOrgForm((prev: typeof orgForm) => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="My Organization"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Slug</label>
            <input
              type="text"
              value={orgForm.slug}
              onChange={(e) => setOrgForm((prev: typeof orgForm) => ({ ...prev, slug: e.target.value.toLowerCase().replace(/\s+/g, '-') }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="my-organization"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description (optional)</label>
            <textarea
              value={orgForm.description}
              onChange={(e) => setOrgForm((prev: typeof orgForm) => ({ ...prev, description: e.target.value }))}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <button type="submit" disabled={isCreating} className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50">
            {isCreating ? 'Creating...' : 'Create Organization'}
          </button>
        </form>
      </div>

      {/* Organization List */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Your Organizations</h3>
        <div className="space-y-3">
          {organizations.map((org: any) => (
            <div key={org.id} className={cn('p-4 border rounded-lg flex items-center justify-between', org.id === currentOrganization?.id ? 'border-primary-300 dark:border-primary-700 bg-primary-50 dark:bg-primary-900/20' : 'border-gray-200 dark:border-gray-700')}>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                  <BuildingIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white">{org.name}</h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{org.slug}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {org.id !== currentOrganization?.id && (
                  <button
                    onClick={() => handleSwitchOrg(org.id)}
                    className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-1"
                  >
                    <ArrowRightIcon className="w-3 h-3" />
                    Switch
                  </button>
                )} else {
                  <span className="px-3 py-1.5 text-sm bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-lg flex items-center gap-1">
                    <CheckIcon className="w-3 h-3" />
                    Active
                  </span>
                }
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Members */}
      {currentOrganization && (
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <UserIcon className="w-5 h-5" />
            Members
          </h3>
          <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-3 mb-6 max-w-md">
            {inviteError && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 flex items-center gap-2 w-full sm:w-auto">
                <AlertCircleIcon className="w-5 h-5" />
                <span className="text-sm">{inviteError}</span>
              </div>
            )}
            <input
              type="email"
              value={inviteForm.email}
              onChange={(e) => setInviteForm((prev: typeof inviteForm) => ({ ...prev, email: e.target.value }))}
              placeholder="Email address"
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <select
              value={inviteForm.role_name}
              onChange={(e) => setInviteForm((prev: typeof inviteForm) => ({ ...prev, role_name: e.target.value as MemberRole }))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="viewer">Viewer</option>
              <option value="developer">Developer</option>
              <option value="administrator">Administrator</option>
            </select>
            <button type="submit" disabled={isInviting} className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 whitespace-nowrap">
              {isInviting ? 'Inviting...' : 'Invite Member'}
            </button>
          </form>

          <div className="space-y-2">
            {loadingMembers ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mx-auto" />
              </div>
            ) : members.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-center py-8">No members yet. Invite your first member above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Member</th>
                      <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Role</th>
                      <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Status</th>
                      <th className="text-left p-3 font-medium text-gray-500 dark:text-gray-400">Joined</th>
                      <th className="text-right p-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((member: any) => (
                      <MemberRow
                        key={member.id}
                        member={member}
                        currentUserId={currentOrganization?.id} // placeholder, we'd need user id from auth
                        onUpdateRole={handleUpdateRole}
                        onRemove={handleRemoveMember}
                        isOwner={member.role_name === 'owner'}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MemberRow({ member, onUpdateRole, onRemove, isOwner }: any) {
  const [editingRole, setEditingRole] = useState(false);
  const [role, setRole] = useState(member.role_name);
  const [updating, setUpdating] = useState(false);

  const handleSaveRole = async () => {
    if (role === member.role_name) {
      setEditingRole(false);
      return;
    }
    setUpdating(true);
    try {
      await onUpdateRole(member.id, role);
    } finally {
      setUpdating(false);
      setEditingRole(false);
    }
  };

  const handleCancelRole = () => {
    setRole(member.role_name);
    setEditingRole(false);
  };

  return (
    <tr className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td className="p-3">
        <div className="flex items-center gap-3">
          <div className="p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
            <UserIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">
              {member.user?.full_name || member.user?.username || 'Unknown'}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">{member.user?.email}</p>
          </div>
        </div>
      </td>
      <td className="p-3">
        {editingRole ? (
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as MemberRole)}
            className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
          >
            <option value="viewer">Viewer</option>
            <option value="developer">Developer</option>
            <option value="administrator">Administrator</option>
            <option value="owner">Owner</option>
          </select>
        ) : (
          <span className={cn(
            'px-2 py-1 text-xs rounded-full font-medium',
            member.role_name === 'owner' && 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
            member.role_name === 'administrator' && 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
            member.role_name === 'developer' && 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
            member.role_name === 'viewer' && 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
          )}>
            {member.role_name}
          </span>
        )}
      </td>
      <td className="p-3">
        <span className={cn(
          'px-2 py-1 text-xs rounded-full',
          member.is_active
            ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
            : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
        )}>
          {member.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="p-3 text-sm text-gray-500 dark:text-gray-400">
        {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'N/A'}
      </td>
      <td className="p-3 text-right">
        <div className="flex items-center justify-end gap-1">
          {!isOwner && !editingRole && (
            <button
              onClick={() => setEditingRole(true)}
              className="p-1.5 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded hover:bg-gray-100 dark:hover:bg-gray-800"
              title="Edit role"
            >
              <EditIcon className="w-4 h-4" />
            </button>
          )}
          {editingRole && (
            <div className="flex gap-1">
              <button
                onClick={handleSaveRole}
                disabled={updating}
                className="p-1.5 text-green-500 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 rounded hover:bg-green-50 dark:hover:bg-green-900/20"
                title="Save"
              >
                <CheckIcon className="w-4 h-4" />
              </button>
              <button
                onClick={handleCancelRole}
                className="p-1.5 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Cancel"
              >
                <XIcon className="w-4 h-4" />
              </button>
            </div>
          )}
          {!isOwner && (
            <button
              onClick={() => onRemove(member.id)}
              disabled={updating}
              className="p-1.5 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
              title="Remove member"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function SecurityTab() {
  const { user, updateUser, clearAuth } = useAuthStore();
  const queryClient = useQueryClient();
  const router = useRouter();

  // Use user from auth store (populated from login response)
  const currentUser = user;

  // Password change state (UI only - backend endpoint not implemented yet)
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!passwordForm.current_password) {
      setPasswordError('Current password is required');
      return;
    }
    if (!passwordForm.new_password) {
      setPasswordError('New password is required');
      return;
    }
    if (passwordForm.new_password.length < 8) {
      setPasswordError('New password must be at least 8 characters');
      return;
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError('Passwords do not match');
      return;
    }

    // Backend endpoint not implemented yet
    setPasswordError('Password change not yet implemented. Use "Forgot Password" flow for now.');
    setTimeout(() => setPasswordError(null), 5000);
  };

  // Sessions management (refresh tokens)
  const [sessions, setSessions] = useState<any[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      // We can't directly fetch refresh tokens, but we can show the current session
      // In a real app, you'd have an endpoint for this
      const tokens = apiClient.getAccessToken();
      if (tokens) {
        setSessions([{ id: 'current', created_at: new Date().toISOString(), current: true }]);
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  };

  const revokeAllSessions = async () => {
    try {
      await apiClient.post('/auth/revoke-all', {});
      apiClient.clearTokens();
      clearAuth();
      loadSessions();
    } catch (err) {
      console.error('Failed to revoke sessions:', err);
    }
  };

  React.useEffect(() => {
    loadSessions();
  }, []);

  return (
    <div className="space-y-6">
      {/* Password */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <KeyIcon className="w-5 h-5" />
            Password
          </h3>
          {!showPasswordForm && (
            <button
              onClick={() => setShowPasswordForm(true)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Change Password
            </button>
          )}
        </div>

        {showPasswordForm && (
          <form onSubmit={handlePasswordChange} className="space-y-4 max-w-md">
            {passwordError && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 flex items-center gap-2">
                <AlertCircleIcon className="w-5 h-5" />
                <span className="text-sm">{passwordError}</span>
              </div>
            )}
            {passwordSuccess && (
              <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-600 dark:text-green-400 flex items-center gap-2">
                <CheckCircleIcon className="w-5 h-5" />
                <span className="text-sm">{passwordSuccess}</span>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Current Password</label>
              <input
                type="password"
                value={passwordForm.current_password}
                onChange={(e) => setPasswordForm(prev => ({ ...prev, current_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">New Password</label>
              <input
                type="password"
                value={passwordForm.new_password}
                onChange={(e) => setPasswordForm(prev => ({ ...prev, new_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
                minLength={8}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Confirm New Password</label>
              <input
                type="password"
                value={passwordForm.confirm_password}
                onChange={(e) => setPasswordForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
              >
                Change Password
              </button>
              <button
                type="button"
                onClick={() => { setShowPasswordForm(false); setPasswordForm({ current_password: '', new_password: '', confirm_password: '' }); }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Active Sessions */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <ShieldIcon className="w-5 h-5" />
          Active Sessions
        </h3>
        <p className="text-gray-500 dark:text-gray-400 mb-4">Manage your active login sessions</p>

        {loadingSessions ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mx-auto" />
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((session: any) => (
              <div key={session.id} className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                    <ShieldIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">Current Session</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {session.created_at ? new Date(session.created_at).toLocaleString() : 'Active now'}
                      {session.current && <span className="ml-2 px-2 py-0.5 text-xs bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded">Current</span>}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={revokeAllSessions}
          className="mt-4 px-4 py-2 border border-red-300 dark:border-red-600 rounded-lg text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          Sign out of all sessions
        </button>
      </div>

      {/* Two-Factor Authentication */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <ShieldIcon className="w-5 h-5" />
          Two-Factor Authentication
        </h3>
        <p className="text-gray-500 dark:text-gray-400 mb-4">Add an extra layer of security to your account</p>
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <p className="text-gray-600 dark:text-gray-400">Two-factor authentication (2FA) setup is not yet implemented.</p>
          <p className="text-gray-600 dark:text-gray-400 mt-2">This feature will be available in a future release.</p>
        </div>
      </div>

      {/* Email Verification */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <MailIcon className="w-5 h-5" />
          Email Verification
        </h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <div>
              <p className="font-medium text-gray-900 dark:text-white">Email Verification Status</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Verify your email address for account security</p>
            </div>
            <span className={cn(
              'px-3 py-1 rounded-full text-sm font-medium',
              currentUser?.email_verified
                ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
            )}>
              {currentUser?.email_verified ? 'Verified' : 'Not Verified'}
            </span>
          </div>
          {!currentUser?.email_verified && (
            <button
              onClick={() => router.push('/verify-email')}
              className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              Verify Email
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function NotificationsTab() {
  // Default notification preferences
  const defaultPrefs = {
    email: {
      execution_completed: true,
      execution_failed: true,
      compensation_triggered: true,
      weekly_summary: false,
    },
    in_app: {
      realtime_updates: true,
      system_announcements: true,
    },
  };

  // Load preferences from localStorage
  const [prefs, setPrefs] = useState<typeof defaultPrefs>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('notification_preferences');
      if (stored) {
        try {
          return { ...defaultPrefs, ...JSON.parse(stored) };
        } catch {
          return defaultPrefs;
        }
      }
    }
    return defaultPrefs;
  });

  // Save preferences to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('notification_preferences', JSON.stringify(prefs));
    }
  }, [prefs]);

  const updateEmailPref = (key: keyof typeof defaultPrefs.email, value: boolean) => {
    setPrefs(prev => ({ ...prev, email: { ...prev.email, [key]: value } }));
  };

  const updateInAppPref = (key: keyof typeof defaultPrefs.in_app, value: boolean) => {
    setPrefs(prev => ({ ...prev, in_app: { ...prev.in_app, [key]: value } }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Email Notifications</h3>
        <div className="space-y-4">
          <NotificationToggle
            label="Workflow execution completed"
            description="Receive email when a workflow execution finishes"
            checked={prefs.email.execution_completed}
            onChange={(value) => updateEmailPref('execution_completed', value)}
          />
          <NotificationToggle
            label="Workflow execution failed"
            description="Receive email when a workflow execution fails"
            checked={prefs.email.execution_failed}
            onChange={(value) => updateEmailPref('execution_failed', value)}
          />
          <NotificationToggle
            label="Compensation triggered"
            description="Receive email when compensation is triggered"
            checked={prefs.email.compensation_triggered}
            onChange={(value) => updateEmailPref('compensation_triggered', value)}
          />
          <NotificationToggle
            label="Weekly summary"
            description="Receive a weekly summary of your workflows"
            checked={prefs.email.weekly_summary}
            onChange={(value) => updateEmailPref('weekly_summary', value)}
          />
        </div>
      </div>
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">In-App Notifications</h3>
        <div className="space-y-4">
          <NotificationToggle
            label="Real-time execution updates"
            description="Show live updates for running executions"
            checked={prefs.in_app.realtime_updates}
            onChange={(value) => updateInAppPref('realtime_updates', value)}
          />
          <NotificationToggle
            label="System announcements"
            description="Receive important system notifications"
            checked={prefs.in_app.system_announcements}
            onChange={(value) => updateInAppPref('system_announcements', value)}
          />
        </div>
      </div>
    </div>
  );
}

function NotificationToggle({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
      <div>
        <p className="font-medium text-gray-900 dark:text-white">{label}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative w-12 h-6 rounded-full transition-colors',
          checked ? 'bg-primary-500' : 'bg-gray-300 dark:bg-gray-600'
        )}
        aria-pressed={checked}
      >
        <span className={cn(
          'absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform',
          checked ? 'translate-x-6' : 'translate-x-0.5'
        )} />
      </button>
    </div>
  );
}

