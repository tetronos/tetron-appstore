#!/usr/bin/env python3
"""Fold install test results and upstream health into status/<id>.json
(ASCAT-016, ASCAT-017).

    python3 scripts/update_status.py RESULTS.json... [--health HEALTH.json] [--issue OUT.md]

A status file changes only when something flips: an app's result on a
platform (ok, fail, skipped) differs from the stored one, or is the first,
or its health flags change. The date in the file is when that happened, so a
weekly run that finds nothing new changes no file. Prints the changed ids.
With --issue, writes a Markdown list of the collection members that fail or
are flagged (nothing when there are none). Stdlib only (Python 3.11+).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402

ROOT = af.ROOT


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fold(status, platform, date, res):
    """status with this run's result for platform; (status, changed)."""
    old = status.get("platforms", {}).get(platform)
    if old and old.get("result") == res["result"]:
        return status, False
    entry = {"result": res["result"], "since": date, "method": res.get("method", "")}
    for k in ("tail", "why"):
        if res.get(k):
            entry[k] = res[k]
    status = dict(status, platforms=dict(status.get("platforms", {}), **{platform: entry}))
    return status, True


def fold_health(status, date, flags):
    flags = {k: v for k, v in flags.items() if v}
    old = {k: v for k, v in status.get("health", {}).items() if k != "since"}
    if old == flags:
        return status, False
    status = dict(status)
    if flags:
        status["health"] = dict(flags, since=date)
    else:
        status.pop("health", None)
    return status, True


def update(runs, health, status_dir):
    """Write the flipped status files; return the changed ids."""
    status_dir.mkdir(exist_ok=True)
    changed = set()
    ids = {i for r in runs for i in r["results"]} | set(health.get("apps", {}))
    for i in sorted(ids):
        path = status_dir / f"{i}.json"
        st, any_change = load(path), False
        for r in runs:
            if i in r["results"]:
                st, c = fold(st, r["platform"], r["date"], r["results"][i])
                any_change |= c
        if i in health.get("apps", {}):
            st, c = fold_health(st, health["date"], health["apps"][i])
            any_change |= c
        if any_change:
            path.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            changed.add(i)
    return sorted(changed)


def issue(runs, health, members):
    """Markdown lines for collection members that fail or are flagged."""
    lines = []
    for i in sorted(members):
        fails = [r["platform"] for r in runs if r["results"].get(i, {}).get("result") == "fail"]
        flags = sorted(k for k, v in health.get("apps", {}).get(i, {}).items() if v)
        if fails or flags:
            what = (["fails on " + ", ".join(fails)] if fails else []) + flags
            lines.append(f"- `{i}` ({members[i]}): {'; '.join(what)}")
    return lines


def main(argv):
    health = {}
    out_issue = None
    files = []
    it = iter(argv)
    for a in it:
        if a == "--health":
            health = load(next(it))
        elif a == "--issue":
            out_issue = next(it)
        else:
            files.append(a)
    runs = [load(f) for f in files]
    runs = [r for r in runs if r.get("results") is not None]
    for i in update(runs, health, ROOT / "status"):
        print(i)
    if out_issue:
        members = bc.membership(af.load_apps(), af.load_collections())
        lines = issue(runs, health, members)
        Path(out_issue).write_text(
            ("The install test or the upstream health check flagged these collection members:\n\n"
             + "\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
