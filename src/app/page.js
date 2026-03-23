'use client';
import { useState, useCallback, useEffect } from 'react';
import { useSites, useTodayStats, useRecentPosts, useMonthlyRevenue, useMonthlyCosts, useAlerts, usePublishTrend, useDashboardConfig } from '@/lib/hooks';
import { supabase, isConfigured } from '@/lib/supabase';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';

// ═══════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════

const NICHE_CATS = [
  { id: 'product', label: '제품 리뷰/비교', icon: '🛍️', items: [
    { slug: 'ai-tools', ko: 'AI 도구', icon: '🤖', cpm: '$25~50' },
    { slug: 'tech', ko: 'IT/전자기기', icon: '💻', cpm: '$20~40' },
    { slug: 'smart-home', ko: '스마트홈', icon: '🏠', cpm: '$20~40' },
    { slug: 'pet', ko: '반려동물', icon: '🐾', cpm: '$15~30' },
    { slug: 'appliance', ko: '생활가전', icon: '🔌', cpm: '$15~25' },
    { slug: 'beauty', ko: '뷰티', icon: '💄', cpm: '$15~30' },
    { slug: 'health', ko: '건강/웰니스', icon: '💪', cpm: '$15~35' },
    { slug: 'baby', ko: '육아/유아', icon: '👶', cpm: '$20~35' },
    { slug: 'fitness', ko: '운동기구', icon: '🏋️', cpm: '$15~25' },
    { slug: 'finance', ko: '재테크', icon: '💰', cpm: '$25~50' },
    { slug: 'education', ko: '교육/생산성', icon: '📚', cpm: '$15~30' },
  ]},
  { id: 'news', label: '뉴스/리서치', icon: '📰', items: [
    { slug: 'news-sbs', ko: 'SBS 뉴스', icon: '📺' },
    { slug: 'news-kbs', ko: 'KBS 뉴스', icon: '📺' },
    { slug: 'news-jtbc', ko: 'JTBC 뉴스', icon: '📺' },
    { slug: 'news-mbc', ko: 'MBC 뉴스', icon: '📺' },
    { slug: 'sns-trend', ko: 'SNS 인기 이슈', icon: '🔥' },
    { slug: 'top10-corp', ko: '10대 대기업', icon: '🏢' },
  ]},
  { id: 'sector', label: '섹터 리서치', icon: '📊', items: [
    { slug: 's-semi', ko: '반도체', icon: '🔬' },
    { slug: 's-ai', ko: 'AI/인공지능', icon: '🤖' },
    { slug: 's-defense', ko: '방산', icon: '🛡️' },
    { slug: 's-pharma', ko: '제약/바이오', icon: '💊' },
    { slug: 's-chem', ko: '화학', icon: '⚗️' },
    { slug: 's-robot', ko: '로봇', icon: '🦾' },
    { slug: 's-security', ko: '보안', icon: '🔒' },
    { slug: 's-enter', ko: '엔터', icon: '🎬' },
    { slug: 's-ev', ko: '전기차/2차전지', icon: '🔋' },
    { slug: 's-space', ko: '우주/항공', icon: '🚀' },
  ]},
  { id: 'info', label: '정보 서비스', icon: '📋', items: [
    { slug: 'gov-support', ko: '정부지원/보조금', icon: '🏛️' },
    { slug: 'tax-guide', ko: '세무/절세', icon: '🧾' },
    { slug: 'agency', ko: '기관 정보', icon: '🏢' },
    { slug: 'event', ko: '행사/컨퍼런스', icon: '🎪' },
    { slug: 'travel', ko: '여행 정보', icon: '✈️' },
    { slug: 'keyword-collect', ko: '키워드 수집', icon: '🔍' },
  ]},
  { id: 'promo', label: '홍보/마케팅', icon: '📢', items: [
    { slug: 'niche-promo', ko: '니치 홍보용', icon: '📣' },
    { slug: 'brand', ko: '브랜드 콘텐츠', icon: '🏷️' },
    { slug: 'compare-land', ko: '비교 랜딩', icon: '⚖️' },
  ]},
];

const AFF_KR = [
  { id: 'coupang', name: '쿠팡 파트너스', comm: '3%', signup: 'partners.coupang.com' },
  { id: 'tenping', name: '텐핑', comm: '건당100~5000원', signup: 'tenping.kr' },
  { id: 'linkprice', name: '링크프라이스', comm: '1~10%', signup: 'linkprice.com' },
  { id: 'adpick', name: '애드픽', comm: '건당200~3000원', signup: 'adpick.co.kr' },
  { id: 'revu', name: '레뷰', comm: '건당500~10000원', signup: 'revu.net' },
  { id: 'dbdbdeep', name: '디비디비딥', comm: '건당500~5000원', signup: 'dbdbdeep.com' },
  { id: 'leaders', name: '리더스CPA', comm: '건당500~8000원', signup: 'leaderscpa.com' },
];

const AFF_GLOBAL = [
  { id: 'amazon', name: 'Amazon Associates', comm: '1~10%', signup: 'affiliate-program.amazon.com' },
  { id: 'shareasale', name: 'ShareASale', comm: '다양', signup: 'shareasale.com' },
  { id: 'cj', name: 'CJ Affiliate', comm: '다양', signup: 'cj.com' },
  { id: 'impact', name: 'Impact', comm: '다양', signup: 'impact.com' },
  { id: 'awin', name: 'Awin', comm: '다양', signup: 'awin.com' },
];

const INIT_SAAS = [
  // AI 글쓰기/콘텐츠
  { name: 'Jasper AI', cat: 'AI글쓰기', comm: '30% 평생반복', url: '' },
  { name: 'Writesonic', cat: 'AI글쓰기', comm: '30% 평생반복', url: '' },
  { name: 'Copy.ai', cat: 'AI글쓰기', comm: '45% 1년반복', url: '' },
  { name: 'Koala AI', cat: 'AI글쓰기', comm: '30% 평생반복', url: '' },
  // AI 영상/음성
  { name: 'Synthesia', cat: 'AI영상', comm: '20% 12개월', url: '' },
  { name: 'ElevenLabs', cat: 'AI음성', comm: '22% 12개월', url: '' },
  { name: 'Descript', cat: 'AI영상', comm: '$25/건', url: '' },
  // SEO 도구
  { name: 'Surfer SEO', cat: 'SEO', comm: '최대125% 1회', url: '' },
  { name: 'Semrush', cat: 'SEO', comm: '$200/건', url: '' },
  { name: 'Mangools', cat: 'SEO', comm: '35% 평생반복', url: '' },
  // 이메일 마케팅
  { name: 'GetResponse', cat: '이메일', comm: '33~50% 반복', url: '' },
  { name: 'Kit(ConvertKit)', cat: '이메일', comm: '50% 12개월', url: '' },
  { name: 'Beehiiv', cat: '이메일', comm: '50% 12개월', url: '' },
  // CRM/마케팅
  { name: 'HubSpot', cat: 'CRM', comm: '30% 12개월', url: '' },
  { name: 'ActiveCampaign', cat: 'CRM', comm: '15~25% 반복', url: '' },
  // 호스팅/클라우드
  { name: 'Cloudways', cat: '호스팅', comm: '$30+7% 평생', url: '' },
  { name: 'Hostinger', cat: '호스팅', comm: '40%+ 1회', url: '' },
  { name: 'Railway', cat: '클라우드', comm: '15% 12개월', url: '' },
  // 디자인
  { name: 'Canva', cat: '디자인', comm: '$36/건', url: '' },
  { name: 'Adobe', cat: '디자인', comm: '최대85% 1회', url: '' },
  // 프로젝트 관리
  { name: 'Notion', cat: '생산성', comm: '50% 12개월', url: '' },
  { name: 'Monday.com', cat: '생산성', comm: '최대100% 1년', url: '' },
  { name: 'ClickUp', cat: '생산성', comm: '20%/$25', url: '' },
  // VPN/보안
  { name: 'NordVPN', cat: 'VPN', comm: '100%+30% 반복', url: '' },
  { name: 'Surfshark', cat: 'VPN', comm: '40% RevShare', url: '' },
  // 교육
  { name: 'Teachable', cat: '교육', comm: '30% 12개월', url: '' },
  { name: 'Thinkific', cat: '교육', comm: '30% 평생반복', url: '' },
  // 금융
  { name: 'Wise', cat: '금융', comm: 'GBP10~50/건', url: '' },
  { name: 'Payoneer', cat: '금융', comm: '$25/건', url: '' },
  // 소셜미디어
  { name: 'Buffer', cat: 'SNS관리', comm: '25% 12개월', url: '' },
  // SaaS 할인 마켓
  { name: 'JoinSecret', cat: 'SaaS딜', comm: '30% 평생반복', url: '' },
];

const AI_MODELS_API = [
  { id: 'gemini', name: 'Gemini 2.0 Flash', cost: '무료', signup: 'aistudio.google.com/apikey' },
  { id: 'grok', name: 'Grok 4.1 Fast', cost: '$0.20/MTok', signup: 'console.x.ai' },
  { id: 'claude', name: 'Claude Haiku 4.5', cost: '$1/MTok', signup: 'console.anthropic.com' },
  { id: 'openai', name: 'GPT-4o Mini', cost: '$0.15/MTok', signup: 'platform.openai.com' },
  { id: 'deepseek', name: 'DeepSeek V3', cost: '$0.07/MTok', signup: 'platform.deepseek.com' },
];

const IMG_APIS = [
  { id: 'pexels', name: 'Pexels', cost: '무료', signup: 'pexels.com/api' },
  { id: 'pixabay', name: 'Pixabay', cost: '무료', signup: 'pixabay.com/api/docs' },
  { id: 'unsplash', name: 'Unsplash', cost: '무료', signup: 'unsplash.com/developers' },
];

const SNS_LIST = [
  { id: 'x', name: 'X (Twitter)' }, { id: 'threads', name: 'Threads' },
  { id: 'naver_blog', name: '네이버 블로그' }, { id: 'naver_cafe', name: '네이버 카페' },
  { id: 'telegram', name: 'Telegram' }, { id: 'discord', name: 'Discord' },
];

