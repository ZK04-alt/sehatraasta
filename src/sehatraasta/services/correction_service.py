"""Local corrections with revision checks and transaction-owned file staging."""
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
import sqlite3

from sehatraasta.domain import Patient, Language, AttachmentCategory
from sehatraasta.domain.medical_dates import validate_medical_date
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .attachment_inspection import generate_attachment_stored_name
from .attachment_validation import validate_attachment_filename
from .file_service import FileService, read_source


class CorrectionService:
    def __init__(self, database):
        self.database = Path(database)

    @contextmanager
    def transaction(self):
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                if connection.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('correction would break record relationships')
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, 'correction', error)
            raise StorageError('correction could not be saved; previous records remain') from None
        finally:
            connection.close()

    @staticmethod
    def owner(connection, visit_id, revision):
        row = connection.execute('SELECT p.* FROM patients p JOIN referral_bundles b USING(patient_id) WHERE b.bundle_id=?', (visit_id,)).fetchone()
        if row is None:
            raise ValueError('visit not found')
        if row['revision'] != revision:
            raise ValueError('records changed; reopen before saving')
        return row['patient_id']

    @staticmethod
    def touch(connection, *patient_ids):
        # Cross-patient moves must not make a source revision valid on a less
        # edited destination. Advance both beyond every involved revision.
        revision = max(connection.execute('SELECT revision FROM patients WHERE patient_id=?', (identifier,)).fetchone()[0]
            for identifier in set(patient_ids)) + 1
        for patient_id in set(patient_ids):
            connection.execute('UPDATE patients SET revision=? WHERE patient_id=?', (revision, patient_id))

    def patient(self, patient_id, revision, name, birth_year, language):
        Patient(patient_id, name, birth_year, Language[language])
        with self.transaction() as connection:
            updated = connection.execute('UPDATE patients SET display_name=?, birth_year=?, language=?, revision=revision+1 WHERE patient_id=? AND revision=?',
                (name, birth_year, language, patient_id, revision))
            if updated.rowcount != 1:
                raise ValueError('patient changed; reopen before saving')

    def visit(self, visit_id, revision, *, patient_id, facility, destination, date_kind, date_value):
        kind, value = validate_medical_date(date_kind, date_value)
        if not isinstance(facility, str) or not isinstance(destination, str):
            raise ValueError('invalid visit details')
        with self.transaction() as connection:
            previous = self.owner(connection, visit_id, revision)
            if connection.execute('SELECT 1 FROM patients WHERE patient_id=?', (patient_id,)).fetchone() is None:
                raise ValueError('destination patient not found')
            connection.execute('UPDATE referral_bundles SET patient_id=?, source_facility=?, destination=?, medical_date_kind=?, medical_date_value=? WHERE bundle_id=?',
                (patient_id, facility, destination, kind, value, visit_id))
            self.touch(connection, previous, patient_id)

    def document(self, attachment_id, revision, *, name, category, document_date, destination_visit, unlink=False):
        category = AttachmentCategory(category).value
        extension = validate_attachment_filename(name)
        if document_date is not None and (not isinstance(document_date, date) or isinstance(document_date, datetime)):
            raise ValueError('invalid document date')
        with self.transaction() as connection:
            row = connection.execute('SELECT * FROM managed_attachments WHERE attachment_id=?', (attachment_id,)).fetchone()
            if row is None:
                raise ValueError('document not found')
            previous = self.owner(connection, row['bundle_id'], revision)
            destination = connection.execute('SELECT patient_id FROM referral_bundles WHERE bundle_id=?', (destination_visit,)).fetchone()
            if destination is None:
                raise ValueError('destination visit not found')
            if extension != Path(row['stored_name']).suffix:
                raise ValueError('keep the document filename extension; use Replace to change file type')
            linked = any(row[key] for key in ('order_id', 'result_id', 'imaging_id', 'instruction_id', 'medication_list'))
            imaging = connection.execute('SELECT 1 FROM imaging_items WHERE attachment_id=?', (attachment_id,)).fetchone()
            if destination_visit != row['bundle_id'] and (linked or imaging) and not unlink:
                raise ValueError('linked document: move the whole visit or explicitly unlink before moving')
            if unlink:
                connection.execute('UPDATE managed_attachments SET order_id=NULL, result_id=NULL, imaging_id=NULL, instruction_id=NULL, medication_list=0 WHERE attachment_id=?', (attachment_id,))
                connection.execute('UPDATE imaging_items SET attachment_id=NULL WHERE attachment_id=?', (attachment_id,))
            connection.execute('UPDATE attachments SET bundle_id=?, original_display_name=?, category=?, date=? WHERE attachment_id=?',
                (destination_visit, name, category, document_date.isoformat() if document_date else None, attachment_id))
            connection.execute('UPDATE managed_attachments SET bundle_id=?, category=? WHERE attachment_id=?', (destination_visit, category, attachment_id))
            self.touch(connection, previous, destination['patient_id'])

    def replace(self, attachment_id, revision, source_path, original_name=None):
        content, extension, mime = read_source(source_path)
        name = original_name or Path(source_path).name
        if validate_attachment_filename(name) != extension:
            raise ValueError('replacement filename does not match its type')
        digest = hashlib.sha256(content).hexdigest()
        files = FileService(self.database)
        staged = files._path(generate_attachment_stored_name(extension))
        old = None
        committed = False
        try:
            with self.transaction() as connection:
                row = connection.execute('SELECT * FROM managed_attachments WHERE attachment_id=?', (attachment_id,)).fetchone()
                if row is None:
                    raise ValueError('document not found')
                patient_id = self.owner(connection, row['bundle_id'], revision)
                if connection.execute('SELECT 1 FROM attachments WHERE sha256=? AND attachment_id!=?', (digest, attachment_id)).fetchone():
                    raise ValueError('duplicate attachment content; open the saved paper instead')
                old = files._path(row['stored_name'])
                files.root.mkdir(parents=True, exist_ok=True)
                with staged.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                connection.execute('UPDATE attachments SET original_display_name=?, generated_stored_name=?, mime_type=?, size_bytes=?, sha256=? WHERE attachment_id=?',
                    (name, staged.name, mime, len(content), digest, attachment_id))
                connection.execute('UPDATE managed_attachments SET stored_name=?, sha256=? WHERE attachment_id=?', (staged.name, digest, attachment_id))
                self.touch(connection, patient_id)
            committed = True
        finally:
            if not committed:
                files.cleanup_uncommitted(staged)
        # Metadata commits first; existing reconciliation can retry an interrupted unlink.
        files.cleanup_uncommitted(old)
