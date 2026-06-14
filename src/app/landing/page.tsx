'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Brain,
  LineChart,
  Lock,
  Radio,
  ShieldCheck,
  Wallet,
} from 'lucide-react';

import { useAuth } from '@/lib/auth-context';

const FEATURES = [
  {
    icon: Brain,
    title: 'AI Recommendation Engine',
    body: 'A 250-feature ensemble (XGBoost + LightGBM + LSTM + Temporal-Fusion + RL meta-learner) ranks every NEPSE stock with probabilistic, leak-free trade plans.',
  },
  {
    icon: Radio,
    title: 'Real Live Data',
    body: 'Intraday NEPSE index and prices straight from the market — no fabricated numbers, with an honest “live / market-closed / as-of” status on every figure.',
  },
  {
    icon: Bot,
    title: 'Autonomous Trading Agent',
    body: 'Kelly-sized positions, stop-loss and trailing exits. Let the trained model find and act on the best setups — paper-trade first, go live only when you choose.',
  },
  {
    icon: ShieldCheck,
    title: 'Portfolio Self-Audit',
    body: 'Connect MeroShare and get an AI health score — concentration, sector risk, drawdowns and per-holding BUY/HOLD/SELL verdicts.',
  },
  {
    icon: Wallet,
    title: 'Broker Integration',
    body: 'MeroShare for holdings and TMS for order placement, in one place — your brokerage workflow, supercharged by the model.',
  },
  {
    icon: Lock,
    title: 'Security First',
    body: 'Bcrypt password hashing, fail-closed JWT signing, and broker credentials encrypted at rest with Fernet. Your logins are never stored in plaintext.',
  },
];

const PIPELINE = [
  { step: '01', title: 'Ingest', body: 'Live NEPSE prices, 334 stock archives, macro & global series, fundamentals and news sentiment.' },
  { step: '02', title: 'Engineer', body: '250 features — technicals, beta/alpha, sector strength, fundamentals (incl. CASA), macro correlations.' },
  { step: '03', title: 'Train', body: 'Ensemble + sequence models + PPO agent, walk-forward validated on a GPU. Retrained on fresh data.' },
  { step: '04', title: 'Act', body: 'Rank, size, and (optionally) execute trades through your broker — with full audit and risk controls.' },
];