const DAYS = ['월', '화', '수', '목', '금', '토', '일'];
const TIMES = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, '0');
  const m = i % 2 === 0 ? '00' : '30';
  return `${h}:${m}`;
});
const TZ_LIST = [
  { id: 'KST', label: '한국 (KST)', off: '+9' },
  { id: 'EST', label: '미국동부 (EST)', off: '-5' },
  { id: 'CST', label: '미국중부 (CST)', off: '-6' },
  { id: 'PST', label: '미국서부 (PST)', off: '-8' },
];
const PRESETS = [
  { id: 'd1', label: '매일 1회', days: [0, 1, 2, 3, 4, 5, 6], times: ['08:00'] },
  { id: 'd2', label: '매일 2회', days: [0, 1, 2, 3, 4, 5, 6], times: ['08:00', '18:00'] },
  { id: 'wd', label: '평일 1회', days: [0, 1, 2, 3, 4], times: ['08:00'] },
  { id: 'mwf', label: '월/수/금', days: [0, 2, 4], times: ['08:00'] },
  { id: 'we', label: '주말만', days: [5, 6], times: ['10:00'] },
  { id: 'custom', label: '직접 설정', days: [], times: [] },
];

const DRAFT_MODELS = [
  { id: 'deepseek-chat', name: 'DeepSeek V3', costPer: 35, speed: '빠름', quality: '보통' },
  { id: 'grok-3', name: 'Grok 3', costPer: 120, speed: '보통', quality: '높음' },
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', costPer: 90, speed: '보통', quality: '높음' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', costPer: 25, speed: '매우 빠름', quality: '보통' },
  { id: 'gpt-5-mini', name: 'GPT-5 mini', costPer: 60, speed: '빠름', quality: '높음' },
  { id: 'gpt-4.1-mini', name: 'GPT-4.1 mini', costPer: 45, speed: '빠름', quality: '보통' },
];
const POLISH_MODELS = [
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', costPer: 80 },
  { id: 'claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5', costPer: 30 },
  { id: 'none', name: '폴리싱 OFF', costPer: 0 },
];

const TABS = [
  { id: 'dash', label: '대시보드', icon: '◎' },
  { id: 'logs', label: '발행 로그', icon: '⊞' },
  { id: 'niche', label: '니치/발행', icon: '◉' },
  { id: 'schedule', label: '스케줄', icon: '◷' },
  { id: 'money', label: '수익화', icon: '↗' },
  { id: 'api', label: 'API/연동', icon: '⊞' },
  { id: 'adsense', label: 'AdSense', icon: '▣' },
  { id: 'revenue', label: '수익', icon: '★' },
  { id: 'costs', label: '비용', icon: '◈' },
  { id: 'alerts', label: '알림', icon: '⚡' },
  { id: 'settings', label: '설정', icon: '⚙' },
  { id: 'admin', label: '관리자', icon: '☰' },
];

const PIE_COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6'];

const ADSENSE_ITEMS = [
  { id: 'posts30', l: '글 30편+', d: '양질의 고유 콘텐츠', c: true },
  { id: 'words', l: '평균 1,500자+', d: '얇은 콘텐츠 회피', c: true },
  { id: 'images', l: '이미지 100%', d: '모든 글에 이미지 2장+', c: true },
  { id: 'about', l: 'About 페이지', d: '사이트 소개+운영자', c: true },
  { id: 'privacy', l: '개인정보처리방침', d: 'Privacy Policy', c: true },
  { id: 'contact', l: '연락처 페이지', d: 'Contact Us', c: true },
  { id: 'disclaimer', l: '면책 고지', d: 'Disclaimer', c: false },
  { id: 'terms', l: '이용약관', d: 'Terms of Use', c: false },
  { id: 'ssl', l: 'HTTPS 적용', d: 'Cloudways 기본 제공', c: true },
  { id: 'speed', l: '속도 3초 이내', d: 'Breeze 캐시', c: true },
  { id: 'mobile', l: '모바일 반응형', d: 'GeneratePress', c: true },
  { id: 'domain', l: '도메인 3개월+', d: '일부 국가', c: false },
  { id: 'nav', l: '메뉴 네비게이션', d: '카테고리+필수메뉴', c: true },
  { id: 'freq', l: '주 2회+ 발행', d: '꾸준한 업데이트', c: false },
  { id: 'unique', l: '100% 고유 콘텐츠', d: '복사 없음', c: true },
];

// ═══════════════════════════════════════════
// SHARED COMPONENTS
// ═══════════════════════════════════════════

function Card({ children, style }) {
  return (
    <div style={{
      background: '#ffffff', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 16,
      padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      animation: 'fadeIn 0.3s ease', ...style
    }}>{children}</div>
  );
}

function StatCard({ label, value, sub, color, icon }) {
  return (
    <Card style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: -8, right: -8, fontSize: 48, opacity: 0.06,
        fontWeight: 900, color: color || '#1a1a2e'
      }}>{icon || '●'}</div>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6, fontWeight: 500, letterSpacing: 0.3 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color || '#1a1a2e', letterSpacing: -0.5 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 6 }}>{sub}</div>}
    </Card>
  );
}

function Badge({ text, color }) {
  const colors = {
    green: { bg: 'rgba(16,185,129,0.08)', text: '#10b981' },
    red: { bg: 'rgba(239,68,68,0.08)', text: '#ef4444' },
    yellow: { bg: 'rgba(245,158,11,0.08)', text: '#f59e0b' },
    blue: { bg: 'rgba(59,130,246,0.08)', text: '#3b82f6' },
    purple: { bg: 'rgba(99,102,241,0.06)', text: '#6366f1' },
  };
  const c = colors[color] || colors.blue;
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 8,
      fontSize: 11, fontWeight: 600, background: c.bg, color: c.text
    }}>{text}</span>
  );
}

function SectionTitle({ children, action }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, color: '#1a1a2e' }}>{children}</h3>
      {action}
    </div>
  );
}

