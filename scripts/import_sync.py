#!/usr/bin/env python3
"""Bring the app files in line with the imported lists (ASCAT-018, ASCAT-019).

    python3 scripts/import_sync.py REPORT.md

Run after import_awesome_tuis.py and import_terminaltrove.py refreshed
sources/. Writes a new app file for each listed app that has none (as
new_apps_report.py finds them, leaving out sources/excluded.toml and any
whose command another app already installs), and changes only the [source]
table of existing ones: `lists` names the imported lists that carry the app
now (`tetron` is kept), and `gone = true` marks an app that left every
imported list it was on; it is kept, never deleted, and loses the mark when
a list carries it again. Then builds the catalog. Writes the pull request
body to REPORT.md and prints how many files changed. Stdlib only.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import check_catalog as cc  # noqa: E402
from new_apps_report import LISTS, new_apps  # noqa: E402


def listed(root=af.ROOT):
    """{list: entries} of the imported lists."""
    out = {}
    for src in LISTS:
        p = root / "sources" / f"{src}.json"
        out[src] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    return out


def carriers(app, lists):
    """The imported lists that carry app. A list is added by the same GitHub
    repository or an entry whose name is the app's id or an alias; a list the
    app is already on is kept also by the same name in any case (different
    apps can share a name: amp the editor is not Amp)."""
    name, repo = app["name"].lower(), af.gh_repo(app.get("homepage"))
    ids = {app["id"], *app.get("aliases", [])}
    had = set(app.get("source", {}).get("lists", []))

    def carries(src, e):
        return (repo and af.gh_repo(e.get("homepage")) == repo) or af.slug(e["name"]) in ids \
            or (src in had and e["name"].lower() == name)
    return [src for src, entries in lists.items() if any(carries(src, e) for e in entries)]


def source_now(app, lists):
    """The [source] table app should have now, or None for none."""
    old = dict(app.get("source", {}))
    on = carriers(app, lists)
    had = [x for x in old.get("lists", []) if x in LISTS]
    new = {k: v for k, v in old.items() if k not in ("lists", "gone")}
    keep = [x for x in old.get("lists", []) if x not in LISTS]
    new["lists"] = sorted(set(on) | set(keep))
    if not on and (had or old.get("gone")):
        new["gone"] = True
    if not new["lists"]:
        del new["lists"]
    return new or None


def new_file(entry, taken, cmds):
    """The app file for a new list entry, or (None, reason)."""
    i = af.slug(entry["name"])
    if i in taken:
        return None, f"id {i!r} is taken"
    b = entry.get("bin") or i
    if b in cmds:
        return None, f"command {b!r} is already installed by another app"
    app = {"id": i, "name": entry["name"], "bin": b, "category": entry.get("category") or "Miscellaneous",
           "description": (entry.get("description") or "").strip() or entry["name"], "homepage": entry["homepage"]}
    if entry.get("cli"):
        app["cli"] = True
    return app, None


def sync(root=af.ROOT):
    """(added ids, skipped [(name, reason)], gone ids, back ids, relisted ids); writes the files."""
    apps_dir = root / "apps"
    apps = af.load_apps(apps_dir)
    lists = listed(root)
    taken = set(apps) | {x for a in apps.values() for x in a.get("aliases", [])}
    cmds = {c for a in apps.values() for c in cc.commands(a)}
    added, skipped = [], []
    for e in new_apps(root):
        app, why = new_file(e, taken, cmds)
        if not app:
            skipped.append((e["name"], why))
            continue
        apps[app["id"]] = app
        taken.add(app["id"]), cmds.add(app["bin"])
        added.append(app["id"])
    gone, back, relisted = [], [], []
    for i, app in sorted(apps.items()):
        before = app.get("source")
        now = source_now(app, lists)
        if now == before and i not in added:
            continue
        if now:
            app["source"] = now
        else:
            app.pop("source", None)
        if i not in added:
            (gone if (now or {}).get("gone") and not (before or {}).get("gone") else
             back if (before or {}).get("gone") and not (now or {}).get("gone") else relisted).append(i)
        af.write_app(app, apps_dir)
    return added, skipped, gone, back, relisted


def report(added, skipped, gone, back, relisted):
    out = ["The weekly import of [awesome-tuis](https://github.com/rothgar/awesome-tuis) and "
           "[Terminal Trove](https://terminaltrove.com) (ASCAT-018). Only new app files and `[source]` "
           "tables change; no app file is deleted.\n"]
    for title, ids in (("New app files", added), ("Left every imported list (`gone = true`, kept)", gone),
                       ("Back on a list", back), ("On other lists now", relisted)):
        if ids:
            out += [f"### {title} ({len(ids)})", *[f"- `apps/{i}.toml`" for i in ids], ""]
    if skipped:
        out += [f"### Not added ({len(skipped)})", *[f"- {n}: {why}" for n, why in skipped], ""]
    out.append("Before merging: check the new apps' category, command and description; a name in "
               "`sources/excluded.toml` is never proposed again.")
    return "\n".join(out) + "\n"


def main(argv):
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    r = sync()
    import build_catalog
    build_catalog.write()
    Path(argv[0]).write_text(report(*r), encoding="utf-8")
    print(len(r[0]) + len(r[2]) + len(r[3]) + len(r[4]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
