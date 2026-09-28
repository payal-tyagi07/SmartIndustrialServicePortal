from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile
from flask import current_app
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "docx"}

def save_attachment(file):
    if not file or not file.filename: return None
    extension = Path(secure_filename(file.filename)).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS: raise ValueError("Only JPG, JPEG, PNG, PDF, and DOCX files are allowed.")
    content = file.read(); file.seek(0)
    if len(content) > current_app.config["MAX_CONTENT_LENGTH"]: raise ValueError("File must not exceed 5 MB.")
    if extension in {"jpg", "jpeg", "png"}:
        try: image = Image.open(BytesIO(content)); image.verify(); mime_type = Image.open(BytesIO(content)).get_format_mimetype()
        except UnidentifiedImageError as exc: raise ValueError("Invalid image content.") from exc
    elif extension == "pdf":
        if not content.startswith(b"%PDF-"): raise ValueError("Invalid PDF content.")
        mime_type = "application/pdf"
    else:
        try:
            with ZipFile(BytesIO(content)) as archive:
                if "[Content_Types].xml" not in archive.namelist(): raise ValueError("Invalid DOCX content.")
        except BadZipFile as exc: raise ValueError("Invalid DOCX content.") from exc
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    name = f"{uuid4().hex}.{extension}"; directory = Path(current_app.config["UPLOAD_FOLDER"]); directory.mkdir(parents=True, exist_ok=True); file.save(directory / name)
    thumbnail = None
    if extension in {"jpg", "jpeg", "png"}:
        thumb_name = f"{uuid4().hex}_thumb.jpg"
        with Image.open(directory / name) as image:
            image.thumbnail((320, 320)); image.convert("RGB").save(directory / thumb_name, "JPEG", quality=85, optimize=True)
        thumbnail = f"uploads/{thumb_name}"
    return name, mime_type, f"uploads/{name}", thumbnail

def soft_delete_complaint(complaint):
    """Remove local file objects while retaining a soft-deleted audit record."""
    complaint.deleted_at = datetime.utcnow()
    for attachment in complaint.attachments:
        for stored_path in (attachment.storage_path, attachment.thumbnail_path):
            if stored_path:
                (Path(current_app.static_folder) / stored_path).unlink(missing_ok=True)
