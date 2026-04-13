import { createClient } from '@supabase/supabase-js';

/**
 * 사이트별 GitHub 인증정보 조회
 * 1순위: sites.config에 저장된 고객 fork 정보
 * 2순위: 환경변수 (admin / self-hosted)
 */
export async function getGitHubCredentials(siteId) {
  // 고객 fork 정보 조회 (sites.config.github_token / github_repo)
  if (siteId) {
    try {
      const supabase = createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      );
      const { data } = await supabase
        .from('sites')
        .select('config')
        .eq('id', siteId)
        .single();

      if (data?.config?.github_token && data?.config?.github_repo) {
        return {
          token: data.config.github_token,
          repo: data.config.github_repo,
          source: 'site',
        };
      }
    } catch {
      // fall through to env vars
    }
  }

  // 환경변수 fallback (admin / self-hosted)
  if (process.env.GITHUB_TOKEN) {
    return {
      token: process.env.GITHUB_TOKEN,
      repo: process.env.GITHUB_REPO || 'planxs-ai/wp-auto',
      source: 'env',
    };
  }

  return null;
}
