import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ClipboardCheck, Lightbulb } from 'lucide-react';
import type { Assessment } from '../../types/diet';

const KIND_LABEL: Record<string, string> = {
  restriction: 'Restriction', nutrient_gap: 'Nutrient', data: 'Data', timing: 'Timing',
};

function icon(status: string) {
  if (status === 'ok' || status === 'estimate' || status === 'info') return <CheckCircle2 size={16} color="var(--color-sage)" />;
  if (status === 'conflict' || status.endsWith('significant')) return <XCircle size={16} color="#DC2626" />;
  if (status === 'unknown' || status === 'incomplete') return <HelpCircle size={16} color="var(--color-text-muted)" />;
  return <AlertTriangle size={16} color="#D97706" />;
}

export const AssessmentPanel: React.FC<{ assessment: Assessment; fresh: boolean }> = ({ assessment, fresh }) => {
  const sorted = [...assessment.checks].sort((a, b) => Number(a.status === 'ok') - Number(b.status === 'ok'));
  return (
    <section className="diet-panel" aria-live="polite" aria-label="Check My Diet results">
      <div className="diet-panel-title">
        <h3><ClipboardCheck size={16} color="var(--color-brand)" /> Plan review</h3>
        {fresh && <span className="diet-chip diet-chip-sage">Updated for your latest changes</span>}
      </div>
      <div className={`assess-label assess-${assessment.label_key}`}>{assessment.label}</div>
      <p className="diet-subtitle" style={{ fontSize: '0.84rem', marginTop: 8 }}>{assessment.summary}</p>
      <div className="check-list">
        {sorted.map(c => (
          <div className="check-item" key={c.key}>
            {icon(c.status)}
            <div><b>{c.title}</b><span className="check-kind">{KIND_LABEL[c.kind] || c.kind}</span><br />{c.message}</div>
          </div>
        ))}
      </div>
      {assessment.suggestions.length > 0 && (
        <>
          <h5 style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', margin: '14px 0 6px' }}>
            Suggestions
          </h5>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {assessment.suggestions.map((s, i) => (
              <li key={i} className="check-item"><Lightbulb size={15} color="var(--color-brand)" /><span>{s.text}
                <span className="check-kind">{s.kind === 'restriction' ? 'restriction conflict' : s.kind === 'nutrient_gap' ? 'calculated gap' : 'general'}</span></span></li>
            ))}
          </ul>
        </>
      )}
      <p className="diet-disclaimer" style={{ marginTop: 12 }}>{assessment.disclaimer}</p>
    </section>
  );
};
