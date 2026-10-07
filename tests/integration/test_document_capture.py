from datetime import datetime
from pathlib import Path
import pytest

from sehatraasta.domain import Language
from sehatraasta.services.file_service import FileService
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.errors import StorageError


def source(tmp_path):
    path = tmp_path / 'fictional-paper.pdf'
    path.write_bytes(b'%PDF-1.4\n% fictional-only signature fixture')
    return path


def test_name_and_original_save_without_visit_reconstruction(tmp_path):
    from sehatraasta.services.document_capture_service import DocumentCaptureService
    database = tmp_path / 'data/records.sqlite'
    service = BundleService(SQLiteRepository(database))
    identifier = DocumentCaptureService(service).save(source(tmp_path), name='Fictional caregiver')
    patient, visit = service.get_bundle_owner(identifier)
    assert patient.name == 'Fictional caregiver'
    assert patient.birth_year is None
    assert visit.source_facility == ''
    assert (visit.medical_date_kind, visit.medical_date_value) == ('unknown', None)
    assert visit.medication_item == visit.diagnostic_results == []
    assert visit.attachments[0].date is None
    assert FileService(database).retrieve(visit.attachments[0].ID)[0] == source(tmp_path).read_bytes()


def test_existing_patient_context_and_approximate_date_survive_restart(tmp_path):
    from sehatraasta.services.document_capture_service import DocumentCaptureService
    database = tmp_path / 'data/records.sqlite'
    service = BundleService(SQLiteRepository(database))
    service.create_patient('PK-001', 'Fictional family member', None, Language.ENGLISH)
    identifier = DocumentCaptureService(service).save(source(tmp_path), patient_id='PK-001',
        medical_date_kind='approximate', medical_date_value='2020-02')
    restarted = BundleService(SQLiteRepository(database))
    patient, visit = restarted.get_bundle_owner(identifier)
    assert patient.ID == 'PK-001'
    assert len(restarted.list_patients()) == 1
    assert (visit.medical_date_kind, visit.medical_date_value) == ('approximate', '2020-02')
    assert visit.creation_time.year >= 2026
    assert visit.attachments[0].date is None


def test_storage_failure_preserves_dataset_and_retry_without_partial_visit(tmp_path, monkeypatch):
    from sehatraasta.services.document_capture_service import DocumentCaptureService
    database = tmp_path / 'data/records.sqlite'
    service = BundleService(SQLiteRepository(database))
    original_path = FileService._path
    def unavailable(self, name):
        raise StorageError('fictional injected storage failure')
    monkeypatch.setattr(FileService, '_path', unavailable)
    with pytest.raises(StorageError):
        DocumentCaptureService(service).save(source(tmp_path), name='Fictional caregiver')
    assert service.list_patients() == []
    assert not (database.parent / 'attachments').exists()
    monkeypatch.setattr(FileService, '_path', original_path)
    assert DocumentCaptureService(service).save(source(tmp_path), name='Fictional caregiver')
    assert len(service.list_patients()) == 1


def test_invalid_date_or_duplicate_does_not_leave_extra_patient_or_visit(tmp_path):
    from sehatraasta.services.document_capture_service import DocumentCaptureService
    database = tmp_path / 'data/records.sqlite'
    service = BundleService(SQLiteRepository(database))
    capture = DocumentCaptureService(service)
    with pytest.raises(ValueError):
        capture.save(source(tmp_path), name='Fictional', medical_date_kind='unknown', medical_date_value='2020')
    assert service.list_patients() == []
    capture.save(source(tmp_path), name='Fictional')
    with pytest.raises(ValueError, match='duplicate'):
        capture.save(source(tmp_path), name='Other Fictional')
    assert len(service.list_patients()) == len(service.list_bundles()) == 1
    assert len(list((database.parent / 'attachments').iterdir())) == 1
