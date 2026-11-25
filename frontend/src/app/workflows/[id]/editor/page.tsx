/**
 * Workflow Visual Editor Page
 * Uses React Flow for drag-and-drop workflow editing
 */

'use client';

import React, { useEffect, useCallback, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ReactFlow,
  Node,
  Edge,
  addEdge,
  Connection,
  NodeTypes,
  EdgeTypes,
  Background,
  Controls,
  MiniMap,
  Panel,
  Handle,
  Position,
  MarkerType,
  useNodesState,
  useEdgesState,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  NodeProps,
  EdgeProps,
} from 'reactflow';
import { apiClient } from '@/services/api';
import { useOrganizationStore, useWorkflowStore, useReactFlowStore, useUIStore } from '@/lib/stores';
import { formatRelativeTime, getStepTypeColor, cn } from '@/lib/utils';
import { MainLayout } from '@/components/layout/MainLayout';
import {
  WorkflowNode,
  StartNode,
  EndNode,
} from '@/components/workflow/nodes';
import { WorkflowEdge } from '@/components/workflow/edges';
import { SidePanel } from '@/components/workflow/SidePanel';
import { Toolbar } from '@/components/workflow/Toolbar';
import { NodePalette } from '@/components/workflow/NodePalette';
import { VersionSelector } from '@/components/workflow/VersionSelector';
import { WorkflowStepDefinition, WorkflowConnection, WorkflowVersion } from '@/types';

const nodeTypes: NodeTypes = {
  workflowNode: WorkflowNode,
  start: StartNode,
  end: EndNode,
};

const edgeTypes: EdgeTypes = {
  workflowEdge: WorkflowEdge,
};

