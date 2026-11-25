/**
 * Custom React Flow Edge Components for reactflow v11
 */

'use client';

import React from 'react';
import type { EdgeProps } from 'reactflow';
import { getBezierPath, getStraightPath, getSmoothStepPath, getMarkerEnd, MarkerType } from 'reactflow';
import { cn } from '@/lib/utils';

type MarkerEndObject = { type: MarkerType; width?: number; height?: number; color?: string };

interface WorkflowEdgeProps extends Omit<EdgeProps, 'markerEnd'> {
  animated?: boolean;
  style?: React.CSSProperties;
  markerEnd?: string | MarkerEndObject;
  pathType?: 'smoothstep' | 'straight' | 'step';
}

interface PathEdgeProps {
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition?: import('reactflow').Position;
  targetPosition?: import('reactflow').Position;
}

function getPath(edgeProps: PathEdgeProps, pathType: 'smoothstep' | 'straight' | 'step' = 'smoothstep') {
  switch (pathType) {
    case 'straight':
      return getStraightPath(edgeProps as EdgeProps);
    case 'step':
      return getStepPath(edgeProps);
    default:
      return getSmoothStepPath(edgeProps as EdgeProps);
  }
}

function getStepPath(edgeProps: PathEdgeProps): string {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition } = edgeProps;
  const xDistance = Math.abs(targetX - sourceX);
  const yDistance = Math.abs(targetY - sourceY);

  if (xDistance > yDistance) {
    const midX = sourceX + (targetX - sourceX) / 2;
    return `M${sourceX},${sourceY} L${midX},${sourceY} L${midX},${targetY} L${targetX},${targetY}`;
  } else {
    const midY = sourceY + (targetY - sourceY) / 2;
    return `M${sourceX},${sourceY} L${sourceX},${midY} L${targetX},${midY} L${targetX},${targetY}`;
  }
}

export function WorkflowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  style = {},
  animated = true,
  markerEnd,
  pathType = 'smoothstep',
  ...rest
}: WorkflowEdgeProps) {
  const defaultMarkerEnd: MarkerEndObject = { type: MarkerType.ArrowClosed, width: 20, height: 20 };
  const effectiveMarkerEnd: MarkerEndObject = typeof markerEnd === 'object' && markerEnd !== null ? markerEnd : defaultMarkerEnd;
  const edgeColor = data?.color || '#3b82f6';
  const isSelected = selected;

  const pathStyle: React.CSSProperties = {
    stroke: isSelected ? '#0ea5e9' : edgeColor,
    strokeWidth: isSelected ? 3 : 2,
    strokeDasharray: animated ? '5,5' : 'none',
    animation: animated ? 'dash 1s linear infinite' : 'none',
    transition: 'stroke 0.2s ease, stroke-width 0.2s ease',
    fill: 'none',
    ...style,
  };

  // Add keyframe animation for dashed lines
  React.useEffect(() => {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = `
      @keyframes dash {
        to {
          stroke-dashoffset: -10;
        }
      }
    `;
    document.head.appendChild(styleSheet);
    return () => {
      document.head.removeChild(styleSheet);
    };
  }, []);

  const path = getPath(
    { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition },
    pathType
  ) as string;

  const markerEndResult = getMarkerEnd(effectiveMarkerEnd.type, {
    stroke: isSelected ? '#0ea5e9' : edgeColor,
    strokeWidth: isSelected ? 3 : 2,
    markerWidth: effectiveMarkerEnd.width,
    markerHeight: effectiveMarkerEnd.height,
    markerColor: effectiveMarkerEnd.color,
  } as any);

  // getMarkerEnd might return a string (marker URL) or an object
  const markerEndUrl = typeof markerEndResult === 'string' ? markerEndResult : (markerEndResult as any).id;
  const markerElement = typeof markerEndResult === 'object' && markerEndResult !== null ? (markerEndResult as any).marker : null;

  return (
    <>
      <path
        id={id}
        d={path}
        style={pathStyle}
        markerEnd={markerEndUrl}
        {...rest}
      >
        {markerElement && (
          <defs>
            <marker
              id={markerEndUrl.replace('url(#', '').replace(')', '')}
              markerWidth={effectiveMarkerEnd.width}
              markerHeight={effectiveMarkerEnd.height}
              refX={effectiveMarkerEnd.width! * 0.5}
              refY={effectiveMarkerEnd.height! * 0.5}
              orient="auto"
            >
              <path
                d={markerElement}
                fill={effectiveMarkerEnd.color || edgeColor}
              />
            </marker>
          </defs>
        )}
      </path>
      {data?.label && (
        <div
          className={cn(
            'absolute bg-white dark:bg-gray-900 px-1.5 py-0.5 rounded text-xs text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 shadow-sm',
            'pointer-events-none'
          )}
          style={{
            transform: `translate(-50%, -50%)`,
            left: `${(sourceX + targetX) / 2}px`,
            top: `${(sourceY + targetY) / 2}px`,
          }}
        >
          {data.label}
        </div>
      )}
    </>
  );
}

// Conditional edge with diamond marker for condition branches
export function ConditionalEdge(props: WorkflowEdgeProps) {
  return <WorkflowEdge {...props} markerEnd={{ type: MarkerType.ArrowClosed, width: 16, height: 16, color: props.data?.color || '#3b82f6' }} />;
}

// Parallel edge with double line style
export function ParallelEdge(props: WorkflowEdgeProps) {
  return <WorkflowEdge {...props} style={{ ...props.style, strokeDasharray: '8,4' }} />;
}

// Compensation edge with distinct styling
export function CompensationEdge(props: WorkflowEdgeProps) {
  return (
    <WorkflowEdge
      {...props}
      animated={false}
      style={{
        ...props.style,
        stroke: '#ef4444',
        strokeDasharray: '4,4',
      }}
      markerEnd={{ type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#ef4444' }}
    />
  );
}