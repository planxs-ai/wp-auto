import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { generatePublishWorkflow } from '@/lib/workflow-template';
import { getGitHubCredentials } from '@/lib/github-helper';

const WORKFLOW_PATH = '.github/workflows/publish.yml';

function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}

async function verifyAuth(request) {
  const authHeader = request.headers.get('authorization');
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );

  if (authHeader?.startsWith('Bearer ')) {
    const token = authHeader.slice(7);
    const { data: { user }, error } = await supabase.auth.getUser(token);
    if (!error && user) return user;
  }
  return null;
}

/**
 * POST /api/schedule
 * 고객 repo의 publish.yml을 생성/업데이트
 *
 * Body: { siteId, scheduleTimes: ['08:00', '18:00'], dailyCount: 2 }
 */
export async function POST(request) {
  const user = await verifyAuth(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { siteId, scheduleTimes, dailyCount } = await request.json();

  if (!siteId || !scheduleTimes || !Array.isArray(scheduleTimes) || scheduleTimes.length === 0) {
    return NextResponse.json({
      error: '사이트 ID와 스케줄 시간이 필요합니다.',
    }, { status: 400 });
  }

  // 사이트 소유권 확인
  const supabase = getSupabaseAdmin();
  const { data: userSite } = await supabase
    .from('user_sites')
    .select('role')
    .eq('user_id', user.id)
    .eq('site_id', siteId)
    .single();

  if (!userSite) {
    return NextResponse.json({
      error: '해당 사이트에 대한 권한이 없습니다.',
    }, { status: 403 });
  }

  // 사이트별 GitHub 인증정보 조회
  const gh = await getGitHubCredentials(siteId);
  if (!gh) {
    return NextResponse.json({
      error: 'GitHub 인증정보가 없습니다.',
      guide: '설정 > GitHub 연동에서 Fork 저장소와 토큰을 먼저 등록하세요.',
    }, { status: 400 });
  }

  // publish.yml 생성
  const workflowContent = generatePublishWorkflow({
    siteId,
    scheduleTimes: scheduleTimes.slice(0, dailyCount || scheduleTimes.length),
    count: '1',
  });

  const [owner, repo] = gh.repo.split('/');
  const apiBase = `https://api.github.com/repos/${owner}/${repo}`;
  const headers = {
    'Authorization': `Bearer ${gh.token}`,
    'Accept': 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
  };

  try {
    // 기존 파일 sha 조회 (업데이트 시 필요)
    let existingSha = null;
    const getResp = await fetch(`${apiBase}/contents/${WORKFLOW_PATH}`, { headers });
    if (getResp.ok) {
      const existing = await getResp.json();
      existingSha = existing.sha;
    }

    // 파일 생성/업데이트
    const putResp = await fetch(`${apiBase}/contents/${WORKFLOW_PATH}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({
        message: `chore: update publish schedule [${scheduleTimes.join(', ')}]`,
        content: Buffer.from(workflowContent).toString('base64'),
        ...(existingSha ? { sha: existingSha } : {}),
      }),
    });

    if (putResp.ok) {
      return NextResponse.json({
        success: true,
        message: `스케줄이 ${gh.repo}에 반영되었습니다 (${scheduleTimes.join(', ')})`,
        repo: gh.repo,
        crons: scheduleTimes.length,
      });
    }

    const errorBody = await putResp.text();
    return NextResponse.json({
      error: `GitHub API 실패: ${putResp.status}`,
      detail: errorBody,
      guide: putResp.status === 404
        ? 'Fork 저장소 주소를 확인하세요.'
        : putResp.status === 403
        ? 'GitHub Token 권한을 확인하세요 (repo + workflow 스코프 필요).'
        : null,
    }, { status: putResp.status });
  } catch (err) {
    return NextResponse.json({
      error: '네트워크 오류',
      detail: err.message,
    }, { status: 500 });
  }
}
