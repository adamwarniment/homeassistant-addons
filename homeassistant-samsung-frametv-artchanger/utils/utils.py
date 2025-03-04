from io import BytesIO
from PIL import Image
from typing import List, Dict, Optional
import pyheif

class Utils:
    def __init__(self, tvips: str, uploaded_files: List[Dict[str, str]]):
        self.tvips = tvips
        self.uploaded_files = uploaded_files
        self.check_tv_ip = len(tvips.split(',')) > 1 if tvips else False #only check the tv_ip if there is more than one tv_ip

    @staticmethod
    def resize_and_crop_image(image_data, target_width=3840, target_height=2160):
        # Check if the input is a BytesIO object or a file path
        if isinstance(image_data, BytesIO):
          image_data.seek(0)
          
          try:
            #Try open as standard image format
            img = Image.open(image_data)
          except Exception as e:
            #Try open as HEIC
            image_data.seek(0) #reset the stream position for pyheif
            heif_file = pyheif.read(image_data)
            img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data)
        else:
          try:
            img = Image.open(image_data)
          except Exception as e:
            heif_file = pyheif.read(image_data)
            img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data)

        # Calculate the aspect ratio
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height

        if img_ratio > target_ratio:
            # Image is wider than target, resize based on height
            new_height = target_height
            new_width = int(new_height * img_ratio)
        else:
            # Image is taller than target, resize based on width
            new_width = target_width
            new_height = int(new_width / img_ratio)

        # Resize the image
        img = img.resize((new_width, new_height), Image.LANCZOS)

        # Calculate dimensions for center cropping
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height

        # Perform center crop
        img = img.crop((left, top, right, bottom))

        # Save the processed image to a BytesIO object
        output = BytesIO()
        img.save(output, format='JPEG', quality=90)
        output.seek(0)
        return output

    def get_remote_filename(self, file_name: str, source_name: str, tv_ip: str) -> Optional[str]:
        for uploaded_file in self.uploaded_files:
            if uploaded_file['file'] == file_name and uploaded_file['source'] == source_name:
                if self.check_tv_ip:
                    if uploaded_file['tv_ip'] == tv_ip:
                        return uploaded_file['remote_filename']
                else:
                    return uploaded_file['remote_filename']
        return None
