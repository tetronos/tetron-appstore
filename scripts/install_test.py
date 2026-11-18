#!/usr/bin/env python3
"""Install test (ASCAT-015), run inside a fresh Debian 13 or Ubuntu 24.04
container (scripts/install-tests.yml).

    python3 scripts/install_test.py --platform debian-13 --installer SUITE.sh \
        --out results.json [--ids a,b | --changed-since REF] [--sample N --week W] [--strict]

Collection members (all, or --ids) are installed by tetron-wm's suite
installer itself, with a list built from the app files for just them, so the
test takes the code path users get. A rotating sample of N other Store apps
with an apt package (chosen by the ISO week W) is installed with apt-get, the
suite installer's way for a package. Then each app's check runs. Each result
is ok, fail (with the last installer lines that name it) or skipped (this
platform has no way to install it: no apt name, release or script; gui and
service members, which need a desktop session or a booted system; gpm, which
needs a mouse). --changed-since REF tests the members a pull request added to
a collection or whose app file it changed; --strict exits 1 when one fails.
Stdlib only (Python 3.11+).
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import build_catalog as bc  # noqa: E402

ROOT = af.ROOT
INSTALLER_ARGS = ["--yes", "--no-wm", "--no-config", "--no-themes", "--no-services", "--no-kmscon",
                  "--no-console", "--no-autostart", "--no-fullscreen", "--size", "extras"]
TAIL = 8


def present(check, home=None):
    """The suite installer's check (present() and have_tool() there)."""
    home = Path(home or os.path.expanduser("~"))
    if "|" in check:
        return any(present(c, home) for c in check.split("|") if c)
    if check == "consolefonts":
        return any(Path(d).is_dir() and any(Path(d).iterdir()) for d in
                   ("/usr/share/consolefonts", "/usr/lib/kbd/consolefonts"))
    if check.startswith("font="):
        if shutil.which("fc-list"):
            r = subprocess.run(["fc-list", check[5:]], capture_output=True, text=True)
            return bool(r.stdout.strip())
        return any(Path("/usr/share/fonts").rglob("DejaVuSansMono.ttf"))
    return bool(shutil.which(check)) or any(os.access(p, os.X_OK) for p in
                                            (home / ".local/bin" / check, Path("/usr/sbin") / check,
                                             Path("/sbin") / check))


def skip_reason(app, names):
    """Why this platform does not install a member, or None."""
    inst = app.get("install", {})
    if app.get("group") == "gui":
        return "needs a desktop session"
    if app.get("group") == "services":
        return "a system service, offered separately"
    if app.get("check", app.get("bin")) == "gpm":
        return "needs a mouse device"
    if not (names["apt"] or inst.get("release") or inst.get("script")):
        return "no apt package, release or script"
    return None


def sample_ids(apps, members, repology, n, week):
    """n Store apps outside the collections with an apt package, rotating by week."""
    pool = sorted(i for i, a in apps.items() if a.get("store", True) and i not in members
                  and bc.package_names(a, repology)["apt"])
    if not pool or not n:
        return []
    start = (week * n) % len(pool)
    return (pool + pool)[start:start + min(n, len(pool))]


def changed_members(base, where, root=ROOT):
    """Members added to a collection, or with a changed app file, since base."""
    import tomllib

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    out = set()
    for f in git("diff", "--name-only", "--no-renames", f"{base}...HEAD", "--", "apps/", "collections/").split():
        if f.startswith("apps/"):
            out.add(Path(f).stem)
        else:
            try:
                before = set(tomllib.loads(git("show", f"{base}:{f}")).get("apps", []))
            except subprocess.CalledProcessError:
                before = set()
            out |= {i for i, c in where.items() if f"collections/{c}.toml" == f} - before
    return sorted(i for i in out if i in where)


def tail_for(log, words):
    hits = [line for line in log.splitlines() if any(w and w in line for w in words)]
    return hits[-TAIL:]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--platform", required=True)
    p.add_argument("--installer", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ids", default="")
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--week", type=int, default=0)
    p.add_argument("--changed-since", default="")
    p.add_argument("--strict", action="store_true")
    a = p.parse_args(argv)

    apps = af.load_apps()
    collections = af.load_collections()
    repology = json.loads((ROOT / "sources" / "repology.json").read_text(encoding="utf-8"))["names"]
    where = bc.membership(apps, collections)
    if a.changed_since:
        wanted = changed_members(a.changed_since, where)
    else:
        wanted = [i for i in a.ids.split(",") if i] or list(where)
    members = [i for i in wanted if i in where]
    results, log = {}, ""

    names = {i: bc.package_names(apps[i], repology) for i in members}
    todo = [i for i in members if not skip_reason(apps[i], names[i])]
    for i in members:
        why = skip_reason(apps[i], names[i])
        if why:
            results[i] = {"result": "skipped", "method": "suite", "why": why}
    if todo:
        only = [dict(c, apps=[i for i in c["apps"] if i in todo]) for c in collections]
        listfile = Path(a.out).with_suffix(".suite-apps.txt")
        listfile.write_text(bc.suite_lines(apps, only, repology), encoding="utf-8")
        r = run(["bash", a.installer, *INSTALLER_ARGS, "--apps-list", str(listfile)])
        log = r.stdout + r.stderr
        Path(a.out).with_suffix(".log").write_text(log, encoding="utf-8")
    for i in todo:
        app = apps[i]
        check = app.get("check", app.get("bin", ""))
        inst = app.get("install", {})
        method = "script" if inst.get("script") else "suite"
        ok = present(check)
        res = {"result": "ok" if ok else "fail", "method": method}
        if not ok:
            res["tail"] = tail_for(log, [check, names[i]["apt"], inst.get("script", ""), app["name"]])
        results[i] = res

    if a.sample:
        run(["apt-get", "update", "-q"])
        for i in sample_ids(apps, set(where), repology, a.sample, a.week):
            apt = bc.package_names(apps[i], repology)["apt"]
            r = run(["apt-get", "install", "-y", "-q", apt], env=dict(os.environ, DEBIAN_FRONTEND="noninteractive"))
            ok = r.returncode == 0 and present(apps[i]["bin"])
            res = {"result": "ok" if ok else "fail", "method": "apt"}
            if not ok:
                res["tail"] = (r.stdout + r.stderr).splitlines()[-TAIL:] if r.returncode else \
                    [f"apt installed {apt}, but {apps[i]['bin']!r} is not on PATH"]
            results[i] = res

    doc = {"platform": a.platform, "date": datetime.date.today().isoformat(), "results": results}
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    counts = {k: sum(1 for r in results.values() if r["result"] == k) for k in ("ok", "fail", "skipped")}
    print(f"{a.platform}: {counts}")
    for i, r in sorted(results.items()):
        if r["result"] == "fail":
            print(f"FAIL {i}: " + " | ".join(r.get("tail", [])))
    return 1 if a.strict and counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
