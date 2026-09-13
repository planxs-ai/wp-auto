import { NextResponse } from 'next/server';
import { requireAdmin, isLivePublishEnabled, errorResponse } from '@/lib/admin-api';

// 요청마다 헤더(토큰)를 본다 (정적 프리렌더 금지)
export const dynamic = 'force-dynamic';

// 대시보드 AdminGate 용 관리자 확인.
// 브라우저 anon 클라이언트로 user_profiles 를 읽지 않고 서버(service key)에서 requireAdmin 과 같은 기준으로 판정한다.
// → 005 적용 전 user_profiles 정책 무한 재귀(42P17)와 무관하게 동작하고, API 와 화면의 판정이 어긋나지 않는다
export async function GET(request) {
  try {
    const user = await requireAdmin(request);
    return NextResponse.json(
      { admin: true, email: user.email || '', live_publish: isLivePublishEnabled() },
      { headers: { 'Cache-Control': 'no-store' } },
    );
  } catch (err) {
    return errorResponse(err);
  }
}
