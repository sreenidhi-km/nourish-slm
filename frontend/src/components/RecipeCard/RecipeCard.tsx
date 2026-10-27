import React, { useState } from 'react';
import type { RecipeData, RecipeValidation, RecipeNutrition, AllergyCheck } from '../../types';
import { Clock, Users, Globe, ShieldCheck, Bookmark, Heart, Copy, Check, ChefHat, Sparkles, Database, Flame, ExternalLink, ChevronDown, ChevronUp, ShieldAlert, ArrowRight } from 'lucide-react';
import { FoodImage } from '../Diet/FoodImage';

const MACRO_COLORS = { protein: '#2D6A4F', carbs: '#E09F3E', fat: '#C8553D' };

/** Per-serving nutrition panel. Values come only from the backend; missing values say "Not available". */
const NutritionPanel: React.FC<{ nutrition?: RecipeNutrition; compact?: boolean }> = ({ nutrition, compact }) => {
  const [showHow, setShowHow] = useState(false);
  if (!nutrition) return null;
  const vals = (nutrition.values || {}) as Record<string, number | null | undefined>;
  const num = (k: string) => (typeof vals[k] === 'number' ? (vals[k] as number) : null);
  const kcal = num('kcal');
  const macros: [keyof typeof MACRO_COLORS, string, number | null, number][] = [
    ['protein', 'Protein', num('protein'), 4], ['carbs', 'Carbs', num('carbs'), 4], ['fat', 'Fat', num('fat'), 9],
  ];
  const macroKcal = macros.reduce((t, [, , g, f]) => t + (g || 0) * f, 0);
  const approx = nutrition.approximate;

  return (
    <div style={{
      marginBottom: compact ? '10px' : '20px', padding: compact ? '10px 12px' : '14px 16px', borderRadius: 'var(--radius-md)',
      background: 'linear-gradient(135deg, rgba(224,159,62,0.08), rgba(45,106,79,0.06))', border: '1px solid var(--color-border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <h4 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Flame size={13} color="var(--color-brand)" /> Nutrition per serving
        </h4>
        {nutrition.status !== 'unavailable' && (
          <span style={{
            fontSize: '0.66rem', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', textTransform: 'uppercase', letterSpacing: '0.4px',
            backgroundColor: approx ? 'rgba(224,159,62,0.15)' : nutrition.status === 'source' ? 'rgba(45,106,79,0.12)' : 'rgba(79,70,229,0.1)',
            color: approx ? '#B7791F' : nutrition.status === 'source' ? 'var(--color-sage)' : '#4F46E5',
          }}>
            {approx ? 'Approximate' : nutrition.status === 'source' ? 'Published values' : 'Calculated'}
          </span>
        )}
      </div>

      {nutrition.status === 'unavailable' ? (
        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--color-bg-main)', border: '1px dashed var(--color-border)' }}>
          Not available — {nutrition.reason}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'stretch', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ minWidth: 96, padding: '8px 12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border)', textAlign: 'center' }}>
              <div style={{ fontSize: compact ? '1.3rem' : '1.75rem', fontWeight: 800, color: 'var(--color-text-primary)', lineHeight: 1.1, fontFamily: 'var(--font-serif)' }}>
                {kcal === null ? '–' : `${approx ? '~' : ''}${Math.round(kcal)}`}
              </div>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>kcal</div>
            </div>
            <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8 }}>
              {macroKcal > 0 && (
                <div style={{ display: 'flex', height: 8, borderRadius: 99, overflow: 'hidden', backgroundColor: 'var(--color-bg-main)' }}
                  aria-label="Share of calories from protein, carbohydrates and fat">
                  {macros.map(([k, , g, f]) => (g ? <div key={k} style={{ width: `${(g * f / macroKcal) * 100}%`, backgroundColor: MACRO_COLORS[k] }} /> : null))}
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 6 }}>
                {[...macros.map(([k, label, g]) => [k, label, g] as [string, string, number | null]), ['fiber', 'Fibre', num('fiber')] as [string, string, number | null]].map(([k, label, g]) => (
                  <div key={k}>
                    <div style={{ fontSize: '0.64rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {k !== 'fiber' && <span style={{ width: 7, height: 7, borderRadius: 99, backgroundColor: MACRO_COLORS[k as keyof typeof MACRO_COLORS] }} />}
                      {label}
                    </div>
                    <div style={{ fontSize: compact ? '0.86rem' : '0.98rem', fontWeight: 700, color: g === null ? 'var(--color-text-muted)' : 'var(--color-text-primary)' }}>
                      {g === null ? 'n/a' : `${g} g`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          {!compact && (
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: 8 }}>
              {nutrition.source_label || nutrition.basis}
              {approx && (
                <button onClick={() => setShowHow(v => !v)} style={{ marginLeft: 6, fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-brand)', textDecoration: 'underline' }}>
                  {showHow ? 'Hide details' : 'How is this calculated?'}
                </button>
              )}
            </div>
          )}
          {showHow && approx && (
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-secondary)', marginTop: 6, lineHeight: 1.5, padding: '8px 10px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border)' }}>
              The model lists ingredients without amounts, so each one uses the typical amount real Food.com recipes use per
              serving (shown in the ingredient list), for {nutrition.servings_assumed || 4} servings. Nutrient values come from USDA FoodData Central.
              {nutrition.not_counted && nutrition.not_counted.length > 0 && <> Not counted (no USDA match): {nutrition.not_counted.join(', ')}.</>}
            </div>
          )}
        </>
      )}
    </div>
  );
};

