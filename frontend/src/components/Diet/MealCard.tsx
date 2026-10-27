import React, { useEffect, useRef, useState } from 'react';
import {
  Minus, Plus, Repeat, Trash2, ChevronDown, ChevronUp, Clock, RotateCcw, Undo2, X, Check, ExternalLink, Info, Search,
} from 'lucide-react';
import type { PlanIngredient, PlanMeal, UsdaFood } from '../../types/diet';
import { FoodImage } from './FoodImage';
import { MacroRow, SourceBadge } from './NutritionSummary';
import { dietService } from '../../services/diet';

interface MealCardProps {
  meal: PlanMeal;
  busy: boolean;
  units: string[];
  onEdit: (op: Record<string, unknown>) => Promise<boolean>;
  onReplace: (meal: PlanMeal) => void;
}

const DIET_CHIP: Record<string, string> = { vegan: '🌱 Vegan', vegetarian: '🥬 Vegetarian', eggitarian: '🍳 Eggetarian', non_vegetarian: '🍗 Non-veg' };
const TAG_LABEL: Record<string, string> = { high_protein: 'High protein', high_fiber: 'High fibre', low_carb: 'Low carb',
  high_carb: 'Carb-rich', low_energy_density: 'Filling, lighter', pre_workout: 'Pre-training friendly', post_workout: 'Recovery friendly' };

