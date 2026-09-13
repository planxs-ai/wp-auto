"""발행 엔진 안전장치 회귀 테스트 (네트워크·유료 API 호출 없음, 전부 모킹).

실행: python -m unittest discover -s tests -v   (저장소 루트에서)
PR #3 조각 A의 테스트를 옮기고, 2026-09-13 결정(초안 기본·지인 끊기·절단 금지)을 검증하는 항목을 더했다.
"""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from scripts import etf_report as etf
from scripts import html_cleanup
from scripts import main as engine
from scripts import site_guard

ROOT = Path(__file__).resolve().parents[1]

# 프롬프트에 다시 들어오면 안 되는 날조 유도 문구 (handoff_reviews.json ENG-3)
FORBIDDEN_PROMPT_PHRASES = (
    '[수치]',
    '[프레임워크',
    '상위 5%',
    '상위 1%',
    '15년',
    '기회비용이 발생',
    '더 효과적입니다',
    '모든 주장을 뒷받침',
    '범위형',
    '일반적으로 알려진 바에 따르면',
    '업계 전문가들의 분석에 의하면',
    'Before→After 변화 수치',
    '직접 경험:',
    '실제 경험 문단" 1개 필수',
    '시스템이 답입니다',
    'personally researched and tested',
)

PROMPT_CATEGORIES = ('', 'IT & 테크 리뷰', '부업 & 수익화', '정부지원 & 보조금',
                     '생활비·살림', 'news-sbs', 's-semi', 'side-income')

# 옛 _remove_adsense_violations가 쓰던 블록 정규식 (절단 재현용)
OLD_CUTTING_PATTERN = r'<div[^>]*>.*?쿠팡\s*파트너스.*?</div>'


class PublisherTests(unittest.TestCase):
    def test_publisher_defaults_to_draft_and_verifies_response(self):
        publisher = engine.WordPressPublisher()
        publisher._get_site_name = Mock(return_value='Test')
        response = Mock()
        response.json.return_value = {'id': 1, 'status': 'draft'}
        with patch('requests.post', return_value=response) as post:
            self.assertEqual(publisher.publish('Title', '<p>Body</p>')['status'], 'draft')
            self.assertEqual(post.call_args.kwargs['json']['status'], 'draft')
            self.assertNotIn('rank_math_robots', post.call_args.kwargs['json'].get('meta', {}))
            # 요청과 다른 상태로 저장되면 성공으로 치지 않는다
            response.json.return_value = {'id': 1, 'status': 'publish'}
            self.assertEqual(publisher.publish('Title', 'Body')['status'], 'failed')
            with self.assertRaises(ValueError):
                publisher.publish('Title', 'Body', status='future')

    def test_supabase_log_leaves_published_at_empty_for_drafts(self):
        with patch.object(engine, 'SUPABASE_URL', 'https://db.test'), \
                patch.object(engine, 'SUPABASE_KEY', 'test-only'):
            logger = engine.SupabaseLogger()
            with patch('requests.post') as post:
                logger.log_publish({'title': 't', 'status': 'draft'})
                self.assertIsNone(post.call_args.kwargs['json']['published_at'])
                logger.log_publish({'title': 't', 'status': 'published'})
                self.assertIsNotNone(post.call_args.kwargs['json']['published_at'])


class PromptTests(unittest.TestCase):
    def test_prompt_modes_include_evidence_rules(self):
        for lang in ('ko', 'en'):
            for adsense in (True, False):
                for golden in (True, False):
                    for category in PROMPT_CATEGORIES:
                        for prompt in engine.get_prompts(lang, adsense, category, golden):
                            self.assertIn('Do not invent firsthand use', prompt)

    def test_prompts_contain_no_fabrication_directives(self):
        texts = list(engine.GOLDEN_INTRO_HOOKS)
        texts += [engine.GOLDEN_DRAFT_PROMPT_KO, engine.GOLDEN_POLISH_PROMPT_KO,
                  engine.DRAFT_PROMPT_KO, engine.POLISH_PROMPT_KO, engine.DRAFT_PROMPT_EN,
                  engine.ADSENSE_DRAFT_PROMPT_KO, engine.ADSENSE_DRAFT_PROMPT_EN]
        for style in engine.NICHE_STYLES.values():
            texts += [style['tone'], style.get('value_focus', ''), style['must_blocks']]
        # get_prompts는 훅을 무작위로 고르므로 훅 전체를 직접 검사하고, 조합 결과도 따로 검사한다.
        for lang in ('ko', 'en'):
            for adsense in (True, False):
                for golden in (True, False):
                    for category in PROMPT_CATEGORIES:
                        texts += list(engine.get_prompts(lang, adsense, category, golden))
        for text in texts:
            for phrase in FORBIDDEN_PROMPT_PHRASES:
                self.assertNotIn(phrase, text)
        for style in engine.NICHE_STYLES.values():
            self.assertNotRegex(style['must_blocks'], r'\d+%가')


