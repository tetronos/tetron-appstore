#!/usr/bin/env python3
# reconcile.py -- run from the tetron-appstore repo root.
# Checks the automatable constraints (CON-AS*) in spec/constraints.py.
# Requirements (ASCAT-*, ASPUB-*, ASCLI-*) are verified by the tests, CI and review.
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "scripts")


def check_build() -> dict:
    """CON-AS01: the generated files are what scripts/build_catalog.py makes."""
    r = subprocess.run([sys.executable, "scripts/build_catalog.py", "--check"], capture_output=True, text=True)
    return {"current": r.returncode == 0, "stale": r.stderr.strip().splitlines()}


def check_files() -> dict:
    """CON-AS02: the offline catalog checks (schemas, uniqueness, collection references, generated files)."""
    import check_catalog
    return {"problems": check_catalog.offline()}


# CON-AS03. Files where these words are expected: the changelog (dates), lock
# files, imported data and the license text.
NOTES_ALLOWED = {"CHANGELOG.md", "Cargo.lock", "uv.lock", "LICENSE", ".gitignore", "reconcile.py"}
NOTES_SKIP_DIRS = ("sources/",)
# Built from parts so this file does not match itself.
OWNER = re.compile(r"(?<![$\w\"{])" + "US" + r"ER(?![\w])")
PRIVATE_DIR = "DO-NOT-" + "COMMIT"
DATE = r"\b20\d\d-[01]\d-[0-3]\d\b"
DATE_IN_COMMENT = re.compile(r"(#|//|/\*|<!--).*" + DATE)
DATE_ANY = re.compile(DATE)


def check_planning_notes() -> dict:
    """CON-AS03: no owner placeholder, private paths or comment dates in committed files."""
    hits = []
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    for f in files:
        if f in NOTES_ALLOWED or f.startswith(NOTES_SKIP_DIRS) or not Path(f).is_file():
            continue
        try:
            lines = Path(f).read_text().splitlines()
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(lines, 1):
            if OWNER.search(line) or PRIVATE_DIR in line or DATE_IN_COMMENT.search(line) \
                    or (f.startswith("spec/") and DATE_ANY.search(line)):
                hits.append(f"{f}:{n}: {line.strip()[:100]}")
    return {"count": len(hits), "hits": hits[:20]}


if __name__ == "__main__":
    ctx = {"build": check_build(), "files": check_files(), "planning_notes": check_planning_notes()}
    print(json.dumps(ctx, indent=2))
    sys.exit(0 if ctx["build"]["current"] and not ctx["files"]["problems"] and ctx["planning_notes"]["count"] == 0
             else 1)
