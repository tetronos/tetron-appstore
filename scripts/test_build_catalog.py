"""Tests for scripts/build_catalog.py and scripts/appfiles.py (ASCAT-001 to
ASCAT-014, ASCAT-020, ASCAT-022) on a small catalog in a temporary folder.

    python3 -m unittest scripts/test_build_catalog.py
"""
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402

APPS = {
    "htop": {"id": "htop", "name": "htop", "bin": "htop", "category": "System", "description": "Processes",
             "homepage": "https://github.com/htop-dev/htop", "install": {"pkg": {"brew": ""}},
             "source": {"lists": ["awesome-tuis", "tetron"]}},
    "bat": {"id": "bat", "name": "bat", "bin": "bat", "check": "batcat|bat", "category": "Files",
            "description": "cat with wings", "homepage": "https://github.com/sharkdp/bat", "cli": True,
            "requires_cwd": True, "notes": {"tip": "Try bat -A"},
            "install": {"recipe": {"install": "cargo install bat", "method": "cargo", "verified": True},
                        "release": {"repo": "sharkdp/bat", "amd64": "bat-*-x86_64.tar.gz"}}},
    "7zip": {"id": "7zip", "name": "7zip", "check": "7z|7zz", "store": False,
             "install": {"deb": "7zip | p7zip-full", "pkg": {"apt": "7zip", "dnf": "7zip", "pacman": "7zip",
                                                             "brew": "sevenzip"}}},
    "nerd-font": {"id": "nerd-font", "name": "nerd-font", "store": False, "install": {"script": "nerd-font"}},
    "zed": {"id": "zed", "name": "Zed", "bin": "zed", "category": "Editors", "description": "Not in a collection",
            "homepage": "https://zed.dev"},
}
COLLECTIONS = {"desktop": ["7zip", "htop"], "essentials": ["nerd-font"], "recommended": ["bat"], "extras": []}
REPOLOGY = {"names": {"htop": {"apt": "htop", "dnf": "htop", "brew": "htop"}, "bat": {"apt": "bat"}}}
RELEASES = {"repos": ["sharkdp/bat"]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ("apps", "collections", "sources", "assets"):
            (self.root / d).mkdir()
        for a in APPS.values():
            af.write_app(a, self.root / "apps")
        self.write_collections(COLLECTIONS)
        (self.root / "sources" / "repology.json").write_text(json.dumps(REPOLOGY))
        (self.root / "sources" / "releases.json").write_text(json.dumps(RELEASES))

    def tearDown(self):
        self.tmp.cleanup()

    def write_collections(self, members):
        for i, name in enumerate(af.COLLECTION_NAMES):
            c = {"name": name, "description": f"The {name} apps", "apps": members[name]}
            if i:
                c["includes"] = af.COLLECTION_NAMES[i - 1]
            (self.root / "collections" / f"{name}.toml").write_text(af.dump_collection(c, {"htop": "why"}))

    def doc(self):
        return json.loads(bc.build(self.root)["assets/catalog.json"])


class AppFiles(Fixture):
    def test_written_files_read_back_the_same(self):
        self.assertEqual(af.load_apps(self.root / "apps"), APPS)

    def test_collection_line_comments_are_kept_out_of_the_data(self):
        c = tomllib.loads((self.root / "collections" / "desktop.toml").read_text())
        self.assertEqual(c["apps"], ["7zip", "htop"])
        self.assertIn("# why", (self.root / "collections" / "desktop.toml").read_text())

    def test_schema_problem_names_the_file_and_the_field(self):
        (self.root / "apps" / "htop.toml").write_text('id = "htop"\nname = "htop"\nclii = true\n')
        with self.assertRaises(af.FileError) as e:
            af.load_apps(self.root / "apps")
        self.assertIn("apps/htop.toml: clii: unknown field", str(e.exception))
        self.assertIn("apps/htop.toml: bin: required", str(e.exception))

    def test_id_must_be_the_file_name(self):
        (self.root / "apps" / "other.toml").write_text(af.dump_app(APPS["zed"]))
        with self.assertRaises(af.FileError) as e:
            af.load_apps(self.root / "apps")
        self.assertIn("apps/other.toml: id must be 'other'", str(e.exception))

    def test_slug(self):
        self.assertEqual([af.slug(n) for n in ("btop++", "GitHub CLI", "AI Mode", "--")],
                         ["btop", "github-cli", "ai-mode", "app"])


class Build(Fixture):
    def test_store_apps_only_sorted_by_category_then_name(self):
        self.assertEqual([a["id"] for a in self.doc()["apps"]], ["zed", "bat", "htop"])

    def test_entry_in_the_released_format(self):
        bat = next(a for a in self.doc()["apps"] if a["id"] == "bat")
        self.assertEqual(bat["recipe"], {"install": "cargo install bat", "method": "cargo", "verified": True,
                                         "requires_cwd": True, "tip": "Try bat -A"})
        self.assertEqual((bat["tier"], bat["set"], bat["collection"], bat["releases"], bat["cli"]),
                         ("recommended", "recommended", "recommended", True, True))
        self.assertEqual(bat["pkg"], {"apt": "bat"})
        self.assertEqual(bat["sources"], [])

    def test_package_names_override_repology_name_by_name(self):
        htop = next(a for a in self.doc()["apps"] if a["id"] == "htop")
        self.assertEqual(htop["pkg"], {"apt": "htop", "dnf": "htop"})
        self.assertEqual((htop["tier"], htop["set"], htop["collection"]), ("default", "essentials", "desktop"))

    def test_no_collection_is_optional(self):
        zed = next(a for a in self.doc()["apps"] if a["id"] == "zed")
        self.assertEqual(zed["tier"], "optional")
        self.assertNotIn("set", zed)

    def test_collections_listed_in_order(self):
        self.assertEqual([(c["name"], c.get("includes"), c["apps"]) for c in self.doc()["collections"]],
                         [("desktop", None, ["7zip", "htop"]), ("essentials", "desktop", ["nerd-font"]),
                          ("recommended", "essentials", ["bat"]), ("extras", "recommended", [])])

    def test_suite_lines(self):
        suite = bc.build(self.root)["assets/suite-apps.txt"]
        self.assertEqual(suite, bc.HEADER + "essentials:apps:7z|7zz:7zip:7zip:7zip:sevenzip\n"
                         "essentials:apps:htop:htop:htop::\n"
                         "recommended:apps:batcat|bat:bat:::\n"
                         "essentials:script:nerd-font\n"
                         "recommended:release:batcat|bat:sharkdp/bat:bat-*-x86_64.tar.gz:\n")
        self.assertEqual(self.doc()["suite_apps"], suite)

    def test_recommends_deb_relation_else_apt_name_scripts_and_services_out(self):
        af.write_app(dict(APPS["htop"], id="nm", name="nm", bin="nmcli", group="services"), self.root / "apps")
        self.write_collections(dict(COLLECTIONS, desktop=["7zip", "htop", "nm"]))
        cols = {c["name"]: c["recommends"] for c in self.doc()["collections"]}
        self.assertEqual(cols, {"desktop": ["7zip | p7zip-full", "htop"], "essentials": [], "recommended": ["bat"],
                                "extras": []})

    def test_packaging_recommends_written(self):
        (self.root / "packaging").mkdir()
        (self.root / "packaging" / "recommended.toml").write_text('name = "x"\nrecommends = [\n  "old",\n]\nsection = "s"\n')
        out = bc.build(self.root)
        self.assertEqual(out["packaging/recommended.toml"], 'name = "x"\nrecommends = [\n  "bat",\n]\nsection = "s"\n')
        self.assertNotIn("packaging/desktop.toml", out)

    def test_same_files_same_bytes(self):
        self.assertEqual(bc.build(self.root), bc.build(self.root))

    def test_check_names_stale_files_and_writes_nothing(self):
        stale, _ = bc.stale(self.root)
        self.assertEqual(stale, ["assets/catalog.json", "assets/suite-apps.txt"])
        self.assertEqual(list((self.root / "assets").iterdir()), [])
        bc.write(self.root)
        self.assertEqual(bc.stale(self.root)[0], [])

    def test_unknown_id_in_a_collection(self):
        self.write_collections(dict(COLLECTIONS, extras=["nope"]))
        with self.assertRaisesRegex(bc.BuildError, r"collections/extras.toml: 'nope' has no apps/nope.toml"):
            bc.build(self.root)

    def test_app_in_two_collections(self):
        self.write_collections(dict(COLLECTIONS, extras=["htop"]))
        with self.assertRaisesRegex(bc.BuildError, r"htop: in collections 'desktop' and 'extras'"):
            bc.build(self.root)

    def test_member_nothing_installs(self):
        af.write_app({"id": "ghost", "name": "ghost", "store": False}, self.root / "apps")
        self.write_collections(dict(COLLECTIONS, extras=["ghost"]))
        with self.assertRaisesRegex(bc.BuildError, "apps/ghost.toml: in a collection with no check"):
            bc.build(self.root)

    def test_wrong_includes(self):
        p = self.root / "collections" / "extras.toml"
        p.write_text(p.read_text().replace('includes = "recommended"', 'includes = "desktop"'))
        with self.assertRaisesRegex(af.FileError, "collections/extras.toml: includes must be 'recommended'"):
            bc.build(self.root)


if __name__ == "__main__":
    unittest.main()
