import React, { useState, useEffect } from 'react';
import type { User } from './types';
import { authService } from './services/auth';
import { Login } from './pages/Login/Login';
import { Register } from './pages/Register/Register';
import { Onboarding } from './pages/Onboarding/Onboarding';
import { VeltrisLogo } from './components/VeltrisLogo/VeltrisLogo';
import { Dashboard } from './pages/Dashboard/Dashboard';

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<'login' | 'register' | 'onboarding' | 'dashboard'>('login');
  const [loading, setLoading] = useState(true);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('nourish_theme') === 'dark';
  });

  // Apply theme whenever it changes
  useEffect(() => {
    const theme = isDarkMode ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nourish_theme', theme);
  }, [isDarkMode]);

  useEffect(() => {
    checkAuth();
    const handleAuthLogout = () => {
      setUser(null);
      setView('login');
    };
    window.addEventListener('auth_logout', handleAuthLogout);
    return () => window.removeEventListener('auth_logout', handleAuthLogout);
  }, []);

  const checkAuth = async () => {
    setLoading(true);
    const storedUser = authService.getStoredUser();
    if (storedUser) {
      try {
        const profile = await authService.getProfile();
        setUser(profile);
        setView('dashboard');
      } catch (e) {
        setUser(null);
        setView('login');
      }
    } else {
      setView('login');
    }
    setLoading(false);
  };

  const handleLoginSuccess = async () => {
    try {
      const profile = await authService.getProfile();
      setUser(profile);
      // Show onboarding only for new registrations (no dietary preference set)
      if (!profile.dietary_preference || profile.dietary_preference === 'no_preference') {
        setView('onboarding');
      } else {
        setView('dashboard');
      }
    } catch (e) {
      setView('dashboard');
    }
  };

  const handleLogout = async () => {
    await authService.logout();
    setUser(null);
    setView('login');
  };

  const toggleDarkMode = () => {
    setIsDarkMode(prev => !prev);
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        height: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-bg-main)',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <VeltrisLogo height={40} />
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          border: '3px solid var(--color-border)',
          borderTopColor: 'var(--color-brand)',
          animation: 'spin 0.8s linear infinite'
        }} />
        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', fontWeight: 500 }}>
          Loading Nourish SLM...
        </span>
      </div>
    );
  }

  if (view === 'login') {
    return (
      <Login
        onSuccess={handleLoginSuccess}
        onNavigateRegister={() => setView('register')}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
      />
    );
  }

  if (view === 'register') {
    return (
      <Register
        onSuccess={handleLoginSuccess}
        onNavigateLogin={() => setView('login')}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
      />
    );
  }

  if (view === 'onboarding') {
    return (
      <Onboarding
        initialPreference={user?.dietary_preference || 'no_preference'}
        onComplete={() => setView('dashboard')}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
      />
    );
  }

  if (user && view === 'dashboard') {
    return (
      <Dashboard
        user={user}
        onLogout={handleLogout}
        onOpenOnboarding={() => setView('onboarding')}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
      />
    );
  }

  return (
    <Login
      onSuccess={handleLoginSuccess}
      onNavigateRegister={() => setView('register')}
      isDarkMode={isDarkMode}
      onToggleDarkMode={toggleDarkMode}
    />
  );
};

export default App;
