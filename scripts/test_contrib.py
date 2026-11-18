"""Tests for scripts/tetron-app (ASCAT-026, ASCAT-027) and scripts/import_sync.py
(ASCAT-018, ASCAT-019).

    python3 -m unittest scripts/test_contrib.py
"""
import importlib.machinery
import importlib.util
import json
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import appfiles as af  # noqa: E402
import import_sync as isync  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("tetron_app", str(HERE / "tetron-app"))
ta = importlib.util.module_from_spec(importlib.util.spec_from_loader("tetron_app", _loader))
_loader.exec_module(ta)


def app(i, **kw):
    return dict({"id": i, "name": i, "bin": i, "category": "c", "description": "d",
                 "homepage": f"https://github.com/o/{i}"}, **kw)


class AssetPattern(unittest.TestCase):
    NAMES = ["x-1.2.0-x86_64-unknown-linux-gnu.tar.gz", "x-1.2.0-x86_64-unknown-linux-musl.tar.gz",
             "x-1.2.0-x86_64-unknown-linux-musl.tar.gz.sha256", "x_1.2.0_amd64.deb",
             "x-1.2.0-aarch64-apple-darwin.tar.gz", "x_1.2.0_arm64.deb", "x-1.2.0-x86_64-pc-windows-msvc.zip"]

    def test_tar_gz_musl_first_version_as_star(self):
        self.assertEqual(ta.asset_pattern(self.NAMES, "amd64", "v1.2.0"), "x-*-x86_64-unknown-linux-musl.tar.gz")

    def test_deb_when_no_linux_tar_gz(self):
        self.assertEqual(ta.asset_pattern(self.NAMES, "arm64", "1.2.0"), "x_*_arm64.deb")

    def test_none(self):
        self.assertIsNone(ta.asset_pattern(["x.zip", "x-darwin.tar.gz"], "amd64", "1"))


class NewApp(unittest.TestCase):
    def fetch(self, path):
        return {"repos/o/new": {"name": "New", "full_name": "O/new", "description": " A tool ",
                                "license": {"spdx_id": "MIT"}},
                "repos/O/new/releases/latest": {"tag_name": "v2.0", "assets": [
                    {"name": "new-v2.0-linux-amd64.tar.gz"}, {"name": "new-v2.0-linux-arm64.tar.gz"}]}}.get(path)

    def test_from_repository_and_release(self):
        a, notes = ta.new_app("https://github.com/o/new", self.fetch, {"x": app("x")})
        self.assertEqual(a, {"id": "new", "name": "New", "bin": "new", "category": "", "description": "A tool",
                             "homepage": "https://github.com/O/new", "license": "MIT",
                             "install": {"release": {"repo": "O/new", "amd64": "new-*-linux-amd64.tar.gz",
                                                     "arm64": "new-*-linux-arm64.tar.gz"}},
                             "source": {"lists": ["tetron"]}})
        self.assertIn("fill in category", notes[0])
        af.dump_app(a)

    def test_refuses_known_repo_taken_id_and_non_github(self):
        with self.assertRaisesRegex(af.FileError, "already apps/x.toml"):
            ta.new_app("https://github.com/O/new", self.fetch, {"x": app("x", homepage="https://github.com/o/new")})
        with self.assertRaisesRegex(af.FileError, "taken"):
            ta.new_app("https://github.com/o/new", self.fetch, {"y": app("y", aliases=["new"])})
        with self.assertRaisesRegex(af.FileError, "not a github.com"):
            ta.new_app("https://gitlab.com/o/new", self.fetch, {})


