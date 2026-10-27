import type { DietaryPreference } from './index';

export type NutrientKey = 'kcal' | 'protein' | 'carbs' | 'fat' | 'fiber';
export type NutrientValues = Partial<Record<NutrientKey, number | null>>;

export interface NutritionResult {
  status: 'source' | 'estimate' | 'unavailable';
  values: NutrientValues;
  basis?: string;
  reason?: string;
  notes?: string[];
  missing?: string[];
  source_label?: string;
  per?: string;
}

export interface CategoryImage {
  url: string;
  alt: string;
  // Food.com fallback photos
  recipe_name?: string;
  recipe_id?: number;
  source_url?: string;
  // Hand-picked photos
  source?: 'unsplash';
  credit?: string;
}

export interface DietCategory {
  key: string;
  group: 'preferences' | 'goals' | 'sports';
  name: string;
  description: string;
  focus: string;
  goal_text: string;
  assistant_name: string;
  image: CategoryImage | null;
}

export interface DietCategoryGroup {
  key: string;
  title: string;
  categories: DietCategory[];
}

export interface DietProfile {
  diet_preference: DietaryPreference;
  goal: string;
  activity_level: string | null;
  sport: string | null;
  other_sport_name?: string | null;
  training_days_per_week: number | null;
  session_minutes: number | null;
  intensity: string | null;
  training_time: string | null;
  day_type: 'training' | 'rest';
  age: number | null;
  sex: 'male' | 'female' | null;
  height_cm: number | null;
  weight_kg: number | null;
  allergies: string[];
  intolerances: string[];
  dislikes: string[];
  cuisine: string;
  meals_per_day: number;
  max_prep_minutes: number | null;
}

export interface CategoryDetail extends DietCategory {
  notes: string[];
  questions: string[];
  default_profile: DietProfile;
  latest_plan_id: string | null;
}

export interface PlanIngredient {
  idx: number;
  quantity: string;
  unit: string;
  name: string;
  description?: string;
  line: string;
  status: 'original' | 'modified' | 'added' | 'removed';
  fdc_id?: number;
  original?: { quantity: string; unit: string; name: string; line: string };
}

export interface ChangeReport {
  name: string;
  status: string;
  before?: { status: string; grams?: number; reason?: string; match?: { description: string; source: string } | null };
  after?: { status: string; grams?: number; reason?: string; conversion?: string; match?: { description: string; source: string } | null };
}

export interface PlanMeal {
  id: string;
  slot: string;
  label: string;
  time: string;
  kind: string;
  post_training: boolean;
  pre_training?: boolean;
  recipe_id: number;
  name: string;
  image_url: string;
  source_url: string;
  category: string;
  cuisines: string[];
  diet: DietaryPreference;
  allergens: string[];
  diet_verify: { ingredient: string; reason: string; applies_to: string[] }[];
  focus_tags: string[];
  recipe_servings: number | null;
  serving_size_g: number | null;
  servings: number;
  source_per_serving: NutrientValues & { sugar?: number | null; sodium?: number | null };
  ingredients: PlanIngredient[];
  steps: string[];
  prep_min: number;
  cook_min: number;
  total_min: number;
  nutrition: NutritionResult & { changes?: ChangeReport[] };
  reason: string;
}

export interface TargetRange {
  low: number | null;
  high: number | null;
  target?: number;
  unit: string;
  basis: string;
}

export interface Targets {
  energy: TargetRange | null;
  protein: TargetRange | null;
  carbs: TargetRange | null;
  fat: TargetRange | null;
  fiber: TargetRange | null;
  shares: Record<string, { low: number; high: number }>;
  per_meal_protein: { low: number; high: number; basis: string } | null;
  training_load: string | null;
  is_training_day: boolean;
  hydration: string[];
  assumptions: string[];
  missing: string[];
  notes: string[];
  references: string[];
  disclaimer: string;
}

export interface AssessmentCheck {
  key: string;
  kind: 'restriction' | 'nutrient_gap' | 'data' | 'timing';
  status: string;
  title: string;
  message: string;
}

export interface Assessment {
  label_key: 'aligned' | 'minor' | 'significant' | 'info';
  label: string;
  summary: string;
  reasons: string[];
  checks: AssessmentCheck[];
  suggestions: { kind: string; text: string; meal_id?: string }[];
  restriction_conflicts: { type: string; meal_id: string; message: string }[];
  verification_notes: { message: string }[];
  assessed_at: string;
  disclaimer: string;
}

export interface PlanTotals {
  values: NutrientValues;
  complete: Record<string, boolean>;
  meals_unavailable: string[];
  meals_estimated: string[];
  meal_count: number;
}

export interface DietPlan {
  id: string;
  name: string;
  is_saved: boolean;
  version: number;
  category_key: string;
  category_name: string;
  assistant_name: string;
  profile: DietProfile;
  meals: PlanMeal[];
  totals: PlanTotals;
  targets: Targets;
  assessment: Assessment;
  notes: string[];
  created_at: string;
  updated_at: string;
  last_change?: string;
}

export interface DietPlanSummary {
  id: string;
  name: string;
  is_saved: boolean;
  category_key: string;
  category_name: string;
  meal_count: number;
  kcal: number | null;
  assessment_label: string | null;
  updated_at: string;
}

export interface RecipeSummary {
  id: number;
  name: string;
  category: string;
  cuisines: string[];
  diet: DietaryPreference;
  diet_label: string;
  allergens: string[];
  meal_types: string[];
  focus_tags: string[];
  image_url: string;
  servings: number | null;
  nutrition_per_serving: NutrientValues;
  total_min: number;
  source_url: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UsdaFood {
  fdc_id: number;
  description: string;
  source: string;
  category: string;
  per_100g: NutrientValues;
}

export interface Proposal {
  id: string;
  title: string;
  description: string;
  op: Record<string, unknown>;
  status: 'pending' | 'applied';
  preview: {
    summary: string;
    meal_before: { name: string; servings: number; nutrition: NutritionResult } | null;
    meal_after: { name: string; servings: number; nutrition: NutritionResult; image_url?: string; ingredients?: string[] } | null;
    totals_before: PlanTotals;
    totals_after: PlanTotals;
    assessment_after: { label: string; label_key: string };
  };
}

export interface DietChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  proposals: Proposal[];
  meta: Record<string, unknown>;
  created_at: string;
}

export interface DietOptions {
  goals: Record<string, string>;
  activity_levels: Record<string, string>;
  intensities: Record<string, string>;
  diet_preferences: Record<string, string>;
  allergens: Record<string, string>;
  intolerances: string[];
  cuisines: string[];
  units: string[];
  sports: Record<string, string>;
}