export default function WorkflowEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const { currentOrganization } = useOrganizationStore();
  const { currentWorkflow, versions, setCurrentVersion } = useWorkflowStore();
  const {
    setNodes,
    setEdges,
    addNode,
    updateNode,
    removeNode,
    addEdge,
    removeEdge,
    updateEdge,
    importFromWorkflow,
    exportToWorkflow,
    nodes,
    edges,
    isDirty,
    setDirty,
    setViewport
  } = useReactFlowStore();
  const { openModal, closeModal, addNotification } = useUIStore();
  const [selectedNode, setSelectedNode] = React.useState<Node | null>(null);
  const [saved, setSaved] = React.useState(true);
  const [selectedVersion, setSelectedVersion] = React.useState<number>(1);
  const [isLoading, setIsLoading] = React.useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = React.useState(false);

  // Fetch workflow data on mount or version change
  useEffect(() => {
    if (workflowId && currentOrganization && selectedVersion) {
      loadWorkflowVersion(selectedVersion);
    }
  }, [workflowId, currentOrganization, selectedVersion]);

  const loadWorkflowVersion = async (versionNumber: number) => {
    setIsLoading(true);
    try {
      const version = await apiClient.getWorkflowVersion(currentOrganization!.id, workflowId, versionNumber);
      if (version.steps && version.connections) {
        importFromWorkflow(version.steps, version.connections);
        setSaved(true);
        setHasUnsavedChanges(false);
        setCurrentVersion(version);
      }
    } catch (error) {
      console.error('Failed to load workflow version:', error);
      addNotification({
        type: 'error',
        title: 'Failed to load workflow',
        message: 'Could not load the workflow version. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleVersionChange = async (newVersion: number) => {
    if (hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Switch versions anyway?')) {
        return;
      }
    }
    setSelectedVersion(newVersion);
  };

  const onNodesChange: OnNodesChange = useCallback((changes) => {
    changes.forEach((change) => {
      switch (change.type) {
        case 'position':
          if (change.position) {
            updateNode(change.id, { position: change.position });
          }
          break;
        case 'remove':
          removeNode(change.id);
          break;
        case 'add':
          addNode(change.item);
          break;
      }
    });
    setDirty(true);
    setSaved(false);
    setHasUnsavedChanges(true);
  }, [updateNode, removeNode, addNode, setDirty]);

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    changes.forEach((change) => {
      switch (change.type) {
        case 'remove':
          removeEdge(change.id);
          break;
        case 'add':
          addEdge(change.item);
          break;
      }
    });
    setDirty(true);
    setSaved(false);
    setHasUnsavedChanges(true);
  }, [addEdge, removeEdge, setDirty]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target) {
        const newEdge: Edge = {
          id: `edge-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          source: connection.source,
          target: connection.target,
          sourceHandle: connection.sourceHandle,
          targetHandle: connection.targetHandle,
          type: 'workflowEdge',
          animated: true,
        };
        addEdge(newEdge);
      }
      setDirty(true);
      setSaved(false);
      setHasUnsavedChanges(true);
    },
    [addEdge, setDirty]
  );

  const handleSave = async () => {
    if (!currentOrganization) return;

    setIsLoading(true);
    try {
      const { steps, connections } = exportToWorkflow();

      // Save steps
      for (const step of steps) {
        // Convert WorkflowStepDefinition to CreateWorkflowStepRequest (null -> undefined for optional fields)
        const stepData = {
          step_key: step.step_key,
          name: step.name,
          description: step.description ?? undefined,
          step_type: step.step_type,
          order: step.order,
          handler: step.handler,
          config: step.config ?? undefined,
          input_mapping: step.input_mapping ?? undefined,
          output_mapping: step.output_mapping ?? undefined,
          timeout_seconds: step.timeout_seconds ?? undefined,
          retry_policy_id: step.retry_policy_id ?? undefined,
          compensation_handler: step.compensation_handler ?? undefined,
          compensation_config: step.compensation_config ?? undefined,
          depends_on: step.depends_on ?? undefined,
          is_critical: step.is_critical ?? undefined,
          continue_on_failure: step.continue_on_failure ?? undefined,
        };
        try {
          await apiClient.updateWorkflowStep(currentOrganization.id, workflowId, selectedVersion, step.step_key, stepData);
        } catch {
          await apiClient.createWorkflowStep(currentOrganization.id, workflowId, selectedVersion, stepData);
        }
      }

      // Save connections to workflow version
      if (connections.length > 0) {
        const version = await apiClient.getWorkflowVersion(currentOrganization.id, workflowId, selectedVersion);
        await apiClient.patch<WorkflowVersion>(
          `/workflows/${workflowId}/versions/${selectedVersion}`,
          { connections },
          { params: { org_id: currentOrganization.id } }
        );
      }

      setSaved(true);
      setDirty(false);
      setHasUnsavedChanges(false);
      addNotification({
        type: 'success',
        title: 'Workflow saved',
        message: `Version ${selectedVersion} saved successfully.`,
      });
    } catch (error) {
      console.error('Failed to save workflow:', error);
      addNotification({
        type: 'error',
        title: 'Failed to save workflow',
        message: 'Could not save the workflow. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleNodeUpdate = useCallback((data: Partial<Node['data']>) => {
    if (selectedNode) {
      updateNode(selectedNode.id, { data: { ...selectedNode.data, ...data } });
      setDirty(true);
      setSaved(false);
      setHasUnsavedChanges(true);
    }
  }, [selectedNode, updateNode, setDirty]);

  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    openModal('node-config');
  };

  const handleCreateVersion = async () => {
    if (!currentOrganization) return;

    const changelog = prompt('Enter changelog for new version:');
    if (!changelog) return;

    try {
      const { steps, connections } = exportToWorkflow();

      await apiClient.post<WorkflowVersion>(
        `/workflows/${workflowId}/versions`,
        {
          definition: {},
          steps,
          connections,
          variables: {},
          changelog,
        },
        { params: { org_id: currentOrganization.id } }
      );

      // Refresh versions list
      const versionsData = await apiClient.getWorkflowVersions(currentOrganization.id, workflowId);
      const latestVersion = Math.max(...versionsData.map(v => v.version_number));

      setSelectedVersion(latestVersion);
      addNotification({
        type: 'success',
        title: 'New version created',
        message: `Version ${latestVersion} created successfully.`,
      });
    } catch (error) {
      console.error('Failed to create version:', error);
      addNotification({
        type: 'error',
        title: 'Failed to create version',
        message: 'Could not create new version. Please try again.',
      });
    }
  };

  return (
    <MainLayout>
      <div className="h-[calc(100vh-4rem)] flex flex-col">
        {/* Toolbar */}
        <Toolbar
          onSave={handleSave}
          onUndo={() => {}}
          onRedo={() => {}}
          onZoomIn={() => {}}
          onZoomOut={() => {}}
          onFitView={() => {}}
          saved={saved}
          dirty={isDirty}
          isLoading={isLoading}
          onCreateVersion={handleCreateVersion}
          versions={versions}
          selectedVersion={selectedVersion}
          onVersionChange={handleVersionChange}
        />

        {/* Editor Area */}
        <div className="flex-1 flex relative overflow-hidden">
          {/* Node Palette */}
          <div className="hidden lg:block w-64 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
            <NodePalette onDragStart={(nodeType) => {}} />
          </div>

          {/* React Flow Canvas */}
          <div className="flex-1 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={handleNodeClick}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView={true}
              attributionPosition="bottom-left"
            >
              <Background
                color="#e5e7eb"
                gap={16}
                size={1}
              />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  if (node.type === 'start') return '#22c55e';
                  if (node.type === 'end') return '#ef4444';
                  return getStepTypeColor(node.data?.type || 'action').replace('bg-', '').replace('dark:bg-', '');
                }}
              />
            </ReactFlow>
          </div>

          {/* Side Panel */}
          <SidePanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onUpdate={handleNodeUpdate}
          />
        </div>
      </div>
    </MainLayout>
  );
}