import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft, ClipboardCheck, Save, SlidersHorizontal, Plus, RefreshCw, Loader2, Shuffle, Droplets, Target, BookmarkCheck,
} from 'lucide-react';
import type { CategoryDetail, DietOptions, DietPlan, DietProfile, PlanMeal, RecipeSummary } from '../../types/diet';
import { dietService, apiErrorMessage } from '../../services/diet';
import { MealCard } from '../../components/Diet/MealCard';
import { PersonaliseForm } from '../../components/Diet/PersonaliseForm';
import { DailyTotals } from '../../components/Diet/NutritionSummary';
import { AssessmentPanel } from '../../components/Diet/AssessmentPanel';
import { DietAssistant } from '../../components/Diet/DietAssistant';
import { RecipePicker } from '../../components/Diet/RecipePicker';

interface Props {
  categoryKey?: string;
  planId?: string;
  onBack: () => void;
  onPlansChanged: () => void;
  onOpenPlan: (planId: string) => void;
  notify: (msg: string, type?: 'success' | 'error') => void;
}

let optionsCache: DietOptions | null = null;

export const DietPlanPage: React.FC<Props> = ({ categoryKey, planId, onBack, onPlansChanged, onOpenPlan, notify }) => {
  const [category, setCategory] = useState<CategoryDetail | null>(null);
  const [plan, setPlan] = useState<DietPlan | null>(null);
  const [options, setOptions] = useState<DietOptions | null>(optionsCache);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const [reviewFresh, setReviewFresh] = useState(false);
  const [picker, setPicker] = useState<{ open: boolean; meal: PlanMeal | null }>({ open: false, meal: null });
  const [saveName, setSaveName] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<string | null>(null);
  const reviewRef = useRef<HTMLDivElement>(null);

  const loadFor = useCallback(async () => {
    setLoading(true);
    setError(null);
    setShowReview(false);
    try {
      if (!optionsCache) { optionsCache = await dietService.getOptions(); setOptions(optionsCache); }
      let p: DietPlan;
      let cat: CategoryDetail;
      if (planId) {
        p = await dietService.getPlan(planId);
        cat = await dietService.getCategory(p.category_key);
      } else if (categoryKey) {
        cat = await dietService.getCategory(categoryKey);
        if (cat.latest_plan_id) {
          p = await dietService.getPlan(cat.latest_plan_id);
        } else {
          p = await dietService.createPlan(categoryKey, {});
          setShowForm(true);
          onPlansChanged();
        }
      } else {
        throw new Error('No plan selected');
      }
      setCategory(cat);
      setPlan(p);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not open this diet plan.'));
    } finally {
      setLoading(false);
    }
  }, [planId, categoryKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadFor(); }, [loadFor]);

  const runEdit = async (op: Record<string, unknown>): Promise<boolean> => {
    if (!plan) return false;
    setBusy(true);
    setError(null);
    try {
      const next = await dietService.editPlan(plan.id, op, plan.version);
      setPlan(next);
      setLastChange(next.last_change || null);
      setReviewFresh(true);
      if (next.is_saved) onPlansChanged();
      return true;
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        notify('This plan changed in another window — reloaded the latest version.', 'error');
        setPlan(await dietService.getPlan(plan.id));
      } else {
        setError(apiErrorMessage(e, 'Could not update the plan.'));
      }
      return false;
    } finally {
      setBusy(false);
    }
  };

  const checkMyDiet = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      const res = await dietService.assess(plan.id);
      setPlan(p => (p ? { ...p, assessment: res.assessment, totals: res.totals, targets: res.targets, version: res.version } : p));
      setShowReview(true);
      setReviewFresh(false);
      window.setTimeout(() => reviewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not check this plan.'));
    } finally {
      setBusy(false);
    }
  };

  const submitProfile = async (profile: Partial<DietProfile>, regenerate: boolean) => {
    const ok = await runEdit({ op: 'update_profile', profile, regenerate });
    if (ok) {
      notify(regenerate ? 'Meal plan rebuilt for your details' : 'Targets and review updated', 'success');
      setShowForm(false);
    }
  };

  const pickRecipe = async (r: RecipeSummary, extra: { slot?: string; time?: string }) => {
    const meal = picker.meal;
    setPicker({ open: false, meal: null });
    if (meal) await runEdit({ op: 'replace_meal', meal_id: meal.id, recipe_id: r.id });
    else await runEdit({ op: 'add_meal', recipe_id: r.id, slot: extra.slot, time: extra.time, servings: 1 });
  };

  const save = async () => {
    if (!plan || saveName === null) return;
    setBusy(true);
    try {
      const saved = await dietService.savePlan(plan.id, saveName.trim() || plan.name, true);
      setPlan(saved);
      setSaveName(null);
      notify(`Saved "${saved.name}"`, 'success');
      onPlansChanged();
    } catch (e) {
      notify(apiErrorMessage(e, 'Could not save the plan.'), 'error');
    } finally {
      setBusy(false);
    }
  };

  const startNew = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      const fresh = await dietService.createPlan(plan.category_key, plan.profile);
      onPlansChanged();
      onOpenPlan(fresh.id);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not create a new plan.'));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="diet-scroll"><div className="diet-container">
        <div className="diet-card-caption" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
          <Loader2 size={14} className="animate-spin" /> Building your plan from the recipe database…
        </div>
        <div className="skeleton" style={{ height: 120, marginBottom: 14 }} />
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 136, marginBottom: 12 }} />)}
      </div></div>
    );
  }
  if (!plan || !category) {
    return (
      <div className="diet-scroll"><div className="diet-container">
        <button className="diet-back" onClick={onBack}><ArrowLeft size={14} /> All diet plans</button>
        <div className="diet-error"><span>{error || 'Plan not available.'}</span>
          <button className="diet-btn diet-btn-sm" onClick={loadFor}><RefreshCw size={13} /> Retry</button></div>
      </div></div>
    );
  }

  const prof = plan.profile;
  const t = plan.targets;
  const sportName = prof.sport ? (options?.sports?.[prof.sport] || prof.sport) : null;

  return (
    <div className="diet-scroll">
      <div className="diet-container animate-fade-in">
        <button className="diet-back" onClick={onBack}><ArrowLeft size={14} /> All diet plans</button>
        <div className="diet-plan-header">
          <div style={{ minWidth: 0 }}>
            <div className="diet-eyebrow">{category.name} · {plan.is_saved ? 'Saved plan' : 'Draft (changes are kept automatically)'}</div>
            <h1 className="diet-title">{plan.is_saved ? plan.name : `${category.name} Nutrition Plan`}</h1>
            <p className="diet-subtitle" style={{ fontSize: '0.86rem' }}>{category.description}</p>
          </div>
          <div className="diet-actions">
            <button className="diet-btn diet-btn-primary" onClick={checkMyDiet} disabled={busy}>
              <ClipboardCheck size={15} /> Check My Diet
            </button>
            <button className="diet-btn" onClick={() => setShowForm(s => !s)} aria-expanded={showForm}>
              <SlidersHorizontal size={14} /> Personalise
            </button>
            {saveName === null ? (
              <button className="diet-btn" onClick={() => setSaveName(plan.is_saved ? plan.name : `${category.name} plan`)} disabled={busy}>
                {plan.is_saved ? <BookmarkCheck size={14} /> : <Save size={14} />} {plan.is_saved ? 'Rename' : 'Save plan'}
              </button>
            ) : (
              <form onSubmit={e => { e.preventDefault(); save(); }} style={{ display: 'flex', gap: 6 }}>
                <input className="diet-input" style={{ width: 180 }} value={saveName} onChange={e => setSaveName(e.target.value)}
                  aria-label="Plan name" autoFocus maxLength={120} />
                <button className="diet-btn diet-btn-sage" type="submit" disabled={busy}>Save</button>
                <button className="diet-btn diet-btn-ghost" type="button" onClick={() => setSaveName(null)}>Cancel</button>
              </form>
            )}
          </div>
        </div>

        {error && <div className="diet-error" style={{ marginBottom: 12 }}><span>{error}</span>
          <button className="diet-btn diet-btn-sm" onClick={() => setError(null)}>Dismiss</button></div>}

        <div className="diet-plan-layout">
          <div style={{ minWidth: 0 }}>
            {showForm && (
              <section className="diet-panel">
                <div className="diet-panel-title"><h3><SlidersHorizontal size={15} color="var(--color-brand)" /> Personalise this plan</h3></div>
                <PersonaliseForm profile={prof} options={options} questions={category.questions} busy={busy} onSubmit={submitProfile} />
              </section>
            )}

            <section className="diet-panel">
              <div className="diet-panel-title">
                <h3><Target size={15} color="var(--color-brand)" /> Plan overview</h3>
                <span className="diet-saving">{busy ? <><Loader2 size={12} className="animate-spin" /> Saving…</> : lastChange ? `Saved: ${lastChange}` : 'All changes saved'}</span>
              </div>
              <dl className="diet-overview">
                {sportName && <div><dt>Sport / activity</dt><dd>{prof.sport === 'other' && prof.other_sport_name ? prof.other_sport_name : sportName}</dd></div>}
                <div><dt>Goal</dt><dd>{options?.goals?.[prof.goal] || prof.goal}</dd></div>
                <div><dt>Dietary preference</dt><dd>{options?.diet_preferences?.[prof.diet_preference] || prof.diet_preference}</dd></div>
                {prof.sport && <div><dt>Training</dt><dd>{prof.day_type === 'rest' ? 'Rest day' : `${prof.session_minutes || '?'} min at ${prof.training_time || '?'}${prof.training_days_per_week ? `, ${prof.training_days_per_week}×/week` : ''}`}</dd></div>}
                <div><dt>Avoiding</dt><dd>{[...prof.allergies, ...prof.intolerances, ...prof.dislikes].join(', ').replace(/_/g, ' ') || 'Nothing listed'}</dd></div>
                <div><dt>Meals</dt><dd>{plan.meals.length} today{prof.cuisine && prof.cuisine !== 'any' ? ` · ${prof.cuisine} first` : ''}</dd></div>
              </dl>
              <div style={{ marginTop: 14 }}>
                <DailyTotals totals={plan.totals} targets={t} />
              </div>
              {t.energy && <p className="diet-card-caption" style={{ marginTop: 8 }} title={t.energy.basis}>Energy estimate: {t.energy.basis}.</p>}
              {[...t.notes, ...t.assumptions, ...plan.notes].map((n, i) => (
                <div key={i} className="meal-notice warn" style={{ marginTop: 8 }}>{n}</div>
              ))}
              {(t.missing.length > 0) && !showForm && (
                <button className="diet-btn diet-btn-sm" style={{ marginTop: 10 }} onClick={() => setShowForm(true)}>
                  Add your details for personal targets
                </button>
              )}
              {prof.sport && t.hydration.length > 0 && (
                <details style={{ marginTop: 10 }}>
                  <summary className="diet-card-caption" style={{ cursor: 'pointer' }}><Droplets size={12} style={{ verticalAlign: '-2px' }} /> Hydration guidance</summary>
                  <ul style={{ paddingLeft: 18, fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginTop: 6, lineHeight: 1.6 }}>
                    {t.hydration.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </details>
              )}
            </section>

            <div ref={reviewRef}>
              {showReview && <div style={{ marginTop: 14 }}><AssessmentPanel assessment={plan.assessment} fresh={reviewFresh} /></div>}
            </div>

            <h2 className="diet-section-title">Daily meal schedule</h2>
            {plan.meals.map(m => (
              <MealCard key={m.id} meal={m} busy={busy} units={options?.units || ['g', 'cup', 'tbsp', 'tsp', 'count']}
                onEdit={runEdit} onReplace={meal => setPicker({ open: true, meal })} />
            ))}
            <div className="diet-actions" style={{ marginTop: 14 }}>
              <button className="diet-btn" onClick={() => setPicker({ open: true, meal: null })} disabled={busy}><Plus size={14} /> Add a meal</button>
              <button className="diet-btn" onClick={() => runEdit({ op: 'regenerate' })} disabled={busy}
                title="Replace all meals with a different selection for the same details"><Shuffle size={14} /> Different meals</button>
              <button className="diet-btn diet-btn-ghost" onClick={startNew} disabled={busy}><Plus size={14} /> Start another {category.name} plan</button>
            </div>

            {category.notes.length > 0 && (
              <div style={{ marginTop: 16 }}>
                {category.notes.map((n, i) => <div key={i} className="meal-notice info">{n}</div>)}
              </div>
            )}
            <p className="diet-disclaimer">
              {t.disclaimer} Values marked "Recipe data" are the recipes' published per-serving values; "Calculated estimate"
              values are recalculated from USDA FoodData Central after your edits. Allergen labels are detected from ingredient
              names. Photos are linked from Food.com. Nothing here guarantees a performance, weight or health outcome.
            </p>
          </div>

          <div className="diet-assistant-col">
            <DietAssistant plan={plan} onPlanUpdated={p => { setPlan(p); setReviewFresh(true); if (p.is_saved) onPlansChanged(); }} />
          </div>
        </div>
      </div>
      {picker.open && (
        <RecipePicker planId={plan.id} meal={picker.meal} onClose={() => setPicker({ open: false, meal: null })} onPick={pickRecipe} />
      )}
    </div>
  );
};
