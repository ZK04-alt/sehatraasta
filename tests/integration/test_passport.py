from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import json
import sqlite3
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from sehatraasta.domain import Language, ReferralStatus, CostCategory, ReviewCategory, PresenceState
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService, read_tables
from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.qr_service import QRService
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.db import connect_database, check_database
from sehatraasta.web import create_app
from sehatraasta.services.file_service import FileService
from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType, InvestigationOrderStatus


def make_case(path, patient_id='PK-001', bundle_id='SR-CASE-001'):
    service = BundleService(SQLiteRepository(path))
    service.create_patient(patient_id, 'Amina Example', 1980, Language.URDU)
    service.create_bundle(patient_id, bundle_id, datetime(2026, 10, 2, 9), 'Example clinic', 'Example hospital', ReferralStatus.DRAFT)
    return service


@pytest.fixture
def case(tmp_path):
    path = tmp_path / 'sender' / 'records.sqlite'
    service = make_case(path)
    service.add_cost('SR-CASE-001', 'CE-001', CostCategory.TRAVEL, Decimal('2500.10'), date(2026, 10, 2), 'Example source', '', 'reported', 'example')
    ReferralContextService(path).save('SR-CASE-001', {'medical_history': 'Example history', 'department': 'Orthopaedics', 'referral_reason': 'Example referral reason', 'follow_up_date': '2026-10-09'})
    return path


def snapshot(path):
    connection = connect_database(path)
    try:
        return read_tables(connection)
    finally:
        connection.close()


def test_passport_excludes_unfinished_visits(case, tmp_path):
    from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService
    UnfinishedVisitService(case).save({'name': ['Unrelated Partial Demo'], 'medications.0.name': ['Private partial text']})
    content = PassportService(case).export('SR-CASE-001')
    with ZipFile(BytesIO(content)) as archive:
        tables = json.loads(archive.read('passport.json'))['tables']
    assert tables['visit_drafts'] == tables['visit_draft_fields'] == []
    assert b'Private partial text' not in json.dumps(tables).encode()
    receiver = tmp_path / 'receiver.sqlite'
    SQLiteRepository(receiver)
    imported = PassportService(receiver).import_passport(content, confirmed=True)
    assert BundleService(SQLiteRepository(receiver)).get_bundle(imported).total_cost_pkr() == Decimal('2500.10')
    assert UnfinishedVisitService(receiver).list() == []


def test_old_schema_three_passport_remains_importable(case, tmp_path):
    import hashlib
    with ZipFile(BytesIO(PassportService(case).export('SR-CASE-001'))) as original:
        members = {name: original.read(name) for name in original.namelist() if name != 'manifest.json'}
    document = json.loads(members['passport.json'])
    tables = document['tables']
    del tables['visit_drafts']; del tables['visit_draft_fields']
    tables['schema_version'] = [row for row in tables['schema_version'] if row['version'] <= 3]
    members['passport.json'] = json.dumps(document).encode()
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps({name: hashlib.sha256(value).hexdigest() for name, value in members.items()}))
        for name, value in members.items():
            archive.writestr(name, value)
    receiver = tmp_path / 'receiver.sqlite'
    SQLiteRepository(receiver)
    assert PassportService(receiver).import_passport(output.getvalue(), confirmed=True)


def test_context_preserves_text_and_survives_backup(case, tmp_path):
    context = ReferralContextService(case).get('SR-CASE-001')
    assert context['medical_history'] == 'Example history'
    assert context['allergies'] == ''
    backup = DatasetBackupService(case)
    name = backup.create(tmp_path / 'exports')
    destination = tmp_path / 'restored'
    backup.restore(tmp_path / 'exports' / name, destination, confirmed=True)
    assert ReferralContextService(destination / 'sehatraasta.sqlite').get('SR-CASE-001') == context


def test_context_survives_later_record_edits_and_second_referral(case):
    expected = ReferralContextService(case).get('SR-CASE-001')
    service = BundleService(SQLiteRepository(case))
    service.set_category_review('SR-CASE-001', ReviewCategory.IMAGING_REPORTS,
        PresenceState.PENDING, 'Example reviewer', datetime(2026, 10, 2), 'Awaited')
    service.add_medication('SR-CASE-001', 'MD-001', 'Example medicine', '10 mg',
        '1 tablet', '', 'As recorded', 'As recorded', '', '')
    service.create_bundle('PK-001', 'SR-CASE-002', datetime(2026, 10, 2),
        'Example clinic', 'Another department', ReferralStatus.DRAFT)
    assert ReferralContextService(case).get('SR-CASE-001') == expected
    assert ReferralContextService(case).get('SR-CASE-002')['medical_history'] == ''
    with ZipFile(BytesIO(PassportService(case).export('SR-CASE-001'))) as archive:
        context = json.loads(archive.read('passport.json'))['tables']['referral_context'][0]
    assert context['medical_history'] == expected['medical_history']
    assert len(service.get_patient('PK-001').referrals) == 2


