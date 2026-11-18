# Changelog

All notable changes to tetron-appstore. The version follows the tetron core minor (0.15.x).

## [Unreleased]

### Changed
- One file per app and one list per collection: every catalog app is `apps/<id>.toml` (1390 Store apps, plus 82 collection members that are not Store apps, `store = false`), and the collections `desktop`, `essentials`, `recommended` and `extras` are `collections/<name>.toml`, moved here from tetron-wm's app sets. `scripts/build_catalog.py` builds `assets/catalog.json` and `assets/suite-apps.txt` from them; the catalog gains `id`, `collection` and a `collections` list, and keeps its format otherwise. `lists/tetron.toml`, `scripts/merge_catalog.py` and `scripts/sync_suite_list.sh` are gone; the imported lists are in `sources/`. A test proves the built catalog equals the merged one, apart from these named changes: a collection member's package names are the ones its suite line used (bat, delta, fd, mtr, pandoc, curl, tcpdump, AI Mode, tetron-browser) and `tier` follows the collection (AI Mode recommended, torrentTUI optional). The recipe tools write into the app files. Spec in `spec/` (libspec), gates in `reconcile.py`.
- The catalog lives here now, moved from tetron-wm: the `tetron-catalog` library (`crates/tetron-catalog`, which tetron-wm uses from this repository), the built-in `assets/catalog.json`, the imported lists, our corrections (`lists/tetron.toml`) and the import, merge and recipe scripts. The published catalog keeps its format, so installed versions see no change. The weekly check covers Terminal Trove too.

## [0.15.0]

### Added
- The Store as its own program, moved out of tetron-wm: categories, search, the app list with installed marks and CLI tags, and the details of the selected app.
- Install with the system's package manager first, else the app's upstream way (cargo, go, pipx, Homebrew), offering a missing toolchain first. Installed apps launch from the Store.
- App menu (Alt+O or a right click): Install or Launch, open or copy the project link and the prebuilt binaries (GitHub releases) link. A click on a link in the details offers Open and Copy for it.
- "Listed by" names the lists an app comes from (awesome-tuis, Terminal Trove, tetron); `from:NAME` in the search shows one list.
- Update list (F5) downloads the newest catalog into the file tetron-wm reads too.
- Inside tetron-wm, installs, apps and links open in tetron-wm windows, AI coding agents ask for a working folder first, and the colours follow the tetron-wm theme as it changes.
- Release binaries for Linux and macOS (x86_64, aarch64), a .deb for Debian and Ubuntu, and install.sh.
