import React, { useState, useEffect } from 'react';
import { ChefHat } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
}

const LOADING_PHASES = [
  "Finding the best recipe...",
  "Preparing your ingredients...",
  "Checking dietary requirements...",
  "Crafting your recipe...",
  "Almost ready...",
];

export const LoadingState: React.FC<LoadingStateProps> = ({ message }) => {
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setPhaseIndex(prev => (prev + 1) % LOADING_PHASES.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  const displayMessage = message || LOADING_PHASES[phaseIndex];

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '14px 18px',
      backgroundColor: 'var(--color-bg-card)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)',
      maxWidth: '340px',
      margin: '8px 0'
    }}>
      <div style={{
        width: '34px',
        height: '34px',
        borderRadius: '50%',
        backgroundColor: 'var(--color-brand-light)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
        className="animate-pulse-subtle"
      >
        <ChefHat size={18} color="var(--color-brand)" />
      </div>

      <div>
        <div style={{
          fontSize: '0.855rem',
          fontWeight: 600,
          color: 'var(--color-text-primary)',
          marginBottom: '3px',
        }}>
          {displayMessage}
        </div>
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          {[0, 1, 2].map(i => (
            <div
              key={i}
              style={{
                width: '5px',
                height: '5px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-brand)',
                opacity: 0.4,
                animation: `pulseSubtle 1.2s ease-in-out infinite ${i * 0.25}s`,
              }}
            />
          ))}
          <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginLeft: '4px' }}>
            a few seconds
          </span>
        </div>
      </div>
    </div>
  );
};
