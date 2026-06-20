'use client';

import React, { useEffect, useRef } from 'react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: number | string;
}

export function Dialog({ open, onClose, title, children, width = 480 }: DialogProps) {
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={backdropRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'dialog-title' : undefined}
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose();
      }}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 200,
      }}
    >
      <div
        style={{
          background: 'var(--bg-raised)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          width,
          maxWidth: '90vw',
          maxHeight: '80vh',
          overflow: 'auto',
          padding: 24,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {title && (
          <h2
            id="dialog-title"
            style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 600, color: 'var(--text)' }}
          >
            {title}
          </h2>
        )}
        {children}
      </div>
    </div>
  );
}
