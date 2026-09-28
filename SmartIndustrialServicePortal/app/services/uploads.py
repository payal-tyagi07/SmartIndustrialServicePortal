from pathlib import Path
from uuid import uuid4
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "pdf"}

def save_attachment(file):
    if not file or not file.filename:
        return None
    suffix = Path(secure_filename(file.filename)).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only JPG, JPEG, PNG, GIF, and PDF files are allowed.")
    filename = f"{uuid4().hex}.{suffix}"
    file.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
    return filename
