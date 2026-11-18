# tetron-appstore

A store for terminal apps: browse, search, install and launch 1,300+ TUIs and command line tools from one catalog, in any terminal. Inside tetron-wm (https://github.com/tetronos/tetron-wm) it opens installs and apps in tetron-wm windows; on its own it runs them in place.

Status: early. It works on its own and inside tetron-wm, where it opens installs and apps in tetron-wm windows, follows the tetron-wm theme and shares its catalog. tetron-wm still has its own built-in Store; it will open this app instead, and the catalog sources will move here.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/tetronos/tetron-appstore/main/install.sh | sh
```

That puts the prebuilt binary for your system in `~/.local/bin`, checked against its SHA256. Debian and Ubuntu can install the `.deb` from the latest release (https://github.com/tetronos/tetron-appstore/releases/latest) instead. With Rust: `cargo install --git https://github.com/tetronos/tetron-appstore`.

## Use

Type to search; `from:trove`, `from:awesome` or `from:tetron` shows one list. Arrows move, Left/Right change category, Enter installs or launches, Alt+O or a right click opens the app menu (open or copy the project and releases links), F5 updates the catalog (it also updates on its own once a day; a bad download never replaces the copy in use), Esc quits. `tetron-appstore --help` lists it all.

## Catalog

The catalog merges imported lists (awesome-tuis https://github.com/rothgar/awesome-tuis, Terminal Trove https://terminaltrove.com), our own list of corrections and additions, and a user list on your machine that updates never overwrite. Later sources win: awesome-tuis, then Terminal Trove, then ours, then yours.

## Maintaining the catalog

Every app is one file, `apps/<id>.toml` (format: `schema/app.schema.json`), imported apps included. Each collection is one list of app ids, `collections/<name>.toml` (`desktop`, `essentials`, `recommended`, `extras`; format: `schema/collection.schema.json`). Adding an app is one new file; adding it to a collection is one line. An app that is in a collection but is not a Store app (a library or service package) has `store = false`.

`scripts/build_catalog.py` builds `assets/catalog.json` (compiled in, and published for Update list) and `assets/suite-apps.txt` (tetron-wm's suite installer list) from those files and:

- `sources/repology.json` (`scripts/match_repology.py`: distribution package names; an app file's `[install.pkg]` wins name by name);
- `sources/releases.json` (`scripts/match_releases.py`: GitHub releases with binaries).

`sources/awesome-tuis.json` (`scripts/import_awesome_tuis.py`) and `sources/terminaltrove.json` (`scripts/import_terminaltrove.py`, from https://carcaradotdev.github.io/terminaltrove-stars/data.json) are the imported lists, never edited by hand; `scripts/new_apps_report.py` lists their apps that have no app file yet, apart from `sources/excluded.toml`. Install recipes come from `scripts/match_brew.py` and `scripts/match_lang_recipes.py`, written into the app files.

A weekly workflow (`.github/workflows/install-tests.yml`) installs every collection member and a rotating sample of other Store apps in Debian 13 and Ubuntu 24.04 containers through tetron-wm's suite installer (`scripts/install_test.py`), and checks upstream health (`scripts/upstream_health.py`: archived, no release for 18 months, gone). `status/<id>.json` changes only when a result flips (`scripts/update_status.py`), by a pull request a maintainer merges; the catalog carries each app's `status`. A failing or flagged collection member opens an issue. A pull request that adds a collection member or changes an app file must install it on both.

A tag `catalog-YYYY.MM.DD.N` on main publishes the catalog (`.github/workflows/catalog-release.yml`): `catalog.json` with its `version` and `suite-apps.txt` on the GitHub release and GitHub Pages, `tetron-catalog-data` (`/usr/share/tetron/catalog.json`, for machines without network and the ISO), and the collection metapackages when their Depends or Recommends differ from the newest published ones, at the next patch version (`scripts/metapackage_plan.py`; `packaging/VERSION` is only the floor, so changing a collection is one line in `collections/` and nobody raises a version by hand).

CI checks that the generated files are current (`python3 scripts/build_catalog.py --check`). `python3 reconcile.py` runs the spec's constraints (`spec/`, libspec). A weekly workflow opens an issue when either imported list has new apps. The library in `crates/tetron-catalog` is shared with tetron-wm, which uses it from this repository.

## License

MIT, see LICENSE.