@pytest.mark.parametrize('values', [{'follow_up_date': 'bad'}, {'medical_history': 4}, {'allergies': 'x' * 4001}, {'department': '\x00'}])
def test_invalid_context_does_not_change_data(case, values):
    before = snapshot(case)
    with pytest.raises((ValueError, TypeError)):
        ReferralContextService(case).save('SR-CASE-001', values)
    assert snapshot(case) == before


def test_passport_transfer_keeps_existing_records_and_qr(case, tmp_path):
    receiving = tmp_path / 'receiver' / 'records.sqlite'
    existing = make_case(receiving)  # Deliberately colliding sender IDs.
    payload = QRService(case).for_bundle('SR-CASE-001')
    content = PassportService(case).export('SR-CASE-001')
    transfer = PassportService(receiving)
    assert transfer.preview(content)['patient'] == 'Amina Example'
    before = existing.get_bundle('SR-CASE-001')
    imported = transfer.import_passport(content, confirmed=True)
    assert imported != 'SR-CASE-001'
    assert existing.get_bundle('SR-CASE-001') == before
    assert len(existing.list_patients()) == 2
    assert QRService(receiving).lookup(payload) == imported
    assert existing.total_cost_pkr(imported) == Decimal('2500.10')
    assert ReferralContextService(receiving).get(imported)['department'] == 'Orthopaedics'
    assert QRService(receiving).lookup_short(json.loads(payload)['id'][:12]) == imported
    before_duplicate = snapshot(receiving)
    with pytest.raises(ValueError, match='already imported'):
        transfer.import_passport(content, confirmed=True)
    assert snapshot(receiving) == before_duplicate


def test_scoped_passport_excludes_other_patient(case):
    make_case(case, 'PK-002', 'SR-OTHER-001')
    with ZipFile(BytesIO(PassportService(case).export('SR-CASE-001'))) as archive:
        tables = json.loads(archive.read('passport.json'))['tables']
    assert len(tables['patients']) == len(tables['referral_bundles']) == 1
    assert tables['patients'][0]['patient_id'] == 'PK-001'


def test_bad_passport_leaves_storage_unchanged(case):
    before = snapshot(case)
    with pytest.raises(ValueError, match='invalid passport'):
        PassportService(case).import_passport(b'bad archive', confirmed=True)
    assert snapshot(case) == before


def test_tampered_passport_rejected(case):
    original = PassportService(case).export('SR-CASE-001')
    output = BytesIO()
    with ZipFile(BytesIO(original)) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for name in source.namelist():
            target.writestr(name, b'{}' if name == 'passport.json' else source.read(name))
    with pytest.raises(ValueError):
        PassportService(case).preview(output.getvalue())


def test_import_requires_confirmation(case):
    before = snapshot(case)
    with pytest.raises(ValueError, match='confirm'):
        PassportService(case).import_passport(PassportService(case).export('SR-CASE-001'))
    # Export may create a QR token, but import added no patient or referral.
    assert snapshot(case)['patients'] == before['patients']


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_new_pages_and_print_are_translated(case, language):
    app = create_app({'TESTING': True, 'DATABASE': case, 'ANDROID_APP': True, 'SECRET_KEY': 'example'})
    client = app.test_client()
    for path in ['/lookup', '/passports/import', '/bundles/SR-CASE-001/context', '/bundles/SR-CASE-001/print']:
        response = client.get(path + '?lang=' + language)
        assert response.status_code == 200
        assert b'[Missing translation:' not in response.data
    assert b'data-scan-camera' in client.get('/lookup').data
    printed = client.get('/bundles/SR-CASE-001/print').data
    assert b'Example history' in printed and b'Orthopaedics' in printed


def test_legacy_backup_restores_with_empty_context(case, tmp_path):
    backup = DatasetBackupService(case)
    folder = tmp_path / 'exports'
    name = backup.create(folder)
    old = tmp_path / 'old.zip'
    import hashlib
    with ZipFile(folder / name) as original, ZipFile(old, 'w', ZIP_DEFLATED) as target:
        members = {name: original.read(name) for name in original.namelist() if name != 'manifest.json'}
        data = json.loads(members['dataset.json'])
        del data['tables']['referral_context']
        del data['tables']['visit_drafts']
        del data['tables']['visit_draft_fields']
        data['tables']['schema_version'] = [row for row in data['tables']['schema_version'] if row['version'] < 3]
        members['dataset.json'] = json.dumps(data).encode()
        target.writestr('manifest.json', json.dumps({name: hashlib.sha256(value).hexdigest() for name, value in members.items()}))
        for name, value in members.items():
            target.writestr(name, value)
    backup.restore(old, tmp_path / 'restored', confirmed=True)
    restored = tmp_path / 'restored' / 'sehatraasta.sqlite'
    assert ReferralContextService(restored).get('SR-CASE-001')['medical_history'] == ''
    assert BundleService(SQLiteRepository(restored)).total_cost_pkr('SR-CASE-001') == Decimal('2500.10')


