"""
Server-side upload validation. Never trust the client-supplied extension
alone — magic bytes are checked so a renamed .exe with a .csv extension
doesn't get treated as a dataset.
"""

import csv
import io

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

# ZIP magic bytes — .xlsx files are zip archives (OOXML).
XLSX_MAGIC = b"PK\x03\x04"
# OLE2 compound file magic bytes — legacy .xls files.
XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class UploadValidationError(Exception):
    pass


def get_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_extension(filename: str) -> str:
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type '.{ext}'. Allowed types: CSV, XLSX, XLS."
        )
    return ext


def validate_magic_bytes(file_head: bytes, ext: str) -> None:
    """
    `file_head` should be the first 8 bytes of the file. Confirms the
    actual file content matches the claimed extension.
    """
    if ext == "xlsx" and not file_head.startswith(XLSX_MAGIC):
        raise UploadValidationError(
            "This file doesn't look like a valid .xlsx file (failed content check)."
        )
    if ext == "xls" and not file_head.startswith(XLS_MAGIC):
        raise UploadValidationError(
            "This file doesn't look like a valid legacy .xls file (failed content check)."
        )
    if ext == "csv":
        # CSV has no magic bytes; reject obviously binary content instead —
        # a null byte in the first chunk almost never appears in real CSV/text.
        if b"\x00" in file_head:
            raise UploadValidationError(
                "This file doesn't look like a valid CSV (binary content detected)."
            )


def validate_csv_parseable(sample_text: str) -> None:
    """Best-effort structural check: can csv.Sniffer make sense of this?"""
    if not sample_text.strip():
        raise UploadValidationError("The uploaded file is empty.")
    try:
        csv.Sniffer().sniff(sample_text[:4096])
    except csv.Error:
        # Not fatal on its own (single-column CSVs can fail sniffing), but
        # combined with a downstream pandas parse failure we'll reject then.
        pass