class ContentShapeTests(unittest.TestCase):
    def test_formatter_no_longer_appends_cta_box(self):
        self.assertFalse(hasattr(engine.ContentFormatter, '_ensure_cta'))
        formatter = engine.ContentFormatter()
        for category in ('', '부업 & 수익화', '생활비·살림'):
            out = formatter.format('<h2>제목</h2><p>본문 문단입니다.</p>', keyword='x', category=category)
            self.assertNotIn('지금 바로 확인해보세요', out)

    def test_quality_gate_has_no_cta_points(self):
        _, details = engine.QualityGate().score('<h2>a</h2><p>지금 바로 클릭해서 확인해보세요</p>', 'a')
        self.assertNotIn('cta', details)

    def test_quality_gate_still_scores_out_of_100(self):
        # CTA 5점을 뺀 뒤에도 기준점(75/80/85/90)의 의미가 같도록 100점 만점으로 환산한다.
        para = '<p>' + '가' * 380 + '</p>'  # 15문단 × 380자 = 5,700자 (길이 만점), 평균 380자 (문단 만점)
        sections = ''.join(f'<h2>예금 금리 비교 {i}</h2>{para * 3}' for i in range(5))
        content = ('<div class="tldr-box">핵심 요약</div>' + sections
                   + '<strong>a</strong>' * 5 + '<blockquote>q</blockquote><div class="tip-box">t</div>'
                   + '<table><tr><td>1</td></tr></table><img src="a.jpg"><img src="b.jpg">'
                   + '<div class="faq-section"><h3>Q. 질문</h3></div>'
                   + '<script type="application/ld+json">{}</script>')
        score, details = engine.QualityGate().score(content, '예금 금리', has_image=True)
        self.assertEqual(details['raw_total'], '95/95')
        self.assertEqual(score, 100)
        low, low_details = engine.QualityGate().score('<p>짧음</p>', '예금')
        self.assertEqual(low, round(int(low_details['raw_total'].split('/')[0]) * 100 / 95))

    def test_html_cleanup_removes_duplicates_only(self):
        html = ('<div class="key-point"><strong>이 글의 순서</strong><ol><li>a</li></ol></div>'
                '<div class="toc"><strong>목차</strong><ol><li><a href="#s1">a</a></li></ol></div>'
                '<figure><img src="x.jpg"/></figure><p>본문</p><figure><img src="x.jpg"/></figure>')
        out, changes = html_cleanup.clean_html(html)
        self.assertEqual(changes, {'duplicate_images': 1, 'duplicate_tocs': 1})
        self.assertEqual(out.count('x.jpg'), 1)
        self.assertIn('href="#s1"', out)
        self.assertNotIn('이 글의 순서', out)
        plain = '<p>바꿀 것 없음</p>'
        self.assertIs(html_cleanup.clean_html(plain)[0], plain)
        with patch.object(html_cleanup, 'BeautifulSoup', None):
            self.assertIs(html_cleanup.clean_html(html)[0], html)

    def test_keyword_pools_exclude_affiliate_monetization_family(self):
        # 블로그·SNS 계정 수익화와 '자동 수익 시스템'도 같은 계열 (절단 13편 중 9편이 이 주제)
        banned = re.compile(r'쿠팡\s*파트너스|애드센스|블로그\s*수익화|인스타(그램)?\s*수익화|자동\s*수익\s*시스템')
        for name in ('keywords.json', 'keywords_bomissu.json'):
            data = json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
            hits = [k['keyword'] for k in data['keywords']
                    if banned.search(k.get('keyword', '') + ' ' + k.get('focus_keyword', ''))]
            self.assertEqual(hits, [], name)
        for niche in ('부업 & 수익화', 'side-income'):
            self.assertEqual([d for d in engine.NICHE_DOMAINS[niche] if banned.search(d)], [])
        self.assertNotIn('부업 & 수익화', engine.DEFAULT_FALLBACK_NICHES)


class KeywordManagerTests(unittest.TestCase):
    def test_never_recycles_and_skips_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            pool = {'keywords': [{'keyword': k, 'pipeline': 'autoblog'} for k in ('a b', 'c d', 'e f')]}
            (data / 'keywords.json').write_text(json.dumps(pool, ensure_ascii=False), encoding='utf-8')
            (data / 'used_keywords.json').write_text(json.dumps(['a b']), encoding='utf-8')
            with patch.object(engine, 'DATA', data), patch.object(engine, 'WP_URL', ''):
                engine.KeywordManager().quarantine('c d', 'cannibal_high', 'test')
                km = engine.KeywordManager()  # 디스크에서 다시 읽는다
                self.assertEqual([k['keyword'] for k in km.select(count=5)], ['e f'])
                km.mark_used('e f')
                # 전부 쓰였거나 격리됐으면 비어 있어야 한다. used를 초기화해 재활용하면 안 된다.
                self.assertEqual(km.select(count=5), [])
            used = json.loads((data / 'used_keywords.json').read_text(encoding='utf-8'))
            self.assertEqual(used, ['a b', 'e f'])
            saved = json.loads((data / 'quarantined_keywords.json').read_text(encoding='utf-8'))
            self.assertEqual([q['keyword'] for q in saved], ['c d'])


