import React, { useEffect, useState } from 'react';
import { X, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import type { Paginated, PlanMeal, RecipeSummary } from '../../types/diet';
import { dietService, apiErrorMessage } from '../../services/diet';
import { FoodImage } from './FoodImage';
import { MacroRow } from './NutritionSummary';

interface Props {
  planId: string;
  meal?: PlanMeal | null;          // replace mode
  onClose: () => void;
  onPick: (recipe: RecipeSummary, extra: { slot?: string; time?: string }) => void;
}

const FOCI: [string, string][] = [['', 'Any'], ['high_protein', 'High protein'], ['high_fiber', 'High fibre'], ['low_carb', 'Low carb'],
  ['high_carb', 'Carb-rich'], ['pre_workout', 'Pre-training'], ['post_workout', 'Recovery'], ['low_energy_density', 'Lighter']];
const SLOTS: [string, string][] = [['breakfast', 'Breakfast'], ['morning_snack', 'Mid-morning snack'], ['lunch', 'Lunch'],
  ['pre_workout', 'Pre-training snack'], ['post_workout', 'Post-training meal'], ['evening_snack', 'Evening snack'], ['dinner', 'Dinner']];

export const RecipePicker: React.FC<Props> = ({ planId, meal, onClose, onPick }) => {
  const [q, setQ] = useState('');
  const [focus, setFocus] = useState('');
  const [cuisine, setCuisine] = useState('');
  const [slot, setSlot] = useState('evening_snack');
  const [time, setTime] = useState('16:30');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<RecipeSummary> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await dietService.alternatives(planId, {
          meal_id: meal?.id, slot: meal ? undefined : slot, q: q.trim() || undefined, focus: focus || undefined,
          cuisine: cuisine || undefined, page,
        });
        if (!cancelled) setData(res);
      } catch (e) {
        if (!cancelled) setError(apiErrorMessage(e, 'Could not load recipes.'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => { cancelled = true; window.clearTimeout(t); };
  }, [planId, meal, q, focus, cuisine, slot, page]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="diet-modal-backdrop" onClick={onClose} role="presentation">
      <div className="diet-modal" role="dialog" aria-modal="true" aria-label={meal ? `Replace ${meal.name}` : 'Add a meal'}
        onClick={e => e.stopPropagation()}>
        <div className="diet-modal-head">
          <div>
            <div className="diet-eyebrow">{meal ? `Replace ${meal.label.toLowerCase()}` : 'Add a meal'}</div>
            <div style={{ fontWeight: 700, color: 'var(--color-text-primary)' }}>
              {meal ? `Currently: ${meal.name}` : 'Choose a recipe that fits your plan'}
            </div>
          </div>
          <button className="diet-icon-btn" onClick={onClose} aria-label="Close"><X size={15} /></button>
        </div>
        <div className="diet-modal-body">
          <div className="form-grid" style={{ marginBottom: 12 }}>
            <div className="form-field" style={{ gridColumn: 'span 2' }}>
              <label htmlFor="rp-q">Search by name or ingredient</label>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: 9, top: 9, color: 'var(--color-text-muted)' }} />
                <input id="rp-q" className="diet-input" style={{ paddingLeft: 28 }} value={q} placeholder="e.g. tofu, dal, oats"
                  onChange={e => { setQ(e.target.value); setPage(1); }} />
              </div>
            </div>
            <div className="form-field">
              <label htmlFor="rp-c">Cuisine</label>
              <select id="rp-c" className="diet-select" value={cuisine} onChange={e => { setCuisine(e.target.value); setPage(1); }}>
                <option value="">Any</option><option value="indian">Indian</option><option value="italian">Italian</option>
                <option value="continental">Continental</option>
              </select>
            </div>
            {!meal && (
              <>
                <div className="form-field">
                  <label htmlFor="rp-s">Meal type</label>
                  <select id="rp-s" className="diet-select" value={slot} onChange={e => { setSlot(e.target.value); setPage(1); }}>
                    {SLOTS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="rp-t">Time</label>
                  <input id="rp-t" type="time" className="diet-input" value={time} onChange={e => setTime(e.target.value)} />
                </div>
              </>
            )}
          </div>
          <div className="diet-filter" style={{ marginTop: 0, marginBottom: 12 }}>
            {FOCI.map(([k, l]) => (
              <button key={k} className={`diet-chip ${focus === k ? 'active' : ''}`} onClick={() => { setFocus(k); setPage(1); }}>{l}</button>
            ))}
          </div>
          <p className="diet-card-caption" style={{ marginBottom: 10 }}>
            Only recipes that match your dietary preference, allergies and disliked foods are shown.
          </p>
          {error && <div className="diet-error">{error}</div>}
          {loading && !data && <div className="picker-grid">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 230 }} />)}</div>}
          {data && data.items.length === 0 && !loading && <p className="diet-subtitle">No recipes match. Try another search or filter.</p>}
          {data && (
            <div className="picker-grid" style={{ opacity: loading ? 0.6 : 1 }}>
              {data.items.map(r => (
                <div className="picker-item" key={r.id}>
                  <FoodImage src={r.image_url} alt={`Photo of ${r.name}`} />
                  <div className="picker-item-body">
                    <div style={{ fontWeight: 700, fontSize: '0.86rem', color: 'var(--color-text-primary)' }}>{r.name}</div>
                    <div className="diet-card-caption">Per serving · {r.diet_label}{r.total_min ? ` · ${r.total_min} min` : ''}</div>
                    <MacroRow values={r.nutrition_per_serving} compact />
                    <button className="diet-btn diet-btn-primary diet-btn-sm" style={{ marginTop: 'auto' }}
                      onClick={() => onPick(r, meal ? {} : { slot, time })}>
                      {meal ? 'Use this recipe' : 'Add to plan'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {data && data.pages > 1 && (
            <div className="diet-actions" style={{ justifyContent: 'center', marginTop: 14 }}>
              <button className="diet-icon-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)} aria-label="Previous page"><ChevronLeft size={14} /></button>
              <span className="diet-card-caption">Page {data.page} of {data.pages} · {data.total} recipes</span>
              <button className="diet-icon-btn" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)} aria-label="Next page"><ChevronRight size={14} /></button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
