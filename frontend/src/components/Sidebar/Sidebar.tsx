import React from 'react';
import type { ChatSession } from '../../types';
import type { DietPlanSummary } from '../../types/diet';
import { VeltrisLogo } from '../VeltrisLogo/VeltrisLogo';
import { Plus, MessageSquare, Bookmark, Heart, Settings, LogOut, Utensils, Trash2, Salad, ClipboardList, X } from 'lucide-react';

export type AppTab = 'chat' | 'diet' | 'saved' | 'favorites' | 'settings';

interface SidebarProps {
  chatSessions: ChatSession[];
  activeChatId?: string;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
  activeTab: AppTab;
  onSelectTab: (tab: AppTab) => void;
  onLogout: () => void;
  // Diet section
  dietPlans?: DietPlanSummary[];
  activeDietPlanId?: string;
  onOpenDiet?: () => void;
  onOpenDietPlan?: (planId: string) => void;
  // Mobile drawer
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  chatSessions,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  activeTab,
  onSelectTab,
  onLogout,
  dietPlans = [],
  activeDietPlanId,
  onOpenDiet,
  onOpenDietPlan,
  mobileOpen = false,
  onCloseMobile,
}) => {
  const navItemStyle = (isActive: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '9px 12px',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: isActive ? 'var(--color-bg-card)' : 'transparent',
    color: isActive ? 'var(--color-brand)' : 'var(--color-text-secondary)',
    fontWeight: isActive ? 600 : 500,
    fontSize: '0.855rem',
    cursor: 'pointer',
    transition: 'background-color var(--transition-fast), color var(--transition-fast)',
    width: '100%',
    textAlign: 'left',
    border: 'none',
    boxShadow: isActive ? 'var(--shadow-xs)' : 'none',
  });

  const close = () => onCloseMobile && onCloseMobile();

  return (
    <>
    <div className={`sidebar-overlay ${mobileOpen ? 'open' : ''}`} onClick={close} aria-hidden="true" />
    <aside className={`app-sidebar ${mobileOpen ? 'open' : ''}`} aria-label="Main navigation" style={{
      width: '256px',
      backgroundColor: 'var(--color-bg-sidebar)',
      borderRight: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      padding: '14px 10px',
      flexShrink: 0,
      transition: 'background-color var(--transition-slow), border-color var(--transition-slow)',
    }}>
      {/* Brand Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 10px 18px 10px' }}>
        <div style={{
          width: '30px', height: '30px',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'var(--color-brand)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0
        }}>
          <Utensils size={16} color="#FFF" />
        </div>
        <div>
          <h1 style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '1.05rem',
            fontWeight: 700,
            color: 'var(--color-text-primary)',
            lineHeight: 1.1
          }}>
            Nourish SLM
          </h1>
          <span style={{
            fontSize: '0.66rem',
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.6px',
            fontWeight: 600
          }}>
            AI Food Assistant
          </span>
        </div>
        <button className="diet-icon-btn mobile-only" style={{ marginLeft: 'auto' }} onClick={close} aria-label="Close menu">
          <X size={15} />
        </button>
      </div>

      {/* New Chat Button */}
      <button
        onClick={() => { onNewChat(); close(); }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '9px 14px',
          backgroundColor: 'var(--color-brand)',
          color: '#FFFFFF',
          borderRadius: 'var(--radius-md)',
          fontWeight: 600,
          fontSize: '0.855rem',
          marginBottom: '18px',
          boxShadow: 'var(--shadow-sm)',
          transition: 'background-color var(--transition-base)',
          width: '100%',
          justifyContent: 'center',
        }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-brand-hover)')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'var(--color-brand)')}
      >
        <Plus size={16} />
        <span>New Recipe Chat</span>
      </button>

      {/* Scrollable middle: Diet section above Chat History */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {/* 1. Diet */}
        <button
          onClick={() => { onOpenDiet && onOpenDiet(); close(); }}
          style={{ ...navItemStyle(activeTab === 'diet' && !activeDietPlanId), marginBottom: '2px' }}
          aria-current={activeTab === 'diet' && !activeDietPlanId ? 'page' : undefined}
        >
          <Salad size={16} color={activeTab === 'diet' && !activeDietPlanId ? 'var(--color-brand)' : 'var(--color-sage)'} />
          <span>Diet</span>
          <span style={{
            marginLeft: 'auto', fontSize: '0.62rem', fontWeight: 700, padding: '1px 7px', borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--color-sage-light)', color: 'var(--color-sage)'
          }}>Plans</span>
        </button>

        {/* 2. My Diet Plans */}
        {dietPlans.length > 0 && (
          <>
            <div style={{
              padding: '8px 10px 4px 10px', fontSize: '0.68rem', fontWeight: 700, color: 'var(--color-text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.6px'
            }}>
              My Diet Plans
            </div>
            {dietPlans.slice(0, 6).map(p => {
              const sel = activeTab === 'diet' && activeDietPlanId === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => { onOpenDietPlan && onOpenDietPlan(p.id); close(); }}
                  title={`${p.name} · ${p.category_name}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px', padding: '7px 10px', borderRadius: 'var(--radius-sm)',
                    backgroundColor: sel ? 'var(--color-bg-card)' : 'transparent',
                    color: sel ? 'var(--color-brand)' : 'var(--color-text-secondary)', fontWeight: sel ? 600 : 400,
                    fontSize: '0.83rem', width: '100%', textAlign: 'left', boxShadow: sel ? 'var(--shadow-xs)' : 'none', cursor: 'pointer',
                  }}
                >
                  <ClipboardList size={13} style={{ flexShrink: 0, opacity: 0.75 }} />
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</span>
                </button>
              );
            })}
          </>
        )}

        {/* 3. Chat History */}
        <div style={{
          padding: '12px 10px 6px 10px',
          fontSize: '0.68rem',
          fontWeight: 700,
          color: 'var(--color-text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.6px'
        }}>
          Recent Chats
        </div>

        {chatSessions.length === 0 ? (
          <div style={{
            padding: '10px 12px',
            fontSize: '0.81rem',
            color: 'var(--color-text-muted)',
            fontStyle: 'italic'
          }}>
            No recipe chats yet
          </div>
        ) : (
          chatSessions.map((session) => {
            const isSelected = activeTab === 'chat' && session.id === activeChatId;
            return (
              <div
                key={session.id}
                onClick={() => {
                  onSelectTab('chat');
                  onSelectChat(session.id);
                  close();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isSelected ? 'var(--color-bg-card)' : 'transparent',
                  color: isSelected ? 'var(--color-brand)' : 'var(--color-text-secondary)',
                  fontWeight: isSelected ? 600 : 400,
                  fontSize: '0.83rem',
                  cursor: 'pointer',
                  transition: 'background-color var(--transition-fast)',
                  boxShadow: isSelected ? 'var(--shadow-xs)' : 'none',
                }}
                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(0,0,0,0.04)'; }}
                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', flex: 1 }}>
                  <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.7 }} />
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {session.title}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteChat(session.id);
                  }}
                  title="Delete Chat"
                  style={{
                    opacity: 0,
                    padding: '3px',
                    cursor: 'pointer',
                    borderRadius: 'var(--radius-xs)',
                    transition: 'opacity var(--transition-fast)',
                    flexShrink: 0,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                  onMouseLeave={e => (e.currentTarget.style.opacity = '0')}
                >
                  <Trash2 size={12} color="var(--color-text-muted)" />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Navigation Footer */}
      <div style={{
        borderTop: '1px solid var(--color-border)',
        paddingTop: '10px',
        marginTop: '8px',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px'
      }}>
        <button
          onClick={() => { onSelectTab('saved'); close(); }}
          style={navItemStyle(activeTab === 'saved')}
        >
          <Bookmark size={15} />
          <span>Saved Recipes</span>
        </button>

        <button
          onClick={() => { onSelectTab('favorites'); close(); }}
          style={navItemStyle(activeTab === 'favorites')}
        >
          <Heart size={15} />
          <span>Favorites</span>
        </button>

        <button
          onClick={() => { onSelectTab('settings'); close(); }}
          style={navItemStyle(activeTab === 'settings')}
        >
          <Settings size={15} />
          <span>Settings</span>
        </button>

        <button
          onClick={onLogout}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '9px 12px',
            borderRadius: 'var(--radius-sm)',
            color: '#DC2626',
            fontWeight: 500,
            fontSize: '0.855rem',
            marginTop: '4px',
            cursor: 'pointer',
            transition: 'background-color var(--transition-fast)',
            width: '100%',
            textAlign: 'left',
          }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#FEE2E2')}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
        >
          <LogOut size={15} />
          <span>Sign Out</span>
        </button>
      </div>

      {/* Powered by Veltris */}
      <div style={{
        marginTop: '10px', paddingTop: '12px', borderTop: '1px solid var(--color-border)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px'
      }}>
        <span style={{ fontSize: '0.62rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600 }}>
          Built for
        </span>
        <VeltrisLogo height={26} />
      </div>
    </aside>
    </>
  );
};
