import React, { useState, useEffect, useRef } from 'react';
import type { User, DietaryPreference, ChatSession, Message, RecipeData } from '../../types';
import { PreferenceToggle } from '../../components/PreferenceToggle/PreferenceToggle';
import { AllergyToggle, ALLERGY_OPTIONS } from '../../components/AllergyToggle/AllergyToggle';
import { UserMenu } from '../../components/UserMenu/UserMenu';
import { Sidebar } from '../../components/Sidebar/Sidebar';
import type { AppTab } from '../../components/Sidebar/Sidebar';
import { DietDashboard } from '../Diet/DietDashboard';
import { DietPlanPage } from '../Diet/DietPlanPage';
import { dietService } from '../../services/diet';
import type { DietPlanSummary } from '../../types/diet';
import '../../styles/diet.css';
import { ChatMessage } from '../../components/ChatMessage/ChatMessage';
import { ChatInput } from '../../components/ChatInput/ChatInput';
import { LoadingState } from '../../components/LoadingState/LoadingState';
import { ThemeToggle } from '../../components/ThemeToggle/ThemeToggle';
import { SavedRecipesPage } from '../SavedRecipes/SavedRecipes';
import { SettingsPage } from '../Settings/Settings';
import { authService } from '../../services/auth';
import { chatService } from '../../services/chat';
import { recipeService } from '../../services/recipes';
import { Utensils, Check, Globe, Menu, Salad } from 'lucide-react';

