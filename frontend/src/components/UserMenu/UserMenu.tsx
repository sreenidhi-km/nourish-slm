import React from 'react';
import type { User as UserType } from '../../types';

interface UserMenuProps {
  user: UserType | null;
}

export const UserMenu: React.FC<UserMenuProps> = ({ user }) => {
  if (!user) return null;

  const initials = user.name
    ? user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div
        style={{
          width: '34px',
          height: '34px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-brand)',
          color: '#FFF',
          fontWeight: 700,
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        {initials}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          {user.name}
        </span>
        <span style={{ fontSize: '0.725rem', color: 'var(--color-text-muted)' }}>
          {user.email}
        </span>
      </div>
    </div>
  );
};
