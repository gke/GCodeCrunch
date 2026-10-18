#!/bin/bash
cd "/home/gke/Documents/Flight/3D Projects" || exit 1

# clear the Python bytecode cache so the latest sources are loaded
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

python3 GCODECrunch.py
