from datetime import datetime, timezone
from pathlib import Path


class StorageError(Exception):
    pass


def log_storage_error(path, operation, error):
    """Record technical diagnostics only: no SQL, parameters, paths or medical text."""
    log_path = Path(path).parent / "storage-errors.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    code = getattr(error, "sqlite_errorcode", "none")
    name = getattr(error, "sqlite_errorname", "none")
    line = f"{timestamp} operation={operation} error={type(error).__name__} code={code} name={name}\n"
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(line)
    except OSError:
        pass
