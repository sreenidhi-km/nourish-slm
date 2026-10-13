import React from 'react';
import { Sun, Moon } from 'lucide-react';

interface ThemeToggleProps {
  isDarkMode: boolean;
  onToggle: () => void;
  size?: 'sm' | 'md';
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ isDarkMode, onToggle, size = 'md' }) => {
  const isSmall = size === 'sm';

  return (
    <button
      onClick={onToggle}
      title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: isSmall ? '4px' : '6px',
        padding: isSmall ? '6px 10px' : '7px 12px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-border)',
        color: 'var(--color-text-secondary)',
        fontSize: isSmall ? '0.75rem' : '0.8rem',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all var(--transition-base)',
        boxShadow: 'var(--shadow-xs)',
        whiteSpace: 'nowrap'
      }}
    >
      {isDarkMode ? (
        <>
          <Sun size={isSmall ? 13 : 15} color="var(--color-egg)" />
          {!isSmall && <span>Light</span>}
        </>
      ) : (
        <>
          <Moon size={isSmall ? 13 : 15} color="var(--color-text-muted)" />
          {!isSmall && <span>Dark</span>}
        </>
      )}
    </button>
  );
};
