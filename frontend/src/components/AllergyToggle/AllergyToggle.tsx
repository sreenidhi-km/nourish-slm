import React, { useEffect, useRef, useState } from 'react';
import { ShieldAlert, ShieldCheck, ChevronDown, Check } from 'lucide-react';

export const ALLERGY_OPTIONS: { key: string; label: string; hint: string }[] = [
  { key: 'peanut', label: 'Peanut', hint: 'peanuts, peanut butter, groundnut' },
  { key: 'tree_nuts', label: 'Tree nuts', hint: 'almond, cashew, walnut, pistachio' },
  { key: 'dairy', label: 'Dairy / lactose', hint: 'milk, paneer, ghee, curd, cheese' },
  { key: 'egg', label: 'Egg', hint: 'eggs, mayonnaise' },
  { key: 'gluten', label: 'Gluten', hint: 'wheat, atta, maida, bread, pasta' },
  { key: 'soy', label: 'Soy', hint: 'tofu, soy sauce, soy milk' },
  { key: 'fish', label: 'Fish', hint: 'salmon, tuna, fish sauce' },
  { key: 'shellfish', label: 'Shellfish', hint: 'prawns, shrimp, crab' },
  { key: 'sesame', label: 'Sesame', hint: 'sesame seeds, tahini, til' },
  { key: 'mustard', label: 'Mustard', hint: 'mustard seeds, mustard oil' },
];

interface AllergyToggleProps {
  selected: string[];
  onChange: (allergies: string[]) => void;
}

/** Header control for the user's allergies. Every chatbot recipe is checked against this list. */
export const AllergyToggle: React.FC<AllergyToggleProps> = ({ selected, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const toggle = (key: string) =>
    onChange(selected.includes(key) ? selected.filter(k => k !== key) : [...selected, key]);

  const active = selected.length > 0;
  const color = active ? '#B45309' : 'var(--color-text-secondary)';
  const label = !active ? 'No allergies'
    : selected.length === 1 ? (ALLERGY_OPTIONS.find(o => o.key === selected[0])?.label || '1 allergy')
    : `${selected.length} allergies`;

  return (
    <div style={{ position: 'relative' }} ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        title="Allergy check: recipes are made free of the allergens you select"
        style={{
          display: 'flex', alignItems: 'center', gap: '7px', padding: '8px 12px',
          backgroundColor: active ? '#FEF3C7' : 'var(--color-bg-elevated)',
          border: `1px solid ${active ? '#F59E0B55' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-md)', color, fontWeight: 600, fontSize: '0.85rem',
          boxShadow: 'var(--shadow-sm)', whiteSpace: 'nowrap',
        }}
      >
        {active ? <ShieldAlert size={16} color={color} /> : <ShieldCheck size={16} color={color} />}
        <span className="header-optional">{label}</span>
        <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {open && (
        <div
          className="animate-fade-in"
          role="menu"
          style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0, width: '290px',
            backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', zIndex: 100, padding: '8px',
          }}
        >
          <div style={{ padding: '4px 8px 8px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Allergy check
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginTop: 3, lineHeight: 1.4 }}>
              Recipes will avoid these. Ingredients that contain them are swapped for safe alternatives.
            </div>
          </div>
          <div style={{ maxHeight: 330, overflowY: 'auto' }}>
            {ALLERGY_OPTIONS.map(opt => {
              const on = selected.includes(opt.key);
              return (
                <button
                  key={opt.key}
                  role="menuitemcheckbox"
                  aria-checked={on}
                  onClick={() => toggle(opt.key)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px', width: '100%', padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)', textAlign: 'left',
                    backgroundColor: on ? '#FEF3C7' : 'transparent',
                  }}
                >
                  <span style={{
                    width: 18, height: 18, borderRadius: 5, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: `1.5px solid ${on ? '#D97706' : 'var(--color-border)'}`, backgroundColor: on ? '#D97706' : 'transparent',
                  }}>
                    {on && <Check size={12} color="#fff" strokeWidth={3} />}
                  </span>
                  <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <span style={{ fontSize: '0.86rem', fontWeight: 600, color: on ? '#92400E' : 'var(--color-text-primary)' }}>{opt.label}</span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>{opt.hint}</span>
                  </span>
                </button>
              );
            })}
          </div>
          {active && (
            <button onClick={() => onChange([])}
              style={{ width: '100%', marginTop: 6, padding: '7px', fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text-secondary)', borderTop: '1px solid var(--color-border)' }}>
              Clear all
            </button>
          )}
          <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', padding: '6px 8px 2px', lineHeight: 1.4 }}>
            Detection uses ingredient names. Always check labels on packaged foods.
          </div>
        </div>
      )}
    </div>
  );
};
