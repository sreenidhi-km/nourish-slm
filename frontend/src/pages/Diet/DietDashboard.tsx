import React, { useEffect, useState } from 'react';
import { Apple, Dumbbell, Trophy, ArrowRight, RefreshCw } from 'lucide-react';
import type { DietCategoryGroup } from '../../types/diet';
import { dietService, apiErrorMessage } from '../../services/diet';
import { FoodImage } from '../../components/Diet/FoodImage';

interface DietDashboardProps {
  onOpenCategory: (key: string) => void;
}

const GROUP_ICONS: Record<string, React.ReactNode> = {
  preferences: <Apple size={14} />, goals: <Dumbbell size={14} />, sports: <Trophy size={14} />,
};

let cachedGroups: DietCategoryGroup[] | null = null;

export const DietDashboard: React.FC<DietDashboardProps> = ({ onOpenCategory }) => {
  const [groups, setGroups] = useState<DietCategoryGroup[] | null>(cachedGroups);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const load = async () => {
    setError(null);
    try {
      const res = await dietService.getCategories();
      cachedGroups = res.groups;
      setGroups(res.groups);
      if (!res.data_available) setError('The recipe database has not been built on the server yet (run scripts/build_diet_dataset.py).');
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not load diet categories.'));
    }
  };

  useEffect(() => { if (!cachedGroups) load(); }, []);

  return (
    <div className="diet-scroll">
      <div className="diet-container animate-fade-in">
        <div className="diet-eyebrow">Diet planning</div>
        <h1 className="diet-title" style={{ margin: '4px 0 6px' }}>Find a plan that fits how you eat and train</h1>
        <p className="diet-subtitle" style={{ maxWidth: 720 }}>
          Every plan is built from real recipes with published nutrition, personalised with your details,
          and fully editable. Each plan has its own assistant that knows your meals and restrictions.
        </p>
        <div className="diet-filter" role="tablist" aria-label="Filter categories">
          {[['all', 'All'], ['preferences', 'Dietary preferences'], ['goals', 'Fitness goals'], ['sports', 'Sports']].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={filter === k} className={`diet-chip ${filter === k ? 'active' : ''}`}
              onClick={() => setFilter(k)}>{l}</button>
          ))}
        </div>

        {error && (
          <div className="diet-error" style={{ marginTop: 16 }}>
            <span>{error}</span>
            <button className="diet-btn diet-btn-sm" onClick={load}><RefreshCw size={13} /> Retry</button>
          </div>
        )}

        {!groups && !error && (
          <div className="diet-grid" style={{ marginTop: 24 }}>
            {Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 300, borderRadius: 16 }} />)}
          </div>
        )}

        {groups && groups.filter(g => filter === 'all' || g.key === filter).map(group => (
          <section key={group.key} aria-labelledby={`grp-${group.key}`}>
            <h2 className="diet-section-title" id={`grp-${group.key}`}>{GROUP_ICONS[group.key]} {group.title}</h2>
            <div className="diet-grid">
              {group.categories.map(cat => (
                <article className="diet-card" key={cat.key}>
                  <FoodImage src={cat.image?.url} alt={cat.image?.alt || cat.name} />
                  <div className="diet-card-body">
                    <h3 className="diet-card-name">{cat.name}</h3>
                    <p className="diet-card-desc">{cat.description}</p>
                    <div className="diet-card-meta"><strong>Focus:</strong> {cat.focus}</div>
                    <div className="diet-card-meta"><strong>Goal:</strong> {cat.goal_text}</div>
                    {cat.image && (
                      <div className="diet-card-caption">
                        {cat.image.source === 'unsplash' ? `${cat.image.alt} · ${cat.image.credit}` : `Pictured: ${cat.image.recipe_name} (Food.com)`}
                      </div>
                    )}
                    <div className="diet-card-footer">
                      <button className="diet-btn diet-btn-primary" style={{ width: '100%' }} onClick={() => onOpenCategory(cat.key)}
                        aria-label={`Explore ${cat.name} plan`}>
                        Explore Plan <ArrowRight size={14} />
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
        <p className="diet-disclaimer">
          Nutritional recommendations are estimates for general guidance. Specialised needs, medical conditions or clinical
          diets should be discussed with a qualified healthcare professional or sports dietitian.
        </p>
      </div>
    </div>
  );
};
