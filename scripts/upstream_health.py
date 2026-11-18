#!/usr/bin/env python3
"""Upstream health of the collection members (ASCAT-017).

    python3 scripts/upstream_health.py OUT.json

For each member with a GitHub repository (its homepage or its release repo):
archived, no release for 18 months (when it has releases), or the repository
gone. For another homepage: gone (404 or 410). Writes
{"date": ..., "apps": {id: {flag: true}}} with every member checked (an
empty table when healthy). GITHUB_TOKEN, when set, raises the API limit.
Stdlib only (Python 3.11+).
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402

STALE_DAYS = 548  # 18 months


def get(url, method="GET"):
    """(status, json or None)."""
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "tetron-appstore-ci",
                                                               "Accept": "application/vnd.github+json"})
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, (json.load(r) if method == "GET" else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, None


def flags_for(app, today, http=get):
    repo = app.get("install", {}).get("release", {}).get("repo") or af.gh_repo(app.get("homepage"))
    if repo:
        code, info = http(f"https://api.github.com/repos/{repo}")
        if code == 404:
            return {"gone": True}
        if code != 200:
            return {}
        flags = {"archived": bool(info.get("archived"))}
        code, rel = http(f"https://api.github.com/repos/{repo}/releases/latest")
        if code == 200 and rel.get("published_at"):
            published = datetime.date.fromisoformat(rel["published_at"][:10])
            flags["no_release_18_months"] = (today - published).days > STALE_DAYS
        return {k: v for k, v in flags.items() if v}
    if app.get("homepage", "").startswith("http"):
        code, _ = http(app["homepage"], "HEAD")
        return {"gone": True} if code in (404, 410) else {}
    return {}


def main(argv):
    apps = af.load_apps()
    members = bc.membership(apps, af.load_collections())
    today = datetime.date.today()
    doc = {"date": today.isoformat(), "apps": {i: flags_for(apps[i], today) for i in sorted(members)}}
    Path(argv[0]).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    flagged = {i: f for i, f in doc["apps"].items() if f}
    print(f"{len(doc['apps'])} members checked, {len(flagged)} flagged: {flagged}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