function Toggle({ on, set }) {
  return (
    <button onClick={() => set(!on)} style={{
      width: 48, height: 26, borderRadius: 13, border: 'none', cursor: 'pointer',
      position: 'relative', background: on ? '#6366f1' : '#cbd5e1', transition: 'background 0.2s',
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

function InputField({ value, onChange, placeholder, type }) {
  return (
    <input
      value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} type={type || 'text'}
      style={{
        width: '100%', padding: '9px 12px', borderRadius: 10,
        border: '1px solid #e2e8f0', background: '#f8fafc', color: '#1a1a2e',
        fontSize: 12, outline: 'none', transition: 'border-color 0.2s'
      }}
    />
  );
}

function EmptyState({ text, small }) {
  return <div style={{ textAlign: 'center', padding: small ? 20 : 48, color: '#94a3b8', fontSize: 13 }}>{text}</div>;
}

function LoadingState() {
  return <div style={{ textAlign: 'center', padding: 24, color: '#94a3b8', fontSize: 13 }}>로딩 중...</div>;
}

function PillButton({ selected, onClick, children, style }) {
  return (
    <button onClick={onClick} style={{
      padding: '8px 16px', borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: 'pointer',
      border: selected ? '2px solid #6366f1' : '1px solid #e2e8f0',
      background: selected ? 'rgba(99,102,241,0.06)' : '#ffffff',
      color: selected ? '#6366f1' : '#64748b', transition: 'all 0.15s', ...style
    }}>{children}</button>
  );
}

function fmt(n) { return (n || 0).toLocaleString('ko-KR'); }
function fmtKRW(n) { return '₩' + fmt(n); }

const CHART_TOOLTIP = {
  contentStyle: {
    background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12,
    boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: 12
  }
};
const CHART_GRID = { strokeDasharray: '3 3', stroke: 'rgba(0,0,0,0.06)' };
const CHART_TICK = { fill: '#94a3b8', fontSize: 11 };

// ═══════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════

export default function Dashboard() {
  const [tab, setTab] = useState('dash');
  const [selectedSite, setSelectedSite] = useState('site-1');
  const { sites } = useSites();
  const { config: savedConfig, saveConfig } = useDashboardConfig();
  const [configLoaded, setConfigLoaded] = useState(false);
  const [showAddSite, setShowAddSite] = useState(false);
  const [newSiteName, setNewSiteName] = useState('');
  const [newSiteDomain, setNewSiteDomain] = useState('');

  const addSite = async () => {
    if (!newSiteName || !newSiteDomain) return;
    const id = 'site-' + (sites.length + 1);
    await supabase.from('sites').insert({
      id, name: newSiteName, domain: newSiteDomain,
      wp_url: '', niche: 'general', status: 'active', daily_target: 5,
      config: {}
    });
    setNewSiteName(''); setNewSiteDomain('');
    setShowAddSite(false); setSelectedSite(id);
  };

  const deleteSite = async (id) => {
    if (sites.length <= 1) return;
    await supabase.from('sites').delete().eq('id', id);
    setSelectedSite(sites.find(s => s.id !== id)?.id || 'site-1');
  };

  // Niche
  const [selNiches, setSelNiches] = useState(['ai-tools']);
  const toggleNiche = useCallback(slug => {
    setSelNiches(p => p.includes(slug) ? p.filter(x => x !== slug) : [...p, slug]);
  }, []);

  // Schedule
  const [tz, setTz] = useState('KST');
  const [preset, setPreset] = useState('mwf');
  const [selDays, setSelDays] = useState([0, 2, 4]);
  const [selTimes, setSelTimes] = useState(['08:00']);
  const [postsPerRun, setPostsPerRun] = useState(1);
  const toggleDay = d => { setSelDays(p => p.includes(d) ? p.filter(x => x !== d) : [...p, d]); setPreset('custom'); };
  const toggleTime = t => { setSelTimes(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t]); setPreset('custom'); };
  const applyPreset = p => { setPreset(p.id); setSelDays(p.days); setSelTimes(p.times); };

  // Monetize
  const [affKeys, setAffKeys] = useState({});
  const setAffKey = (id, v) => setAffKeys(p => ({ ...p, [id]: v }));
  const [saas, setSaas] = useState(INIT_SAAS);
  const updateSaas = (i, f, v) => { const n = [...saas]; n[i] = { ...n[i], [f]: v }; setSaas(n); };
  const addSaas = () => setSaas([...saas, { name: '', cat: '', comm: '', url: '' }]);
  const rmSaas = i => setSaas(saas.filter((_, j) => j !== i));

  // API
  const [apiKeys, setApiKeys] = useState({});
  const setApi = (id, v) => setApiKeys(p => ({ ...p, [id]: v }));
  const [snsOn, setSnsOn] = useState({});
  const toggleSns = id => setSnsOn(p => ({ ...p, [id]: !p[id] }));

  // AdSense
  const [adChecks, setAdChecks] = useState({});
  const toggleAd = id => setAdChecks(p => ({ ...p, [id]: !p[id] }));

  // Language & Mode
  const [lang, setLang] = useState('ko');
  const [autoMode, setAutoMode] = useState(true);

  // Computed
  const adDone = Object.values(adChecks).filter(Boolean).length;
  const adPct = Math.round(adDone / ADSENSE_ITEMS.length * 100);
  const connectedAff = Object.values(affKeys).filter(Boolean).length + saas.filter(s => s.url).length;
  const connectedApi = Object.values(apiKeys).filter(Boolean).length;
  const snsCount = Object.values(snsOn).filter(Boolean).length;

  // Supabase에서 저장된 설정 로드 (최초 1회)
  useEffect(() => {
    if (savedConfig && !configLoaded) {
      if (savedConfig.selNiches) setSelNiches(savedConfig.selNiches);
      if (savedConfig.tz) setTz(savedConfig.tz);
      if (savedConfig.preset) setPreset(savedConfig.preset);
      if (savedConfig.selDays) setSelDays(savedConfig.selDays);
      if (savedConfig.selTimes) setSelTimes(savedConfig.selTimes);
      if (savedConfig.postsPerRun) setPostsPerRun(savedConfig.postsPerRun);
      if (savedConfig.affKeys) setAffKeys(savedConfig.affKeys);
      if (savedConfig.adChecks) setAdChecks(savedConfig.adChecks);
      if (savedConfig.lang) setLang(savedConfig.lang);
      if (savedConfig.autoMode !== undefined) setAutoMode(savedConfig.autoMode);
      if (savedConfig.snsOn) setSnsOn(savedConfig.snsOn);
      if (savedConfig.saas) setSaas(savedConfig.saas);
      setConfigLoaded(true);
    }
  }, [savedConfig, configLoaded]);

  // 설정 변경 시 Supabase에 자동 저장 (디바운스)
  useEffect(() => {
    if (!configLoaded) return;
    const timer = setTimeout(() => {
      saveConfig({
        selNiches, tz, preset, selDays, selTimes, postsPerRun,
        affKeys, adChecks, lang, autoMode, snsOn, saas
      });
    }, 1000);
    return () => clearTimeout(timer);
  }, [selNiches, tz, preset, selDays, selTimes, postsPerRun, affKeys, adChecks, lang, autoMode, snsOn, saas, configLoaded, saveConfig]);

  if (!isConfigured) return <SetupGuide />;

  const sharedProps = {
    siteId: selectedSite, selNiches, toggleNiche, tz, setTz, preset, setPreset,
    selDays, selTimes, postsPerRun, setPostsPerRun, toggleDay, toggleTime, applyPreset,
    affKeys, setAffKey, saas, updateSaas, addSaas, rmSaas,
    apiKeys, setApi, snsOn, toggleSns, adChecks, toggleAd,
    lang, setLang, autoMode, setAutoMode,
    adPct, connectedAff, connectedApi, snsCount, sites, savedConfig,
  };

  return (
    <div style={{ minHeight: '100vh', background: '#FAFBFC' }}>
      {/* ── Header ── */}
      <header style={{
        background: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 50%, #f0f9ff 100%)',
        borderBottom: '1px solid rgba(0,0,0,0.06)', padding: '20px 24px 0'
      }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 900, letterSpacing: -0.5, color: '#1a1a2e' }}>
                <span style={{ color: '#6366f1' }}>Clone Factory</span>{' '}
                <span style={{ fontWeight: 400, color: '#4a5568' }}>v4.0</span>
              </h1>
              <p style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                WP 자동 블로그 수익화 대시보드 · {sites.length}개 사이트
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <Badge text={autoMode ? 'AUTO' : 'MANUAL'} color={autoMode ? 'green' : 'yellow'} />
                <Badge text={`${selNiches.length}개 니치`} color="purple" />
                <Badge text={`${connectedAff}개 수익화`} color="green" />
                <Badge text={lang.toUpperCase()} color="blue" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <select
                  value={selectedSite} onChange={e => setSelectedSite(e.target.value)}
                  style={{
                    background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
                    padding: '8px 14px', color: '#1a1a2e', fontSize: 12, fontWeight: 500,
                    cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.04)'
                  }}
                >
                  {sites.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.status === 'paused' ? '(중단)' : ''}
                    </option>
                  ))}
                </select>
                <button onClick={() => setShowAddSite(!showAddSite)} style={{
                  width: 32, height: 32, borderRadius: 8, border: '1px solid #e2e8f0',
                  background: showAddSite ? '#6366f1' : '#fff', color: showAddSite ? '#fff' : '#6366f1',
                  fontSize: 16, fontWeight: 700, cursor: 'pointer', display: 'flex',
                  alignItems: 'center', justifyContent: 'center'
                }}>+</button>
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'rgba(16,185,129,0.08)', padding: '5px 12px', borderRadius: 20
              }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981', animation: 'pulse 2s infinite' }} />
                <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>Realtime</span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 2, overflowX: 'auto' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: '9px 16px', border: 'none', borderRadius: '10px 10px 0 0',
                cursor: 'pointer', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
                display: 'flex', alignItems: 'center', gap: 5,
                background: tab === t.id ? '#ffffff' : 'transparent',
                color: tab === t.id ? '#6366f1' : '#94a3b8',
                boxShadow: tab === t.id ? '0 -1px 4px rgba(0,0,0,0.03)' : 'none',
                transition: 'all 0.15s'
              }}>
                <span style={{ fontSize: 13 }}>{t.icon}</span> {t.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── Content ── */}
      {/* 사이트 추가 패널 */}
      {showAddSite && (
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '12px 24px 0' }}>
          <Card style={{ display: 'flex', alignItems: 'flex-end', gap: 12, padding: 16 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>사이트 이름</label>
              <InputField value={newSiteName} onChange={setNewSiteName} placeholder="예: 내 블로그" />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>도메인</label>
              <InputField value={newSiteDomain} onChange={setNewSiteDomain} placeholder="예: myblog.com" />
            </div>
            <button onClick={addSite} disabled={!newSiteName || !newSiteDomain} style={{
              padding: '9px 20px', borderRadius: 10, border: 'none', background: '#6366f1',
              color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              opacity: (!newSiteName || !newSiteDomain) ? 0.4 : 1
            }}>추가</button>
            {sites.length > 1 && (
              <button onClick={() => { if (confirm(`"${sites.find(s=>s.id===selectedSite)?.name}" 사이트를 삭제하시겠습니까?`)) deleteSite(selectedSite); }} style={{
                padding: '9px 16px', borderRadius: 10, border: '1px solid rgba(239,68,68,0.3)',
                background: 'rgba(239,68,68,0.04)', color: '#ef4444', fontSize: 12, fontWeight: 700, cursor: 'pointer'
              }}>현재 사이트 삭제</button>
            )}
          </Card>
        </div>
      )}

      <main style={{ maxWidth: 1280, margin: '0 auto', padding: '24px 24px 60px' }}>
        {tab === 'dash' && <DashTab {...sharedProps} />}
        {tab === 'logs' && <PostsTab siteId={selectedSite} />}
        {tab === 'niche' && <NicheTab {...sharedProps} />}
        {tab === 'schedule' && <ScheduleTab {...sharedProps} />}
        {tab === 'money' && <MoneyTab {...sharedProps} />}
        {tab === 'api' && <ApiTab {...sharedProps} />}
        {tab === 'adsense' && <AdSenseTab {...sharedProps} />}
        {tab === 'revenue' && <RevenueTab siteId={selectedSite} />}
        {tab === 'costs' && <CostsTab siteId={selectedSite} />}
        {tab === 'alerts' && <AlertsTab siteId={selectedSite} />}
        {tab === 'settings' && <SettingsTab siteId={selectedSite} sites={sites} />}
        {tab === 'admin' && <AdminTab {...sharedProps} />}
      </main>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 1: DASHBOARD
// ═══════════════════════════════════════════

