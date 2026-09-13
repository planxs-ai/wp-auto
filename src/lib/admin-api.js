import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// ═══════════════════════════════════════════
// 관리자 API 라우트 공통 (서버 전용)
// - Authorization: Bearer <Supabase 사용자 JWT> 를 검증한다
// - 관리자 판정은 두 조건을 모두 만족해야 한다
//     ① 서버 env ADMIN_USER_IDS 허용 목록에 있는 사용자 id
//     ② user_profiles.role = 'admin'
//   role 컬럼은 005 가드 트리거 전에는 본인이 UPDATE 로 바꿀 수 있다(001 users_update_own_profile).
//   그래서 role 하나만 믿지 않고, DB 밖(Vercel env)의 허용 목록을 함께 본다
// - SUPABASE_SERVICE_KEY·ADMIN_USER_IDS 가 없으면 anon 키로 넘어가지 않고 500 을 돌려준다 (fail-closed)
// - GitHub 자격증명은 서버 환경변수(GITHUB_TOKEN)만 쓴다. 사이트 설정·요청 본문에서 받지 않는다
// ═══════════════════════════════════════════

export class AdminApiError extends Error {
  constructor(status, message, guide) {
    super(message);
    this.status = status;
    this.guide = guide || null;
  }
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !serviceKey) {
    throw new AdminApiError(
      500,
      '서버 설정 오류: SUPABASE_SERVICE_KEY 가 설정되지 않아 관리자 권한을 확인할 수 없습니다.',
      'Vercel Production 환경변수에 SUPABASE_SERVICE_KEY 를 넣고 재배포한 뒤, /api/health 의 supabase_service_key 가 true 인지 확인하세요.',
    );
  }
  return createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });
}

// 관리자 허용 목록 (쉼표 구분 auth.users id). 비어 있으면 아무도 통과시키지 않는다
function getAdminUserIds() {
  const ids = (process.env.ADMIN_USER_IDS || '')
    .split(',')
    .map((id) => id.trim().toLowerCase())
    .filter(Boolean);
  if (ids.length === 0) {
    throw new AdminApiError(
      500,
      '서버 설정 오류: ADMIN_USER_IDS 가 설정되지 않아 관리자를 확인할 수 없습니다.',
      'Supabase Authentication → Users 에서 관리자 계정의 User UID 를 복사해 Vercel Production 환경변수 ADMIN_USER_IDS 에 넣고(여러 명이면 쉼표로 구분) 재배포하세요.',
    );
  }
  return ids;
}

// 요청자가 관리자인지 확인한다. 아니면 AdminApiError 를 던진다.
export async function requireAdmin(request) {
  const header = request.headers.get('authorization') || '';
  const token = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
  if (!token) throw new AdminApiError(401, '로그인이 필요합니다.');

  // 설정 누락은 토큰 검증보다 먼저 드러낸다 (외부 호출 없이 500)
  const allowedIds = getAdminUserIds();
  const admin = getSupabaseAdmin();

  const { data: userData, error: userError } = await admin.auth.getUser(token);
  const user = userData?.user;
  if (userError || !user) {
    throw new AdminApiError(401, '세션이 만료되었거나 유효하지 않습니다. 다시 로그인하세요.');
  }

  // ① 허용 목록 — role 값과 관계없이 목록 밖이면 거부
  if (!allowedIds.includes(String(user.id).toLowerCase())) {
    console.warn('[admin-api] 허용 목록 밖 사용자 거부:', user.id);
    throw new AdminApiError(403, '관리자만 실행할 수 있습니다.');
  }

  // ② role — 허용 목록에 있어도 role 이 admin 이 아니면 거부 (계정 강등 시 즉시 막히도록)
  const { data: profile, error: profileError } = await admin
    .from('user_profiles')
    .select('role')
    .eq('id', user.id)
    .maybeSingle();
  if (profileError) {
    console.error('[admin-api] user_profiles 조회 실패:', profileError.message);
    throw new AdminApiError(500, '관리자 권한 조회에 실패했습니다. 서버 로그를 확인하세요.');
  }
  if (profile?.role !== 'admin') {
    throw new AdminApiError(
      403,
      '관리자만 실행할 수 있습니다.',
      'ADMIN_USER_IDS 에는 있지만 user_profiles.role 이 admin 이 아닙니다. Supabase SQL Editor 에서 이 계정의 role 을 확인하세요.',
    );
  }
  return user;
}

// ═══════════════════════════════════════════
// 실제 발행 스위치
// AdSense 심사 기간 결정(새 글 0)에 따라 기본은 잠김. PUBLISH_DISPATCH_ENABLED='true' 일 때만 열린다.
// 대시보드에서 dry_run=false 로 publish.yml·etf-report.yml 을 실행하는 경로에만 쓴다.
// (Actions 화면·gh workflow run 으로 직접 실행하는 경로는 막지 않는다)
// ═══════════════════════════════════════════
export function isLivePublishEnabled() {
  return process.env.PUBLISH_DISPATCH_ENABLED === 'true';
}

export function requireLivePublish(what) {
  if (isLivePublishEnabled()) return;
  throw new AdminApiError(
    409,
    `실제 발행이 잠겨 있어 실행하지 않았습니다: ${what}`,
    '지금은 테스트 모드(dry_run)로만 실행할 수 있습니다. 실제 발행이 꼭 필요하면 gh workflow run 으로 직접 실행하고, AdSense 승인 뒤에는 Vercel 환경변수 PUBLISH_DISPATCH_ENABLED=true 를 넣고 재배포하세요.',
  );
}

// GitHub Actions workflow_dispatch 호출. 성공(204)이면 { ok: true } 를 돌려준다.
export async function dispatchWorkflow(file, inputs, defaultRepo) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    throw new AdminApiError(
      500,
      '서버 설정 오류: GITHUB_TOKEN 이 없어 워크플로를 실행할 수 없습니다.',
      'gh workflow run 으로 직접 실행하거나, 이 저장소 하나에 Actions 쓰기 권한만 준 fine-grained 토큰을 Vercel 에 넣고 재배포하세요.',
    );
  }
  const repo = process.env.GITHUB_REPO || defaultRepo;
  const resp = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/${file}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: 'main', inputs }),
  });
  if (resp.status === 204) return { ok: true, repo };
  return { ok: false, repo, status: resp.status, detail: await resp.text() };
}

// GitHub 가 거절한 경우. 사용자 세션 문제(401)와 섞이지 않게 502 로 돌려준다.
export function githubFailure(result, file) {
  const guides = {
    401: 'GITHUB_TOKEN 이 만료되었거나 폐기되었습니다.',
    403: 'GITHUB_TOKEN 권한을 확인하세요 (대상 저장소의 Actions 쓰기 권한 필요).',
    404: `GITHUB_REPO(${result.repo}) 와 main 브랜치의 ${file} 가 있는지 확인하세요.`,
    422: '보낸 input 이 워크플로 선언과 다르거나, 워크플로가 비활성(disabled) 상태일 수 있습니다.',
  };
  return NextResponse.json({
    error: `GitHub API 실패: ${result.status}`,
    guide: guides[result.status] || null,
    detail: result.detail,
    repo: result.repo,
    workflow: file,
  }, { status: 502 });
}

export function errorResponse(err) {
  if (err instanceof AdminApiError) {
    return NextResponse.json({ error: err.message, guide: err.guide }, { status: err.status });
  }
  console.error('[admin-api] 처리 중 오류:', err);
  return NextResponse.json({ error: '서버 오류가 발생했습니다.' }, { status: 500 });
}
