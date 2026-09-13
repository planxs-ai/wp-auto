<?php
/**
 * Plugin Name: PlanX Reading Experience
 * Description: Compact archive summaries, warm readable styles and published information-page links.
 * Version: 1.0.0
 * Requires at least: 6.0
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) { exit; }

// Presentation only: disabling the plugin restores the original theme output.
// No content writes, tracking, ads or crawler-specific output; one legacy-policy redirect.
add_filter('the_content', function ($content) {
    if (is_admin() || is_feed() || !in_the_loop() || !is_main_query()) { return $content; }
    if (!(is_home() || is_archive() || is_search())) { return $content; }
    $post = get_post();
    if (!$post || $post->post_type !== 'post') { return $content; }
    $raw = $post->post_excerpt ?: $post->post_content;
    $raw = preg_replace('/<script\b[^>]*>.*?<\/script>/is', '', $raw);
    $raw = preg_replace('/<style\b[^>]*>.*?<\/style>/is', '', $raw);
    $text = trim(preg_replace('/\s+/u', ' ', wp_strip_all_tags(strip_shortcodes($raw))));
    $summary = wp_html_excerpt($text, 180, '…');
    return '<p class="planx-summary">' . esc_html($summary) . '</p><p><a class="planx-read-more" href="' . esc_url(get_permalink($post)) . '">내용 읽기<span class="screen-reader-text">: ' . esc_html(get_the_title($post)) . '</span></a></p>';
}, 99);

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

add_action('loop_start', function ($query) {
    static $shown = false;
    if ($shown || is_admin() || !is_home() || !$query->is_main_query() || is_paged()) { return; }
    $shown = true;
    echo '<section class="planx-welcome" aria-label="사이트 안내"><p class="planx-eyebrow">PLANX AI · 읽고, 비교하고, 확인하기</p><h2>나에게 필요한 선택 기준을 찾으세요.</h2><p>디지털 도구와 생활 정보의 비교 기준, 확인할 자료와 실행 순서를 정리합니다.</p></section>';
});

add_action('wp_footer', function () {
    $links = array();
    foreach (array('about' => '소개', 'contact' => '문의', 'privacy-policy' => '개인정보처리방침', 'editorial-policy' => '작성·정정 원칙') as $slug => $label) {
        $page = get_page_by_path($slug);
        if ($page && $page->post_status === 'publish') {
            $links[] = '<a href="' . esc_url(get_permalink($page)) . '">' . esc_html($label) . '</a>';
        }
    }
    if ($links) { echo '<nav class="planx-information" aria-label="사이트 정보">' . implode(' ', $links) . '</nav>'; }
});

// The public audit identified this unedited WordPress sample policy on this site.
// Preserve its record and route readers to the maintained policy instead of deleting it.
add_action('template_redirect', function () {
    if (wp_parse_url(home_url(), PHP_URL_HOST) !== 'planx-ai.com' || !is_page(1208)) { return; }
    $policy = get_page_by_path('privacy-policy');
    if ($policy && $policy->post_status === 'publish' && (int)$policy->ID !== 1208) {
        wp_safe_redirect(get_permalink($policy), 301);
        exit;
    }
});

// Remove duplicate TOCs only in rendered articles, preserving every stored post.
add_filter('the_content', function ($content) {
    if (is_admin() || is_feed() || !is_singular('post') || !in_the_loop() || !is_main_query() || !class_exists('DOMDocument')) { return $content; }
    if (strpos($content, '이 글의 순서') === false && strpos($content, '목차') === false) { return $content; }
    $doc = new DOMDocument('1.0', 'UTF-8');
    $previous = libxml_use_internal_errors(true);
    $ok = $doc->loadHTML('<?xml encoding="UTF-8"><html><body><div id="planx-toc-root">' . $content . '</div></body></html>', LIBXML_NONET);
    libxml_clear_errors();
    libxml_use_internal_errors($previous);
    if (!$ok) { return $content; }
    $xp = new DOMXPath($doc);
    $root = $doc->getElementById('planx-toc-root');
    if (!$root) { return $content; }
    $candidates = array(); $keep = null;
    foreach ($xp->query('.//div[(./ol or ./ul) and not(.//h2 or .//h3)]', $root) as $node) {
        $text = trim(preg_replace('/\s+/u', ' ', $node->textContent));
        $length = function_exists('mb_strlen') ? mb_strlen($text, 'UTF-8') : strlen($text);
        $prefix = function_exists('mb_substr') ? mb_substr($text, 0, 70, 'UTF-8') : substr($text, 0, 210);
        if ($length >= 1500 || !preg_match('/이 글의 순서|^목차/u', $prefix)) { continue; }
        $candidates[] = $node;
        if (!$keep && $xp->query('.//a[starts-with(@href,"#")]', $node)->length) { $keep = $node; }
    }
    if (count($candidates) < 2 || !$keep) { return $content; }
    foreach ($candidates as $node) {
        if ($node !== $keep && $node->parentNode && !$xp->query('.//a[starts-with(@href,"#")]', $node)->length) {
            $node->parentNode->removeChild($node);
        }
    }
    $output = '';
    foreach ($root->childNodes as $node) { $output .= $doc->saveHTML($node); }
    return $output;
}, 98);
