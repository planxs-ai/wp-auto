import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
from scripts import main as engine
from scripts.editorial_pages import build_pages, create_missing_drafts
from scripts.audit_adsense import review_flags


class EditorialTests(unittest.TestCase):
    def test_publisher_defaults_to_draft_and_verifies_response(self):
        publisher = engine.WordPressPublisher()
        publisher._get_site_name = Mock(return_value='Test')
        response = Mock()
        response.json.return_value = {'id': 1, 'status': 'draft'}
        with patch('requests.post', return_value=response) as post:
            self.assertEqual(publisher.publish('Title', '<p>Body</p>')['status'], 'draft')
            self.assertEqual(post.call_args.kwargs['json']['status'], 'draft')
            self.assertNotIn('rank_math_robots', post.call_args.kwargs['json'].get('meta', {}))
            response.json.return_value = {'id': 1, 'status': 'publish'}
            self.assertEqual(publisher.publish('Title', 'Body')['status'], 'failed')

    def test_pages_reject_placeholder_email_and_escape_identity(self):
        with self.assertRaises(ValueError):
            build_pages('Test', 'Owner', 'Description', 'contact@example.com')
        pages = build_pages('A < B', 'Owner', '<script>bad</script>', 'editor@site.test')
        self.assertTrue(all(p['status'] == 'draft' for p in pages))
        self.assertNotIn('<script>', pages[0]['content'])
        self.assertIn('settings/ads', pages[2]['content'])

    def test_pages_preserve_existing_and_fail_closed(self):
        pages = build_pages('Test', 'Owner', 'Description', 'editor@site.test')
        session = Mock()
        session.get.return_value.json.return_value = [{'id': 1}]
        created, skipped, failed = create_missing_drafts('https://site.test', {}, pages, session)
        self.assertEqual(len(skipped), 4)
        session.post.assert_not_called()
        session.get.return_value.raise_for_status.side_effect = ValueError('failed lookup')
        self.assertEqual(len(create_missing_drafts('https://site.test', {}, pages, session)[2]), 4)
        session.post.assert_not_called()

    def test_prompt_modes_include_evidence_rules(self):
        for lang in ('ko', 'en'):
            for adsense in (True, False):
                for golden in (True, False):
                    for prompt in engine.get_prompts(lang, adsense, 'IT & 테크 리뷰', golden):
                        self.assertIn('Do not invent firsthand use', prompt)
                        self.assertNotIn('실제 경험 문단" 1개 필수', prompt)

    def test_existing_content_flags_are_review_requests(self):
        flags = review_flags('<p>제가 실제로 사용해보니 실패 없는 투자였습니다.</p>')
        self.assertTrue(any('기록 대조' in f for f in flags))
        self.assertTrue(any('단정' in f for f in flags))

    def run_pipeline_case(self, stage=1, review='true', dry=False, score=95, warnings=None):
        with ExitStack() as stack:
            stack.enter_context(patch.dict('os.environ', {'FORCE_RUN': 'true', 'EDITORIAL_REVIEW_REQUIRED': review}))
            stack.enter_context(patch.object(engine, 'GROK_KEY', 'test-only'))
            for name in ('WP_URL', 'WP_USER', 'WP_PASS', 'SITE_ID'):
                stack.enter_context(patch.object(engine, name, ''))
            for name in ('_load_api_keys_from_site', '_git_commit_used', '_submit_indexnow', '_ping_sitemaps'):
                stack.enter_context(patch.object(engine, name))
            stack.enter_context(patch.object(engine.time, 'sleep'))
            stack.enter_context(patch.object(engine, '_get_dashboard_config', return_value={'monetization_stage': stage}))
            stack.enter_context(patch.object(engine, '_insert_internal_links', side_effect=lambda c, *a: c))
            stack.enter_context(patch.object(engine, '_inject_eeat_blocks', side_effect=lambda c, *a, **kw: c))
            stack.enter_context(patch.object(engine, '_check_adsense_violations', return_value=[]))
            mocks = {}
            for name in ('KeywordManager', 'DynamicKeywordGenerator', 'ContentGenerator', 'ContentFormatter',
                         'ImageManager', 'AffiliateManager', 'AdSenseOptimizer', 'QualityGate', 'NaverCafePublisher',
                         'WordPressPublisher', 'SupabaseLogger', 'TelegramPublisher', 'DiscordPublisher'):
                mocks[name] = stack.enter_context(patch.object(engine, name)).return_value
            km = mocks['KeywordManager']
            km.keywords = {}
            km.select.return_value = [{'keyword': 'test subject'}]
            km.check_cannibalization.return_value = []
            mocks['ContentGenerator'].generate.return_value = ('<title>Test</title><p>Body</p>', 0, 30)
            mocks['ContentFormatter'].format.side_effect = lambda c, **kw: c
            mocks['ImageManager'].fetch_multiple.return_value = []
            mocks['ImageManager'].fetch_image.return_value = None
            mocks['ImageManager'].insert_image.side_effect = lambda c, *a: (c, False, '')
            mocks['AffiliateManager'].insert_links.side_effect = lambda c, *a, **kw: (c, False)
            mocks['AdSenseOptimizer'].optimize.side_effect = lambda c: c
            mocks['QualityGate'].validate.return_value = (score >= 85, score, {})
            mocks['QualityGate'].credibility_audit.return_value = warnings or []
            mocks['WordPressPublisher'].publish.return_value = {'id': 123, 'status': 'draft'}
            engine.run_pipeline(count=1, dry_run=dry, site_override={
                'id': 'test-site', 'wp_url': 'https://site.test', 'config': {}})
            if dry:
                mocks['WordPressPublisher'].publish.assert_not_called()
                km.mark_used.assert_not_called()
                engine._git_commit_used.assert_not_called()
            else:
                self.assertEqual(mocks['WordPressPublisher'].publish.call_args.kwargs['status'], 'draft')
                self.assertEqual(mocks['SupabaseLogger'].log_publish.call_args.args[0]['status'], 'draft')
                km.mark_used.assert_called_once_with('test subject')
            engine._submit_indexnow.assert_not_called()
            engine._ping_sitemaps.assert_not_called()
            for name in ('NaverCafePublisher', 'TelegramPublisher', 'DiscordPublisher'):
                mocks[name].publish.assert_not_called()

    def test_approval_stage_cannot_publish_even_with_review_disabled(self):
        self.run_pipeline_case(stage=1, review='false')

    def test_review_default_applies_to_later_stages(self):
        self.run_pipeline_case(stage=3)

    def test_low_score_cannot_publish_in_later_stage(self):
        self.run_pipeline_case(stage=3, review='false', score=10)

    def test_credibility_warning_cannot_publish(self):
        self.run_pipeline_case(stage=3, review='false', warnings=[{'tag': 'citation', 'count': 1}])

    def test_dry_run_does_not_consume_keyword_or_publish(self):
        self.run_pipeline_case(dry=True)


if __name__ == '__main__':
    unittest.main()
