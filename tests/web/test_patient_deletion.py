from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
import sqlite3

import pytest

from test_routes import app, client, post, token
from sehatraasta.domain import Language, ReferralStatus, InvestigationOrderStatus, CostCategory, ReviewCategory, PresenceState
from sehatraasta.services.file_service import FileService
from sehatraasta.services.patient_deletion_service import PatientDeletionService
from sehatraasta.services.qr_service import QRService
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError


def confirmation(client):
    page = client.get('/patients/PK-001/delete')
    assert page.status_code == 200
    return {name: re.search(fr'name="{name}" value="([^"]+)"', page.text)[1]
            for name in ('csrf', 'revision')}


def populated(app, client):
    service = app.extensions['bundles']
    service.create_bundle('PK-001', 'RB-002', datetime(2026, 9, 21), 'A', 'B', ReferralStatus.DRAFT)
    service.create_patient('PK-002', 'Other Patient', 1990, Language.ENGLISH)
    service.create_bundle('PK-002', 'RB-003', datetime(2026, 9, 21), 'A', 'B', ReferralStatus.DRAFT)
    bundle_id = 'SR-DEMO-001'
    service.add_medication(bundle_id, 'MD-001', 'Test medicine', 'test strength', 'test dose', 'test route', 'test frequency', 'test duration', 'Test instructions', 'source not supplied')
    service.add_order(bundle_id, 'Test order', date(2026, 9, 21), 'source not supplied', InvestigationOrderStatus.ORDERED)
    service.add_result(bundle_id, 'RS-001', 'Test result', date(2026, 9, 21), 'Test source', 'Test result text', 'Test order')
    service.add_instruction(bundle_id, 'test', Language.ENGLISH, 'Test instruction', 'source not supplied', date(2026, 9, 21))
    service.add_imaging(bundle_id, 'IM-001', 'X-ray', 'Test part', date(2026, 9, 21), 'Test facility', 'Test report', None)
    service.add_cost(bundle_id, 'CO-001', CostCategory.TRAVEL, Decimal('250'), date(2026, 9, 21), 'test response')
    service.set_category_review(bundle_id, ReviewCategory.MEDICATION_LIST, PresenceState.PRESENT, 'Test reviewer', datetime(2026, 9, 21), 'Test review')
    for bundle, identifier, content in [('SR-DEMO-001', 'AT-001', b'one'), ('RB-002', 'AT-002', b'two'), ('RB-003', 'AT-003', b'other')]:
        response = post(client, f'/bundles/{bundle}/attachments/new', dict(
            ID=identifier, file=(BytesIO(b'%PDF-1.4' + content), 'report.pdf'),
            category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED'))
        assert response.status_code == 303
        QRService(app.config['DATABASE']).for_bundle(bundle)
    return service


def test_removes_all_owned_records_files_and_tokens_only(app, client):
    service = populated(app, client)
    other = service.get_patient('PK-002')
    response = client.post('/patients/PK-001/delete', data={**confirmation(client), 'confirm': 'yes'})
    assert response.status_code == 303
    assert client.get('/patients/PK-001').status_code == 404
    assert client.get('/bundles/RB-002').status_code == 404
    assert service.get_patient('PK-002') == other
    files = FileService(app.config['DATABASE'])
    assert files.retrieve(service.get_bundle('RB-003').attachments[0].ID)[0] == b'%PDF-1.4other'
    from sehatraasta.services.recovery_service import RecoveryService
    recovery = RecoveryService(app.config['DATABASE'])
    assert len(list(files.root.iterdir())) == 3  # ordinary removal retains owned originals
    assert recovery.permanent(recovery.list()[0]['item_id']) == 0
    assert len(list(files.root.iterdir())) == 1
    with connect_database(app.config['DATABASE']) as connection:
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        for table in ('referral_bundles', 'managed_attachments', 'file_audit_events', 'bundle_tokens',
                      'medication_items', 'investigation_orders', 'diagnostic_results', 'instructions',
                      'imaging_items', 'cost_entries', 'category_reviews', 'attachments', 'audit_events'):
            assert connection.execute(f"SELECT COUNT(*) FROM {table} WHERE bundle_id IN ('SR-DEMO-001', 'RB-002')").fetchone()[0] == 0


def test_requires_csrf_confirmation_and_current_revision(app, client):
    data = confirmation(client)
    assert client.post('/patients/PK-001/delete', data={'confirm': 'yes', 'revision': data['revision']}).status_code == 400
    assert client.post('/patients/PK-001/delete', data=data).status_code == 422
    app.extensions['bundles'].create_bundle('PK-001', 'RB-002', datetime(2026, 9, 21), 'A', 'B', ReferralStatus.DRAFT)
    assert client.post('/patients/PK-001/delete', data={**data, 'confirm': 'yes'}).status_code == 409
    assert client.get('/bundles/RB-002').status_code == 200


def test_database_failure_rolls_back_files_and_metadata(app, client):
    populated(app, client)
    database = app.config['DATABASE']
    with connect_database(database) as connection:
        connection.execute("CREATE TRIGGER reject_delete BEFORE DELETE ON patients BEGIN SELECT RAISE(ABORT, 'blocked'); END")
    revision = app.extensions['bundles'].get_patient('PK-001')._storage_revision
    with pytest.raises(StorageError):
        PatientDeletionService(database).delete('PK-001', revision)
    identifier = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    assert FileService(database).retrieve(identifier)[0] == b'%PDF-1.4one'
    assert client.get('/bundles/RB-002').status_code == 200


def test_file_cleanup_failure_is_reported_and_can_be_retried(app, client, monkeypatch):
    populated(app, client)
    database = app.config['DATABASE']
    original = Path.unlink
    def blocked(path, *args, **kwargs):
        if path.parent.name == 'attachments':
            raise PermissionError('locked')
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', blocked)
        revision = app.extensions['bundles'].get_patient('PK-001')._storage_revision
        assert PatientDeletionService(database).delete('PK-001', revision) == 2
    FileService(database).reconcile()
    assert len(list(FileService(database).root.iterdir())) == 1


def test_missing_attachment_does_not_prevent_patient_removal(app, client):
    populated(app, client)
    database = app.config['DATABASE']
    with connect_database(database) as connection:
        name = connection.execute("SELECT stored_name FROM managed_attachments WHERE bundle_id='SR-DEMO-001'").fetchone()[0]
    (FileService(database).root / name).unlink()
    revision = app.extensions['bundles'].get_patient('PK-001')._storage_revision
    assert PatientDeletionService(database).delete('PK-001', revision) == 0