export default function LandingPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg, #0a0e1a)', color: 'var(--text-primary, #e6ecff)' }}>
      {/* Nav */}
      <nav
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1.25rem clamp(1rem, 5vw, 4rem)', position: 'sticky', top: 0, zIndex: 10,
          background: 'rgba(10,14,26,0.7)', backdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--glass-border, rgba(255,255,255,0.08))',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 800, letterSpacing: '0.02em' }}>
          <LineChart size={24} color="var(--accent, #00ff88)" />
          NEPSE&nbsp;<span style={{ color: 'var(--accent, #00ff88)' }}>ALPHA</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <Link href="/auth/login" style={linkBtn}>Log in</Link>
          <Link href="/auth/register" style={{ ...primaryBtn, padding: '0.55rem 1.1rem' }}>Get started</Link>
        </div>
      </nav>

      {/* Hero */}
      <header style={{ maxWidth: 1080, margin: '0 auto', padding: 'clamp(3rem, 9vw, 7rem) clamp(1rem, 5vw, 2rem) 3rem', textAlign: 'center' }}>
        <div style={badge}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--accent,#00ff88)', boxShadow: '0 0 10px #00ff88' }} />
          Live NEPSE intelligence · AI-driven
        </div>
        <h1 style={{ fontSize: 'clamp(2.2rem, 6vw, 4rem)', fontWeight: 800, lineHeight: 1.05, margin: '1.25rem 0 0' }}>
          Trade NEPSE with a<br />
          <span style={{ background: 'linear-gradient(90deg,#00ff88,#4ade80,#818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            data-scientist in your pocket.
          </span>
        </h1>
        <p style={{ maxWidth: 640, margin: '1.5rem auto 0', fontSize: '1.05rem', color: 'var(--text-secondary,#9fb0d0)', lineHeight: 1.6 }}>
          A research platform that fuses live market data, a 250-feature machine-learning ensemble, and
          your broker account — to surface high-conviction trades and optionally execute them for you.
        </p>
        <div style={{ display: 'flex', gap: '0.85rem', justifyContent: 'center', marginTop: '2rem', flexWrap: 'wrap' }}>
          <Link href="/auth/register" style={primaryBtn}>
            Start free <ArrowRight size={18} />
          </Link>
          <Link href="/auth/login" style={ghostBtn}>I already have an account</Link>
        </div>
        <p style={{ marginTop: '1rem', fontSize: '0.78rem', color: 'var(--text-muted,#5a6580)' }}>
          Outputs are probabilistic research, not guaranteed returns. You stay in control of every live trade.
        </p>
      </header>

      {/* Features */}
      <section style={section}>
        <h2 style={sectionTitle}>Everything you need to act on the market</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.1rem', marginTop: '2.5rem' }}>
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} style={card}>
              <div style={{ width: 42, height: 42, borderRadius: 12, display: 'grid', placeItems: 'center', background: 'rgba(0,255,136,0.1)', border: '1px solid rgba(0,255,136,0.25)', marginBottom: '0.9rem' }}>
                <Icon size={20} color="var(--accent,#00ff88)" />
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem' }}>{title}</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary,#9fb0d0)', lineHeight: 1.55 }}>{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section style={{ ...section, paddingTop: 0 }}>
        <h2 style={sectionTitle}>From raw market to executed trade</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginTop: '2.5rem' }}>
          {PIPELINE.map(({ step, title, body }) => (
            <div key={step} style={{ ...card, position: 'relative' }}>
              <div style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent,#00ff88)', opacity: 0.5 }}>{step}</div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: '0.4rem 0 0.5rem' }}>{title}</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary,#9fb0d0)', lineHeight: 1.55 }}>{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section style={{ ...section, textAlign: 'center' }}>
        <div style={{ ...card, maxWidth: 680, margin: '0 auto', padding: '3rem 2rem', background: 'linear-gradient(160deg, rgba(0,255,136,0.08), rgba(129,140,248,0.06))' }}>
          <h2 style={{ fontSize: 'clamp(1.6rem, 4vw, 2.4rem)', fontWeight: 800 }}>Ready to let the model work for you?</h2>
          <p style={{ color: 'var(--text-secondary,#9fb0d0)', margin: '1rem auto 0', maxWidth: 460 }}>
            Create an account, connect your broker in paper mode, and watch the AI build your watchlist.
          </p>
          <div style={{ display: 'flex', gap: '0.85rem', justifyContent: 'center', marginTop: '1.75rem', flexWrap: 'wrap' }}>
            <Link href="/auth/register" style={primaryBtn}>Create your account <ArrowRight size={18} /></Link>
          </div>
        </div>
      </section>

      <footer style={{ borderTop: '1px solid var(--glass-border, rgba(255,255,255,0.08))', padding: '2rem', textAlign: 'center', color: 'var(--text-muted,#5a6580)', fontSize: '0.8rem' }}>
        © {new Date().getFullYear()} NEPSE ALPHA · For research and educational use. Not financial advice.
      </footer>
    </div>
  );
}

const linkBtn: React.CSSProperties = { color: 'var(--text-secondary,#9fb0d0)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 };
const primaryBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.8rem 1.5rem', borderRadius: 12,
  background: 'var(--accent,#00ff88)', color: '#04210f', fontWeight: 700, textDecoration: 'none', fontSize: '0.95rem',
  boxShadow: '0 8px 24px rgba(0,255,136,0.25)',
};
const ghostBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.8rem 1.5rem', borderRadius: 12,
  background: 'transparent', color: 'var(--text-primary,#e6ecff)', fontWeight: 600, textDecoration: 'none', fontSize: '0.95rem',
  border: '1px solid var(--glass-border, rgba(255,255,255,0.14))',
};
const badge: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 1rem', borderRadius: 999,
  background: 'rgba(0,255,136,0.08)', border: '1px solid rgba(0,255,136,0.25)', color: 'var(--accent,#00ff88)',
  fontSize: '0.78rem', fontFamily: 'var(--font-mono, monospace)',
};
const section: React.CSSProperties = { maxWidth: 1080, margin: '0 auto', padding: 'clamp(2.5rem, 6vw, 4.5rem) clamp(1rem, 5vw, 2rem)' };
const sectionTitle: React.CSSProperties = { fontSize: 'clamp(1.5rem, 4vw, 2.2rem)', fontWeight: 800, textAlign: 'center' };
const card: React.CSSProperties = {
  background: 'var(--glass-bg, rgba(255,255,255,0.03))', border: '1px solid var(--glass-border, rgba(255,255,255,0.08))',
  borderRadius: 16, padding: '1.5rem',
};
