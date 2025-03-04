import os
import logging
import random
from io import BytesIO
from typing import List, Tuple, Optional, Dict

#folder_path = '/media/frame'

def get_media_folder_images(folder_path: str) -> List[str]:
    """Get a list of JPG/PNG/HEIC files in the folder, and search recursively if you want to use subdirectories"""
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    logging.info(f"Files in {folder_path}:")
    for file in files:
        logging.info(f"  - {file}")
    return [os.path.join(root, f) for root, dirs, files in os.walk(folder_path) for f in files if f.endswith(('.jpg', '.png', '.heic'))]

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
    for file in files:
        logging.info(f"Image  - {file}")
    selected_file = random.choice(files)
    return f"{os.path.basename(selected_file)}"

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
    
    file_type = 'JPEG' if full_path.endswith('.jpg') else 'PNG'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type