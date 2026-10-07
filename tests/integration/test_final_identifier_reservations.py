"""Forced collisions must not make retained fictional records unrestorable."""
import pytest
from test_corrections import case
from sehatraasta.services.identifiers import IDAllocator
from sehatraasta.services.recovery_service import RecoveryService
from sehatraasta.services.correction_service import CorrectionService


@pytest.mark.parametrize('nested', [False, True])
def test_generated_text_id_skips_removed_records(case, monkeypatch, nested):
    service, _ = case
    service.add_medication('RB-001', 'MD-222222', 'Fictional old', '1 mg', '1 tablet', '', 'Daily', '3 days', '', '')
    recovery = RecoveryService(service.repository.path)
    removed = recovery.remove_record('medication', 'MD-222222', service.get_patient('PK-001')._storage_revision)
    if nested:
        parent = recovery.remove('patient', 'PK-001', service.get_patient('PK-001')._storage_revision)
    sequence = iter('222222333333')
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: next(sequence))
    assert IDAllocator(service.repository).allocate('medication') == 'MD-333333'
    if nested:
        recovery.restore(parent)
    recovery.restore(removed)
    assert service.get_bundle('RB-001').medication_item[0].ID == 'MD-222222'


def test_replacement_id_skips_active_and_retained_documents(case, tmp_path, monkeypatch):
    service, _ = case
    from sehatraasta.services.file_service import FileService
    from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType
    other = tmp_path / 'other.pdf'
    other.write_bytes(b'%PDF-1.4\nFictional other')
    FileService(service.repository.path).import_file('RB-001', 'AT-222222', other,
        AttachmentCategory.OTHER, None, Provenance(ProvenanceType.NOT_SUPPLIED))
    recovery = RecoveryService(service.repository.path)
    recovery.remove('document', 'AT-222222', service.get_patient('PK-001')._storage_revision)
    replacement = tmp_path / 'replacement.pdf'
    replacement.write_bytes(b'%PDF-1.4\nFictional replacement')
    sequence = iter('222222333333')
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: next(sequence))
    CorrectionService(service.repository.path).replace('AT-001', service.get_patient('PK-001')._storage_revision, replacement)
    for item in recovery.list():
        recovery.restore(item['item_id'])
    assert {paper.ID for paper in service.get_bundle('RB-001').attachments} == {'AT-001', 'AT-222222', 'AT-333333'}
