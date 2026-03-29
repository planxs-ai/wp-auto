'use client';
import { useCurrentUser, usePlanFeatures } from '@/lib/auth';
import { PLANS } from '@/lib/plan-features';
import { Card, ActionButton, Badge } from '@/components/ui';

const FEATURE_LIST = [
  { key: 'sites', label: '사이트 수', getValue: (p) => p.maxSites === 999 ? '무제한' : `${p.maxSites}개` },
  { key: 'posts', label: '일일 발행', getValue: (p) => p.maxDailyPosts === 999 ? '무제한' : `${p.maxDailyPosts}편` },
  { key: 'categories', label: '카테고리', getValue: (p) => p.maxCategories === 999 ? '전체' : `${p.maxCategories}개` },
  { key: 'goldenMode', label: 'Golden Mode', getValue: (p) => p.features.goldenMode ? '\u2705' : '\u274c' },
  { key: 'polishing', label: 'AI 폴리싱', getValue: (p) => p.features.polishing ? 'Claude Sonnet' : '\u274c' },
  { key: 'customSchedule', label: '커스텀 스케줄', getValue: (p) => p.features.customSchedule ? '\u2705' : '\u274c' },
  { key: 'modelSelection', label: 'AI 모델 선택', getValue: (p) => p.features.modelSelection ? '\u2705' : '\u274c' },
  { key: 'revenueSimulation', label: '수익 시뮬레이션', getValue: (p) => p.features.revenueSimulation ? '\u2705' : '\u274c' },
  { key: 'seoAnalysis', label: 'SEO 분석', getValue: (p) => p.features.seoAnalysis ? '\u2705' : '\u274c' },
  { key: 'telegramAlerts', label: 'Telegram 알림', getValue: (p) => p.features.telegramAlerts ? '\u2705' : '\u274c' },
  { key: 'snsAutomation', label: 'SNS 자동화', getValue: (p) => p.features.snsAutomation ? '\u2705' : '\u274c' },
  { key: 'marketingContent', label: '마케팅 글 생성', getValue: (p) => p.features.marketingContent ? '\u2705' : '\u274c' },
];

export default function UpgradePage() {
  const { planId, trialActive } = useCurrentUser();
  const plans = ['standard', 'premium', 'mama'];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 8 }}>플랜 업그레이드</h1>
        <p style={{ fontSize: 14, color: 'var(--text-dim)' }}>
          더 많은 글, 더 높은 품질, 더 많은 수익. 지금 업그레이드하세요.
        </p>
      </div>

      <div className="grid-responsive" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 40 }}>
        {plans.map(pid => {
          const p = PLANS[pid];
          const isCurrent = pid === planId;
          const isPopular = pid === 'premium';
          return (
            <Card key={pid} style={{
              position: 'relative', textAlign: 'center',
              border: isPopular ? '2px solid var(--accent)' : '1px solid var(--card-border)',
              transform: isPopular ? 'scale(1.03)' : 'none',
            }}>
              {isPopular && (
                <div style={{
                  position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)',
                  padding: '4px 16px', borderRadius: 20, background: 'var(--accent)',
                  color: '#fff', fontSize: 11, fontWeight: 700,
                }}>인기</div>
              )}

              <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 4, marginTop: isPopular ? 8 : 0 }}>
                {p.name}
              </div>

              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 28, fontWeight: 800, color: 'var(--text)' }}>
                  \u20a9{(p.price.monthly / 1000).toFixed(0)}K
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-dim)' }}> /월</span>
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 16 }}>
                연간 결제 시 \u20a9{(p.price.yearly / 1000).toFixed(0)}K/년
                <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                  {' '}(2개월 무료)
                </span>
              </div>

              {isCurrent ? (
                <div style={{
                  padding: '10px 20px', borderRadius: 10, background: 'var(--input-bg)',
                  color: 'var(--text-dim)', fontSize: 13, fontWeight: 600,
                }}>현재 플랜</div>
              ) : (
                <ActionButton
                  variant={isPopular ? 'primary' : 'secondary'}
                  style={{ width: '100%' }}
                >
                  {pid === 'mama' ? '상담 신청' : '업그레이드'}
                </ActionButton>
              )}
            </Card>
          );
        })}
      </div>

      {/* Feature Comparison Table */}
      <Card>
        <SectionTitle_>기능 비교</SectionTitle_>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--card-border)' }}>
                <th style={{ ...thStyle, textAlign: 'left' }}>기능</th>
                {plans.map(pid => (
                  <th key={pid} style={{ ...thStyle, textAlign: 'center', color: pid === planId ? 'var(--accent)' : 'var(--text)' }}>
                    {PLANS[pid].name}
                    {pid === planId && <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>현재</div>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {FEATURE_LIST.map(feat => (
                <tr key={feat.key} style={{ borderBottom: '1px solid var(--card-border)' }}>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{feat.label}</td>
                  {plans.map(pid => (
                    <td key={pid} style={{ ...tdStyle, textAlign: 'center' }}>
                      {feat.getValue(PLANS[pid])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function SectionTitle_({ children }) {
  return <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>{children}</h3>;
}

const thStyle = { padding: '12px 8px', fontSize: 14, fontWeight: 700 };
const tdStyle = { padding: '10px 8px', fontSize: 13, color: 'var(--text-secondary)' };
