#!/usr/bin/env bash
# Push the working copy to Home Assistant as a *local* add-on and rebuild it.
# Needs the "Advanced SSH & Web Terminal" (or core SSH) add-on with your key, e.g.
#   HA_SSH=root@homeassistant.local dev/deploy-ha.sh
# It appears in HA as "Frame Art (dev)" under Local add-ons, separate from the released one.
set -euo pipefail
cd "$(dirname "$0")/.."
HA_SSH="${HA_SSH:-root@homeassistant.local}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

rsync -a --exclude __pycache__ frameart/ "$STAGE/frameart_dev/"
# distinct slug/name so it can live next to the released add-on
sed -i.bak -e 's/^slug: .*/slug: frameart_dev/' -e 's/^name: .*/name: Frame Art (dev)/' \
  -e 's/^panel_title: .*/panel_title: Frame Art (dev)/' "$STAGE/frameart_dev/config.yaml"
rm "$STAGE/frameart_dev/config.yaml.bak"

rsync -az --delete "$STAGE/frameart_dev/" "$HA_SSH:/addons/frameart_dev/"
ssh "$HA_SSH" 'ha store reload >/dev/null &&
  if ha apps info local_frameart_dev >/dev/null 2>&1 || ha addons info local_frameart_dev >/dev/null 2>&1; then
    (ha apps rebuild local_frameart_dev 2>/dev/null || ha addons rebuild local_frameart_dev) && echo "rebuilt"
  else
    (ha apps install local_frameart_dev 2>/dev/null || ha addons install local_frameart_dev) && echo "installed – start it from Settings → Add-ons"
  fi'