interface DashboardProps {
  user: User;
  onLogout: () => void;
  onOpenOnboarding: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  user: initialUser,
  onLogout,
  isDarkMode,
  onToggleDarkMode
}) => {
  const [user, setUser] = useState<User>(initialUser);
  const [activeTab, setActiveTab] = useState<AppTab>('chat');
  // Diet section state: dashboard of categories, or a specific plan (by category or saved plan id)
  const [dietView, setDietView] = useState<{ categoryKey?: string; planId?: string; nonce: number } | null>(null);
  const [dietPlans, setDietPlans] = useState<DietPlanSummary[]>([]);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  // Cuisine is tracked as a top-level concern (single source of truth)
  const [selectedCuisine, setSelectedCuisine] = useState<string>('All');

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadChatHistory();
    loadDietPlans();
  }, []);

  const loadDietPlans = async () => {
    try {
      setDietPlans(await dietService.listPlans(true));
    } catch (e) {
      // non-fatal: the sidebar simply shows no saved plans
    }
  };

  const openDiet = () => {
    setActiveTab('diet');
    setDietView(null);
  };

  const openDietCategory = (key: string) => {
    setActiveTab('diet');
    setDietView({ categoryKey: key, nonce: Date.now() });
  };

  const openDietPlan = (planId: string) => {
    setActiveTab('diet');
    setDietView({ planId, nonce: Date.now() });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadChatHistory = async () => {
    try {
      const history = await chatService.getHistory();
      setChatSessions(history);
    } catch (e) {
      // non-fatal
    }
  };

  const loadChatSession = async (chatId: string) => {
    try {
      setActiveChatId(chatId);
      setActiveTab('chat');
      const data = await chatService.getChatSession(chatId);
      setMessages(data.messages || []);
    } catch (e) {
      // non-fatal
    }
  };

  const handleNewChat = () => {
    setActiveChatId(undefined);
    setMessages([]);
    setActiveTab('chat');
  };

  const handleDeleteChat = async (chatId: string) => {
    try {
      await chatService.deleteChatSession(chatId);
      if (activeChatId === chatId) {
        handleNewChat();
      }
      loadChatHistory();
    } catch (e) {
      // non-fatal
    }
  };

  const handlePreferenceChange = async (newPref: DietaryPreference) => {
    try {
      await authService.updatePreference(newPref);
      setUser(prev => ({ ...prev, dietary_preference: newPref }));
      showToast(`Preference updated to ${newPref.replace('_', ' ')}`, 'success');
    } catch (e) {
      showToast('Failed to update preference', 'error');
    }
  };

  const handleAllergiesChange = async (next: string[]) => {
    const prev = user.allergies || [];
    setUser(u => ({ ...u, allergies: next }));          // update immediately; saved in the background
    try {
      await authService.updateAllergies(next);
      const names = next.map(k => ALLERGY_OPTIONS.find(o => o.key === k)?.label || k);
      showToast(next.length ? `Allergy check on: ${names.join(', ')}` : 'Allergy check turned off', 'success');
    } catch (e) {
      setUser(u => ({ ...u, allergies: prev }));
      showToast('Failed to save allergies', 'error');
    }
  };

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToastMessage(msg);
    setToastType(type);
    setTimeout(() => setToastMessage(null), 3200);
  };

  const handleSendMessage = async (text: string, cuisine: string) => {
    setIsLoading(true);
    setSelectedCuisine(cuisine); // Keep cuisine in sync

    const userMsg: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);

    try {
      const res = await chatService.sendMessage(text, user.dietary_preference, cuisine, activeChatId, user.allergies || []);

      if (!activeChatId && res.chat_id) {
        setActiveChatId(res.chat_id);
      }

      const assistantMsg: Message = {
        role: 'assistant',
        content: res.message,
        recipe_data: res.recipe,
        validation: res.validation
      };

      setMessages(prev => [...prev, assistantMsg]);
      loadChatHistory();
    } catch (err: any) {
      const errorMsg: Message = {
        role: 'assistant',
        content: err?.response?.status === 422
          ? 'Please enter an ingredient or recipe request.'
          : "Recipe generation is temporarily unavailable. Please try again."
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveRecipe = async (recipe: RecipeData) => {
    try {
      await recipeService.saveRecipe(recipe.title, recipe);
      showToast(`Saved "${recipe.title}"`, 'success');
    } catch (e) {
      showToast('Could not save recipe. Try again.', 'error');
    }
  };

  const handleFavoriteRecipe = async (recipe: RecipeData) => {
    try {
      await recipeService.addFavorite(recipe.title, recipe);
      showToast(`Added "${recipe.title}" to favorites`, 'success');
    } catch (e) {
      showToast('Could not add to favorites. Try again.', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>

      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            backgroundColor: toastType === 'success' ? 'var(--color-text-primary)' : '#DC2626',
            color: '#FFFFFF',
            padding: '10px 18px',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            maxWidth: '320px'
          }}
          className="animate-fade-in"
        >
          {toastType === 'success'
            ? <Check size={15} color="var(--color-sage)" />
            : <span>⚠</span>
          }
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Sidebar */}
      <Sidebar
        dietPlans={dietPlans}
        activeDietPlanId={activeTab === 'diet' ? dietView?.planId : undefined}
        onOpenDiet={openDiet}
        onOpenDietPlan={openDietPlan}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
        chatSessions={chatSessions}
        activeChatId={activeChatId}
        onSelectChat={loadChatSession}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onLogout={onLogout}
      />

      {/* Main Content Area */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: 'var(--color-bg-main)',
        overflow: 'hidden',
        minWidth: 0
      }}>
        {/* Header */}
        <header className="app-header" style={{
          height: '60px',
          borderBottom: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-bg-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          boxShadow: 'var(--shadow-sm)',
          zIndex: 10,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
            <button className="diet-icon-btn mobile-only" onClick={() => setMobileNavOpen(true)} aria-label="Open menu">
              <Menu size={16} />
            </button>
            {activeTab === 'diet' ? <Salad size={18} color="var(--color-sage)" /> : <Utensils size={18} color="var(--color-brand)" />}
            <h2 style={{
              fontSize: '0.975rem',
              fontWeight: 700,
              color: 'var(--color-text-primary)',
              fontFamily: 'var(--font-serif)'
            }}>
              {activeTab === 'diet' ? 'Diet Planning' : 'Nourish SLM'}
            </h2>
            <span className="header-optional" style={{
              fontSize: '0.7rem',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--color-brand-light)',
              color: 'var(--color-brand)',
              fontWeight: 600,
              border: '1px solid var(--color-brand-border)'
            }}>
              Qwen3-4B · LoRA
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Cuisine indicator */}
            {selectedCuisine !== 'All' && activeTab === 'chat' && (
              <div className="header-optional" style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border)',
                fontSize: '0.75rem',
                color: 'var(--color-text-secondary)',
                fontWeight: 600
              }}>
                <Globe size={12} color="var(--color-text-muted)" />
                <span>{selectedCuisine}</span>
              </div>
            )}

            {/* Dietary Preference Toggle */}
            <PreferenceToggle
              currentPreference={user.dietary_preference}
              onSelectPreference={handlePreferenceChange}
            />

            {/* Allergy checkpoint */}
            {activeTab === 'chat' && (
              <AllergyToggle selected={user.allergies || []} onChange={handleAllergiesChange} />
            )}

            {/* Dark Mode Toggle */}
            <ThemeToggle isDarkMode={isDarkMode} onToggle={onToggleDarkMode} size="sm" />

            {/* User Profile */}
            <UserMenu user={user} />
          </div>
        </header>

        {/* View Switcher */}
        {activeTab === 'diet' && (
          dietView ? (
            <DietPlanPage
              key={`${dietView.categoryKey || ''}-${dietView.planId || ''}-${dietView.nonce}`}
              categoryKey={dietView.categoryKey}
              planId={dietView.planId}
              onBack={openDiet}
              onPlansChanged={loadDietPlans}
              onOpenPlan={openDietPlan}
              notify={showToast}
            />
          ) : (
            <DietDashboard onOpenCategory={openDietCategory} />
          )
        )}
        {activeTab === 'saved' && <SavedRecipesPage type="saved" onNewChat={handleNewChat} />}
        {activeTab === 'favorites' && <SavedRecipesPage type="favorites" onNewChat={handleNewChat} />}
        {activeTab === 'settings' && (
          <SettingsPage
            user={user}
            onUpdatePreference={handlePreferenceChange}
            isDarkMode={isDarkMode}
            onToggleDarkMode={onToggleDarkMode}
          />
        )}

        {activeTab === 'chat' && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Chat Scroll Area */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>
              {messages.length === 0 ? (
                <div
                  style={{ maxWidth: '600px', margin: '40px auto 0 auto', textAlign: 'center' }}
                  className="animate-fade-in"
                >
                  <div style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--color-brand-light)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 20px auto',
                    border: '1px solid var(--color-brand-border)'
                  }}>
                    <Utensils size={26} color="var(--color-brand)" />
                  </div>
                  <h3 style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '1.65rem',
                    fontWeight: 700,
                    color: 'var(--color-text-primary)',
                    marginBottom: '10px'
                  }}>
                    Hello, {user.name.split(' ')[0]} 👋
                  </h3>
                  <p style={{
                    fontSize: '0.95rem',
                    color: 'var(--color-text-secondary)',
                    lineHeight: 1.6,
                    marginBottom: '28px'
                  }}>
                    Tell me what ingredients you have or what you'd like to cook today.
                    I'll generate a personalized recipe using your{' '}
                    <strong style={{ color: 'var(--color-brand)' }}>
                      {user.dietary_preference.replace('_', ' ')}
                    </strong>{' '}
                    preference.
                  </p>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '12px',
                    textAlign: 'left',
                    maxWidth: '480px',
                    margin: '0 auto'
                  }}>
                    {[
                      { emoji: '🇮🇳', label: 'Indian', hint: 'Curries, biryanis, dals' },
                      { emoji: '🇮🇹', label: 'Italian', hint: 'Pasta, risotto, pizza' },
                      { emoji: '🌍', label: 'Continental', hint: 'Grills, roasts, casseroles' },
                    ].map(({ emoji, label, hint }) => (
                      <div
                        key={label}
                        style={{
                          padding: '14px',
                          borderRadius: 'var(--radius-md)',
                          backgroundColor: 'var(--color-bg-card)',
                          border: '1px solid var(--color-border)',
                          boxShadow: 'var(--shadow-xs)',
                          cursor: 'default'
                        }}
                      >
                        <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>{emoji}</div>
                        <div style={{ fontSize: '0.825rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '3px' }}>{label}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>{hint}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, index) => (
                  <ChatMessage
                    key={index}
                    message={msg}
                    onSaveRecipe={handleSaveRecipe}
                    onFavoriteRecipe={handleFavoriteRecipe}
                  />
                ))
              )}

              {isLoading && (
                <div style={{ padding: '4px 0' }}>
                  <LoadingState />
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Bottom Chat Input */}
            <div style={{
              borderTop: '1px solid var(--color-border)',
              backgroundColor: 'var(--color-bg-main)',
              flexShrink: 0,
            }}>
              <ChatInput
                onSend={handleSendMessage}
                isLoading={isLoading}
                currentCuisine={selectedCuisine}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
