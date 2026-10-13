import React, { useEffect, useState } from 'react';
import type { SavedRecipe } from '../../types';
import { recipeService } from '../../services/recipes';
import { RecipeCard } from '../../components/RecipeCard/RecipeCard';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { Bookmark, Heart } from 'lucide-react';

interface SavedRecipesProps {
  type: 'saved' | 'favorites';
  onNewChat: () => void;
}

export const SavedRecipesPage: React.FC<SavedRecipesProps> = ({ type, onNewChat }) => {
  const [items, setItems] = useState<SavedRecipe[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadItems();
  }, [type]);

  const loadItems = async () => {
    setLoading(true);
    try {
      const data = type === 'saved' ? await recipeService.getSavedRecipes() : await recipeService.getFavorites();
      setItems(data);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const isSavedType = type === 'saved';

  return (
    <div style={{ flex: 1, padding: '28px 36px', overflowY: 'auto', backgroundColor: 'var(--color-bg-main)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', backgroundColor: isSavedType ? 'var(--color-brand-light)' : '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isSavedType ? <Bookmark size={22} color="var(--color-brand)" /> : <Heart size={22} color="#DC2626" />}
        </div>
        <div>
          <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.6rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {isSavedType ? 'Saved Recipes' : 'Favorite Recipes'}
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
            {isSavedType ? 'Recipes you saved during your chat sessions' : 'Your bookmarked favorite dishes'}
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
          Loading recipes...
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title={isSavedType ? 'No saved recipes yet' : 'No favorite recipes yet'}
          description="When you generate recipes in chat, click the Save or Favorite button to keep them here for easy cooking access."
          actionText="Create New Recipe"
          onAction={onNewChat}
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {items.map((item) => (
            <RecipeCard
              key={item.id}
              recipe={item.recipe_data}
            />
          ))}
        </div>
      )}
    </div>
  );
};
