'use client';

// ═══════════════════════════════════════════
// Shared UI Components
// ═══════════════════════════════════════════

export function Card({ children, style, onClick }) {
  return (
    <div onClick={onClick} style={{
      background: 'var(--card)', border: '1px solid var(--card-border)', borderRadius: 16,
      padding: 24, boxShadow: 'var(--card-shadow)',
      animation: 'fadeIn 0.3s ease', cursor: onClick ? 'pointer' : 'default', ...style
    }}>{children}</div>
  );
}

export function StatCard({ label, value, sub, color, icon }) {
  return (
    <Card style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: -8, right: -8, fontSize: 48, opacity: 0.06,
        fontWeight: 900, color: color || 'var(--text)'
      }}>{icon || ''}</div>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 6, fontWeight: 500, letterSpacing: 0.3 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color || 'var(--text)', letterSpacing: -0.5 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>{sub}</div>}
    </Card>
  );
}

export function Badge({ text, color }) {
  const colors = {
    green: { bg: 'var(--green-bg)', text: 'var(--green)' },
    red: { bg: 'var(--red-bg)', text: 'var(--red)' },
    yellow: { bg: 'var(--yellow-bg)', text: 'var(--yellow)' },
    blue: { bg: 'var(--blue-bg)', text: 'var(--blue)' },
    purple: { bg: 'var(--accent-bg)', text: 'var(--accent)' },
  };
  const c = colors[color] || colors.blue;
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 8,
      fontSize: 11, fontWeight: 600, background: c.bg, color: c.text
    }}>{text}</span>
  );
}

export function SectionTitle({ children, action }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>{children}</h3>
      {action}
    </div>
  );
}

export function Toggle({ on, set }) {
  return (
    <button onClick={() => set(!on)} style={{
      width: 48, height: 26, borderRadius: 13, border: 'none', cursor: 'pointer',
      position: 'relative', background: on ? 'var(--accent)' : '#cbd5e1', transition: 'background 0.2s',
      flexShrink: 0
    }}>
      <div style={{
        width: 20, height: 20, borderRadius: 10, background: '#fff',
        position: 'absolute', top: 3, left: on ? 25 : 3, transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.15)'
      }} />
    </button>
  );
}

export function InputField({ value, onChange, placeholder, type, style: extraStyle }) {
  return (
    <input
      value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} type={type || 'text'}
      style={{
        width: '100%', padding: '10px 14px', borderRadius: 10,
        border: '1px solid var(--border-light)', background: 'var(--input-bg)', color: 'var(--text)',
        fontSize: 13, outline: 'none', transition: 'border-color 0.2s', ...extraStyle
      }}
    />
  );
}

export function PillButton({ selected, onClick, children, style, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '8px 16px', borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
      border: selected ? '2px solid var(--accent)' : '1px solid var(--border-light)',
      background: selected ? 'var(--accent-bg)' : 'var(--card)',
      color: selected ? 'var(--accent)' : 'var(--text-secondary)',
      opacity: disabled ? 0.5 : 1, transition: 'all 0.15s', ...style
    }}>{children}</button>
  );
}

export function EmptyState({ text, small }) {
  return <div style={{ textAlign: 'center', padding: small ? 20 : 48, color: 'var(--text-dim)', fontSize: 13 }}>{text}</div>;
}

export function LoadingState({ text }) {
  return <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-dim)', fontSize: 13 }}>{text || '...'}</div>;
}

export function ProgressBar({ value, max, color, height }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ width: '100%', height: height || 8, background: 'var(--input-bg)', borderRadius: 99, overflow: 'hidden' }}>
      <div style={{
        width: `${pct}%`, height: '100%', borderRadius: 99,
        background: color || 'var(--accent)', transition: 'width 0.6s ease'
      }} />
    </div>
  );
}

export function ActionButton({ children, onClick, variant, style: extraStyle, disabled }) {
  const variants = {
    primary: { bg: 'var(--accent)', color: '#fff', border: 'none' },
    secondary: { bg: 'var(--card)', color: 'var(--accent)', border: '1px solid var(--accent)' },
    ghost: { bg: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-light)' },
  };
  const v = variants[variant] || variants.primary;
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '10px 20px', borderRadius: 10, fontSize: 13, fontWeight: 600,
      cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1,
      background: v.bg, color: v.color, border: v.border,
      transition: 'all 0.15s', ...extraStyle
    }}>{children}</button>
  );
}
