import { apiClient } from './api';
import type { RecipeData, SavedRecipe } from '../types';

export const recipeService = {
  async saveRecipe(title: string, recipeData: RecipeData) {
    const res = await apiClient.post('/recipes/save', {
      title,
      recipe_data: recipeData
    });
    return res.data;
  },

  async getSavedRecipes(): Promise<SavedRecipe[]> {
    const res = await apiClient.get('/recipes/saved');
    return res.data;
  },

  async deleteSavedRecipe(id: number) {
    const res = await apiClient.delete(`/recipes/saved/${id}`);
    return res.data;
  },

  async addFavorite(title: string, recipeData: RecipeData) {
    const res = await apiClient.post('/favorites', {
      title,
      recipe_data: recipeData
    });
    return res.data;
  },

  async getFavorites(): Promise<SavedRecipe[]> {
    const res = await apiClient.get('/favorites');
    return res.data;
  },

  async deleteFavorite(id: number) {
    const res = await apiClient.delete(`/favorites/${id}`);
    return res.data;
  }
};
