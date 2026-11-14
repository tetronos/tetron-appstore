# Changelog

All notable changes to tetron-appstore. The version follows the tetron core minor (0.15.x).

## [Unreleased]

## [0.15.0]

### Added
- The Store as its own program, moved out of tetron-wm: categories, search, the app list with installed marks and CLI tags, and the details of the selected app.
- Install with the system's package manager first, else the app's upstream way (cargo, go, pipx, Homebrew), offering a missing toolchain first. Installed apps launch from the Store.
- App menu (Alt+O or a right click): Install or Launch, open or copy the project link and the prebuilt binaries (GitHub releases) link. A click on a link in the details offers Open and Copy for it.
- "Listed by" names the lists an app comes from (awesome-tuis, Terminal Trove, tetron); `from:NAME` in the search shows one list.
- Update list (F5) downloads the newest catalog into the file tetron-wm reads too.
- Inside tetron-wm, installs, apps and links open in tetron-wm windows, AI coding agents ask for a working folder first, and the colours follow the tetron-wm theme as it changes.
- Release binaries for Linux and macOS (x86_64, aarch64), a .deb for Debian and Ubuntu, and install.sh.
