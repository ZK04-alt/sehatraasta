import re

from .enums import AttachmentCategory


def validate_id(ID):

    if not isinstance(ID, str):
        raise ValueError("invalid ID")
    elif not ID.strip():
        raise ValueError("missing ID")

    elif not re.fullmatch(r"[A-Z]{2}-\d{3}", ID) and not re.fullmatch(
        r"[A-Z]{2}-[A-Z]{2,20}-\d{3}", ID
    ):
        raise ValueError("invalid ID")


def validate_attachment_category(category):
    if not isinstance(category, AttachmentCategory):
        raise ValueError("unsupported attachment category")


def validate_record_id(ID, prefix, extended=False):
    """Accept new entity-specific IDs without invalidating saved legacy records."""
    if not isinstance(ID, str):
        raise ValueError('invalid ID')
    if not ID.strip():
        raise ValueError('missing ID')
    if re.fullmatch(re.escape(prefix) + r'-[2-9A-HJ-NP-Z]{6}', ID):
        return
    if extended:
        validate_id(ID)
    elif not re.fullmatch(r'[A-Z]{2}-\d{3}', ID):
        raise ValueError('invalid ID')
