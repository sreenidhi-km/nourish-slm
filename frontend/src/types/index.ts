export type DietaryPreference = 'vegan' | 'vegetarian' | 'eggitarian' | 'non_vegetarian' | 'no_preference';

export interface User {
  id: number;
  name: string;
  email: string;
  dietary_preference: DietaryPreference;
  allergies?: string[];
}

export interface IngredientConflict {
  ingredient: string;
  reason: string;
  suggested_alternative?: string;
}

export interface RecipeValidation {
  passed: boolean;
  conflicts: IngredientConflict[];
  violating_ingredients?: string[];
  user_preference?: string;
}

export interface RecipeData {
  title: string;
  diet_type: DietaryPreference;
  cuisine: string;
  ingredients: string[];
  instructions: string[];
  prep_time: string;
  cook_time: string;
  servings: string;
  source?: 'slm' | 'retrieval' | 'template';
  // Nutrition & presentation (added by the backend; absent on older saved recipes)
  nutrition?: RecipeNutrition;
  image_url?: string;
  image_alt?: string;
  source_url?: string;
  labels?: { diet: string; diet_label: string; allergens: string[]; basis?: string };
  ingredient_quantities?: string[];
  related_recipe?: RelatedRecipe;
  allergy_check?: AllergyCheck;
  quantities_are_suggested?: boolean;
}

export interface AllergyCheck {
  checked: string[];
  checked_keys?: string[];
  passed: boolean;
  substitutions: { ingredient: string; replacement: string; allergen: string }[];
  remaining: { ingredient: string; allergens: string[] }[];
  note?: string;
}

export interface RecipeNutrition {
  status: 'source' | 'estimate' | 'unavailable';
  values?: { kcal?: number | null; protein?: number | null; carbs?: number | null; fat?: number | null; fiber?: number | null };
  basis?: string;
  source_label?: string;
  reason?: string;
  per?: string;
  missing?: string[];
  approximate?: boolean;
  servings_assumed?: number;
  assumed_amounts?: { ingredient: string; grams_total: number; basis: string; usda: string }[];
  not_counted?: string[];
}

export interface RelatedRecipe {
  id: number;
  name: string;
  image_url: string;
  source_url: string;
  servings: number | null;
  ingredient_lines: string[];
  steps: string[];
  prep_min: number;
  cook_min: number;
  nutrition: RecipeNutrition;
  labels: { diet: string; diet_label: string; allergens: string[] };
}

export interface Message {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  recipe_data?: RecipeData;
  validation?: RecipeValidation;
  created_at?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  messages_count?: number;
}

export interface SavedRecipe {
  id: number;
  title: string;
  recipe_data: RecipeData;
  saved_at: string;
}
