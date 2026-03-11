#!/usr/bin/env bash
# Render build script for the backend / worker services.
# This runs during every deploy on Render's native Python runtime.

set -e

echo "=== Installing system dependencies ==="
# Render allows apt installs during build
apt-get update -qq && apt-get install -y -qq ffmpeg fonts-noto fontconfig || true
fc-cache -f 2>/dev/null || true

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Verifying bundled font ==="
python -c "
from PIL import ImageFont
import os
font_path = os.path.join(os.path.dirname(__file__) if '__file__' in dir() else '.', 'fonts', 'NotoSansDevanagari.ttf')
if not os.path.exists(font_path):
    font_path = 'fonts/NotoSansDevanagari.ttf'
if os.path.exists(font_path):
    f = ImageFont.truetype(font_path, 42)
    print(f'Font OK: {font_path} ({os.path.getsize(font_path)} bytes)')
else:
    print('WARNING: Bundled font not found at fonts/NotoSansDevanagari.ttf')
"

echo "=== Build complete ==="
