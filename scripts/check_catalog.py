#!/usr/bin/env python3
"""The checks on every change to the catalog (ASCAT-020 to ASCAT-025).

    python3 scripts/check_catalog.py                      # the offline checks
    python3 scripts/check_catalog.py --base REF [--labels a,b]
        # also, for the app files changed since REF: release assets on
        # GitHub (ASCAT-023) and the reviewed-script label (ASCAT-025); and
        # packaging/VERSION rises when a metapackage's recommends changed (ASPUB-003)

Offline: every app and collection file matches its schema (ASCAT-020); no
id or alias is used twice and no command is used by two apps unless both
name the other in shares_bin (ASCAT-021); every collection names real apps
and no app is in two collections (ASCAT-022); the generated files are
current (ASCAT-024). Exits 1 naming each problem's file. GITHUB_TOKEN, when
set, raises the GitHub API limit; release lookups are cached for a day in
target/release-assets.json. Stdlib only (Python 3.11+).
"""
import fnmatch
import json
import os
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402

ROOT = af.ROOT
CACHE = ROOT / "target" / "release-assets.json"
CACHE_SECONDS = 86400
LABEL = "reviewed-script"


def commands(app):
    """The commands an app puts on PATH: bin and each check alternative."""
    out = {app["bin"]} if app.get("bin") else set()
    for alt in app.get("check", "").split("|"):
        if alt and not alt.startswith("font=") and alt != "consolefonts":
            out.add(alt)
    return out


def uniqueness(apps):
    """ASCAT-021 problems."""
    problems, names = [], {}
    for i, a in sorted(apps.items()):
        for alias in a.get("aliases", []):
            other = names.get(alias) or (alias if alias in apps and alias != i else None)
            if other:
                problems.append(f"apps/{i}.toml: alias {alias!r} is already {other!r}")
            names[alias] = i
        for s in a.get("shares_bin", []):
            if s not in apps:
                problems.append(f"apps/{i}.toml: shares_bin names {s!r}, which has no app file")
    by_cmd = {}
    for i, a in sorted(apps.items()):
        for c in commands(a):
            by_cmd.setdefault(c, []).append(i)
    for c, ids in sorted(by_cmd.items()):
        for x in ids:
            for y in ids:
                if x < y and not (y in apps[x].get("shares_bin", []) and x in apps[y].get("shares_bin", [])):
                    problems.append(f"apps/{x}.toml and apps/{y}.toml: both install {c!r}; if they are "
                                    f"different apps, each names the other in shares_bin")
    return problems


def offline(root=ROOT):
    """Every offline problem (ASCAT-020, 021, 022, 024) as a list of strings."""
    try:
        apps = af.load_apps(root / "apps")
        bc.membership(apps, af.load_collections(root / "collections"))
    except (af.FileError, bc.BuildError) as e:
        return str(e).splitlines()
    problems = uniqueness(apps)
    if problems:
        return problems
    try:
        stale, _ = bc.stale(root)
    except (af.FileError, bc.BuildError) as e:
        return str(e).splitlines()
    return [f"{p} is stale; run python3 scripts/build_catalog.py" for p in stale]


# ── Changed app files ──────────────────────────────────────────────────


def git(*args, root=ROOT):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def changed(base, root=ROOT):
    """{id: (app before or None, app now)} for app files changed since base."""
    out = {}
    for f in git("diff", "--name-only", "--no-renames", "--diff-filter=AM", f"{base}...HEAD", "--", "apps/", root=root).split():
        i = Path(f).stem
        try:
            old = tomllib.loads(git("show", f"{base}:{f}", root=root))
        except subprocess.CalledProcessError:
            old = None
        out[i] = (old, tomllib.loads((root / f).read_text(encoding="utf-8")))
    return out


def script_review(changes, labels):
    """ASCAT-025: an added or changed recipe that runs a downloaded script needs the label."""
    if LABEL in labels:
        return []
    out = []
    for i, (old, new) in sorted(changes.items()):
        r = new.get("install", {}).get("recipe", {})
        if r.get("method") == "script" and r != (old or {}).get("install", {}).get("recipe"):
            out.append(f"apps/{i}.toml: a script recipe ({r.get('install', '')!r}) needs the {LABEL!r} "
                       f"label after a maintainer read the script")
    return out


def latest_assets(repo, fetch=None):
    """The asset names of repo's latest release (cached), or None when it has none."""
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(repo)
    if hit and time.time() - hit["at"] < CACHE_SECONDS:
        return hit["assets"]
    assets = (fetch or fetch_assets)(repo)
    cache[repo] = {"at": time.time(), "assets": assets}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return assets


def fetch_assets(repo):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "tetron-appstore-ci"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return [a["name"] for a in json.load(r).get("assets", [])]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def release_assets(changes, fetch=None):
    """ASCAT-023: each changed [install.release] pattern matches an asset of the latest release."""
    out = []
    for i, (_, new) in sorted(changes.items()):
        rel = new.get("install", {}).get("release")
        if not rel:
            continue
        assets = latest_assets(rel["repo"], fetch)
        if assets is None:
            out.append(f"apps/{i}.toml: {rel['repo']} has no latest release")
            continue
        for arch in ("amd64", "arm64"):
            pat = rel.get(arch)
            if pat and not any(fnmatch.fnmatchcase(a, pat) for a in assets):
                out.append(f"apps/{i}.toml: no {arch} asset matching {pat!r} in {rel['repo']}'s latest release")
    return out


def version_tuple(v):
    """(0, 15, 3) from "0.15.3" or "0.15.3-1"."""
    return tuple(int(x) for x in v.strip().split("-")[0].split("."))


def metapackage_version(base, root=ROOT):
    """ASPUB-003: packaging/VERSION rises when a metapackage's recommends change."""
    def at_base(f):
        try:
            return git("show", f"{base}:{f}", root=root)
        except subprocess.CalledProcessError:
            return None
    changed = [s for s in bc.PACKAGES if at_base(f"packaging/{s}.toml") is not None and
               tomllib.loads(at_base(f"packaging/{s}.toml")).get("recommends")
               != tomllib.loads((root / "packaging" / f"{s}.toml").read_text(encoding="utf-8")).get("recommends")]
    old = at_base("packaging/VERSION")
    if not changed or old is None:
        return []
    new = (root / "packaging" / "VERSION").read_text(encoding="utf-8")
    if version_tuple(new) <= version_tuple(old):
        return [f"packaging/VERSION: the recommends of {', '.join(changed)} changed, so it must rise "
                f"above {old.strip()}"]
    return []


def main(argv):
    problems = offline()
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
        labels = set(argv[argv.index("--labels") + 1].split(",")) if "--labels" in argv else set()
        changes = changed(base)
        problems += script_review(changes, labels) + release_assets(changes) + metapackage_version(base)
    for p in problems:
        print(f"check_catalog: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
