import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from scripts.site_remediation import clean_html, apply_plan, restore_backup, SITE


class SiteRemediationTests(unittest.TestCase):
    def test_cleanup_is_idempotent_and_preserves_unique_media(self):
        html = '''<p>중요한 설명</p><div><p>이 글의 순서</p><ol><li>설명</li></ol></div>
        <div><span>이 글의 순서</span><ol><li><a href="#part">설명</a></li></ol></div>
        <figure><img src="a.jpg"><figcaption>credit A</figcaption></figure>
        <figure><img src="a.jpg"><figcaption>credit A</figcaption></figure>
        <figure><img src="b.jpg"><figcaption>credit B</figcaption></figure><!-- wp:paragraph -->'''
        cleaned, counts = clean_html(html)
        self.assertEqual(counts, {'duplicate_images':1,'duplicate_tocs':1})
        self.assertIn('중요한 설명',cleaned)
        self.assertIn('credit B',cleaned)
        self.assertIn('wp:paragraph',cleaned)
        self.assertEqual(clean_html(cleaned)[0],cleaned)
        self.assertFalse(any(clean_html(cleaned)[1].values()))

    def test_no_transform_without_identified_structure_problem(self):
        html='<p class="x">A &amp; B</p>\n'
        self.assertEqual(clean_html(html)[0],html)

    def record(self,content):
        return {'id':7,'slug':'sample','modified_gmt':'2026-09-12T00:00:00',
                'content':{'raw':content},'title':{'raw':'Title'},'excerpt':{'raw':''},'status':'publish'}

    def plan(self):
        return {'site':SITE,'version':1,'rows':[{'id':7,'slug':'sample',
                'modified_gmt':'2026-09-12T00:00:00','changes':{'duplicate_images':1}}]}

    def test_changed_post_is_not_overwritten(self):
        s=Mock(); post=self.record('body');post['modified_gmt']='later';s.get.return_value.json.return_value=post
        with tempfile.TemporaryDirectory() as d:
            result=apply_plan(self.plan(),s,d)
            self.assertEqual(result[0]['status'],'changed_since_plan')
            s.post.assert_not_called()

    def test_backup_precedes_write_and_restoration_is_verified(self):
        html='<figure><img src="same"></figure><figure><img src="same"></figure>'
        post=self.record(html);after=self.record(clean_html(html)[0])
        s=Mock();s.get.return_value.json.side_effect=[post,after];s.post.return_value.status_code=200
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'posts-7.json'
            def check(*a,**kw):
                self.assertTrue(path.exists())
                self.assertEqual(json.loads(path.read_text())['before']['content'],html)
                self.assertNotIn('status',kw['json'])
                self.assertFalse(kw['allow_redirects'])
                return Mock(status_code=200)
            s.post.side_effect=check
            self.assertEqual(apply_plan(self.plan(),s,d)[0]['status'],'verified')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            s.post.side_effect=None;s.get.return_value.json.side_effect=[after,post]
            restore_backup(path,s)
            self.assertEqual(s.post.call_args.kwargs['json']['content'],html)
            self.assertEqual(apply_plan(self.plan(),s,d)[0]['status'],'already_attempted_inspect_backup')

    def test_other_site_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):apply_plan({'site':'https://other.test','version':1},Mock(),d)

    def test_hypothetical_return_examples(self):
        for end,want in [(920000,0),(940000,0.02),(850000,-0.07)]:
            self.assertAlmostEqual((end+80000-1000000)/1000000,want)


if __name__=='__main__':unittest.main()
