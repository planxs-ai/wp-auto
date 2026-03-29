'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/lib/auth';
import { CONSUMER_CATEGORIES } from '@/lib/plan-features';
import { Card, InputField, ActionButton, PillButton } from '@/components/ui';

const BLOG_STAGES = [
  { id: 'new', label: '\ucc98\uc74c \uc2dc\uc791', desc: '\ube14\ub85c\uadf8\ub97c \ub9c9 \uac1c\uc124\ud588\uac70\ub098 \uae00\uc774 \uac70\uc758 \uc5c6\uc5b4\uc694', icon: '\ud83c\udf31', color: '#3b82f6', stage: 1,
    result: 'AdSense \uc2b9\uc778\uc744 \ubaa9\ud45c\ub85c \uc21c\uc218 \uc815\ubcf4\uc131 \uae00\uc744 \ubc1c\ud589\ud569\ub2c8\ub2e4.' },
  { id: 'pre-adsense', label: 'AdSense \uc2b9\uc778 \uc804', desc: '\uae00\uc740 \uc788\uc9c0\ub9cc \uc544\uc9c1 AdSense \uc2b9\uc778\uc744 \ubabb \ubc1b\uc558\uc5b4\uc694', icon: '\ud83d\udcdd', color: '#f59e0b', stage: 1,
    result: 'AdSense \uc2b9\uc778 \uc870\uac74\uc744 \ub9de\ucd94\uba70 \ud488\uc9c8 \ub192\uc740 \uae00\uc744 \ubc1c\ud589\ud569\ub2c8\ub2e4.' },
  { id: 'post-adsense', label: 'AdSense \uc2b9\uc778 \uc644\ub8cc', desc: 'AdSense\ub294 \ub418\uc5c8\ub294\ub370 \uc218\uc775\uc774 \uc801\uc5b4\uc694', icon: '\u2705', color: '#10b981', stage: 2,
    result: 'AdSense + \ud150\ud551 CPA\ub85c \uc218\uc775\ud654\ub97c \uc2dc\uc791\ud569\ub2c8\ub2e4.' },
  { id: 'monetizing', label: '\uc218\uc775\ud654 \uc9c4\ud589 \uc911', desc: '\ucfe0\ud321/\ud150\ud551 \ub4f1 \uc218\uc775 \ucc44\ub110\uc744 \uc774\ubbf8 \uc0ac\uc6a9 \uc911\uc774\uc5d0\uc694', icon: '\ud83d\udcb0', color: '#7c3aed', stage: 3,
    result: '\ubaa8\ub4e0 \uc218\uc775 \ucc44\ub110\uc744 \uc790\ub3d9\ud654\ud558\uace0 \uadf9\ub300\ud654\ud569\ub2c8\ub2e4!' },
];

const SCHEDULE_PRESETS = [
  { id: 'daily2', label: '매일 2회', desc: '08:00, 18:00', times: ['08:00', '18:00'] },
  { id: 'daily4', label: '매일 4회', desc: '07/12/17/22시', times: ['07:00', '12:00', '17:00', '22:00'] },
  { id: 'weekday', label: '평일만', desc: '평일 08:00', times: ['08:00'] },
];

const TOTAL_STEPS = 5;

