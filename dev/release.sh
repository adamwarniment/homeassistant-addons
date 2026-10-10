#!/usr/bin/env bash
# Bump the add-on version, commit, tag and push. Home Assistant sees the new
# version on its next store refresh and rebuilds the add-on locally on update.
#   dev/release.sh 2.0.1
set -euo pipefail
cd "$(dirname "$0")/.."
NEW="${1:?usage: dev/release.sh <version>}"
[ -z "$(git status --porcelain)" ] || { echo "Commit or stash your changes first." >&2; exit 1; }
grep -q "^## $NEW" frameart/CHANGELOG.md || { echo "Add a '## $NEW' section to frameart/CHANGELOG.md first." >&2; exit 1; }
.venv/bin/python -m pytest -q
sed -i.bak "s/^version: .*/version: \"$NEW\"/" frameart/config.yaml && rm frameart/config.yaml.bak
git commit -qam "Release $NEW"
git tag "v$NEW"
git push --follow-tags
echo "Released $NEW. In HA: Settings → Add-ons → Add-on store → ⋮ → Check for updates."
