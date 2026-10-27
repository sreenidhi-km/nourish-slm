import React, { useEffect, useRef, useState } from 'react';
import { Bot, Send, ChevronDown, ChevronUp, Check, Loader2 } from 'lucide-react';
import type { DietChatMessage, DietPlan, Proposal } from '../../types/diet';
import { dietService, apiErrorMessage } from '../../services/diet';
import { MacroRow } from './NutritionSummary';

interface Props {
  plan: DietPlan;
  onPlanUpdated: (plan: DietPlan) => void;
}

const STARTERS = [
  'Why is my lunch included?',
  'Replace my lunch with a higher-protein meal',
  'Can you suggest an Indian alternative for dinner?',
  'Is my pre-training snack suitable?',
  'Does this plan meet my requirements?',
  'How can I modify this plan for a rest day?',
];

function renderText(text: string) {
  // minimal formatting: **bold** and line breaks (no HTML injection)
  return text.split('\n').map((line, i) => (
    <React.Fragment key={i}>
      {line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
        part.startsWith('**') && part.endsWith('**') ? <strong key={j}>{part.slice(2, -2)}</strong> : <React.Fragment key={j}>{part}</React.Fragment>)}
      {i < text.split('\n').length - 1 && <br />}
    </React.Fragment>
  ));
}

const ProposalCard: React.FC<{ p: Proposal; busy: boolean; onApply: () => void }> = ({ p, busy, onApply }) => {
  const after = p.preview.meal_after?.nutrition;
  const tb = p.preview.totals_before?.values || {};
  const ta = p.preview.totals_after?.values || {};
  const d = (k: 'kcal' | 'protein' | 'carbs') => {
    const a = ta[k]; const b = tb[k];
    if (a === null || a === undefined || b === null || b === undefined) return '—';
    const diff = Math.round((a - b) * (k === 'kcal' ? 1 : 10)) / (k === 'kcal' ? 1 : 10);
    return `${Math.round(a)}${k === 'kcal' ? ' kcal' : ' g'} (${diff >= 0 ? '+' : ''}${diff})`;
  };
  return (
    <div className="proposal">
      <div className="proposal-title">{p.title}</div>
      <div className="proposal-desc">{p.description}</div>
      {after && <MacroRow nutrition={after} compact />}
      <div className="proposal-delta" style={{ marginTop: 6 }}>
        <span>Day calories</span><span>{d('kcal')}</span>
        <span>Day protein</span><span>{d('protein')}</span>
        <span>Day carbs</span><span>{d('carbs')}</span>
        <span>Review after</span><span>{p.preview.assessment_after?.label}</span>
      </div>
      {p.status === 'applied'
        ? <span className="diet-chip diet-chip-sage"><Check size={11} /> Applied & saved</span>
        : <button className="diet-btn diet-btn-sage diet-btn-sm" disabled={busy} onClick={onApply}>Apply to my plan</button>}
    </div>
  );
};

export const DietAssistant: React.FC<Props> = ({ plan, onPlanUpdated }) => {
  const [messages, setMessages] = useState<DietChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Each plan id has its own conversation; switching plans loads that plan's history only.
  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setLoading(true);
    setError(null);
    dietService.getChat(plan.id)
      .then(res => { if (!cancelled) setMessages(res.messages); })
      .catch(e => { if (!cancelled) setError(apiErrorMessage(e, 'Could not load this assistant.')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plan.id]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [messages, sending]);

  const send = async (text: string) => {
    const msg = text.trim();
    if (!msg || sending) return;
    setInput('');
    setSending(true);
    setError(null);
    const temp: DietChatMessage = { id: -Date.now(), role: 'user', content: msg, proposals: [], meta: {}, created_at: '' };
    setMessages(m => [...m, temp]);
    try {
      const res = await dietService.sendChat(plan.id, msg);
      setMessages(m => [...m.filter(x => x.id !== temp.id), res.user_message, res.reply]);
    } catch (e) {
      setMessages(m => m.filter(x => x.id !== temp.id));
      setInput(msg);
      setError(apiErrorMessage(e, 'The assistant is unavailable right now.'));
    } finally {
      setSending(false);
    }
  };

  const apply = async (messageId: number, proposalId: string) => {
    setSending(true);
    setError(null);
    try {
      const res = await dietService.applyProposal(plan.id, messageId, proposalId);
      setMessages(m => [...m.map(x => (x.id === messageId ? res.message : x)), res.confirmation]);
      onPlanUpdated(res.plan);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not apply that change.'));
    } finally {
      setSending(false);
    }
  };

  return (
    <section className={`diet-panel assistant ${collapsed ? 'collapsed' : ''}`} aria-label={plan.assistant_name}>
      <div className="assistant-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'var(--color-sage)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Bot size={16} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.86rem', color: 'var(--color-text-primary)' }}>{plan.assistant_name}</div>
            <div className="diet-card-caption">Ask about this plan · knows your meals and restrictions</div>
          </div>
        </div>
        <button className="diet-icon-btn assistant-toggle" onClick={() => setCollapsed(c => !c)} aria-expanded={!collapsed}
          aria-label={collapsed ? 'Show assistant' : 'Hide assistant'}>
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>
      <div className="assistant-body" aria-live="polite">
        {loading && <div className="diet-card-caption"><Loader2 size={13} className="animate-spin" /> Loading conversation…</div>}
        {!loading && messages.length === 0 && (
          <div className="assistant-msg assistant">
            Hi! I'm your {plan.assistant_name}. I can explain why meals are in your plan, suggest swaps that respect your
            restrictions, check timing around training and adjust the plan — I'll always show the recalculated numbers and
            only change your plan when you press Apply.
          </div>
        )}
        {messages.map(m => (
          <div key={m.id} className={`assistant-msg ${m.role}`}>
            {renderText(m.content)}
            {m.role === 'assistant' && m.proposals.map(p => (
              <ProposalCard key={p.id} p={p} busy={sending} onApply={() => apply(m.id, p.id)} />
            ))}
          </div>
        ))}
        {sending && <div className="assistant-msg assistant"><Loader2 size={13} className="animate-spin" /> Thinking…</div>}
        {error && <div className="diet-error">{error}</div>}
        <div ref={endRef} />
      </div>
      {messages.length < 2 && !loading && (
        <div className="assistant-suggestions">
          {STARTERS.map(s => <button key={s} className="diet-chip" disabled={sending} onClick={() => send(s)}>{s}</button>)}
        </div>
      )}
      <form className="assistant-input" onSubmit={e => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about this plan…" maxLength={1000}
          aria-label={`Message ${plan.assistant_name}`} disabled={sending} />
        <button type="submit" className="diet-btn diet-btn-primary" disabled={sending || !input.trim()} aria-label="Send">
          <Send size={14} />
        </button>
      </form>
    </section>
  );
};
