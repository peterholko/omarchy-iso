#!/bin/bash

console_ocr() {
  local shot="$1" prepped="$2"

  # Keep the ordinary pass for antialiased text and highlighted form fields.
  magick "$shot" -colorspace gray -negate -resize 150% "$prepped" 2>/dev/null || return 0
  tesseract "$prepped" - --psm 6 2>/dev/null || true

  # The console's dim ANSI text is discarded by Tesseract's automatic
  # threshold. A second pass recovers hints such as the welcome action.
  magick "$shot" -colorspace gray -threshold 20% -negate -resize 200% "$prepped" 2>/dev/null || return 0
  tesseract "$prepped" - --psm 6 2>/dev/null || true
}