class PipelineTests(unittest.TestCase):
    def run_case(self, stage=1, review='true', dry=False, score=95, warnings=None,
                 content='<title>Test</title><p>Body</p>', conflicts=None, real_violation_check=False,
                 dashboard=None, publish_status='draft', env_unset=False, site_id='site-1', extra=(),
                 wp_url=None):
        with ExitStack() as stack:
            env = {'FORCE_RUN': 'true'}
            if not env_unset:
                env['EDITORIAL_REVIEW_REQUIRED'] = review
            stack.enter_context(patch.dict('os.environ', env))
            if env_unset:
                os.environ.pop('EDITORIAL_REVIEW_REQUIRED', None)  # patch.dict가 끝나면 원래대로 되돌린다
            stack.enter_context(patch.object(engine, 'GROK_KEY', 'test-only'))
            for name in ('WP_URL', 'WP_USER', 'WP_PASS', 'SITE_ID'):
                stack.enter_context(patch.object(engine, name, ''))
            mocks = {}
            for name in ('_load_api_keys_from_site', '_git_commit_used', '_submit_indexnow', '_ping_sitemaps'):
                mocks[name] = stack.enter_context(patch.object(engine, name))
            stack.enter_context(patch.object(engine.time, 'sleep'))
            cfg = {'monetization_stage': stage}
            cfg.update(dashboard or {})
            stack.enter_context(patch.object(engine, '_get_dashboard_config', return_value=cfg))
            stack.enter_context(patch.object(engine, '_insert_internal_links', side_effect=lambda c, *a: c))
            stack.enter_context(patch.object(engine, '_inject_eeat_blocks', side_effect=lambda c, *a, **kw: c))
            if not real_violation_check:
                stack.enter_context(patch.object(engine, '_check_adsense_violations', return_value=[]))
            for target in extra:
                stack.enter_context(target)
            for name in ('KeywordManager', 'DynamicKeywordGenerator', 'ContentGenerator', 'ContentFormatter',
                         'ImageManager', 'AffiliateManager', 'AdSenseOptimizer', 'QualityGate',
                         'NaverCafePublisher', 'WordPressPublisher', 'SupabaseLogger',
                         'TelegramPublisher', 'DiscordPublisher'):
                mocks[name] = stack.enter_context(patch.object(engine, name)).return_value
            km = mocks['KeywordManager']
            km.keywords = {}
            km.select.return_value = [{'keyword': 'test subject'}]
            km.check_cannibalization.return_value = conflicts or []
            mocks['ContentGenerator'].generate.return_value = (content, 0, len(content))
            mocks['ContentFormatter'].format.side_effect = lambda c, **kw: c
            mocks['ImageManager'].fetch_multiple.return_value = []
            mocks['ImageManager'].fetch_image.return_value = None
            mocks['ImageManager'].insert_image.side_effect = lambda c, *a: (c, False, '')
            mocks['AffiliateManager'].insert_links.side_effect = lambda c, *a, **kw: (c, False)
            mocks['AdSenseOptimizer'].optimize.side_effect = lambda c: c
            mocks['QualityGate'].validate.return_value = (score >= 85, score, {})
            mocks['QualityGate'].credibility_audit.return_value = warnings or []
            # publish_status가 dict면 WordPressPublisher.publish의 반환값 그대로 쓴다(실패 케이스용).
            mocks['WordPressPublisher'].publish.return_value = (
                publish_status if isinstance(publish_status, dict)
                else {'id': 123, 'status': publish_status, 'url': 'https://site.test/?p=123'})
            # 소유 사이트는 실제 도메인으로 (run_pipeline이 WP 호스트를 사이트 도메인과 대조한다)
            if wp_url is None:  # '' (주소 없음)은 그대로 넘겨 거부되는지 본다
                wp_url = ('https://' + engine.OWNED_SITES[site_id] if site_id in engine.OWNED_SITES
                          else 'https://friend-site.example')
            mocks['result'] = engine.run_pipeline(count=1, dry_run=dry, site_override={
                'id': site_id, 'wp_url': wp_url, 'config': {}})
        return mocks

    def assert_saved_as_draft(self, mocks):
        self.assertEqual(mocks['WordPressPublisher'].publish.call_args.kwargs['status'], 'draft')
        self.assertEqual(mocks['SupabaseLogger'].log_publish.call_args.args[0]['status'], 'draft')
        mocks['KeywordManager'].mark_used.assert_called_once_with('test subject')
        self.assert_nothing_broadcast(mocks)

    def assert_nothing_broadcast(self, mocks):
        mocks['_submit_indexnow'].assert_not_called()
        mocks['_ping_sitemaps'].assert_not_called()
        for name in ('NaverCafePublisher', 'TelegramPublisher', 'DiscordPublisher'):
            mocks[name].publish.assert_not_called()

    def test_approval_stage_cannot_publish_even_with_review_disabled(self):
        self.assert_saved_as_draft(self.run_case(stage=1, review='false'))

    def test_review_default_applies_to_later_stages(self):
        self.assert_saved_as_draft(self.run_case(stage=3))

    def test_unset_review_env_defaults_to_draft(self):
        self.assertNotIn('EDITORIAL_REVIEW_REQUIRED', os.environ)
        self.assert_saved_as_draft(self.run_case(stage=3, env_unset=True))

    def test_unrecognised_review_value_fails_closed(self):
        self.assert_saved_as_draft(self.run_case(stage=3, review='no'))

    def test_low_score_cannot_publish_in_later_stage(self):
        self.assert_saved_as_draft(self.run_case(stage=3, review='false', score=10))

    def test_credibility_warning_cannot_publish(self):
        self.assert_saved_as_draft(self.run_case(stage=3, review='false',
                                                 warnings=[{'tag': 'citation', 'count': 1}]))

    def test_dry_run_does_not_consume_keyword_or_publish(self):
        mocks = self.run_case(dry=True, conflicts=None)
        mocks['WordPressPublisher'].publish.assert_not_called()
        mocks['KeywordManager'].mark_used.assert_not_called()
        mocks['KeywordManager'].quarantine.assert_not_called()
        mocks['_git_commit_used'].assert_not_called()
        self.assert_nothing_broadcast(mocks)

    def test_sns_is_off_unless_dashboard_turns_it_on(self):
        mocks = self.run_case(stage=3, review='false', publish_status='published')
        self.assertEqual(mocks['WordPressPublisher'].publish.call_args.kwargs['status'], 'publish')
        for name in ('NaverCafePublisher', 'TelegramPublisher', 'DiscordPublisher'):
            mocks[name].publish.assert_not_called()
        mocks = self.run_case(stage=3, review='false', publish_status='published',
                              dashboard={'snsOn': {'telegram': True}})
        mocks['TelegramPublisher'].publish.assert_called_once()
        mocks['NaverCafePublisher'].publish.assert_not_called()

    def test_adsense_violation_keeps_body_and_saves_draft(self):
        self.assertFalse(hasattr(engine, '_remove_adsense_violations'))
        self.assertFalse(hasattr(engine, 'ADSENSE_BANNED_BLOCKS'))
        content = ('<title>부업 정리</title>'
                   '<div class="tldr-box"><strong>핵심 요약:</strong> 도입부 요약입니다.</div>'
                   '<p>도입부 문단입니다. 이 문단은 잘리면 안 됩니다.</p>'
                   '<h2>1단계</h2><p>첫 단계 설명입니다.</p>'
                   '<div class="tip-box">쿠팡 파트너스 가입 절차 안내</div>'
                   '<p>마무리 문단입니다.</p>')
        expected = engine.extract_title(engine._sanitize_content(content))[1]
        # 옛 정규식이었다면 도입부부터 잘려 나갔을 입력임을 확인 (테스트가 의미 있는지)
        self.assertLess(len(re.sub(OLD_CUTTING_PATTERN, '', expected, flags=re.S | re.I)), len(expected) // 2)
        mocks = self.run_case(stage=1, review='false', content=content, real_violation_check=True)
        published_body = mocks['WordPressPublisher'].publish.call_args.args[1]
        self.assertEqual(len(published_body), len(expected))
        self.assertEqual(published_body, expected)
        self.assertIn('도입부 문단입니다', published_body)
        self.assert_saved_as_draft(mocks)
        alert_tags = [c.args[3] for c in mocks['SupabaseLogger'].log_alert.call_args_list if len(c.args) > 3]
        self.assertIn('adsense_violation', alert_tags)

    def test_html_cleanup_failure_keeps_original_content(self):
        content = '<title>T</title><p>본문 유지</p>'
        expected = engine.extract_title(engine._sanitize_content(content))[1]
        mocks = self.run_case(stage=3, content=content, extra=(
            patch.object(html_cleanup, 'clean_html', side_effect=RuntimeError('boom')),))
        self.assertEqual(mocks['WordPressPublisher'].publish.call_args.args[1], expected)
        self.assert_saved_as_draft(mocks)

    def test_near_duplicate_keyword_is_quarantined_not_generated(self):
        mocks = self.run_case(stage=3, conflicts=[('비슷한 주제', 0.9)])
        mocks['ContentGenerator'].generate.assert_not_called()
        mocks['WordPressPublisher'].publish.assert_not_called()
        mocks['KeywordManager'].quarantine.assert_called_once_with('test subject', 'cannibal_high', ANY)
        mocks = self.run_case(stage=3, dry=True, conflicts=[('비슷한 주제', 0.9)])
        mocks['KeywordManager'].quarantine.assert_not_called()

    def test_pipeline_refuses_sites_outside_owned_pair(self):
        mocks = self.run_case(site_id='site-9999999999999')  # 허용 목록 밖 사이트
        self.assertEqual(mocks['result'], 'refused')
        mocks['ContentGenerator'].generate.assert_not_called()
        mocks['WordPressPublisher'].publish.assert_not_called()

    def test_pipeline_binds_site_id_to_wp_host(self):
        # 사이트 ID는 맞아도 글을 보낼 주소가 그 사이트 도메인이 아니면 생성 전에 멈춘다.
        for site_id, wp_url in (
                ('site-1', 'https://friend-site.example'),              # 지인 주소
                ('site-1', 'https://planx-ai.com.friend-site.example'),  # 접미사 우회
                ('site-1', 'https://planx-ai.com@friend-site.example'),  # userinfo 우회
                ('site-1775046458524', 'https://planx-ai.com'),          # BOMISSU_WP_URL 미설정 → planx 주소 폴백
                ('site-1', '')):
            mocks = self.run_case(stage=3, site_id=site_id, wp_url=wp_url)
            self.assertEqual(mocks['result'], 'refused', wp_url)
            mocks['KeywordManager'].select.assert_not_called()
            mocks['ContentGenerator'].generate.assert_not_called()
            mocks['WordPressPublisher'].publish.assert_not_called()
        # 같은 도메인의 흔한 표기 차이는 통과한다.
        for wp_url in ('https://www.PLANX-AI.com/', 'https://planx-ai.com/wp-json/wp/v2', 'planx-ai.com'):
            mocks = self.run_case(stage=3, wp_url=wp_url)
            self.assertIsNone(mocks['result'], wp_url)
            self.assert_saved_as_draft(mocks)

    def test_legacy_mode_without_site_config_checks_env_wp_url(self):
        # --site-id 없이(레거시) SITE_ID=site-1, WP_URL=지인 주소: DB 설정이 없어도 환경변수 주소를 검사한다.
        with patch.object(engine, 'SITE_ID', 'site-1'), \
                patch.object(engine, 'WP_URL', 'https://friend-site.example'), \
                patch.object(engine, '_get_site_config', return_value=None), \
                patch.object(engine, 'KeywordManager') as km, \
                patch.object(engine, 'ContentGenerator') as gen:
            self.assertEqual(engine.run_pipeline(count=1), 'refused')
            km.assert_not_called()
            gen.assert_not_called()

    def test_status_mismatch_quarantines_keyword_and_alerts(self):
        # 초안을 요청했는데 WordPress가 다른 상태로 저장한 경우: 글은 생겼으므로 같은 주제를 다시 만들지 않는다.
        mocks = self.run_case(stage=3, publish_status={
            'status': 'failed', 'id': 77, 'error': 'WordPress status mismatch; inspect post before retry'})
        mocks['KeywordManager'].quarantine.assert_called_once_with('test subject', 'wp_status_mismatch', ANY)
        mocks['KeywordManager'].mark_used.assert_not_called()
        alert_tags = [c.args[3] for c in mocks['SupabaseLogger'].log_alert.call_args_list if len(c.args) > 3]
        self.assertIn('wp_status_mismatch', alert_tags)
        self.assert_nothing_broadcast(mocks)
        # 글이 만들어지지 않은 실패(네트워크 등)는 격리하지 않는다. 다음 실행에서 다시 시도할 수 있다.
        mocks = self.run_case(stage=3, publish_status={'status': 'failed', 'error': 'timeout'})
        mocks['KeywordManager'].quarantine.assert_not_called()


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        with patch.object(sys, 'argv', ['main.py'] + argv):
            engine.main()

    def test_etf_pipeline_is_limited_to_owned_sites_too(self):
        fake_etf = Mock()
        fake_etf.run_etf_report.return_value = 'dry_run'
        with patch.dict(sys.modules, {'etf_report': fake_etf}), \
                patch.object(engine, 'GROK_KEY', 'test-only'):
            with patch.object(engine, 'SITE_ID', 'site-2'):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main(['--pipeline', 'etf-report'])
                self.assertEqual(ctx.exception.code, 1)
                fake_etf.run_etf_report.assert_not_called()
            with patch.object(engine, 'SITE_ID', 'site-1'):
                self.run_main(['--pipeline', 'etf-report', '--dry-run'])
                # 대상 사이트를 모듈에 넘긴다. 초안 기본·site-1 전용·WP 호스트·paused 확인은 etf_report가 한다.
                fake_etf.run_etf_report.assert_called_once_with(
                    report_type='blog-ready', dry_run=True, site_id='site-1')
            # 모듈이 거부하면(예: bomissu에 ETF, 지인 WP 주소) exit 1
            fake_etf.run_etf_report.return_value = 'refused'
            with patch.object(engine, 'SITE_ID', ''):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main(['--pipeline', 'etf-report', '--site-id', 'site-1775046458524'])
                self.assertEqual(ctx.exception.code, 1)

    def test_legacy_mode_requires_explicit_site_id(self):
        # SITE_ID 환경변수가 없으면 'site-1'로 채우지 않는다: fork가 WP_URL만 바꿔 돌리던 우회 경로.
        with patch.object(engine, 'SITE_ID', ''), \
                patch.object(engine, 'WP_URL', 'https://friend-site.example'), \
                patch.object(engine, 'GROK_KEY', 'test-only'), \
                patch.object(engine, 'run_pipeline') as run:
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(['--count', '1'])
            self.assertEqual(ctx.exception.code, 1)
            run.assert_not_called()

    def test_module_site_id_has_no_default(self):
        # 모듈 수준 기본값이 다시 'site-1'로 돌아가지 않았는지 소스에서 확인한다(main.py·etf_report.py 모두).
        for name in ('main.py', 'etf_report.py'):
            tree = ast.parse((ROOT / 'scripts' / name).read_text(encoding='utf-8'))
            defaults = [node.value.args[1].value for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'SITE_ID' for t in node.targets)
                        and isinstance(node.value, ast.Call) and len(node.value.args) == 2
                        and isinstance(node.value.args[1], ast.Constant)]
            self.assertEqual(defaults, [''], name)

    def test_refused_pipeline_exits_1(self):
        # run_pipeline이 WP 호스트 불일치로 거부하면 CLI도 실패로 끝난다(성공처럼 보이지 않게).
        with patch.object(engine, 'SITE_ID', 'site-1'), \
                patch.object(engine, 'WP_URL', 'https://friend-site.example'), \
                patch.object(engine, 'GROK_KEY', 'test-only'), \
                patch.object(engine, 'run_pipeline', return_value='refused'):
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(['--count', '1'])
            self.assertEqual(ctx.exception.code, 1)
        with patch.object(engine, 'SITE_ID', ''), \
                patch.object(engine, '_get_site_config',
                             return_value={'id': 'site-1', 'wp_url': 'https://friend-site.example'}), \
                patch.object(engine, 'run_pipeline', return_value='refused'):
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(['--site-id', 'site-1', '--count', '1'])
            self.assertEqual(ctx.exception.code, 1)

    def test_setup_pages_is_bound_to_owned_host(self):
        with patch.object(engine, 'SITE_ID', 'site-1'), \
                patch.object(engine, 'WP_URL', 'https://friend-site.example'), \
                patch.object(engine, 'WP_USER', 'u'), patch.object(engine, 'WP_PASS', 'p'), \
                patch.object(engine, 'EssentialPagesCreator') as epc:
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(['--setup-pages'])
            self.assertEqual(ctx.exception.code, 1)
            epc.assert_not_called()

    def test_site_id_outside_owned_pair_exits_1(self):
        self.assertEqual(engine.OWNED_SITE_IDS, frozenset({'site-1', 'site-1775046458524'}))
        for site_id in ('site-2', 'site-9999999999999', 'site-1775048459655'):
            with patch.object(engine, 'SITE_ID', 'site-1'), \
                    patch.object(engine, '_get_site_config') as get_cfg, \
                    patch.object(engine, 'run_pipeline') as run:
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main(['--site-id', site_id, '--count', '1'])
                self.assertEqual(ctx.exception.code, 1)
                get_cfg.assert_not_called()
                run.assert_not_called()

    def test_owned_site_id_runs_pipeline(self):
        for site_id in sorted(engine.OWNED_SITE_IDS):
            with patch.object(engine, 'SITE_ID', 'site-1'), \
                    patch.object(engine, '_get_site_config', return_value={'id': site_id}), \
                    patch.object(engine, 'run_pipeline') as run:
                self.run_main(['--site-id', site_id, '--count', '1'])
                self.assertEqual(run.call_args.kwargs['site_override'], {'id': site_id})

    def test_legacy_env_mode_is_limited_too(self):
        with patch.object(engine, 'SITE_ID', 'site-2'), patch.object(engine, 'WP_URL', 'https://x.test'), \
                patch.object(engine, 'GROK_KEY', 'test-only'), patch.object(engine, 'run_pipeline') as run:
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(['--count', '1'])
            self.assertEqual(ctx.exception.code, 1)
            run.assert_not_called()

    def test_scheduled_mode_and_fake_pipelines_are_gone(self):
        self.assertFalse(hasattr(engine, '_get_all_active_sites'))
        for argv in (['--mode', 'scheduled'], ['--pipeline', 'hotdeal'], ['--pipeline', 'promo']):
            with patch.object(engine, 'run_pipeline') as run, patch('sys.stderr'):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main(argv)
                self.assertEqual(ctx.exception.code, 2)
                run.assert_not_called()


