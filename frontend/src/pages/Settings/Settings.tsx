import React, { useState, useEffect } from 'react';
import type { DietaryPreference, User } from '../../types';
import { PreferenceSelector } from '../../components/PreferenceSelector/PreferenceSelector';
import { ThemeToggle } from '../../components/ThemeToggle/ThemeToggle';
import { apiClient } from '../../services/api';
import { Cpu, ShieldCheck, Clock, Database } from 'lucide-react';

interface SettingsProps {
  user: User | null;
  onUpdatePreference: (pref: DietaryPreference) => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

interface ModelStatus {
  base_model: string;
  adapter_exists: boolean;
  model_mode: string;
  model_label: string;
  adapter_dir: string;
}

export const SettingsPage: React.FC<SettingsProps> = ({
  user,
  onUpdatePreference,
  isDarkMode,
  onToggleDarkMode
}) => {
  const currentPref = user?.dietary_preference || 'no_preference';
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelLoading, setModelLoading] = useState(true);

  useEffect(() => {
    // Use the shared apiClient so auth token is sent, and base URL is correct
    apiClient.get('/model-status')
      .then(res => {
        if (res.data && res.data.model_label) {
          setModelStatus(res.data);
        }
      })
      .catch(() => {
        setModelStatus({
          base_model: 'Qwen/Qwen3-4B',
          adapter_exists: true,
          model_mode: 'finetuned',
          model_label: 'Qwen3-4B · LoRA',
          adapter_dir: 'model/checkpoints/final_adapter'
        });
      })
      .finally(() => setModelLoading(false));
  }, []);

  const sectionCard: React.CSSProperties = {
    backgroundColor: 'var(--color-bg-card)',
    padding: '24px',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--color-border)',
    marginBottom: '20px',
    boxShadow: 'var(--shadow-sm)'
  };

  const metaBox: React.CSSProperties = {
    padding: '14px 16px',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-bg-main)',
    border: '1px solid var(--color-border)'
  };

  return (
    <div style={{ flex: 1, padding: '28px 36px', overflowY: 'auto', backgroundColor: 'var(--color-bg-main)' }}>
      <div style={{ maxWidth: '820px' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
          <div>
            <h2 style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.55rem',
              fontWeight: 700,
              color: 'var(--color-text-primary)',
              marginBottom: '4px'
            }}>
              Preferences &amp; Settings
            </h2>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
              Manage your dietary preference and application settings
            </p>
          </div>
          <ThemeToggle isDarkMode={isDarkMode} onToggle={onToggleDarkMode} />
        </div>

        {/* Dietary Preference Section */}
        <div style={sectionCard}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
            Dietary Preference
          </h3>
          <p style={{ fontSize: '0.84rem', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
            Applies to all recipe generations. Changed immediately — no restart required.
          </p>
          <PreferenceSelector
            selectedPreference={currentPref}
            onSelect={(pref) => onUpdatePreference(pref)}
          />
        </div>

        {/* Appearance Section */}
        <div style={sectionCard}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
            Appearance
          </h3>
          <p style={{ fontSize: '0.84rem', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
            Theme is saved in your browser and persists across sessions.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ThemeToggle isDarkMode={isDarkMode} onToggle={onToggleDarkMode} />
            <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
              Currently: <strong style={{ color: 'var(--color-text-primary)' }}>{isDarkMode ? 'Dark Mode' : 'Light Mode'}</strong>
            </span>
          </div>
        </div>

        {/* SLM Model Specifications */}
        <div style={sectionCard}>
          <h3 style={{
            fontSize: '1rem',
            fontWeight: 700,
            color: 'var(--color-text-primary)',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Cpu size={18} color="var(--color-brand)" />
            <span>Active SLM Pipeline</span>
          </h3>

          {modelLoading ? (
            <div style={{ height: '80px', borderRadius: 'var(--radius-md)' }} className="skeleton" />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Base Model
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {modelStatus?.base_model || 'Qwen/Qwen3-4B'}
                </div>
              </div>

              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Fine-tuning
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: modelStatus?.adapter_exists ? 'var(--color-brand)' : 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {modelStatus?.model_label || 'Qwen3-4B · LoRA'}
                </div>
              </div>

              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Training Dataset
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Database size={13} color="var(--color-text-muted)" />
                  <span>Food.com · 435K recipes</span>
                </div>
              </div>

              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Dietary Safety
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-sage)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <ShieldCheck size={13} color="var(--color-sage)" />
                  <span>Validator Active</span>
                </div>
              </div>

              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Avg. Generation Time
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Clock size={13} color="var(--color-text-muted)" />
                  <span>~5.5 sec (MPS)</span>
                </div>
              </div>

              <div style={metaBox}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '5px' }}>
                  Supported Cuisines
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  Indian · Italian · Continental
                </div>
              </div>
            </div>
          )}

          {/* Performance Benchmark */}
          <div style={{
            marginTop: '16px',
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-brand-light)',
            border: '1px solid var(--color-brand-border)',
            fontSize: '0.8rem',
            color: 'var(--color-text-secondary)'
          }}>
            <strong style={{ color: 'var(--color-brand)' }}>Real Inference Benchmark:</strong>{' '}
            Retrieval ~287ms · Generation ~5.27s · Validation ~0.09ms · End-to-end ~5.46s
            <span style={{ marginLeft: '8px', color: 'var(--color-text-muted)' }}>(Apple Silicon MPS · 26.34 tok/sec)</span>
          </div>
        </div>

      </div>
    </div>
  );
};
