import { NextResponse } from 'next/server';
import { requireAdmin, requireLivePublish, dispatchWorkflow, githubFailure, errorResponse } from '@/lib/admin-api';

// ETF 리포트 워크플로 수동 실행 (관리자 전용)
// report_type 은 목록 값만 받는다: etf-report.yml 의 run 스크립트에 그대로 들어가기 때문
// etf-report.yml 의 정지 가드는 schedule 에만 걸리고, etf_report.py 는 sites.status(paused)를 보지 않는다.
// 그래서 dry_run=false 는 여기서 실제 발행 스위치로 막는다
const REPORT_TYPES = ['blog-ready', 'daily', 'rotation', 'performance'];
// 기존 기본값 유지. 운영에서는 Vercel 의 GITHUB_REPO 로 대상 저장소를 지정한다
const DEFAULT_REPO = 'mymiryu-commits/wp-auto';

const isTrue = (v) => v === true || v === 'true';

export async function POST(request) {
  try {
    await requireAdmin(request);

    const body = (await request.json().catch(() => null)) || {};
    const reportType = body.report_type || 'blog-ready';
    if (!REPORT_TYPES.includes(reportType)) {
      return NextResponse.json({ error: `알 수 없는 리포트 유형: ${reportType}` }, { status: 400 });
    }

    const dryRun = isTrue(body.dry_run);
    if (!dryRun) requireLivePublish('3days 리포트는 planx-ai.com(site-1)에 바로 공개됩니다');

    const inputs = {
      report_type: reportType,
      dry_run: dryRun ? 'true' : 'false',
      force: isTrue(body.force) ? 'true' : 'false',
    };
    const result = await dispatchWorkflow('etf-report.yml', inputs, DEFAULT_REPO);
    if (!result.ok) return githubFailure(result, 'etf-report.yml');

    return NextResponse.json({
      success: true,
      message: '3days 리포트 실행 요청 완료',
      repo: result.repo,
    });
  } catch (err) {
    return errorResponse(err);
  }
}
