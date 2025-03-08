import os
import logging
import random
from io import BytesIO
from typing import List, Tuple, Optional, Dict
from PIL import Image

#folder_path = '/media/frame'

def get_media_folder_images(folder_path: str) -> List[str]:
    """Get a list of JPG/PNG/HEIC files in the folder, and search recursively if you want to use subdirectories"""
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    #logging.info(f"Files in {folder_path}:")
    #for file in files:
    #    logging.info(f"  - {file}")
    return [os.path.join(root, f) for root, dirs, files in os.walk(folder_path) for f in files if f.endswith(('.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG', '.heic', '.HEIC'))]

def find_portrait_image_url(media_folder_path, exclusions: List[str] = []) -> Optional[str]:
    """
    Similar to get_image_url, but selects only portrait images (15% taller than wide).
    Also accepts an exclusions list of filepaths to skip.
    """
    if media_folder_path:
        folder_path = media_folder_path
    else:
        folder_path = '/media/frame'

    files = get_media_folder_images(folder_path)
    random.shuffle(files) # Shuffle the list in place
    if not files:
        logging.info('No images found in the media folder.')
        return None

    for file_path in files:
        print(file_path);
        # Check if the file_path is in the exclusions list
        if file_path in exclusions:
            logging.info(f"Skipping excluded file: {file_path}")
            continue

        try:
            with open(file_path, 'rb') as f:
                img_data = BytesIO(f.read())
                img = Image.open(img_data)
                width, height = img.size
                if height > width * 1.15:  # Check for portrait orientation (15% taller)
                    return folder_path + '/' + os.path.basename(file_path)
                else:
                    print('not portrait')
        except (IOError, OSError) as e:
            logging.warning(f"Error processing image {file_path}: {e}. Skipping.")
            continue  # Skip to the next image if there's an error

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
