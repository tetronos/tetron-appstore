#!/bin/sh
# Copy tetron-wm's suite app list (its app sets, WMINST-001) into
# assets/suite-apps.txt, then merge the catalog again: the merge gives each
# app its set and tier from it, and the catalog carries it as suite_apps.
# tetron-wm owns the list (lists/tetron.toml App sets, scripts/gen_suite_lists.py);
# run this after it changes there. TETRON_WM_RAW overrides the source (a ref or fork).
set -eu
cd "$(dirname "$0")/.."
raw="${TETRON_WM_RAW:-https://raw.githubusercontent.com/tetronos/tetron-wm/main}"
curl -fsSL "$raw/assets/suite-apps.txt" -o assets/suite-apps.txt.part
mv assets/suite-apps.txt.part assets/suite-apps.txt
python3 scripts/merge_catalog.py
git status --short assets/ || true