function DashTab({ siteId, selNiches, connectedAff, connectedApi, adPct, selDays, selTimes, postsPerRun, lang, setLang, autoMode, snsOn }) {
  const { stats } = useTodayStats(siteId);
  const { total: rev } = useMonthlyRevenue(siteId);
  const { costs } = useMonthlyCosts(siteId);
  const { trend } = usePublishTrend(siteId, 7);
  const { alerts } = useAlerts(siteId);
  const unread = alerts.filter(a => !a.is_read).length;
  const snsCount = Object.values(snsOn).filter(Boolean).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
        {[
          { l: '니치', v: selNiches.length, u: '개', c: '#6366f1', i: '◉' },
          { l: '수익화', v: connectedAff, u: '개', c: '#10b981', i: '↗' },
          { l: 'API', v: connectedApi, u: '개', c: '#3b82f6', i: '⊞' },
          { l: 'AdSense', v: `${adPct}%`, u: '', c: adPct >= 100 ? '#10b981' : '#f59e0b', i: '▣' },
          { l: '스케줄', v: `${selDays.length}일×${selTimes.length}`, u: '회', c: '#8b5cf6', i: '◷' },
        ].map((s, i) => (
          <Card key={i} style={{ padding: 16 }}>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, marginBottom: 4 }}>{s.l}</div>
            <div style={{ fontSize: 26, fontWeight: 900, color: s.c }}>
              {s.v}<span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>{s.u}</span>
            </div>
          </Card>
        ))}
      </div>

      {/* Pipeline */}
      <Card>
        <SectionTitle>파이프라인</SectionTitle>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          {[
            { l: '니치', v: `${selNiches.length}개 복합`, c: '#6366f1' },
            { l: '키워드', v: autoMode ? '3소스 자동' : '수동', c: '#8b5cf6' },
            { l: 'AI', v: '5-Layer 유니크', c: '#a78bfa' },
            { l: '이미지', v: 'Pexels+Pixabay', c: '#3b82f6' },
            { l: '품질', v: '70점+', c: '#10b981' },
            { l: '수익화', v: connectedAff > 0 ? `${connectedAff}개 연결` : '미설정', c: connectedAff > 0 ? '#f59e0b' : '#ef4444' },
            { l: 'WP발행', v: 'AdSense최적화', c: '#10b981' },
            { l: 'SNS', v: snsCount > 0 ? '자동공유' : '미설정', c: '#3b82f6' },
          ].map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {i > 0 && <span style={{ color: '#d1d5db', fontWeight: 700, fontSize: 12 }}>→</span>}
              <div style={{
                background: `${s.c}0a`, border: `1px solid ${s.c}1a`, borderRadius: 10, padding: '6px 12px'
              }}>
                <div style={{ fontSize: 9, color: '#94a3b8', fontWeight: 600 }}>{s.l}</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: s.c }}>{s.v}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Chart + Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <Card>
          <SectionTitle>7일 발행 추이</SectionTitle>
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={trend} barCategoryGap="20%">
                <CartesianGrid {...CHART_GRID} />
                <XAxis dataKey="date" tick={CHART_TICK} tickFormatter={d => d.slice(5)} />
                <YAxis tick={CHART_TICK} />
                <Tooltip {...CHART_TOOLTIP} />
                <Bar dataKey="published" fill="#6366f1" radius={[6, 6, 0, 0]} name="발행" />
                <Bar dataKey="failed" fill="#ef4444" radius={[6, 6, 0, 0]} name="실패" opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="데이터 수집 중... GitHub Actions 발행 후 자동 반영됩니다." />
          )}
        </Card>

        <Card>
          <SectionTitle action={unread > 0 ? <Badge text={`${unread}건 새 알림`} color="red" /> : null}>알림</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 200, overflowY: 'auto' }}>
            {alerts.slice(0, 5).map(a => (
              <div key={a.id} style={{
                padding: '10px 12px', borderRadius: 10,
                background: a.is_read ? '#f8fafc' : 'rgba(99,102,241,0.06)',
                border: '1px solid rgba(0,0,0,0.06)', fontSize: 12
              }}>
                <div style={{ fontWeight: 600, color: a.severity === 'critical' ? '#ef4444' : '#1a1a2e' }}>{a.title}</div>
                <div style={{ color: '#94a3b8', marginTop: 3 }}>{a.message?.slice(0, 60)}</div>
              </div>
            ))}
            {alerts.length === 0 && <EmptyState text="알림 없음" small />}
          </div>
        </Card>
      </div>

      {/* Supabase KPI */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <StatCard label="오늘 발행" icon="✎" value={`${stats.posts}편`} sub={stats.failures > 0 ? `${stats.failures}건 실패` : '전체 성공'} color="#6366f1" />
        <StatCard label="이번 달 수익" icon="↗" value={fmtKRW(rev.krw)} sub={rev.usd > 0 ? `$${rev.usd.toFixed(2)}` : ''} color="#10b981" />
        <StatCard label="이번 달 비용" icon="◈" value={fmtKRW(costs.total_krw)} color="#f59e0b" />
        <StatCard label="순이익" icon="★" value={fmtKRW(rev.krw - costs.total_krw)} sub={costs.total_krw > 0 ? `ROI ${(((rev.krw - costs.total_krw) / costs.total_krw) * 100).toFixed(0)}%` : ''} color={rev.krw - costs.total_krw >= 0 ? '#10b981' : '#ef4444'} />
      </div>

      {/* Selected Niches + Lang */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <Card>
          <SectionTitle>선택된 니치</SectionTitle>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {selNiches.map(slug => {
              const n = NICHE_CATS.flatMap(c => c.items).find(x => x.slug === slug);
              return n ? <Badge key={slug} text={`${n.icon} ${n.ko}`} color="purple" /> : null;
            })}
            {selNiches.length === 0 && <span style={{ fontSize: 12, color: '#94a3b8' }}>니치를 선택하세요</span>}
          </div>
        </Card>
        <Card>
          <SectionTitle>언어</SectionTitle>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { id: 'ko', label: '🇰🇷 한국어' },
              { id: 'en', label: '🇺🇸 English' },
              { id: 'both', label: '🌐 둘 다' },
            ].map(l => (
              <PillButton key={l.id} selected={lang === l.id} onClick={() => setLang(l.id)} style={{ flex: 1 }}>
                {l.label}
              </PillButton>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 2: NICHE
// ═══════════════════════════════════════════

function NicheTab({ selNiches, toggleNiche, siteId }) {
  const [count, setCount] = useState(1);
  const [dryRun, setDryRun] = useState(false);
  const [pubStatus, setPubStatus] = useState('idle');
  const [pubMsg, setPubMsg] = useState('');
  const { posts, loading: postsLoading } = useRecentPosts(siteId, 5);

  const handlePublish = async () => {
    setPubStatus('loading');
    setPubMsg('');
    try {
      const nicheParam = selNiches.length === 1 ? selNiches[0] : '';
      const resp = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count, pipeline: 'autoblog', dry_run: dryRun, niche: nicheParam }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setPubStatus('success');
        setPubMsg(`${dryRun ? '[테스트] ' : ''}발행 요청 완료! GitHub Actions에서 ${count}편 처리 중...`);
      } else {
        setPubStatus('error');
        setPubMsg(data.error || '요청 실패');
      }
    } catch (err) {
      setPubStatus('error');
      setPubMsg('네트워크 오류: ' + err.message);
    }
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>니치 선택 (복합 가능)</h2>
        <p style={{ fontSize: 13, color: '#94a3b8' }}>여러 니치를 동시에 선택할 수 있습니다. 선택한 모든 니치에서 키워드가 자동 생성됩니다.</p>
      </div>

      {NICHE_CATS.map(cat => (
        <Card key={cat.id}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 12 }}>{cat.icon} {cat.label}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
            {cat.items.map(n => {
              const sel = selNiches.includes(n.slug);
              return (
                <button key={n.slug} onClick={() => toggleNiche(n.slug)} style={{
                  padding: '12px 10px', borderRadius: 12, cursor: 'pointer', textAlign: 'left',
                  border: sel ? '2px solid #6366f1' : '1px solid #e2e8f0',
                  background: sel ? 'rgba(99,102,241,0.06)' : '#ffffff',
                  transition: 'all 0.15s'
                }}>
                  <div style={{ fontSize: 22 }}>{n.icon}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: sel ? '#6366f1' : '#1a1a2e', marginTop: 6 }}>{n.ko}</div>
                  {n.cpm && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>CPM {n.cpm}</div>}
                </button>
              );
            })}
          </div>
        </Card>
      ))}

      <Card style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.12)' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#6366f1' }}>선택됨: {selNiches.length}개</span>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {selNiches.map(slug => {
            const n = NICHE_CATS.flatMap(c => c.items).find(x => x.slug === slug);
            return n ? <Badge key={slug} text={`${n.icon} ${n.ko}`} color="purple" /> : null;
          })}
        </div>
      </Card>

      {/* 콘텐츠 앵글 & 다양성 설명 */}
      {selNiches.length > 0 && (
        <Card>
          <SectionTitle>콘텐츠 다양성 엔진</SectionTitle>
          <p style={{ fontSize: 12, color: '#4a5568', marginTop: -8, marginBottom: 14 }}>
            선택한 니치에서 아래 요소를 자동 조합하여 매번 고유한 키워드를 AI가 생성합니다.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#6366f1', marginBottom: 6 }}>콘텐츠 앵글 (16종 랜덤)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {['소개/개요', '활용법', '수익화', '비교/대안', '조합 시너지', '월간 Top', '카테고리 순위', '초보 가이드',
                  '고급 활용', '무료vs유료', '트렌드', '사례/후기', '문제해결', '비용절감', '자동화', '업데이트'].map(a => (
                  <span key={a} style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: '#f1f5f9', color: '#4a5568' }}>{a}</span>
                ))}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#6366f1', marginBottom: 6 }}>콘텐츠 포맷 (8종 랜덤)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {['리스트형', '비교표', '스텝가이드', '사례연구', 'Q&A형', '체크리스트', '타임라인', '데이터중심'].map(f => (
                  <span key={f} style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: '#f1f5f9', color: '#4a5568' }}>{f}</span>
                ))}
              </div>
            </div>
          </div>
          <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#10b981' }}>다양성 보장 알고리즘</div>
            <div style={{ fontSize: 11, color: '#4a5568', marginTop: 4 }}>
              앵글(16) × 포맷(8) × 타겟독자(12) × 니치 도메인 키워드 = <strong>수천 가지 조합</strong>
              <br />+ 사이트별 고유 시드 + 발행 이력 중복 체크 → 20명이 같은 니치를 선택해도 동일 글 불가
            </div>
          </div>
        </Card>
      )}

      {/* ── 발행 섹션 ── */}
      <Card>
        <SectionTitle>발행</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8, fontWeight: 500 }}>발행 편수</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[1, 3, 5, 10].map(n => (
                <button key={n} onClick={() => setCount(n)} style={{
                  padding: '10px 20px', borderRadius: 10, cursor: 'pointer', fontSize: 14, fontWeight: 700,
                  border: count === n ? '2px solid #6366f1' : '2px solid #e2e8f0',
                  background: count === n ? 'rgba(99,102,241,0.06)' : '#fff',
                  color: count === n ? '#6366f1' : '#64748b',
                  transition: 'all 0.15s',
                }}>{n}편</button>
              ))}
            </div>
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', borderRadius: 10, background: '#f8fafc'
          }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a2e' }}>테스트 모드</span>
              <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 8 }}>실제 발행 없이 엔진만 실행</span>
            </div>
            <button onClick={() => setDryRun(!dryRun)} style={{
              width: 48, height: 26, borderRadius: 13, border: 'none',
              background: dryRun ? '#6366f1' : '#e2e8f0',
              cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
            }}>
              <div style={{
                width: 20, height: 20, borderRadius: '50%', background: '#fff',
                position: 'absolute', top: 3, left: dryRun ? 25 : 3,
                transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              }} />
            </button>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={handlePublish} disabled={pubStatus === 'loading' || selNiches.length === 0} style={{
              flex: 1, padding: '14px 24px', borderRadius: 12, border: 'none', cursor: pubStatus === 'loading' || selNiches.length === 0 ? 'not-allowed' : 'pointer',
              background: selNiches.length === 0 ? '#e2e8f0' : dryRun ? 'linear-gradient(135deg, #f59e0b, #d97706)' : 'linear-gradient(135deg, #6366f1, #818cf8)',
              color: selNiches.length === 0 ? '#94a3b8' : '#fff',
              fontSize: 15, fontWeight: 700, transition: 'opacity 0.15s',
              opacity: pubStatus === 'loading' ? 0.7 : 1,
              boxShadow: selNiches.length > 0 ? '0 4px 12px rgba(99,102,241,0.3)' : 'none',
            }}>
              {selNiches.length === 0 ? '니치를 먼저 선택하세요'
                : pubStatus === 'loading' ? '요청 전송 중...'
                : dryRun ? `테스트 발행 (${count}편)` : `발행하기 (${count}편)`}
            </button>
          </div>

          {pubMsg && (
            <div style={{
              padding: '12px 16px', borderRadius: 10, fontSize: 13, fontWeight: 500,
              background: pubStatus === 'success' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
              color: pubStatus === 'success' ? '#059669' : '#dc2626',
            }}>{pubMsg}</div>
          )}

          {selNiches.length > 0 && (
            <div style={{ padding: '10px 14px', borderRadius: 8, background: '#f8fafc', fontSize: 12, color: '#94a3b8', lineHeight: 1.7 }}>
              선택된 니치({selNiches.length}개)에서 자동 키워드 생성 후 발행합니다.
              진행 상황은 발행 로그 탭에서 실시간 확인 가능.
            </div>
          )}
        </div>
      </Card>

      {/* ── 최근 발행 ── */}
      <Card>
        <SectionTitle>최근 발행</SectionTitle>
        {postsLoading ? <LoadingState /> : posts.length === 0 ? (
          <EmptyState text="아직 발행된 글이 없습니다" small />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {posts.map(p => (
              <div key={p.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px', borderRadius: 10, background: '#f8fafc'
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 500, color: '#1a1a2e',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                  }}>{p.title}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                    {p.keyword} · {new Date(p.published_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}
                  </div>
                </div>
                <Badge text={p.status === 'published' ? '발행' : '실패'} color={p.status === 'published' ? 'green' : 'red'} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 3: SCHEDULE
// ═══════════════════════════════════════════

function ScheduleTab({ tz, setTz, preset, applyPreset, selDays, selTimes, postsPerRun, setPostsPerRun, toggleDay, toggleTime }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>발행 스케줄</h2>
        <p style={{ fontSize: 13, color: '#94a3b8' }}>30분 단위, 한국/미국 시간대, 요일+시간+횟수 조합으로 설정합니다.</p>
      </div>

      {/* Timezone */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a2e', marginBottom: 10 }}>타임존</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TZ_LIST.map(t => (
            <PillButton key={t.id} selected={tz === t.id} onClick={() => setTz(t.id)}>
              {t.label} ({t.off})
            </PillButton>
          ))}
        </div>
      </Card>

      {/* Presets */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a2e', marginBottom: 10 }}>빠른 설정</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {PRESETS.map(p => (
            <PillButton key={p.id} selected={preset === p.id} onClick={() => applyPreset(p)}>
              {p.label}
            </PillButton>
          ))}
        </div>
      </Card>

      {/* Days */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a2e', marginBottom: 10 }}>요일 선택</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {DAYS.map((d, i) => (
            <button key={i} onClick={() => toggleDay(i)} style={{
              width: 44, height: 44, borderRadius: 12, fontSize: 14, fontWeight: 700, cursor: 'pointer',
              border: selDays.includes(i) ? '2px solid #6366f1' : '1px solid #e2e8f0',
              background: selDays.includes(i) ? 'rgba(99,102,241,0.08)' : '#ffffff',
              color: selDays.includes(i) ? '#6366f1' : '#94a3b8',
              transition: 'all 0.15s'
            }}>{d}</button>
          ))}
        </div>
      </Card>

      {/* Times */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a2e', marginBottom: 10 }}>시간 선택 (30분 단위, 복수 선택)</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 4, maxHeight: 220, overflowY: 'auto' }}>
          {TIMES.map(t => (
            <button key={t} onClick={() => toggleTime(t)} style={{
              padding: '6px 2px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              border: selTimes.includes(t) ? '2px solid #6366f1' : '1px solid #f1f5f9',
              background: selTimes.includes(t) ? 'rgba(99,102,241,0.08)' : '#ffffff',
              color: selTimes.includes(t) ? '#6366f1' : '#94a3b8',
              transition: 'all 0.15s'
            }}>{t}</button>
          ))}
        </div>
      </Card>

      {/* Posts per run */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a2e', marginBottom: 10 }}>1회 실행당 발행 수</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[1, 2, 3, 5, 10].map(n => (
            <PillButton key={n} selected={postsPerRun === n} onClick={() => setPostsPerRun(n)}>
              {n}편
            </PillButton>
          ))}
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 10 }}>
          주간 예상: {selDays.length}일 × {selTimes.length}회 × {postsPerRun}편 ={' '}
          <strong style={{ color: '#6366f1' }}>{selDays.length * selTimes.length * postsPerRun}편/주</strong>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 4: MONETIZE
