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
// No content writes, tracking, ads, redirects or crawler-specific output.
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

add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('planx-reading-experience', plugin_dir_url(__FILE__) . 'reader.css', array(), '1.0.0');
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
