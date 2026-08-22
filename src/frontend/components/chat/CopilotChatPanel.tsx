'use client';

import {
  CopilotChat,
  useAgentContext,
  useInterrupt,
  useRenderTool,
} from '@copilotkit/react-core/v2';
import { useEffect, useMemo } from 'react';
import { z } from 'zod';

import type {
  ArtifactRef,
  Clarification,
  ReviewItem,
} from '../../lib/types';
import { artifactIcon, artifactLabel } from '../../lib/artifacts';
import { Card } from '../ui/Card';
import { ClarificationCard, ReviewCard } from './ChatMessage';

const artifactTypeSchema = z.enum([
  'genome_track',
  'locus_plot',
  'feature_table',
  'coordinate_table',
  'motif_logo',
  'structure_3d',
  'contact_map',
  'sequence_viewer',
  'guide_table',
  'off_target_table',
  'report',
  'protein_design_table',
  'origami_layout',
  'citation_set',
  'file',
]);

const artifactSchema = z.object({
  id: z.string(),
  type: artifactTypeSchema,
  title: z.string(),
  status: z.enum(['pending', 'ready', 'partial', 'failed']),
  run_id: z.string(),
  summary: z.record(z.string(), z.unknown()).optional(),
  actionable: z.boolean(),
  review_status: z.enum([
    'not_required',
    'pending',
    'approved',
    'rejected',
    'changes_requested',
  ]),
  created_at: z.string(),
});

const artifactToolSchema = z.object({ artifact: artifactSchema });

interface CopilotChatPanelProps {
  sessionId: string;
  title: string;
  organism?: string;
  assembly?: string;
  selectedArtifactIds: string[];
  pinnedEntityIds?: string[];
  onArtifactAdded: (artifact: ArtifactRef) => void;
}

function ArtifactToolCard({
  artifact,
  onArtifactAdded,
}: {
  artifact: ArtifactRef;
  onArtifactAdded: (artifact: ArtifactRef) => void;
}) {
  useEffect(() => {
    onArtifactAdded(artifact);
  }, [artifact, onArtifactAdded]);

  return (
    <Card accent="blue" style={{ margin: '8px 0' }}>
      <button
        type="button"
        onClick={() => onArtifactAdded(artifact)}
        style={{
          alignItems: 'center',
          background: 'none',
          border: 0,
          color: 'var(--text)',
          cursor: 'pointer',
          display: 'flex',
          fontFamily: 'inherit',
          gap: 8,
          padding: 0,
          textAlign: 'left',
          width: '100%',
        }}
      >
        <span aria-hidden="true" style={{ fontSize: 18 }}>
          {artifactIcon(artifact.type)}
        </span>
        <span style={{ flex: 1 }}>
          <strong style={{ display: 'block', fontSize: 13 }}>{artifact.title}</strong>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            {artifactLabel(artifact.type)} · open in workspace
          </span>
        </span>
        <span style={{ color: 'var(--accent)' }}>Open →</span>
      </button>
    </Card>
  );
}

function GenericToolCard({
  name,
  parameters,
  status,
}: {
  name: string;
  parameters: unknown;
  status: 'inProgress' | 'executing' | 'complete';
}) {
  const step = (
    parameters &&
    typeof parameters === 'object' &&
    'step' in parameters &&
    typeof parameters.step === 'object'
  )
    ? parameters.step as { label?: string; status?: string; tool_version?: string }
    : undefined;
  const label = step?.label ?? name.replaceAll('_', ' ');

  return (
    <div
      aria-label={`${label} ${status}`}
      style={{
        alignItems: 'center',
        background: 'var(--bg-overlay)',
        border: '1px solid var(--border)',
        borderRadius: 7,
        color: 'var(--text-muted)',
        display: 'flex',
        fontSize: 12,
        gap: 8,
        margin: '6px 0',
        padding: '7px 10px',
      }}
    >
      <span aria-hidden="true">{status === 'complete' ? '✓' : '◌'}</span>
      <span style={{ color: 'var(--text)' }}>{label}</span>
      {step?.tool_version && (
        <code style={{ fontSize: 10, marginLeft: 'auto' }}>{step.tool_version}</code>
      )}
    </div>
  );
}

