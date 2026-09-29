import { NextResponse } from 'next/server';

// 빌드 시점이 아니라 요청 시점의 환경변수를 보여야 한다 (정적 프리렌더 금지)
export const dynamic = 'force-dynamic';

/**
 * 서버 환경변수 설정 상태 확인 (값은 내보내지 않고 설정 여부만)
 * 배포 직후, 005 RLS 잠금을 적용하기 전에 supabase_service_key·admin_user_ids 가 true 인지 확인하는 용도
 */
export async function GET() {
  const checks = {
    supabase_url: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
    supabase_anon_key: !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    // 관리자 확인(/api/admin/me, /api/setup, /api/etf-report)은 두 값이 모두 있어야 한다. 없으면 500
    supabase_service_key: !!process.env.SUPABASE_SERVICE_KEY,
    admin_user_ids: !!(process.env.ADMIN_USER_IDS || '').trim(),
    // 선택: 없으면 대시보드의 발행·ETF 버튼만 멈춘다 (gh CLI 로 대신 실행)
    github_token: !!process.env.GITHUB_TOKEN,
    github_repo: !!process.env.GITHUB_REPO,
  };

  const ok = checks.supabase_url && checks.supabase_anon_key && checks.supabase_service_key && checks.admin_user_ids;

  return NextResponse.json({
    ok,
    checks,
    optional: ['github_token', 'github_repo'],
    missing: Object.entries(checks).filter(([, v]) => !v).map(([k]) => k),
    // 대시보드에서 dry_run=false 실행 허용 여부 (AdSense 심사 기간에는 false 가 정상)
    switches: { publish_dispatch_enabled: process.env.PUBLISH_DISPATCH_ENABLED === 'true' },
  });
}
