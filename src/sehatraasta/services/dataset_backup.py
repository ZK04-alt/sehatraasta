"""Versioned JSON and attachment ZIP. Synthetic-only, not encrypted or signed.

Never extract archive paths. Import only into a newly created folder after a
successful dry run. Limits: 100 MiB expanded data and 1000 archive members.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from uuid import uuid4
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from sehatraasta.storage.db import check_database, connect_database, initialize_database
from sehatraasta.storage.errors import StorageError
from sehatraasta.storage.sqlite_repository import SQLiteRepository
from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType
from .qr_service import make_payload
from .attachment_validation import validate_attachment_signature, validate_attachment_size
from .file_service import FileService


TABLES = (
    "schema_version", "patients", "referral_bundles", "encounters", "medication_items",
    "instructions", "attachments", "investigation_orders", "diagnostic_results",
    "imaging_items", "cost_entries", "category_reviews", "audit_events",
    "managed_attachments", "file_audit_events", "bundle_tokens",
)
MAX_BYTES = 100 * 1024 * 1024


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def read_tables(connection):
    # Names are fixed constants, never archive/user-provided SQL identifiers.
    return {table: [dict(row) for row in connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in TABLES}


def check_files(database, members):
    service = FileService(database)
    connection = connect_database(database, read_only=True)
    try:
        rows = connection.execute("SELECT a.*, m.stored_name, m.sha256 AS managed_sha, m.category AS managed_category, m.source_type, m.source_identifier FROM managed_attachments m JOIN attachments a USING(attachment_id)").fetchall()
        if connection.execute("SELECT 1 FROM attachments WHERE generated_stored_name != '' AND attachment_id NOT IN (SELECT attachment_id FROM managed_attachments)").fetchone():
            raise ValueError("unmanaged attachment file reference")
        for token in connection.execute("SELECT token FROM bundle_tokens"):
            make_payload(token[0])
        expected = {"attachments/" + row["stored_name"] for row in rows}
        if set(members) != expected:
            raise ValueError("backup attachment set does not match metadata")
        for row in rows:
            AttachmentCategory(row["managed_category"])
            source_type = ProvenanceType(row["source_type"])
            source = None if source_type == ProvenanceType.NOT_SUPPLIED else row["source"]
            Provenance(source_type, source, row["source_identifier"])
            service._path(row["stored_name"])
            content = members["attachments/" + row["stored_name"]]
            validate_attachment_size(len(content))
            mime = validate_attachment_signature(Path(row["stored_name"]).suffix, content[:8])
            if (mime != row["mime_type"] or len(content) != row["size_bytes"]
                    or hashlib.sha256(content).hexdigest() != row["sha256"]
                    or row["managed_sha"] != row["sha256"]
                    or row["managed_category"] != row["category"]
                    or row["generated_stored_name"] != row["stored_name"]):
                raise ValueError("backup attachment integrity check failed")
    finally:
        connection.close()


class DatasetBackupService:
    def __init__(self, database):
        self.database = Path(database)

    def create(self, output_folder):
        folder = Path(output_folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("synthetic-backup-" + uuid4().hex + ".zip")
        connection = connect_database(self.database)
        temporary = None
        try:
            with connection:
                # FileService also holds this write lock during its operations.
                connection.execute("BEGIN IMMEDIATE")
                check_database(connection)
                tables = read_tables(connection)
                members = {"dataset.json": encoded({"version": 2, "synthetic_only": True, "tables": tables})}
                service = FileService(self.database)
                for row in tables["managed_attachments"]:
                    with service._path(row["stored_name"]).open("rb") as stream:
                        members["attachments/" + row["stored_name"]] = stream.read(5242881)
                if sum(len(value) for value in members.values()) > MAX_BYTES or len(members) > 999:
                    raise ValueError("dataset exceeds synthetic backup limits")
                check_files(self.database, {key: value for key, value in members.items() if key != "dataset.json"})
                manifest = {key: hashlib.sha256(value).hexdigest() for key, value in members.items()}
                with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", encoded(manifest))
                    for name, content in members.items():
                        archive.writestr(name, content)
            self.dry_run(temporary)
            temporary.rename(target)
            return target.name
        except (OSError, sqlite3.Error, BadZipFile) as error:
            raise StorageError("could not create complete synthetic backup") from None
        finally:
            connection.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _read_archive(self, path):
        try:
            with ZipFile(path) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                if len(names) != len(set(names)) or len(names) > 1000 or sum(item.file_size for item in infos) > MAX_BYTES:
                    raise ValueError()
                if "manifest.json" not in names or "dataset.json" not in names:
                    raise ValueError()
                for item in infos:
                    if item.filename not in ("manifest.json", "dataset.json"):
                        if not item.filename.startswith("attachments/"):
                            raise ValueError()
                        FileService(self.database)._path(item.filename[len("attachments/"):])
                    if item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError()
                members = {name: archive.read(name) for name in names}
            manifest = json.loads(members.pop("manifest.json"))
            if not isinstance(manifest, dict) or set(manifest) != set(members):
                raise ValueError()
            for name, content in members.items():
                if hashlib.sha256(content).hexdigest() != manifest[name]:
                    raise ValueError()
            document = json.loads(members.pop("dataset.json"))
            if type(document["version"]) is not int or document["version"] != 2 or document["synthetic_only"] is not True or set(document["tables"]) != set(TABLES):
                raise ValueError()
            return document["tables"], members
        except (OSError, BadZipFile, RuntimeError, KeyError, TypeError, ValueError, StorageError, UnicodeError):
            raise ValueError("invalid or corrupt synthetic backup") from None

    def _restore_staged(self, folder, tables, members):
        database = folder / "sehatraasta.sqlite"
        initialize_database(database)
        connection = connect_database(database)
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("PRAGMA defer_foreign_keys = ON")
                connection.execute("DELETE FROM schema_version")
                for table in TABLES:
                    columns = [row[1] for row in connection.execute('PRAGMA table_info("' + table + '")')]
                    sql = 'INSERT INTO "' + table + '" (' + ','.join('"' + column + '"' for column in columns) + ') VALUES (' + ','.join('?' for column in columns) + ')'
                    if not isinstance(tables[table], list):
                        raise ValueError("invalid backup rows")
                    for row in tables[table]:
                        if not isinstance(row, dict) or set(row) != set(columns):
                            raise ValueError("invalid backup columns")
                        connection.execute(sql, [row[column] for column in columns])
                check_database(connection)
        finally:
            connection.close()
        # Domain validation runs in addition to relational constraints.
        SQLiteRepository(database).list_patients()
        check_files(database, members)
        service = FileService(database)
        if members:
            service.root.mkdir()
        for name, content in members.items():
            service._path(name[len("attachments/"):]).write_bytes(content)
        return {"patients": len(tables["patients"]), "bundles": len(tables["referral_bundles"]),
                "attachments": len(members), "rows": sum(len(rows) for rows in tables.values()),
                "total_paisa": sum(row["amount_paisa"] for row in tables["cost_entries"])}

    def dry_run(self, archive):
        tables, members = self._read_archive(archive)
        try:
            with tempfile.TemporaryDirectory(prefix="sehatraasta-check-") as name:
                return self._restore_staged(Path(name), tables, members)
        except (ValueError, TypeError, KeyError, sqlite3.Error, StorageError, OSError):
            raise ValueError("backup validation failed; current data was not changed") from None

    def restore(self, archive, destination, confirmed=False):
        if confirmed is not True:
            raise ValueError("review the dry-run summary and confirm restore")
        target = Path(destination)
        if target.exists() or target.is_symlink():
            raise ValueError("restore requires a new folder")
        tables, members = self._read_archive(archive)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="sehatraasta-restore-", dir=target.parent) as name:
                staging = Path(name) / "instance"
                staging.mkdir()
                summary = self._restore_staged(staging, tables, members)
                if target.exists():
                    raise ValueError("restore requires a new folder")
                staging.rename(target)
                return summary
        except (OSError, sqlite3.Error, StorageError, KeyError, TypeError):
            raise ValueError("restore failed; current data was not changed") from None
