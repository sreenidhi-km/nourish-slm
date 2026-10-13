import React, { useState } from 'react';
import type { DietaryPreference } from '../../types';
import { PreferenceSelector } from '../../components/PreferenceSelector/PreferenceSelector';
import { VeltrisLogo } from '../../components/VeltrisLogo/VeltrisLogo';
import { ThemeToggle } from '../../components/ThemeToggle/ThemeToggle';
import { authService } from '../../services/auth';
import { Utensils, ArrowRight } from 'lucide-react';

interface OnboardingProps {
  initialPreference?: DietaryPreference;
  onComplete: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export const Onboarding: React.FC<OnboardingProps> = ({
  initialPreference = 'no_preference',
  onComplete,
  isDarkMode,
  onToggleDarkMode
}) => {
  const [selectedPref, setSelectedPref] = useState<DietaryPreference>(initialPreference);
  const [saving, setSaving] = useState(false);

  const handleContinue = async () => {
    setSaving(true);
    try {
      await authService.updatePreference(selectedPref);
    } catch (e) {
      // non-fatal — proceed anyway
    } finally {
      setSaving(false);
      onComplete();
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: 'var(--color-bg-main)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 20px',
      position: 'relative',
    }}>
      {/* Theme toggle */}
      <div style={{ position: 'absolute', top: '20px', right: '20px' }}>
        <ThemeToggle isDarkMode={isDarkMode} onToggle={onToggleDarkMode} />
      </div>

      {/* Veltris logo top-left */}
      <div style={{ position: 'absolute', top: '20px', left: '24px' }}>
        <VeltrisLogo height={34} />
      </div>

      <div style={{ maxWidth: '840px', width: '100%', textAlign: 'center' }} className="animate-fade-in">
        {/* Logo */}
        <div style={{
          width: '52px', height: '52px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-brand)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 20px auto',
          boxShadow: 'var(--shadow-md)'
        }}>
          <Utensils size={26} color="#FFF" />
        </div>

        <h1 style={{
          fontFamily: 'var(--font-serif)',
          fontSize: '2.1rem',
          fontWeight: 700,
          color: 'var(--color-text-primary)',
          marginBottom: '10px'
        }}>
          What kind of food do you enjoy?
        </h1>
        <p style={{
          fontSize: '1rem',
          color: 'var(--color-text-secondary)',
          marginBottom: '40px',
          maxWidth: '480px',
          margin: '0 auto 40px auto'
        }}>
          Choose your dietary preference. This guides every recipe generated for you.
          You can change it anytime from Settings.
        </p>

        <PreferenceSelector
          selectedPreference={selectedPref}
          onSelect={(pref) => setSelectedPref(pref)}
        />

        <div style={{ marginTop: '40px', display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={handleContinue}
            disabled={saving}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '14px 36px',
              backgroundColor: saving ? 'var(--color-border)' : 'var(--color-brand)',
              color: '#FFFFFF',
              borderRadius: 'var(--radius-md)',
              fontWeight: 700,
              fontSize: '1rem',
              boxShadow: saving ? 'none' : 'var(--shadow-md)',
              transition: 'all var(--transition-base)',
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >
            <span>{saving ? 'Saving...' : 'Start Cooking'}</span>
            {!saving && <ArrowRight size={20} />}
          </button>
        </div>
      </div>
    </div>
  );
};
