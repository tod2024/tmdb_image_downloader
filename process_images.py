import os
import logging
import requests
import zipfile
import shutil
from PIL import Image
from io import BytesIO
import pandas as pd  # Added Pandas import

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# TMDB API configuration
API_KEY = "7023be09f4209997fe159bee5f0fc3b5"
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

def process_images_from_csv(file, output_folder):
    """
    Processes images based on an uploaded CSV file containing movie names.

    :param file: File-like object of the uploaded CSV.
    :param output_folder: Path to the output folder for processed images.
    """
    import pandas as pd

    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(f"{output_folder}/backdrop", exist_ok=True)
    os.makedirs(f"{output_folder}/logos", exist_ok=True)

    # Define transformations
    transformations = [
        {"width": 240, "height": 135, "format": "png", "addLogo": False},
        {"width": 800, "height": 450, "format": "png", "addLogo": False},
        {"width": 1280, "height": 480, "format": "png", "addLogo": True},
        {"width": 640, "height": 360, "format": "webp", "addLogo": False}
    ]

    # Read the CSV file using Pandas
    try:
        data = pd.read_csv(file)
        data.columns = data.columns.str.strip().str.lower()  # Normalize column names
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return

    if "movie name" not in data.columns:
        logger.error(f"CSV file must contain a 'movie_name' column. Detected columns: {list(data.columns)}")
        return

    for _, row in data.iterrows():
        movie_name = row.get("movie name")
        if pd.isna(movie_name):
            logger.error("Missing movie name in CSV row. Skipping row.")
            continue

        movie_id = get_movie_id(movie_name)
        if not movie_id:
            logger.error(f"Movie ID not found for movie: {movie_name}. Skipping.")
            continue

        # Fetch image paths using movie ID
        image_data = fetch_image_data(movie_id)
        if not image_data:
            logger.error(f"No images found for movie ID: {movie_id}. Skipping.")
            continue

        # Process backdrop image
        if image_data.get("backdrop"):
            download_and_process_image(
                image_data["backdrop"],
                "backdrop",
                transformations,
                output_folder,
                movie_name
            )

        # Process logo image
        if image_data.get("logo"):
            download_and_process_image(
                image_data["logo"],
                "logos",
                transformations,
                output_folder,
                movie_name
            )


def get_movie_id(movie_name):
    """
    Fetches the TMDB movie ID for a given movie name.

    :param movie_name: Name of the movie.
    :return: Movie ID or None if not found.
    """
    response = requests.get(f"{BASE_URL}/search/movie", params={"api_key": API_KEY, "query": movie_name})
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0].get("id")  # Return the first matching result
    logger.error(f"Failed to fetch movie ID for {movie_name}. Response: {response.text}")
    return None


def fetch_image_data(movie_id):
    """
    Fetches image paths for a given movie ID.

    :param movie_id: TMDB movie ID.
    :return: Dictionary with image paths or None.
    """
    response = requests.get(f"{BASE_URL}/movie/{movie_id}/images", params={"api_key": API_KEY})
    if response.status_code == 200:
        data = response.json()
        return {
            "backdrop": data.get("backdrops", [{}])[0].get("file_path"),
            "logo": data.get("logos", [{}])[0].get("file_path")
        }
    logger.error(f"Failed to fetch images for movie ID {movie_id}. Response: {response.text}")
    return None


def download_and_process_image(image_path, image_type, transformations, output_folder, movie_name):
    """
    Downloads and processes a single image.

    :param image_path: Path of the image on TMDB.
    :param image_type: Type of image (e.g., 'backdrop' or 'logos').
    :param transformations: List of transformations to apply.
    :param output_folder: Path to the output folder for processed images.
    :param movie_name: Name of the movie for naming the files.
    """
    from PIL import Image

    # Replace spaces in the movie name with underscores
    movie_name = movie_name.replace(" ", "_")

    # Construct the full image URL
    image_url = f"{IMAGE_BASE_URL}{image_path}"
    response = requests.get(image_url)

    if response.status_code == 200:
        logger.info(f"Downloading {image_type} image from {image_url}.")
        try:
            # Open the image from the response content
            image = Image.open(BytesIO(response.content))

            # If processing a logo, only apply transformations if the logo is fetched
            if image_type == "logos":
                # Process only the logo image (no transformations needed for multiple ratios)
                output_path = f"{output_folder}/{image_type}/{movie_name}.{transformations[0]['format']}"
                image.save(output_path, format=transformations[0]['format'].upper())
                logger.info(f"Saved logo image to {output_path}.")
            else:
                # Process all transformations for backdrops
                for transform in transformations:
                    width, height = transform["width"], transform["height"]
                    aspect_ratio = f"{width}x{height}"
                    output_path = f"{output_folder}/{image_type}/{movie_name}_{aspect_ratio}.{transform['format']}"

                    # Resize and save the processed image
                    processed_image = image.resize((width, height))
                    processed_image.save(output_path, format=transform["format"].upper())
                    logger.info(f"Saved {image_type} image to {output_path}.")

        except Exception as e:
            logger.error(f"Error processing {image_type} image from {image_url}: {e}")
    else:
        logger.error(f"Failed to download {image_type} image from {image_url}. Response: {response.text}")



def zip_images(output_folder, zip_file_path):
    """
    Zips all files in the output folder into a single ZIP file.

    :param output_folder: Folder containing the processed images.
    :param zip_file_path: Path where the zip file should be saved.
    """
    try:
        # Create a zip file
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through all files in the directory
            for foldername, subfolders, filenames in os.walk(output_folder):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, output_folder)  # Create relative path for the zip file
                    zipf.write(file_path, arcname=arcname)
        logger.info(f"Images successfully zipped: {zip_file_path}")
    except Exception as e:
        logger.error(f"Error zipping images: {e}")
        raise


def clear_directory(directory):
    """
    Clears all files in a specified directory.

    :param directory: Path to the directory to clear.
    """
    # Check if the directory exists
    if os.path.exists(directory):
        # Remove all files and subdirectories
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Remove subdirectory
                else:
                    os.remove(file_path)  # Remove file
            except Exception as e:
                logger.error(f"Error removing file or directory {file_path}: {e}")
    else:
        logger.info(f"Directory {directory} does not exist, skipping clear.")