import React, { useEffect, useState } from 'react';
import { SlidersHorizontal, RefreshCw, Check } from 'lucide-react';
import type { DietOptions, DietProfile } from '../../types/diet';

interface Props {
  profile: DietProfile;
  options: DietOptions | null;
  questions: string[];
  busy: boolean;
  onSubmit: (profile: Partial<DietProfile>, regenerate: boolean) => void;
}

const numOrNull = (v: string) => (v.trim() === '' ? null : Number(v));

export const PersonaliseForm: React.FC<Props> = ({ profile, options, questions, busy, onSubmit }) => {
  const [p, setP] = useState<DietProfile>(profile);
  const [dislikes, setDislikes] = useState(profile.dislikes.join(', '));
  const [otherAllergy, setOtherAllergy] = useState(
    profile.allergies.filter(a => !options?.allergens || !(a in options.allergens)).join(', '));
  useEffect(() => {
    setP(profile);
    setDislikes(profile.dislikes.join(', '));
  }, [profile]);

  const has = (q: string) => questions.includes(q);
  const set = <K extends keyof DietProfile>(k: K, v: DietProfile[K]) => setP(prev => ({ ...prev, [k]: v }));
  const toggle = (k: 'allergies' | 'intolerances', v: string) =>
    setP(prev => ({ ...prev, [k]: prev[k].includes(v) ? prev[k].filter(x => x !== v) : [...prev[k], v] }));

  const build = (): Partial<DietProfile> => {
    const known = p.allergies.filter(a => options?.allergens && a in options.allergens);
    const extra = otherAllergy.split(',').map(s => s.trim()).filter(Boolean);
    return {
      ...p,
      allergies: [...known, ...extra],
      dislikes: dislikes.split(',').map(s => s.trim()).filter(Boolean),
    };
  };

  const training = has('sport') && !!p.sport;

  return (
    <form
      onSubmit={e => { e.preventDefault(); onSubmit(build(), true); }}
      aria-label="Personalise this plan"
    >
      <p className="diet-subtitle" style={{ fontSize: '0.8rem', marginBottom: 12 }}>
        Only what's needed for your recommendations. Everything is optional — skip anything you'd rather not share.
        Age, height and weight are used only to estimate energy and gram targets and are stored with this plan only.
      </p>
      <div className="form-grid">
        {has('diet_preference') && (
          <div className="form-field">
            <label htmlFor="pf-diet">Dietary preference</label>
            <select id="pf-diet" className="diet-select" value={p.diet_preference}
              onChange={e => set('diet_preference', e.target.value as DietProfile['diet_preference'])}>
              {Object.entries(options?.diet_preferences || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
        {has('goal') && (
          <div className="form-field">
            <label htmlFor="pf-goal">Primary goal</label>
            <select id="pf-goal" className="diet-select" value={p.goal} onChange={e => set('goal', e.target.value)}>
              {Object.entries(options?.goals || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
        {has('activity_level') && (
          <div className="form-field">
            <label htmlFor="pf-act">Activity level</label>
            <select id="pf-act" className="diet-select" value={p.activity_level || ''}
              onChange={e => set('activity_level', e.target.value || null)}>
              <option value="">{p.sport ? 'Work it out from my training' : 'Not set'}</option>
              {Object.entries(options?.activity_levels || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
        {training && (
          <>
            <div className="form-field">
              <label htmlFor="pf-sport">Sport / activity</label>
              <select id="pf-sport" className="diet-select" value={p.sport || ''} onChange={e => set('sport', e.target.value)}>
                {Object.entries(options?.sports || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            {p.sport === 'other' && (
              <div className="form-field">
                <label htmlFor="pf-other">Which sport?</label>
                <input id="pf-other" className="diet-input" value={p.other_sport_name || ''}
                  onChange={e => set('other_sport_name', e.target.value)} placeholder="e.g. Kabaddi" />
              </div>
            )}
            <div className="form-field">
              <label htmlFor="pf-days">Training days / week</label>
              <input id="pf-days" type="number" min={0} max={7} className="diet-input" value={p.training_days_per_week ?? ''}
                onChange={e => set('training_days_per_week', numOrNull(e.target.value))} />
            </div>
            <div className="form-field">
              <label htmlFor="pf-min">Session length (minutes)</label>
              <input id="pf-min" type="number" min={10} max={480} className="diet-input" value={p.session_minutes ?? ''}
                onChange={e => set('session_minutes', numOrNull(e.target.value))} />
            </div>
            <div className="form-field">
              <label htmlFor="pf-int">Intensity</label>
              <select id="pf-int" className="diet-select" value={p.intensity || 'moderate'} onChange={e => set('intensity', e.target.value)}>
                {Object.entries(options?.intensities || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="pf-time">Usual training time</label>
              <input id="pf-time" type="time" className="diet-input" value={p.training_time || ''}
                onChange={e => set('training_time', e.target.value || null)} />
            </div>
            <div className="form-field">
              <label>Plan for</label>
              <div className="check-chips">
                {(['training', 'rest'] as const).map(d => (
                  <label key={d} className={p.day_type === d ? 'on' : ''}>
                    <input type="radio" name="daytype" checked={p.day_type === d} onChange={() => set('day_type', d)} />
                    {d === 'training' ? 'Training day' : 'Rest day'}
                  </label>
                ))}
              </div>
            </div>
          </>
        )}
        {has('age') && (
          <div className="form-field">
            <label htmlFor="pf-age">Age (optional)</label>
            <input id="pf-age" type="number" min={14} max={100} className="diet-input" value={p.age ?? ''}
              onChange={e => set('age', numOrNull(e.target.value))} />
          </div>
        )}
        {has('sex') && (
          <div className="form-field">
            <label htmlFor="pf-sex">Sex for energy equation (optional)</label>
            <select id="pf-sex" className="diet-select" value={p.sex || ''} onChange={e => set('sex', (e.target.value || null) as DietProfile['sex'])}>
              <option value="">Prefer not to say</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </div>
        )}
        {has('height_cm') && (
          <div className="form-field">
            <label htmlFor="pf-h">Height in cm (optional)</label>
            <input id="pf-h" type="number" min={120} max={230} className="diet-input" value={p.height_cm ?? ''}
              onChange={e => set('height_cm', numOrNull(e.target.value))} />
          </div>
        )}
        {has('weight_kg') && (
          <div className="form-field">
            <label htmlFor="pf-w">Weight in kg (optional)</label>
            <input id="pf-w" type="number" min={30} max={250} step="0.1" className="diet-input" value={p.weight_kg ?? ''}
              onChange={e => set('weight_kg', numOrNull(e.target.value))} />
          </div>
        )}
        {has('cuisine') && (
          <div className="form-field">
            <label htmlFor="pf-cui">Preferred cuisine</label>
            <select id="pf-cui" className="diet-select" value={p.cuisine || 'any'} onChange={e => set('cuisine', e.target.value)}>
              {(options?.cuisines || ['any']).map(c => <option key={c} value={c}>{c === 'any' ? 'Any cuisine' : c[0].toUpperCase() + c.slice(1)}</option>)}
            </select>
          </div>
        )}
        {has('meals_per_day') && (
          <div className="form-field">
            <label htmlFor="pf-meals">Meals per day</label>
            <select id="pf-meals" className="diet-select" value={p.meals_per_day} onChange={e => set('meals_per_day', Number(e.target.value))}>
              {[3, 4, 5, 6].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            {training && <div className="hint">Pre/post-training snacks are included in this count where possible.</div>}
          </div>
        )}
        {has('max_prep_minutes') && (
          <div className="form-field">
            <label htmlFor="pf-prep">Max cooking time (minutes)</label>
            <input id="pf-prep" type="number" min={10} max={240} className="diet-input" value={p.max_prep_minutes ?? ''}
              placeholder="No limit" onChange={e => set('max_prep_minutes', numOrNull(e.target.value))} />
          </div>
        )}
        {has('allergies') && (
          <div className="form-field form-wide">
            <label>Allergies</label>
            <div className="check-chips">
              {Object.entries(options?.allergens || {}).map(([k, v]) => (
                <label key={k} className={p.allergies.includes(k) ? 'on' : ''}>
                  <input type="checkbox" checked={p.allergies.includes(k)} onChange={() => toggle('allergies', k)} /> {v}
                </label>
              ))}
            </div>
            <input className="diet-input" style={{ marginTop: 6 }} value={otherAllergy} onChange={e => setOtherAllergy(e.target.value)}
              placeholder="Other foods to strictly avoid (comma separated)" aria-label="Other allergies" />
            <div className="hint">Allergen detection uses ingredient names — always check product labels.</div>
          </div>
        )}
        {has('intolerances') && (
          <div className="form-field form-wide">
            <label>Intolerances</label>
            <div className="check-chips">
              {(options?.intolerances || []).map(k => (
                <label key={k} className={p.intolerances.includes(k) ? 'on' : ''}>
                  <input type="checkbox" checked={p.intolerances.includes(k)} onChange={() => toggle('intolerances', k)} /> {k}
                </label>
              ))}
            </div>
          </div>
        )}
        {has('dislikes') && (
          <div className="form-field form-wide">
            <label htmlFor="pf-dis">Foods you dislike</label>
            <input id="pf-dis" className="diet-input" value={dislikes} onChange={e => setDislikes(e.target.value)}
              placeholder="e.g. mushroom, olives" />
          </div>
        )}
      </div>
      <div className="diet-actions" style={{ marginTop: 14, justifyContent: 'flex-end' }}>
        <button type="button" className="diet-btn" disabled={busy} onClick={() => onSubmit(build(), false)}
          title="Keep the current meals and recalculate targets and the assessment">
          <Check size={14} /> Update targets only
        </button>
        <button type="submit" className="diet-btn diet-btn-primary" disabled={busy}>
          {busy ? <RefreshCw size={14} className="animate-spin" /> : <SlidersHorizontal size={14} />} Rebuild my meal plan
        </button>
      </div>
    </form>
  );
};
