#!/bin/sh
# Install tetron-appstore from its latest GitHub release:
#   curl -fsSL https://raw.githubusercontent.com/tetronos/tetron-appstore/main/install.sh | sh
#
# Downloads the binary for this OS and CPU (Linux or macOS, x86_64 or
# aarch64), checks it against the release's SHA256 file and puts it in
# ~/.local/bin (no sudo). On Debian and Ubuntu the release also has a .deb.
#   TETRON_APPSTORE_VERSION=v0.15.0  a given release instead of the latest
#   TETRON_APPSTORE_BIN_DIR=DIR      install there instead of ~/.local/bin
set -eu

REPO=tetronos/tetron-appstore
BIN_DIR="${TETRON_APPSTORE_BIN_DIR:-$HOME/.local/bin}"

die() { echo "tetron-appstore: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

have curl || die "curl is needed"
have tar || die "tar is needed"

case "$(uname -s)" in
  Linux) os=unknown-linux-gnu ;;
  Darwin) os=apple-darwin ;;
  *) die "no prebuilt binary for $(uname -s); install with: cargo install --git https://github.com/$REPO" ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) cpu=x86_64 ;;
  aarch64 | arm64) cpu=aarch64 ;;
  *) die "no prebuilt binary for $(uname -m); install with: cargo install --git https://github.com/$REPO" ;;
esac
target="$cpu-$os"

# The latest tag from the releases/latest web redirect (not the rate-limited API).
tag="${TETRON_APPSTORE_VERSION:-}"
if [ -z "$tag" ]; then
  tag="$(curl -fsSI "https://github.com/$REPO/releases/latest" | tr -d '\r' \
    | awk 'tolower($1)=="location:"{print $2}' | tail -1 | sed 's|.*/releases/tag/||')"
fi
case "$tag" in v*) ;; *) die "could not find the latest release (got '$tag')" ;; esac

file="tetron-appstore-$target.tar.gz"
url="https://github.com/$REPO/releases/download/$tag/$file"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "tetron-appstore: downloading $tag for $target"
curl -fsSL "$url" -o "$tmp/$file" || die "download failed: $url"
curl -fsSL "$url.sha256" -o "$tmp/$file.sha256" || die "download failed: $url.sha256"
want="$(cut -d' ' -f1 "$tmp/$file.sha256")"
if have sha256sum; then got="$(sha256sum "$tmp/$file" | cut -d' ' -f1)"; else got="$(shasum -a 256 "$tmp/$file" | cut -d' ' -f1)"; fi
if [ -z "$want" ] || [ "$want" != "$got" ]; then die "checksum mismatch for $file; nothing installed"; fi

tar -xzf "$tmp/$file" -C "$tmp" tetron-appstore
mkdir -p "$BIN_DIR"
install -m 755 "$tmp/tetron-appstore" "$BIN_DIR/tetron-appstore"
echo "tetron-appstore: installed $BIN_DIR/tetron-appstore ($("$BIN_DIR/tetron-appstore" --version))"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "tetron-appstore: $BIN_DIR is not on your PATH; add it, or run $BIN_DIR/tetron-appstore" ;;
esac
