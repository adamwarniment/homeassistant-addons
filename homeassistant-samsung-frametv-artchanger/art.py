import sys
import logging
import os
import json
import argparse
from io import BytesIO
from typing import List
import random
import datetime

sys.path.append('../')

from samsungtvws import SamsungTVWS
from sources import bing_wallpapers, google_art, media_folder
from utils.utils import Utils

# Add command line argument parsing
parser = argparse.ArgumentParser(description='Upload images to Samsung TV.')
parser.add_argument('--upload-all', action='store_true', help='Upload all images at once')
parser.add_argument('--debug', action='store_true', help='Enable debug mode to check if TV is reachable')
parser.add_argument('--tvip', help='Comma-separated IP addresses of Samsung Frame TVs')
parser.add_argument('--same-image', action='store_true', help='Use the same image for all TVs (default: different images)')
parser.add_argument('--google-art', action='store_true', help='Download and upload image from Google Arts & Culture')
parser.add_argument('--download-high-res', action='store_true', help='Download high resolution image using dezoomify-rs')
parser.add_argument('--bing-wallpapers', action='store_true', help='Download and upload image from Bing Wallpapers')
parser.add_argument('--media-folder', action='store_true', help='Use images from the local media folder')
parser.add_argument('--debugimage', action='store_true', help='Save downloaded and resized images for inspection')
#parser.add_argument('--filter', action="store", type=str, default="none", help='photo filter to apply')
parser.add_argument('--media-folder-path', action='store', type=str, help='File path to look for photos')
parser.add_argument('--matte', action="store", type=str, help='matte to apply')
parser.add_argument('--matte-color', action="store", type=str, help='matte color to apply')
parser.add_argument('--log-path', action="store", type=str, help='Where file should logs be written to?')

args = parser.parse_args()


# Increase debug level
logging.basicConfig(level=logging.INFO)

# log the current date time
logging.info(f"Starting at {datetime.datetime.now()}")
logging.info(f"Arguments: {args}")

# Set the path to the file that will store the list of uploaded filenames
# set upload_list_path as arg with fallback of uploaded_files.json
if args.log_path:
    upload_list_path = args.log_path
else:
    upload_list_path = 'uploaded_files.json'

# Load the list of uploaded filenames from the file
if os.path.isfile(upload_list_path):
    with open(upload_list_path, 'r') as f:
        uploaded_files = json.load(f)
else:
    uploaded_files = []

sources = []
if args.bing_wallpapers:
    sources.append(bing_wallpapers)
if args.google_art:
    sources.append(google_art)
if args.media_folder:
    sources.append(media_folder)

if not sources:
    logging.error('No image source specified. Please use --google-art, --bing-wallpapers, or --media-folder')
    sys.exit(1)

tvip = args.tvip.split(',') if args.tvip else []
use_same_image = args.same_image

# get matte type
matte = args.matte
matte_color = args.matte_color
# Set the matte and matte color
if matte != 'none':
    matte_var = f"{matte}_{matte_color}"
else:
    matte_var = matte

# get filter_type
#filter_type = args.filter

utils = Utils(args.tvip, uploaded_files)

def process_tv(tv_ip: str, image_data: BytesIO, file_type: str, image_urls: List[str], remote_filename: str, source_name: str, matte_var: str):
    tv = SamsungTVWS(tv_ip)

    print('processing', tv_ip, image_data, file_type, image_urls, remote_filename, source_name, matte_var)
    
    # Check if TV supports art mode
    if not tv.art().supported():
        print(f'TV at {tv_ip} does not support art mode.')
        return

    if remote_filename is None:
        try:
            print(f'Uploading image to TV at {tv_ip}')
            remote_filename = tv.art().upload(image_data.getvalue(), file_type=file_type, matte=matte_var)
            if remote_filename is None:
                raise Exception('No remote filename returned')

            #set filter
            #await tv.set_photo_filter(remote_filename, filter_type)

            tv.art().select_image(remote_filename, show=True)
            print(f'Image uploaded and selected on TV at {tv_ip}')
            # Add the filename(s) to the list of uploaded filenames
            for img_url in image_urls:
                uploaded_files.append({
                    'file': img_url,
                    'remote_filename': remote_filename,
                    'tv_ip': tv_ip if len(tvip) > 1 else None,
                    'source': source_name,
                    'matte': matte_var,
                    'timestamp': datetime.datetime.now().isoformat()
                })
            # Save the list of uploaded filenames to the file
            # log the text that will be written to upload_list_path
            print(f'Writing uploaded files to {upload_list_path}')
            with open(upload_list_path, 'w') as f:
                # log the json dump
                print(f'uploaded files {uploaded_files}')
                json.dump(uploaded_files, f)
        except Exception as e:
            print(f'There was an error uploading the image to TV at {tv_ip}: ' + str(e))
    else:
        if not args.upload_all:
            # Select the image using the remote file name only if not in 'upload-all' mode
            print(f'Setting existing image on TV at {tv_ip}, skipping upload')
            tv.art().select_image(remote_filename, show=True)

def get_image_for_tv(tv_ip: str):
    selected_source = random.choice(sources)
    logging.info(f'Selected source: {selected_source.__name__}')

    image_url = selected_source.get_image_url(args)
    remote_filename = utils.get_remote_filename(image_url, selected_source.__name__, tv_ip)

    if remote_filename:
        return None, None, [image_url], remote_filename, selected_source.__name__

    image_data, file_type = selected_source.get_image(args, image_url)
    if image_data is None:
        return None, None, None, None, None

    save_debug_image(image_data, f'debug_{selected_source.__name__}_original.jpg')

    logging.info('Resizing and cropping the image...')
    #resized_image_data = utils.resize_and_crop_image(image_data)
    resized_image_data, img_srcs, portraits = utils.resize_or_combine_local_media(image_data, image_url, args.media_folder_path)
    # overrider file_type
    file_type = 'JPEG'

    print('pre-porcessing', resized_image_data, file_type, img_srcs, None, selected_source.__name__)

    return resized_image_data, file_type, img_srcs, None, selected_source.__name__

def save_debug_image(image_data: BytesIO, filename: str) -> None:
    if args.debugimage:
        with open(filename, 'wb') as f:
            f.write(image_data.getvalue())
        logging.info(f'Debug image saved as {filename}')

if tvip:
    if len(tvip) > 1 and use_same_image:
        image_data, file_type, image_urls, remote_filename, source_name = get_image_for_tv(None)
        for tv_ip in tvip:
            process_tv(tv_ip, image_data, file_type, image_urls, remote_filename, source_name, matte_var)
    else:
        for tv_ip in tvip:
            image_data, file_type, image_urls, remote_filename, source_name = get_image_for_tv(tv_ip)
            process_tv(tv_ip, image_data, file_type, image_urls, remote_filename, source_name, matte_var)
else:
    logging.error('No TV IP addresses specified. Please use --tvip')
    sys.exit(1)
