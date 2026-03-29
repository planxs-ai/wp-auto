'use client';
import { useState, useEffect, useMemo } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { supabase, monthStartKST } from '@/lib/supabase';
import { useCurrentUser, useUserSites, usePlanFeatures } from '@/lib/auth';
import { Card, StatCard, SectionTitle, Badge, ProgressBar, ActionButton, PlanLock } from '@/components/ui';


const STAGES = [
  { id: 1, label: 'AdSense 승인', color: '#3b82f6',
    desc: '양질의 콘텐츠로 Google AdSense 승인을 획득합니다.',
    tips: ['20편 이상 고유 콘텐츠 필요', '필수 페이지: About, Privacy, Contact', '제휴 링크 없이 순수 정보성 글만'] },
  { id: 2, label: '수익화 시작', color: '#f59e0b',
    desc: '텐핑 CPA + 쿠팡 수동 링크로 첫 수익을 만듭니다.',
    tips: ['텐핑 고단가 오퍼 선택 (보험 3,000~8,000원)', '쿠팡 15만원 판매 → API 해금', 'IT/가전 리뷰에 쿠팡 링크 매칭'] },
  { id: 3, label: '수익 극대화', color: '#10b981',
    desc: '쿠팡 API + 텐핑 풀가동 + AI 도구 레퍼럴로 극대화합니다.',
    tips: ['쿠팡 API 딥링크 자동화', 'AI 도구 레퍼럴 프로그램 가입', '높은 RPM 카테고리 비중 확대'] },
];

