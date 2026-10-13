import React from 'react';
import type { DietaryPreference } from '../../types';
import { Leaf, Egg, Drumstick, Sparkles, Check } from 'lucide-react';

interface PreferenceSelectorProps {
  selectedPreference: DietaryPreference;
  onSelect: (pref: DietaryPreference) => void;
}

const CARDS: { id: DietaryPreference; title: string; desc: string; icon: any; emoji: string }[] = [
  { id: 'vegan', title: 'Vegan', desc: '100% plant-based. Free from meat, poultry, fish, eggs, and dairy.', icon: Leaf, emoji: '🌱' },
  { id: 'vegetarian', title: 'Vegetarian', desc: 'Plant-based with dairy products allowed. No meat, poultry, or fish.', icon: Leaf, emoji: '🥬' },
  { id: 'eggitarian', title: 'Eggitarian', desc: 'Vegetarian diet enriched with eggs and dairy products.', icon: Egg, emoji: '🍳' },
  { id: 'non_vegetarian', title: 'Non-Vegetarian', desc: 'Includes chicken, meat, seafood, eggs, and all ingredients.', icon: Drumstick, emoji: '🍗' },
  { id: 'no_preference', title: 'No Preference', desc: 'Open to all recipes and cooking styles without restrictions.', icon: Sparkles, emoji: '✨' }
];

export const PreferenceSelector: React.FC<PreferenceSelectorProps> = ({ selectedPreference, onSelect }) => {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', width: '100%' }}>
      {CARDS.map((card) => {
        const isSelected = card.id === selectedPreference;
        return (
          <div
            key={card.id}
            onClick={() => onSelect(card.id)}
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: isSelected ? 'var(--color-brand-light)' : 'var(--color-bg-card)',
              border: isSelected ? '2px solid var(--color-brand)' : '1px solid var(--color-border)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
              position: 'relative'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <span style={{ fontSize: '1.75rem' }}>{card.emoji}</span>
              {isSelected && (
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: 'var(--color-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Check size={14} color="#FFF" />
                </div>
              )}
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
              {card.title}
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>
              {card.desc}
            </p>
          </div>
        );
      })}
    </div>
  );
};
