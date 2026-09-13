<?php
/**
 * PlanX 읽기 화면 — WPCode 스니펫 1438 대체본 (목차 필터 없음, 2026-09-13)
 *
 * 원본: origin/codex/adsense-editorial-readiness:wordpress/planx-reading-experience/wpcode-snippet.php
 *
 * 원본과 달라진 점
 *  1. 단일 글 목차 제거 필터(원본 81-112행, DOMDocument 파싱)를 통째로 뺐다.
 *     짝 없는 </div>가 있는 글 6편(1311·1107·1307·1172·1236·1118)의 공개 본문을 자르던 원인이다.
 *  2. 1208·옛 한글 정책 주소 → /privacy-policy/ 301을 redirect_canonical(우선순위 10)보다 먼저
 *     (우선순위 0) 실행해 한 번에 이동한다. 1208을 나중에 비공개·초안으로 돌려도 계속 작동한다.
 *  3. 홈·목록 요약 출처: Rank Math 메타 설명 → 발췌 → 본문. 본문에서는 '핵심 요약:' 머리말,
 *     ``` 코드 울타리, 목록·표·제목·'이 글의 순서' 표시를 걷어 낸다.
 *     메타 설명·발췌에 자동 생성 흔적(끝이 '...'인 절단, 붙은 번호 목록, ```, '이 글의 순서',
 *     기호 나열)이 있으면 쓰지 않고 다음 출처로 넘긴다. 엔진이 만든 메타 설명은 본문 앞 문장 3개를
 *     157자에서 자르고 '...'를 붙인 값이라 대부분 여기서 걸린다. 설정 'trace_filter'로 끌 수 있다.
 *  4. 문구: 'PLANX AI' → 'PlanX', 사이트 소개를 '재테크 · AI 도구 · 생활경제'로 바꿨다.
 *  5. 비밀번호 보호 글은 요약을 만들지 않는다(원본은 보호 글 본문 앞부분을 홈에 노출).
 *  6. 모든 콜백은 필요한 함수가 없거나 예외가 나면 원래 화면을 그대로 둔다.
 *     planx-ai.com이 아닌 사이트에 잘못 붙여 넣으면 아무 일도 하지 않는다.
 *
 * 화면 표시만 바꾼다. 저장된 글·페이지·설정은 건드리지 않는다. 비활성화하면 테마 원래 화면으로 돌아간다.
 * PHP 7.4 이상. 추적·광고·크롤러 전용 출력 없음.
 */
if (!defined('ABSPATH')) { return; }

// 같은 코드가 두 번 실행돼도(스니펫 중복 등록) 한 번만 적용한다.
if (defined('PLANX_RX_LOADED')) { return; }
define('PLANX_RX_LOADED', '2026-09-13');

if (!function_exists('add_action') || !function_exists('add_filter')) { return; }

// ── 설정: 문구·링크·주소는 여기서만 고친다 ─────────────────────────────
$planx_rx_cfg = array(
    'host'             => 'planx-ai.com',  // 이 호스트에서만 작동
    'summary_len'      => 180,             // 홈·목록 요약 최대 글자 수
    'summary_min'      => 20,              // 메타 설명·발췌가 이보다 짧으면 다음 출처로 넘어감
    // 메타 설명·발췌에 자동 생성 흔적이 있으면 건너뛰고 다음 출처(발췌 → 본문)를 쓴다.
    // false로 바꾸면 흔적 검사 없이 메타 설명을 무조건 1순위로 쓴다(엔진 메타의 '...' 절단이 홈에 그대로 나옴).
    'trace_filter'     => true,
    'welcome'          => array(
        'eyebrow' => 'PlanX · 재테크 · AI 도구 · 생활경제',
        'title'   => '나에게 맞는 선택 기준을 찾으세요.',
        'body'    => '재테크, AI 도구, 생활경제 주제의 비교 기준과 확인할 자료, 실행 순서를 정리합니다.',
    ),
    // 하단 정보 링크. 공개(publish) 상태인 페이지만 표시한다. slug 또는 id로 지정.
    'info_links'       => array(
        array('slug' => 'about',            'label' => '소개'),
        array('slug' => 'contact',          'label' => '문의'),
        array('slug' => 'privacy-policy',   'label' => '개인정보처리방침'),
        array('slug' => 'editorial-policy', 'label' => '작성·정정 원칙'),
        // 페이지 15·18의 contact@example.com을 고친 뒤 아래 두 줄의 주석을 풀어 추가한다.
        // array('id' => 15, 'label' => '면책·제휴 고지'),
        // array('id' => 18, 'label' => '이용약관'),
    ),
    'legacy_policy_id' => 1208,             // WP 샘플 개인정보 페이지(옛 한글 주소)
    'policy_slug'      => 'privacy-policy', // 301 도착지
);