ETF_CONTENT = ('<h2>ETF 시장 점검</h2><h2>1. 주도 섹터</h2><p>' + '가' * 50 + '</p>'
               '<h2>4. 매매 신호</h2><p>투자 참고용입니다.</p>')


class EtfReportTests(unittest.TestCase):
    """ETF 경로도 초안 기본·편집 검토·paused·사이트 가드를 따른다 (예전 etf_report.py는 'publish' 고정)."""

    def run_etf(self, review=None, site_id='site-1', wp_url='https://planx-ai.com', site_status='',
                publish_result=None, dry=False):
        with ExitStack() as stack:
            stack.enter_context(patch.dict('os.environ', {}))  # 끝나면 원래 환경으로 되돌린다
            os.environ.pop('EDITORIAL_REVIEW_REQUIRED', None)
            if review is not None:
                os.environ['EDITORIAL_REVIEW_REQUIRED'] = review
            for name, value in (('WP_URL', wp_url), ('WP_USER', 'u'), ('WP_PASS', 'p'), ('SITE_ID', '')):
                stack.enter_context(patch.object(etf, name, value))
            fake_main = Mock()  # 스타일링 단계의 `from main import ContentFormatter`
            fake_main.ContentFormatter.return_value.format.side_effect = lambda c, **kw: c
            stack.enter_context(patch.dict(sys.modules, {'main': fake_main}))
            m = {}
            m['status'] = stack.enter_context(patch.object(etf, '_get_site_status', return_value=site_status))
            m['fetch'] = stack.enter_context(patch.object(
                etf, 'fetch_etf_report', return_value={'daily': {'sector_rankings': [{'sector': '반도체'}]}}))
            stack.enter_context(patch.object(etf, 'build_etf_blog_prompt', return_value='prompt'))
            m['generate'] = stack.enter_context(patch.object(
                etf, 'generate_blog_content', return_value=(ETF_CONTENT, 'test-model')))
            stack.enter_context(patch.object(etf, '_build_sector_chart_html', return_value=''))
            stack.enter_context(patch.object(etf, '_build_signal_badge_html', return_value=''))
            stack.enter_context(patch.object(etf, '_simple_quality_check', return_value=80))
            stack.enter_context(patch.object(etf, '_extract_payload', return_value={}))
            stack.enter_context(patch.object(etf, 'is_korean_market_open', return_value=True))

            def fake_publish(title, *args, **kwargs):
                return publish_result or {
                    'status': 'published' if kwargs.get('status') == 'publish' else 'draft',
                    'id': 9, 'url': 'https://planx-ai.com/?p=9', 'title': title}
            m['publish'] = stack.enter_context(patch.object(etf, 'publish_to_wordpress', side_effect=fake_publish))
            m['log'] = stack.enter_context(patch.object(etf, 'log_to_supabase'))
            m['sns'] = stack.enter_context(patch.object(etf, 'notify_sns'))
            m['result'] = etf.run_etf_report(dry_run=dry, site_id=site_id)
        return m

    def test_defaults_to_draft_without_sns(self):
        # 미설정·'true'·오타·빈값 모두 초안 (fail-closed)
        for review in (None, 'true', 'no', ''):
            m = self.run_etf(review=review)
            self.assertEqual(m['result'], 'draft', review)
            self.assertEqual(m['publish'].call_args.kwargs['status'], 'draft')
            self.assertEqual(m['log'].call_args.args[0]['status'], 'draft')
            self.assertEqual(m['log'].call_args.kwargs['site_id'], 'site-1')
            m['sns'].assert_not_called()

    def test_publishes_and_notifies_only_when_review_explicitly_off(self):
        m = self.run_etf(review='false')
        self.assertEqual(m['publish'].call_args.kwargs['status'], 'publish')
        self.assertEqual(m['result'], 'published')
        m['sns'].assert_called_once()
        # 요청과 다른 상태로 저장되거나 실패하면 알리지 않는다
        m = self.run_etf(review='false', publish_result={
            'status': 'failed', 'id': 9, 'error': 'WordPress status mismatch; inspect post before retry'})
        self.assertEqual(m['result'], 'failed')
        m['sns'].assert_not_called()

    def test_paused_site_stops_before_paid_calls(self):
        m = self.run_etf(site_status='paused')
        self.assertEqual(m['result'], 'skipped')
        m['status'].assert_called_once_with('site-1')
        for name in ('fetch', 'generate', 'publish', 'sns'):
            m[name].assert_not_called()

    def test_only_planx_with_matching_wp_host(self):
        cases = (('site-1775046458524', 'https://bomissu.com'),   # bomissu에 ETF(PlanX 브랜드) 금지
                 ('site-9999999999999', 'https://planx-ai.com'),  # 지인 ID
                 ('', 'https://planx-ai.com'),                    # 대상 미지정 (기본값으로 채우지 않음)
                 ('site-1', 'https://friend-site.example'),       # 지인 주소
                 ('site-1', 'https://planx-ai.com.friend-site.example'),
                 ('site-1', ''))                                  # 실제 저장인데 주소 없음
        for site_id, wp_url in cases:
            m = self.run_etf(site_id=site_id, wp_url=wp_url)
            self.assertEqual(m['result'], 'refused', (site_id, wp_url))
            for name in ('status', 'fetch', 'generate', 'publish', 'sns'):
                m[name].assert_not_called()
        # 드라이런은 WP_URL이 비어 있어도 되지만, 값이 지인 주소면 거부한다.
        m = self.run_etf(dry=True, wp_url='')
        self.assertEqual(m['result'], 'dry_run')
        m['publish'].assert_not_called()
        self.assertEqual(self.run_etf(dry=True, wp_url='https://friend-site.example')['result'], 'refused')

    def test_publish_to_wordpress_defaults_to_draft_and_verifies_response(self):
        response = Mock()
        response.json.return_value = {'id': 5, 'status': 'draft', 'link': 'https://planx-ai.com/?p=5'}
        with patch.object(etf, 'WP_URL', 'https://planx-ai.com'), \
                patch.object(etf, '_get_or_create_category_robust', return_value=3), \
                patch.object(etf, '_get_or_create_tags', return_value=[]), \
                patch('requests.post', return_value=response) as post:
            result = etf.publish_to_wordpress('T', '<p>b</p>')
            self.assertEqual(post.call_args.kwargs['json']['status'], 'draft')
            self.assertEqual(result['status'], 'draft')
            # 초안을 요청했는데 공개로 저장되면 성공으로 치지 않는다
            response.json.return_value = {'id': 5, 'status': 'publish'}
            self.assertEqual(etf.publish_to_wordpress('T', 'b')['status'], 'failed')
            response.json.return_value = {'id': 6, 'status': 'publish', 'link': 'x'}
            self.assertEqual(etf.publish_to_wordpress('T', 'b', status='publish')['status'], 'published')
            with self.assertRaises(ValueError):
                etf.publish_to_wordpress('T', 'b', status='future')

    def test_supabase_log_leaves_published_at_empty_for_drafts(self):
        with patch.object(etf, 'SUPABASE_URL', 'https://db.test'), \
                patch.object(etf, 'SUPABASE_KEY', 'test-only'), patch('requests.post') as post:
            etf.log_to_supabase({'status': 'draft', 'title': 't'}, 'm', 'blog-ready', site_id='site-1')
            body = post.call_args.kwargs['json']
            self.assertIsNone(body['published_at'])
            self.assertEqual(body['site_id'], 'site-1')
            etf.log_to_supabase({'status': 'published', 'title': 't'}, 'm', 'blog-ready', site_id='site-1')
            self.assertIsNotNone(post.call_args.kwargs['json']['published_at'])

    def test_site_status_lookup(self):
        with patch.object(etf, 'SUPABASE_URL', 'https://db.test'), patch.object(etf, 'SUPABASE_KEY', 'test-only'):
            with patch('requests.get') as get:
                get.return_value.json.return_value = [{'status': 'paused'}]
                self.assertEqual(etf._get_site_status('site-1'), 'paused')
                self.assertIn('id=eq.site-1', get.call_args.args[0])
            with patch('requests.get', side_effect=RuntimeError('down')):
                self.assertEqual(etf._get_site_status('site-1'), '')

    def test_cli_exits_1_when_refused(self):
        with patch.object(sys, 'argv', ['etf_report.py', '--dry-run']), \
                patch.object(etf, 'run_etf_report', return_value='refused'):
            with self.assertRaises(SystemExit) as ctx:
                etf.main()
            self.assertEqual(ctx.exception.code, 1)


