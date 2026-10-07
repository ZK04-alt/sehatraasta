from test_corrections import case
from sehatraasta.services.file_service import FileService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
import pytest


@pytest.mark.parametrize('kind,identifier', [('document', 'AT-001'), ('visit', 'RB-001'), ('patient', 'PK-001')])
def test_remove_restart_restore_preserves_original_and_other_patient(case, kind, identifier):
    from sehatraasta.services.recovery_service import RecoveryService
    service, original = case
    database = service.repository.path
    recovery = RecoveryService(database)
    item = recovery.remove(kind, identifier, service.get_patient('PK-001')._storage_revision)
    assert recovery.list()[0]['item_id'] == item
    assert service.get_patient('PK-002').name == 'Fictional PK-002'
    with pytest.raises(ValueError):
        FileService(database).retrieve('AT-001')
    assert FileService(database).reconcile() == 0
    assert list(FileService(database).root.iterdir())
    RecoveryService(database).restore(item)
    assert FileService(database).retrieve('AT-001')[0] == original.read_bytes()
    assert service.get_bundle_owner('RB-001')[0].ID == 'PK-001'
    assert RecoveryService(database).list() == []


def test_backup_includes_recovery_but_live_views_exclude_it(case, tmp_path):
    from sehatraasta.services.recovery_service import RecoveryService
    service, original = case
    recovery = RecoveryService(service.repository.path)
    item = recovery.remove('visit', 'RB-001', service.get_patient('PK-001')._storage_revision)
    backup = DatasetBackupService(service.repository.path)
    archive = backup.create(tmp_path / 'exports')
    backup.restore(tmp_path / 'exports' / archive, tmp_path / 'restored', confirmed=True)
    database = tmp_path / 'restored' / 'sehatraasta.sqlite'
    restored = BundleService(SQLiteRepository(database))
    assert [visit.ID for _, visit in restored.list_bundles()] == ['RB-002']
    RecoveryService(database).restore(item)
    assert FileService(database).retrieve('AT-001')[0] == original.read_bytes()


def test_permanent_delete_removes_retained_file_and_is_idempotent(case):
    from sehatraasta.services.recovery_service import RecoveryService
    service, _ = case
    recovery = RecoveryService(service.repository.path)
    item = recovery.remove('document', 'AT-001', service.get_patient('PK-001')._storage_revision)
    assert recovery.permanent(item) == 0
    assert not list(FileService(service.repository.path).root.iterdir())
    assert recovery.list() == []
    with pytest.raises(ValueError):
        recovery.restore(item)


def test_patient_permanent_deletion_includes_previously_removed_children(case):
    from sehatraasta.services.recovery_service import RecoveryService
    service, _ = case
    recovery = RecoveryService(service.repository.path)
    recovery.remove('document', 'AT-001', service.get_patient('PK-001')._storage_revision)
    patient = recovery.remove('patient', 'PK-001', service.get_patient('PK-001')._storage_revision)
    recovery.permanent(patient)
    assert recovery.list() == []
    assert not list(FileService(service.repository.path).root.iterdir())


def test_replacement_preserves_previous_scan_in_recovery(case, tmp_path):
    from sehatraasta.services.recovery_service import RecoveryService
    from sehatraasta.services.correction_service import CorrectionService
    service, original = case
    replacement = tmp_path / 'better.pdf'
    replacement.write_bytes(b'%PDF-1.4\nFictional improved scan')
    CorrectionService(service.repository.path).replace('AT-001', service.get_patient('PK-001')._storage_revision, replacement)
    recovery = RecoveryService(service.repository.path)
    assert recovery.list()[0]['kind'] == 'replacement'
    recovery.restore(recovery.list()[0]['item_id'])
    papers = service.get_bundle('RB-001').attachments
    assert len(papers) == 2
    assert {FileService(service.repository.path).retrieve(paper.ID)[0] for paper in papers} == {replacement.read_bytes(), original.read_bytes()}


def test_move_visit_carries_removed_original_to_correct_patient(case):
    from sehatraasta.services.recovery_service import RecoveryService
    from sehatraasta.services.correction_service import CorrectionService
    service, original = case
    recovery = RecoveryService(service.repository.path)
    removed = recovery.remove('document', 'AT-001', service.get_patient('PK-001')._storage_revision)
    CorrectionService(service.repository.path).visit('RB-001', service.get_patient('PK-001')._storage_revision,
        patient_id='PK-002', facility='', destination='', date_kind='unknown', date_value=None)
    assert recovery.list()[0]['parent_patient'] == 'PK-002'
    recovery.restore(removed)
    assert service.get_bundle_owner('RB-001')[0].ID == 'PK-002'
    assert FileService(service.repository.path).retrieve('AT-001')[0] == original.read_bytes()


def test_structured_edit_move_remove_restore_preserves_rows(case):
    from datetime import date
    from sehatraasta.services.correction_service import CorrectionService
    from sehatraasta.services.recovery_service import RecoveryService
    service, _ = case
    service.add_medication('RB-001','MD-001','Fictional medicine','1 mg','1 tablet','','Daily','3 days','','paper')
    edits = CorrectionService(service.repository.path)
    edits.record('medication','MD-001',service.get_patient('PK-001')._storage_revision,
        {'name':'Corrected fictional medicine'},'RB-002')
    assert service.get_bundle('RB-001').medication_item == []
    assert service.get_bundle('RB-002').medication_item[0].name == 'Corrected fictional medicine'
    with pytest.raises(ValueError):
        edits.record('medication','MD-001',service.get_patient('PK-002')._storage_revision, {'name':''},'RB-002')
    removed = RecoveryService(service.repository.path).remove_record('medication','MD-001',service.get_patient('PK-002')._storage_revision)
    assert service.get_bundle('RB-002').medication_item == []
    RecoveryService(service.repository.path).restore(removed)
    assert service.get_bundle('RB-002').medication_item[0].ID == 'MD-001'


def test_removed_bytes_are_reserved_until_restore_or_permanent_delete(case):
    from sehatraasta.services.recovery_service import RecoveryService
    from sehatraasta.domain import AttachmentCategory,Provenance,ProvenanceType
    service,original=case
    recovery=RecoveryService(service.repository.path)
    item=recovery.remove('document','AT-001',service.get_patient('PK-001')._storage_revision)
    files=FileService(service.repository.path)
    with pytest.raises(ValueError,match='duplicate'):
        files.import_file('RB-002','AT-002',original,AttachmentCategory.OTHER,None,Provenance(ProvenanceType.NOT_SUPPLIED))
    recovery.permanent(item)
    files.import_file('RB-002','AT-002',original,AttachmentCategory.OTHER,None,Provenance(ProvenanceType.NOT_SUPPLIED))


def test_failed_permanent_cleanup_stays_pending_and_retry_finishes(case,monkeypatch):
    from sehatraasta.services.recovery_service import RecoveryService
    from pathlib import Path
    service,_=case
    recovery=RecoveryService(service.repository.path)
    item=recovery.remove('document','AT-001',service.get_patient('PK-001')._storage_revision)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',lambda *args,**kwargs: (_ for _ in ()).throw(OSError('Fictional locked file')))
        assert recovery.permanent(item)==1
    assert recovery.list()[0]['state']=='purging'
    with pytest.raises(ValueError): recovery.restore(item)
    assert recovery.permanent(item)==0
    assert recovery.list()==[]
