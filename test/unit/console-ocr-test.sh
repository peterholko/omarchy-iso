#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source "$ROOT/test/console-ocr.sh"
work=$(mktemp -d)
# Resolve /tmp's symlink on macOS; Leptonica requires the physical path.
work=$(cd "$work" && pwd -P)
trap 'rm -rf "$work"' EXIT

text=$(console_ocr "$ROOT/test/unit/fixtures/installer-greeter.png" "$work/screen.png")
for expected in "Beautiful, Fun" "Press Return to Start Install"; do
  if ! grep -qF "$expected" <<<"$text"; then
    printf 'not ok - welcome screen contains %s\n%s\n' "$expected" "$text" >&2
    exit 1
  fi
done
printf 'ok - OCR reads both the welcome tagline and dim action prompt\n'
