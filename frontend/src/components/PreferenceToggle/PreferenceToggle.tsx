import React, { useState, useRef, useEffect } from 'react';
import type { DietaryPreference } from '../../types';
import { Leaf, Egg, Drumstick, Sparkles, ChevronDown, Check } from 'lucide-react';

interface PreferenceToggleProps {
  currentPreference: DietaryPreference;
  onSelectPreference: (pref: DietaryPreference) => void;
}

export const PREFERENCE_OPTIONS: { id: DietaryPreference; label: string; icon: any; color: string; bg: string }[] = [
  { id: 'vegan', label: 'Vegan', icon: Leaf, color: '#15803D', bg: '#DCFCE7' },
  { id: 'vegetarian', label: 'Vegetarian', icon: Leaf, color: '#16A34A', bg: '#F0FDF4' },
  { id: 'eggitarian', label: 'Eggitarian', icon: Egg, color: '#D97706', bg: '#FEF3C7' },
  { id: 'non_vegetarian', label: 'Non-Vegetarian', icon: Drumstick, color: '#DC2626', bg: '#FEE2E2' },
  { id: 'no_preference', label: 'No Preference', icon: Sparkles, color: '#4F46E5', bg: '#EEF2FF' }
];

export const PreferenceToggle: React.FC<PreferenceToggleProps> = ({ currentPreference, onSelectPreference }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeOption = PREFERENCE_OPTIONS.find(o => o.id === currentPreference) || PREFERENCE_OPTIONS[4];
  const IconComponent = activeOption.icon;

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div style={{ position: 'relative' }} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 14px',
          backgroundColor: activeOption.bg,
          border: `1px solid ${activeOption.color}33`,
          borderRadius: 'var(--radius-md)',
          color: activeOption.color,
          fontWeight: 600,
          fontSize: '0.875rem',
          transition: 'all 0.2s ease',
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        <IconComponent size={16} color={activeOption.color} />
        <span>{activeOption.label}</span>
        <ChevronDown size={14} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            width: '220px',
            backgroundColor: 'var(--color-bg-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 100,
            padding: '6px',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px'
          }}
          className="animate-fade-in"
        >
          <div style={{ padding: '6px 10px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Dietary Preference
          </div>
          {PREFERENCE_OPTIONS.map((opt) => {
            const OptIcon = opt.icon;
            const isSelected = opt.id === currentPreference;
            return (
              <button
                key={opt.id}
                onClick={() => {
                  onSelectPreference(opt.id);
                  setIsOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isSelected ? opt.bg : 'transparent',
                  color: isSelected ? opt.color : 'var(--color-text-primary)',
                  fontWeight: isSelected ? 600 : 500,
                  fontSize: '0.875rem',
                  textAlign: 'left',
                  transition: 'background-color 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <OptIcon size={16} color={opt.color} />
                  <span>{opt.label}</span>
                </div>
                {isSelected && <Check size={16} color={opt.color} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
