'use client';
import { useState, useEffect, useCallback } from 'react';
import { supabase, todayKST, monthStartKST } from '@/lib/supabase';

// ── 사이트 목록 ──
export function useSites() {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      const { data } = await supabase
        .from('sites')
        .select('*')
        .order('created_at');
      setSites(data || []);
      setLoading(false);
    }
    fetch();

    const channel = supabase
      .channel('sites-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sites' }, () => fetch())
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, []);

  return { sites, loading };
}

// ── 오늘 통계 ──
export function useTodayStats(siteId) {
  const [stats, setStats] = useState({ posts: 0, failures: 0, cost: 0 });
  const [loading, setLoading] = useState(true);
  const today = todayKST();

  const fetch = useCallback(async () => {
    const [postsRes, costsRes] = await Promise.all([
      supabase
        .from('publish_logs')
        .select('status', { count: 'exact' })
        .eq('site_id', siteId)
        .gte('published_at', today + 'T00:00:00+09:00')
        .lt('published_at', today + 'T23:59:59+09:00'),
      supabase
        .from('api_costs')
        .select('cost_krw')
        .eq('site_id', siteId)
        .gte('recorded_at', today + 'T00:00:00+09:00')
    ]);

    const logs = postsRes.data || [];
    const costs = costsRes.data || [];

    setStats({
      posts: logs.filter(l => l.status === 'published').length,
      failures: logs.filter(l => l.status === 'failed').length,
      cost: costs.reduce((sum, c) => sum + (c.cost_krw || 0), 0)
    });
    setLoading(false);
  }, [siteId, today]);

  useEffect(() => {
    fetch();
    const ch = supabase
      .channel(`today-${siteId}`)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'publish_logs', filter: `site_id=eq.${siteId}` }, () => fetch())
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'api_costs', filter: `site_id=eq.${siteId}` }, () => fetch())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [siteId, fetch]);

  return { stats, loading };
}

// ── 최근 발행 로그 ──
export function useRecentPosts(siteId, limit = 20) {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    const { data } = await supabase
      .from('publish_logs')
      .select('*')
      .eq('site_id', siteId)
      .order('created_at', { ascending: false })
      .limit(limit);
    setPosts(data || []);
    setLoading(false);
  }, [siteId, limit]);

  useEffect(() => {
    fetch();
    const ch = supabase
      .channel(`posts-${siteId}`)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'publish_logs', filter: `site_id=eq.${siteId}` }, () => fetch())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [siteId, fetch]);

  return { posts, loading };
}

// ── 월간 수익 ──
export function useMonthlyRevenue(siteId) {
  const [revenue, setRevenue] = useState([]);
  const [total, setTotal] = useState({ krw: 0, usd: 0 });
  const [loading, setLoading] = useState(true);
  const monthStart = monthStartKST();

  useEffect(() => {
    async function fetch() {
      const { data } = await supabase
        .from('revenue')
        .select('*')
        .eq('site_id', siteId)
        .gte('date', monthStart)
        .order('date', { ascending: false });

      const rows = data || [];
      setRevenue(rows);
      setTotal({
        krw: rows.reduce((s, r) => s + (r.revenue_krw || 0), 0),
        usd: rows.reduce((s, r) => s + (r.revenue_usd || 0), 0)
      });
      setLoading(false);
    }
    fetch();
  }, [siteId, monthStart]);

  return { revenue, total, loading };
}

// ── 월간 비용 ──
export function useMonthlyCosts(siteId) {
  const [costs, setCosts] = useState({ total_krw: 0, by_model: {} });
  const [loading, setLoading] = useState(true);
  const monthStart = monthStartKST();

  useEffect(() => {
    async function fetch() {
      const { data } = await supabase
        .from('api_costs')
        .select('model, cost_krw')
        .eq('site_id', siteId)
        .gte('recorded_at', monthStart + 'T00:00:00+09:00');

      const rows = data || [];
      const byModel = {};
      let total = 0;
      rows.forEach(r => {
        byModel[r.model] = (byModel[r.model] || 0) + (r.cost_krw || 0);
        total += r.cost_krw || 0;
      });
      setCosts({ total_krw: total, by_model: byModel });
      setLoading(false);
    }
    fetch();
  }, [siteId, monthStart]);

  return { costs, loading };
}

// ── 알림 ──
export function useAlerts(siteId) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    const query = supabase
      .from('alerts')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(50);

    if (siteId && siteId !== 'all') {
      query.eq('site_id', siteId);
    }

    const { data } = await query;
    setAlerts(data || []);
    setLoading(false);
  }, [siteId]);

  useEffect(() => {
    fetch();
    const ch = supabase
      .channel('alerts-live')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alerts' }, () => fetch())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [fetch]);

  const markRead = async (id) => {
    await supabase.from('alerts').update({ is_read: true }).eq('id', id);
    fetch();
  };

  return { alerts, loading, markRead };
}

// ── 발행 추이 (최근 7일) ──
export function usePublishTrend(siteId, days = 7) {
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      const since = new Date();
      since.setDate(since.getDate() - days);
      const sinceStr = since.toISOString().split('T')[0];

      const { data } = await supabase
        .from('publish_logs')
        .select('published_at, status')
        .eq('site_id', siteId)
        .gte('published_at', sinceStr + 'T00:00:00+09:00')
        .order('published_at');

      // 일별 집계
      const byDay = {};
      (data || []).forEach(row => {
        const day = row.published_at.split('T')[0];
        if (!byDay[day]) byDay[day] = { date: day, published: 0, failed: 0 };
        if (row.status === 'published') byDay[day].published++;
        else if (row.status === 'failed') byDay[day].failed++;
      });

      setTrend(Object.values(byDay).sort((a, b) => a.date.localeCompare(b.date)));
      setLoading(false);
    }
    fetch();
  }, [siteId, days]);

  return { trend, loading };
}

// ── 총 발행 수 (Stage 전환 조건) ──
export function useTotalPublished(siteId) {
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      const { count: total } = await supabase
        .from('publish_logs')
        .select('*', { count: 'exact', head: true })
        .eq('site_id', siteId)
        .eq('status', 'published');
      setCount(total || 0);
      setLoading(false);
    }
    fetch();
  }, [siteId]);

  return { totalPublished: count, loading };
}

// ── 대시보드 설정 (Supabase 영속화) ──
export function useDashboardConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      const { data } = await supabase
        .from('dashboard_config')
        .select('*')
        .eq('id', 'global')
        .single();
      setConfig(data?.settings || {});
      setLoading(false);
    }
    fetch();
  }, []);

  const saveConfig = useCallback(async (newSettings) => {
    const merged = { ...(config || {}), ...newSettings };
    setConfig(merged);
    await supabase
      .from('dashboard_config')
      .upsert({
        id: 'global',
        settings: merged,
        updated_at: new Date().toISOString()
      });
  }, [config]);

  return { config, loading, saveConfig };
}
