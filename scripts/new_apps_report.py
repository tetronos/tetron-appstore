#!/usr/bin/env python3
"""Compare the freshly regenerated assets/catalog.json against the committed one
and write a Markdown report of apps that are new in the imported lists
(awesome-tuis, Terminal Trove).

Usage: python3 scripts/new_apps_report.py <out.md>
Prints the number of new apps to stdout. Used by the catalog-check GitHub Action
to decide whether to open/update an alert issue.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    committed = subprocess.run(
        ["git", "show", "HEAD:assets/catalog.json"],
        capture_output=True, text=True, cwd=ROOT,
    )
    apps = lambda doc: doc["apps"] if isinstance(doc, dict) else doc  # older catalogs were a bare list
    old_names = {a["name"] for a in apps(json.loads(committed.stdout))} if committed.returncode == 0 else set()

    new_catalog = apps(json.loads((ROOT / "assets" / "catalog.json").read_text()))
    new_apps = [a for a in new_catalog if a["name"] not in old_names]

    lines = [
        f"The scheduled check found **{len(new_apps)} new app(s)** in "
        "[awesome-tuis](https://github.com/rothgar/awesome-tuis) and "
        "[Terminal Trove](https://terminaltrove.com) "
        "that are not yet in the catalog:\n",
    ]
    for a in new_apps:
        lines.append(f"- [{a['name']}]({a['homepage']}) — _{a['category']}_ ({', '.join(a.get('sources', []))})")
    lines.append(
        "\n---\nTo add them, run locally and commit:\n"
        "```\n"
        "curl -fsSL https://raw.githubusercontent.com/rothgar/awesome-tuis/master/README.md -o /tmp/awesome-tuis.md\n"
        "python3 scripts/import_awesome_tuis.py /tmp/awesome-tuis.md\n"
        "curl -fsSL https://carcaradotdev.github.io/terminaltrove-stars/data.json -o /tmp/terminaltrove.json\n"
        "python3 scripts/import_terminaltrove.py /tmp/terminaltrove.json\n"
        "python3 scripts/merge_catalog.py\n"
        "python3 scripts/match_repology.py && python3 scripts/match_brew.py\n"
        "python3 scripts/match_lang_recipes.py && python3 scripts/match_releases.py\n"
        "# then derive install recipes for the rest, run scripts/derive_os.py, and commit;\n"
        "# our fixes for an imported app go in lists/tetron.toml, never in the imported lists\n"
        "```"
    )

    Path(sys.argv[1]).write_text("\n".join(lines))
    print(len(new_apps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
