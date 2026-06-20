'use client';

import React from 'react';

interface CardProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
  /** Show a left-side color accent */
  accent?: 'blue' | 'green' | 'yellow' | 'red';
  onClick?: () => void;
}

const ACCENT_COLORS: Record<string, string> = {
  blue: 'var(--accent)',
  green: 'var(--success)',
  yellow: 'var(--warning)',
  red: 'var(--danger)',
};

export function Card({ children, style, className, accent, onClick }: CardProps) {
  return (
    <div
      className={className}
      onClick={onClick}
      style={{
        background: 'var(--bg-raised)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        borderLeft: accent ? `3px solid ${ACCENT_COLORS[accent]}` : undefined,
        padding: '12px 16px',
        cursor: onClick ? 'pointer' : undefined,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function CardHeader({ children, style }: CardHeaderProps) {
  return (
    <div style={{ marginBottom: 8, ...style }}>
      {children}
    </div>
  );
}

export function CardBody({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={style}>{children}</div>;
}
