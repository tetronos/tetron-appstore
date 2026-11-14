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

## License

MIT, see LICENSE.
