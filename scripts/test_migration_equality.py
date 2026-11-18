"""ASCAT-029: the catalog built from apps/ and collections/ equals the catalog
merged before the move (commit BEFORE, the last merge on main), apart from
the added fields and the named changes below. Kept until phase 1 is merged.

Needs the git history (CI checks out with fetch-depth 0).

    python3 -m unittest scripts/test_migration_equality.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog  # noqa: E402

ROOT = build_catalog.ROOT
BEFORE = "2e4072d"
ADDED = {"id", "collection"}
# Named changes, each with its reason.
# A collection member's package names are the ones its suite line used,
# checked in containers (they were two lists before, now one).
PKG_FROM_SUITE = {"AI Mode", "bat", "curl", "delta", "fd", "mtr", "pandoc", "tcpdump",
                  "tetron-browser"}
# tier follows the collection: these carried a hand-written tier that
# disagreed with their set (or had none).
TIER_FROM_COLLECTION = {"AI Mode", "torrentTUI"}


def before():
    text = subprocess.run(["git", "show", f"{BEFORE}:assets/catalog.json"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout
    return json.loads(text)


def suite_by_size(text):
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            out.setdefault(line.split(":")[0], []).append(line)
    return {k: sorted(v) for k, v in out.items()}


class MigrationKeepsTheCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = before()
        cls.new = json.loads(build_catalog.build()["assets/catalog.json"])

    def test_same_apps(self):
        self.assertEqual(sorted(a["name"] for a in self.old["apps"]), sorted(a["name"] for a in self.new["apps"]))

    def test_same_fields_apart_from_the_named_changes(self):
        old = {a["name"]: a for a in self.old["apps"]}
        diffs = []
        for n in self.new["apps"]:
            o = dict(old[n["name"]])
            n = {k: v for k, v in n.items() if k not in ADDED}
            o["sources"] = list(dict.fromkeys(o["sources"]))
            if n["name"] in PKG_FROM_SUITE:
                o.pop("pkg", None), n.pop("pkg", None)
            if n["name"] in TIER_FROM_COLLECTION:
                o.pop("tier"), n.pop("tier")
            for k in sorted(set(o) | set(n)):
                if o.get(k) != n.get(k):
                    diffs.append(f"{n['name']}.{k}: {o.get(k)!r} -> {n.get(k)!r}")
        self.assertEqual(diffs, [])

    def test_named_changes_are_still_changes(self):
        """A name listed above whose field no longer differs is dropped from the list."""
        old = {a["name"]: a for a in self.old["apps"]}
        new = {a["name"]: a for a in self.new["apps"]}
        self.assertEqual([x for x in sorted(PKG_FROM_SUITE) if old[x].get("pkg") == new[x].get("pkg")], [])
        self.assertEqual([x for x in sorted(TIER_FROM_COLLECTION) if old[x]["tier"] == new[x]["tier"]], [])

    def test_same_suite_lines_per_size(self):
        self.assertEqual(suite_by_size(self.old["suite_apps"]), suite_by_size(self.new["suite_apps"]))

    def test_schema_unchanged(self):
        self.assertEqual(self.old["schema"], self.new["schema"])


if __name__ == "__main__":
    unittest.main()
