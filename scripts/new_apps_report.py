#!/usr/bin/env python3
"""Write a Markdown report of the apps on the imported lists
(sources/awesome-tuis.json, sources/terminaltrove.json, refreshed by the
importers) that have no app file yet, matched by name or command in any case
or by a GitHub repository homepage, and leaving out sources/excluded.toml.

Usage: python3 scripts/new_apps_report.py <out.md>
Prints the number of new apps to stdout. Used by the catalog-check GitHub Action
to decide whether to open/update an alert issue.
"""
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles as af  # noqa: E402

LISTS = {"awesome-tuis": "awesome-tuis", "terminaltrove": "Terminal Trove"}


def new_apps(root=af.ROOT):
    apps = af.load_apps(root / "apps").values()
    known = {a["name"].lower() for a in apps} | {a["bin"] for a in apps if "bin" in a}
    ids = {x for a in apps for x in (a["id"], *a.get("aliases", []))}
    repos = {af.gh_repo(a.get("homepage")) for a in apps} - {None}
    ex = root / "sources" / "excluded.toml"
    known |= {n.lower() for n in tomllib.loads(ex.read_text(encoding="utf-8"))["exclude"]} if ex.exists() else set()
    out, seen = [], set()
    for src in LISTS:
        p = root / "sources" / f"{src}.json"
        for a in json.loads(p.read_text(encoding="utf-8")) if p.exists() else []:
            if a["name"].lower() in known or a.get("bin") in known or a["name"].lower() in seen \
                    or af.slug(a["name"]) in ids or af.gh_repo(a.get("homepage")) in repos:
                continue
            seen.add(a["name"].lower())
            out.append(dict(a, source=src))
    return out


def main() -> int:
    found = new_apps()
    lines = [
        f"The scheduled check found **{len(found)} new app(s)** in "
        "[awesome-tuis](https://github.com/rothgar/awesome-tuis) and "
        "[Terminal Trove](https://terminaltrove.com) "
        "that have no app file yet:\n",
    ]
    for a in found:
        lines.append(f"- [{a['name']}]({a['homepage']}) _{a['category']}_ ({LISTS[a['source']]})")
    lines.append(
        "\n---\nTo add one, write apps/<id>.toml (schema/app.schema.json) and run "
        "`python3 scripts/build_catalog.py`; to never propose one, add its name to "
        "sources/excluded.toml."
    )
    Path(sys.argv[1]).write_text("\n".join(lines) + "\n")
    print(len(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
