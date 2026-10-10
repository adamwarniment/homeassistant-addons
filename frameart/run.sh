#!/usr/bin/with-contenv bashio
# with-contenv exposes SUPERVISOR_TOKEN to the Python process
bashio::log.info "Starting Frame Art $(bashio::addon.version)"
mkdir -p /media/frame
cd /app
exec python3 -m frameart
