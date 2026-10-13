import React from 'react';
import type { ChatSession } from '../../types';
import { VeltrisLogo } from '../VeltrisLogo/VeltrisLogo';
import { Plus, MessageSquare, Bookmark, Heart, Settings, LogOut, Utensils, Trash2 } from 'lucide-react';

interface SidebarProps {
  chatSessions: ChatSession[];
  activeChatId?: string;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
  activeTab: 'chat' | 'saved' | 'favorites' | 'settings';
  onSelectTab: (tab: 'chat' | 'saved' | 'favorites' | 'settings') => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  chatSessions,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  activeTab,
  onSelectTab,
  onLogout
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

  return (
    <aside style={{
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
      </div>

      {/* New Chat Button */}
      <button
        onClick={onNewChat}
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

      {/* Recent Chats Section */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{
          padding: '4px 10px 6px 10px',
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
          onClick={() => onSelectTab('saved')}
          style={navItemStyle(activeTab === 'saved')}
        >
          <Bookmark size={15} />
          <span>Saved Recipes</span>
        </button>

        <button
          onClick={() => onSelectTab('favorites')}
          style={navItemStyle(activeTab === 'favorites')}
        >
          <Heart size={15} />
          <span>Favorites</span>
        </button>

        <button
          onClick={() => onSelectTab('settings')}
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
  );
};
