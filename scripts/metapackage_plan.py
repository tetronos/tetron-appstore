#!/usr/bin/env python3
"""Whether a catalog release builds the collection metapackages, and at
which version (ASPUB-003).

    python3 scripts/metapackage_plan.py [PACKAGES_URL [RELEASES_URL]]

Prints "build VERSION" or "skip". Builds when the Depends or Recommends of
tetron-wm-essentials, -recommended or -extras (packaging/*.toml, with
{minor} filled in) differ from the newest published one in the tetronos apt
repository, or one is not published. VERSION is the newest published patch
plus one (apt index and this repository's catalog releases, which apt may
not have yet), or packaging/VERSION (the floor) when that is higher. Nobody
raises a version by hand. GH_TOKEN or GITHUB_TOKEN, when set, is used for
the GitHub API. Stdlib only (Python 3.11+).
"""
import json
import os
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog as bc  # noqa: E402
from check_catalog import version_tuple  # noqa: E402

INDEX = "https://tetronos.github.io/apt/dists/stable/main/binary-amd64/Packages"
RELEASES = "https://api.github.com/repos/tetronos/tetron-appstore/releases?per_page=100"
NAMES = {f"tetron-wm-{s}": s for s in bc.PACKAGES}
ASSET = re.compile(r"^tetron-wm-(?:%s)_([0-9.]+)-[0-9]+_all\.deb$" % "|".join(bc.PACKAGES))


def relations(text):
    """A Depends or Recommends value as a sorted list (spacing does not matter)."""
    return sorted(" ".join(x.split()) for x in text.split(",") if x.strip())


def published(index_text):
    """{package: (newest version tuple, {"Depends": [...], "Recommends": [...]})} from a Packages index."""
    out, cur = {}, {}

    def flush():
        p = cur.get("Package")
        if p in NAMES:
            v = version_tuple(cur.get("Version", "0"))
            if p not in out or v > out[p][0]:
                out[p] = (v, {k: relations(cur.get(k, "")) for k in ("Depends", "Recommends")})
    for line in index_text.splitlines() + [""]:
        if not line.strip():
            flush(), cur.clear()
        elif not line[0].isspace() and ":" in line:
            k, v = line.split(":", 1)
            cur[k] = v.strip()
    return out


def wanted(floor, root=bc.ROOT):
    """{package: {"Depends": [...], "Recommends": [...]}} as this checkout would build them."""
    minor = ".".join(floor.strip().split(".")[:2])
    out = {}
    for p, s in NAMES.items():
        t = tomllib.loads((root / "packaging" / f"{s}.toml").read_text(encoding="utf-8"))
        out[p] = {"Depends": relations(", ".join(t.get("depends", [])).replace("{minor}", minor)),
                  "Recommends": relations(", ".join(t.get("recommends", [])))}
    return out


def released(releases_json):
    """Version tuples of the metapackages attached to this repository's releases."""
    return [version_tuple(m.group(1)) for r in releases_json for a in r.get("assets", [])
            if (m := ASSET.match(a.get("name", "")))]


def plan(floor, index_text, releases_json=(), want=None):
    """("build", "0.15.20") or ("skip", None)."""
    pub = published(index_text)
    want = want if want is not None else wanted(floor)
    if all(p in pub and pub[p][1] == want[p] for p in NAMES):
        return "skip", None
    seen = [v for v, _ in pub.values()] + released(releases_json)
    f = version_tuple(floor)
    newest = max((v for v in seen if v[:2] == f[:2]), default=None)
    nxt = f if newest is None else max(f, newest[:2] + (newest[2] + 1,))
    return "build", ".".join(map(str, nxt))


def fetch(url):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "tetron-appstore"}
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok and url.startswith("https://api.github.com/"):
        h["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def main(argv):
    index = fetch(argv[0] if argv else INDEX)
    rel = json.loads(fetch(argv[1] if len(argv) > 1 else RELEASES))
    decision, version = plan((bc.ROOT / "packaging" / "VERSION").read_text(encoding="utf-8"), index, rel)
    print(decision if version is None else f"{decision} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
