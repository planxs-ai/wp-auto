'use client';
import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AuthProvider, useAuth, useCurrentUser, usePlanFeatures } from '@/lib/auth';
import { Badge } from '@/components/ui';

const NAV_ITEMS = [
  { id: 'dashboard', label: '홈', icon: '\u25ce', path: '/dashboard' },
  { id: 'blog', label: '내 블로그', icon: '\u25a3', path: '/blog' },
  { id: 'revenue', label: '수익', icon: '\u2606', path: '/revenue' },
  { id: 'settings', label: '설정', icon: '\u2699', path: '/settings' },
];

function ConsumerShell({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const { displayName, planId: actualPlanId, onboardingCompleted, trialActive, isAdmin } = useCurrentUser();
  const { plan, planId, isTrial } = usePlanFeatures();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (!loading && user && !onboardingCompleted && pathname !== '/onboarding') {
      router.push('/onboarding');
    }
  }, [loading, user, onboardingCompleted, pathname, router]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <div style={{ color: 'var(--text-dim)', fontSize: 14 }}>Loading...</div>
      </div>
    );
  }

  if (!user) return null;
  if (!onboardingCompleted && pathname !== '/onboarding') return null;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Desktop Sidebar */}
      <aside className="consumer-sidebar" style={styles.sidebar}>
        <div style={styles.logo}>
          <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent)', letterSpacing: -0.5 }}>AutoBlog</span>
        </div>

        {/* User info */}
        <div style={styles.userBox}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{displayName}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
            <Badge text={plan.name} color={planId === 'mama' ? 'yellow' : planId === 'premium' ? 'purple' : 'blue'} />
            {isTrial && <Badge text="7\uc77c \uccb4\ud5d8" color="green" />}
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '8px 12px' }}>
          {NAV_ITEMS.map(item => {
            const active = pathname === item.path;
            return (
              <button
                key={item.id}
                onClick={() => { router.push(item.path); setMobileMenuOpen(false); }}
                style={{
                  ...styles.navItem,
                  background: active ? 'var(--accent-bg)' : 'transparent',
                  color: active ? 'var(--accent)' : 'var(--text-secondary)',
                  fontWeight: active ? 700 : 500,
                }}
              >
                <span style={{ fontSize: 16, width: 24, textAlign: 'center' }}>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}

          {actualPlanId === 'standard' && (
            <button
              onClick={() => router.push('/upgrade')}
              style={{ ...styles.navItem, ...styles.upgradeBtn }}
            >
              <span style={{ fontSize: 16, width: 24, textAlign: 'center' }}>{'\u2b50'}</span>
              <span>업그레이드</span>
            </button>
          )}

          {isAdmin && (
            <button
              onClick={() => window.location.href = '/'}
              style={{ ...styles.navItem, ...styles.adminBtn }}
            >
              <span style={{ fontSize: 16, width: 24, textAlign: 'center' }}>{'\u2630'}</span>
              <span>관리자 대시보드</span>
            </button>
          )}
        </nav>

        {/* Plan usage */}
        <div style={styles.usageBox}>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>오늘 발행</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            <strong>0</strong> / {plan.maxDailyPosts === 999 ? '무제한' : plan.maxDailyPosts}편
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="consumer-mobile-header" style={styles.mobileHeader}>
        <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} style={styles.hamburger}>
          {mobileMenuOpen ? '\u2715' : '\u2630'}
        </button>
        <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>AutoBlog</span>
        <div style={{ width: 32 }} />
      </div>

      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div style={styles.mobileOverlay} onClick={() => setMobileMenuOpen(false)}>
          <div style={styles.mobileMenu} onClick={e => e.stopPropagation()}>
            <div style={styles.userBox}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{displayName}</div>
              <Badge text={plan.name} color={planId === 'mama' ? 'yellow' : planId === 'premium' ? 'purple' : 'blue'} />
              {isTrial && <Badge text="7\uc77c \uccb4\ud5d8" color="green" />}
            </div>
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => { router.push(item.path); setMobileMenuOpen(false); }}
                style={{
                  ...styles.navItem,
                  background: pathname === item.path ? 'var(--accent-bg)' : 'transparent',
                  color: pathname === item.path ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
            {isAdmin && (
              <button
                onClick={() => { window.location.href = '/'; setMobileMenuOpen(false); }}
                style={{ ...styles.navItem, ...styles.adminBtn, marginTop: 8 }}
              >
                <span>{'\u2630'}</span>
                <span>관리자 대시보드</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="consumer-main" style={styles.main}>
        {children}
      </main>
    </div>
  );
}

export default function ConsumerLayout({ children }) {
  return (
    <AuthProvider>
      <ConsumerShell>{children}</ConsumerShell>
    </AuthProvider>
  );
}

const styles = {
  sidebar: {
    width: 240, borderRight: '1px solid var(--card-border)', background: 'var(--card)',
    display: 'flex', flexDirection: 'column', position: 'fixed', top: 0, left: 0, bottom: 0,
    zIndex: 50,
  },
  logo: {
    padding: '20px 20px 12px', borderBottom: '1px solid var(--card-border)',
  },
  userBox: {
    padding: '16px 20px', borderBottom: '1px solid var(--card-border)',
  },
  navItem: {
    display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '10px 12px',
    borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: 13,
    transition: 'all 0.15s', marginBottom: 2, textAlign: 'left',
  },
  upgradeBtn: {
    marginTop: 12, background: 'linear-gradient(135deg, rgba(124,58,237,0.08), rgba(59,130,246,0.08))',
    color: 'var(--accent)', fontWeight: 600, border: '1px dashed var(--accent)',
  },
  adminBtn: {
    marginTop: 8, background: 'rgba(239,68,68,0.06)',
    color: 'var(--red)', fontWeight: 600, border: '1px solid rgba(239,68,68,0.2)',
  },
  usageBox: {
    padding: '12px 20px', borderTop: '1px solid var(--card-border)',
  },
  main: {
    flex: 1, marginLeft: 240, padding: 32, minHeight: '100vh',
  },
  mobileHeader: {
    display: 'none', position: 'fixed', top: 0, left: 0, right: 0, height: 56,
    background: 'var(--card)', borderBottom: '1px solid var(--card-border)',
    alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', zIndex: 40,
  },
  hamburger: {
    width: 32, height: 32, border: 'none', background: 'transparent',
    fontSize: 20, cursor: 'pointer', color: 'var(--text)',
  },
  mobileOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 45,
  },
  mobileMenu: {
    position: 'absolute', top: 0, left: 0, bottom: 0, width: 280,
    background: 'var(--card)', padding: 16, overflowY: 'auto',
  },
  // Responsive: hide sidebar on mobile via CSS would be better, but using inline styles
  // Mobile breakpoint handling is done via the mobileHeader display toggle
};
