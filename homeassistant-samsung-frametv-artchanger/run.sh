#!/usr/bin/with-contenv bashio

TVIP=$(bashio::config 'tv')

mkdir -p /media/frame
echo "Using ${TVIP} as the IP's of the Samsung Frame"

PARAMS=""

if bashio::config.true 'google_art'; then
    PARAMS="${PARAMS} --google-art"
fi
if bashio::config.true 'bing_wallpapers'; then
    PARAMS="${PARAMS} --bing-wallpapers"
fi
if bashio::config.true 'media_folder'; then
    PARAMS="${PARAMS} --media-folder"
fi
if bashio::config.true 'download_high_res'; then
    PARAMS="${PARAMS} --download-high-res"
fi
if bashio::config.true 'same_image'; then
    PARAMS="${PARAMS} --same-image"
fi
if bashio::config.true 'media_folder_path'; then
    PARAMS="${PARAMS} --media-folder-path"
fi
if bashio::config.true 'matte'; then
    PARAMS="${PARAMS} --matte"
fi
if bashio::config.true 'matte_color'; then
    PARAMS="${PARAMS} --matte-color"
fi
if bashio::config.true 'log_path'; then
    PARAMS="${PARAMS} --log-path"
fi

python3 art.py --tvip ${TVIP} ${PARAMS}

echo "done, closing now!"
kill -s SIGHUP 1
