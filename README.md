# tetron-appstore

A store for terminal apps: browse, search, install and launch 1,300+ TUIs and command line tools from one catalog, in any terminal. Inside tetron-wm (https://github.com/tetronos/tetron-wm) it opens installs and apps in tetron-wm windows; on its own it runs them in place.

Status: not started. The Store is being moved out of tetron-wm in three steps: a shared catalog library inside tetron-wm, then this standalone app running alongside tetron-wm's built-in Store, then the switch (tetron-wm runs this app, its built-in Store is removed) and the catalog sources move here.

## Catalog

The catalog merges imported lists (awesome-tuis https://github.com/rothgar/awesome-tuis, Terminal Trove https://terminaltrove.com), our own list of corrections and additions, and a user list on your machine that updates never overwrite. Later sources win: awesome-tuis, then Terminal Trove, then ours, then yours.

## License

MIT, see LICENSE.
