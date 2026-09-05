#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source "$ROOT/test/console-ocr.sh"
source "$ROOT/test/boot-console.sh"
work=$(mktemp -d)
work=$(cd "$work" && pwd -P)
trap 'rm -rf "$work"' EXIT

text=$(console_ocr "$ROOT/test/unit/fixtures/disk-password.png" "$work/screen.png")
console_is_luks_prompt "$text"
if console_is_luks_prompt ""; then
  echo 'not ok - a blank screen is not a disk password prompt' >&2
  exit 1
fi

printf '0\n' >"$work/frame"
GUEST_LOGIN_PASSWORD=fixture-parent
log() { :; }
capture_console() { :; }
vm_running() { return 0; }
sleep() { SECONDS=$((SECONDS + $1)); }
press() { printf 'key %s\n' "$1" >>"$work/events"; }
type_text() {
  (( $(<"$work/frame") >= 3 )) || return 1
  printf 'type %s\n' "$1" >>"$work/events"
}
ocr_screen() {
  local frame=$(<"$work/frame")
  printf '%s\n' "$((frame + 1))" >"$work/frame"
  if ((frame >= 2)); then
    printf 'A password is required to access the root volume:\n'
  fi
}
enter_luks_password fixture 30
[[ $(grep -c '^type ' "$work/events") == "1" ]]
grep -q '^key ctrl-u$' "$work/events"
grep -q '^key ret$' "$work/events"
printf 'ok - disk password waits through blank boot screens for the real prompt\n'

: >"$work/events"
ocr_screen() { :; }
if enter_luks_password fixture-timeout 10 2>"$work/error"; then
  echo 'not ok - a missing disk prompt must time out' >&2
  exit 1
fi
if grep -q '^type ' "$work/events"; then
  echo 'not ok - no password is typed without a disk prompt' >&2
  exit 1
fi
printf 'ok - a missing prompt times out without typing a password\n'
