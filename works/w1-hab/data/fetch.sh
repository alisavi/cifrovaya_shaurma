#!/usr/bin/env bash
# Скачивание исходных данных в data/raw и печать sha256 для PASSPORT.md.
# Usage: ./fetch.sh <url> [filename]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

URL="${1:?usage: fetch.sh <url> [filename]}"
DEFAULT_NAME="$(basename "${URL%%\?*}")"
NAME="${2:-$DEFAULT_NAME}"
DEST="$RAW/$NAME"

curl -fL --retry 3 --retry-delay 2 -o "$DEST" "$URL"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$DEST"
else
  shasum -a 256 "$DEST"
fi
