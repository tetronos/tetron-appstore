# tetron-appstore

A store for terminal apps: browse, search, install and launch 1,300+ TUIs and command line tools from one catalog, in any terminal. Inside tetron-wm (https://github.com/tetronos/tetron-wm) it opens installs and apps in tetron-wm windows; on its own it runs them in place.

Status: early. It works on its own and inside tetron-wm, where it opens installs and apps in tetron-wm windows, follows the tetron-wm theme and shares its catalog. tetron-wm still has its own built-in Store; it will open this app instead, and the catalog sources will move here.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/tetronos/tetron-appstore/main/install.sh | sh
```

That puts the prebuilt binary for your system in `~/.local/bin`, checked against its SHA256. Debian and Ubuntu can install the `.deb` from the latest release (https://github.com/tetronos/tetron-appstore/releases/latest) instead. With Rust: `cargo install --git https://github.com/tetronos/tetron-appstore`.

## Use

Type to search; `from:trove`, `from:awesome` or `from:tetron` shows one list. Arrows move, Left/Right change category, Enter installs or launches, Alt+O or a right click opens the app menu (open or copy the project and releases links), F5 updates the catalog, Esc quits. `tetron-appstore --help` lists it all.

## Catalog

The catalog merges imported lists (awesome-tuis https://github.com/rothgar/awesome-tuis, Terminal Trove https://terminaltrove.com), our own list of corrections and additions, and a user list on your machine that updates never overwrite. Later sources win: awesome-tuis, then Terminal Trove, then ours, then yours.

## Maintaining the catalog

`assets/catalog.json` (compiled in, and published for Update list) is built by `scripts/merge_catalog.py` from:

- `lists/awesome-tuis.json` (`scripts/import_awesome_tuis.py`, from the awesome-tuis README) and `lists/terminaltrove.json` (`scripts/import_terminaltrove.py`, from https://carcaradotdev.github.io/terminaltrove-stars/data.json), never edited by hand;
- `lists/tetron.toml`, our corrections and additions, which win;
- `lists/repology.json` (`scripts/match_repology.py`: distribution package names), `lists/releases.json` (`scripts/match_releases.py`: GitHub releases with binaries), and install recipes from `scripts/match_brew.py` and `scripts/match_lang_recipes.py`;
- `assets/suite-apps.txt`, tetron-wm's install sizes, copied by `scripts/sync_suite_list.sh`.

CI checks that `catalog.json` is current (`python3 scripts/merge_catalog.py --check`). A weekly workflow opens an issue when either imported list has new apps. The library in `crates/tetron-catalog` is shared with tetron-wm, which uses it from this repository.

## License

MIT, see LICENSE.