export default function OnboardingPage() {
  const router = useRouter();
  const { user, refreshProfile } = useAuth();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Step 1: Site connection
  const [wpUrl, setWpUrl] = useState('');
  const [wpUser, setWpUser] = useState('');
  const [wpPassword, setWpPassword] = useState('');
  const [siteTestResult, setSiteTestResult] = useState(null);

  // Step 2: Categories
  const [selectedCats, setSelectedCats] = useState([]);

  // Step 3: Schedule
  const [schedulePreset, setSchedulePreset] = useState('daily2');

  // Step 4: Monetization stage
  const [blogStage, setBlogStage] = useState(null);

  const toggleCat = (slug) => {
    setSelectedCats(prev =>
      prev.includes(slug) ? prev.filter(s => s !== slug) : [...prev, slug]
    );
  };

  const normalizeUrl = (raw) => {
    let u = raw.trim().replace(/\/$/, '');
    if (!/^https?:\/\//i.test(u)) u = 'https://' + u;
    return u;
  };

  const testSite = async () => {
    setSiteTestResult('testing');
    try {
      const url = normalizeUrl(wpUrl);
      setWpUrl(url);
      const res = await fetch(`${url}/wp-json/wp/v2/posts?per_page=1`, {
        headers: { Authorization: 'Basic ' + btoa(`${wpUser}:${wpPassword}`) },
      });
      setSiteTestResult(res.ok ? 'success' : 'failed');
    } catch {
      setSiteTestResult('failed');
    }
  };

  const handleComplete = async () => {
    if (!user) return;
    setSaving(true);

    try {
      // Find existing site by domain or create new
      const siteUrl = wpUrl.replace(/\/$/, '');
      const domain = new URL(siteUrl).hostname;
      let site;

      // Check if site already exists
      const { data: existing } = await supabase
        .from('sites').select('*').eq('domain', domain).single();

      if (existing) {
        // Link existing site to user
        await supabase.from('sites').update({ owner_id: user.id, wp_url: siteUrl }).eq('id', existing.id);
        site = existing;
      } else {
        // Create new site
        const newId = `site-${Date.now()}`;
        const { data: created } = await supabase
          .from('sites')
          .insert({ id: newId, name: domain, domain, wp_url: siteUrl, owner_id: user.id, status: 'active', config: {} })
          .select().single();
        site = created;
      }

      if (site) {
        // Link user to site
        await supabase.from('user_sites').upsert({ user_id: user.id, site_id: site.id, role: 'owner' });

        // Save dashboard config
        await supabase.from('dashboard_config').upsert({
          site_id: site.id,
          config: {
            niches: selectedCats,
            schedule_preset: schedulePreset,
            blog_stage: blogStage,
            monetization_stage: getStageFromBlogStage(blogStage),
          },
        });
      }

      // Mark onboarding complete
      await supabase.from('user_profiles').update({
        onboarding_completed: true,
        onboarding_step: TOTAL_STEPS,
        monetization_stage: getStageFromBlogStage(blogStage),
      }).eq('id', user.id);

      refreshProfile();
      router.push('/dashboard');
    } catch (err) {
      console.error('Onboarding error:', err);
    } finally {
      setSaving(false);
    }
  };

  const canNext = () => {
    if (step === 1) return wpUrl && wpUser && wpPassword;
    if (step === 2) return selectedCats.length >= 2;
    if (step === 4) return blogStage != null;
    return true;
  };

  function getStageFromBlogStage(id) {
    const found = BLOG_STAGES.find(s => s.id === id);
    return found ? found.stage : 1;
  }

  return (
    <div style={styles.container}>
      {/* Progress */}
      <div style={styles.progress}>
        {Array.from({ length: TOTAL_STEPS }, (_, i) => (
          <div key={i} style={{
            flex: 1, height: 4, borderRadius: 2,
            background: i + 1 <= step ? 'var(--accent)' : 'var(--border-light)',
            transition: 'background 0.3s',
          }} />
        ))}
      </div>
      <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-dim)', marginBottom: 24 }}>
        {step} / {TOTAL_STEPS}
      </div>

      {/* Step 1: Site Connection */}
      {step === 1 && (
        <Card style={styles.card}>
          <div style={styles.stepIcon}>{'\ud83c\udf10'}</div>
          <h2 style={styles.stepTitle}>사이트 연결</h2>
          <p style={styles.stepDesc}>WordPress 사이트를 연결하면 자동 발행이 시작됩니다.</p>

          <div style={styles.form}>
            <div>
              <label style={styles.label}>WordPress URL</label>
              <InputField value={wpUrl} onChange={setWpUrl} placeholder="https://your-blog.com" />
            </div>
            <div>
              <label style={styles.label}>사용자명</label>
              <InputField value={wpUser} onChange={setWpUser} placeholder="WordPress 사용자명" />
            </div>
            <div>
              <label style={styles.label}>앱 비밀번호</label>
              <InputField value={wpPassword} onChange={setWpPassword} placeholder="WordPress 앱 비밀번호" type="password" />
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                WordPress 관리자 &rarr; 사용자 &rarr; 프로필 &rarr; 앱 비밀번호에서 생성
              </div>
            </div>
            {siteTestResult === 'success' && (
              <div style={{ ...styles.testResult, background: 'var(--green-bg)', color: 'var(--green)' }}>
                {'\u2705'} 연결 성공! WordPress 사이트가 확인되었습니다.
              </div>
            )}
            {siteTestResult === 'failed' && (
              <div style={{ ...styles.testResult, background: 'var(--red-bg)', color: 'var(--red)' }}>
                {'\u274c'} 연결 실패. URL과 인증 정보를 확인해주세요.
              </div>
            )}
            {siteTestResult === 'testing' && (
              <div style={{ ...styles.testResult, background: 'var(--blue-bg)', color: 'var(--blue)' }}>
                연결 테스트 중...
              </div>
            )}
            <ActionButton onClick={testSite} variant="secondary"
              disabled={!wpUrl || !wpUser || !wpPassword}
              style={{ width: '100%' }}>
              연결 테스트
            </ActionButton>
          </div>
        </Card>
      )}

      {/* Step 2: Categories */}
      {step === 2 && (
        <Card style={styles.card}>
          <div style={styles.stepIcon}>{'\ud83d\udcc2'}</div>
          <h2 style={styles.stepTitle}>카테고리 선택</h2>
          <p style={styles.stepDesc}>어떤 주제의 글을 발행할까요? 최소 2개를 선택해주세요.</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {CONSUMER_CATEGORIES.filter(g => g.items.some(i => i.plans.includes('standard'))).map(group => (
              <div key={group.id}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>
                  {group.label}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {group.items.filter(i => i.plans.includes('standard')).map(item => (
                    <PillButton key={item.slug} selected={selectedCats.includes(item.slug)}
                      onClick={() => toggleCat(item.slug)}>
                      {item.icon} {item.ko}
                    </PillButton>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16, padding: 12, background: 'var(--accent-bg)', borderRadius: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
            {'\ud83d\udca1'} <strong>AI 도구 + 재테크</strong> 조합이 수익률이 가장 높습니다!
          </div>
        </Card>
      )}

      {/* Step 3: Schedule */}
      {step === 3 && (
        <Card style={styles.card}>
          <div style={styles.stepIcon}>{'\ud83d\udd53'}</div>
          <h2 style={styles.stepTitle}>발행 스케줄</h2>
          <p style={styles.stepDesc}>글을 자동으로 발행할 시간을 선택하세요. 언제든 변경할 수 있습니다.</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {SCHEDULE_PRESETS.map(preset => (
              <button key={preset.id} onClick={() => setSchedulePreset(preset.id)} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 16px', borderRadius: 12, border: schedulePreset === preset.id ? '2px solid var(--accent)' : '1px solid var(--border-light)',
                background: schedulePreset === preset.id ? 'var(--accent-bg)' : 'var(--card)',
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{preset.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>{preset.desc}</div>
                </div>
                <div style={{
                  width: 20, height: 20, borderRadius: 10,
                  border: schedulePreset === preset.id ? '6px solid var(--accent)' : '2px solid var(--border-light)',
                  transition: 'all 0.15s',
                }} />
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Step 4: Blog Stage */}
      {step === 4 && (
        <Card style={styles.card}>
          <div style={styles.stepIcon}>{'\ud83d\udcca'}</div>
          <h2 style={styles.stepTitle}>현재 어느 단계인가요?</h2>
          <p style={styles.stepDesc}>선택하시면 단계에 맞는 최적의 전략을 자동으로 설정합니다.</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {BLOG_STAGES.map(s => (
              <button key={s.id} onClick={() => setBlogStage(s.id)} style={{
                display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px',
                borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s', width: '100%', textAlign: 'left',
                border: blogStage === s.id ? `2px solid ${s.color}` : '1px solid var(--border-light)',
                background: blogStage === s.id ? `${s.color}10` : 'var(--card)',
              }}>
                <div style={{ fontSize: 28 }}>{s.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{s.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>{s.desc}</div>
                </div>
                <div style={{
                  width: 20, height: 20, borderRadius: 10,
                  border: blogStage === s.id ? `6px solid ${s.color}` : '2px solid var(--border-light)',
                  transition: 'all 0.15s',
                }} />
              </button>
            ))}
          </div>

          {blogStage && (
            <div style={{ marginTop: 16, padding: 12, background: 'var(--accent-bg)', borderRadius: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
              {'\u2705'} {BLOG_STAGES.find(s => s.id === blogStage)?.result}
            </div>
          )}
        </Card>
      )}

      {/* Step 5: Complete */}
      {step === 5 && (
        <Card style={{ ...styles.card, textAlign: 'center' }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>{'\ud83c\udf89'}</div>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>준비 완료!</h2>
          <p style={{ color: 'var(--text-dim)', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
            첫 글이 곧 자동 발행됩니다.<br />
            대시보드에서 진행 상황을 확인하세요.
          </p>

          <div style={{
            padding: 16, background: 'var(--accent-bg)', borderRadius: 12,
            marginBottom: 24, textAlign: 'left',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>
              설정 요약
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              {'\ud83c\udf10'} {wpUrl}<br />
              {'\ud83d\udcc2'} {selectedCats.length}개 카테고리 선택<br />
              {'\ud83d\udd53'} {SCHEDULE_PRESETS.find(p => p.id === schedulePreset)?.label}<br />
              {'\ud83d\udcca'} {BLOG_STAGES.find(s => s.id === blogStage)?.label || '미선택'}
            </div>
          </div>

          <div style={{
            padding: 12, background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)',
            borderRadius: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 500, marginBottom: 20,
          }}>
            {'\ud83c\udf81'} Premium 7일 무료 체험이 활성화되었습니다!
          </div>
        </Card>
      )}

      {/* Navigation Buttons */}
      <div style={styles.nav}>
        {step > 1 && (
          <ActionButton variant="ghost" onClick={() => setStep(s => s - 1)}>
            &larr; 이전
          </ActionButton>
        )}
        <div style={{ flex: 1 }} />
        {step < TOTAL_STEPS ? (
          <ActionButton onClick={() => setStep(s => s + 1)} disabled={!canNext()}>
            다음 &rarr;
          </ActionButton>
        ) : (
          <ActionButton onClick={handleComplete} disabled={saving}>
            {saving ? '저장 중...' : '대시보드로 이동'}
          </ActionButton>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: { maxWidth: 520, margin: '0 auto', padding: '40px 20px' },
  progress: { display: 'flex', gap: 6, marginBottom: 8 },
  card: { padding: 32 },
  stepIcon: { fontSize: 48, textAlign: 'center', marginBottom: 12 },
  stepTitle: { fontSize: 20, fontWeight: 700, textAlign: 'center', color: 'var(--text)', marginBottom: 6 },
  stepDesc: { fontSize: 13, color: 'var(--text-dim)', textAlign: 'center', marginBottom: 24, lineHeight: 1.6 },
  form: { display: 'flex', flexDirection: 'column', gap: 14 },
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 },
  testResult: { padding: '10px 14px', borderRadius: 10, fontSize: 12, fontWeight: 500 },
  optionBtn: {
    display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px',
    borderRadius: 12, border: '1px solid', cursor: 'pointer',
    width: '100%', textAlign: 'left', transition: 'all 0.15s',
  },
  checkbox: {
    width: 24, height: 24, borderRadius: 6, border: '2px solid var(--border-light)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 14, fontWeight: 700, color: 'var(--green)', marginLeft: 'auto',
  },
  nav: { display: 'flex', alignItems: 'center', marginTop: 24, gap: 12 },
};
