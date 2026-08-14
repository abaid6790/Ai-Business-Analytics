"""
Thin storage abstraction so routes/services never touch `os.path` /
`open()` directly. Swapping to S3 or another backend later means changing
this one module, not every place that reads/writes dataset files.
"""

import os
import uuid

from werkzeug.utils import secure_filename


class LocalStorage:
    def __init__(self, upload_folder: str, temp_subfolder: str = "tmp"):
        self.upload_folder = upload_folder
        self.temp_folder = os.path.join(upload_folder, temp_subfolder)

    # --- Temp storage (between upload-preview and commit) ---
    def user_temp_dir(self, user_id: int) -> str:
        path = os.path.join(self.temp_folder, str(user_id))
        os.makedirs(path, exist_ok=True)
        return path

    def save_temp_file(self, user_id: int, file_storage, extension: str) -> str:
        """Saves an uploaded file to a per-user temp dir under a random name.
        Returns the temp filename (not full path) — callers store just this."""
        temp_dir = self.user_temp_dir(user_id)
        temp_filename = f"{uuid.uuid4().hex}.{extension}"
        file_storage.save(os.path.join(temp_dir, temp_filename))
        return temp_filename

    def temp_file_path(self, user_id: int, temp_filename: str) -> str:
        # secure_filename strips path traversal characters; combined with
        # per-user directories, a user can never reference another user's
        # temp file even if they guessed the exact random filename.
        safe_name = secure_filename(temp_filename)
        return os.path.join(self.user_temp_dir(user_id), safe_name)

    def temp_file_exists(self, user_id: int, temp_filename: str) -> bool:
        return os.path.isfile(self.temp_file_path(user_id, temp_filename))

    def discard_temp_file(self, user_id: int, temp_filename: str) -> None:
        path = self.temp_file_path(user_id, temp_filename)
        if os.path.isfile(path):
            os.remove(path)

    # --- Permanent storage ---
    def user_dataset_dir(self, user_id: int) -> str:
        path = os.path.join(self.upload_folder, str(user_id))
        os.makedirs(path, exist_ok=True)
        return path

    def commit_temp_file(self, user_id: int, temp_filename: str, extension: str) -> str:
        """Moves a temp file into permanent storage. Returns the full path."""
        temp_path = self.temp_file_path(user_id, temp_filename)
        if not os.path.isfile(temp_path):
            raise FileNotFoundError("Temp upload not found or expired.")

        permanent_dir = self.user_dataset_dir(user_id)
        permanent_filename = f"{uuid.uuid4().hex}.{extension}"
        permanent_path = os.path.join(permanent_dir, permanent_filename)
        os.replace(temp_path, permanent_path)
        return permanent_path

    def delete_file(self, path: str) -> None:
        if path and os.path.isfile(path):
            os.remove(path)

    def save_cleaned_dataframe(self, user_id: int, df, file_type: str) -> tuple[str, str]:
        """Writes a cleaned dataframe to permanent storage as a brand-new
        file — the source dataset's file on disk is never touched.
        Returns (path, actual_file_type) since legacy .xls can't be written
        by openpyxl and is upgraded to .xlsx on save."""
        actual_type = "xlsx" if file_type == "xls" else file_type
        permanent_dir = self.user_dataset_dir(user_id)
        permanent_filename = f"{uuid.uuid4().hex}_cleaned.{actual_type}"
        permanent_path = os.path.join(permanent_dir, permanent_filename)

        if actual_type == "csv":
            df.to_csv(permanent_path, index=False)
        else:
            df.to_excel(permanent_path, index=False, engine="openpyxl")

        return permanent_path, actual_type
