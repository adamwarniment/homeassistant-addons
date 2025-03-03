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

#FILTER=$(bashio::config 'filter')
MATTE=$(bashio::config 'matte')
MATTE_COLOR=$(bashio::config 'matte_color')
MEDIA_FOLDER_PATH=$(bashio::config 'media_folder_path')
LOG_PATH=$(bashio::config 'log_path')

python3 art.py --tvip ${TVIP} ${PARAMS} --matte ${MATTE} --matte-color ${MATTE_COLOR} --media-folder-path ${MEDIA_FOLDER_PATH} --log-path ${LOG_PATH}

echo "done, closing now!"
kill -s SIGHUP 1