/** Result of the allergy checkpoint: swaps made, or a warning for anything that could not be swapped. */
const AllergyPanel: React.FC<{ check?: AllergyCheck }> = ({ check }) => {
  if (!check || !check.checked || check.checked.length === 0) return null;
  const ok = check.passed;
  return (
    <div role={ok ? 'status' : 'alert'} style={{
      marginBottom: '18px', padding: '12px 14px', borderRadius: 'var(--radius-md)',
      backgroundColor: ok ? 'rgba(45,106,79,0.07)' : 'rgba(220,38,38,0.07)',
      border: `1px solid ${ok ? 'rgba(45,106,79,0.25)' : 'rgba(220,38,38,0.35)'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: '0.85rem', color: ok ? 'var(--color-sage)' : '#B91C1C' }}>
        {ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
        {ok ? `Allergy check passed: free of ${check.checked.join(', ')}` : `Allergy warning: contains ${Array.from(new Set(check.remaining.flatMap(r => r.allergens))).join(', ')}`}
      </div>
      {check.substitutions.length > 0 && (
        <ul style={{ margin: '8px 0 0', paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {check.substitutions.map((sub, i) => (
            <li key={i} style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ textDecoration: 'line-through', opacity: 0.75 }}>{sub.ingredient}</span>
              <ArrowRight size={12} />
              <strong style={{ color: 'var(--color-text-primary)' }}>{sub.replacement}</strong>
              <span style={{ fontSize: '0.68rem', padding: '1px 7px', borderRadius: 99, backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 600 }}>{sub.allergen}</span>
            </li>
          ))}
        </ul>
      )}
      {!ok && (
        <div style={{ fontSize: '0.8rem', color: '#B91C1C', marginTop: 6 }}>
          No safe swap was found for: {check.remaining.map(r => r.ingredient).join(', ')}. Leave these out or choose another recipe.
        </div>
      )}
      <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', marginTop: 6 }}>{check.note}</div>
    </div>
  );
};

interface RecipeCardProps {
  recipe: RecipeData;
  validation?: RecipeValidation;
  onSave?: (recipe: RecipeData) => void;
  onFavorite?: (recipe: RecipeData) => void;
  onRegenerate?: () => void;
}

function getDietBadge(diet: string): { bg: string; color: string; label: string } {
  switch ((diet || '').toLowerCase()) {
    case 'vegan':
      return { bg: 'rgba(21, 128, 61, 0.12)', color: '#15803D', label: '🌱 Vegan' };
    case 'vegetarian':
      return { bg: 'rgba(22, 163, 74, 0.12)', color: '#16A34A', label: '🥬 Vegetarian' };
    case 'eggitarian':
      return { bg: 'rgba(217, 119, 6, 0.12)', color: '#D97706', label: '🍳 Eggitarian' };
    case 'non_vegetarian':
      return { bg: 'rgba(220, 38, 38, 0.12)', color: '#DC2626', label: '🍗 Non-Vegetarian' };
    default:
      return { bg: 'rgba(79, 70, 229, 0.12)', color: '#4F46E5', label: '✨ No Preference' };
  }
}

function getCuisineEmoji(cuisine: string): string {
  const c = (cuisine || '').toLowerCase();
  if (c === 'indian') return '🇮🇳';
  if (c === 'italian') return '🇮🇹';
  if (c === 'continental') return '🌍';
  return '🍽️';
}

export const RecipeCard: React.FC<RecipeCardProps> = ({
  recipe,
  validation,
  onSave,
  onFavorite,
}) => {
  const [checkedIngredients, setCheckedIngredients] = useState<Record<number, boolean>>({});
  const [isSaved, setIsSaved] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showRelated, setShowRelated] = useState(false);

  // Guard: ensure recipe exists and has required fields
  if (!recipe || !recipe.title) return null;

  const toggleIngredient = (index: number) => {
    setCheckedIngredients(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const handleCopy = async () => {
    const ingList = ((recipe.ingredient_quantities && recipe.ingredient_quantities.length ? recipe.ingredient_quantities : recipe.ingredients) || []).map(i => `• ${i}`).join('\n');
    const stepList = (recipe.instructions || []).map((step, i) => `${i + 1}. ${step}`).join('\n');
    const text = [
      `🍽️ ${recipe.title}`,
      `Cuisine: ${recipe.cuisine || 'General'} | Diet: ${(recipe.diet_type || '').replace('_', ' ')}`,
      `Prep: ${recipe.prep_time || '–'} | Cook: ${recipe.cook_time || '–'} | Serves: ${recipe.servings || '–'}`,
      '',
      'INGREDIENTS',
      ingList,
      '',
      'INSTRUCTIONS',
      stepList,
      ...(recipe.nutrition && recipe.nutrition.status !== 'unavailable' && recipe.nutrition.values
        ? ['', `NUTRITION (per serving): ${Math.round(recipe.nutrition.values.kcal || 0)} kcal, ${recipe.nutrition.values.protein ?? '–'} g protein, ${recipe.nutrition.values.carbs ?? '–'} g carbs, ${recipe.nutrition.values.fat ?? '–'} g fat`]
        : []),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for older browsers
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  };

  const handleSaveClick = () => {
    if (onSave) onSave(recipe);
    setIsSaved(true);
  };

  const handleFavoriteClick = () => {
    if (onFavorite) onFavorite(recipe);
    setIsFavorited(f => !f);
  };

  const dietBadge = getDietBadge(recipe.diet_type);
  const cuisineEmoji = getCuisineEmoji(recipe.cuisine);

  const ingredients = (recipe.ingredient_quantities && recipe.ingredient_quantities.length ? recipe.ingredient_quantities : recipe.ingredients) || [];
  const related = recipe.related_recipe;
  const instructions = recipe.instructions || [];
  const servings = recipe.servings || '';

  const actionBtnStyle = (active?: boolean, activeColor?: string): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    padding: '6px 12px',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: active ? (activeColor || 'var(--color-sage-light)') : 'var(--color-bg-main)',
    border: '1px solid var(--color-border)',
    fontSize: '0.815rem',
    fontWeight: 600,
    color: active ? (activeColor === '#FEE2E2' ? '#DC2626' : 'var(--color-sage)') : 'var(--color-text-secondary)',
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
  });

  return (
    <div
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-md)',
        padding: '22px 24px',
        margin: '12px 0',
        width: '100%',
        maxWidth: '740px',
        transition: 'box-shadow var(--transition-base)',
      }}
      className="animate-fade-in"
      onMouseEnter={e => (e.currentTarget.style.boxShadow = 'var(--shadow-lg)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'var(--shadow-md)')}
    >
      {/* Header Row: Diet badge + Validation badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
        <span style={{
          padding: '4px 10px',
          borderRadius: 'var(--radius-full)',
          backgroundColor: dietBadge.bg,
          color: dietBadge.color,
          fontSize: '0.72rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          border: `1px solid ${dietBadge.color}33`
        }}>
          {dietBadge.label}
        </span>

        {validation && validation.passed && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.72rem',
            color: 'var(--color-sage)',
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'rgba(45,106,79,0.08)',
            border: '1px solid rgba(45,106,79,0.2)'
          }}>
            <ShieldCheck size={13} />
            <span>Dietary Validated</span>
          </div>
        )}

        {recipe.source && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.72rem',
            color: 'var(--color-text-secondary)',
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--color-bg-main)',
            border: '1px solid var(--color-border)'
          }}>
            {recipe.source === 'slm' ? <Sparkles size={13} /> : <Database size={13} />}
            <span>
              {recipe.source === 'slm' ? 'Generated by SLM' : recipe.source === 'retrieval' ? 'From recipe database' : 'Quick template'}
            </span>
          </div>
        )}
      </div>

      {/* Photo (only when it shows this same recipe) */}
      {recipe.image_url && (
        <FoodImage src={recipe.image_url} alt={recipe.image_alt || `Photo of ${recipe.title}`}
          style={{ width: '100%', aspectRatio: '16 / 8', borderRadius: 'var(--radius-md)', marginBottom: '14px' }} />
      )}

      {/* Title */}
      <h2 style={{
        fontFamily: 'var(--font-serif)',
        fontSize: '1.45rem',
        fontWeight: 700,
        color: 'var(--color-text-primary)',
        marginBottom: '14px',
        lineHeight: 1.25
      }}>
        {recipe.title}
      </h2>

      {/* Metadata Row */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '14px',
        fontSize: '0.83rem',
        color: 'var(--color-text-secondary)',
        paddingBottom: '16px',
        borderBottom: '1px solid var(--color-border)',
        marginBottom: '20px'
      }}>
        {recipe.cuisine && recipe.cuisine !== 'General' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Globe size={14} color="var(--color-brand)" />
            <span>{cuisineEmoji} {recipe.cuisine}</span>
          </div>
        )}
        {recipe.prep_time && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Clock size={14} color="var(--color-brand)" />
            <span>Prep <strong>{recipe.prep_time}</strong></span>
          </div>
        )}
        {recipe.cook_time && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <ChefHat size={14} color="var(--color-brand)" />
            <span>Cook <strong>{recipe.cook_time}</strong></span>
          </div>
        )}
        {servings && servings !== 'Servings not specified' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Users size={14} color="var(--color-brand)" />
            <span>Serves <strong>{servings}</strong></span>
          </div>
        )}
        {recipe.labels && recipe.labels.allergens.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }} title={recipe.labels.basis}>
            <span>Contains: <strong>{recipe.labels.allergens.join(', ')}</strong></span>
          </div>
        )}
      </div>

      <AllergyPanel check={recipe.allergy_check} />

      <NutritionPanel nutrition={recipe.nutrition} />

      {/* Ingredients Section */}
      {ingredients.length > 0 && (
        <div style={{ marginBottom: '22px' }}>
          <h4 style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
            marginBottom: '12px'
          }}>
            Ingredients
            {recipe.quantities_are_suggested && (
              <span style={{ marginLeft: 8, textTransform: 'none', letterSpacing: 0, fontWeight: 500, fontSize: '0.72rem' }}>
                · suggested amounts for {servings || 4} servings (typical Food.com quantities)
              </span>
            )}
          </h4>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
            gap: '6px'
          }}>
            {ingredients.map((ing, idx) => (
              <label
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '7px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--color-bg-main)',
                  border: '1px solid var(--color-border)',
                  fontSize: '0.845rem',
                  cursor: 'pointer',
                  userSelect: 'none',
                  textDecoration: checkedIngredients[idx] ? 'line-through' : 'none',
                  opacity: checkedIngredients[idx] ? 0.5 : 1,
                  transition: 'opacity var(--transition-fast)',
                  color: 'var(--color-text-primary)',
                }}
              >
                <input
                  type="checkbox"
                  checked={!!checkedIngredients[idx]}
                  onChange={() => toggleIngredient(idx)}
                  style={{ accentColor: 'var(--color-brand)', flexShrink: 0 }}
                />
                <span>{ing}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Instructions Section */}
      {instructions.length > 0 && (
        <div style={{ marginBottom: '22px' }}>
          <h4 style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
            marginBottom: '12px'
          }}>
            Instructions
          </h4>
          <ol style={{ paddingLeft: '0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {instructions.map((step, idx) => (
              <li
                key={idx}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                  fontSize: '0.875rem',
                  color: 'var(--color-text-secondary)',
                  lineHeight: 1.55
                }}
              >
                <span style={{
                  flexShrink: 0,
                  width: '22px',
                  height: '22px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-brand-light)',
                  color: 'var(--color-brand)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  border: '1px solid var(--color-brand-border)',
                  marginTop: '2px',
                }}>
                  {idx + 1}
                </span>
                <span style={{ flex: 1 }}>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Closest database recipe with verified nutrition (for model-written recipes without quantities) */}
      {related && (
        <div style={{ marginBottom: '18px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          <button onClick={() => setShowRelated(v => !v)} aria-expanded={showRelated}
            style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '12px', padding: '10px 12px', textAlign: 'left', backgroundColor: 'var(--color-bg-main)', cursor: 'pointer' }}>
            <FoodImage src={related.image_url} alt={`Photo of ${related.name}`} style={{ width: 64, height: 52, borderRadius: 8, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Similar recipe with verified nutrition</div>
              <div style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: '0.9rem' }}>{related.name}</div>
              <div style={{ fontSize: '0.76rem', color: 'var(--color-text-secondary)' }}>
                {related.nutrition.values ? `${Math.round(related.nutrition.values.kcal || 0)} kcal · ${related.nutrition.values.protein} g protein per serving · ${related.labels.diet_label}` : ''}
              </div>
            </div>
            {showRelated ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showRelated && (
            <div style={{ padding: '12px 14px' }}>
              <NutritionPanel nutrition={related.nutrition} compact />
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                Ingredients{related.servings ? ` (makes ${related.servings} servings)` : ''} · {related.prep_min ? `prep ${related.prep_min} min` : ''} {related.cook_min ? `· cook ${related.cook_min} min` : ''}
              </div>
              <ul style={{ paddingLeft: 18, fontSize: '0.82rem', color: 'var(--color-text-secondary)', marginBottom: 10 }}>
                {related.ingredient_lines.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
              <ol style={{ paddingLeft: 18, fontSize: '0.82rem', color: 'var(--color-text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {related.steps.map((st, i) => <li key={i}>{st}</li>)}
              </ol>
              <a href={related.source_url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', color: 'var(--color-brand)', marginTop: 8, fontWeight: 600 }}>
                Original recipe on Food.com <ExternalLink size={11} />
              </a>
            </div>
          )}
        </div>
      )}

      {recipe.source_url && !related && (
        <a href={recipe.source_url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 14, fontWeight: 600 }}>
          Photo and recipe source: Food.com <ExternalLink size={11} />
        </a>
      )}

      {/* Validation Conflicts */}
      {validation && !validation.passed && validation.conflicts.length > 0 && (
        <div style={{
          padding: '10px 14px',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'rgba(220, 38, 38, 0.06)',
          border: '1px solid rgba(220, 38, 38, 0.2)',
          marginBottom: '16px',
          fontSize: '0.81rem',
          color: '#B91C1C'
        }}>
          <strong>Note:</strong> Some ingredients were adjusted to meet your dietary requirements.
        </div>
      )}

      {/* Action Footer */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '10px',
        paddingTop: '16px',
        borderTop: '1px solid var(--color-border)'
      }}>
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap' }}>
          <button
            onClick={handleSaveClick}
            disabled={isSaved}
            style={actionBtnStyle(isSaved)}
            title={isSaved ? 'Recipe saved' : 'Save recipe'}
          >
            <Bookmark size={13} color={isSaved ? 'var(--color-sage)' : 'currentColor'} fill={isSaved ? 'var(--color-sage)' : 'none'} />
            <span>{isSaved ? 'Saved' : 'Save'}</span>
          </button>

          <button
            onClick={handleFavoriteClick}
            style={actionBtnStyle(isFavorited, '#FEE2E2')}
            title={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
          >
            <Heart size={13} color={isFavorited ? '#DC2626' : 'currentColor'} fill={isFavorited ? '#DC2626' : 'none'} />
            <span>{isFavorited ? 'Favorited' : 'Favorite'}</span>
          </button>
        </div>

        <div style={{ display: 'flex', gap: '7px' }}>
          <button
            onClick={handleCopy}
            title="Copy recipe to clipboard"
            style={actionBtnStyle(copied)}
          >
            {copied
              ? <Check size={13} color="var(--color-sage)" />
              : <Copy size={13} />
            }
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