def attach_example(case, tmp_path):
    source = tmp_path / 'example.pdf'
    source.write_bytes(b'%PDF-1.4\nPublic synthetic signature fixture\n%%EOF')
    service = BundleService(SQLiteRepository(case))
    service.add_order('SR-CASE-001', 'Example X-ray', date(2026, 10, 2), 'Example clinic', InvestigationOrderStatus.ORDERED)
    FileService(case).import_file('SR-CASE-001', 'AT-001', source, AttachmentCategory.OTHER,
        date(2026, 10, 2), Provenance(ProvenanceType.NOT_SUPPLIED), order_id=1)
    return source.read_bytes()


def test_document_bytes_and_order_links_transfer(case, tmp_path):
    content = attach_example(case, tmp_path)
    receiver = tmp_path / 'receiver' / 'records.sqlite'
    make_case(receiver)
    receiving = BundleService(SQLiteRepository(receiver))
    receiving.add_order('SR-CASE-001', 'Unrelated existing order', date(2026, 10, 2), 'Example source', InvestigationOrderStatus.ORDERED)
    imported = PassportService(receiver).import_passport(PassportService(case).export('SR-CASE-001'), confirmed=True)
    tables = snapshot(receiver)
    managed = next(row for row in tables['managed_attachments'] if row['bundle_id'] == imported)
    order = next(row for row in tables['investigation_orders'] if row['bundle_id'] == imported)
    assert managed['order_id'] == order['order_id'] == 2
    assert FileService(receiver).retrieve(managed['attachment_id'])[0] == content
    assert managed['stored_name'] != snapshot(case)['managed_attachments'][0]['stored_name']


def test_mid_import_failure_rolls_back_rows_and_files(case, tmp_path, monkeypatch):
    attach_example(case, tmp_path)
    content = PassportService(case).export('SR-CASE-001')
    receiver = tmp_path / 'receiver' / 'records.sqlite'
    make_case(receiver)
    class InterruptingConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            if statement.startswith('INSERT INTO "referral_bundles"'):
                assert self.execute('SELECT COUNT(*) FROM patients').fetchone()[0] == 2
                assert len(list(FileService(receiver).root.glob('*'))) == 1
                raise sqlite3.IntegrityError('intentional test interruption')
            return super().execute(statement, parameters)
    def interrupted_connection(path):
        connection = sqlite3.connect(path, factory=InterruptingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection
    monkeypatch.setattr('sehatraasta.services.passport_service.connect_database', interrupted_connection)
    before = snapshot(receiver)
    with pytest.raises(sqlite3.Error):
        PassportService(receiver).import_passport(content, confirmed=True)
    assert snapshot(receiver) == before
    assert list(FileService(receiver).root.glob('*')) == []


def csrf(response):
    import re
    return re.search(r'name="csrf" value="([^"]+)"', response.data.decode()).group(1)


def test_import_checks_file_before_confirmation_and_retains_existing(case, tmp_path):
    receiver = tmp_path / 'receiver' / 'records.sqlite'
    make_case(receiver)
    app = create_app({'TESTING': True, 'DATABASE': receiver, 'SECRET_KEY': 'example'})
    client = app.test_client()
    content = PassportService(case).export('SR-CASE-001')
    path = '/passports/import'
    response = client.get(path)
    data = {'csrf': csrf(response), 'intent': 'import', 'archive': (BytesIO(content), 'passport.zip')}
    unchecked = client.post(path, data=data)
    assert unchecked.status_code == 422
    assert len(SQLiteRepository(receiver).list_patients()) == 1
    checked = client.post(path, data={'csrf': csrf(unchecked), 'intent': 'check', 'archive': (BytesIO(content), 'passport.zip')})
    assert checked.status_code == 200 and b'Amina Example' in checked.data
    imported = client.post(path, data={'csrf': csrf(checked), 'intent': 'import', 'archive': (BytesIO(content), 'passport.zip')})
    assert imported.status_code == 303
    assert len(SQLiteRepository(receiver).list_patients()) == 2
    assert client.get(imported.location).status_code == 200


def test_export_requires_permission(case):
    client = create_app({'TESTING': True, 'DATABASE': case, 'SECRET_KEY': 'example'}).test_client()
    page = client.get('/bundles/SR-CASE-001')
    import re
    token = re.search(r'action="/bundles/SR-CASE-001/passport[^\"]*"><input type="hidden" name="csrf" value="([^"]+)"', page.data.decode()).group(1)
    assert client.post('/bundles/SR-CASE-001/passport', data={'csrf': token}).status_code == 422


@pytest.mark.parametrize('replacement', [None, [], {'patients': []}])
def test_invalid_archive_shapes_are_safe_errors(case, replacement):
    import hashlib
    content = PassportService(case).export('SR-CASE-001')
    output = BytesIO()
    with ZipFile(BytesIO(content)) as original, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        members = {name: original.read(name) for name in original.namelist() if name != 'manifest.json'}
        document = json.loads(members['passport.json'])
        document['tables'] = replacement
        members['passport.json'] = json.dumps(document).encode()
        target.writestr('manifest.json', json.dumps({name: hashlib.sha256(value).hexdigest() for name, value in members.items()}))
        for name, value in members.items():
            target.writestr(name, value)
    before = snapshot(case)
    with pytest.raises(ValueError, match='invalid passport file'):
        PassportService(case).import_passport(output.getvalue(), confirmed=True)
    assert snapshot(case) == before