class Tree(unittest.TestCase):
    """A temporary root with the real collections and the given apps and lists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(af.COLLECTIONS, self.root / "collections")
        (self.root / "apps").mkdir()
        (self.root / "sources").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def apps(self, *apps):
        for a in apps:
            af.write_app(a, self.root / "apps")

    def lists(self, **lists):
        for k, v in lists.items():
            (self.root / "sources" / f"{k}.json").write_text(json.dumps(v), encoding="utf-8")

    def read(self, i):
        return tomllib.loads((self.root / "apps" / f"{i}.toml").read_text(encoding="utf-8"))


class AddTo(Tree):
    def test_appends_and_keeps_comments(self):
        p = self.root / "collections" / "extras.toml"
        p.write_text(p.read_text(encoding="utf-8").replace("apps = [", "# kept\napps = [", 1), encoding="utf-8")
        self.apps(app("zzz-new"))
        ta.add_to("extras", "zzz-new", self.root)
        text = p.read_text(encoding="utf-8")
        self.assertIn("# kept", text)
        self.assertEqual(tomllib.loads(text)["apps"][-1], "zzz-new")

    def test_refuses_unknown_collection_missing_file_second_collection(self):
        member = tomllib.loads((self.root / "collections" / "essentials.toml").read_text())["apps"][0]
        self.apps(app(member))
        for args, msg in ((("nope", member), "no collection"), (("extras", "ghost"), "does not exist"),
                          (("extras", member), "already in collections/essentials.toml")):
            with self.assertRaisesRegex(af.FileError, msg):
                ta.add_to(*args, self.root)


ENTRY = {"category": "Editors", "description": "e", "homepage": "https://github.com/u/{}"}


def entry(name, **kw):
    return dict(ENTRY, name=name, bin=name, homepage=ENTRY["homepage"].format(name), **kw)


class ImportSync(Tree):
    def test_new_gone_back_and_never_deleted(self):
        self.apps(app("stays", homepage="https://github.com/u/stays", source={"lists": ["awesome-tuis"]}),
                  app("left", source={"lists": ["terminaltrove", "tetron"]}),
                  app("back", homepage="https://github.com/u/back", source={"lists": ["tetron"], "gone": True}),
                  app("ours", source={"lists": ["tetron"]}))
        self.lists(**{"awesome-tuis": [entry("stays"), entry("fresh")],
                      "terminaltrove": [entry("back"), entry("Fresh", cli=True)]})
        added, skipped, gone, back, relisted = isync.sync(self.root)
        self.assertEqual((added, skipped, gone, back), (["fresh"], [], ["left"], ["back"]))
        self.assertEqual(self.read("left")["source"], {"lists": ["tetron"], "gone": True})
        self.assertEqual(self.read("back")["source"], {"lists": ["terminaltrove", "tetron"]})
        self.assertEqual(self.read("ours")["source"], {"lists": ["tetron"]})
        self.assertEqual(self.read("fresh"), {"id": "fresh", "name": "fresh", "bin": "fresh", "category": "Editors",
                                              "description": "e", "homepage": "https://github.com/u/fresh",
                                              "source": {"lists": ["awesome-tuis", "terminaltrove"]}})
        self.assertEqual(sorted(p.stem for p in (self.root / "apps").glob("*.toml")),
                         ["back", "fresh", "left", "ours", "stays"])
        self.assertEqual(isync.sync(self.root), ([], [], [], [], []))

    def test_same_name_other_repo_is_not_added(self):
        self.apps(app("ampcode", name="Amp", homepage="https://ampcode.com", source={"lists": ["tetron"]}))
        self.lists(**{"awesome-tuis": [entry("amp")]})
        self.assertEqual(isync.sync(self.root)[4], [])
        self.assertEqual(self.read("ampcode")["source"], {"lists": ["tetron"]})

    def test_command_clash_is_reported_not_written(self):
        self.apps(app("bat", check="batcat|bat", source={"lists": ["tetron"]}))
        self.lists(**{"awesome-tuis": [dict(entry("batcat-tui"), bin="batcat")]})
        self.assertEqual(isync.sync(self.root)[:2], ([], [("batcat-tui", "command 'batcat' is already installed by another app")]))
        self.assertIn("Not added (1)", isync.report([], [("batcat-tui", "x")], [], [], []))


class RealFiles(unittest.TestCase):
    def test_real_lists_change_at_most_dua(self):
        """The real app files agree with sources/ (dua is on awesome-tuis as dua-cli)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for sub in ("apps", "collections", "sources"):
                shutil.copytree(af.ROOT / sub, root / sub)
            r = isync.sync(root)
            self.assertEqual(r[:4], ([], [], [], []))
            self.assertLessEqual(set(r[4]), {"dua"})


if __name__ == "__main__":
    unittest.main()
