import unittest
from unittest.mock import Mock

from scripts.quarantine_adsense_posts import candidate_ids, quarantine, SITE


class QuarantineTests(unittest.TestCase):
    def plan(self):
        rows = [{"id": 1, "review_flags": ["experience_evidence_required"]},
                {"id": 2, "review_flags": ["no_external_reference_link"]},
                {"id": 1426, "review_flags": ["unsupported_outcome_review"]}]
        return {"site": SITE, "version": 1, "post_count": 3, "rows": rows}

    def test_only_reviewed_posts_are_kept_public(self):
        self.assertEqual(candidate_ids(self.plan()), [1, 2])

    def test_dry_run_never_writes(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {"title": {"raw": "t"}, "content": {"raw": "c"},
                                      "excerpt": {"raw": "e"}, "status": "publish", "slug": "s"}
        response.raise_for_status.return_value = None
        session.get.return_value = response
        result = quarantine(self.plan(), session, apply=False)
        self.assertEqual([item["result"] for item in result["items"]],
                         ["would_draft", "would_draft"])
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
