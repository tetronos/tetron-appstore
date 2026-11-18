#!/usr/bin/env python3
"""One-time migration (ASCAT-028): write apps/, collections/ and sources/
from the merged catalog (lists/, scripts/merge_catalog.py) and tetron-wm's
app sets (its lists/tetron.toml "App sets" section).

    python3 scripts/explode_catalog.py WM_LISTS_TOML

Every merged app becomes apps/<id>.toml; every app set member that is not a
catalog app becomes one with store = false. A member is the catalog app
whose command matches it the way the old merge gave apps their set (a
check alternative or a package name equal to the app's command). Package
names keep only what differs from sources/repology.json, except a member's,
which keeps all four (they were checked in containers for its suite line).
Prints the id collisions it resolved and the members it could not link.
"""
import json
import shutil
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402
import merge_catalog as mc  # noqa: E402

ROOT = af.ROOT
DESCRIPTIONS = {
    "desktop": "The tools tetron-wm's own features call",
    "essentials": "The apps a working terminal machine should have, one good pick per need",
    "recommended": "More good terminal apps for daily work",
    "extras": "Further apps for special needs",
}


def explode(wm):
    merged = mc.merged_apps()
    repology = json.loads((mc.LISTS / "repology.json").read_text(encoding="utf-8"))["names"]
    log = []

    # ids: the slug of the name; a second app with the same slug adds its command.
    apps, by_name, by_bin = {}, {}, {}
    for a in sorted(merged, key=lambda a: a["name"].lower()):
        i = af.slug(a["name"])
        if i in apps:
            j = f"{i}-{af.slug(a['bin'])}"
            n = 2
            while j in apps:
                j, n = f"{i}-{n}", n + 1
            log.append(f"id {i!r} taken: {a['name']!r} ({a['bin']}) is {j!r}")
            i = j
        app = {"id": i, "name": a["name"], "bin": a["bin"]}
        for k in ("category", "description", "homepage"):
            app[k] = a[k]
        for k in ("cli", "needs_url"):
            if a.get(k):
                app[k] = True
        if "variants" in a:
            app["variants"] = a["variants"]
        if "agent" in a:
            app["agent"] = a["agent"]
        inst = {}
        found = repology.get(a["name"], {})
        pkg = {m: a.get("pkg", {}).get(m, "") for m in af.MANAGERS if a.get("pkg", {}).get(m, "") != found.get(m, "")}
        if pkg:
            inst["pkg"] = pkg
        if "recipe" in a:
            r = dict(a["recipe"])
            if "requires_cwd" in r:
                app["requires_cwd"] = r.pop("requires_cwd")
            if "tip" in r:
                app["notes"] = {"tip": r.pop("tip")}
            inst["recipe"] = r
        if inst:
            app["install"] = inst
        app["source"] = {"lists": list(dict.fromkeys(a["sources"]))}
        if "tier" in a:
            log.append(f"tier {a['tier']!r} of {a['name']!r} now follows its collection")
        apps[i] = app
        by_name[a["name"].lower()] = app
        by_bin.setdefault(a["bin"], []).append(app)

    def link(names, what):
        hits = list({id(x): x for n in names for alt in n.split("|") if alt for x in by_bin.get(alt, [])}.values())
        if len(hits) > 1:
            log.append(f"{what}: matches {[h['name'] for h in hits]}; linked to the first")
        return hits[0] if hits else None

    def new_member(name, **fields):
        i = af.slug(name)
        if i in apps:
            i = f"{i}-pkg"
            log.append(f"member {name!r}: id taken, is {i!r}")
        apps[i] = dict({"id": i, "name": name, "store": False}, **fields)
        return apps[i]

    members = {s: [] for s in af.COLLECTION_NAMES}

    def add(coll, app):
        for c in members.values():
            if app["id"] in c:
                raise SystemExit(f"{app['id']} is in two sets")
        members[coll].append(app["id"])

    by_member = {}
    for p in wm.get("package", []):
        names = {m: p.get(m, p["name"]) for m in af.MANAGERS}
        check = p.get("check", "")
        app = link([check] + list(names.values()), f"package {p['name']}") if check else None
        if app is None:
            app = new_member(p["name"])
            log.append(f"package {p['name']!r}: not a Store app, apps/{app['id']}.toml (store = false)")
        if check and check != app.get("bin"):
            app["check"] = check
        if p.get("group", "apps") != "apps":
            app["group"] = p["group"]
        inst = app.setdefault("install", {})
        inst["pkg"] = names
        deb = p.get("deb", names["apt"])
        if deb != names["apt"]:
            inst["deb"] = deb
        add(p["set"], app)
        by_member[p["name"].lower()] = app
    for a in sorted((a for a in wm.get("app", [])), key=lambda a: a["name"].lower()):
        app = by_name.get(a["name"].lower())
        if app is None:
            raise SystemExit(f"app {a['name']}: not in the catalog")
        add(a["set"], app)
        by_member[a["name"].lower()] = app
    for s in wm.get("script", []):
        app = link([s["name"]], f"script {s['name']}")
        if app is None:
            app = new_member(s["name"])
            log.append(f"script {s['name']!r}: not a Store app, apps/{app['id']}.toml (store = false)")
        app.setdefault("install", {})["script"] = s["name"]
        app.setdefault("notes", {})["how"] = s["how"]
        add(s["set"], app)
        by_member[s["name"].lower()] = app
    for r in wm.get("release", []):
        app = by_member[r["name"].lower()]
        app.setdefault("install", {})["release"] = {k: r[k] for k in ("repo", "amd64", "arm64") if k in r}
    return apps, members, log


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    wm = tomllib.loads(Path(argv[0]).read_text(encoding="utf-8"))
    apps, members, log = explode(wm)
    for d in ("apps", "collections", "sources"):
        (ROOT / d).mkdir(exist_ok=True)
    for app in apps.values():
        af.write_app(app)
    for i, name in enumerate(af.COLLECTION_NAMES):
        c = {"name": name, "description": DESCRIPTIONS[name], "apps": members[name]}
        if i:
            c["includes"] = af.COLLECTION_NAMES[i - 1]
        (ROOT / "collections" / f"{name}.toml").write_text(af.dump_collection(c), encoding="utf-8")
    for f in ("awesome-tuis.json", "terminaltrove.json", "repology.json", "releases.json"):
        shutil.copyfile(mc.LISTS / f, ROOT / "sources" / f)
    print("\n".join(log))
    print(f"wrote {len(apps)} app files, {sum(map(len, members.values()))} collection members")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
