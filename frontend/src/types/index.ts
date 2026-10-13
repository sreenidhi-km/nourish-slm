export type DietaryPreference = 'vegan' | 'vegetarian' | 'eggitarian' | 'non_vegetarian' | 'no_preference';

export interface User {
  id: number;
  name: string;
  email: string;
  dietary_preference: DietaryPreference;
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
