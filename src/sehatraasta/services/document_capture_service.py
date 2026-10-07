"""Atomically preserve one original with only a recognisable patient context."""
from datetime import date, datetime, timezone
import sqlite3

from sehatraasta.domain import (AttachmentCategory, Language, Patient, Provenance,
    ProvenanceType, ReferralBundle, ReferralStatus)
from sehatraasta.domain.medical_dates import validate_medical_date
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .file_service import FileService
from .identifiers import IDAllocator


class DocumentCaptureService:
    def __init__(self, bundles):
        self.bundles = bundles
        self.repository = bundles.repository

    def save(self, source_path, patient_id='', name='', birth_year=None,
             language=Language.ENGLISH, medical_date_kind='unknown',
             medical_date_value=None, facility='', original_name=None, unfinished=None):
        kind, value = validate_medical_date(medical_date_kind, medical_date_value)
        allocator = IDAllocator(self.repository)
        patient = self.bundles.get_patient(patient_id) if patient_id else Patient(
            allocator.allocate('patient'), name, birth_year, language)
        visit = ReferralBundle(allocator.allocate('bundle'), datetime.now(timezone.utc),
            facility, '', ReferralStatus.DRAFT, medical_date_kind=kind, medical_date_value=value)
        attachment_id = allocator.allocate('attachment')
        files = FileService(self.repository.path)
        connection = connect_database(self.repository.path)
        created = None
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if patient_id:
                    updated = connection.execute('UPDATE patients SET revision=revision+1 WHERE patient_id=? AND revision=?',
                        (patient.ID, patient._storage_revision))
                    if updated.rowcount != 1:
                        raise ValueError('patient changed; reload before saving')
                else:
                    connection.execute('INSERT INTO patients(patient_id,display_name,birth_year,language) VALUES(?,?,?,?)',
                        (patient.ID, patient.name, patient.birth_year, patient.language.name))
                self.repository._write_bundle(connection, patient.ID, visit)
                created = files.import_in_transaction(connection, visit.ID, attachment_id,
                    source_path, AttachmentCategory.OTHER,
                    date.fromisoformat(value) if kind == 'exact' else None,
                    Provenance(ProvenanceType.NOT_SUPPLIED), original_name=original_name)
                if unfinished:
                    removed = connection.execute('DELETE FROM visit_drafts WHERE draft_id=? AND revision=?', unfinished)
                    if removed.rowcount != 1:
                        raise ValueError('unfinished visit changed; reopen before saving')
            created = None
            return visit.ID
        except sqlite3.IntegrityError:
            raise ValueError('duplicate record; no changes saved') from None
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.repository.path, 'document_capture', error)
            raise StorageError('could not save paper; no changes saved') from None
        finally:
            connection.close()
            if created is not None:
                files.cleanup_uncommitted(created)
