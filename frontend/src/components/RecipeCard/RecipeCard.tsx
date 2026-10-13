import React, { useState } from 'react';
import type { RecipeData, RecipeValidation } from '../../types';
import { Clock, Users, Globe, ShieldCheck, Bookmark, Heart, Copy, Check, ChefHat, Sparkles, Database } from 'lucide-react';

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

  // Guard: ensure recipe exists and has required fields
  if (!recipe || !recipe.title) return null;

  const toggleIngredient = (index: number) => {
    setCheckedIngredients(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const handleCopy = async () => {
    const ingList = (recipe.ingredients || []).map(i => `• ${i}`).join('\n');
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

  const ingredients = recipe.ingredients || [];
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
      </div>

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
