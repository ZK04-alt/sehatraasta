import re


def validate_id(ID):

    if not isinstance(ID, str):
        raise ValueError("invalid ID")
    elif not ID.strip():
        raise ValueError("missing ID")

    elif not re.fullmatch(r"[A-Z]{2}-\d{3}", ID) and not re.fullmatch(
        r"[A-Z]{2}-[A-Z]{2,20}-\d{3}", ID
    ):
        raise ValueError("invalid ID")