// 호스트 확인: 다른 사이트(bomissu 등)나 스테이징에 붙여 넣어도 PlanX 문구가 새지 않게 한다.
// 스테이징에서 시험하려면 wp-config.php에 define('PLANX_RX_FORCE', true); 를 둔다.
$planx_rx_host = (function_exists('wp_parse_url') && function_exists('home_url'))
    ? strtolower((string) wp_parse_url(home_url(), PHP_URL_HOST)) : '';
if (strpos($planx_rx_host, 'www.') === 0) { $planx_rx_host = substr($planx_rx_host, 4); }
if ($planx_rx_host !== $planx_rx_cfg['host'] && !(defined('PLANX_RX_FORCE') && PLANX_RX_FORCE)) { return; }

// ── 도우미 ─────────────────────────────────────────────────────────
// 필요한 WordPress 함수가 모두 있을 때만 true.
$planx_rx_has = function (array $functions) {
    foreach ($functions as $fn) {
        if (!function_exists($fn)) { return false; }
    }
    return true;
};

// preg_replace가 실패(잘못된 UTF-8, 역추적 한도)하면 입력을 그대로 돌려준다.
$planx_rx_re = function ($pattern, $replacement, $subject) {
    $out = preg_replace($pattern, $replacement, (string) $subject);
    return $out === null ? (string) $subject : $out;
};

// HTML 조각 → 한 줄 텍스트. 요약에 쓸모없는 블록(목록·표·제목·코드 등)은 먼저 걷어 낸다.
$planx_rx_html_to_text = function ($html, $drop_blocks) use ($planx_rx_re) {
    $html = (string) $html;
    if (function_exists('strip_shortcodes')) { $html = strip_shortcodes($html); }
    $html = $planx_rx_re('/<(script|style|noscript|svg)\b[^>]*>.*?<\/\1\s*>/isu', ' ', $html);
    if ($drop_blocks) {
        $html = $planx_rx_re('/<(figure|table|ol|ul|pre|nav|form|h[1-6])\b[^>]*>.*?<\/\1\s*>/isu', ' ', $html);
    }
    // 블록 경계에 공백을 넣어 '…합니다.다음 문단'처럼 붙지 않게 한다.
    $html = $planx_rx_re('/<(?:br\s*\/?|\/(?:p|div|li|h[1-6]|section|blockquote|td|th|tr))\s*>/iu', ' ', $html);
    $text = function_exists('wp_strip_all_tags') ? wp_strip_all_tags($html) : strip_tags($html);
    return html_entity_decode($text, ENT_QUOTES, 'UTF-8');
};

// 자동 생성 흔적(머리말·코드 울타리·목차 표시)을 걷어 내고 공백을 정리한다.
$planx_rx_clean = function ($text) use ($planx_rx_re) {
    $text = $planx_rx_re('/```[a-z0-9_-]*/iu', ' ', $text);
    $text = $planx_rx_re('/이 글의 순서\s*[:：]?/u', ' ', $text);
    $text = $planx_rx_re('/[\s\x{00A0}]+/u', ' ', $text);
    $text = trim($text);
    $text = $planx_rx_re('/^[\p{So}\p{P}\p{M}\s]{0,6}(?:최종\s*)?핵심\s*요약\s*[:：]?\s*/u', '', $text);
    $text = $planx_rx_re('/^(?:요약|TL;?DR)\s*[:：]\s*/iu', '', $text);
    return trim($text);
};

$planx_rx_len = function ($text) {
    return function_exists('mb_strlen') ? mb_strlen($text, 'UTF-8') : strlen($text);
};

