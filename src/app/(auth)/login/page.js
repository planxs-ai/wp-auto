'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { signIn, signUp } from '@/lib/supabase';
import { Card, InputField, ActionButton } from '@/components/ui';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await signIn(email, password);
        router.push('/dashboard');
      } else {
        if (password !== passwordConfirm) {
          setError('비밀번호가 일치하지 않습니다');
          setLoading(false);
          return;
        }
        await signUp(email, password, displayName);
        router.push('/onboarding');
      }
    } catch (err) {
      const msg = err.message || '오류가 발생했습니다';
      const messages = {
        'Invalid login credentials': '이메일 또는 비밀번호가 올바르지 않습니다',
        'Email not confirmed': '이메일 인증이 완료되지 않았습니다. 메일함을 확인해주세요.',
        'User already registered': '이미 가입된 이메일입니다',
        'Password should be at least 6 characters': '비밀번호는 6자 이상이어야 합니다',
        'Signups not allowed for this instance': '회원가입이 비활성화되어 있습니다',
        'Email rate limit exceeded': '너무 많은 요청이 발생했습니다. 잠시 후 다시 시도해주세요.',
        'For security purposes, you can only request this once every 60 seconds': '보안을 위해 60초에 한 번만 요청할 수 있습니다. 잠시 후 다시 시도해주세요.',
      };
      // rate limit 관련 메시지 패턴 매칭
      if (!messages[msg] && (msg.toLowerCase().includes('rate') || msg.toLowerCase().includes('too many'))) {
        setError('요청이 너무 많습니다. 잠시 후 다시 시도해주세요.');
        return;
      }
      setError(messages[msg] || msg);
    } finally {
      setLoading(false);
    }
  };

  if (signupSuccess) {
    return (
      <div style={styles.container}>
        <Card style={styles.card}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x2709;&#xfe0f;</div>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>이메일을 확인해주세요</h2>
            <p style={{ color: 'var(--text-dim)', fontSize: 14, lineHeight: 1.6 }}>
              <strong>{email}</strong>으로 인증 메일을 보냈습니다.<br />
              메일의 링크를 클릭하면 가입이 완료됩니다.
            </p>
            <ActionButton onClick={() => { setMode('login'); setSignupSuccess(false); }} variant="secondary" style={{ marginTop: 24 }}>
              로그인으로 돌아가기
            </ActionButton>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', letterSpacing: -1 }}>AutoBlog</div>
        <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 4 }}>AI 기반 자동 블로그 수익화 플랫폼</div>
      </div>

      <Card style={styles.card}>
        <div style={styles.tabs}>
          <button
            onClick={() => { setMode('login'); setError(''); }}
            style={{ ...styles.tab, ...(mode === 'login' ? styles.tabActive : {}) }}
          >로그인</button>
          <button
            onClick={() => { setMode('signup'); setError(''); }}
            style={{ ...styles.tab, ...(mode === 'signup' ? styles.tabActive : {}) }}
          >회원가입</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {mode === 'signup' && (
            <div>
              <label style={styles.label}>이름</label>
              <InputField value={displayName} onChange={setDisplayName} placeholder="표시될 이름" />
            </div>
          )}
          <div>
            <label style={styles.label}>이메일</label>
            <InputField value={email} onChange={setEmail} placeholder="email@example.com" type="email" />
          </div>
          <div>
            <label style={styles.label}>비밀번호</label>
            <div style={{ position: 'relative' }}>
              <InputField value={password} onChange={setPassword} placeholder={mode === 'signup' ? '6자 이상' : '비밀번호'} type={showPassword ? 'text' : 'password'} />
              <button type="button" onClick={() => setShowPassword(!showPassword)} style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                border: 'none', background: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--text-dim)',
              }}>{showPassword ? '숨기기' : '보기'}</button>
            </div>
          </div>
          {mode === 'signup' && (
            <div>
              <label style={styles.label}>비밀번호 확인</label>
              <InputField value={passwordConfirm} onChange={setPasswordConfirm} placeholder="비밀번호 다시 입력" type={showPassword ? 'text' : 'password'} />
            </div>
          )}

          {error && (
            <div style={styles.error}>{error}</div>
          )}

          <ActionButton
            onClick={handleSubmit}
            disabled={loading || !email || !password}
            style={{ width: '100%', marginTop: 8, padding: '12px 20px' }}
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '무료로 시작하기'}
          </ActionButton>
        </form>

        {mode === 'signup' && (
          <div style={{ marginTop: 16, padding: 16, background: 'var(--accent-bg)', borderRadius: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
            <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--accent)' }}>&#x1f381; 7일 Premium 무료 체험</div>
            가입 즉시 Premium 기능을 7일간 무료로 체험할 수 있습니다. Golden Mode, 고급 분석, 맞춤 스케줄 등 모든 프리미엄 기능을 경험해보세요.
          </div>
        )}
      </Card>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    padding: 24, background: 'var(--bg)',
  },
  header: { textAlign: 'center', marginBottom: 32 },
  card: { width: '100%', maxWidth: 400, padding: 32 },
  tabs: {
    display: 'flex', marginBottom: 24, background: 'var(--input-bg)',
    borderRadius: 10, padding: 4,
  },
  tab: {
    flex: 1, padding: '10px 0', border: 'none', background: 'transparent',
    borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
    color: 'var(--text-dim)', transition: 'all 0.2s',
  },
  tabActive: {
    background: 'var(--card)', color: 'var(--text)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
  },
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 },
  error: {
    padding: '10px 14px', borderRadius: 10, fontSize: 12,
    background: 'var(--red-bg)', color: 'var(--red)', fontWeight: 500,
  },
};
