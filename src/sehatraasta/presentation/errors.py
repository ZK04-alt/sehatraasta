from dataclasses import dataclass

from sehatraasta.storage.errors import StorageError
from .catalogs import translate


@dataclass(frozen=True)
class UIError:
    code: str
    field: str | None = None
    status: int = 422

    def message(self, language="en"):
        return translate(self.code, language)

    def to_dict(self, language="en"):
        return {"code": self.code, "field": self.field,
                "message": self.message(language), "status": self.status}

    def as_text(self, language="en"):
        if self.field is None:
            return self.message(language)
        return translate('field.' + self.field, language) + ': ' + self.message(language)


def error_from_exception(error, field=None):
    """Stable display codes; raw exceptions never enter translated messages."""
    if isinstance(error, StorageError):
        return UIError("error.unavailable", field, 503)
    if not isinstance(error, (ValueError, TypeError)):
        return UIError("error.unexpected", None, 500)
    message = str(error).lower()
    # Only known field names enter public output; never echo arbitrary exception text.
    if field is None:
        for name in ('name', 'id', 'source', 'destination', 'date', 'category', 'language', 'amount'):
            if message in ('missing ' + name, 'invalid ' + name, 'unknown ' + name):
                field = name
    if "not found" in message or "file missing" in message:
        return UIError("error.not_found", field, 404)
    if "duplicate" in message:
        return UIError("error.duplicate", field, 409)
    if message.startswith("missing"):
        return UIError("error.required", field)
    if "amount" in message or "paisa" in message:
        return UIError("error.amount", field)
    if "date" in message or "time" in message:
        return UIError("error.date", field)
    if ("unknown" in message or "unsupported" in message) and "file" not in message:
        return UIError("error.choice", field)
    if "file" in message or "attachment" in message:
        return UIError("error.file", field)
    if "id" == message.removeprefix("invalid "):
        return UIError("error.id", field)
    return UIError("error.invalid", field)
