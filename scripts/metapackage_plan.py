#!/usr/bin/env python3
"""Whether a catalog release builds the collection metapackages (ASPUB-003).

    python3 scripts/metapackage_plan.py [PACKAGES_URL]

Compares packaging/VERSION with the newest tetron-wm-essentials,
-recommended and -extras in the tetronos apt repository (its amd64 Packages
index). Prints "build" when VERSION is newer than all of them, "skip" when
VERSION is the newest published one (no collection changed since). Exits 1 when
VERSION is older than a published one: apt would never choose it, and it
would mean the patch number went down. Stdlib only (Python 3.11+).
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog as bc  # noqa: E402
from check_catalog import version_tuple  # noqa: E402

INDEX = "https://tetronos.github.io/apt/dists/stable/main/binary-amd64/Packages"
NAMES = {f"tetron-wm-{s}" for s in bc.PACKAGES}


def published(index_text):
    """{package: [version tuples]} of the metapackages in a Packages index."""
    out, pkg = {}, None
    for line in index_text.splitlines():
        if line.startswith("Package: "):
            pkg = line[9:].strip()
        elif line.startswith("Version: ") and pkg in NAMES:
            out.setdefault(pkg, []).append(version_tuple(line[9:]))
    return out


def plan(version, index_text):
    v = version_tuple(version)
    pub = published(index_text)
    newest = max((x for vs in pub.values() for x in vs), default=None)
    if newest is None or v > newest:
        return "build", None
    if v == newest and all(v in vs for vs in pub.values()) and len(pub) == len(NAMES):
        return "skip", None
    shown = ".".join(map(str, newest))
    return None, f"packaging/VERSION {version.strip()} is not newer than the published {shown}; raise it"


def main(argv):
    url = argv[0] if argv else INDEX
    with urllib.request.urlopen(url, timeout=60) as r:
        index = r.read().decode("utf-8")
    decision, err = plan((bc.ROOT / "packaging" / "VERSION").read_text(encoding="utf-8"), index)
    if err:
        print(f"metapackage_plan: {err}", file=sys.stderr)
        return 1
    print(decision)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
