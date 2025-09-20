import os
import logging
import random
from io import BytesIO
from typing import List, Tuple, Optional, Dict
from PIL import Image
from pillow_heif import register_heif_opener

# Register the HEIF opener to enable Pillow to read HEIC/HEIF files
register_heif_opener()

def get_media_folder_images(folder_path: str) -> List[str]:
    """Get a list of supported image files in the folder, and search recursively."""
    supported_extensions = ('.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG', '.heic', '.HEIC', '.heif', '.HEIF')
    return [os.path.join(root, f) for root, dirs, files in os.walk(folder_path) for f in files if f.endswith(supported_extensions)]

def find_portrait_image_url(media_folder_path, exclusions: List[str] = []) -> Optional[str]:
    """
    Selects a portrait image (15% taller than wide) and returns its URL.
    It accepts an exclusions list of filepaths to skip.
    """
    if media_folder_path:
        folder_path = media_folder_path
    else:
        folder_path = '/media/frame'

    files = get_media_folder_images(folder_path)
    random.shuffle(files)
    if not files:
        logging.info('No images found in the media folder.')
        return None

    for file_path in files:
        file_name = os.path.basename(file_path)
        if file_name in exclusions:
            logging.info(f"Skipping excluded file: {file_path}")
            continue

        try:
            with open(file_path, 'rb') as f:
                img_data = BytesIO(f.read())
                img = Image.open(img_data)
                width, height = img.size
                if height > width * 1.15:
                    return os.path.basename(file_path)
                else:
                    print('not portrait')
        except (IOError, OSError) as e:
            logging.warning(f"Error processing image {file_path}: {e}. Skipping.")
            continue

    logging.info('No suitable portrait images found in the media folder.')
    return None

def get_image_url(args):
    # folder path with fallback
    if args.media_folder_path:
        folder_path = args.media_folder_path
    else:
        folder_path = '/media/frame'
        
    files = get_media_folder_images(folder_path)
    if not files:
        logging.info('No images found in the media folder.')
        return None
    selected_file = random.choice(files)
    return f"{os.path.basename(selected_file)}"

def get_image_direct_path(media_folder_path, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    # folder path with fallback
    if media_folder_path:
        folder_path = media_folder_path
    else:
        folder_path = '/media/frame'

    full_path = os.path.join(folder_path, image_url)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return None, None
    
    file_type = 'JPEG' if full_path.endswith(('.jpg', '.jpeg', '.JPEG', '.JPG')) else \
                'PNG' if full_path.endswith(('.png', '.PNG')) else \
                'HEIC' if full_path.endswith(('.heic', '.heif', '.HEIC', '.HEIF')) else \
                'unknown'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type

def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    # folder path with fallback
    if args.media_folder_path:
        folder_path = args.media_folder_path
    else:
        folder_path = '/media/frame'

    full_path = os.path.join(folder_path, image_url)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return None, None
    
    file_type = 'JPEG' if full_path.endswith(('.jpg', '.jpeg', '.JPEG', '.JPG')) else \
                'PNG' if full_path.endswith(('.png', '.PNG')) else \
                'HEIC' if full_path.endswith(('.heic', '.heif', '.HEIC', '.HEIF')) else \
                'unknown'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type