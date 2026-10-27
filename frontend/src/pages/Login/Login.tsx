import React, { useState } from 'react';
import { Utensils, ArrowRight } from 'lucide-react';
import { VeltrisLogo } from '../../components/VeltrisLogo/VeltrisLogo';
import { ThemeToggle } from '../../components/ThemeToggle/ThemeToggle';
import { authService } from '../../services/auth';

interface LoginProps {
  onSuccess: () => void;
  onNavigateRegister: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export const Login: React.FC<LoginProps> = ({
  onSuccess,
  onNavigateRegister,
  isDarkMode,
  onToggleDarkMode
}) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please enter your email and password.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await authService.login(email, password);
      onSuccess();
    } catch (err: any) {
      if (!err?.response) {
        // No HTTP response: the backend is down or still starting (e.g. loading the model)
        setError('Cannot reach the Nourish server. It may still be starting up - please wait a moment and try again.');
      } else {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Invalid email or password. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 14px',
    borderRadius: 'var(--radius-md)',
    border: '1.5px solid var(--color-border)',
    fontSize: '0.9rem',
    outline: 'none',
    backgroundColor: 'var(--color-bg-input)',
    color: 'var(--color-text-primary)',
    transition: 'border-color var(--transition-base)',
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--color-bg-main)',
      padding: '20px',
      position: 'relative',
    }}>
      {/* Theme toggle top-right */}
      <div style={{ position: 'absolute', top: '20px', right: '20px' }}>
        <ThemeToggle isDarkMode={isDarkMode} onToggle={onToggleDarkMode} />
      </div>

      {/* Veltris logo top-left */}
      <div style={{ position: 'absolute', top: '20px', left: '24px' }}>
        <VeltrisLogo height={34} />
      </div>

      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          backgroundColor: 'var(--color-bg-card)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          padding: '36px 32px'
        }}
        className="animate-fade-in"
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '28px' }}>
          <div style={{
            width: '42px', height: '42px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <Utensils size={22} color="#FFF" />
          </div>
          <div>
            <h2 style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.35rem',
              fontWeight: 700,
              color: 'var(--color-text-primary)',
              lineHeight: 1.1
            }}>
              Nourish SLM
            </h2>
            <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
              AI-Powered Recipe Assistant
            </span>
          </div>
        </div>

        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
          Welcome back
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginBottom: '24px' }}>
          Sign in to your personalized recipe assistant
        </p>

        {error && (
          <div style={{
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: '#FEE2E2',
            color: '#B91C1C',
            fontSize: '0.83rem',
            marginBottom: '16px',
            border: '1px solid #FECACA',
            fontWeight: 500
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              marginBottom: '6px',
              textTransform: 'uppercase',
              letterSpacing: '0.4px'
            }}>
              Email Address
            </label>
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              style={inputStyle}
              onFocus={e => e.target.style.borderColor = 'var(--color-brand)'}
              onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: 'var(--color-text-secondary)',
              marginBottom: '6px',
              textTransform: 'uppercase',
              letterSpacing: '0.4px'
            }}>
              Password
            </label>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={inputStyle}
              onFocus={e => e.target.style.borderColor = 'var(--color-brand)'}
              onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
            />
          </div>

          <button
            id="login-submit"
            type="submit"
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              width: '100%',
              padding: '12px',
              backgroundColor: loading ? 'var(--color-border)' : 'var(--color-brand)',
              color: '#FFF',
              borderRadius: 'var(--radius-md)',
              fontWeight: 700,
              fontSize: '0.92rem',
              marginTop: '4px',
              transition: 'background-color var(--transition-base)',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : 'var(--shadow-sm)'
            }}
          >
            <span>{loading ? 'Signing in...' : 'Sign In'}</span>
            {!loading && <ArrowRight size={17} />}
          </button>
        </form>

        <div style={{
          marginTop: '24px',
          textAlign: 'center',
          fontSize: '0.85rem',
          color: 'var(--color-text-secondary)'
        }}>
          Don't have an account?{' '}
          <button
            onClick={onNavigateRegister}
            style={{
              color: 'var(--color-brand)',
              fontWeight: 700,
              cursor: 'pointer',
              textDecoration: 'underline',
              textDecorationColor: 'transparent',
              transition: 'text-decoration-color var(--transition-fast)',
            }}
            onMouseEnter={e => (e.target as HTMLButtonElement).style.textDecorationColor = 'var(--color-brand)'}
            onMouseLeave={e => (e.target as HTMLButtonElement).style.textDecorationColor = 'transparent'}
          >
            Create Account
          </button>
        </div>
      </div>
    </div>
  );
};
