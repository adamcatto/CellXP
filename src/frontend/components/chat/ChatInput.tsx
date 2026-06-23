'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Button } from '../ui/Button';
import type { SessionId, ArtifactRef } from '../../lib/types';

interface ChatInputProps {
  sessionId: SessionId;
  disabled?: boolean;
  /** Whether a run is currently in flight */
  running?: boolean;
  onSend: (message: string) => void;
  onStop?: () => void;
  pinnedEntities?: string[];
  recentArtifacts?: ArtifactRef[];
}

type InputFormat = 'fasta' | 'vcf' | 'pdb' | 'smiles' | null;

function detectFormat(text: string): InputFormat {
  const t = text.trim();
  if (/^>/.test(t)) return 'fasta';
  if (/^##fileformat=VCF/.test(t)) return 'vcf';
  if (/^ATOM\s+\d/.test(t) || /^HEADER\s/.test(t)) return 'pdb';
  // Gene / entity tokens (BRCA1, CYP2D6, HLA-A) are not SMILES.
  if (/^[A-Z][A-Za-z0-9-]{1,31}$/.test(t) && !/[=#@%/\\]/.test(t)) return null;
  // Require SMILES-specific syntax so pasted prose is not misclassified.
  if (
    /^[A-Za-z0-9@+\-[\]()=#%/\\.:]+$/i.test(t) &&
    (/[=[\]()@#/\\]/.test(t) || /\d[a-z]/i.test(t)) &&
    t.length >= 3
  ) {
    return 'smiles';
  }
  return null;
}

export function ChatInput({
  sessionId: _sessionId,
  disabled,
  running,
  onSend,
  onStop,
  pinnedEntities = [],
  recentArtifacts = [],
}: ChatInputProps) {
  const [text, setText] = useState('');
  const [showSlash, setShowSlash] = useState(false);
  const [showMention, setShowMention] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [detectedFormat, setDetectedFormat] = useState<InputFormat>(null);
  const [formatConfirmed, setFormatConfirmed] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);
    setDetectedFormat(null);
    setFormatConfirmed(false);

    const last = val.split('\n').pop() ?? '';
    // Slash autocomplete
    if (last.startsWith('/') && last.length > 0) {
      setShowSlash(true);
      setShowMention(false);
    } else if (last.includes('@') && !last.includes(' ')) {
      const idx = last.lastIndexOf('@');
      setMentionQuery(last.slice(idx + 1));
      setShowMention(true);
      setShowSlash(false);
    } else {
      setShowSlash(false);
      setShowMention(false);
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = e.clipboardData.getData('text');
    const fmt = detectFormat(pasted);
    if (fmt) {
      // CHT-4: surface the detected format before sending
      setDetectedFormat(fmt);
      setFormatConfirmed(false);
    }
  };

  const doSend = useCallback(() => {
    const msg = text.trim();
    if (!msg || disabled || running) return;
    // CHT-4: warn if detected format not confirmed
    if (detectedFormat && !formatConfirmed) return;
    onSend(msg);
    setText('');
    setDetectedFormat(null);
    setFormatConfirmed(false);
    setShowSlash(false);
    setShowMention(false);
  }, [text, disabled, running, detectedFormat, formatConfirmed, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
    if ((e.metaKey || e.ctrlKey) && e.key === '.') {
      e.preventDefault();
      onStop?.();
    }
  };

  // Filtered mention suggestions
  const mentionSuggestions = [
    ...pinnedEntities
      .filter(e => e.toLowerCase().includes(mentionQuery.toLowerCase()))
      .map(e => ({ id: e, label: e, kind: 'entity' as const })),
    ...recentArtifacts
      .filter(a => a.title.toLowerCase().includes(mentionQuery.toLowerCase()))
      .slice(0, 5)
      .map(a => ({ id: a.id, label: a.title, kind: 'artifact' as const })),
  ].slice(0, 8);

  const insertMention = (label: string) => {
    const parts = text.split('@');
    const newText = parts.slice(0, -1).join('@') + `@${label} `;
    setText(newText);
    setShowMention(false);
    textareaRef.current?.focus();
  };

  const isDisabled = disabled || running;
  const pendingFormatConfirmation = Boolean(detectedFormat && !formatConfirmed);

  return (
    <div
      style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--bg-raised)',
        padding: '10px 12px',
      }}
    >
      {/* Detected format banner */}
      {detectedFormat && !formatConfirmed && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 10px',
            background: 'rgba(79,127,255,0.12)',
            border: '1px solid var(--accent)',
            borderRadius: 6,
            fontSize: 12,
            marginBottom: 8,
          }}
        >
          <span>
            Detected <strong>{detectedFormat.toUpperCase()}</strong> content — treat as attached input?
          </span>
          <Button size="sm" variant="primary" onClick={() => setFormatConfirmed(true)}>
            Yes, attach
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDetectedFormat(null);
              setFormatConfirmed(false);
            }}
          >
            No, send as text
          </Button>
        </div>
      )}

      {/* Slash command popover */}
      {showSlash && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 12,
            background: 'var(--bg-raised)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '6px 0',
            minWidth: 260,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            zIndex: 50,
          }}
        >
          {[
            { label: '/score_variant', desc: 'Score a variant with AlphaGenome' },
            { label: '/design_guides', desc: 'Design CRISPR guides' },
            { label: '/lit', desc: 'Literature search (RAG)' },
            { label: '/annotate', desc: 'Annotate a genomic region' },
          ].map(cmd => (
            <button
              key={cmd.label}
              onClick={() => { setText(cmd.label + ' '); setShowSlash(false); textareaRef.current?.focus(); }}
              style={{
                display: 'flex',
                flexDirection: 'column',
                width: '100%',
                padding: '6px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'inherit',
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--accent)' }}>
                {cmd.label}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{cmd.desc}</span>
            </button>
          ))}
        </div>
      )}

      {/* Mention popover */}
      {showMention && mentionSuggestions.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 12,
            background: 'var(--bg-raised)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '6px 0',
            minWidth: 220,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            zIndex: 50,
          }}
        >
          {mentionSuggestions.map(s => (
            <button
              key={s.id}
              onClick={() => insertMention(s.label)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '5px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 13,
                color: 'var(--text)',
                textAlign: 'left',
              }}
            >
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {s.kind === 'entity' ? '@' : '◇'}
              </span>
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Main composer row */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', position: 'relative' }}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onPaste={handlePaste}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder={running ? 'Run in progress…' : 'Ask about a gene, variant, structure, or pathway…'}
          aria-label="Message composer"
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            background: 'var(--bg-overlay)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            color: 'var(--text)',
            fontFamily: 'inherit',
            fontSize: 14,
            padding: '8px 12px',
            lineHeight: 1.5,
            outline: 'none',
            transition: 'border-color 120ms',
            minHeight: 38,
            maxHeight: 200,
            overflowY: 'auto',
          }}
        />
        {running ? (
          <Button
            variant="danger"
            onClick={onStop}
            aria-label="Stop run"
            title="Cancel (⌘.)"
          >
            ■ Stop
          </Button>
        ) : (
          <Button
            type="button"
            variant="primary"
            onClick={doSend}
            disabled={!text.trim() || isDisabled || pendingFormatConfirmation}
            title={pendingFormatConfirmation ? 'Confirm detected input format first' : 'Send (↵)'}
            aria-label="Send message"
          >
            Send
          </Button>
        )}
      </div>

      {/* Keyboard hint */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textAlign: 'right' }}>
        ↵ send · ⇧↵ new line · / macros · @ mention
      </div>
    </div>
  );
}
