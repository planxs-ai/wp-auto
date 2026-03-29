'use client';
import { useState, useEffect, useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { supabase, todayKST, monthStartKST } from '@/lib/supabase';
import { useCurrentUser, usePlanFeatures, useUserSites, useMilestones } from '@/lib/auth';
import { MILESTONES } from '@/lib/plan-features';
import { Card, StatCard, SectionTitle, Badge, ProgressBar, ActionButton, PlanLock } from '@/components/ui';

export default function ConsumerDashboard() {
  const { displayName, monetizationStage } = useCurrentUser();
  const { plan, planId, isPremiumOrAbove } = usePlanFeatures();
  const { sites } = useUserSites();
  const { isAchieved } = useMilestones();

  const siteId = sites[0]?.id;
  const siteName = sites[0]?.name || sites[0]?.domain || '';

  const [todayStats, setTodayStats] = useState({ posts: 0, failures: 0, cost: 0 });
  const [monthRevenue, setMonthRevenue] = useState(0);
  const [prevMonthRevenue, setPrevMonthRevenue] = useState(0);
  const [totalPosts, setTotalPosts] = useState(0);
  const [recentPosts, setRecentPosts] = useState([]);
  const [revenueTrend, setRevenueTrend] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!siteId) { setLoading(false); return; }

    const today = todayKST();
    const monthStart = monthStartKST();

    async function fetchAll() {
      try {
      const [postsRes, totalRes, recentRes, revenueRes, prevRevenueRes, trendRes] = await Promise.all([
        // Today's posts
        supabase.from('publish_logs').select('status', { count: 'exact' })
          .eq('site_id', siteId).gte('published_at', today + 'T00:00:00+09:00').lt('published_at', today + 'T23:59:59+09:00'),
        // Total posts
        supabase.from('publish_logs').select('id', { count: 'exact', head: true })
          .eq('site_id', siteId).eq('status', 'success'),
        // Recent 5 posts
        supabase.from('publish_logs').select('*')
          .eq('site_id', siteId).eq('status', 'success').order('published_at', { ascending: false }).limit(5),
        // This month revenue
        supabase.from('revenue').select('amount')
          .eq('site_id', siteId).gte('date', monthStart),
        // Previous month revenue
        supabase.from('revenue').select('amount')
          .eq('site_id', siteId)
          .gte('date', getPrevMonthStart())
          .lt('date', monthStart),
        // Revenue trend (last 30 days)
        supabase.from('revenue').select('date, amount, source')
          .eq('site_id', siteId)
          .gte('date', getLast30Days())
          .order('date'),
      ]);

      setTodayStats({
        posts: postsRes.count || 0,
        failures: (postsRes.data || []).filter(p => p.status === 'failed').length,
      });
      setTotalPosts(totalRes.count || 0);
      setRecentPosts(recentRes.data || []);
      setMonthRevenue((revenueRes.data || []).reduce((s, r) => s + (r.amount || 0), 0));
      setPrevMonthRevenue((prevRevenueRes.data || []).reduce((s, r) => s + (r.amount || 0), 0));
      setRevenueTrend(aggregateTrend(trendRes.data || []));
      } catch (err) {
        setError(err.message || '\ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4');
      }
      setLoading(false);
    }

    fetchAll();
  }, [siteId]);

  const revenueChange = prevMonthRevenue > 0
    ? Math.round(((monthRevenue - prevMonthRevenue) / prevMonthRevenue) * 100)
    : monthRevenue > 0 ? 100 : 0;

  const healthScore = useMemo(() => {
    let score = 50;
    if (totalPosts >= 30) score += 20;
    else if (totalPosts >= 10) score += 10;
    if (todayStats.posts >= 2) score += 15;
    if (todayStats.failures === 0) score += 10;
    if (monthRevenue > 0) score += 5;
    return Math.min(score, 100);
  }, [totalPosts, todayStats, monthRevenue]);

  const healthColor = healthScore >= 80 ? 'var(--green)' : healthScore >= 60 ? 'var(--yellow)' : 'var(--red)';
  const healthLabel = healthScore >= 80 ? '양호' : healthScore >= 60 ? '보통' : '주의';

  const smartAction = useMemo(() => {
    if (totalPosts < 20) return { text: `AdSense 승인까지 ${20 - totalPosts}편 더 필요합니다. 꾸준히 발행하세요!`, action: null };
    if (monetizationStage === 1) return { text: 'AdSense 승인을 신청할 준비가 됐습니다!', action: '설정에서 확인' };
    if (monetizationStage === 2) return { text: '쿠팡 파트너스 상품을 등록하면 수익이 증가합니다', action: '수익 탭에서 확인' };
    return { text: '모든 수익 채널이 가동 중입니다. 계속 발행하세요!', action: null };
  }, [totalPosts, monetizationStage]);

  if (loading) {
    return <div style={{ padding: 40, color: 'var(--text-dim)', textAlign: 'center' }}>{'\ub300\uc2dc\ubcf4\ub4dc \ub85c\ub529 \uc911...'}</div>;
  }

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
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'\ud83c\udf10'}</div>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>사이트를 연결해주세요</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 24 }}>블로그 사이트를 연결하면 자동 발행이 시작됩니다.</p>
        <ActionButton onClick={() => window.location.href = '/settings'}>사이트 연결하기</ActionButton>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', marginBottom: 4 }}>
          안녕하세요, {displayName}님!
        </h1>
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          {siteName} &middot; {plan.name} 플랜
        </div>
      </div>

      {/* Score Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 32 }}>
        <StatCard label="오늘 발행" value={`${todayStats.posts}편`} color="var(--accent)" icon="\u25a3"
          sub={todayStats.posts > 0 ? `목표 ${plan.maxDailyPosts === 999 ? '무제한' : plan.maxDailyPosts}편` : '발행 대기 중'} />
        <StatCard label="이달 수익" value={fmtKRW(monthRevenue)} color="var(--green)"
          icon="\u2606" sub={revenueChange !== 0 ? `${revenueChange > 0 ? '\u25b2' : '\u25bc'}${Math.abs(revenueChange)}% vs 지난달` : ''} />
        <StatCard label="총 발행" value={`${totalPosts}편`} color="var(--blue)" icon="\u25ce" />
        <StatCard label="블로그 건강도" value={`${healthScore}점`} color={healthColor}
          icon="\u25c9" sub={healthLabel} />
      </div>

      {/* Revenue Trend */}
      <Card style={{ marginBottom: 24 }}>
        <SectionTitle>이번 달 수익 트렌드</SectionTitle>
        {revenueTrend.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={revenueTrend}>
              <defs>
                <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false}
                tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false}
                tickFormatter={v => `${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v) => [`\u20a9${v.toLocaleString()}`, '수익']}
                contentStyle={{ borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12 }} />
              <Area type="monotone" dataKey="amount" stroke="var(--accent)" strokeWidth={2}
                fill="url(#colorRevenue)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)', fontSize: 13 }}>
            수익 데이터가 아직 없습니다. 글이 발행되면 여기에 수익 추이가 표시됩니다.
          </div>
        )}
      </Card>

      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
        {/* Smart Actions */}
        <Card>
          <SectionTitle>다음 할 일</SectionTitle>
          <div style={{
            padding: 16, borderRadius: 12, border: '1px solid var(--accent)',
            background: 'var(--accent-bg)',
          }}>
            <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6 }}>
              {'\ud83c\udfaf'} {smartAction.text}
            </div>
            {smartAction.action && (
              <div style={{ marginTop: 10 }}>
                <ActionButton variant="secondary" style={{ fontSize: 12, padding: '6px 14px' }}>
                  {smartAction.action} &rarr;
                </ActionButton>
              </div>
            )}
          </div>
        </Card>

        {/* Recent Posts */}
        <Card>
          <SectionTitle action={
            <button onClick={() => window.location.href = '/blog'}
              style={{ border: 'none', background: 'none', color: 'var(--accent)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              전체보기 &rarr;
            </button>
          }>최근 발행</SectionTitle>
          {recentPosts.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {recentPosts.map((post, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 0', borderBottom: i < recentPosts.length - 1 ? '1px solid var(--card-border)' : 'none'
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {post.title || '제목 없음'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                      {post.published_at ? new Date(post.published_at).toLocaleDateString('ko-KR') : ''}
                      {post.niche && ` \u00b7 ${post.niche}`}
                    </div>
                  </div>
                  {post.quality_score != null && (
                    <Badge
                      text={`${post.quality_score}점`}
                      color={post.quality_score >= 90 ? 'green' : post.quality_score >= 80 ? 'yellow' : 'red'}
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-dim)', fontSize: 13 }}>
              아직 발행된 글이 없습니다
            </div>
          )}
        </Card>
      </div>

      {/* Milestones */}
      <Card style={{ marginBottom: 24 }}>
        <SectionTitle>마일스톤</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {MILESTONES.slice(0, 5).map(ms => {
            const achieved = isAchieved(ms.id);
            const progress = getMilestoneProgress(ms, totalPosts, monthRevenue);
            return (
              <div key={ms.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ fontSize: 20, width: 32, textAlign: 'center', opacity: achieved ? 1 : 0.4 }}>
                  {achieved ? '\u2705' : ms.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: achieved ? 'var(--green)' : 'var(--text)' }}>
                      {ms.label}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                      {achieved ? '달성!' : `${Math.round(progress)}%`}
                    </span>
                  </div>
                  <ProgressBar value={achieved ? 100 : progress} max={100}
                    color={achieved ? 'var(--green)' : 'var(--accent)'} height={6} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Premium upsell for Standard users */}
      {!isPremiumOrAbove && (
        <Card style={{ background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)', border: '1px solid rgba(124,58,237,0.15)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', marginBottom: 4 }}>
                Premium으로 수익을 극대화하세요
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                Golden Mode, 고급 분석, 일 20편 발행, 맞춤 스케줄
              </div>
            </div>
            <ActionButton onClick={() => window.location.href = '/upgrade'} style={{ whiteSpace: 'nowrap' }}>
              업그레이드
            </ActionButton>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Helpers ──

function fmtKRW(n) {
  if (n >= 10000) return `\u20a9${(n / 10000).toFixed(1)}만`;
  return `\u20a9${(n || 0).toLocaleString('ko-KR')}`;
}

function getPrevMonthStart() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function getLast30Days() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
}

function aggregateTrend(data) {
  const byDate = {};
  for (const r of data) {
    byDate[r.date] = (byDate[r.date] || 0) + (r.amount || 0);
  }
  return Object.entries(byDate).map(([date, amount]) => ({ date, amount })).sort((a, b) => a.date.localeCompare(b.date));
}

function getMilestoneProgress(ms, totalPosts, monthRevenue) {
  if (ms.metric === 'total_posts') return Math.min((totalPosts / ms.target) * 100, 100);
  if (ms.metric === 'monthly_revenue') return Math.min((monthRevenue / ms.target) * 100, 100);
  return 0;
}
