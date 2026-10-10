#!/usr/bin/env bash
# Run the add-on on your machine: UI at http://127.0.0.1:8099, uploads go to .dev/data/cache/dry-run
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r frameart/requirements.txt pytest; }
[ -d dev/media ] || .venv/bin/python dev/make_samples.py dev/media
mkdir -p .dev/data
if [ ! -f .dev/data/settings.json ]; then
  printf '{"library": {"folder": "%s"}, "tv": {"dry_run": true}}\n' "$PWD/dev/media" > .dev/data/settings.json
fi
cd frameart
FRAMEART_DATA="$PWD/../.dev/data" exec ../.venv/bin/python -m frameart
