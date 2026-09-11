"""Read synthetic attachment files without copying them or changing the database."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sehatraasta.services.attachment_validation import (
    validate_attachment_filename,
    validate_attachment_signature,
    validate_attachment_size,
)


@dataclass
class AttachmentInspection:
    name: str
    extension: str
    MIME_type: str
    size: int
    sha: str


def inspect_attachment_file(source_path):
    if not isinstance(source_path, (str, Path)):
        raise ValueError("invalid attachment source")
    if isinstance(source_path, str) and not source_path.strip():
        raise ValueError("invalid attachment source")
    if "\x00" in str(source_path):
        raise ValueError("invalid attachment source")

    path = Path(source_path)

    try:
        if path.is_symlink():
            raise ValueError("invalid attachment source")

        # stat() reports missing files and access errors before we read anything.
        path.stat()
        if not path.is_file():
            raise ValueError("invalid attachment source")

        name = path.name
        extension = validate_attachment_filename(name)
        size = 0
        hash_object = hashlib.sha256()

        with path.open("rb") as file:
            chunk = file.read(4096)
            if not chunk:
                raise ValueError("invalid file size")

            MIME_type = validate_attachment_signature(extension, chunk[:8])

            # Count and hash the same bytes, including the first chunk's header.
            while chunk:
                size += len(chunk)
                validate_attachment_size(size)
                hash_object.update(chunk)
                chunk = file.read(4096)

        return AttachmentInspection(
            name, extension, MIME_type, size, hash_object.hexdigest()
        )
    except FileNotFoundError:
        raise ValueError("attachment file not found") from None
    except OSError:
        raise ValueError("cannot read attachment file") from None


def generate_attachment_stored_name(extension):
    if not isinstance(extension, str) or extension not in [
        ".pdf", ".png", ".jpg", ".jpeg"
    ]:
        raise ValueError("unsupported file extension")

    # This proposes a name only. The later copy operation must prevent overwrites.
    return uuid4().hex + extension
