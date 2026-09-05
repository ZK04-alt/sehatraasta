import os
from pathlib import Path
import sqlite3
import tempfile

from .errors import StorageError, log_storage_error


MIGRATION_PATH = Path(__file__).parent / "migrations" / "001_initial.sql"
TABLE_NAMES = frozenset({
    "schema_version", "patients", "referral_bundles", "audit_events",
    "instructions", "cost_entries", "attachments", "imaging_items",
    "medication_items", "encounters", "category_reviews",
    "investigation_orders", "diagnostic_results",
})


def connect_database(path, read_only=False):
    connection = None
    try:
        if read_only:
            uri = Path(path).resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        else:
            connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except (OSError, sqlite3.Error) as error:
        if connection is not None:
            connection.close()
        log_storage_error(path, "connect", error)
        raise StorageError("could not open database") from error


def check_database(connection):
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )}
    if tables != TABLE_NAMES:
        raise StorageError("unrecognized or incomplete database schema")
    versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
    if versions != [1]:
        raise StorageError("unsupported database version")
    # Also reject a database that has the right table names but different columns.
    template = sqlite3.connect(":memory:")
    try:
        template.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
        expected = template.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        ).fetchall()
        actual = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        ).fetchall()
        if [tuple(row) for row in actual] != expected:
            raise StorageError("database schema does not match version 1")
    finally:
        template.close()
    if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
        raise StorageError("database integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise StorageError("database contains broken relationships")


def initialize_database(path):
    connection = None
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = connect_database(path)
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table'"
            ).fetchone()
            if exists is None:
                # Execute the trusted migration within this transaction. Avoid
                # executescript here because it commits an existing transaction.
                statement = ""
                for line in MIGRATION_PATH.read_text(encoding="utf-8").splitlines():
                    statement += line + "\n"
                    if sqlite3.complete_statement(statement):
                        sql = statement.strip()
                        if sql not in ("BEGIN TRANSACTION;", "COMMIT;"):
                            connection.execute(sql)
                        statement = ""
                if statement.strip():
                    raise StorageError("incomplete database migration")
            check_database(connection)
    except (OSError, sqlite3.Error, StorageError) as error:
        log_storage_error(path, "initialize", error)
        raise StorageError("could not initialize database; existing data was preserved") from error
    finally:
        if connection is not None:
            connection.close()


def backup_database(source_path, backup_path):
    """Write a checked SQLite snapshot. Never overwrite an existing backup."""
    source_path = Path(source_path).resolve()
    backup_path = Path(backup_path).resolve()
    if source_path == backup_path or backup_path.exists():
        raise ValueError("choose a new backup file")
    source = destination = None
    temporary = None
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = connect_database(source_path, read_only=True)
        check_database(source)
        descriptor, name = tempfile.mkstemp(prefix="backup-", suffix=".sqlite", dir=backup_path.parent)
        os.close(descriptor)
        temporary = Path(name)
        destination = connect_database(temporary)
        source.backup(destination)
        check_database(destination)
        destination.close()
        destination = None
        # Windows rename fails if the destination exists, preserving old backups.
        if backup_path.exists():
            raise ValueError("choose a new backup file")
        temporary.rename(backup_path)
        temporary = None
        return backup_path
    except (OSError, sqlite3.Error, StorageError) as error:
        log_storage_error(source_path, "backup", error)
        raise StorageError("could not create a verified backup") from error
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def restore_database(backup_path, destination_path):
    """Restore to a new database path, preserving both backup and current data."""
    return backup_database(backup_path, destination_path)