/** USDA food typeahead: lets the user pick the exact nutrition record for a new ingredient. */
const UsdaPicker: React.FC<{ value: string; onChange: (v: string) => void; onPick: (f: UsdaFood) => void; placeholder?: string; label: string }> = ({
  value, onChange, onPick, placeholder, label,
}) => {
  const [results, setResults] = useState<UsdaFood[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => {
    window.clearTimeout(timer.current);
    if (value.trim().length < 2 || !open) { setResults([]); return; }
    timer.current = window.setTimeout(async () => {
      try { setResults(await dietService.searchIngredients(value.trim())); } catch { setResults([]); }
    }, 300);
    return () => window.clearTimeout(timer.current);
  }, [value, open]);
  return (
    <div style={{ position: 'relative' }}>
      <input value={value} placeholder={placeholder} aria-label={label}
        onChange={e => { onChange(e.target.value); setOpen(true); }} onBlur={() => window.setTimeout(() => setOpen(false), 200)} />
      {open && results.length > 0 && (
        <div className="usda-results" style={{ position: 'absolute', zIndex: 20, left: 0, right: 0 }} role="listbox">
          {results.map(f => (
            <button type="button" key={f.fdc_id} role="option" aria-selected="false"
              onMouseDown={e => e.preventDefault()} onClick={() => { onPick(f); setOpen(false); }}>
              {f.description}
              <small>{f.per_100g.kcal} kcal · {f.per_100g.protein} g protein per 100 g · {f.source}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const IngredientRow: React.FC<{ ing: PlanIngredient; meal: PlanMeal; busy: boolean; units: string[];
  onEdit: (op: Record<string, unknown>) => Promise<boolean> }> = ({ ing, meal, busy, units, onEdit }) => {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(ing.name);
  const [qty, setQty] = useState(ing.quantity);
  const [unit, setUnit] = useState(ing.unit);
  const [fdc, setFdc] = useState<number | undefined>(ing.fdc_id);
  useEffect(() => { setName(ing.name); setQty(ing.quantity); setUnit(ing.unit); setFdc(ing.fdc_id); }, [ing]);
  const removed = ing.status === 'removed';
  const unitOptions = Array.from(new Set([unit, ...units].filter(u => u !== undefined)));

  if (!editing) {
    return (
      <tr className={`${removed ? 'removed' : ''} ${ing.status === 'modified' || ing.status === 'added' ? 'changed' : ''}`}>
        <td className="ing-name-cell" style={{ color: 'var(--color-text-primary)' }}>
          {ing.line || ing.name}
          {ing.status === 'modified' && ing.original && <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>was: {ing.original.line}</div>}
          {ing.status === 'added' && <span className="diet-chip diet-chip-brand" style={{ marginLeft: 6 }}>added</span>}
        </td>
        <td className="ing-actions-cell">
          <div className="ing-actions">
            {!removed && <button className="diet-btn diet-btn-sm" disabled={busy} onClick={() => setEditing(true)}
              aria-label={`Edit ${ing.name}`}>Edit</button>}
            {ing.status !== 'original' && (
              <button className="diet-icon-btn" disabled={busy} title="Undo change" aria-label={`Undo change to ${ing.name}`}
                onClick={() => onEdit({ op: 'restore_ingredient', meal_id: meal.id, index: ing.idx })}><Undo2 size={13} /></button>
            )}
            {!removed && (
              <button className="diet-icon-btn" disabled={busy} title="Remove ingredient" aria-label={`Remove ${ing.name}`}
                onClick={() => onEdit({ op: 'remove_ingredient', meal_id: meal.id, index: ing.idx })}><Trash2 size={13} /></button>
            )}
          </div>
        </td>
      </tr>
    );
  }
  return (
    <tr className="changed">
      <td className="ing-name-cell" colSpan={2}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2.4fr) minmax(0,0.8fr) minmax(0,0.9fr) auto', gap: 6, alignItems: 'center' }}>
          <UsdaPicker label="Ingredient" value={name} onChange={v => { setName(v); setFdc(undefined); }}
            onPick={f => { setName(f.description); setFdc(f.fdc_id); if (!unit || !['g', 'kg', 'oz', 'lb'].includes(unit)) setUnit('g'); }} />
          <input value={qty} onChange={e => setQty(e.target.value)} aria-label="Quantity" placeholder="Qty" inputMode="decimal" />
          <select value={unit} onChange={e => setUnit(e.target.value)} aria-label="Unit">
            {unitOptions.map(u => <option key={u} value={u}>{u || '(count)'}</option>)}
          </select>
          <div className="ing-actions">
            <button className="diet-icon-btn" disabled={busy} title="Save" aria-label="Save ingredient"
              onClick={async () => {
                const op: Record<string, unknown> = { op: 'update_ingredient', meal_id: meal.id, index: ing.idx, quantity: qty, unit };
                if (name !== ing.name || fdc !== ing.fdc_id) op.name = name;
                if (fdc) op.fdc_id = fdc;
                if (await onEdit(op)) setEditing(false);
              }}><Check size={13} /></button>
            <button className="diet-icon-btn" title="Cancel" aria-label="Cancel" onClick={() => setEditing(false)}><X size={13} /></button>
          </div>
        </div>
        {fdc && <div style={{ fontSize: '0.68rem', color: 'var(--color-sage)', marginTop: 3 }}>Using USDA record #{fdc}</div>}
      </td>
    </tr>
  );
};

export const MealCard: React.FC<MealCardProps> = ({ meal, busy, units, onEdit, onReplace }) => {
  const [open, setOpen] = useState(false);
  const [time, setTime] = useState(meal.time);
  const [newIng, setNewIng] = useState({ name: '', quantity: '100', unit: 'g', fdc_id: undefined as number | undefined });
  useEffect(() => setTime(meal.time), [meal.time]);
  const changed = meal.ingredients.some(i => i.status !== 'original');
  const n = meal.nutrition;
  const unavailable = n?.status === 'unavailable';

  return (
    <article className="meal-card" aria-label={`${meal.label}: ${meal.name}`}>
      <div className="meal-main">
        <FoodImage src={meal.image_url} alt={`Photo of ${meal.name}`} />
        <div style={{ minWidth: 0 }}>
          <div className="meal-head">
            <div className="meal-slot">
              <Clock size={12} />
              <input type="time" className="meal-time-input" value={time} aria-label={`Time for ${meal.label}`}
                onChange={e => setTime(e.target.value)}
                onBlur={() => { if (time && time !== meal.time) onEdit({ op: 'set_time', meal_id: meal.id, time }); }} />
              <span>{meal.label}</span>
            </div>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              <SourceBadge nutrition={n} />
              {DIET_CHIP[meal.diet] && <span className="diet-chip">{DIET_CHIP[meal.diet]}</span>}
            </div>
          </div>
          <h4 className="meal-name">{meal.name}</h4>
          <MacroRow nutrition={n} />
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 6 }}>
            {meal.focus_tags.filter(t => TAG_LABEL[t]).slice(0, 3).map(t => <span key={t} className="diet-chip diet-chip-brand">{TAG_LABEL[t]}</span>)}
            {meal.allergens.length > 0 && <span className="diet-chip diet-chip-warn" title="Detected from ingredient names">Contains: {meal.allergens.join(', ').replace(/_/g, ' ')}</span>}
            {meal.total_min > 0 && <span className="diet-chip">{meal.total_min} min</span>}
          </div>
          <div className="meal-tools">
            <div className="stepper" aria-label="Servings">
              <button disabled={busy || meal.servings <= 0.25} aria-label="Fewer servings"
                onClick={() => onEdit({ op: 'set_servings', meal_id: meal.id, servings: Math.max(0.25, meal.servings - 0.25) })}><Minus size={13} /></button>
              <span>{meal.servings} serving{meal.servings === 1 ? '' : 's'}</span>
              <button disabled={busy || meal.servings >= 4} aria-label="More servings"
                onClick={() => onEdit({ op: 'set_servings', meal_id: meal.id, servings: Math.min(4, meal.servings + 0.25) })}><Plus size={13} /></button>
            </div>
            <button className="diet-btn diet-btn-sm" disabled={busy} onClick={() => onReplace(meal)}><Repeat size={13} /> Replace</button>
            <button className="diet-btn diet-btn-sm" onClick={() => setOpen(o => !o)} aria-expanded={open}>
              {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />} {open ? 'Hide details' : 'Recipe & edit'}
            </button>
            <button className="diet-btn diet-btn-sm diet-btn-ghost diet-btn-danger" disabled={busy}
              onClick={() => { if (window.confirm(`Remove ${meal.name} from this plan?`)) onEdit({ op: 'remove_meal', meal_id: meal.id }); }}>
              <Trash2 size={13} /> Remove
            </button>
          </div>
        </div>
      </div>

      {open && (
        <div className="meal-detail">
          <div className="meal-reason"><Info size={13} style={{ verticalAlign: '-2px', marginRight: 5 }} />{meal.reason}</div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: '0.76rem', color: 'var(--color-text-secondary)', marginBottom: 10 }}>
            <span>Recipe makes: <b>{meal.recipe_servings ? `${meal.recipe_servings} servings` : 'not stated'}</b></span>
            {meal.serving_size_g ? <span>Serving size: <b>{Math.round(meal.serving_size_g)} g</b></span> : null}
            {meal.prep_min > 0 && <span>Prep: <b>{meal.prep_min} min</b></span>}
            {meal.cook_min > 0 && <span>Cook: <b>{meal.cook_min} min</b></span>}
          </div>
          <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginBottom: 8 }}>
            Per serving (published): {Math.round(meal.source_per_serving.kcal || 0)} kcal · basis: {n?.basis || n?.reason}
          </div>
          {unavailable && <div className="meal-notice warn">{n.reason}</div>}
          {n?.status === 'estimate' && <div className="meal-notice info">{(n.notes || []).join(' ')}</div>}
          {meal.diet_verify.length > 0 && (
            <div className="meal-notice warn">Check: {meal.diet_verify.map(v => `${v.ingredient} — ${v.reason}`).join('; ')}</div>
          )}

          <h5 style={{ marginTop: 14 }}>Ingredients {meal.recipe_servings ? `(for ${meal.recipe_servings} servings)` : ''}</h5>
          <table className="ing-table">
            <thead><tr><th style={{ textAlign: 'left' }} /><th /></tr></thead>
            <tbody>
              {meal.ingredients.map(ing => (
                <IngredientRow key={`${meal.id}-${ing.idx}`} ing={ing} meal={meal} busy={busy} units={units} onEdit={onEdit} />
              ))}
              <tr>
                <td className="ing-name-cell" colSpan={2}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2.4fr) minmax(0,0.8fr) minmax(0,0.9fr) auto', gap: 6, alignItems: 'center', marginTop: 6 }}>
                    <UsdaPicker label="New ingredient" placeholder="Add ingredient (search USDA)…" value={newIng.name}
                      onChange={v => setNewIng(s => ({ ...s, name: v, fdc_id: undefined }))}
                      onPick={f => setNewIng(s => ({ ...s, name: f.description, fdc_id: f.fdc_id }))} />
                    <input value={newIng.quantity} onChange={e => setNewIng(s => ({ ...s, quantity: e.target.value }))} aria-label="New ingredient quantity" />
                    <select value={newIng.unit} onChange={e => setNewIng(s => ({ ...s, unit: e.target.value }))} aria-label="New ingredient unit">
                      {units.map(u => <option key={u} value={u}>{u}</option>)}
                    </select>
                    <button className="diet-btn diet-btn-sm" disabled={busy || !newIng.name.trim()}
                      onClick={async () => {
                        const ok = await onEdit({ op: 'add_ingredient', meal_id: meal.id, name: newIng.name, quantity: newIng.quantity,
                          unit: newIng.unit, fdc_id: newIng.fdc_id });
                        if (ok) setNewIng({ name: '', quantity: '100', unit: 'g', fdc_id: undefined });
                      }}><Search size={12} /> Add</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          {changed && (
            <button className="diet-btn diet-btn-sm" style={{ marginTop: 8 }} disabled={busy}
              onClick={() => onEdit({ op: 'reset_meal', meal_id: meal.id })}><RotateCcw size={12} /> Reset to original recipe</button>
          )}
          {(n?.changes || []).length > 0 && (
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 8, lineHeight: 1.5 }}>
              {(n.changes || []).map((c, i) => (
                <div key={i}>• {c.name}: {c.after?.status === 'ok' ? `${c.after.grams} g → USDA "${c.after.match?.description}" (${c.after.conversion})`
                  : c.after ? `not calculable (${c.after.reason})` : ''}
                  {c.before && c.before.status === 'ok' ? ` · original ${c.before.grams} g "${c.before.match?.description}"` : c.before ? ` · original: ${c.before.reason}` : ''}</div>
              ))}
            </div>
          )}

          <h5 style={{ marginTop: 16 }}>Instructions</h5>
          <ol className="steps-list">{meal.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <a href={meal.source_url} target="_blank" rel="noreferrer" className="diet-back" style={{ marginTop: 10 }}>
            View the original recipe and photo on Food.com <ExternalLink size={12} />
          </a>
        </div>
      )}
    </article>
  );
};
