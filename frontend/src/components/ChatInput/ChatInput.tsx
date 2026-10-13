import React, { useState } from 'react';
import { Send, Globe, Sparkles } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string, cuisine: string) => void;
  isLoading: boolean;
  currentCuisine?: string;
}

const QUICK_PROMPTS = [
  "I have potatoes, onions and tomatoes",
  "I have chicken, rice and onions",
  "Give me a pasta recipe",
  "I have eggs and vegetables, what can I make?",
  "High-protein vegetarian dinner ideas",
];

// ONLY these three cuisines are supported
const CUISINES = [
  { value: "All", label: "Any Cuisine" },
  { value: "Indian", label: "🇮🇳 Indian" },
  { value: "Italian", label: "🇮🇹 Italian" },
  { value: "Continental", label: "🌍 Continental" },
];

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading, currentCuisine }) => {
  const [text, setText] = useState('');
  const [selectedCuisine, setSelectedCuisine] = useState(currentCuisine || 'All');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSend(text.trim(), selectedCuisine);
    setText('');
  };

  const handleChipClick = (prompt: string) => {
    if (isLoading) return;
    onSend(prompt, selectedCuisine);
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '860px',
      margin: '0 auto',
      padding: '12px 20px 20px 20px'
    }}>
      {/* Quick Prompt Chips */}
      <div style={{
        display: 'flex',
        gap: '7px',
        overflowX: 'auto',
        paddingBottom: '10px',
        marginBottom: '10px',
        msOverflowStyle: 'none',
        scrollbarWidth: 'none'
      }}>
        {QUICK_PROMPTS.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => handleChipClick(prompt)}
            disabled={isLoading}
            style={{
              whiteSpace: 'nowrap',
              padding: '5px 12px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
              fontSize: '0.775rem',
              color: 'var(--color-text-secondary)',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'all var(--transition-fast)',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.5 : 1,
              boxShadow: 'var(--shadow-xs)',
            }}
            onMouseEnter={e => {
              if (!isLoading) {
                (e.target as HTMLButtonElement).style.borderColor = 'var(--color-brand)';
                (e.target as HTMLButtonElement).style.color = 'var(--color-brand)';
              }
            }}
            onMouseLeave={e => {
              (e.target as HTMLButtonElement).style.borderColor = 'var(--color-border)';
              (e.target as HTMLButtonElement).style.color = 'var(--color-text-secondary)';
            }}
          >
            <Sparkles size={11} color="var(--color-brand)" />
            <span>{prompt}</span>
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          backgroundColor: 'var(--color-bg-card)',
          border: '1.5px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '8px 10px',
          boxShadow: 'var(--shadow-md)',
          transition: 'border-color var(--transition-base)',
        }}
        onFocus={e => e.currentTarget.style.borderColor = 'var(--color-brand)'}
        onBlur={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
      >
        {/* Cuisine Selector Dropdown — Only Indian / Italian / Continental */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          paddingRight: '10px',
          borderRight: '1.5px solid var(--color-border)',
          flexShrink: 0
        }}>
          <Globe size={15} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
          <select
            value={selectedCuisine}
            onChange={(e) => setSelectedCuisine(e.target.value)}
            style={{
              border: 'none',
              backgroundColor: 'transparent',
              fontSize: '0.82rem',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              outline: 'none',
              cursor: 'pointer',
              minWidth: '110px',
            }}
          >
            {CUISINES.map((c) => (
              <option key={c.value} value={c.value} style={{ backgroundColor: 'var(--color-bg-card)', color: 'var(--color-text-primary)' }}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {/* Text Input */}
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Tell me what's in your kitchen... (e.g. 'potatoes, onions, tomatoes')"
          disabled={isLoading}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            backgroundColor: 'transparent',
            fontSize: '0.92rem',
            color: 'var(--color-text-primary)',
            padding: '5px 8px',
          }}
        />

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          style={{
            width: '38px',
            height: '38px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: text.trim() && !isLoading ? 'var(--color-brand)' : 'var(--color-border)',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color var(--transition-base)',
            cursor: text.trim() && !isLoading ? 'pointer' : 'not-allowed',
            flexShrink: 0,
          }}
        >
          <Send size={17} />
        </button>
      </form>

      {/* Cuisine indicator */}
      {selectedCuisine !== 'All' && (
        <div style={{
          marginTop: '8px',
          textAlign: 'center',
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)'
        }}>
          Filtering for <strong style={{ color: 'var(--color-brand)' }}>{selectedCuisine}</strong> cuisine recipes
        </div>
      )}
    </div>
  );
};
