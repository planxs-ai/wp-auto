#!/usr/bin/env python3
"""Keep the five reviewed PlanX posts public and move every other post to draft."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

SITE = "https://planx-ai.com"
KEEP_PUBLIC = {1426, 1427, 1428, 1429, 1430}


def candidate_ids(plan):
    return sorted({
        int(row["id"])
        for row in plan["rows"]
        if row.get("kind", "posts") == "posts"
        and int(row["id"]) not in KEEP_PUBLIC
    })


def quarantine(plan, session, apply=False):
    if plan.get("site") != SITE or plan.get("version") != 1:
        raise ValueError("Unexpected plan target or version")
    ids = candidate_ids(plan)
    plan_post_ids = {int(row["id"]) for row in plan["rows"]
                     if row.get("kind", "posts") == "posts"}
    expected = len(plan_post_ids - KEEP_PUBLIC)
    if int(plan.get("post_count", 0)) != len(plan_post_ids):
        raise ValueError("Plan post count does not match its rows")
    if len(ids) != expected or not 1 <= len(ids) <= 700:
        raise ValueError(f"Refusing unexpected candidate count: {len(ids)}")
    result = {"site": SITE, "created_at": datetime.now(timezone.utc).isoformat(),
              "apply": apply, "candidate_count": len(ids), "items": []}
    for post_id in ids:
        endpoint = f"{SITE}/wp-json/wp/v2/posts/{post_id}"
        response = session.get(endpoint, params={"context": "edit"}, timeout=30)
        response.raise_for_status()
        post = response.json()
        before = {key: post[key]["raw"] if isinstance(post.get(key), dict) else post.get(key)
                  for key in ("title", "content", "excerpt", "status", "slug")}
        item = {"id": post_id, "before": before, "result": "already_not_public"}
        if before["status"] == "publish":
            item["result"] = "would_draft"
            if apply:
                written = session.post(endpoint, json={"status": "draft"}, timeout=30,
                                       allow_redirects=False)
                if written.status_code not in (200, 201):
                    raise ValueError(f"Draft write rejected for {post_id}")
                checked = session.get(endpoint, params={"context": "edit"}, timeout=30)
                checked.raise_for_status()
                if checked.json().get("status") != "draft":
                    raise ValueError(f"Draft verification failed for {post_id}")
                item["result"] = "draft_verified"
        result["items"].append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="docs/adsense/remediation-plan.json")
    parser.add_argument("--output", default="adsense-quarantine-backup.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.environ.get("WP_URL", "").rstrip("/") != SITE:
        parser.error("WP_URL must be https://planx-ai.com")
    if not all(os.environ.get(k) for k in ("WP_USERNAME", "WP_APP_PASSWORD")):
        parser.error("WordPress credentials are required")
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    with requests.Session() as session:
        session.auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
        result = quarantine(plan, session, apply=args.apply)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {status: sum(i["result"] == status for i in result["items"])
               for status in sorted({i["result"] for i in result["items"]})}
    print(json.dumps({"candidate_count": result["candidate_count"], "summary": summary}))


if __name__ == "__main__":
    main()