// 글자 수 기준으로 자르고, 가능하면 단어 경계에서 끊는다.
$planx_rx_cut = function ($text, $limit) use ($planx_rx_re, $planx_rx_len) {
    if ($planx_rx_len($text) <= $limit) { return $text; }
    if (!function_exists('mb_substr')) {
        return function_exists('wp_html_excerpt') ? wp_html_excerpt($text, $limit, '…') : substr($text, 0, $limit * 3) . '…';
    }
    $cut = mb_substr($text, 0, $limit, 'UTF-8');
    if (function_exists('mb_strrpos')) {
        $space = mb_strrpos($cut, ' ', 0, 'UTF-8');
        if ($space !== false && $space > (int) ($limit * 0.7)) { $cut = mb_substr($cut, 0, $space, 'UTF-8'); }
    }
    return $planx_rx_re('/[\s,.·…]+$/u', '', $cut) . '…';
};

// Rank Math 메타 설명. 변수(%excerpt% 등)는 Rank Math로 풀고, 풀 수 없으면 쓰지 않는다.
$planx_rx_rank_math = function ($post) {
    if (!function_exists('get_post_meta')) { return ''; }
    try {
        $desc = get_post_meta($post->ID, 'rank_math_description', true);
        if (!is_string($desc) || trim($desc) === '') { return ''; }
        $var = '/%[a-z_]+(?:\([^)%]*\))?%/i';
        if (preg_match($var, $desc)) {
            $helper = array('RankMath\\Helper', 'replace_vars');
            $desc = (class_exists('RankMath\\Helper') && is_callable($helper))
                ? (string) call_user_func($helper, $desc, $post) : '';
            if (preg_match($var, $desc)) { return ''; }
        }
        return $desc;
    } catch (\Throwable $e) {
        return '';
    }
};

// 저장된 요약 문구(메타 설명·발췌)에 자동 생성 흔적이 있으면 true → 쓰지 않고 다음 출처로 넘긴다.
// 엔진(scripts/main.py)은 메타 설명이 따로 없으면 태그만 벗긴 본문 앞 문장 3개를 이어 붙이고
// 160자를 넘으면 157자에서 잘라 '...'를 붙인다. 메타·발췌에서는 목록 블록을 걷어 낼 수 없으므로
// 흔적이 보이면 목록·표를 걷어 내는 본문 경로가 낫다. $raw는 원문, $text는 정리된 한 줄 텍스트.
$planx_rx_has_trace = function ($raw, $text) use ($planx_rx_cfg) {
    if (empty($planx_rx_cfg['trace_filter'])) { return false; }
    if (preg_match('/```|이 글의 순서|목차\s*[:：]/u', (string) $raw)) { return true; }      // 코드 울타리·목차 표시
    if (preg_match('/(?:\.{3}|…)\]?$/u', $text)) { return true; }                            // 문장 중간 절단
    // 번호 목록 조각: 번호('1. ')가 2개 이상이고 그중 하나라도 앞 글자에 붙어 있으면('기초2. ') 태그가 벗겨진 목록이다.
    // 'GPT-4. '처럼 붙은 번호 하나뿐이거나 '2026. 3. 1.'처럼 띄어 쓴 날짜는 통과한다.
    $glued = (int) preg_match_all('/[^\s\d.,]\d{1,2}\.(?=\s|$)/u', $text);
    if ($glued >= 1 && (int) preg_match_all('/(?:^|[^\d.,])\d{1,2}\.(?=\s|$)/u', $text) >= 2) { return true; }
    if ((int) preg_match_all('/\p{So}/u', $text) >= 2) { return true; }                      // 기호 나열(📈…★)
    return false;
};

