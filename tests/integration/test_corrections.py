from datetime import datetime
from pathlib import Path
import pytest

from sehatraasta.domain import Language, ReferralStatus, AttachmentCategory, Provenance, ProvenanceType
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.file_service import FileService
from sehatraasta.storage import SQLiteRepository


@pytest.fixture
def case(tmp_path):
    database = tmp_path / 'local' / 'records.sqlite'
    service = BundleService(SQLiteRepository(database))
    for patient, visit in [('PK-001', 'RB-001'), ('PK-002', 'RB-002')]:
        service.create_patient(patient, 'Fictional ' + patient, None, Language.ENGLISH)
        service.create_bundle(patient, visit, datetime(2026, 10, 7), '', '', ReferralStatus.DRAFT)
    source = tmp_path / 'fictional.pdf'
    source.write_bytes(b'%PDF-1.4\nFictional original')
    FileService(database).import_file('RB-001', 'AT-001', source,
        AttachmentCategory.OTHER, None, Provenance(ProvenanceType.NOT_SUPPLIED))
    return service, source


def test_visit_reassignment_preserves_original_and_rejects_stale_edit(case):
    from sehatraasta.services.correction_service import CorrectionService
    service, source = case
    revision = service.get_patient('PK-001')._storage_revision
    edits = CorrectionService(service.repository.path)
    edits.visit('RB-001', revision, patient_id='PK-002', facility='Fictional corrected clinic',
        destination='', date_kind='approximate', date_value='2008-07')
    patient, visit = service.get_bundle_owner('RB-001')
    assert patient.ID == 'PK-002'
    assert visit.medical_date_value == '2008-07'
    assert FileService(service.repository.path).retrieve('AT-001')[0] == source.read_bytes()
    with pytest.raises(ValueError, match='changed'):
        edits.visit('RB-001', revision, patient_id='PK-002', facility='stale',
            destination='', date_kind='unknown', date_value=None)
    assert service.get_bundle('RB-001').source_facility == 'Fictional corrected clinic'


def test_document_move_has_one_owner_and_replacement_failure_keeps_bytes(case, tmp_path):
    from sehatraasta.services.correction_service import CorrectionService
    service, source = case
    edits = CorrectionService(service.repository.path)
    revision = service.get_patient('PK-001')._storage_revision
    edits.document('AT-001', revision, name='Fictional renamed.pdf', category='other',
        document_date=None, destination_visit='RB-002')
    assert service.get_bundle('RB-001').attachments == []
    assert service.get_bundle('RB-002').attachments[0].name == 'Fictional renamed.pdf'
    bad = tmp_path / 'bad.pdf'
    bad.write_bytes(b'not a PDF')
    with pytest.raises(ValueError):
        edits.replace('AT-001', service.get_patient('PK-002')._storage_revision, bad)
    assert FileService(service.repository.path).retrieve('AT-001')[0] == source.read_bytes()
    assert len(list(FileService(service.repository.path).root.iterdir())) == 1


def test_failed_file_write_keeps_old_original_and_successful_retry_replaces(case, tmp_path, monkeypatch):
    from sehatraasta.services.correction_service import CorrectionService
    from sehatraasta.storage.errors import StorageError
    import sehatraasta.services.correction_service as module
    service, original = case
    edits = CorrectionService(service.repository.path)
    revision = service.get_patient('PK-001')._storage_revision
    replacement = tmp_path / 'fictional-better.pdf'
    replacement.write_bytes(b'%PDF-1.4\nFictional better scan')
    def full_disk(_):
        raise OSError('fictional low-storage simulation')
    with monkeypatch.context() as patch:
        patch.setattr(module.os, 'fsync', full_disk)
        with pytest.raises(StorageError):
            edits.replace('AT-001', revision, replacement)
    assert FileService(service.repository.path).retrieve('AT-001')[0] == original.read_bytes()
    assert len(list(FileService(service.repository.path).root.iterdir())) == 1
    edits.replace('AT-001', revision, replacement)
    assert FileService(service.repository.path).retrieve('AT-001')[0] == replacement.read_bytes()
    assert service.get_bundle('RB-001').attachments[0].name == 'fictional-better.pdf'
