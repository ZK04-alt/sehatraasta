"""Synthetic local file intake. A type signature is not malware screening.

Policy: reject duplicate bytes across the dataset. Recovery removes generated
files without committed metadata. Delete commits metadata first; reconciliation
removes any leftover bytes after an interrupted delete. Run reconciliation only
while no other application process is using this instance.
"""
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
import re
import sqlite3

from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType
from sehatraasta.domain.validation import validate_id
from sehatraasta.storage.audit_repository import AuditRepository
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .attachment_inspection import generate_attachment_stored_name
from .attachment_validation import (
    validate_attachment_filename, validate_attachment_size, validate_attachment_signature,
)


def read_source(path):
    path = Path(path)
    extension = validate_attachment_filename(path.name)
    if path.is_symlink() or not path.is_file():
        raise ValueError("attachment file not found or unsafe")
    with path.open("rb") as stream:
        content = stream.read(5242881)
    validate_attachment_size(len(content))
    mime = validate_attachment_signature(extension, content[:8])
    return content, extension, mime


class FileService:
    def __init__(self, database):
        self.database = Path(database)
        self.root = self.database.parent / "attachments"
        self.audit = AuditRepository(self.database)

    def _path(self, name):
        if not re.fullmatch(r"[a-f0-9]{32}\.(pdf|png|jpg|jpeg)", name):
            raise StorageError("invalid stored attachment reference")
        if self.root.is_symlink() or self.root.is_junction():
            raise StorageError("unsafe attachment storage")
        path = self.root / name
        if path.is_symlink():
            raise StorageError("unsafe attachment storage")
        return path

    def import_file(self, bundle_id, attachment_id, source_path, category,
                    attachment_date, provenance, synthetic=False, order_id=None,
                    result_id=None, imaging_id=None, instruction_id=None,
                    medication_list=False):
        if synthetic is not True:
            raise ValueError("confirm that the file contains only synthetic data")
        validate_id(attachment_id)
        if not isinstance(category, AttachmentCategory):
            raise ValueError("unsupported attachment category")
        if not isinstance(provenance, Provenance):
            raise ValueError("invalid provenance")
        provenance.checks()
        if not isinstance(attachment_date, date) or isinstance(attachment_date, datetime):
            raise ValueError("invalid date")
        if type(medication_list) is not bool:
            raise ValueError("invalid medication list link")
        if sum(value is not None for value in (order_id, result_id, imaging_id, instruction_id)) + medication_list > 1:
            raise ValueError("choose at most one attachment link")
        connection = connect_database(self.database)
        created = None
        try:
            content, extension, mime = read_source(source_path)
            digest = hashlib.sha256(content).hexdigest()
            name = Path(source_path).name
            stored_name = generate_attachment_stored_name(extension)
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM referral_bundles WHERE bundle_id = ?", (bundle_id,)).fetchone() is None:
                    raise ValueError("bundle not found")
                if connection.execute("SELECT 1 FROM attachments WHERE sha256 = ?", (digest,)).fetchone():
                    raise ValueError("duplicate attachment content")
                connection.execute(
                    "INSERT INTO attachments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (attachment_id, bundle_id, category.value, name, stored_name, mime,
                     len(content), digest, attachment_date.isoformat(), provenance.source or "source not supplied"),
                )
                connection.execute(
                    "INSERT INTO managed_attachments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (attachment_id, bundle_id, stored_name, digest, category.value,
                     provenance.source_type.value, provenance.source_identifier,
                     order_id, result_id, imaging_id, instruction_id, int(medication_list)),
                )
                if connection.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("attachment link not found in this bundle")
                path = self._path(stored_name)
                self.root.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    created = path
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.audit.record(connection, bundle_id, attachment_id, "import", "success")
                connection.execute("UPDATE patients SET revision = revision + 1 WHERE patient_id = (SELECT patient_id FROM referral_bundles WHERE bundle_id = ?)", (bundle_id,))
            created = None
            return attachment_id
        except sqlite3.IntegrityError:
            raise ValueError("duplicate attachment ID or invalid attachment link") from None
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, "attachment_import", error)
            raise StorageError("could not store attachment; run reconciliation if cleanup failed") from None
        finally:
            connection.close()
            if created is not None:
                try:
                    created.unlink(missing_ok=True)
                except OSError as error:
                    log_storage_error(self.database, "attachment_cleanup", error)

    def retrieve(self, attachment_id):
        """Return verified bytes and MIME type, never an internal storage path."""
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT a.*, m.stored_name FROM attachments a JOIN managed_attachments m USING(attachment_id) WHERE a.attachment_id = ?", (attachment_id,)).fetchone()
                if row is None:
                    raise ValueError("stored attachment not found")
                path = self._path(row["stored_name"])
                if not path.exists():
                    outcome = "missing"
                    content = None
                else:
                    with path.open("rb") as stream:
                        content = stream.read(5242881)
                    outcome = "success"
                    if len(content) != row["size_bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                        outcome = "integrity failure"
                self.audit.record(connection, row["bundle_id"], attachment_id, "retrieve", outcome)
            if outcome != "success":
                raise ValueError("attachment file missing" if outcome == "missing" else "attachment integrity check failed")
            return content, row["mime_type"]
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, "attachment_retrieve", error)
            raise StorageError("could not retrieve attachment") from None
        finally:
            connection.close()

    def download(self, attachment_id, output):
        content, _ = self.retrieve(attachment_id)
        target = Path(output)
        if target.resolve().is_relative_to(self.database.parent.resolve()):
            raise ValueError("choose a download location outside the instance folder")
        try:
            with target.open("xb") as stream:
                stream.write(content)
        except OSError:
            raise StorageError("could not create download; choose a new file") from None

    def delete(self, attachment_id):
        connection = connect_database(self.database)
        path = None
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT * FROM managed_attachments WHERE attachment_id = ?", (attachment_id,)).fetchone()
                if row is None:
                    raise ValueError("stored attachment not found")
                path = self._path(row["stored_name"])
                outcome = "success" if path.exists() else "missing"
                self.audit.record(connection, row["bundle_id"], attachment_id, "delete", outcome)
                connection.execute("DELETE FROM managed_attachments WHERE attachment_id = ?", (attachment_id,))
                connection.execute("DELETE FROM attachments WHERE attachment_id = ?", (attachment_id,))
                connection.execute("UPDATE patients SET revision = revision + 1 WHERE patient_id = (SELECT patient_id FROM referral_bundles WHERE bundle_id = ?)", (row["bundle_id"],))
            path.unlink(missing_ok=True)
            return outcome
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, "attachment_delete", error)
            raise StorageError("attachment deletion interrupted; run reconciliation") from None
        finally:
            connection.close()

    def reconcile(self):
        """Exclusive local maintenance: remove only generated unreferenced files."""
        connection = connect_database(self.database)
        removed = 0
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute("SELECT * FROM managed_attachments").fetchall()
                referenced = {row["stored_name"] for row in rows}
                self._path("0" * 32 + ".pdf")
                if self.root.exists():
                    for path in self.root.iterdir():
                        if re.fullmatch(r"[a-f0-9]{32}\.(pdf|png|jpg|jpeg)", path.name) and path.name not in referenced:
                            self._path(path.name).unlink()
                            removed += 1
                for row in rows:
                    if not self._path(row["stored_name"]).exists():
                        self.audit.record(connection, row["bundle_id"], row["attachment_id"], "reconcile", "missing")
            return removed
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, "attachment_reconcile", error)
            raise StorageError("could not reconcile attachments") from None
        finally:
            connection.close()