function interruptMetadata(interrupt: unknown): Record<string, unknown> {
  if (!interrupt || typeof interrupt !== 'object' || !('metadata' in interrupt)) return {};
  const metadata = interrupt.metadata;
  return metadata && typeof metadata === 'object'
    ? metadata as Record<string, unknown>
    : {};
}

function CopilotBindings({
  selectedArtifactIds,
  pinnedEntityIds,
  onArtifactAdded,
}: Pick<
  CopilotChatPanelProps,
  'selectedArtifactIds' | 'pinnedEntityIds' | 'onArtifactAdded'
>) {
  const workspaceContext = useMemo(
    () => ({
      selected_artifact_ids: selectedArtifactIds.slice(0, 20),
      pinned_entity_ids: (pinnedEntityIds ?? []).slice(0, 50),
    }),
    [pinnedEntityIds, selectedArtifactIds],
  );

  useAgentContext({
    description: 'CellXP workspace context',
    value: workspaceContext,
  });

  useRenderTool(
    {
      name: 'render_cellxp_artifact',
      parameters: artifactToolSchema,
      render: ({ status, parameters }) => {
        if (status === 'inProgress' || !parameters.artifact) {
          return <GenericToolCard name="Rendering biological artifact" parameters={parameters} status={status} />;
        }
        return (
          <ArtifactToolCard
            artifact={parameters.artifact}
            onArtifactAdded={onArtifactAdded}
          />
        );
      },
    },
    [onArtifactAdded],
  );

  useRenderTool(
    {
      name: '*',
      render: ({ name, parameters, status }) => (
        <GenericToolCard name={name} parameters={parameters} status={status} />
      ),
    },
    [],
  );

  useInterrupt({
    enabled: event => (
      event.value &&
      typeof event.value === 'object' &&
      'reason' in event.value &&
      event.value.reason === 'input_required'
    ),
    render: ({ interrupt, resolve }) => {
      const clarification = interruptMetadata(interrupt).clarification as Clarification | undefined;
      if (!clarification) {
        return (
          <Card accent="blue">
            <p>{interrupt?.message ?? 'CellXP needs more information.'}</p>
            <button type="button" onClick={() => void resolve({})}>Continue</button>
          </Card>
        );
      }
      return (
        <ClarificationCard
          clarification={clarification}
          onAnswer={answer => void resolve(answer)}
        />
      );
    },
  });

  useInterrupt({
    enabled: event => (
      event.value &&
      typeof event.value === 'object' &&
      'reason' in event.value &&
      event.value.reason === 'confirmation'
    ),
    render: ({ interrupt, resolve }) => {
      const review = interruptMetadata(interrupt).review as ReviewItem | undefined;
      if (!review) {
        return (
          <Card accent="yellow">
            <p>{interrupt?.message ?? 'Review is required.'}</p>
          </Card>
        );
      }
      return (
        <ReviewCard
          review={review}
          onDecide={(decision, note) => void resolve({ decision, note })}
        />
      );
    },
  });

  return null;
}

export function CopilotChatPanel({
  title,
  organism,
  assembly,
  selectedArtifactIds,
  pinnedEntityIds,
  onArtifactAdded,
}: CopilotChatPanelProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div
        style={{
          alignItems: 'center',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          flexShrink: 0,
          gap: 10,
          minHeight: 42,
          padding: '0 16px',
        }}
      >
        <strong style={{ fontSize: 14 }}>{title}</strong>
        {organism && (
          <span
            style={{
              background: 'var(--bg-overlay)',
              borderRadius: 10,
              color: 'var(--text-muted)',
              fontSize: 11,
              padding: '2px 8px',
            }}
          >
            {organism}{assembly ? ` · ${assembly}` : ''}
          </span>
        )}
      </div>
      <CopilotBindings
        selectedArtifactIds={selectedArtifactIds}
        pinnedEntityIds={pinnedEntityIds}
        onArtifactAdded={onArtifactAdded}
      />
      <div style={{ flex: 1, minHeight: 0 }}>
        <CopilotChat
          labels={{
            chatInputPlaceholder: 'Ask about a gene, variant, structure, pathway, or analysis…',
            welcomeMessageText: 'Ask CellXP about DNA, RNA, proteins, metabolites, or a biological analysis.',
          }}
          style={{ height: '100%' }}
          throttleMs={50}
        />
      </div>
    </div>
  );
}
