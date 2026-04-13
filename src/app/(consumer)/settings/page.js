'use client';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, signOut } from '@/lib/supabase';
import { useAuth, useCurrentUser, useUserSites, usePlanFeatures } from '@/lib/auth';
import { CONSUMER_CATEGORIES } from '@/lib/plan-features';
import { Card, SectionTitle, Badge, InputField, ActionButton, PillButton } from '@/components/ui';
import { isCentral } from '@/lib/instance';

// ── Constants ──

const SETUP_SEQUENCE = [
  { id: 'wp-init', label: '블로그 초기화', icon: '\u2699', direct: true },
  { id: 'publish', label: '첫 글 발행', icon: '\uD83D\uDCDD' },
];

const DEFAULT_TIMES = ['07:00', '12:00', '17:00', '22:00', '06:00'];

const STEPS = [
  { id: 1, label: '사이트 연결', icon: '\uD83C\uDF10' },
  { id: 2, label: 'GitHub 연동', icon: '\uD83D\uDD17' },
  { id: 3, label: '블로그 설정', icon: '\u2699' },
];

// ── Page ──

export default function SettingsPage() {
  const router = useRouter();
  const { user, refreshProfile } = useAuth();
  const { displayName, planId, isAdmin } = useCurrentUser();
  const { plan, isPremiumOrAbove } = usePlanFeatures();
  const { sites, activeSite, setActiveSite, refreshSites, loading: sitesLoading } = useUserSites();
  const site = activeSite;

  // Config
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);
  const [nameEdit, setNameEdit] = useState(displayName);
  const [selectedCats, setSelectedCats] = useState([]);
  const [nicheEditing, setNicheEditing] = useState(true);

  // Schedule
  const [dailyCount, setDailyCount] = useState(2);
  const [scheduleTimes, setScheduleTimes] = useState(['07:00', '18:00']);

  // First post count
  const [firstPostCount, setFirstPostCount] = useState(3);

  // Blog info
  const [blogOwner, setBlogOwner] = useState('');
  const [blogDesc, setBlogDesc] = useState('');
  const [contactEmail, setContactEmail] = useState('');

  // Site registration
  const [siteMode, setSiteMode] = useState('view');
  const [wpUrl, setWpUrl] = useState('');
  const [wpUser, setWpUser] = useState('');
  const [wpPassword, setWpPassword] = useState('');
  const [wpLoginPass, setWpLoginPass] = useState('');
  const [siteTestResult, setSiteTestResult] = useState(null);
  const [savingSite, setSavingSite] = useState(false);

  // Setup actions
  const [setupLog, setSetupLog] = useState([]);
  const [setupRunning, setSetupRunning] = useState({});

  // One-click launch
  const [launchRunning, setLaunchRunning] = useState(false);
  const [launchStep, setLaunchStep] = useState(-1); // current index in SETUP_SEQUENCE
  const [launchResults, setLaunchResults] = useState([]); // { id, status, error? }

  // Monetization
  const [monetizationStage, setMonetizationStage] = useState(1);
  const [coupangProducts, setCoupangProducts] = useState([]); // [{name, category, url}]
  const [tenpingCampaigns, setTenpingCampaigns] = useState([]); // [{name, category, url, cpa}]
  const [newCoupang, setNewCoupang] = useState({ name: '', category: '', url: '' });
  const [newTenping, setNewTenping] = useState({ name: '', category: '', url: '', cpa: '' });

  // Site registration error
  const [siteError, setSiteError] = useState('');

  // API keys (Supabase에 저장)
  const [ghSecrets, setGhSecrets] = useState({
    DEEPSEEK_API_KEY: '', GROK_API_KEY: '', GEMINI_API_KEY: '',
    CLAUDE_API_KEY: '', PEXELS_API_KEY: '', PIXABAY_API_KEY: '',
    UNSPLASH_ACCESS_KEY: '',
  });
  const [ghSecretsResult, setGhSecretsResult] = useState(null);
  const [ghSecretsSaving, setGhSecretsSaving] = useState(false);
  const [ghSecretsComplete, setGhSecretsComplete] = useState(false);
  const [copiedField, setCopiedField] = useState('');

  // System health
  const [systemHealth, setSystemHealth] = useState(null);

  useEffect(() => {
    fetch('/api/health').then(r => r.json()).then(setSystemHealth).catch(() => null);
  }, []);

  // Load config + setup log
  useEffect(() => {
    if (!site?.id) return;
    supabase.from('dashboard_config').select('config').eq('site_id', site.id).single()
      .then(({ data }) => {
        if (data?.config) {
          setConfig(data.config);
          setSelectedCats(data.config.niches || []);
          if ((data.config.niches || []).length >= 2) setNicheEditing(false);
          setSetupLog(data.config.setup_log || []);
          setDailyCount(data.config.daily_count || 2);
          setScheduleTimes(data.config.schedule_times || DEFAULT_TIMES.slice(0, data.config.daily_count || 2));
          setFirstPostCount(data.config.first_post_count || 3);
          setBlogOwner(data.config.blog_owner || '');
          setBlogDesc(data.config.blog_desc || '');
          setContactEmail(data.config.contact_email || '');
          setMonetizationStage(data.config.monetization_stage || 1);
          setCoupangProducts(data.config.coupang_manual_products || []);
          setTenpingCampaigns(data.config.tenping_campaigns || []);
        } else {
          setConfig(null);
          setSelectedCats([]);
          setSetupLog([]);
          setDailyCount(2);
          setScheduleTimes(['07:00', '18:00']);
          setFirstPostCount(3);
          setBlogOwner('');
          setBlogDesc('');
          setContactEmail('');
        }
        setSetupRunning({});
        setLaunchRunning(false);
        setLaunchStep(-1);
        setLaunchResults([]);
      });
  }, [site?.id]);

  useEffect(() => {
    if (sitesLoading) return;
    if (site) {
      setSiteMode('view');
    } else if (sites.length === 0) {
      setSiteMode('register');
    }
  }, [site, sites.length, sitesLoading]);

  // API 키 로드 (sites.config.api_keys)
  useEffect(() => {
    if (site?.config?.api_keys) {
      const keys = site.config.api_keys;
      setGhSecrets(prev => ({
        ...prev,
        ...Object.fromEntries(Object.entries(keys).map(([k, v]) => [k, v ? '********' : '']))
      }));
      if (keys.DEEPSEEK_API_KEY || keys.GROK_API_KEY || keys.GEMINI_API_KEY) {
        setGhSecretsComplete(true);
      }
    }
  }, [site?.id]);

  // ── Step completion ──
  const siteConnected = !!site;
  const completedSetupIds = useMemo(
    () => setupLog.filter(l => l.status === 'success').map(l => l.action),
    [setupLog]
  );
  const REQUIRED_SETUP_IDS = ['wp-init', 'publish'];
  const wpSetupDone = REQUIRED_SETUP_IDS.every(id => completedSetupIds.includes(id));
  const scheduleConfigured = dailyCount >= 1 && scheduleTimes.length >= dailyCount;
  const step3Complete = wpSetupDone && scheduleConfigured;

  const currentStepComplete = (stepId) => {
    if (stepId === 1) return siteConnected;
    if (stepId === 2) return ghSecretsComplete || (isCentral() && isAdmin);
    if (stepId === 3) return step3Complete;
    return false;
  };

  // ── API 키 저장 (Supabase sites.config.api_keys) ──
  const registerGhSecrets = async () => {
    if (!site?.id) return;
    setGhSecretsSaving(true);
    setGhSecretsResult(null);
    try {
      // 실제 값만 필터 (********는 기존 값 유지)
      const newKeys = Object.fromEntries(
        Object.entries(ghSecrets).filter(([, v]) => v.trim() && v !== '********')
      );
      const mergedKeys = { ...(site.config?.api_keys || {}), ...newKeys };

      await supabase.from('sites').update({
        config: { ...site.config, api_keys: mergedKeys },
      }).eq('id', site.id);

      setGhSecretsResult({
        success: true,
        message: `API 키 ${Object.keys(newKeys).length}개가 저장되었습니다.`,
      });
      setGhSecretsComplete(true);
    } catch (err) {
      setGhSecretsResult({ error: err.message });
    }
    setGhSecretsSaving(false);
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(''), 2000);
  };

  // ── Site actions ──

  const normalizeUrl = (raw) => {
    let u = raw.trim().replace(/\/$/, '');
    if (!/^https?:\/\//i.test(u)) u = 'https://' + u;
    return u;
  };

  const testConnection = async () => {
    setSiteTestResult('testing');
    try {
      const url = normalizeUrl(wpUrl);
      const res = await fetch(`${url}/wp-json/wp/v2/posts?per_page=1`, {
        headers: { Authorization: 'Basic ' + btoa(`${wpUser}:${wpPassword}`) },
      });
      setSiteTestResult(res.ok ? 'success' : 'failed');
    } catch {
      setSiteTestResult('failed');
    }
  };

  const registerSite = async () => {
    if (!user) return;
    setSavingSite(true);
    try {
      const siteUrl = normalizeUrl(wpUrl);
      const domain = new URL(siteUrl).hostname;
      const { data: existing } = await supabase
        .from('sites').select('*').eq('domain', domain).single();

      let newSite;
      if (existing) {
        await supabase.from('sites').update({
          owner_id: user.id, wp_url: siteUrl,
          config: { wp_username: wpUser, wp_app_password: wpPassword, wp_login_password: wpLoginPass || wpPassword },
        }).eq('id', existing.id);
        newSite = existing;
      } else {
        const newId = `site-${Date.now()}`;
        const { data: created } = await supabase
          .from('sites')
          .insert({
            id: newId, name: domain, domain, wp_url: siteUrl,
            owner_id: user.id, status: 'active',
            config: { wp_username: wpUser, wp_app_password: wpPassword, wp_login_password: wpLoginPass || wpPassword },
          })
          .select().single();
        newSite = created;
      }

      if (newSite) {
        await supabase.from('user_sites').upsert({
          user_id: user.id, site_id: newSite.id, role: 'owner',
        });
        setActiveSite(newSite.id);
        await supabase.from('user_profiles').update({
          onboarding_completed: true, onboarding_step: 5,
        }).eq('id', user.id);
        refreshProfile();
      }

      await refreshSites();
      setSiteMode('view');
      resetSiteForm();
      setSiteError('');
    } catch (err) {
      setSiteError(err?.message || '사이트 등록에 실패했습니다. 다시 시도해주세요.');
    }
    setSavingSite(false);
  };

  const updateSite = async () => {
    if (!user || !site?.id) return;
    setSavingSite(true);
    try {
      const siteUrl = normalizeUrl(wpUrl);
      const domain = new URL(siteUrl).hostname;
      await supabase.from('sites').update({
        wp_url: siteUrl, domain, name: domain,
        config: { wp_username: wpUser, wp_app_password: wpPassword, wp_login_password: wpLoginPass || wpPassword },
      }).eq('id', site.id);
      await refreshSites();
      setSiteMode('view');
      resetSiteForm();
      setSiteError('');
    } catch (err) {
      setSiteError(err?.message || '사이트 정보 변경에 실패했습니다.');
    }
    setSavingSite(false);
  };

  const startEdit = () => {
    setSiteMode('edit');
    setWpUrl(site?.wp_url || '');
    setWpUser(site?.config?.wp_username || '');
    setWpPassword(site?.config?.wp_app_password || '');
    setWpLoginPass(site?.config?.wp_login_password || '');
    setSiteTestResult(null);
  };

  const startRegister = () => {
    setSiteMode('register');
    resetSiteForm();
  };

  const resetSiteForm = () => {
    setWpUrl('');
    setWpUser('');
    setWpPassword('');
    setWpLoginPass('');
    setSiteTestResult(null);
  };

  // ── Single setup action ──

  const runSingleAction = useCallback(async (actionDef) => {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token || '';

    // wp-init: 새 직접 API로 블로그 초기화 (메뉴+페이지+카테고리+타이틀+Sample삭제)
    if (actionDef.id === 'wp-init') {
      const res = await fetch('/api/wp-setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          siteId: site?.id,
          actions: ['set-title', 'delete-sample', 'setup-pages', 'setup-categories', 'setup-menu'],
          blogName: blogOwner ? `${blogOwner} 블로그` : undefined,
          blogOwner,
          blogDesc,
          contactEmail,
          niches: selectedCats,
        }),
      });
      return res.json();
    }

    // publish: 기존 GitHub Actions 방식 유지
    let actionInputs = actionDef.inputs || {};
    if (actionDef.id === 'publish') {
      actionInputs = { count: String(firstPostCount) };
    }

    const res = await fetch('/api/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ action: actionDef.id, siteId: site?.id, inputs: actionInputs }),
    });
    return res.json();
  }, [site?.id, firstPostCount, blogOwner, blogDesc, contactEmail, selectedCats]);

  const persistSetupLog = useCallback(async (log) => {
    if (!site?.id) return;
    const merged = { ...(config || {}), setup_log: log };
    setConfig(merged);
    await supabase.from('dashboard_config').upsert({ site_id: site.id, config: merged });
  }, [site?.id, config]);

  // ── One-click launch: sequential execution ──

  const handleLaunch = async () => {
    if (launchRunning) return;
    setLaunchRunning(true);
    setLaunchResults([]);

    // Save settings first
    await saveSettingsInner();

    // Save blog info for setup-pages
    if (site?.id) {
      await supabase.from('dashboard_config').upsert({
        site_id: site.id,
        config: {
          ...(config || {}), blog_owner: blogOwner, blog_desc: blogDesc, contact_email: contactEmail,
          niches: selectedCats, daily_count: dailyCount,
          schedule_times: scheduleTimes.slice(0, dailyCount), first_post_count: firstPostCount,
        },
      });
    }

    const results = [];
    let allLog = [...setupLog];

    for (let i = 0; i < SETUP_SEQUENCE.length; i++) {
      const action = SETUP_SEQUENCE[i];
      setLaunchStep(i);

      try {
        const data = await runSingleAction(action);
        const success = !!data.success;
        const logEntry = {
          action: action.id, label: action.label,
          completed_at: new Date().toISOString(),
          status: success ? 'success' : 'failed',
          error: success ? undefined : (data.error || ''),
        };

        results.push({ id: action.id, status: success ? 'success' : 'failed', error: logEntry.error });
        setLaunchResults([...results]);

        allLog = [...allLog.filter(l => l.action !== action.id), logEntry];
        setSetupLog(allLog);
        await persistSetupLog(allLog);

        if (!success) {
          break; // stop on failure
        }
      } catch {
        results.push({ id: action.id, status: 'failed', error: '네트워크 오류' });
        setLaunchResults([...results]);
        break;
      }
    }

    setLaunchStep(-1);
    setLaunchRunning(false);
  };

  // ── Individual action run ──

  const runSetupAction = async (action) => {
    setSetupRunning(prev => ({ ...prev, [action.id]: true }));
    try {
      if (action.id === 'wp-init' && site?.id) {
        await supabase.from('dashboard_config').upsert({
          site_id: site.id,
          config: { ...(config || {}), blog_owner: blogOwner, blog_desc: blogDesc, contact_email: contactEmail },
        });
      }
      const data = await runSingleAction(action);
      const logEntry = {
        action: action.id, label: action.label,
        completed_at: new Date().toISOString(),
        status: data.success ? 'success' : 'failed',
        error: data.success ? undefined : ((data.error || '실패') + (data.guide ? ` — ${data.guide}` : '')),
      };
      const updatedLog = [...setupLog.filter(l => l.action !== action.id), logEntry];
      setSetupLog(updatedLog);
      await persistSetupLog(updatedLog);
    } catch {
      const logEntry = {
        action: action.id, label: action.label,
        completed_at: new Date().toISOString(), status: 'failed', error: '네트워크 오류',
      };
      const updatedLog = [...setupLog.filter(l => l.action !== action.id), logEntry];
      setSetupLog(updatedLog);
      await persistSetupLog(updatedLog);
    }
    setSetupRunning(prev => ({ ...prev, [action.id]: false }));
  };

  // ── Settings ──

  const toggleCat = (slug) => {
    setSelectedCats(prev =>
      prev.includes(slug) ? prev.filter(s => s !== slug) : [...prev, slug]
    );
  };

  const saveSettingsInner = async () => {
    if (!user || !site?.id) return;
    await Promise.all([
      supabase.from('user_profiles').update({ display_name: nameEdit }).eq('id', user.id),
      supabase.from('dashboard_config').upsert({
        site_id: site.id,
        config: {
          ...config, niches: selectedCats, daily_count: dailyCount,
          schedule_times: scheduleTimes.slice(0, dailyCount),
          first_post_count: firstPostCount,
          blog_owner: blogOwner, blog_desc: blogDesc, contact_email: contactEmail,
          monetization_stage: monetizationStage,
          coupang_manual_products: coupangProducts,
          tenping_campaigns: tenpingCampaigns,
        },
      }),
    ]);
    refreshProfile();
  };

  // 스케줄 GitHub 동기화 상태
  const [scheduleSync, setScheduleSync] = useState(null); // null | 'syncing' | 'success' | 'failed'
  const [scheduleSyncError, setScheduleSyncError] = useState('');

  const syncScheduleToGitHub = async () => {
    if (!site?.id || dailyCount < 1 || scheduleTimes.length < 1) return;
    setScheduleSync('syncing');
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const res = await fetch('/api/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token || ''}`,
        },
        body: JSON.stringify({
          siteId: site.id,
          scheduleTimes: scheduleTimes.slice(0, dailyCount),
          dailyCount,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setScheduleSync('success');
        setScheduleSyncError('');
      } else {
        setScheduleSync('failed');
        setScheduleSyncError(data.error + (data.guide ? ` — ${data.guide}` : ''));
      }
    } catch {
      setScheduleSync('failed');
      setScheduleSyncError('네트워크 오류');
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await saveSettingsInner();
      await syncScheduleToGitHub();
    } catch { /* silent */ }
    setSaving(false);
  };

  const handleSignOut = async () => {
    await signOut();
    window.location.href = '/login';
  };

  // ── Render ──

  const formReady = wpUrl && wpUser && wpPassword;
  const nicheReady = selectedCats.length >= 2;
  const canLaunch = isAdmin || !isCentral() || ghSecretsComplete; // admin, self-hosted, or fork owner
  const launchReady = canLaunch && nicheReady && blogOwner && contactEmail;

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800 }}>설정</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Badge text={plan.name} color={planId === 'premium' ? 'purple' : planId === 'mama' ? 'yellow' : 'blue'} />
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{user?.email}</span>
        </div>
      </div>

      {/* ── Step Progress ── */}
      <Card style={{ marginBottom: 24, padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          {STEPS.map((step, i) => {
            const done = currentStepComplete(step.id);
            const active = !done && (step.id === 1 || currentStepComplete(step.id - 1));
            return (
              <div key={step.id} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 16,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, fontWeight: 700,
                    background: done ? 'var(--green)' : active ? 'var(--accent)' : 'var(--border-light)',
                    color: done || active ? '#fff' : 'var(--text-dim)',
                    transition: 'all 0.3s',
                  }}>
                    {done ? '\u2713' : step.id}
                  </div>
                  <div>
                    <div style={{
                      fontSize: 12, fontWeight: 600,
                      color: done ? 'var(--green)' : active ? 'var(--accent)' : 'var(--text-dim)',
                    }}>
                      {step.label}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                      {done ? '완료' : active ? '진행 중' : '대기'}
                    </div>
                  </div>
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{
                    flex: 1, height: 2, margin: '0 12px',
                    background: done ? 'var(--green)' : 'var(--border-light)',
                    transition: 'background 0.3s',
                  }} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ═══ STEP 1: Site Connection ═══ */}
      {site && siteMode === 'view' ? (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 16px', borderRadius: 10,
            background: 'var(--green-bg)', border: '1px solid rgba(16,185,129,0.15)',
            opacity: 0.85,
          }}>
            <StepBadge num={1} done={true} />
            <div style={{ fontSize: 12, color: 'var(--text-dim)', flexShrink: 0 }}>STEP 1</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {site.domain || site.name}
            </div>
            <span style={{ fontSize: 11, color: 'var(--green)', flexShrink: 0 }}>
              {'\u2705'} 연결됨
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6, padding: '0 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>Site ID:</span>
              <code style={{ fontSize: 11, color: 'var(--accent)', background: 'var(--accent-bg)', padding: '2px 8px', borderRadius: 6, fontFamily: 'monospace' }}>
                {site.id}
              </code>
              <button
                onClick={() => { navigator.clipboard.writeText(site.id); }}
                style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--text-dim)', padding: 0 }}
                title="복사"
              >
                {'\uD83D\uDCCB'}
              </button>
            </div>
            <button onClick={startEdit}
              style={{ border: 'none', background: 'none', color: 'var(--text-dim)', fontSize: 10, cursor: 'pointer', textDecoration: 'underline' }}>
              사이트 정보 변경
            </button>
          </div>
        </div>
      ) : (
      <Card style={{ marginBottom: 20 }}>
        <SectionTitle>STEP 1 &mdash; 사이트 연결</SectionTitle>

        {(siteMode === 'register' || siteMode === 'edit') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {siteMode === 'register' && (
              <div style={{ padding: 12, background: 'var(--accent-bg)', borderRadius: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>
                {'\uD83C\uDF10'} WordPress 사이트를 연결합니다. 앱 비밀번호가 필요합니다.
              </div>
            )}
            <div>
              <label style={st.label}>WordPress URL</label>
              <InputField value={wpUrl} onChange={setWpUrl} placeholder="https://your-blog.com" />
            </div>
            <div>
              <label style={st.label}>사용자명</label>
              <InputField value={wpUser} onChange={setWpUser} placeholder="WordPress 사용자명" />
            </div>
            <div>
              <label style={st.label}>앱 비밀번호 (API용)</label>
              <InputField value={wpPassword} onChange={setWpPassword} placeholder="WordPress 앱 비밀번호" type="password" />
              <AppPasswordGuide />
            </div>
            <div>
              <label style={st.label}>관리자 로그인 비밀번호 (CSS 자동 적용용, 선택)</label>
              <InputField value={wpLoginPass} onChange={setWpLoginPass} placeholder="wp-admin 로그인 비밀번호" type="password" />
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                CSS 디자인 자동 적용에 필요합니다. 없으면 앱 비밀번호로 시도합니다.
              </div>
            </div>

            {siteTestResult === 'success' && (
              <div style={{ ...st.testBanner, background: 'var(--green-bg)', color: 'var(--green)' }}>
                {'\u2705'} 연결 성공! WordPress API가 정상 응답합니다.
              </div>
            )}
            {siteTestResult === 'failed' && (
              <div style={{ ...st.testBanner, background: 'var(--red-bg)', color: 'var(--red)' }}>
                {'\u274C'} 연결 실패. URL, 사용자명, 앱 비밀번호를 확인해주세요.
              </div>
            )}
            {siteTestResult === 'testing' && (
              <div style={{ ...st.testBanner, background: 'var(--blue-bg)', color: 'var(--blue)' }}>
                연결 테스트 중...
              </div>
            )}

            {siteError && (
              <div style={{ ...st.testBanner, background: 'var(--red-bg)', color: 'var(--red)' }}>
                {'\u274C'} {siteError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <ActionButton variant="secondary" onClick={testConnection} disabled={!formReady} style={{ flex: 1 }}>
                연결 테스트
              </ActionButton>
              <ActionButton
                onClick={siteMode === 'register' ? registerSite : updateSite}
                disabled={!formReady || savingSite}
                style={{ flex: 1 }}>
                {savingSite ? '저장 중...' : siteMode === 'register' ? '사이트 등록' : '변경 저장'}
              </ActionButton>
              {(site || sites.length > 0) && (
                <ActionButton variant="ghost" onClick={() => { setSiteMode('view'); resetSiteForm(); }}
                  style={{ padding: '8px 14px' }}>
                  취소
                </ActionButton>
              )}
            </div>
          </div>
        )}

        {!site && siteMode === 'view' && (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-dim)' }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>{'\uD83C\uDF10'}</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: 'var(--text)' }}>
              사이트를 연결해주세요
            </div>
            <div style={{ fontSize: 12, marginBottom: 16 }}>
              WordPress 사이트를 연결하면 자동 발행이 시작됩니다.
            </div>
            <ActionButton onClick={startRegister}>사이트 등록</ActionButton>
          </div>
        )}
      </Card>
      )}

      {/* ═══ STEP 2: GitHub 연동 + API 키 ═══ */}
      {(isCentral() && isAdmin) ? null : (
        siteConnected && ghSecretsComplete ? (
          <div style={{ marginBottom: 20 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px', borderRadius: 10,
              background: 'var(--green-bg)', border: '1px solid rgba(16,185,129,0.15)',
              opacity: 0.85,
            }}>
              <StepBadge num={2} done={true} />
              <div style={{ fontSize: 12, color: 'var(--text-dim)', flexShrink: 0 }}>STEP 2</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1 }}>
                API 키 등록 완료
              </div>
              <span style={{ fontSize: 11, color: 'var(--green)', flexShrink: 0 }}>
                {'\u2705'} 완료
              </span>
            </div>
            <button
              onClick={() => setGhSecretsComplete(false)}
              style={{ border: 'none', background: 'none', color: 'var(--text-dim)', fontSize: 10, cursor: 'pointer', textDecoration: 'underline', marginTop: 4, marginLeft: 16 }}
            >
              API 키 변경
            </button>
          </div>
        ) : (
        <Card style={{ marginBottom: 20, opacity: siteConnected ? 1 : 0.5, pointerEvents: siteConnected ? 'auto' : 'none' }}>
          <SectionTitle>STEP 2 &mdash; {isCentral() ? 'Fork + API 키' : 'API 키 등록'}</SectionTitle>
          {!siteConnected && (
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 12 }}>
              {'\uD83D\uDD12'} STEP 1에서 사이트를 먼저 연결해주세요.
            </div>
          )}

          {siteConnected && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Central 모드: Fork 안내 + 시크릿 복사 */}
              {isCentral() && (
                <>
                  {/* Fork 안내 */}
                  <a
                    href="https://github.com/planxs-ai/wp-auto/fork"
                    target="_blank" rel="noopener"
                    style={{
                      display: 'block', textAlign: 'center', padding: '10px 16px',
                      background: 'var(--bg-secondary)', borderRadius: 10,
                      color: 'var(--accent)', fontWeight: 600, fontSize: 13,
                      textDecoration: 'none', border: '1px solid var(--border-light)',
                    }}
                  >
                    1. GitHub에서 Fork하기 &rarr;
                  </a>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: -8 }}>
                    Fork 후 Actions 탭에서 &quot;I understand my workflows, go ahead and enable them&quot; 클릭
                  </div>

                  {/* GitHub Secrets 복사 */}
                  <div style={{ padding: 12, background: 'var(--accent-bg)', borderRadius: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>
                    2. Fork한 저장소 &rarr; Settings &rarr; Secrets and variables &rarr; Actions에 아래 3개를 추가하세요.
                  </div>

                  {[
                    { name: 'SUPABASE_URL', value: process.env.NEXT_PUBLIC_SUPABASE_URL || '' },
                    { name: 'SUPABASE_KEY', value: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '' },
                    { name: 'SITE_ID', value: site?.id || '' },
                  ].map(({ name, value }) => (
                    <div key={name} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8,
                    }}>
                      <code style={{ fontSize: 11, fontWeight: 700, color: 'var(--text)', minWidth: 110 }}>{name}</code>
                      <code style={{
                        flex: 1, fontSize: 10, color: 'var(--text-dim)', fontFamily: 'monospace',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {value.length > 30 ? value.slice(0, 15) + '...' + value.slice(-10) : value}
                      </code>
                      <button
                        onClick={() => copyToClipboard(value, name)}
                        style={{
                          border: 'none', borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
                          fontSize: 11, fontWeight: 600, flexShrink: 0,
                          background: copiedField === name ? 'var(--green)' : 'var(--accent)',
                          color: '#fff',
                        }}
                      >
                        {copiedField === name ? '복사됨' : '복사'}
                      </button>
                    </div>
                  ))}

                  <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 14, marginTop: 4 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>
                      3. AI API 키 입력
                    </div>
                  </div>
                </>
              )}

              {!isCentral() && (
                <div style={{ padding: 12, background: 'var(--accent-bg)', borderRadius: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 500 }}>
                  {'\uD83D\uDD11'} AI API 키를 입력하면 자동으로 설정됩니다.
                </div>
              )}

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, display: 'block', color: 'var(--text)' }}>
                  DeepSeek API Key <span style={{ color: 'var(--red)' }}>*필수</span>
                </label>
                <InputField
                  value={ghSecrets.DEEPSEEK_API_KEY}
                  onChange={(v) => setGhSecrets(prev => ({ ...prev, DEEPSEEK_API_KEY: v }))}
                  placeholder="sk-..." type="password"
                />
              </div>

              <details style={{ cursor: 'pointer' }}>
                <summary style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 500 }}>
                  선택 API Keys (Grok, Gemini, Claude, 이미지)
                </summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                  {[
                    { key: 'GROK_API_KEY', label: 'Grok API Key' },
                    { key: 'GEMINI_API_KEY', label: 'Gemini API Key' },
                    { key: 'CLAUDE_API_KEY', label: 'Claude API Key' },
                    { key: 'PEXELS_API_KEY', label: 'Pexels API Key' },
                    { key: 'PIXABAY_API_KEY', label: 'Pixabay API Key' },
                    { key: 'UNSPLASH_ACCESS_KEY', label: 'Unsplash Access Key' },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <label style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2, display: 'block' }}>{label}</label>
                      <InputField
                        value={ghSecrets[key]}
                        onChange={(v) => setGhSecrets(prev => ({ ...prev, [key]: v }))}
                        placeholder={label} type="password"
                      />
                    </div>
                  ))}
                </div>
              </details>

              {ghSecretsResult && (
                <div style={{
                  padding: 12, borderRadius: 10, fontSize: 12,
                  background: ghSecretsResult.success ? 'var(--green-bg)' : 'var(--red-bg)',
                  color: ghSecretsResult.success ? 'var(--green)' : 'var(--red)',
                }}>
                  {ghSecretsResult.success
                    ? `${'\u2705'} ${ghSecretsResult.message}`
                    : `${'\u274C'} ${ghSecretsResult.error || ghSecretsResult.message}`
                  }
                </div>
              )}

              <ActionButton
                onClick={registerGhSecrets}
                disabled={ghSecretsSaving || !ghSecrets.DEEPSEEK_API_KEY.trim() || ghSecrets.DEEPSEEK_API_KEY === '********'}
              >
                {ghSecretsSaving ? '저장 중...' : 'API 키 저장'}
              </ActionButton>
            </div>
          )}
        </Card>
        )
      )}

      {/* ═══ STEP 3: Blog Setup + Launch ═══ */}
      <Card style={{ marginBottom: 20, opacity: siteConnected ? 1 : 0.5, pointerEvents: siteConnected ? 'auto' : 'none' }}>
        <SectionTitle>STEP 3 &mdash; 블로그 설정</SectionTitle>
        {!siteConnected && (
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 12 }}>
            {'\uD83D\uDD12'} STEP 1에서 사이트를 먼저 연결해주세요.
          </div>
        )}

        {/* 2-A: Niche Selection */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <StepBadge num={'A'} done={nicheReady} />
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flex: 1 }}>
              니치 선택 (블로그 주제)
            </div>
            {nicheReady && !nicheEditing && (
              <button onClick={() => setNicheEditing(true)} style={{
                padding: '6px 14px', borderRadius: 8, border: '1px solid var(--card-border)', background: 'var(--card)',
                color: 'var(--accent, #6366f1)', fontSize: 11, fontWeight: 700, cursor: 'pointer',
              }}>니치 변경</button>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingLeft: 36 }}>
            {/* 선정된 니치 표시 (비편집 모드) */}
            {nicheReady && !nicheEditing && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {selectedCats.map(slug => {
                  const allItems = CONSUMER_CATEGORIES.flatMap(g => g.items);
                  const item = allItems.find(i => i.slug === slug);
                  return item ? (
                    <span key={slug} style={{
                      padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                      background: 'rgba(99,102,241,0.08)', color: '#6366f1', border: '1px solid rgba(99,102,241,0.2)',
                    }}>{item.icon} {item.ko}</span>
                  ) : null;
                })}
              </div>
            )}

            {/* 니치 선택 그리드 (편집 모드) */}
            {nicheEditing && (
              <>
                {CONSUMER_CATEGORIES.map(group => (
                  <div key={group.id}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                      {group.label}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {group.items.map(item => {
                        const locked = !item.plans.includes(planId);
                        return (
                          <PillButton key={item.slug} selected={selectedCats.includes(item.slug)}
                            onClick={() => !locked && toggleCat(item.slug)} disabled={locked}>
                            {item.icon} {item.ko}
                            {locked && ' \uD83D\uDD12'}
                          </PillButton>
                        );
                      })}
                    </div>
                  </div>
                ))}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ fontSize: 11, color: nicheReady ? 'var(--green)' : 'var(--text-dim)', flex: 1 }}>
                    {nicheReady
                      ? `\u2705 ${selectedCats.length}개 선택 완료`
                      : `최소 2개 선택 필요 (현재 ${selectedCats.length}개)`}
                  </div>
                  {nicheReady && (
                    <button onClick={() => setNicheEditing(false)} style={{
                      padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: 'var(--accent, #6366f1)', color: '#fff', fontSize: 11, fontWeight: 700,
                    }}>선택 완료</button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <Divider />

        {/* 2-B: Blog info */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <StepBadge num={'B'} done={blogOwner && contactEmail} />
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              기본 정보
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingLeft: 36 }}>
            <div>
              <label style={st.label}>블로그 운영자명 <span style={{ color: 'var(--red)', fontSize: 11 }}>*필수</span></label>
              <InputField value={blogOwner} onChange={setBlogOwner} placeholder="홍길동 / My Blog Team" />
            </div>
            <div>
              <label style={st.label}>블로그 소개 (한 줄)</label>
              <InputField value={blogDesc} onChange={setBlogDesc} placeholder="실생활에 도움이 되는 정보를 공유하는 블로그입니다" />
            </div>
            <div>
              <label style={st.label}>연락처 이메일 <span style={{ color: 'var(--red)', fontSize: 11 }}>*필수</span></label>
              <InputField value={contactEmail} onChange={setContactEmail} placeholder="contact@example.com" />
            </div>
          </div>
        </div>

        <Divider />

        {/* 2-C: Schedule */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <StepBadge num={'C'} done={scheduleConfigured} />
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              발행 스케줄
            </div>
          </div>
          <div style={{ paddingLeft: 36 }}>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                하루 발행 횟수
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {[1,2,3,4,5].map(n => {
                  const maxAllowed = plan.maxDailyPosts === 999 ? 5 : Math.min(plan.maxDailyPosts, 5);
                  const locked = n > maxAllowed;
                  return (
                    <button key={n} onClick={() => {
                      if (locked) return;
                      setDailyCount(n);
                      setScheduleTimes(prev => {
                        const next = [...prev];
                        while (next.length < n) next.push(DEFAULT_TIMES[next.length] || '09:00');
                        return next.slice(0, n);
                      });
                    }} style={{
                      width: 48, height: 48, borderRadius: 12,
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                      border: dailyCount === n ? '2px solid var(--accent)' : '1px solid var(--border-light)',
                      background: dailyCount === n ? 'var(--accent-bg)' : 'var(--card)',
                      cursor: locked ? 'not-allowed' : 'pointer',
                      opacity: locked ? 0.4 : 1,
                    }}>
                      <span style={{ fontSize: 16, fontWeight: 700, color: dailyCount === n ? 'var(--accent)' : 'var(--text)' }}>{n}</span>
                      <span style={{ fontSize: 8, color: 'var(--text-dim)' }}>회/일</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Array.from({ length: dailyCount }, (_, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
                  borderRadius: 10, border: '1px solid var(--border-light)', background: 'var(--card)',
                }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: 12, background: 'var(--accent-bg)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700, color: 'var(--accent)', flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ flex: 1, fontSize: 12, color: 'var(--text)' }}>{i + 1}회차</div>
                  <input
                    type="time"
                    value={scheduleTimes[i] || DEFAULT_TIMES[i] || '09:00'}
                    onChange={e => {
                      setScheduleTimes(prev => {
                        const next = [...prev];
                        next[i] = e.target.value;
                        return next;
                      });
                    }}
                    style={{
                      padding: '4px 10px', borderRadius: 8, border: '1px solid var(--border-light)',
                      fontSize: 13, fontWeight: 600, background: 'var(--input-bg)', color: 'var(--text)', width: 100,
                    }}
                  />
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8, padding: '6px 10px', background: 'var(--input-bg)', borderRadius: 8 }}>
              {'\u23F0'} KST(한국 표준시) 기준. 저장 시 GitHub 스케줄에 자동 반영됩니다.
            </div>
            {scheduleSync === 'success' && (
              <div style={{ fontSize: 11, color: 'var(--green)', marginTop: 6, padding: '6px 10px', background: 'var(--green-bg)', borderRadius: 8 }}>
                {'\u2705'} 발행 스케줄이 GitHub에 반영되었습니다.
              </div>
            )}
            {scheduleSync === 'failed' && (
              <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 6, padding: '6px 10px', background: 'var(--red-bg)', borderRadius: 8 }}>
                {'\u274C'} GitHub 동기화 실패: {scheduleSyncError}
              </div>
            )}
            {scheduleSync === 'syncing' && (
              <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 6 }}>
                GitHub에 스케줄 반영 중...
              </div>
            )}
          </div>
        </div>

        <Divider />

        {/* 2-D: One-click Launch OR individual actions */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <StepBadge num={'D'} done={wpSetupDone} />
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              블로그 초기화
            </div>
          </div>

          {!canLaunch && (
            <div style={{ paddingLeft: 36, marginBottom: 16 }}>
              <div style={{ padding: 14, background: 'var(--input-bg)', borderRadius: 12, fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                {'\u2139\uFE0F'} 관리자가 발행 스케줄을 관리합니다. 셀프 호스팅을 원하시면 <a href="/guide" style={{ color: 'var(--accent)', fontWeight: 600 }}>설치 가이드</a>를 참고하세요.
              </div>
            </div>
          )}

          {canLaunch && !wpSetupDone && !launchRunning && (
            <div style={{ paddingLeft: 36, marginBottom: 16 }}>
              <div style={{ padding: 14, background: 'var(--accent-bg)', borderRadius: 12, marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', marginBottom: 6 }}>
                  {'\uD83D\uDE80'} "블로그 시작하기" 버튼 하나로 모든 초기 설정이 자동 실행됩니다
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                  메뉴 설정 &rarr; 필수 페이지 생성 &rarr; CSS 디자인 적용 &rarr; 첫 글 발행까지 순서대로 실행됩니다.
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>첫 글</div>
                <select
                  value={firstPostCount}
                  onChange={e => setFirstPostCount(Number(e.target.value))}
                  style={{
                    padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border-light)',
                    fontSize: 12, background: 'var(--input-bg)', color: 'var(--text)',
                  }}
                >
                  {[1,2,3,4,5].map(n => (
                    <option key={n} value={n}>{n}편</option>
                  ))}
                </select>
              </div>

              <ActionButton
                onClick={handleLaunch}
                disabled={!launchReady}
                style={{ width: '100%', padding: '14px 0', fontSize: 15, fontWeight: 700, borderRadius: 14 }}
              >
                {'\uD83D\uDE80'} 블로그 시작하기
              </ActionButton>

              {!launchReady && (
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6, textAlign: 'center' }}>
                  {!nicheReady ? '니치를 2개 이상 선택해주세요' : '운영자명과 이메일을 입력해주세요'}
                </div>
              )}
            </div>
          )}

          {/* Launch progress */}
          {launchRunning && (
            <div style={{ paddingLeft: 36, marginBottom: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {SETUP_SEQUENCE.map((action, idx) => {
                  const result = launchResults.find(r => r.id === action.id);
                  const isCurrent = launchStep === idx;
                  const isPending = launchStep < idx && !result;
                  return (
                    <div key={action.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                      borderRadius: 10,
                      border: result?.status === 'success' ? '1px solid var(--green)'
                        : result?.status === 'failed' ? '1px solid var(--red)'
                        : isCurrent ? '1px solid var(--accent)'
                        : '1px solid var(--border-light)',
                      background: result?.status === 'success' ? 'var(--green-bg)'
                        : result?.status === 'failed' ? 'var(--red-bg)'
                        : isCurrent ? 'var(--accent-bg)'
                        : 'var(--card)',
                      opacity: isPending ? 0.5 : 1,
                    }}>
                      <span style={{ fontSize: 16 }}>{action.icon}</span>
                      <div style={{ flex: 1, fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                        {action.label}
                      </div>
                      <span style={{ fontSize: 12 }}>
                        {result?.status === 'success' ? '\u2705'
                          : result?.status === 'failed' ? '\u274C'
                          : isCurrent ? '\u23F3 실행 중...'
                          : '\u23F8'}
                      </span>
                    </div>
                  );
                })}
              </div>
              {launchResults.some(r => r.status === 'failed') && (
                <div style={{ marginTop: 10, padding: 10, background: 'var(--red-bg)', borderRadius: 8, fontSize: 11, color: 'var(--red)' }}>
                  {'\u274C'} {launchResults.find(r => r.status === 'failed')?.error || '실행 실패'}. 아래 개별 실행으로 재시도해주세요.
                </div>
              )}
            </div>
          )}

          {/* Individual actions (after launch or for re-runs) */}
          {(wpSetupDone || launchResults.length > 0) && !launchRunning && (
            <div style={{ paddingLeft: 36 }}>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 8 }}>
                개별 실행 (재설정 시)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {SETUP_SEQUENCE.map((action, idx) => {
                  const logEntry = setupLog.find(l => l.action === action.id);
                  const isDone = logEntry?.status === 'success';
                  const isRunning = setupRunning[action.id];
                  return (
                    <div key={action.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                      borderRadius: 8, border: '1px solid var(--border-light)', background: 'var(--card)',
                    }}>
                      <span style={{ fontSize: 14 }}>{action.icon}</span>
                      <div style={{ flex: 1, fontSize: 12, color: 'var(--text)' }}>{action.label}</div>
                      {isDone && <span style={{ fontSize: 10, color: 'var(--green)' }}>{'\u2705'}</span>}
                      <ActionButton
                        variant="ghost"
                        disabled={isRunning}
                        onClick={() => runSetupAction(action)}
                        style={{ fontSize: 11, padding: '4px 10px' }}
                      >
                        {isRunning ? '...' : isDone ? '재실행' : '실행'}
                      </ActionButton>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ── Setup Log ── */}
      {setupLog.length > 0 && (
        <Card style={{ marginBottom: 20 }}>
          <SectionTitle>설정 기록</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[...setupLog].sort((a, b) => (b.completed_at || '').localeCompare(a.completed_at || '')).map((entry, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderRadius: 8,
                background: entry.status === 'success' ? 'var(--green-bg)' : 'var(--red-bg)',
              }}>
                <span style={{ fontSize: 14 }}>
                  {entry.status === 'success' ? '\u2705' : '\u274C'}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                    {entry.label || entry.action}
                  </div>
                  {entry.error && (
                    <div style={{ fontSize: 11, color: 'var(--red)' }}>{entry.error}</div>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                  {entry.completed_at ? new Date(entry.completed_at).toLocaleString('ko-KR') : ''}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ═══ STEP 3: Monetization ═══ */}
      {siteConnected && wpSetupDone && (
        <Card style={{ marginBottom: 20 }}>
          <SectionTitle>수익화 설정</SectionTitle>

          {/* Stage selector */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 10 }}>
              수익화 단계
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[
                { stage: 1, label: 'Stage 1', desc: 'AdSense 승인 준비', color: 'var(--blue)' },
                { stage: 2, label: 'Stage 2', desc: '수익화 시작', color: 'var(--green)' },
                { stage: 3, label: 'Stage 3', desc: '수익 극대화', color: 'var(--accent)' },
              ].map(s => (
                <button key={s.stage} onClick={() => setMonetizationStage(s.stage)} style={{
                  flex: 1, minWidth: 100, padding: '12px 10px', borderRadius: 12, cursor: 'pointer',
                  border: monetizationStage === s.stage ? `2px solid ${s.color}` : '1px solid var(--border-light)',
                  background: monetizationStage === s.stage ? `${s.color}10` : 'var(--card)',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: monetizationStage === s.stage ? s.color : 'var(--text)' }}>
                    {s.label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>{s.desc}</div>
                </button>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8, padding: '8px 10px', background: 'var(--input-bg)', borderRadius: 8, lineHeight: 1.6 }}>
              {monetizationStage === 1 && 'Stage 1: 고품질 글만 발행 (85점+). 제휴 링크 없음. AdSense 승인 후 Stage 2로 전환하세요.'}
              {monetizationStage === 2 && 'Stage 2: 쿠팡/텐핑 제휴 링크 자동 삽입 시작. 아래에서 상품/캠페인을 등록하세요.'}
              {monetizationStage === 3 && 'Stage 3: 최대 수익 모드. 전환 키워드 비중 높음 + 쿠팡 API 딥링크.'}
            </div>
          </div>

          {/* Coupang Products (Stage 2+) */}
          {monetizationStage >= 2 && (
            <>
              <Divider />
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 10 }}>
                  {'\uD83D\uDED2'} 쿠팡 파트너스 상품
                </div>
                {coupangProducts.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                    {coupangProducts.map((p, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                        borderRadius: 8, border: '1px solid var(--border-light)', background: 'var(--card)',
                      }}>
                        <div style={{ flex: 1, fontSize: 12 }}>
                          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{p.name}</span>
                          <span style={{ color: 'var(--text-dim)', marginLeft: 6 }}>({p.category})</span>
                        </div>
                        <button onClick={() => setCoupangProducts(prev => prev.filter((_, j) => j !== i))}
                          style={{ border: 'none', background: 'none', color: 'var(--red)', fontSize: 14, cursor: 'pointer' }}>
                          {'\u2716'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <InputField value={newCoupang.name} onChange={v => setNewCoupang(p => ({ ...p, name: v }))}
                    placeholder="상품명" style={{ flex: 1, minWidth: 100 }} />
                  <InputField value={newCoupang.category} onChange={v => setNewCoupang(p => ({ ...p, category: v }))}
                    placeholder="카테고리" style={{ flex: 1, minWidth: 80 }} />
                  <InputField value={newCoupang.url} onChange={v => setNewCoupang(p => ({ ...p, url: v }))}
                    placeholder="쿠팡 파트너스 링크" style={{ flex: 2, minWidth: 150 }} />
                  <ActionButton variant="secondary" onClick={() => {
                    if (newCoupang.name && newCoupang.url) {
                      setCoupangProducts(prev => [...prev, { ...newCoupang }]);
                      setNewCoupang({ name: '', category: '', url: '' });
                    }
                  }} style={{ fontSize: 12, padding: '6px 12px', whiteSpace: 'nowrap' }}>
                    추가
                  </ActionButton>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                  쿠팡 파트너스에서 딥링크를 생성하여 붙여넣으세요. 글 발행 시 관련 키워드에 자동 삽입됩니다.
                </div>
              </div>

              {/* Tenping Campaigns */}
              <Divider />
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 10 }}>
                  {'\uD83D\uDCB0'} 텐핑 CPA 캠페인
                </div>
                {tenpingCampaigns.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                    {tenpingCampaigns.map((c, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                        borderRadius: 8, border: '1px solid var(--border-light)', background: 'var(--card)',
                      }}>
                        <div style={{ flex: 1, fontSize: 12 }}>
                          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{c.name}</span>
                          <span style={{ color: 'var(--text-dim)', marginLeft: 6 }}>({c.category})</span>
                          {c.cpa && <span style={{ color: 'var(--green)', marginLeft: 6 }}>{c.cpa}원/건</span>}
                        </div>
                        <button onClick={() => setTenpingCampaigns(prev => prev.filter((_, j) => j !== i))}
                          style={{ border: 'none', background: 'none', color: 'var(--red)', fontSize: 14, cursor: 'pointer' }}>
                          {'\u2716'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <InputField value={newTenping.name} onChange={v => setNewTenping(p => ({ ...p, name: v }))}
                    placeholder="캠페인명" style={{ flex: 1, minWidth: 100 }} />
                  <InputField value={newTenping.category} onChange={v => setNewTenping(p => ({ ...p, category: v }))}
                    placeholder="카테고리" style={{ flex: 1, minWidth: 80 }} />
                  <InputField value={newTenping.url} onChange={v => setNewTenping(p => ({ ...p, url: v }))}
                    placeholder="텐핑 링크" style={{ flex: 2, minWidth: 150 }} />
                  <InputField value={newTenping.cpa} onChange={v => setNewTenping(p => ({ ...p, cpa: v }))}
                    placeholder="CPA(원)" style={{ width: 80 }} />
                  <ActionButton variant="secondary" onClick={() => {
                    if (newTenping.name && newTenping.url) {
                      setTenpingCampaigns(prev => [...prev, { ...newTenping }]);
                      setNewTenping({ name: '', category: '', url: '', cpa: '' });
                    }
                  }} style={{ fontSize: 12, padding: '6px 12px', whiteSpace: 'nowrap' }}>
                    추가
                  </ActionButton>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                  텐핑에서 캠페인 URL을 복사하여 등록하세요. 관련 글에 CPA 링크가 자동 삽입됩니다.
                </div>
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── Profile ── */}
      <Card style={{ marginBottom: 20 }}>
        <SectionTitle>내 정보</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={st.label}>이름</label>
            <InputField value={nameEdit} onChange={setNameEdit} placeholder="표시 이름" />
          </div>
          <div>
            <label style={st.label}>이메일</label>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '10px 0' }}>{user?.email}</div>
          </div>
          <div>
            <label style={st.label}>플랜</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Badge text={plan.name} color={planId === 'premium' ? 'purple' : planId === 'mama' ? 'yellow' : 'blue'} />
              {planId === 'standard' && (
                <button onClick={() => router.push('/upgrade')}
                  style={{ border: 'none', background: 'none', color: 'var(--accent)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                  업그레이드 &rarr;
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* ── System Status ── */}
      {systemHealth && !systemHealth.ok && (
        <Card style={{ marginBottom: 20, border: '1px solid var(--red)', background: 'rgba(239,68,68,0.04)' }}>
          <SectionTitle>{'\u26A0\uFE0F'} 시스템 설정 필요</SectionTitle>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 12, lineHeight: 1.6 }}>
            자동화 기능을 사용하려면 아래 환경변수를 Vercel에 설정해야 합니다.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <SystemCheckRow label="GITHUB_TOKEN" ok={systemHealth.checks.github_token}
              desc="GitHub Personal Access Token (repo + workflow 권한)" />
            <SystemCheckRow label="GITHUB_REPO" ok={systemHealth.checks.github_repo_custom}
              desc={systemHealth.checks.github_repo_display}
              warn={!systemHealth.checks.github_repo_custom}
              warnMsg="기본값 사용 중 - fork한 경우 본인 저장소로 변경 필요" />
            <SystemCheckRow label="SUPABASE_URL" ok={systemHealth.checks.supabase_url}
              desc="Supabase 프로젝트 URL" />
            <SystemCheckRow label="SUPABASE_ANON_KEY" ok={systemHealth.checks.supabase_anon_key}
              desc="Supabase Anonymous Key" />
          </div>
        </Card>
      )}

      {/* ── Actions ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 40 }}>
        <ActionButton onClick={saveSettings} disabled={saving || !site} style={{ flex: 1 }}>
          {saving ? '저장 중...' : '설정 저장'}
        </ActionButton>
        <ActionButton variant="ghost" onClick={handleSignOut} style={{ color: 'var(--red)' }}>
          로그아웃
        </ActionButton>
      </div>
    </div>
  );
}

// ── Sub-components ──

function StepBadge({ num, done }) {
  return (
    <div style={{
      width: 26, height: 26, borderRadius: 13, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: done ? 'var(--green)' : 'var(--border-light)',
      color: done ? '#fff' : 'var(--text-dim)',
      fontSize: 11, fontWeight: 700,
    }}>
      {done ? '\u2713' : num}
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--card-border)', margin: '4px 0 16px' }} />;
}

function AppPasswordGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 4 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{ border: 'none', background: 'none', color: 'var(--accent)', fontSize: 11, cursor: 'pointer', textDecoration: 'underline', padding: 0 }}
      >
        {open ? '가이드 닫기' : '앱 비밀번호 만드는 방법'}
      </button>
      {open && (
        <div style={{ marginTop: 8, padding: 12, background: 'var(--input-bg)', borderRadius: 10, fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.8 }}>
          <strong>WordPress 앱 비밀번호 생성 방법:</strong><br/>
          1. WordPress 관리자 페이지 접속 (yoursite.com/wp-admin)<br/>
          2. 좌측 메뉴 "사용자" &rarr; "프로필"<br/>
          3. 페이지 하단 "앱 비밀번호" 섹션<br/>
          4. 새 앱 이름 입력 (예: "AutoBlog") &rarr; "새 앱 비밀번호 추가"<br/>
          5. 생성된 비밀번호 복사 (공백 포함 전체 복사)<br/>
          <div style={{ marginTop: 6, padding: 8, background: 'var(--accent-bg)', borderRadius: 6, color: 'var(--accent)' }}>
            {'\uD83D\uDCA1'} 앱 비밀번호가 보이지 않으면 HTTPS 또는 Application Passwords 플러그인이 필요합니다.
          </div>
        </div>
      )}
    </div>
  );
}

function SystemCheckRow({ label, ok, desc, warn, warnMsg }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
      borderRadius: 8, background: ok ? 'var(--green-bg)' : 'var(--red-bg)',
    }}>
      <span style={{ fontSize: 14 }}>{ok ? '\u2705' : '\u274C'}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{label}</div>
        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{desc}</div>
        {warn && warnMsg && (
          <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 2 }}>{'\u26A0\uFE0F'} {warnMsg}</div>
        )}
      </div>
    </div>
  );
}

// ── Styles ──

const st = {
  label: {
    fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4,
  },
  testBanner: {
    padding: '10px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
  },
};
