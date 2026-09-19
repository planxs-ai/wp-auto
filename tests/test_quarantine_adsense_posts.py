import unittest
from unittest.mock import Mock

from scripts.quarantine_adsense_posts import candidate_ids, quarantine, SITE


class QuarantineTests(unittest.TestCase):
    def plan(self):
        rows = [{"id": 1, "review_flags": ["experience_evidence_required"]},
                {"id": 2, "review_flags": ["no_external_reference_link"]},
                {"id": 1426, "review_flags": ["unsupported_outcome_review"]}]
        return {"site": SITE, "version": 1, "rows": rows}

    def test_only_high_risk_unverified_posts_are_selected(self):
        self.assertEqual(candidate_ids(self.plan()), [1])

    def test_dry_run_never_writes(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {"title": {"raw": "t"}, "content": {"raw": "c"},
                                      "excerpt": {"raw": "e"}, "status": "publish", "slug": "s"}
        response.raise_for_status.return_value = None
        session.get.return_value = response
        result = quarantine(self.plan(), session, apply=False)
        self.assertEqual(result["items"][0]["result"], "would_draft")
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
