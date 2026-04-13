import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getGitHubCredentials } from '@/lib/github-helper';

// Each workflow and its allowed input keys (GitHub 422s on unknown inputs)
const WORKFLOW_CONFIG = {
  'setup-menu': {
    file: 'setup-menu.yml',
    inputs: ['wp_url', 'wp_username', 'wp_app_password', 'site_id'],
  },
  'setup-pages': {
    file: 'setup-pages.yml',
    inputs: ['wp_url', 'wp_username', 'wp_app_password', 'site_id', 'blog_owner', 'blog_desc', 'contact_email'],
  },
  'inject-css': {
    file: 'inject-css.yml',
    inputs: ['wp_url', 'wp_username', 'wp_app_password', 'wp_login_password', 'site_id'],
  },
  'inject-css-posts': {
    file: 'inject-css-posts.yml',
    inputs: ['wp_url', 'wp_username', 'wp_app_password', 'dry_run', 'force_update'],
  },
  'publish': {
    file: 'publish.yml',
    inputs: ['site_id', 'count', 'dry_run', 'pipeline', 'niche'],
  },
};

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

async function getSiteCredentials(siteId) {
  if (!siteId) return null;
  const supabase = getSupabaseAdmin();
  const { data } = await supabase
    .from('sites')
    .select('wp_url, domain, config')
    .eq('id', siteId)
    .single();
  if (!data) return null;
  return {
    wp_url: data.wp_url,
    domain: data.domain,
    wp_username: data.config?.wp_username || '',
    wp_app_password: data.config?.wp_app_password || '',
    wp_login_password: data.config?.wp_login_password || data.config?.wp_app_password || '',
  };
}

export async function POST(request) {
  const user = await verifyAuth(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { action, siteId, inputs } = await request.json();

  const config = WORKFLOW_CONFIG[action];
  if (!config) {
    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  }

  // 사이트별 GitHub 인증정보 조회
  const gh = await getGitHubCredentials(siteId);

  // 권한 확인: 고객 fork(site 소유자) 또는 admin
  const supabaseAdmin = getSupabaseAdmin();
  if (gh?.source === 'site') {
    // 고객 fork — 사이트 소유자만 허용
    const { data: userSite } = await supabaseAdmin
      .from('user_sites')
      .select('role')
      .eq('user_id', user.id)
      .eq('site_id', siteId)
      .single();
    if (!userSite) {
      return NextResponse.json({ error: '해당 사이트에 대한 권한이 없습니다.' }, { status: 403 });
    }
  } else {
    // env 변수 fallback — admin만 허용
    const { data: profile } = await supabaseAdmin
      .from('user_profiles')
      .select('role')
      .eq('id', user.id)
      .single();
    if (profile?.role !== 'admin') {
      return NextResponse.json({
        error: '관리자만 워크플로우를 실행할 수 있습니다.',
        guide: 'GitHub 연동에서 Fork 저장소를 먼저 등록하세요.',
      }, { status: 403 });
    }
  }

  if (!gh) {
    return NextResponse.json({
      error: 'GitHub 인증정보가 없습니다.',
      guide: '설정 > GitHub 연동에서 Fork 저장소와 토큰을 먼저 등록하세요.',
    }, { status: 400 });
  }

  // Fetch site credentials from Supabase
  const creds = await getSiteCredentials(siteId);
  if (!creds || !creds.wp_url) {
    return NextResponse.json({
      error: '사이트 인증정보를 찾을 수 없습니다. 설정에서 사이트를 먼저 연결해주세요.',
      siteId,
    }, { status: 400 });
  }

  // Build all possible values, then filter to only allowed inputs
  const allValues = {
    ...(inputs || {}),
    wp_url: creds.wp_url,
    wp_username: creds.wp_username,
    wp_app_password: creds.wp_app_password,
    wp_login_password: creds.wp_login_password,
    site_id: siteId || '',
  };

  // Only include keys that the target workflow defines (prevents GitHub 422)
  const workflowInputs = {};
  for (const key of config.inputs) {
    if (allValues[key] !== undefined && allValues[key] !== '') {
      workflowInputs[key] = String(allValues[key]);
    }
  }

  const [owner, repo] = gh.repo.split('/');

  const resp = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${config.file}/dispatches`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${gh.token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main', inputs: workflowInputs }),
    }
  );

  if (resp.status === 204) {
    return NextResponse.json({
      success: true, action,
      message: `${action} triggered on ${gh.repo} for ${creds.domain}`,
    });
  }

  const errorBody = await resp.text();
  return NextResponse.json({
    error: `GitHub API failed: ${resp.status}`,
    detail: errorBody,
    guide: resp.status === 404
      ? 'Fork 저장소를 확인하세요. publish.yml이 존재하는지 확인해주세요.'
      : resp.status === 403
      ? 'GitHub Token 권한을 확인하세요 (repo + workflow 스코프 필요).'
      : null,
    debug: { repo: gh.repo, workflow: config.file, site: creds.domain },
  }, { status: resp.status });
}