// 요약 출처 우선순위: Rank Math 메타 설명 → 발췌 → 본문. 메타·발췌는 흔적 검사를 통과할 때만 쓴다.
$planx_rx_summary = function ($post) use ($planx_rx_cfg, $planx_rx_html_to_text, $planx_rx_clean, $planx_rx_len, $planx_rx_cut, $planx_rx_rank_math, $planx_rx_has_trace) {
    $limit = (int) $planx_rx_cfg['summary_len'];
    foreach (array($planx_rx_rank_math($post), (string) $post->post_excerpt) as $source) {
        if ($source === '') { continue; }
        $text = $planx_rx_clean($planx_rx_html_to_text($source, false));
        if ($planx_rx_len($text) < (int) $planx_rx_cfg['summary_min']) { continue; }
        if ($planx_rx_has_trace($source, $text)) { continue; }
        return $planx_rx_cut($text, $limit);
    }
    $text = $planx_rx_clean($planx_rx_html_to_text((string) $post->post_content, true));
    return $text === '' ? '' : $planx_rx_cut($text, $limit);
};

// ── 1. 홈·분류·검색 목록: 본문 대신 요약 + '내용 읽기' ─────────────────────
add_filter('the_content', function ($content) use ($planx_rx_has, $planx_rx_summary) {
    if (!$planx_rx_has(array('is_admin', 'is_feed', 'in_the_loop', 'is_main_query', 'is_home', 'is_archive', 'is_search',
        'get_post', 'post_password_required', 'get_permalink', 'get_the_title', 'esc_html', 'esc_url'))) { return $content; }
    try {
        if (is_admin() || is_feed() || !in_the_loop() || !is_main_query()) { return $content; }
        if (!(is_home() || is_archive() || is_search())) { return $content; }
        $post = get_post();
        if (!$post || $post->post_type !== 'post') { return $content; }
        if (post_password_required($post)) { return $content; }
        $summary = $planx_rx_summary($post);
        $link = '<p><a class="planx-read-more" href="' . esc_url(get_permalink($post)) . '">내용 읽기<span class="screen-reader-text">: '
            . esc_html(get_the_title($post)) . '</span></a></p>';
        return ($summary === '' ? '' : '<p class="planx-summary">' . esc_html($summary) . '</p>') . $link;
    } catch (\Throwable $e) {
        return $content;
    }
}, 99);