export default function RevenuePage() {
  const { monetizationStage } = useCurrentUser();
  const { isPremiumOrAbove } = usePlanFeatures();
  const { sites } = useUserSites();
  const siteId = sites[0]?.id;

  const [revenueData, setRevenueData] = useState([]);
  const [monthTotal, setMonthTotal] = useState(0);
  const [prevMonthTotal, setPrevMonthTotal] = useState(0);
  const [byChannel, setByChannel] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!siteId) { setLoading(false); return; }

    const monthStart = monthStartKST();
    const prevStart = getPrevMonthStart();

    async function fetchData() {
      try {
        const [currentRes, prevRes, trendRes] = await Promise.all([
          supabase.from('revenue').select('amount, source').eq('site_id', siteId).gte('date', monthStart),
          supabase.from('revenue').select('amount').eq('site_id', siteId).gte('date', prevStart).lt('date', monthStart),
          supabase.from('revenue').select('date, amount, source').eq('site_id', siteId)
            .gte('date', getLast30Days()).order('date'),
        ]);

        const current = currentRes.data || [];
        setMonthTotal(current.reduce((s, r) => s + (r.amount || 0), 0));
        setPrevMonthTotal((prevRes.data || []).reduce((s, r) => s + (r.amount || 0), 0));

        const channels = {};
        for (const r of current) {
          const src = r.source || '\uae30\ud0c0';
          channels[src] = (channels[src] || 0) + (r.amount || 0);
        }
        setByChannel(channels);

        const byDate = {};
        for (const r of (trendRes.data || [])) {
          byDate[r.date] = (byDate[r.date] || 0) + (r.amount || 0);
        }
        setRevenueData(Object.entries(byDate).map(([date, amount]) => ({ date, amount })));
      } catch (err) {
        setError(err.message || '\ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4');
      }
      setLoading(false);
    }
    fetchData();
  }, [siteId]);

  const changeRate = prevMonthTotal > 0
    ? Math.round(((monthTotal - prevMonthTotal) / prevMonthTotal) * 100) : 0;

  const channelData = Object.entries(byChannel).map(([name, value]) => ({ name: translateSource(name), value }))
    .sort((a, b) => b.value - a.value);

  const currentStage = STAGES.find(s => s.id === monetizationStage) || STAGES[0];

  if (loading) return <div style={{ padding: 40, color: 'var(--text-dim)', textAlign: 'center' }}>{'\ub85c\ub529 \uc911...'}</div>;

  if (error) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'\u26a0\ufe0f'}</div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{'\ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4'}</h2>
        <p style={{ color: 'var(--text-dim)', fontSize: 13 }}>{error}</p>
        <ActionButton onClick={() => window.location.reload()} variant="secondary" style={{ marginTop: 16 }}>{'\ub2e4\uc2dc \uc2dc\ub3c4'}</ActionButton>
      </div>
    );
  }

  if (!siteId) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'\ud83d\udcb0'}</div>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>사이트를 먼저 연결해주세요</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 24, fontSize: 14 }}>WordPress 사이트가 연결되면 수익 현황을 여기서 확인할 수 있습니다.</p>
        <ActionButton onClick={() => window.location.href = '/settings'}>설정에서 연결하기</ActionButton>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>수익</h1>
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          이번 달: {fmtKRW(monthTotal)} {changeRate !== 0 && `(${changeRate > 0 ? '+' : ''}${changeRate}% vs 지난달)`}
        </div>
      </div>

      {/* Channel Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatCard label="총 수익" value={fmtKRW(monthTotal)} color="var(--accent)" icon="\u2606" />
        {channelData.slice(0, 3).map(ch => (
          <StatCard key={ch.name} label={ch.name} value={fmtKRW(ch.value)} color="var(--green)" />
        ))}
      </div>

      {/* Revenue Trend */}
      <Card style={{ marginBottom: 24 }}>
        <SectionTitle>수익 추이 (최근 30일)</SectionTitle>
        {revenueData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={revenueData}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false}
                tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false}
                tickFormatter={v => `${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v) => [`\u20a9${v.toLocaleString()}`, '수익']}
                contentStyle={{ borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12 }} />
              <Area type="monotone" dataKey="amount" stroke="var(--accent)" strokeWidth={2}
                fill="url(#revGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)', fontSize: 13 }}>
            수익 데이터가 아직 없습니다
          </div>
        )}
      </Card>

      {/* Monetization Roadmap */}
      <Card style={{ marginBottom: 24 }}>
        <SectionTitle>수익화 로드맵</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {STAGES.map(stage => {
            const isCurrent = stage.id === monetizationStage;
            const isDone = stage.id < monetizationStage;
            return (
              <div key={stage.id} style={{
                padding: 16, borderRadius: 12,
                border: isCurrent ? `2px solid ${stage.color}` : '1px solid var(--card-border)',
                background: isCurrent ? `${stage.color}10` : isDone ? 'var(--green-bg)' : 'var(--card)',
                opacity: !isCurrent && !isDone ? 0.6 : 1,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: isDone ? 'var(--green)' : isCurrent ? stage.color : 'var(--border-light)',
                    color: '#fff', fontSize: 13, fontWeight: 700,
                  }}>{isDone ? '\u2713' : stage.id}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>{stage.label}</div>
                  {isCurrent && <Badge text="현재" color="purple" />}
                  {isDone && <Badge text="완료" color="green" />}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{stage.desc}</div>
                {isCurrent && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {stage.tips.map((tip, i) => (
                      <div key={i} style={{ fontSize: 11, color: 'var(--text-dim)', paddingLeft: 12 }}>
                        &bull; {tip}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Premium: Revenue Simulation */}
      {!isPremiumOrAbove && (
        <PlanLock planRequired="Premium">
          <Card>
            <SectionTitle>수익 시뮬레이션</SectionTitle>
            <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>
              현재 속도 기반 수익 예측 차트
            </div>
          </Card>
        </PlanLock>
      )}
    </div>
  );
}

function fmtKRW(n) {
  if (n >= 10000) return `\u20a9${(n / 10000).toFixed(1)}만`;
  return `\u20a9${(n || 0).toLocaleString('ko-KR')}`;
}

function getPrevMonthStart() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function getLast30Days() {
  const d = new Date(); d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
}

function translateSource(src) {
  const map = { adsense: 'AdSense', coupang: '쿠팡', tenping: '텐핑', referral: '레퍼럴' };
  return map[src] || src;
}
