'use client';

import React, { useState } from 'react';

export interface Tab {
  id: string;
  label: string;
  icon?: string;
  badge?: string | number;
}

interface TabsProps {
  tabs: Tab[];
  activeId?: string;
  onChange?: (id: string) => void;
  style?: React.CSSProperties;
}

export function Tabs({ tabs, activeId, onChange, style }: TabsProps) {
  const [localActive, setLocalActive] = useState(tabs[0]?.id ?? '');
  const active = activeId ?? localActive;

  const handleClick = (id: string) => {
    setLocalActive(id);
    onChange?.(id);
  };

  return (
    <div
      role="tablist"
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--border)',
        gap: 0,
        overflowX: 'auto',
        ...style,
      }}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => handleClick(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              background: 'none',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
              color: isActive ? 'var(--text)' : 'var(--text-muted)',
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'color 120ms, border-color 120ms',
              marginBottom: -1,
            }}
          >
            {tab.icon && <span aria-hidden="true">{tab.icon}</span>}
            {tab.label}
            {tab.badge !== undefined && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  background: 'var(--accent)',
                  color: '#fff',
                  borderRadius: 10,
                  padding: '1px 5px',
                  minWidth: 16,
                  textAlign: 'center',
                }}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  id: string;
  activeId: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function TabPanel({ id, activeId, children, style }: TabPanelProps) {
  if (id !== activeId) return null;
  return (
    <div role="tabpanel" style={{ flex: 1, overflow: 'auto', ...style }}>
      {children}
    </div>
  );
}