class SiteGuardTests(unittest.TestCase):
    def test_site_id_is_bound_to_wp_host(self):
        self.assertEqual(engine.OWNED_SITE_IDS, site_guard.OWNED_SITE_IDS)
        allowed = (('site-1', 'https://planx-ai.com'), ('site-1', 'https://www.planx-ai.com/wp-json/wp/v2'),
                   ('site-1', 'PLANX-AI.COM'), ('site-1775046458524', 'https://bomissu.com/'))
        refused = (('site-1', 'https://bomissu.com'), ('site-1775046458524', 'https://planx-ai.com'),
                   ('site-1', 'https://planx-ai.com.evil.example'), ('site-1', 'https://planx-ai.com@evil.example'),
                   ('site-1', 'https://evil.example/planx-ai.com'), ('site-2', 'https://planx-ai.com'),
                   ('', 'https://planx-ai.com'), ('site-1', ''), ('site-1', None), ('site-1', 'https://[bad'))
        for site_id, url in allowed:
            self.assertTrue(site_guard.wp_url_allowed(site_id, url), (site_id, url))
        for site_id, url in refused:
            self.assertFalse(site_guard.wp_url_allowed(site_id, url), (site_id, url))


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def active_lines(name):
        text = (ROOT / '.github' / 'workflows' / name).read_text(encoding='utf-8')
        return text, [line for line in text.splitlines() if not line.lstrip().startswith('#')]

    @staticmethod
    def expressions_in_run_blocks(text):
        """run: 셸 스크립트 안에 들어간 ${{ }} 식 목록. 입력·matrix 값은 env로 넘겨야 셸 주입이 없다."""
        hits, block_indent = [], None
        for line in text.splitlines():
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if block_indent is not None:
                if not stripped or indent > block_indent:
                    if '${{' in line:
                        hits.append(stripped)
                    continue
                block_indent = None
            match = re.match(r'(-\s+)?run:\s*(.*)$', stripped)
            if match:
                rest = match.group(2)
                if rest.startswith(('|', '>')):
                    block_indent = indent + len(match.group(1) or '')
                elif '${{' in rest:
                    hits.append(stripped)
        return hits

    def test_workflow_run_steps_take_inputs_via_env_only(self):
        # 검사기가 옛 패턴을 실제로 잡는지 먼저 확인
        self.assertTrue(self.expressions_in_run_blocks(
            '      - name: x\n        run: |\n          git commit -m "[golden/${{ matrix.site }}]"\n'))
        for name in ('publish.yml', 'publish-golden.yml'):
            text, _ = self.active_lines(name)
            self.assertEqual(self.expressions_in_run_blocks(text), [], name)

    def test_golden_workflow_is_repo_guarded_with_choice_site_input(self):
        text, _ = self.active_lines('publish-golden.yml')
        self.assertIn("if: github.repository == 'planxs-ai/wp-auto'", text)
        block = re.search(r'\n      site_id:\n((?:        .*\n)+)', text)
        self.assertIsNotNone(block)
        self.assertIn('type: choice', block.group(1))
        self.assertEqual(re.findall(r'^\s+- (\S+)\s*$', block.group(1), re.M),
                         ['all', 'site-1', 'site-1775046458524'])

    def test_publish_workflow_is_dispatch_only_for_owned_sites(self):
        text, active = self.active_lines('publish.yml')
        self.assertFalse(any(line.strip().startswith('schedule:') or 'cron:' in line for line in active))
        self.assertNotIn('fork-publish', text)
        self.assertNotIn("github.repository != 'planxs-ai/wp-auto'", text)
        self.assertNotIn('hotdeal', text)
        self.assertNotIn('- promo', text)
        self.assertIn('EDITORIAL_REVIEW_REQUIRED: "true"', text)
        self.assertEqual(sorted(set(re.findall(r'--site-id (\S+)', text))), sorted(engine.OWNED_SITE_IDS))

    def test_golden_workflow_targets_owned_sites_as_drafts(self):
        text, active = self.active_lines('publish-golden.yml')
        self.assertFalse(any(line.strip().startswith('schedule:') or 'cron:' in line for line in active))
        self.assertIn('EDITORIAL_REVIEW_REQUIRED: "true"', text)
        self.assertNotIn('site-2', text)
        self.assertNotIn('site-3', text)


if __name__ == '__main__':
    unittest.main()
