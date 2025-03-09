from io import BytesIO
import os
import logging
from PIL import Image, ImageDraw
from typing import List, Tuple, Optional, Dict
import pillow_heif

from sources import media_folder

class Utils:
    def __init__(self, tvips: str, uploaded_files: List[Dict[str, str]]):
        self.tvips = tvips
        self.uploaded_files = uploaded_files
        self.check_tv_ip = len(tvips.split(',')) > 1 if tvips else False #only check the tv_ip if there is more than one tv_ip

    @staticmethod
    def resize_or_combine_local_media(img_data, img_src='', media_folder_path='', target_width=3840, target_height=2160):
        # log img_data
        isPortrait = Utils.check_portrait(img_data)
        print(isPortrait)
        if isPortrait:
            ## go find another image that is portrait
            # args.media_folder_path = './test/images' #removed, using command line argument instead
            portrait_img_src = media_folder.find_portrait_image_url(media_folder_path, [img_src])
            img_data_two, img_filetype_two = media_folder.get_image_direct_path(media_folder_path, portrait_img_src)
            #img_data_two = Utils.get_image_data(portrait_img_src)
            logging.info('portrait image')
            output_img = Utils.combine_imgs(img_data, img_data_two)
            
            if output_img: #only run if an image exists
                # Save the combined image to a file
                #output_path = "./test/images/output.jpg"
                #os.makedirs(os.path.dirname(output_path), exist_ok=True)
                #output_img.save(output_path, format="JPEG", quality=90)
                #logging.info(f"Combined image saved to: {output_path}")
                return output_img, [img_src, portrait_img_src], True
            else:
                logging.error("No output image was generated.")

        else:
            output_img = Utils.resize_and_crop_image(img_data, target_width, target_height)
            if output_img:
            # Save the combined image to a file
                #output_path = "./test/images/output.jpg"
                #os.makedirs(os.path.dirname(output_path), exist_ok=True)
                #output_img.save(output_path, format="JPEG", quality=90)
                #logging.info(f"Combined image saved to: {output_path}")
                return output_img, [img_src], False
            else:
                logging.error("No output image was generated.")
        return None #No longer returns bytesIO, returns None
    
    @staticmethod
    def resize_and_crop_image(image_data, target_width=3840, target_height=2160):
        # Check if the input is a BytesIO object or a file path
        if isinstance(image_data, BytesIO):
            image_data.seek(0)
            try:
                # Try to open as a standard image format
                img = Image.open(image_data)
            except Exception:
                # Try to open as HEIC using pillow_heif
                image_data.seek(0)  # Reset the stream position
                try:
                    heif_file = pillow_heif.read_heif(image_data)
                    img = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                    )
                except Exception as e:
                    raise Exception(f"Failed to open image as either standard or HEIC format: {e}")

        else:
            try:
                # Try to open as a standard image format
                img = Image.open(image_data)
            except Exception:
                # Try to open as HEIC using pillow_heif
                try:
                    heif_file = pillow_heif.read_heif(image_data)
                    img = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                    )
                except Exception as e:
                     raise Exception(f"Failed to open image as either standard or HEIC format: {e}")

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
    
    @staticmethod
    def check_portrait(img_data):
        ## check if img_src holds an image that is 15% taller than it is wide
        #if not img_data:
        #    return None
            
        image_data = img_data

        if isinstance(image_data, BytesIO):
            image_data.seek(0)
            try:
                img = Image.open(image_data)
            except Exception:
                image_data.seek(0)
                heif_file = pillow_heif.read_heif(image_data)
                img = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )
        else:
            return None
            
        width, height = img.size
        
        # Check if the image is 15% taller than it is wide
        if height > width * 1.15:
            return True
        else:
            return False

    @staticmethod
    def get_image_data(image_path: str) -> Tuple[Optional[BytesIO], Optional[str]]:

        full_path = image_path
        if not os.path.exists(full_path):
            return None, None
        
        file_type = 'JPEG' if full_path.endswith(('.jpg','jpeg','.JPEG','.JPG')) else 'PNG' if full_path.endswith(('.png','.PNG')) else 'HEIC' if full_path.endswith(('.heic','.heif', '.HEIC', '.HEIF')) else 'unknown'
        with open(full_path, 'rb') as f:
            data = BytesIO(f.read())
        return data, file_type

    @staticmethod
    def combine_imgs(img_data1, img_data2, target_width=3840, target_height=2160):
        try:
            image_data1 = img_data1
            image_data2 = img_data2

            print(image_data1)
            print(image_data2)


            # Ensure both inputs are BytesIO objects
            if not isinstance(image_data1, BytesIO) or not isinstance(image_data2, BytesIO):
                logging.error("Both inputs must be BytesIO objects.")
                return None

            image_data1.seek(0)
            image_data2.seek(0)

            # Open the images, handling HEIC if necessary
            try:
                img1 = Image.open(image_data1)
            except Exception:
                image_data1.seek(0)
                heif_file = pillow_heif.read_heif(image_data1)
                img1 = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )

            try:
                img2 = Image.open(image_data2)
            except Exception:
                image_data2.seek(0)
                heif_file = pillow_heif.read_heif(image_data2)
                img2 = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )
            
            # Check if images are portrait (taller than wide)
            if img1.height <= img1.width or img2.height <= img2.width:
                logging.error("Both images must be portrait")
                return None

            # Resize images if they are not the target height
            if img1.height != target_height:
                img1 = Utils.resize_and_crop_image(image_data1, target_width // 2, target_height)

            if img2.height != target_height:
                img2 = Utils.resize_and_crop_image(image_data2, target_width // 2, target_height)

            img1_data = Image.open(img1)
            img2_data = Image.open(img2)

            # Calculate the dimensions for each half of the combined image
            half_width = target_width // 2

            # Create a new blank image with the target dimensions
            combined_img = Image.new("RGB", (target_width, target_height))

            # Paste the first image onto the left side
            combined_img.paste(img1_data, (0, 0))

            # Paste the second image onto the right side
            combined_img.paste(img2_data, (half_width, 0))

            # Add black line at the center
            draw = ImageDraw.Draw(combined_img)
            line_start = (half_width - 15, 0)
            line_end = (half_width + 15, target_height)
            draw.line([line_start, line_end], fill=(0, 0, 0), width=30)

            output = BytesIO()
            combined_img.save(output, format='JPEG', quality=90)
            output.seek(0)
            return output

        except Exception as e:
            logging.error(f"Error combining images: {e}")
            return None

    @staticmethod
    def resize_portrait_img(image_data):
      """
      Resizes a portrait image to a target width of 1920 and height of 2160, 
      extracting the vertical middle portion if the image is too tall.

      Args:
          image_data: A BytesIO object or a file path to the image data.

      Returns:
          A BytesIO object containing the resized image, or None if an error occurs.
      """
      target_width = 1920
      target_height = 2160

      try:
          # Open the image, handling both BytesIO and file paths, and HEIC format
          if isinstance(image_data, BytesIO):
              image_data.seek(0)
              try:
                  img = Image.open(image_data)
              except Exception:
                  image_data.seek(0)
                  heif_file = pillow_heif.read_heif(image_data)
                  img = Image.frombytes(
                      heif_file.mode,
                      heif_file.size,
                      heif_file.data,
                      "raw",
                  )
          else:
              try:
                  img = Image.open(image_data)
              except Exception:
                  heif_file = pillow_heif.read_heif(image_data)
                  img = Image.frombytes(
                      heif_file.mode,
                      heif_file.size,
                      heif_file.data,
                      "raw",
                  )

          # Check if the image is already the correct size
          if img.width == target_width and img.height == target_height:
              output = BytesIO()
              img.save(output, format='JPEG', quality=90)
              output.seek(0)
              return output

          # Check if the image is portrait (taller than wide)
          if img.width > img.height:
              logging.error("Input image is not portrait.")
              return None

          # Resize the image, maintaining aspect ratio, if smaller than target width
          if img.width < target_width:
            img = img.resize((target_width, int(img.height * (target_width/img.width))), Image.LANCZOS)

          # Calculate cropping dimensions for vertical middle extraction
          if img.height > target_height:
              top = (img.height - target_height) // 2
              bottom = top + target_height
              img = img.crop((0, top, target_width, bottom))

          # Resize to the target size (1920x2160)
          if img.size != (target_width, target_height):
            img = img.resize((target_width, target_height), Image.LANCZOS)

          # Save the processed image to a BytesIO object
          output = BytesIO()
          img.save(output, format='JPEG', quality=90)
          output.seek(0)
          return output

      except Exception as e:
          logging.error(f"Error resizing/cropping image: {e}")
          return None

    def get_remote_filename(self, file_name: str, source_name: str, tv_ip: str) -> Optional[str]:
        for uploaded_file in self.uploaded_files:
            if uploaded_file['file'] == file_name and uploaded_file['source'] == source_name:
                if self.check_tv_ip:
                    if uploaded_file['tv_ip'] == tv_ip:
                        return uploaded_file['remote_filename']
                else:
                    return uploaded_file['remote_filename']
        return None
    
    
