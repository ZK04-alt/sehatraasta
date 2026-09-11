from pathlib import Path


def validate_attachment_filename(name):

    invalid_chars = ["/", "\\", "\t", "\n", "\x00", "\r"]

    if not isinstance(name, str):
        raise ValueError("invalid attachment filename")
    if not name.strip():
        raise ValueError("missing attachment filename")
    if (
        len(name) > 150
        or any(char in name for char in invalid_chars)
        or not name.isprintable()
    ):
        raise ValueError("invalid attachment filename")

    extension = Path(name).suffix
    extension = extension.lower()

    if extension not in [".pdf", ".png", ".jpg", ".jpeg"]:
        raise ValueError("unsupported file extension")

    stem = Path(name).stem
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)}
    if stem.split(".")[0].upper() in reserved or any(char in name for char in ':<>"|?*'):
        raise ValueError("invalid attachment filename")
    if Path(stem).suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".exe", ".js", ".bat", ".cmd"):
        raise ValueError("invalid attachment filename")

    return extension


def validate_attachment_size(size):
    if not isinstance(size, int) or size <= 0 or isinstance(size, bool):
        raise ValueError("invalid file size")
    if size > 5242880:
        raise ValueError("file too large")


def validate_attachment_signature(ext, header):
    if not isinstance(ext, str) or ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
        raise ValueError("unsupported file extension")
    if not isinstance(header, bytes):
        raise ValueError("invalid file header")

    if ext == ".pdf" and header.startswith(b"%PDF-"):
        return "application/pdf"
    if ext == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if ext in [".jpg", ".jpeg"] and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # A matching beginning is not complete format validation or malware screening.
    raise ValueError("file type does not match extension")
