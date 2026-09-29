import { NextResponse } from 'next/server';
import { requireAdmin, requireLivePublish, dispatchWorkflow, githubFailure, errorResponse, AdminApiError } from '@/lib/admin-api';

// ═══════════════════════════════════════════
// 관리자 전용 GitHub Actions 트리거
// - WP 자격증명은 요청·DB 에서 읽지 않는다. 각 워크플로가 GitHub secrets 에서 사이트별로 읽는다
// - 워크플로가 선언한 input 만 보낸다 (선언 밖 키를 보내면 GitHub 가 422)
// ═══════════════════════════════════════════

// 운영 사이트. 워크플로의 site_id choice 옵션과 같아야 한다 (planx-ai.com, bomissu.com)
const SITE_IDS = ['site-1', 'site-1775046458524'];
const DEFAULT_REPO = 'planxs-ai/wp-auto';

// patterns: run 스크립트에 그대로 들어가는 문자열 input 은 형식을 제한한다
const WORKFLOW_CONFIG = {
  'setup-menu': { file: 'setup-menu.yml', inputs: ['site_id'] },
  'setup-pages': { file: 'setup-pages.yml', inputs: ['site_id', 'blog_owner', 'blog_desc', 'contact_email'] },
  'inject-css': { file: 'inject-css.yml', inputs: ['site_id'] },
  'inject-css-posts': { file: 'inject-css-posts.yml', inputs: ['site_id', 'dry_run', 'force_update'] },
  // publish.yml 은 사이트 input 이 없다. 실행하면 planx·bomissu job 이 함께 돈다.
  // 그래서 편수는 사이트당 3편까지(두 사이트 합계 최대 6편)로 묶고, 실제 발행은 스위치로 잠근다.
  // publish.yml 에 site_id input 이 생기면 inputs 에 'site_id' 를 넣어 선택한 사이트만 보낸다
  'publish': {
    file: 'publish.yml',
    inputs: ['count', 'dry_run', 'pipeline', 'niche'],
    patterns: { count: /^[1-3]$/, dry_run: /^(true|false)$/, pipeline: /^(autoblog|hotdeal|promo)$/, niche: /^[a-z0-9-]*$/ },
    live: (inputs) => inputs.dry_run !== 'true',
    liveNote: 'publish.yml 은 planx·bomissu 두 사이트 job 을 함께 실행합니다',
  },
};

export async function POST(request) {
  try {
    await requireAdmin(request);

    const body = (await request.json().catch(() => null)) || {};
    const { action, siteId } = body;
    const config = WORKFLOW_CONFIG[action];
    if (!config) throw new AdminApiError(400, `알 수 없는 작업: ${action}`);

    // 사이트를 받는 작업은 운영 사이트만 허용. publish 도 다른 사이트를 고른 채 누르면 막는다
    const needsSite = config.inputs.includes('site_id');
    if ((needsSite || siteId) && !SITE_IDS.includes(siteId)) {
      throw new AdminApiError(400, `운영 사이트(${SITE_IDS.join(', ')})에서만 실행할 수 있습니다. 받은 값: ${siteId || '(없음)'}`);
    }

    const values = { ...(body.inputs || {}), site_id: siteId };
    const inputs = {};
    for (const key of config.inputs) {
      const value = values[key];
      if (value === undefined || value === null || value === '') continue;
      const text = String(value);
      const pattern = config.patterns?.[key];
      if (pattern && !pattern.test(text)) {
        throw new AdminApiError(400, `${key} 값 형식이 올바르지 않습니다: ${text}`);
      }
      inputs[key] = text;
    }

    // dry_run 을 빼고 보내면 워크플로 기본값('false')으로 실제 발행된다 → 'true' 가 아니면 실제 발행으로 본다
    if (config.live && config.live(inputs)) requireLivePublish(config.liveNote);

    const result = await dispatchWorkflow(config.file, inputs, DEFAULT_REPO);
    if (!result.ok) return githubFailure(result, config.file);

    return NextResponse.json({
      success: true,
      action,
      repo: result.repo,
      message: `${config.file} 실행 요청 완료 (${result.repo})`,
    });
  } catch (err) {
    return errorResponse(err);
  }
}
