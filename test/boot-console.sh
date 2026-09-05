#!/bin/bash

console_is_luks_prompt() {
  grep -qiE 'passphrase|access the root volume|unlock.*(disk|crypt|luks)' <<<"$1"
}

enter_luks_password() {
  local prefix="$1" timeout="${2:-300}" deadline=$((SECONDS + ${2:-300}))
  log "Waiting for the encrypted disk password prompt"

  until console_is_luks_prompt "$(ocr_screen)"; do
    if ! vm_running || ((SECONDS >= deadline)); then
      capture_console "failure-$prefix-luks-prompt"
      echo "Timed out after ${timeout}s waiting for the encrypted disk prompt" >&2
      return 1
    fi
    # Reveal Plymouth's text prompt when its graphical prompt is unreadable.
    press escape
    sleep 5
  done

  capture_console "success-$prefix-01-luks-prompt"
  press ctrl-u
  type_text "$GUEST_LOGIN_PASSWORD"
  capture_console "success-$prefix-02-luks-passphrase"
  press ret
}
