"""Tests for scripts/check_catalog.py (ASCAT-020 to ASCAT-025).

    python3 -m unittest scripts/test_check_catalog.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402
import check_catalog as cc  # noqa: E402


def app(i, **kw):
    return dict({"id": i, "name": i, "bin": i, "category": "c", "description": "d", "homepage": "h"}, **kw)


class Uniqueness(unittest.TestCase):
    def test_shared_command_needs_both_sides(self):
        apps = {"kilo": app("kilo"), "kilo-code": app("kilo-code", bin="kilo", shares_bin=["kilo"])}
        self.assertEqual(len(cc.uniqueness(apps)), 1)
        apps["kilo"]["shares_bin"] = ["kilo-code"]
        self.assertEqual(cc.uniqueness(apps), [])

    def test_check_alternatives_count_fonts_do_not(self):
        apps = {"bat": app("bat", check="batcat|bat"), "batcat": app("batcat"),
                "f1": app("f1", check="font=X"), "f2": app("f2", check="font=X")}
        self.assertEqual(cc.uniqueness(apps), ["apps/bat.toml and apps/batcat.toml: both install 'batcat'; "
                                               "if they are different apps, each names the other in shares_bin"])

    def test_alias_used_twice_or_naming_an_id(self):
        apps = {"a": app("a", aliases=["old"]), "b": app("b", aliases=["old"]), "c": app("c", aliases=["a"])}
        self.assertEqual(cc.uniqueness(apps), ["apps/b.toml: alias 'old' is already 'a'",
                                               "apps/c.toml: alias 'a' is already 'a'"])

    def test_shares_bin_names_a_real_app(self):
        self.assertEqual(cc.uniqueness({"a": app("a", shares_bin=["gone"])}),
                         ["apps/a.toml: shares_bin names 'gone', which has no app file"])


SCRIPT = {"install": {"recipe": {"install": "curl -fsSL https://x/i.sh | sh", "method": "script"}}}


class ScriptReview(unittest.TestCase):
    def test_new_or_changed_script_needs_the_label(self):
        changes = {"new": (None, SCRIPT), "same": (SCRIPT, SCRIPT),
                   "cargo": (None, {"install": {"recipe": {"install": "cargo install x", "method": "cargo"}}})}
        self.assertEqual([p.split(":")[0] for p in cc.script_review(changes, set())], ["apps/new.toml"])
        self.assertEqual(cc.script_review(changes, {"reviewed-script"}), [])


class ReleaseAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache, cc.CACHE = cc.CACHE, Path(self.tmp.name) / "cache.json"
        self.calls = []

    def tearDown(self):
        cc.CACHE = self.cache
        self.tmp.cleanup()

    def fetch(self, repo):
        self.calls.append(repo)
        return {"o/lazygit": ["lazygit_0.44_linux_x86_64.tar.gz", "lazygit_0.44_linux_arm64.tar.gz"]}.get(repo)

    def changes(self, **rel):
        return {"x": (None, {"install": {"release": dict({"repo": "o/lazygit"}, **rel)}})}

    def test_patterns_match_with_the_version_as_star(self):
        ch = self.changes(amd64="lazygit_*_linux_x86_64.tar.gz", arm64="lazygit_*_linux_arm64.tar.gz")
        self.assertEqual(cc.release_assets(ch, self.fetch), [])

    def test_missing_asset_named(self):
        self.assertEqual(cc.release_assets(self.changes(arm64="lazygit_*_aarch64.tar.gz"), self.fetch),
                         ["apps/x.toml: no arm64 asset matching 'lazygit_*_aarch64.tar.gz' in o/lazygit's latest release"])

    def test_no_release(self):
        self.assertEqual(cc.release_assets(self.changes(repo="o/none", amd64="x"), self.fetch),
                         ["apps/x.toml: o/none has no latest release"])

    def test_cached(self):
        ch = self.changes(amd64="lazygit_*_linux_x86_64.tar.gz")
        cc.release_assets(ch, self.fetch), cc.release_assets(ch, self.fetch)
        self.assertEqual(self.calls, ["o/lazygit"])


class ChangedFiles(unittest.TestCase):
    def test_only_added_or_changed_app_files_with_their_old_version(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = lambda *a: subprocess.run(a, cwd=root, check=True, capture_output=True)
            run("git", "init", "-q", "-b", "main")
            run("git", "config", "user.email", "t@t"), run("git", "config", "user.name", "t")
            (root / "apps").mkdir()
            for i in ("a", "b"):
                af.write_app(app(i), root / "apps")
            run("git", "add", "."), run("git", "commit", "-qm", "base")
            af.write_app(app("a", cli=True), root / "apps")
            af.write_app(app("c"), root / "apps")
            run("git", "add", "."), run("git", "commit", "-qm", "change")
            got = cc.changed("HEAD~1", root)
            self.assertEqual(sorted(got), ["a", "c"])
            self.assertEqual((got["a"][0], got["a"][1]["cli"], got["c"][0]), (app("a"), True, None))


class MetapackageVersion(unittest.TestCase):
    def repo(self, d, recs, version):
        root = Path(d)
        (root / "packaging").mkdir(exist_ok=True)
        (root / "packaging" / "recommended.toml").write_text(f"recommends = {recs}\n")
        (root / "packaging" / "VERSION").write_text(version + "\n")
        return root

    def test_changed_recommends_need_a_higher_version(self):
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
            run("git", "init", "-q", "-b", "main")
            run("git", "config", "user.email", "t@t"), run("git", "config", "user.name", "t")
            root = self.repo(d, '["a"]', "0.15.30")
            run("git", "add", "."), run("git", "commit", "-qm", "base")
            self.assertEqual(cc.metapackage_version("HEAD", root), [])
            self.repo(d, '["a", "b"]', "0.15.30")
            self.assertEqual(len(cc.metapackage_version("HEAD", root)), 1)
            self.repo(d, '["a", "b"]', "0.15.31")
            self.assertEqual(cc.metapackage_version("HEAD", root), [])

    def test_version_tuple(self):
        self.assertEqual(cc.version_tuple("0.15.3-1\n"), (0, 15, 3))
        self.assertLess(cc.version_tuple("0.15.9"), cc.version_tuple("0.15.10"))


class Plan(unittest.TestCase):
    INDEX = "".join(f"Package: tetron-wm-{s}\nVersion: {v}-1\n\n" for s in ("essentials", "recommended", "extras")
                    for v in ("0.15.16", "0.15.17")) + "Package: tetron-wm-desktop\nVersion: 0.15.40-1\n\n"

    def test_newer_builds_published_skips_older_refuses(self):
        import metapackage_plan as mp
        self.assertEqual(mp.plan("0.15.30", self.INDEX), ("build", None))
        self.assertEqual(mp.plan("0.15.17", self.INDEX), ("skip", None))
        self.assertIsNone(mp.plan("0.15.0", self.INDEX)[0])
        self.assertIsNone(mp.plan("0.15.16", self.INDEX)[0])
        self.assertEqual(mp.plan("0.15.1", ""), ("build", None))


class Offline(unittest.TestCase):
    def test_real_catalog_passes(self):
        self.assertEqual(cc.offline(), [])


if __name__ == "__main__":
    unittest.main()
