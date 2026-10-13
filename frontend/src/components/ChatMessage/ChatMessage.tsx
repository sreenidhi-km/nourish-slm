import React from 'react';
import type { Message, RecipeData } from '../../types';
import { RecipeCard } from '../RecipeCard/RecipeCard';
import { ChefHat, User } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
  onSaveRecipe?: (recipe: RecipeData) => void;
  onFavoriteRecipe?: (recipe: RecipeData) => void;
  onRegenerateRecipe?: () => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onSaveRecipe,
  onFavoriteRecipe,
  onRegenerateRecipe
}) => {
  const isUser = message.role === 'user';

  return (
    <div
      style={{
        display: 'flex',
        gap: '14px',
        margin: '16px 0',
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start'
      }}
      className="animate-fade-in"
    >
      {/* Avatar */}
      <div
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          backgroundColor: isUser ? 'var(--color-brand)' : 'var(--color-sage)',
          color: '#FFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: 'var(--shadow-sm)'
        }}
      >
        {isUser ? <User size={18} /> : <ChefHat size={18} />}
      </div>

      {/* Content */}
      <div style={{ maxWidth: '85%', display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        <div
          style={{
            padding: '12px 18px',
            borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
            backgroundColor: isUser ? 'var(--color-brand)' : 'var(--color-bg-card)',
            color: isUser ? '#FFFFFF' : 'var(--color-text-primary)',
            fontSize: '0.95rem',
            lineHeight: 1.5,
            border: isUser ? 'none' : '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          {message.content}
        </div>

        {/* Structured Recipe Card if available */}
        {message.recipe_data && (
          <RecipeCard
            recipe={message.recipe_data}
            validation={message.validation}
            onSave={onSaveRecipe}
            onFavorite={onFavoriteRecipe}
            onRegenerate={onRegenerateRecipe}
          />
        )}
      </div>
    </div>
  );
};