// ── 2. 읽기 화면 CSS (원본과 동일, 변수 없는 고정 문자열) ─────────────────
add_action('wp_head', function () {
    echo '<style id="planx-reading-experience">' . <<<'PLANXCSS'
:root { --planx-paper:#fffdf8; --planx-ink:#382f24; --planx-gold:#936b2f; --planx-line:#e9ddc9; }
body { background:var(--planx-paper); color:var(--planx-ink); }
.planx-welcome { margin:0 0 30px; padding:32px; background:#fbf3e4; border:1px solid var(--planx-line); border-radius:16px; }
.planx-welcome h2 { margin:8px 0 14px; font-size:clamp(24px,3vw,36px); line-height:1.45; letter-spacing:-.03em; }
.planx-eyebrow { color:var(--planx-gold); font-size:12px; font-weight:700; letter-spacing:.06em; }
.planx-summary { line-height:1.8; color:#635744; }
.planx-read-more { font-weight:700; color:#79531e; text-decoration:underline; text-underline-offset:4px; }
.planx-information { display:flex; flex-wrap:wrap; justify-content:center; gap:12px 24px; padding:24px; border-top:1px solid var(--planx-line); font-size:14px; background:#fbf5e9; }
.planx-information a { color:#694c25; }
.entry-content { overflow-wrap:anywhere; }
.entry-content p { line-height:1.9!important; color:var(--planx-ink)!important; }
.entry-content strong[style] { color:var(--planx-ink)!important; background:linear-gradient(transparent 65%,#f2dfb9 65%)!important; }
.entry-content div[style*="#f5f3ff"], .entry-content div[style*="#ede9fe"], .entry-content .tldr-box { background:#fff6e6!important; border-color:#d4b579!important; }
.entry-content table { display:block; width:100%; overflow-x:auto; border-collapse:collapse; margin:24px 0; }
.entry-content th,.entry-content td { padding:12px; border:1px solid var(--planx-line); vertical-align:top; }
.entry-content th { background:#f7ecd8; color:var(--planx-ink); }
.entry-content a:focus-visible,.planx-information a:focus-visible,.planx-read-more:focus-visible { outline:3px solid #936b2f; outline-offset:4px; }
.entry-content pre { overflow:auto; padding:18px; background:#fbf3e4; color:#382f24; }
@media(max-width:600px) { .planx-welcome {padding:22px;} .entry-content {font-size:16px;} .entry-title {font-size:26px;line-height:1.45;} }

PLANXCSS
    . '</style>';
});

// ── 3. 홈 첫 페이지 안내 ─────────────────────────────────────────────
add_action('loop_start', function ($query) use ($planx_rx_cfg, $planx_rx_has) {
    static $shown = false;
    if ($shown || !$planx_rx_has(array('is_admin', 'is_home', 'is_paged', 'esc_html'))) { return; }
    try {
        if (is_admin() || !is_home() || is_paged() || !is_object($query) || !method_exists($query, 'is_main_query') || !$query->is_main_query()) { return; }
        $shown = true;
        $w = $planx_rx_cfg['welcome'];
        echo '<section class="planx-welcome" aria-label="사이트 안내"><p class="planx-eyebrow">' . esc_html($w['eyebrow'])
            . '</p><h2>' . esc_html($w['title']) . '</h2><p>' . esc_html($w['body']) . '</p></section>';
    } catch (\Throwable $e) {
        return;
    }
});

// ── 4. 하단 정보 링크 ───────────────────────────────────────────────
add_action('wp_footer', function () use ($planx_rx_cfg, $planx_rx_has) {
    if (!$planx_rx_has(array('get_page_by_path', 'get_post', 'get_permalink', 'esc_url', 'esc_html'))) { return; }
    try {
        $links = array();
        $seen = array();
        foreach ($planx_rx_cfg['info_links'] as $item) {
            $page = isset($item['id']) ? get_post((int) $item['id']) : get_page_by_path((string) $item['slug']);
            if (!$page || $page->post_type !== 'page' || $page->post_status !== 'publish') { continue; }
            if ((int) $page->ID === (int) $planx_rx_cfg['legacy_policy_id'] || isset($seen[$page->ID])) { continue; }
            $url = get_permalink($page);
            if (!$url) { continue; }
            $seen[$page->ID] = true;
            $links[] = '<a href="' . esc_url($url) . '">' . esc_html($item['label']) . '</a>';
        }
        if ($links) { echo '<nav class="planx-information" aria-label="사이트 정보">' . implode(' ', $links) . '</nav>'; }
    } catch (\Throwable $e) {
        return;
    }
});

// ── 5. 1208·옛 한글 정책 주소 → /privacy-policy/ 301 (한 번에) ─────────────
// WP 샘플 개인정보 페이지 1208은 지우지 않고 보존하되, 독자는 관리 중인 정책 페이지로 보낸다.
// 우선순위 0: redirect_canonical(10)이 ?page_id=1208을 한글 주소로 먼저 보내는 2단계 이동을 막는다.
// 1208이 공개면 is_page(1208)로, 비공개·초안이면 요청 변수(page_id, pagename)로 알아본다.
add_action('template_redirect', function () use ($planx_rx_cfg, $planx_rx_has) {
    if (!$planx_rx_has(array('is_page', 'get_query_var', 'get_post', 'get_page_by_path', 'get_permalink', 'wp_safe_redirect'))) { return; }
    try {
        $legacy_id = (int) $planx_rx_cfg['legacy_policy_id'];
        $hit = is_page($legacy_id) || (int) get_query_var('page_id') === $legacy_id;
        if (!$hit) {
            $requested = trim((string) get_query_var('pagename'), '/');
            $legacy = $requested === '' ? null : get_post($legacy_id);
            $name = $legacy ? preg_replace('/__trashed$/', '', (string) $legacy->post_name) : '';
            $hit = $name !== '' && strtolower(rawurldecode($requested)) === strtolower(rawurldecode($name));
        }
        if (!$hit) { return; }
        $policy = get_page_by_path((string) $planx_rx_cfg['policy_slug']);
        if (!$policy || $policy->post_status !== 'publish' || (int) $policy->ID === $legacy_id) { return; }
        $target = get_permalink($policy);
        if (!$target) { return; }
        wp_safe_redirect($target, 301, 'PlanX reading snippet');
        exit;
    } catch (\Throwable $e) {
        return;
    }
}, 0);
