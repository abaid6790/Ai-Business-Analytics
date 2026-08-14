import os
import uuid

import joblib


def save_model(models_folder: str, user_id: int, pipeline) -> str:
    user_dir = os.path.join(models_folder, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"{uuid.uuid4().hex}.joblib")
    joblib.dump(pipeline, path)
    return path


def load_model(path: str):
    return joblib.load(path)


def delete_model(path: str) -> None:
    if path and os.path.isfile(path):
        os.remove(path)
