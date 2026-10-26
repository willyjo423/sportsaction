#!/bin/bash
# Rebuild the sharp board and push it. Runs a few minutes after the fade board's scrape.
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null
[ -f .env ] && export $(grep -v '^#' .env | xargs)
mkdir -p data
{
  echo "=== $(date)"
  python build.py
  if ! git diff --quiet -- docs; then
    git add docs && git commit -qm "Board update $(date '+%Y-%m-%d %H:%M')" && git push -q && echo pushed
  fi
} >> data/publish.log 2>&1