// ═══════════════════════════════════════════

const MONEY_CATS = [
  { id: 'kr', label: '한국', icon: '●' },
  { id: 'global', label: '글로벌', icon: '◎' },
  { id: 'all', label: 'SaaS 전체', icon: '★' },
  { id: 'AI글쓰기', label: 'AI 글쓰기', icon: '✎' },
  { id: 'AI영상', label: 'AI 영상', icon: '▶' },
  { id: 'AI음성', label: 'AI 음성', icon: '♪' },
  { id: 'SEO', label: 'SEO', icon: '↗' },
  { id: '이메일', label: '이메일', icon: '✉' },
  { id: 'CRM', label: 'CRM', icon: '⊞' },
  { id: '호스팅', label: '호스팅', icon: '⊡' },
  { id: '클라우드', label: '클라우드', icon: '☁' },
  { id: '디자인', label: '디자인', icon: '◆' },
  { id: '생산성', label: '생산성', icon: '☰' },
  { id: 'VPN', label: 'VPN', icon: '⊙' },
  { id: '교육', label: '교육', icon: '⊕' },
  { id: '금융', label: '금융', icon: '◈' },
  { id: 'SNS관리', label: 'SNS', icon: '◉' },
  { id: 'SaaS딜', label: 'SaaS딜', icon: '◇' },
];

