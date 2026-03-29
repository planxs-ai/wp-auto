'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { supabase } from '@/lib/supabase';
import { useUserSites, usePlanFeatures } from '@/lib/auth';
import { Card, SectionTitle, Badge, EmptyState, PillButton, PlanLock, ActionButton } from '@/components/ui';

const PIE_COLORS = ['#7c3aed', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6'];
const FILTERS = [
  { id: 'all', label: '전체' },
  { id: 'today', label: '오늘' },
  { id: 'week', label: '이번주' },
];

export default function BlogPage() {
  const router = useRouter();
  const { sites } = useUserSites();
  const { isPremiumOrAbove } = usePlanFeatures();
  const siteId = sites[0]?.id;

  const [posts, setPosts] = useState([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ total: 0, avgQuality: 0 });

  useEffect(() => {
    if (!siteId) { setLoading(false); return; }

    async function fetchData() {
      try {
        let query = supabase.from('publish_logs').select('*')
          .eq('site_id', siteId).eq('status', 'published')
          .order('published_at', { ascending: false });

        if (filter === 'today') {
          const today = new Date().toISOString().split('T')[0];
          query = query.gte('published_at', today + 'T00:00:00');
        } else if (filter === 'week') {
          const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0];
          query = query.gte('published_at', weekAgo);
        }

        const { data } = await query.limit(50);
        const allPosts = data || [];
        setPosts(allPosts);

        const qualities = allPosts.filter(p => p.quality_score != null);
        setStats({
          total: allPosts.length,
          avgQuality: qualities.length > 0 ? Math.round(qualities.reduce((s, p) => s + p.quality_score, 0) / qualities.length) : 0,
        });
      } catch (err) {
        setError(err.message || '데이터를 불러오지 못했습니다');
      }
      setLoading(false);
    }
    fetchData();
  }, [siteId, filter]);

  const filteredPosts = search
    ? posts.filter(p => (p.title || '').toLowerCase().includes(search.toLowerCase()))
    : posts;

  const nicheData = Object.entries(
    posts.reduce((acc, p) => { acc[p.niche || '기타'] = (acc[p.niche || '기타'] || 0) + 1; return acc; }, {})
  ).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

  if (loading) return <div style={{ padding: 40, color: 'var(--text-dim)', textAlign: 'center' }}>{'로딩 중...'}</div>;

  if (error) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'⚠️'}</div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{'데이터를 불러오지 못했습니다'}</h2>
        <p style={{ color: 'var(--text-dim)', fontSize: 13 }}>{error}</p>
        <ActionButton onClick={() => window.location.reload()} variant="secondary" style={{ marginTop: 16 }}>{'다시 시도'}</ActionButton>
      </div>
    );
  }

  if (!siteId) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'📝'}</div>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>사이트를 먼저 연결해주세요</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 24, fontSize: 14 }}>WordPress 사이트가 연결되면 발행된 글을 여기서 확인할 수 있습니다.</p>
        <ActionButton onClick={() => router.push('/settings')}>설정에서 연결하기</ActionButton>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>내 블로그</h1>
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          총 {stats.total}편 발행 &middot; 평균 품질 {stats.avgQuality}점
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {FILTERS.map(f => (
          <PillButton key={f.id} selected={filter === f.id} onClick={() => setFilter(f.id)}>
            {f.label}
          </PillButton>
        ))}
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="🔍 검색..."
          style={{
            marginLeft: 'auto', padding: '8px 14px', borderRadius: 10,
            border: '1px solid var(--border-light)', background: 'var(--input-bg)',
            fontSize: 12, outline: 'none', width: 200,
          }}
        />
      </div>

      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24, marginBottom: 24 }}>
        {/* Posts List */}
        <Card>
          <SectionTitle>발행 목록</SectionTitle>
          {filteredPosts.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {filteredPosts.map((post, i) => (
                <div key={post.id || i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 0', borderBottom: '1px solid var(--card-border)',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {post.title || '제목 없음'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 3, display: 'flex', gap: 8 }}>
                      <span>{post.niche || '기타'}</span>
                      <span>{post.published_at ? new Date(post.published_at).toLocaleDateString('ko-KR') : ''}</span>
                      {post.word_count && <span>{post.word_count.toLocaleString()}자</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {post.quality_score != null && (
                      <Badge text={`${post.quality_score}점`}
                        color={post.quality_score >= 90 ? 'green' : post.quality_score >= 80 ? 'yellow' : 'red'} />
                    )}
                    {post.wp_post_id && (
                      <a href={`https://${sites[0]?.domain || ''}/?p=${post.wp_post_id}`} target="_blank" rel="noopener noreferrer"
                        style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none' }}>
                        {'↗'}
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="아직 발행된 글이 없습니다" />
          )}
        </Card>

        {/* Category Distribution */}
        <div>
          <Card>
            <SectionTitle>카테고리 분포</SectionTitle>
            {nicheData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={nicheData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                      innerRadius={35} outerRadius={65} paddingAngle={2}
                      label={({ name, value }) => `${value}`}>
                      {nicheData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v) => [`${v}편`, '']}
                      contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                  {nicheData.slice(0, 8).map((d, i) => (
                    <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                      <span style={{ color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</span>
                      <span style={{ color: 'var(--text)', fontWeight: 600, flexShrink: 0 }}>{d.value}편</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState text="데이터 없음" small />
            )}
          </Card>

          {/* Premium: Performance Analysis */}
          {!isPremiumOrAbove && (
            <div style={{ marginTop: 16 }}>
              <PlanLock planRequired="Premium">
                <Card>
                  <SectionTitle>성과 분석</SectionTitle>
                  <div style={{ height: 120 }} />
                </Card>
              </PlanLock>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
