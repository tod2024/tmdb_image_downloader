import os
import logging
from flask import Flask, render_template, request, send_file, jsonify,send_from_directory
from process_images import process_images_from_csv, clear_directory
from datetime import datetime
import zipfile

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "static/TMDBImages"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
# Define the path to the root directory where index.html is located
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))


@app.route("/")
def index():
    """
    Serve the index.html file from the project root.
    """
    return send_from_directory(PROJECT_ROOT, 'index.html')


@app.route("/upload", methods=["POST"])
def upload_file():
    logger.info("File upload endpoint hit.")

    # Check if the file is in the request
    if "file" not in request.files:
        logger.error("No file part in the request.")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    # Check if the file has a name
    if file.filename == "":
        logger.error("No file selected for uploading.")
        return jsonify({"error": "No file selected"}), 400

    # Ensure the file is a CSV
    if not file.filename.endswith(".csv"):
        logger.error("Uploaded file is not a CSV.")
        return jsonify({"error": "Only CSV files are allowed"}), 400

    try:
        # Clear the 'backdrop' and 'logos' directories before processing
        clear_directory(f"{OUTPUT_FOLDER}")


        # Process the images from the uploaded CSV
        process_images_from_csv(file, OUTPUT_FOLDER)

        # Generate the download URL with timestamp in filename
        timestamp = datetime.now().strftime("%Y-%m-%d")  # Get the current date in YYYY-MM-DD format
        zip_path = os.path.join(OUTPUT_FOLDER, f"TMDBImages_{timestamp}.zip")

        # Create the ZIP file using Python's zipfile module
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through all files in the directory and add them to the ZIP file
            for foldername, subfolders, filenames in os.walk(OUTPUT_FOLDER):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, OUTPUT_FOLDER)  # Create relative path for the zip file
                    zipf.write(file_path, arcname=arcname)

        logger.info(f"Images successfully zipped: {zip_path}")
        return jsonify({"message": "Processing completed.", "download_url": f"/download?file={zip_path}"})
    except Exception as e:
        logger.error(f"Error processing images: {e}")
        return jsonify({"error": "Failed to process images."}), 500



@app.route("/download", methods=["GET"])
def download_file():
    """
    Allows the user to download the processed images ZIP file.
    """
    file_path = request.args.get("file")
    if not file_path:
        logger.error("No file path provided in the request.")
        return jsonify({"error": "File not specified"}), 400

    if not os.path.exists(file_path):
        logger.error(f"Requested file does not exist: {file_path}")
        return jsonify({"error": "File not found"}), 404

    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error sending file {file_path}: {e}")
        return jsonify({"error": "Failed to download file"}), 500



if __name__ == "__main__":
    app.run(debug=True)