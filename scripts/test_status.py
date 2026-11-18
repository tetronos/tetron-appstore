"""Tests for the install tests and status files (ASCAT-015 to ASCAT-017):
scripts/install_test.py, update_status.py, upstream_health.py and the status
in the catalog.

    python3 -m unittest scripts/test_status.py
"""
import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog as bc  # noqa: E402
import install_test as it  # noqa: E402
import update_status as us  # noqa: E402
import upstream_health as uh  # noqa: E402

NONE = {"apt": "", "dnf": "", "pacman": "", "brew": ""}


class InstallTest(unittest.TestCase):
    def test_present_finds_local_bin_and_alternatives(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / ".local" / "bin"
            b.mkdir(parents=True)
            (b / "zzfake").write_text("#!/bin/sh\n")
            os.chmod(b / "zzfake", 0o755)
            self.assertTrue(it.present("zzfake", d))
            self.assertTrue(it.present("nope-xyz|zzfake", d))
            self.assertFalse(it.present("nope-xyz", d))

    def test_skip_reasons(self):
        self.assertEqual(it.skip_reason({"group": "gui"}, NONE), "needs a desktop session")
        self.assertEqual(it.skip_reason({"group": "services"}, NONE), "a system service, offered separately")
        self.assertEqual(it.skip_reason({"check": "gpm"}, dict(NONE, apt="gpm")), "needs a mouse device")
        self.assertEqual(it.skip_reason({"bin": "blueutil"}, dict(NONE, brew="blueutil")),
                         "no apt package, release or script")
        self.assertIsNone(it.skip_reason({"install": {"script": "fresh"}}, NONE))
        self.assertIsNone(it.skip_reason({"install": {"release": {"repo": "a/b"}}}, NONE))

    def test_no_candidate_on_this_platform(self):
        none, some = (lambda n: False), (lambda n: True)
        apt = dict(NONE, apt="newsboat")
        self.assertEqual(it.no_candidate({}, apt, none), "no apt package on this platform, and no release or script")
        self.assertIsNone(it.no_candidate({}, apt, some))
        self.assertIsNone(it.no_candidate({"install": {"release": {"repo": "a/b"}}}, apt, none))
        self.assertIsNone(it.no_candidate({"install": {"script": "x"}}, apt, none))

    def test_sample_rotates_by_week_over_store_apps_with_apt(self):
        apps = {f"a{n}": {"name": f"a{n}", "install": {"pkg": {"apt": f"a{n}"}}} for n in range(5)}
        apps["hidden"] = {"name": "hidden", "store": False, "install": {"pkg": {"apt": "h"}}}
        apps["noapt"] = {"name": "noapt"}
        apps["member"] = {"name": "member", "install": {"pkg": {"apt": "m"}}}
        self.assertEqual(it.sample_ids(apps, {"member"}, {}, 2, 0), ["a0", "a1"])
        self.assertEqual(it.sample_ids(apps, {"member"}, {}, 2, 2), ["a4", "a0"])
        self.assertEqual(sorted(it.sample_ids(apps, {"member"}, {}, 9, 1)), ["a0", "a1", "a2", "a3", "a4"])

    def test_tail_keeps_the_last_lines_naming_the_app(self):
        log = "\n".join([f"line {n} about zz" for n in range(20)] + ["other"])
        self.assertEqual(it.tail_for(log, ["zz", ""]), [f"line {n} about zz" for n in range(12, 20)])


RUN1 = {"platform": "debian-13", "date": "2026-01-05",
        "results": {"a": {"result": "ok", "method": "suite"}, "b": {"result": "fail", "method": "suite",
                                                                    "tail": ["E: no b"]}}}


class Status(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "status"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, i):
        return json.loads((self.dir / f"{i}.json").read_text())

    def test_first_results_are_written(self):
        self.assertEqual(us.update([RUN1], {}, self.dir), ["a", "b"])
        self.assertEqual(self.read("b")["platforms"]["debian-13"],
                         {"result": "fail", "since": "2026-01-05", "method": "suite", "tail": ["E: no b"]})

    def test_same_result_next_week_changes_nothing(self):
        us.update([RUN1], {}, self.dir)
        again = dict(RUN1, date="2026-01-12")
        self.assertEqual(us.update([again], {}, self.dir), [])
        self.assertEqual(self.read("a")["platforms"]["debian-13"]["since"], "2026-01-05")

    def test_a_flip_is_written_with_its_date(self):
        us.update([RUN1], {}, self.dir)
        flip = dict(RUN1, date="2026-01-12", results={"a": {"result": "fail", "method": "suite"}})
        self.assertEqual(us.update([flip], {}, self.dir), ["a"])
        self.assertEqual(self.read("a")["platforms"]["debian-13"]["since"], "2026-01-12")

    def test_platforms_are_kept_apart(self):
        us.update([RUN1], {}, self.dir)
        ubuntu = dict(RUN1, platform="ubuntu-24.04")
        self.assertEqual(us.update([ubuntu], {}, self.dir), ["a", "b"])
        self.assertEqual(sorted(self.read("a")["platforms"]), ["debian-13", "ubuntu-24.04"])

    def test_health_flags_flip_too(self):
        h = {"date": "2026-01-05", "apps": {"a": {"archived": True}}}
        self.assertEqual(us.update([], h, self.dir), ["a"])
        self.assertEqual(us.update([], dict(h, date="2026-01-12"), self.dir), [])
        self.assertEqual(us.update([], {"date": "2026-01-19", "apps": {"a": {}}}, self.dir), ["a"])
        self.assertNotIn("health", self.read("a"))

    def test_issue_lists_failing_or_flagged_members_only(self):
        h = {"apps": {"c": {"archived": True}, "a": {}}}
        self.assertEqual(us.issue([RUN1], h, {"a": "desktop", "b": "extras", "c": "essentials"}),
                         ["- `b` (extras): fails on debian-13", "- `c` (essentials): archived"])

    def test_catalog_status(self):
        st = {"platforms": {"ubuntu-24.04": {"result": "fail"}, "debian-13": {"result": "ok"}},
              "health": {"archived": True, "since": "2026-01-05"}}
        self.assertEqual(bc.app_status(st), {"debian-13": "ok", "ubuntu-24.04": "fail", "health": ["archived"]})


class Health(unittest.TestCase):
    TODAY = datetime.date(2026, 6, 1)

    def http(self, pages):
        return lambda url, method="GET": pages.get(url, (404, None))

    def test_archived_and_old_release(self):
        api = "https://api.github.com/repos/o/r"
        pages = {api: (200, {"archived": True}), api + "/releases/latest": (200, {"published_at": "2024-01-01T00:00:00Z"})}
        self.assertEqual(uh.flags_for({"homepage": "https://github.com/o/r"}, self.TODAY, self.http(pages)),
                         {"archived": True, "no_release_18_months": True})

    def test_recent_release_and_no_releases_are_healthy(self):
        api = "https://api.github.com/repos/o/r"
        recent = {api: (200, {}), api + "/releases/latest": (200, {"published_at": "2026-05-01T00:00:00Z"})}
        self.assertEqual(uh.flags_for({"homepage": "https://github.com/o/r"}, self.TODAY, self.http(recent)), {})
        self.assertEqual(uh.flags_for({"homepage": "https://github.com/o/r"}, self.TODAY, self.http({api: (200, {})})), {})

    def test_gone(self):
        self.assertEqual(uh.flags_for({"homepage": "https://github.com/o/gone"}, self.TODAY, self.http({})), {"gone": True})
        self.assertEqual(uh.flags_for({"homepage": "https://example.org/x"}, self.TODAY, self.http({})), {"gone": True})

    def test_network_trouble_flags_nothing(self):
        down = lambda url, method="GET": (0, None)
        self.assertEqual(uh.flags_for({"homepage": "https://github.com/o/r"}, self.TODAY, down), {})
        self.assertEqual(uh.flags_for({"homepage": "https://example.org/x"}, self.TODAY, down), {})


if __name__ == "__main__":
    unittest.main()
