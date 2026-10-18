#!/bin/bash
set -e
cd "$(dirname "$0")"
rm -rf __pycache__ src/__pycache__ scripts/__pycache__ 2>/dev/null || true
python3 main.py "$@"