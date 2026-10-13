import React from 'react';
import { UtensilsCrossed } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, actionText, onAction }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px',
        textAlign: 'center',
        maxWidth: '480px',
        margin: '40px auto'
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-brand-light)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '16px'
        }}
      >
        <UtensilsCrossed size={28} color="var(--color-brand)" />
      </div>
      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
        {title}
      </h3>
      <p style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)', marginBottom: '20px', lineHeight: 1.5 }}>
        {description}
      </p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: '10px 18px',
            backgroundColor: 'var(--color-brand)',
            color: '#FFF',
            borderRadius: 'var(--radius-md)',
            fontWeight: 600,
            fontSize: '0.875rem'
          }}
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