function MoneyTab({ affKeys, setAffKey, saas, updateSaas, addSaas, rmSaas }) {
  const [moneyTab, setMoneyTab] = useState('kr');

  // 통계
  const krOn = AFF_KR.filter(a => affKeys[a.id]).length;
  const glOn = AFF_GLOBAL.filter(a => affKeys[a.id]).length;
  const saasOn = saas.filter(s => s.url).length;
  const catCounts = {};
  saas.forEach(s => {
    if (!catCounts[s.cat]) catCounts[s.cat] = { total: 0, on: 0 };
    catCounts[s.cat].total++;
    if (s.url) catCounts[s.cat].on++;
  });

  const isSaasTab = moneyTab !== 'kr' && moneyTab !== 'global';
  const filtered = moneyTab === 'all' ? saas : saas.filter(s => s.cat === moneyTab);

  // 어필리에이트 행 렌더러
  const AffRow = ({ name, comm, value, onChange, placeholder }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ width: 130, fontSize: 12, fontWeight: 600, color: '#1a1a2e', flexShrink: 0 }}>{name}</div>
      <div style={{ width: 110, fontSize: 10, color: '#10b981', flexShrink: 0 }}>{comm}</div>
      <div style={{ flex: 1 }}>
        <InputField value={value} onChange={onChange} placeholder={placeholder} />
      </div>
      <Badge text={value ? 'ON' : 'OFF'} color={value ? 'green' : 'yellow'} />
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>수익화 설정</h2>
          <p style={{ fontSize: 13, color: '#94a3b8' }}>
            총 {krOn + glOn + saasOn}개 연결 — 한국 {krOn}/{AFF_KR.length} · 글로벌 {glOn}/{AFF_GLOBAL.length} · SaaS {saasOn}/{saas.length}
          </p>
        </div>
        {isSaasTab && (
          <button onClick={addSaas} style={{
            padding: '6px 14px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.3)',
            background: 'rgba(99,102,241,0.04)', color: '#6366f1', fontSize: 11, fontWeight: 700, cursor: 'pointer'
          }}>+ 추가</button>
        )}
      </div>

      {/* 통합 탭 */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {MONEY_CATS.map(c => {
          const isActive = moneyTab === c.id;
          let cnt = null;
          if (c.id === 'kr') cnt = { on: krOn, total: AFF_KR.length };
          else if (c.id === 'global') cnt = { on: glOn, total: AFF_GLOBAL.length };
          else if (c.id === 'all') cnt = { on: saasOn, total: saas.length };
          else cnt = catCounts[c.id];
          if (!cnt && c.id !== 'kr' && c.id !== 'global' && c.id !== 'all') return null;
          return (
            <button key={c.id} onClick={() => setMoneyTab(c.id)} style={{
              padding: '6px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              border: isActive ? '1.5px solid #6366f1' : '1px solid #e2e8f0',
              background: isActive ? 'rgba(99,102,241,0.06)' : '#fff',
              color: isActive ? '#6366f1' : '#64748b',
              display: 'flex', alignItems: 'center', gap: 4, transition: 'all 0.15s'
            }}>
              <span style={{ fontSize: 11 }}>{c.icon}</span>
              {c.label}
              {cnt && <span style={{
                fontSize: 9, padding: '1px 5px', borderRadius: 4, marginLeft: 2,
                background: cnt.on > 0 ? 'rgba(16,185,129,0.1)' : 'rgba(0,0,0,0.04)',
                color: cnt.on > 0 ? '#10b981' : '#94a3b8'
              }}>{cnt.on}/{cnt.total}</span>}
            </button>
          );
        })}
      </div>

      {/* 한국 어필리에이트 */}
      {moneyTab === 'kr' && (
        <Card>
          {AFF_KR.map(a => (
            <AffRow key={a.id} name={a.name} comm={a.comm}
              value={affKeys[a.id] || ''} onChange={v => setAffKey(a.id, v)}
              placeholder={a.id === 'coupang' ? 'Access Key' : '레퍼럴 URL 또는 ID'} />
          ))}
        </Card>
      )}

      {/* 글로벌 어필리에이트 */}
      {moneyTab === 'global' && (
        <Card>
          {AFF_GLOBAL.map(a => (
            <AffRow key={a.id} name={a.name} comm={a.comm}
              value={affKeys[a.id] || ''} onChange={v => setAffKey(a.id, v)}
              placeholder="트래킹 ID 또는 레퍼럴 URL" />
          ))}
        </Card>
      )}

      {/* SaaS 레퍼럴 */}
      {isSaasTab && (
        <Card>
          {filtered.map(s => {
            const realIdx = saas.indexOf(s);
            return (
              <div key={realIdx} style={{
                display: 'grid', gridTemplateColumns: '130px 70px 100px 1fr 32px',
                gap: 8, alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f1f5f9'
              }}>
                <input value={s.name} onChange={e => updateSaas(realIdx, 'name', e.target.value)} placeholder="서비스명"
                  style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#f8fafc', color: '#1a1a2e', fontSize: 11, outline: 'none' }} />
                <select value={s.cat} onChange={e => updateSaas(realIdx, 'cat', e.target.value)}
                  style={{ padding: '5px 4px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#f8fafc', color: '#64748b', fontSize: 9, outline: 'none', cursor: 'pointer' }}>
                  {MONEY_CATS.filter(c => c.id !== 'kr' && c.id !== 'global' && c.id !== 'all').map(c => (
                    <option key={c.id} value={c.id}>{c.label}</option>
                  ))}
                </select>
                <span style={{ fontSize: 10, color: '#10b981', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.comm}</span>
                <input value={s.url} onChange={e => updateSaas(realIdx, 'url', e.target.value)} placeholder="레퍼럴 URL"
                  style={{ padding: '7px 10px', borderRadius: 8, border: s.url ? '1px solid rgba(16,185,129,0.3)' : '1px solid #e2e8f0', background: s.url ? 'rgba(16,185,129,0.03)' : '#f8fafc', color: '#1a1a2e', fontSize: 11, outline: 'none' }} />
                <button onClick={() => rmSaas(realIdx)} style={{
                  width: 28, height: 28, borderRadius: 8, border: 'none',
                  background: 'rgba(239,68,68,0.06)', color: '#ef4444', fontSize: 14, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>×</button>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: 20, color: '#94a3b8', fontSize: 12 }}>
              이 카테고리에 등록된 서비스가 없습니다.
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 5: API / INTEGRATION
// ═══════════════════════════════════════════

function ApiTab({ apiKeys, setApi, snsOn, toggleSns, savedConfig }) {
  const apiStatus = savedConfig?.api_status || {};
  const lastChecked = apiStatus.last_checked ? new Date(apiStatus.last_checked).toLocaleString('ko-KR') : '확인 안됨';

  const STATUS_MAP = [
    { key: 'wp', label: 'WordPress', desc: 'WP_URL + WP_USERNAME + WP_APP_PASSWORD' },
    { key: 'grok', label: 'Grok', desc: 'GROK_API_KEY' },
    { key: 'gemini', label: 'Gemini', desc: 'GEMINI_API_KEY' },
    { key: 'claude', label: 'Claude', desc: 'CLAUDE_API_KEY' },
    { key: 'deepseek', label: 'DeepSeek', desc: 'DEEPSEEK_API_KEY' },
    { key: 'pexels', label: 'Pexels', desc: 'PEXELS_API_KEY' },
    { key: 'pixabay', label: 'Pixabay', desc: 'PIXABAY_API_KEY' },
    { key: 'unsplash', label: 'Unsplash', desc: 'UNSPLASH_ACCESS_KEY' },
    { key: 'supabase', label: 'Supabase', desc: 'SUPABASE_URL + SUPABASE_KEY' },
    { key: 'naver_cafe', label: '네이버 카페', desc: 'NAVER_CLIENT_ID + SECRET + REFRESH_TOKEN + CLUBID + MENUID' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 실제 연결 상태 (GitHub Secrets/Vercel 기준) */}
      {Object.keys(apiStatus).length > 0 && (
        <Card style={{ border: '1px solid rgba(99,102,241,0.15)', background: 'rgba(99,102,241,0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e' }}>서버 API 연결 상태</div>
            <span style={{ fontSize: 10, color: '#94a3b8' }}>마지막 확인: {lastChecked}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
            {STATUS_MAP.map(s => {
              const ok = apiStatus[s.key];
              return (
                <div key={s.key} style={{
                  padding: '10px 8px', borderRadius: 10, textAlign: 'center',
                  background: ok ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.04)',
                  border: `1px solid ${ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.1)'}`
                }}>
                  <div style={{ fontSize: 18, marginBottom: 4 }}>{ok ? '●' : '○'}</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: ok ? '#10b981' : '#ef4444' }}>{s.label}</div>
                  <div style={{ fontSize: 8, color: '#94a3b8', marginTop: 2 }}>{s.desc}</div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 10 }}>
            GitHub Secrets 또는 Vercel 환경변수에 입력된 키를 기준으로 엔진 실행 시 자동 감지됩니다.
          </div>
        </Card>
      )}

      <div>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>API 키 / 연동 설정</h2>
        <p style={{ fontSize: 13, color: '#94a3b8' }}>AI 모델, 이미지 API, SNS 자동 공유를 설정합니다.</p>
      </div>

      {/* AI Models */}
      <Card>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 12 }}>AI 모델 (글쓰기)</div>
        {AI_MODELS_API.map(m => (
          <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
            <div style={{ width: 140, fontSize: 12, fontWeight: 600, color: '#1a1a2e', flexShrink: 0 }}>{m.name}</div>
            <div style={{ width: 90, fontSize: 10, color: '#94a3b8', flexShrink: 0 }}>{m.cost}</div>
            <div style={{ flex: 1 }}>
              <InputField value={apiKeys[m.id] || ''} onChange={v => setApi(m.id, v)} placeholder="API Key" type="password" />
            </div>
            <Badge text={apiKeys[m.id] ? '연결' : '미등록'} color={apiKeys[m.id] ? 'green' : 'yellow'} />
            <a href={`https://${m.signup}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 10, color: '#6366f1', textDecoration: 'none', fontWeight: 600, flexShrink: 0 }}>발급</a>
          </div>
        ))}
      </Card>

      {/* Image APIs */}
      <Card>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 12 }}>이미지 API</div>
        {IMG_APIS.map(m => (
          <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
            <div style={{ width: 110, fontSize: 12, fontWeight: 600, color: '#1a1a2e' }}>{m.name}</div>
            <div style={{ width: 90, fontSize: 10, color: '#94a3b8' }}>{m.cost}</div>
            <div style={{ flex: 1 }}>
              <InputField value={apiKeys[m.id] || ''} onChange={v => setApi(m.id, v)} placeholder="API Key" type="password" />
            </div>
            <Badge text={apiKeys[m.id] ? '연결' : '미등록'} color={apiKeys[m.id] ? 'green' : 'yellow'} />
            <a href={`https://${m.signup}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 10, color: '#6366f1', textDecoration: 'none', fontWeight: 600 }}>발급</a>
          </div>
        ))}
      </Card>

      {/* SNS */}
      <Card>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 6 }}>SNS 자동 공유</div>
        <p style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>글 발행 후 자동으로 SNS에 공유합니다.</p>
        {SNS_LIST.map(s => (
          <div key={s.id} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 0', borderBottom: '1px solid #f1f5f9'
          }}>
            <span style={{ fontSize: 13, color: '#1a1a2e', fontWeight: 500 }}>{s.name}</span>
            <Toggle on={!!snsOn[s.id]} set={() => toggleSns(s.id)} />
          </div>
        ))}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 6: ADSENSE
// ═══════════════════════════════════════════

function AdSenseTab({ adChecks, toggleAd, adPct }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e', marginBottom: 4 }}>AdSense 승인 준비</h2>
        <p style={{ fontSize: 13, color: '#94a3b8' }}>모든 필수 항목 충족 시 Google AdSense에 신청할 수 있습니다.</p>
      </div>

      {/* Progress */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e' }}>승인 준비율</span>
          <span style={{ fontSize: 32, fontWeight: 900, color: adPct >= 100 ? '#10b981' : adPct >= 70 ? '#f59e0b' : '#ef4444' }}>{adPct}%</span>
        </div>
        <div style={{ width: '100%', height: 10, background: '#f1f5f9', borderRadius: 5, overflow: 'hidden' }}>
          <div style={{
            width: `${adPct}%`, height: '100%', borderRadius: 5,
            background: adPct >= 100 ? '#10b981' : adPct >= 70 ? '#f59e0b' : '#ef4444',
            transition: 'width 0.5s'
          }} />
        </div>
        {adPct >= 100 && (
          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <a href="https://www.google.com/adsense/start/" target="_blank" rel="noopener noreferrer" style={{
              display: 'inline-block', padding: '12px 32px', borderRadius: 12,
              background: '#10b981', color: '#fff', fontWeight: 700, fontSize: 14, textDecoration: 'none',
              boxShadow: '0 2px 8px rgba(16,185,129,0.3)'
            }}>AdSense 신청하기</a>
          </div>
        )}
      </Card>

      {/* Checklist */}
      <Card>
        {ADSENSE_ITEMS.map(item => (
          <div key={item.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 0', borderBottom: '1px solid #f1f5f9'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button onClick={() => toggleAd(item.id)} style={{
                width: 22, height: 22, borderRadius: 6, border: 'none', cursor: 'pointer',
                background: adChecks[item.id] ? '#10b981' : '#e2e8f0',
                color: '#fff', fontSize: 12, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s'
              }}>{adChecks[item.id] ? '✓' : ''}</button>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#1a1a2e' }}>
                  {item.l} {item.c && <span style={{ fontSize: 9, color: '#ef4444', fontWeight: 700 }}>필수</span>}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8' }}>{item.d}</div>
              </div>
            </div>
            <Badge text={adChecks[item.id] ? '완료' : '미완료'} color={adChecks[item.id] ? 'green' : 'yellow'} />
          </div>
        ))}
      </Card>

      {/* Manual */}
      <Card>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 12 }}>신청 매뉴얼</div>
        {['adsense.google.com 접속 + Google 로그인', '사이트 URL 입력', '계정 유형: 개인, 국가: 대한민국',
          '전화번호 인증 (SMS)', 'AdSense 코드를 WP head에 삽입 (Ad Inserter)', '심사 대기 (2~14일)', '승인 후 자동 광고 ON'
        ].map((s, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
            <div style={{
              width: 24, height: 24, borderRadius: 12, background: '#6366f1', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, flexShrink: 0
            }}>{i + 1}</div>
            <span style={{ fontSize: 12, color: '#1a1a2e', lineHeight: '24px' }}>{s}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 7: REVENUE (Supabase)
// ═══════════════════════════════════════════

function RevenueTab({ siteId }) {
  const { revenue, total } = useMonthlyRevenue(siteId);

  const byChannel = {};
  revenue.forEach(r => {
    if (!byChannel[r.channel]) byChannel[r.channel] = 0;
    byChannel[r.channel] += r.revenue_krw || 0;
  });

  const byDate = {};
  revenue.forEach(r => {
    if (!byDate[r.date]) byDate[r.date] = { date: r.date, total: 0 };
    byDate[r.date].total += r.revenue_krw || 0;
  });
  const dailyTrend = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));

  const CHANNEL_COLORS = {
    adsense: '#10b981', coupang_cps: '#3b82f6', tenping_cpa: '#f59e0b',
    stibee: '#ef4444', kmong: '#6366f1'
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <StatCard label="이번 달 총 수익" value={fmtKRW(total.krw)} color="#10b981" icon="↗" />
        {Object.entries(byChannel).map(([ch, v]) => (
          <StatCard key={ch} label={ch.replace('_', ' ').toUpperCase()} value={fmtKRW(v)} color={CHANNEL_COLORS[ch] || '#3b82f6'} />
        ))}
      </div>

      {dailyTrend.length > 0 && (
        <Card>
          <SectionTitle>일별 수익 추이</SectionTitle>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={dailyTrend}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid {...CHART_GRID} />
              <XAxis dataKey="date" tick={CHART_TICK} tickFormatter={d => d.slice(5)} />
              <YAxis tick={CHART_TICK} tickFormatter={v => `₩${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={v => fmtKRW(v)} {...CHART_TOOLTIP} />
              <Area type="monotone" dataKey="total" stroke="#10b981" strokeWidth={2.5} fill="url(#revenueGrad)" dot={{ r: 3, fill: '#10b981' }} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {revenue.length === 0 && (
        <Card><EmptyState text="수익 데이터가 없습니다. report_agent.py가 수익을 수집하면 자동 반영됩니다." /></Card>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 8: COSTS (Supabase)
// ═══════════════════════════════════════════

function CostsTab({ siteId }) {
  const { costs } = useMonthlyCosts(siteId);
  const { total: rev } = useMonthlyRevenue(siteId);
  const profit = rev.krw - costs.total_krw;
  const roi = costs.total_krw > 0 ? ((profit / costs.total_krw) * 100).toFixed(0) : '-';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
        <StatCard label="이번 달 API 비용" value={fmtKRW(costs.total_krw)} color="#f59e0b" icon="◈" />
        <StatCard label="순이익" value={fmtKRW(profit)} color={profit >= 0 ? '#10b981' : '#ef4444'} icon="★" />
        <StatCard label="ROI" value={roi !== '-' ? `${roi}%` : '-'} color="#6366f1" icon="↗" />
      </div>

      <Card>
        <SectionTitle>모델별 비용</SectionTitle>
        {Object.entries(costs.by_model).length > 0 ? (
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start' }}>
            <ResponsiveContainer width={200} height={200}>
              <PieChart>
                <Pie
                  data={Object.entries(costs.by_model).map(([name, value]) => ({ name, value }))}
                  cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  dataKey="value" paddingAngle={3} strokeWidth={0}
                >
                  {Object.keys(costs.by_model).map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={v => fmtKRW(v)} {...CHART_TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1 }}>
              {Object.entries(costs.by_model).sort((a, b) => b[1] - a[1]).map(([model, cost], i) => {
                const pct = costs.total_krw > 0 ? (cost / costs.total_krw * 100) : 0;
                return (
                  <div key={model}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 10, height: 10, borderRadius: 3, background: PIE_COLORS[i % PIE_COLORS.length] }} />
                        <span style={{ fontSize: 13, fontWeight: 500, color: '#4a5568' }}>{model}</span>
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 700 }}>
                        {fmtKRW(cost)} <span style={{ color: '#94a3b8', fontWeight: 400 }}>({pct.toFixed(1)}%)</span>
                      </span>
                    </div>
                    <div style={{ height: 6, background: '#f1f5f9', borderRadius: 3 }}>
                      <div style={{
                        height: '100%', width: `${pct}%`, borderRadius: 3,
                        background: PIE_COLORS[i % PIE_COLORS.length], transition: 'width 0.5s'
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <EmptyState text="비용 데이터 없음" />
        )}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 9: ALERTS (Supabase)
// ═══════════════════════════════════════════

function AlertsTab({ siteId }) {
  const { alerts, markRead } = useAlerts(siteId);

  const sevStyle = {
    critical: { color: '#ef4444', bg: 'rgba(239,68,68,0.06)' },
    warning: { color: '#f59e0b', bg: 'rgba(245,158,11,0.06)' },
    info: { color: '#10b981', bg: 'rgba(16,185,129,0.06)' },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e' }}>알림 ({alerts.length}건)</h2>
      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {alerts.map(a => {
            const sev = sevStyle[a.severity] || sevStyle.info;
            return (
              <div key={a.id} style={{
                padding: '14px 16px', borderRadius: 12,
                background: a.is_read ? '#f8fafc' : sev.bg,
                border: '1px solid rgba(0,0,0,0.06)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: sev.color, fontSize: 10 }}>●</span>
                    {a.title}
                  </div>
                  <div style={{ fontSize: 12, color: '#4a5568', marginTop: 4 }}>{a.message}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 6 }}>
                    {new Date(a.created_at).toLocaleString('ko-KR')}
                  </div>
                </div>
                {!a.is_read && (
                  <button onClick={() => markRead(a.id)} style={{
                    background: 'rgba(99,102,241,0.06)', border: 'none', borderRadius: 8,
                    padding: '6px 14px', color: '#6366f1', fontSize: 12,
                    fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap'
                  }}>읽음</button>
                )}
              </div>
            );
          })}
          {alerts.length === 0 && <EmptyState text="알림 없음" />}
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 10: SETTINGS (AI Model + Site Config)
// ═══════════════════════════════════════════

function SettingsTab({ siteId, sites }) {
  const site = sites.find(s => s.id === siteId);
  const [draftModel, setDraftModel] = useState('deepseek-chat');
  const [polishModel, setPolishModel] = useState('claude-sonnet-4-20250514');
  const cfg = site?.config || {};
  const [siteName, setSiteName] = useState(site?.name || '');
  const [domain, setDomain] = useState(site?.domain || '');
  const [wpUrl, setWpUrl] = useState(site?.wp_url || '');
  const [wpUser, setWpUser] = useState(cfg.wp_username || '');
  const [wpPass, setWpPass] = useState(cfg.wp_app_password || '');
  const [target, setTarget] = useState(site?.daily_target || 10);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [paused, setPaused] = useState(site?.status === 'paused');

  useEffect(() => {
    if (site) {
      const c = site.config || {};
      setSiteName(site.name || '');
      setDomain(site.domain || '');
      setWpUrl(site.wp_url || '');
      setWpUser(c.wp_username || '');
      setWpPass(c.wp_app_password || '');
      setTarget(site.daily_target || 10);
      setPaused(site.status === 'paused');
    }
  }, [site]);

  const draft = DRAFT_MODELS.find(m => m.id === draftModel) || DRAFT_MODELS[0];
  const polish = POLISH_MODELS.find(m => m.id === polishModel) || POLISH_MODELS[0];
  const totalCost = draft.costPer + polish.costPer;

  const handleSave = async () => {
    setSaving(true);
    await supabase.from('sites').update({
      name: siteName,
      domain: domain,
      wp_url: wpUrl,
      daily_target: target,
      status: paused ? 'paused' : 'active',
      config: { ...cfg, wp_username: wpUser, wp_app_password: wpPass },
      ai_config: { draft_model: draftModel, polish_model: polishModel },
      updated_at: new Date().toISOString()
    }).eq('id', siteId);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 760 }}>
      {/* Cost Summary */}
      <Card style={{ background: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 50%, #f0f9ff 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 500, marginBottom: 4 }}>예상 편당 비용</div>
            <div style={{ fontSize: 36, fontWeight: 900, color: '#6366f1', letterSpacing: -1 }}>{fmtKRW(totalCost)}</div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>초안 {fmtKRW(draft.costPer)} + 폴리싱 {fmtKRW(polish.costPer)}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>일 10편 기준 월 비용</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#1a1a2e' }}>{fmtKRW(totalCost * 10 * 30)}</div>
          </div>
        </div>
      </Card>

      {/* Draft Model */}
      <Card>
        <SectionTitle>초안 모델 (Draft)</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {DRAFT_MODELS.map(m => (
            <label key={m.id} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
              border: draftModel === m.id ? '2px solid #6366f1' : '1px solid #e2e8f0',
              background: draftModel === m.id ? 'rgba(99,102,241,0.04)' : '#f8fafc',
              transition: 'all 0.15s'
            }}>
              <input type="radio" name="draft" value={m.id} checked={draftModel === m.id}
                onChange={() => setDraftModel(m.id)} style={{ display: 'none' }} />
              <div style={{
                width: 20, height: 20, borderRadius: '50%', border: '2px solid',
                borderColor: draftModel === m.id ? '#6366f1' : '#cbd5e1',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                {draftModel === m.id && <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#6366f1' }} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>{m.name}</div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>속도: {m.speed} · 품질: {m.quality}</div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#6366f1' }}>{fmtKRW(m.costPer)}</div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>편당</div>
              </div>
            </label>
          ))}
        </div>
      </Card>

      {/* Polish Model */}
      <Card>
        <SectionTitle>폴리싱 모델 (Polish)</SectionTitle>
        <p style={{ fontSize: 13, color: '#4a5568', marginBottom: 14, marginTop: -8 }}>
          초안을 Claude로 다듬어 문체와 SEO를 개선합니다. OFF 시 초안을 그대로 발행합니다.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {POLISH_MODELS.map(m => (
            <label key={m.id} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
              border: polishModel === m.id ? '2px solid #6366f1' : '1px solid #e2e8f0',
              background: polishModel === m.id ? 'rgba(99,102,241,0.04)' : '#f8fafc',
              transition: 'all 0.15s'
            }}>
              <input type="radio" name="polish" value={m.id} checked={polishModel === m.id}
                onChange={() => setPolishModel(m.id)} style={{ display: 'none' }} />
              <div style={{
                width: 20, height: 20, borderRadius: '50%', border: '2px solid',
                borderColor: polishModel === m.id ? '#6366f1' : '#cbd5e1',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                {polishModel === m.id && <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#6366f1' }} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>
                  {m.name}
                  {m.id === 'none' && <span style={{ color: '#94a3b8', fontWeight: 400 }}> (비용 절감)</span>}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: m.costPer > 0 ? '#6366f1' : '#10b981' }}>
                  {m.costPer > 0 ? fmtKRW(m.costPer) : 'FREE'}
                </div>
                {m.costPer > 0 && <div style={{ fontSize: 11, color: '#94a3b8' }}>편당</div>}
              </div>
            </label>
          ))}
        </div>
      </Card>

      {/* Site Config */}
      <Card>
        <SectionTitle>사이트 설정</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>사이트 이름</label>
            <input value={siteName} onChange={e => setSiteName(e.target.value)} placeholder="블로그 이름"
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '10px 14px', color: '#1a1a2e', fontSize: 14, width: '100%', fontWeight: 500, outline: 'none' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>도메인</label>
            <input value={domain} onChange={e => setDomain(e.target.value)} placeholder="example.com"
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '10px 14px', color: '#1a1a2e', fontSize: 14, width: '100%', fontWeight: 500, outline: 'none' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>WordPress API URL</label>
            <input value={wpUrl} onChange={e => setWpUrl(e.target.value)} placeholder="https://example.com/wp-json/wp/v2"
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '10px 14px', color: '#1a1a2e', fontSize: 13, width: '100%', fontWeight: 500, outline: 'none',
                fontFamily: 'monospace' }} />
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>예: https://example.com/wp-json/wp/v2</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>WP 사용자명</label>
              <input value={wpUser} onChange={e => setWpUser(e.target.value)} placeholder="admin"
                style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                  padding: '10px 14px', color: '#1a1a2e', fontSize: 13, width: '100%', fontWeight: 500, outline: 'none' }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>WP 앱 비밀번호</label>
              <input value={wpPass} onChange={e => setWpPass(e.target.value)} placeholder="xxxx xxxx xxxx xxxx" type="password"
                style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                  padding: '10px 14px', color: '#1a1a2e', fontSize: 13, width: '100%', fontWeight: 500, outline: 'none',
                  fontFamily: 'monospace' }} />
            </div>
          </div>
          <div style={{ fontSize: 10, color: '#f59e0b', background: 'rgba(245,158,11,0.06)', padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(245,158,11,0.12)' }}>
            멀티사이트 모드: 사이트별 WP 인증정보가 여기에 저장됩니다. GitHub Secrets의 WP 인증정보는 폴백으로 사용됩니다.
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6, fontWeight: 500 }}>일일 발행 목표</label>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {[1, 3, 5, 10, 15, 20].map(n => (
                <PillButton key={n} selected={target === n} onClick={() => setTarget(n)}>
                  {n}편
                </PillButton>
              ))}
              <input type="number" value={target} onChange={e => setTarget(Number(e.target.value))} min={1} max={50}
                style={{
                  background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
                  padding: '8px 12px', color: '#1a1a2e', fontSize: 13, width: 70, fontWeight: 600, textAlign: 'center', outline: 'none'
                }} />
              <span style={{ fontSize: 12, color: '#94a3b8' }}>편/일</span>
            </div>
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
              월 예상: {target * 30}편 · 월 예상 비용: {fmtKRW(totalCost * target * 30)}
            </div>
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 14px', borderRadius: 10,
            background: paused ? 'rgba(239,68,68,0.04)' : '#f8fafc',
            border: paused ? '1px solid rgba(239,68,68,0.15)' : '1px solid #e2e8f0'
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: paused ? '#ef4444' : '#1a1a2e' }}>
                발행 일시정지 {paused && '(중단됨)'}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>ON 시 이 사이트의 자동 발행을 중단합니다</div>
            </div>
            <Toggle on={paused} set={setPaused} />
          </div>
        </div>
      </Card>

      {/* Integration Status */}
      <Card>
        <SectionTitle>연동 상태</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { name: 'Supabase Realtime', status: true },
            { name: 'GitHub Actions', status: true },
            { name: 'WordPress API', status: !!site?.wp_url },
            { name: 'Google Search Console', status: false },
            { name: 'AdSense API', status: false },
          ].map(s => (
            <div key={s.name} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 14px', borderRadius: 10, background: '#f8fafc'
            }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: '#1a1a2e' }}>{s.name}</span>
              <Badge text={s.status ? '연결됨' : '미연결'} color={s.status ? 'green' : 'yellow'} />
            </div>
          ))}
        </div>
      </Card>

      {/* Save */}
      <button onClick={handleSave} disabled={saving} style={{
        background: saved ? '#10b981' : '#6366f1', border: 'none', borderRadius: 12,
        padding: '14px 24px', color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
        transition: 'all 0.2s', opacity: saving ? 0.6 : 1,
        boxShadow: '0 2px 8px rgba(99,102,241,0.3)'
      }}>
        {saving ? '저장 중...' : saved ? '저장 완료' : '설정 저장'}
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB 11: ADMIN
// ═══════════════════════════════════════════

function AdminTab({ autoMode, setAutoMode, selNiches, connectedAff, connectedApi }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e' }}>관리자 패널</h2>

      <Card>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e', marginBottom: 12 }}>시스템 상태</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {[
            { l: '자동모드', v: autoMode ? 'ON' : 'OFF', c: autoMode ? '#10b981' : '#ef4444' },
            { l: '선택 니치', v: selNiches.length + '개', c: '#6366f1' },
            { l: '수익화 연결', v: connectedAff + '개', c: '#f59e0b' },
            { l: 'AI 모델', v: connectedApi + '개', c: '#3b82f6' },
          ].map((s, i) => (
            <div key={i} style={{
              background: `${s.c}08`, border: `1px solid ${s.c}1a`, borderRadius: 12,
              padding: 14, textAlign: 'center'
            }}>
              <div style={{ fontSize: 10, color: '#94a3b8', fontWeight: 600 }}>{s.l}</div>
              <div style={{ fontSize: 20, fontWeight: 900, color: s.c, marginTop: 4 }}>{s.v}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a2e' }}>자동 생성 모드</div>
          <Toggle on={autoMode} set={setAutoMode} />
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8' }}>ON: CSV 소진 시 Trends+Reddit+AI에서 키워드 자동 발굴</div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// TAB: PUBLISH LOGS (품질 점수 포함)
// ═══════════════════════════════════════════

function PostsTab({ siteId }) {
  const { posts, loading } = useRecentPosts(siteId, 50);

  function qualityColor(score) {
    if (score >= 80) return '#10b981';
    if (score >= 70) return '#f59e0b';
    return '#ef4444';
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a2e' }}>발행 로그 ({posts.length}건)</h2>
      <Card>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                {['시간', '제목', '품질', '파이프라인', '키워드', '길이', '이미지', '쿠팡', 'SNS', '상태'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '12px 8px', color: '#94a3b8',
                    fontWeight: 600, fontSize: 11, letterSpacing: 0.5
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {posts.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '12px 8px', whiteSpace: 'nowrap', color: '#94a3b8', fontSize: 12 }}>
                    {new Date(p.published_at).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td style={{ padding: '12px 8px', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.url ? (
                      <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ color: '#6366f1', textDecoration: 'none', fontWeight: 500 }}>{p.title}</a>
                    ) : p.title}
                  </td>
                  <td style={{ padding: '12px 8px' }}>
                    {p.quality_score > 0 ? (
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '3px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                        background: `${qualityColor(p.quality_score)}12`,
                        color: qualityColor(p.quality_score)
                      }}>
                        {p.quality_score}
                      </span>
                    ) : (
                      <span style={{ color: '#cbd5e1', fontSize: 11 }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 8px' }}><Badge text={p.pipeline || 'autoblog'} color="purple" /></td>
                  <td style={{ padding: '12px 8px', color: '#4a5568', fontSize: 12 }}>{p.keyword?.slice(0, 18)}</td>
                  <td style={{ padding: '12px 8px', fontVariantNumeric: 'tabular-nums' }}>{fmt(p.content_length)}</td>
                  <td style={{ padding: '12px 8px', textAlign: 'center' }}>
                    {p.has_image ? (
                      <span style={{ fontSize: 10, color: '#10b981', fontWeight: 600 }}>{p.image_tier || 'O'}</span>
                    ) : (
                      <span style={{ color: '#cbd5e1' }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 8px', textAlign: 'center' }}>
                    {p.has_coupang ? <span style={{ color: '#10b981' }}>O</span> : <span style={{ color: '#cbd5e1' }}>—</span>}
                  </td>
                  <td style={{ padding: '12px 8px' }}>
                    {(Array.isArray(p.sns_shared) ? p.sns_shared : []).map(s => <Badge key={s} text={s} color="blue" />)}
                  </td>
                  <td style={{ padding: '12px 8px' }}>
                    <Badge text={p.status} color={p.status === 'published' ? 'green' : p.status === 'failed' ? 'red' : 'yellow'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading && <LoadingState />}
          {!loading && posts.length === 0 && (
            <EmptyState text="발행 로그가 없습니다. GitHub Actions 발행 후 자동 기록됩니다." />
          )}
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// QUICK PUBLISH TAB
// ═══════════════════════════════════════════

// ═══════════════════════════════════════════
// SETUP GUIDE
// ═══════════════════════════════════════════

function SetupGuide() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 50%, #f0f9ff 100%)'
    }}>
      <Card style={{ maxWidth: 600, width: '100%' }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 8, color: '#1a1a2e' }}>
          <span style={{ color: '#6366f1' }}>Clone Factory</span> 설정
        </h2>
        <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 28 }}>Supabase 연동이 필요합니다.</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {[
            { step: '1', title: 'Supabase SQL 스키마 실행', desc: 'Supabase Dashboard → SQL Editor → supabase_schema_final.sql 내용 붙여넣기 → Run' },
            { step: '2', title: '환경변수 설정', desc: 'Vercel: Settings → Environment Variables에 추가',
              code: 'NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co\nNEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key' },
            { step: '3', title: '배포', desc: 'GitHub push → Vercel 자동 배포 → 대시보드 접속' }
          ].map(item => (
            <div key={item.step} style={{ display: 'flex', gap: 14 }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%', background: 'rgba(99,102,241,0.06)',
                color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 700, flexShrink: 0
              }}>{item.step}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4, color: '#1a1a2e' }}>{item.title}</div>
                <div style={{ fontSize: 12, color: '#4a5568' }}>{item.desc}</div>
                {item.code && (
                  <div style={{
                    background: '#f8fafc', borderRadius: 10, padding: 14, fontSize: 12,
                    fontFamily: 'monospace', border: '1px solid #e2e8f0', marginTop: 8,
                    whiteSpace: 'pre-wrap', color: '#1a1a2e', lineHeight: 1.8
                  }}>{item.code}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
