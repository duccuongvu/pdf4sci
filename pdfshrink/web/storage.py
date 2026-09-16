"""Per-job temporary file storage for the web app.

Each upload gets a random token (its job directory name); the input PDF,
compressed output, and a small metadata file live there. Tokens are opaque
uuid4 hex strings, never derived from user input, so there is no path-
traversal surface even though a token round-trips through the client
between requests.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass

_BASE_DIR = os.path.join(tempfile.gettempdir(), "pdfshrink-web")
os.makedirs(_BASE_DIR, exist_ok=True)


@dataclass
class StoredFile:
    token: str
    path: str
    original_name: str


def _job_dir(token: str) -> str:
    return os.path.join(_BASE_DIR, token)


def save_upload(file_storage) -> StoredFile:
    token = uuid.uuid4().hex
    job_dir = _job_dir(token)
    os.makedirs(job_dir, exist_ok=True)
    filename = file_storage.filename or "input.pdf"
    path = os.path.join(job_dir, "input.pdf")
    file_storage.save(path)
    with open(os.path.join(job_dir, "meta.json"), "w") as f:
        json.dump({"filename": filename}, f)
    return StoredFile(token=token, path=path, original_name=filename)


def input_path(token: str) -> str:
    return os.path.join(_job_dir(token), "input.pdf")


def output_path(token: str) -> str:
    return os.path.join(_job_dir(token), "output.pdf")


def job_exists(token: str) -> bool:
    return os.path.isfile(input_path(token))


def get_original_name(token: str) -> str:
    try:
        with open(os.path.join(_job_dir(token), "meta.json")) as f:
            return json.load(f).get("filename", "document.pdf")
    except Exception:
        return "document.pdf"


def cleanup(token: str) -> None:
    shutil.rmtree(_job_dir(token), ignore_errors=True)
