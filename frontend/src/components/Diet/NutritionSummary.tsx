import React from 'react';
import type { NutrientValues, NutritionResult, PlanTotals, TargetRange, Targets } from '../../types/diet';

const LABELS: Record<string, string> = { kcal: 'Calories', protein: 'Protein', carbs: 'Carbs', fat: 'Fat', fiber: 'Fibre' };
const UNITS: Record<string, string> = { kcal: 'kcal', protein: 'g', carbs: 'g', fat: 'g', fiber: 'g' };

export function fmt(v: number | null | undefined, key: string): string {
  if (v === null || v === undefined) return '—';
  return key === 'kcal' ? `${Math.round(v)}` : `${Math.round(v * 10) / 10}`;
}

/** Inline macro list for a meal or recipe; missing values are shown as "Not available", never guessed. */
export const MacroRow: React.FC<{ values?: NutrientValues | null; nutrition?: NutritionResult | null; compact?: boolean }> = ({
  values, nutrition, compact,
}) => {
  if (nutrition && nutrition.status === 'unavailable') {
    return <div className="macro-row"><span className="macro-na">Nutrition not available — {nutrition.reason}</span></div>;
  }
  const v = values || nutrition?.values || {};
  return (
    <div className="macro-row" style={compact ? { fontSize: '0.74rem', gap: '4px 10px' } : undefined}>
      {(['kcal', 'protein', 'carbs', 'fat', 'fiber'] as const).map(k => (
        <span key={k}>
          {v[k] === null || v[k] === undefined
            ? <><span className="macro-na">{LABELS[k]} n/a</span></>
            : <><b>{fmt(v[k], k)}</b> {k === 'kcal' ? 'kcal' : `g ${LABELS[k].toLowerCase()}`}</>}
        </span>
      ))}
    </div>
  );
};

function targetFor(key: string, targets: Targets): TargetRange | null {
  if (key === 'kcal') return targets.energy;
  return (targets as unknown as Record<string, TargetRange | null>)[key] ?? null;
}

/** Daily totals compared with the user's estimated targets. */
export const DailyTotals: React.FC<{ totals: PlanTotals; targets: Targets }> = ({ totals, targets }) => {
  return (
    <div className="nutri-grid">
      {(['kcal', 'protein', 'carbs', 'fat', 'fiber'] as const).map(k => {
        const v = totals.values[k];
        const t = targetFor(k, targets);
        let pct = 0;
        let cls = '';
        let tText = 'No personal target yet';
        if (t && (t.low !== null || t.high !== null)) {
          const lo = t.low ?? 0;
          const hi = t.high ?? null;
          tText = hi !== null && t.low !== null ? `Target ${Math.round(lo)}–${Math.round(hi)} ${UNITS[k]}`
            : t.low !== null ? `At least ${Math.round(lo)} ${UNITS[k]}` : `At most ${Math.round(hi as number)} ${UNITS[k]}`;
          const ref = hi ?? lo * 1.2;
          pct = v !== null && v !== undefined && ref ? Math.min(100, (v / ref) * 100) : 0;
          if (v !== null && v !== undefined) {
            if (t.low !== null && v < t.low) cls = 'low';
            else if (hi !== null && v > hi) cls = 'high';
          }
        }
        const incomplete = totals.complete && totals.complete[k] === false;
        return (
          <div className="nutri-tile" key={k}>
            <div className="label">{LABELS[k]}</div>
            <div className="value">{fmt(v, k)}<small>{UNITS[k]}</small></div>
            <div className="target" title={t?.basis}>{tText}{incomplete ? ' · partial data' : ''}</div>
            <div className="nutri-bar" aria-hidden="true"><span className={cls} style={{ width: `${pct}%` }} /></div>
          </div>
        );
      })}
    </div>
  );
};

export const SourceBadge: React.FC<{ nutrition?: NutritionResult | null }> = ({ nutrition }) => {
  if (!nutrition) return null;
  if (nutrition.status === 'source') return <span className="diet-chip diet-chip-sage" title={nutrition.basis}>Recipe data</span>;
  if (nutrition.status === 'estimate') return <span className="diet-chip diet-chip-warn" title={nutrition.basis}>Calculated estimate</span>;
  return <span className="diet-chip diet-chip-danger" title={nutrition.reason}>Not available</span>;
};
