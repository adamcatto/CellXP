'use client';

import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const BASE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  fontFamily: 'inherit',
  fontWeight: 500,
  cursor: 'pointer',
  border: '1px solid transparent',
  borderRadius: 'var(--radius)',
  transition: 'background 120ms ease, border-color 120ms ease, opacity 120ms ease',
  userSelect: 'none',
  whiteSpace: 'nowrap',
};

const SIZE_STYLES: Record<ButtonSize, React.CSSProperties> = {
  sm: { fontSize: 12, padding: '3px 10px', height: 26 },
  md: { fontSize: 13, padding: '5px 14px', height: 32 },
  lg: { fontSize: 14, padding: '7px 18px', height: 38 },
};

const VARIANT_STYLES: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: 'var(--accent)',
    color: '#fff',
    borderColor: 'var(--accent)',
  },
  secondary: {
    background: 'var(--bg-overlay)',
    color: 'var(--text)',
    borderColor: 'var(--border)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--text-muted)',
    borderColor: 'transparent',
  },
  danger: {
    background: 'var(--danger)',
    color: '#fff',
    borderColor: 'var(--danger)',
  },
};

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled,
  children,
  style,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      {...rest}
      disabled={isDisabled}
      style={{
        ...BASE,
        ...SIZE_STYLES[size],
        ...VARIANT_STYLES[variant],
        opacity: isDisabled ? 0.45 : 1,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        ...style,
      }}
    >
      {loading && <Spinner size={size === 'lg' ? 14 : 12} />}
      {children}
    </button>
  );
}

function Spinner({ size = 12 }: { size?: number }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        border: '2px solid currentColor',
        borderTopColor: 'transparent',
        borderRadius: '50%',
        animation: 'spin 600ms linear infinite',
      }}
    />
  );
}
