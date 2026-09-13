'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { signIn } from '@/lib/supabase';
import { Card, InputField, ActionButton } from '@/components/ui';

// 관리자 로그인 전용. 회원가입은 받지 않는다 (소비자 SaaS 기능 삭제, 2026-09-13 결정)
const ERROR_MESSAGES = {
  'Invalid login credentials': '이메일 또는 비밀번호가 올바르지 않습니다',
  'Email not confirmed': '이메일 인증이 끝나지 않은 계정입니다',
  'Email rate limit exceeded': '너무 많은 요청이 발생했습니다. 잠시 후 다시 시도해주세요.',
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
      router.push('/');
    } catch (err) {
      const msg = err.message || '오류가 발생했습니다';
      if (!ERROR_MESSAGES[msg] && (msg.toLowerCase().includes('rate') || msg.toLowerCase().includes('too many'))) {
        setError('요청이 너무 많습니다. 잠시 후 다시 시도해주세요.');
        return;
      }
      setError(ERROR_MESSAGES[msg] || msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', letterSpacing: -1 }}>AutoBlog</div>
        <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 4 }}>관리자 대시보드</div>
      </div>

      <Card style={styles.card}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={styles.label}>이메일</label>
            <InputField value={email} onChange={setEmail} placeholder="email@example.com" type="email" />
          </div>
          <div>
            <label style={styles.label}>비밀번호</label>
            <div style={{ position: 'relative' }}>
              <InputField value={password} onChange={setPassword} placeholder="비밀번호" type={showPassword ? 'text' : 'password'} />
              <button type="button" onClick={() => setShowPassword(!showPassword)} style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                border: 'none', background: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--text-dim)',
              }}>{showPassword ? '숨기기' : '보기'}</button>
            </div>
          </div>

          {error && <div style={styles.error}>{error}</div>}

          <ActionButton
            onClick={handleSubmit}
            disabled={loading || !email || !password}
            style={{ width: '100%', marginTop: 8, padding: '12px 20px' }}
          >
            {loading ? '로그인 중...' : '로그인'}
          </ActionButton>
        </form>
      </Card>

      <div style={{ marginTop: 20, textAlign: 'center', fontSize: 12, color: 'var(--text-dim)' }}>
        관리자 계정만 로그인할 수 있습니다. 회원가입은 받지 않습니다.
      </div>
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
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 },
  error: {
    padding: '10px 14px', borderRadius: 10, fontSize: 12,
    background: 'var(--red-bg)', color: 'var(--red)', fontWeight: 500,
  },
};
