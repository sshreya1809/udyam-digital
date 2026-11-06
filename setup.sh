#!/bin/sh
# One-time setup: compile the macOS Vision OCR helper (~2 min) and build the React frontend.
set -e
cd "$(dirname "$0")"
[ -x ocr/ocr ] || swiftc -O ocr/ocr.swift -o ocr/ocr
export PATH="$PWD/.tools/node/bin:$PATH"     # project-local Node.js, if present
(cd frontend && npm install && npm run build)
echo "Ready. Start with: python3 server.py   (http://127.0.0.1:8000)"
