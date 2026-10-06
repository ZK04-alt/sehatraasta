from datetime import datetime
from io import BytesIO
import re

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.qr_service import QRService
from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.web import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'instance/data.sqlite', 'SECRET_KEY': 'test-only'})
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    service.create_patient('PK-001', 'Amina Demo', 1980, Language.URDU)
    service.create_bundle('PK-001', 'SR-DEMO-001', datetime(2026, 9, 21, 9), 'Demo BHU', 'Demo District Hospital', ReferralStatus.DRAFT)
    app.extensions['bundles'] = service
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path):
    page = client.get(path)
    assert page.status_code == 200, page.data.decode()
    return re.search(r'name="csrf" value="([^"]+)"', page.data.decode())[1]


def post(client, path, data):
    return client.post(path, data={'csrf': token(client, path), **data})


PAGES = ['/', '/bundles', '/patients', '/patients/PK-001', '/patients/new', '/bundles/new',
    '/bundles/SR-DEMO-001', '/bundles/SR-DEMO-001/edit', '/bundles/SR-DEMO-001/medications/new',
    '/bundles/SR-DEMO-001/orders/new', '/bundles/SR-DEMO-001/results/new', '/bundles/SR-DEMO-001/imaging/new',
    '/bundles/SR-DEMO-001/instructions/new', '/bundles/SR-DEMO-001/costs/new', '/bundles/SR-DEMO-001/reviews',
    '/bundles/SR-DEMO-001/attachments', '/bundles/SR-DEMO-001/attachments/new', '/bundles/SR-DEMO-001/costs',
    '/bundles/SR-DEMO-001/audit', '/bundles/SR-DEMO-001/print',
    '/lookup', '/backups', '/restore', '/privacy', '/terms']


@pytest.mark.parametrize('path', PAGES)
def test_get_page(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b'/static/wordmark.svg' in response.data
    assert b'DEVELOPMENT VERSION' not in response.data
    assert b'[Missing translation:' not in response.data


@pytest.mark.parametrize('path', ['/patients/new', '/bundles/new', '/bundles/SR-DEMO-001/medications/new',
    '/bundles/SR-DEMO-001/orders/new', '/bundles/SR-DEMO-001/results/new', '/bundles/SR-DEMO-001/imaging/new',
    '/bundles/SR-DEMO-001/instructions/new', '/bundles/SR-DEMO-001/costs/new', '/bundles/SR-DEMO-001/reviews',
    '/bundles/SR-DEMO-001/attachments/new', '/restore', '/backups'])
def test_empty_forms_rejected(client, path):
    assert post(client, path, {}).status_code == 422


def test_patient_bundle_persistence_and_duplicate(client, app):
    values = dict(ID='PK-002', name='Demo مثال', birth_year='1980', language='PASHTO')
    csrf = token(client, '/patients/new')
    assert client.post('/patients/new', data=dict(values, csrf=csrf)).status_code == 303
    assert client.post('/patients/new', data=dict(values, csrf=csrf)).status_code == 409
    patient_id = app.extensions['bundles'].list_patients()[-1].ID
    assert patient_id != 'PK-002' and patient_id.startswith('PT-')
    values = dict(mode='existing', patient_id=patient_id, ID='RB-002', creation_time='2026-09-21T12:00',
                  source_facility='Demo source', destination='Demo destination', status='DRAFT')
    response = post(client, '/bundles/new', values)
    assert response.status_code == 303
    generated_id = response.headers['Location'].split('/bundles/')[1].split('?')[0]
    assert generated_id != 'RB-002'
    reopened = BundleService(SQLiteRepository(app.config['DATABASE']))
    assert reopened.get_patient(patient_id).name == 'Demo مثال'
    assert reopened.get_bundle(generated_id).destination == 'Demo destination'


def test_bundle_form_generates_id_and_preselects_patient(client, app):
    page = client.get('/bundles/new?patient_id=PK-001').data.decode()
    assert 'name="ID"' not in page
    assert '<select id="patient_id"' in page
    assert 'value="PK-001" selected' in page
    assert 'Amina Demo · 1980' in page
    assert datetime.fromisoformat(re.search(r'type="datetime-local"\s+value="([^"]+)"', page)[1])
    assert 'assigned automatically' in page


def test_generated_bundles_distinct_and_replay_rejected(client, app):
    values = dict(mode='existing', patient_id='PK-001', creation_time='2026-09-22T12:00',
                  source_facility='Demo BHU', destination='Demo Hospital', status='DRAFT')
    csrf = token(client, '/bundles/new')
    first = client.post('/bundles/new', data=dict(values, csrf=csrf))
    assert first.status_code == 303
    assert client.post('/bundles/new', data=dict(values, csrf=csrf)).status_code == 409
    second = post(client, '/bundles/new', values)
    assert second.status_code == 303
    assert first.location != second.location
    reopened = BundleService(SQLiteRepository(app.config['DATABASE']))
    assert len(reopened.get_patient('PK-001').referrals) == 3
    assert reopened.get_bundle('SR-DEMO-001').destination == 'Demo District Hospital'


def test_bundle_language_switch_and_invalid_patient_do_not_save(client, app):
    values = dict(mode='existing', patient_id='PK-999', creation_time='2026-09-22T12:00',
                  source_facility='Demo BHU', destination='Demo Hospital', status='DRAFT')
    assert post(client, '/bundles/new', values).status_code == 422
    values.update(patient_id='PK-001', intent='language', lang='ur')
    response = post(client, '/bundles/new', values)
    assert response.status_code == 200
    assert b'value="PK-001" selected' in response.data
    assert len(app.extensions['bundles'].list_bundles()) == 1


RECORDS = [
    ('medications', dict(ID='MD-001', name='Fictional item', strength='as supplied', dose='verbatim', route='verbatim', frequency='verbatim', duration='verbatim', instructions='<script>unsafe()</script> اصل متن', source='Demo sheet')),
    ('orders', dict(name='Demo X-ray', date='2026-09-21', source='Demo sheet', workflow_status='ORDERED')),
    ('results', dict(ID='DR-001', name='Demo result', date='2026-09-21', source='Demo sheet', interpretation='Fictional result')),
    ('imaging', dict(ID='IM-001', modality='Demo X-ray', body_part='Fictional', date='2026-09-21', facility='Demo BHU', report='Fictional report')),
    ('instructions', dict(category='Follow-up', language='URDU', text='اصل متن ABC-123', source='Demo sheet', date='2026-09-21')),
    ('costs', dict(ID='CE-001', category='TRAVEL', amount='2500.10', date='2026-09-21', source='demo interview response', source_type='reported', source_identifier='DEMO-INTERVIEW')),
]


@pytest.mark.parametrize('kind,values', RECORDS)
def test_record_service_operations(client, kind, values):
    assert post(client, '/bundles/SR-DEMO-001/' + kind + '/new', values).status_code == 303
    page = client.get('/bundles/SR-DEMO-001').data
    assert b'<script>unsafe' not in page
    if kind == 'medications':
        assert b'&lt;script&gt;' in page
    if kind == 'costs':
        assert b'2500.10' in page or b'2,500.10' in page


def test_reviews_keep_pending_missing_unreviewed_distinct(client, app):
    assert post(client, '/bundles/SR-DEMO-001/reviews', dict(category='IMAGING_REPORTS', state='PENDING', text='Demo reviewer', time='2026-09-21T12:00', note='Awaiting fictional report')).status_code == 303
    assert app.extensions['bundles'].get_bundle('SR-DEMO-001').category_reviews[0].state.value == 'pending'
    page = client.get('/bundles/SR-DEMO-001').data
    assert b'Pending' in page and b'Not reviewed' in page and b'Missing' in page


def test_invalid_cost_and_type_no_write(client, app):
    values = RECORDS[-1][1].copy()
    for amount in ('-1', 'NaN', '2.001', 'invalid'):
        values['amount'] = amount
        response = post(client, '/bundles/SR-DEMO-001/costs/new', values)
        assert response.status_code == 422
        assert b'href="#amount"' in response.data
    assert app.extensions['bundles'].get_bundle('SR-DEMO-001').cost_entries == []


def test_language_switch_does_not_save(client, app):
    response = post(client, '/patients/new', dict(intent='language', lang='ur', ID='PK-002', name='اصل متن', birth_year='1980', language='URDU'))
    assert response.status_code == 200 and b'dir="rtl"' in response.data
    assert 'اصل متن' in response.data.decode()
    assert len(app.extensions['bundles'].list_patients()) == 1


def test_language_switch_keeps_domain_error_and_values(client, app):
    path = '/bundles/SR-DEMO-001/costs/new'
    values = dict(RECORDS[-1][1], amount='-1')
    invalid = post(client, path, values)
    assert invalid.status_code == 422
    csrf = re.search(r'name="csrf" value="([^"]+)"', invalid.data.decode())[1]
    response = client.post(path, data=dict(values, csrf=csrf, lang='ur', intent='language', had_errors='1'))
    assert response.status_code == 200
    assert b'dir="rtl"' in response.data and b'href="#amount"' in response.data
    assert b'value="-1"' in response.data
    assert app.extensions['bundles'].get_bundle('SR-DEMO-001').cost_entries == []


def test_form_security_replay_and_expiry(client, app):
    path = '/patients/new'
    values = dict(ID='PK-002', name='Demo', birth_year='1980', language='ENGLISH')
    assert client.post(path, data=values).status_code == 400
    csrf = token(client, path)
    assert client.post(path, data=dict(values, csrf=csrf), headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post(path, data=dict(values, csrf=csrf)).status_code == 303
    assert client.post(path, data=dict(values, csrf=csrf)).status_code == 409
    app.config['FORM_MAX_AGE'] = -1
    assert post(client, path, values).status_code == 400
    assert client.get('/', headers={'Host': 'evil.example'}).status_code == 400
    assert client.get('/', environ_base={'REMOTE_ADDR': '10.0.0.2'}).status_code == 403


def test_missing_storage_and_unexpected(client, app, monkeypatch):
    assert client.get('/not-found').status_code == 404
    assert client.get('/bundles/RB-999').status_code == 404
    def broken():
        raise StorageError('private text C:/secret/file')
    monkeypatch.setattr(app.extensions['bundles'], 'list_bundles', broken)
    result = client.get('/')
    assert result.status_code == 503 and b'C:/secret' not in result.data
    def crash():
        raise RuntimeError('private trace')
    monkeypatch.setattr(app.extensions['bundles'], 'list_bundles', crash)
    result = client.get('/')
    assert result.status_code == 500 and b'private trace' not in result.data and b'Traceback' not in result.data


def test_upload_download_delete_and_reject(client, app):
    path = '/bundles/SR-DEMO-001/attachments/new'
    def values(content, name):
        return dict(ID='AT-001', file=(BytesIO(content), name), category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED', synthetic='yes')
    assert post(client, path, values(b'bad bytes', 'demo.pdf')).status_code == 422
    assert post(client, path, values(b'%PDF-1.4\nFictional document', '../demo.pdf')).status_code == 422
    content = b'%PDF-1.4\nFictional test document\n%%EOF'
    assert post(client, path, values(content, 'demo.pdf')).status_code == 303
    attachment_id = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    assert attachment_id != 'AT-001'
    attachment_path = '/attachments/' + attachment_id
    response = client.get(attachment_path + '/download')
    assert response.data == content and 'attachment;' in response.headers['Content-Disposition']
    assert b'instance' not in response.data
    assert post(client, attachment_path + '/delete', {'confirm': 'yes'}).status_code == 303
    assert client.get(attachment_path + '/download').status_code == 404


def test_print_export_lookup_backup_restore(client, app):
    assert client.get('/bundles/SR-DEMO-001/print').status_code == 200
    payload = QRService(app.config['DATABASE']).for_bundle('SR-DEMO-001')
    assert post(client, '/lookup', {'payload': payload}).status_code == 303
    assert post(client, '/lookup', {'payload': 'bad'}).status_code == 422
    page = client.get('/bundles/SR-DEMO-001').data.decode()
    csrf = re.search(r'name="csrf" value="([^"]+)"', page)[1]
    assert client.post('/bundles/SR-DEMO-001/export', data={'csrf': csrf}).status_code == 200
    archive = post(client, '/backups', {'confirm': 'yes'})
    assert archive.status_code == 200
    values = lambda intent: dict(archive=(BytesIO(archive.data), 'synthetic.zip'), intent=intent)
    assert post(client, '/restore', values('restore')).status_code == 422
    assert post(client, '/restore', values('check')).status_code == 200
    assert post(client, '/restore', values('restore')).status_code == 200
    assert len(list(app.config['DATABASE'].parent.glob('restores/*/sehatraasta.sqlite'))) == 1


def test_android_restore_reports_opened_dataset(client, app):
    activated = []
    app.config['ANDROID_APP'] = True
    app.config['ACTIVATE_RESTORE'] = activated.append
    archive = post(client, '/backups', {'confirm': 'yes'})
    assert archive.status_code == 200
    values = lambda intent: dict(archive=(BytesIO(archive.data), 'backup.zip'), intent=intent)
    assert post(client, '/restore', values('check')).status_code == 200
    response = post(client, '/restore', values('restore'))
    assert response.status_code == 200
    assert len(activated) == 1
    assert b'Backup restored and opened.' in response.data
    assert b'active dataset is unchanged' not in response.data


def test_empty_database_starts_without_fake_records(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'empty.sqlite'})
    page = app.test_client().get('/')
    assert page.status_code == 200 and b'No records yet' in page.data
    assert app.extensions['bundles'].list_patients() == []


def test_edit_preserves_original_source_and_exact_cost(client, app):
    assert post(client, '/bundles/SR-DEMO-001/costs/new', RECORDS[-1][1]).status_code == 303
    response = post(client, '/bundles/SR-DEMO-001/edit', dict(source_facility='اصل متن', destination='Demo new destination', status='READY_FOR_REVIEW'))
    assert response.status_code == 303
    item = app.extensions['bundles'].get_bundle('SR-DEMO-001')
    assert item.source_facility == 'اصل متن' and item.destination == 'Demo new destination'
    assert str(app.extensions['bundles'].total_cost_pkr(item.ID)) == '2500.10'


def test_cross_form_token_is_rejected(client, app):
    csrf = token(client, '/patients/new')
    assert client.post('/backups', data={'csrf': csrf, 'confirm': 'yes'}).status_code == 400
    assert len(app.extensions['bundles'].list_patients()) == 1


def test_failed_save_preserves_values_and_private_logs(client, app, monkeypatch):
    def fail(*args):
        raise StorageError('SECRET source text C:/private/document.pdf')
    monkeypatch.setattr(app.extensions['bundles'], 'create_patient', fail)
    response = post(client, '/patients/new', dict(ID='PK-002', name='Demo retained', birth_year='1980', language='ENGLISH'))
    assert response.status_code == 503 and b'Demo retained' in response.data
    assert b'SECRET' not in response.data
    log = (app.config['DATABASE'].parent / 'storage-errors.log').read_text()
    assert 'StorageError' in log and 'SECRET' not in log and 'document.pdf' not in log


def test_missing_attachment_is_audited_and_delete_needs_confirmation(client, app):
    from sehatraasta.services.file_service import FileService
    values = dict(ID='AT-001', file=(BytesIO(b'%PDF-1.4\nSynthetic fixture'), 'fictional.pdf'),
                  category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED', synthetic='yes')
    assert post(client, '/bundles/SR-DEMO-001/attachments/new', values).status_code == 303
    attachment_id = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    attachment_path = '/attachments/' + attachment_id
    page = client.get(attachment_path + '/delete')
    assert page.status_code == 200 and b'fictional.pdf' in page.data
    assert attachment_id.encode() not in page.data
    assert post(client, attachment_path + '/delete', {}).status_code == 422
    assert post(client, attachment_path + '/delete', {'confirm': 'no'}).status_code == 422
    root = app.config['DATABASE'].parent / 'attachments'
    next(root.glob('*.pdf')).unlink()  # Only a generated file in pytest's temporary directory.
    response = client.get(attachment_path + '/download')
    assert response.status_code == 404 and str(root).encode() not in response.data
    events = FileService(app.config['DATABASE']).audit.list_events('SR-DEMO-001')
    assert events[-1]['action'] == 'retrieve' and events[-1]['outcome'] == 'missing'
    assert post(client, attachment_path + '/delete', {'confirm': 'yes'}).status_code == 303
    assert client.get(attachment_path + '/delete').status_code == 404


def test_failed_upload_leaves_storage_unchanged(client, app):
    for size, confirmation in [(5 * 1024 * 1024 + 1, 'yes')]:
        values = dict(ID='AT-001', file=(BytesIO(b'%PDF-1.4' + b'0' * size), 'demo.pdf'),
                      category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED', synthetic=confirmation)
        assert post(client, '/bundles/SR-DEMO-001/attachments/new', values).status_code == 422
    assert app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments == []
    root = app.config['DATABASE'].parent / 'attachments'
    assert not root.exists() or not list(root.iterdir())


def test_upload_staging_uses_generated_name_and_preserves_display_name(client, app, monkeypatch):
    from pathlib import Path
    from sehatraasta.services.file_service import FileService
    original_import = FileService.import_file
    seen = []
    def inspect(service, bundle_id, attachment_id, source_path, *args, **kwargs):
        seen.append(Path(source_path))
        assert re.fullmatch(r'[a-f0-9]{32}\.pdf', Path(source_path).name)
        assert kwargs['original_name'] == 'Fictional Report.pdf'
        return original_import(service, bundle_id, attachment_id, source_path, *args, **kwargs)
    monkeypatch.setattr(FileService, 'import_file', inspect)
    values = dict(ID='AT-001', file=(BytesIO(b'%PDF-1.4\nSynthetic only'), 'Fictional Report.pdf'),
                  category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED', synthetic='yes')
    assert post(client, '/bundles/SR-DEMO-001/attachments/new', values).status_code == 303
    attachment = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0]
    assert attachment.name == 'Fictional Report.pdf'
    assert seen and not seen[0].exists()


def test_invalid_backup_leaves_active_dataset_unchanged(client, app):
    response = post(client, '/restore', {'archive': (BytesIO(b'not a zip'), 'demo.zip'), 'intent': 'check'})
    assert response.status_code == 422
    assert len(app.extensions['bundles'].list_patients()) == 1
    assert not (app.config['DATABASE'].parent / 'restores').exists()


def test_large_request_and_wrong_methods_are_safe(client, app):
    app.config['MAX_CONTENT_LENGTH'] = 1024
    assert client.post('/patients/new', data={'name': 'x' * 2000}).status_code == 413
    assert client.get('/bundles/SR-DEMO-001/export').status_code == 405
    assert client.get('/bundles/SR-DEMO-001/unknown/new').status_code == 404
    assert client.get('/static/../../SAFETY.md').status_code == 404


def test_new_factory_has_no_global_dataset_or_token_state(tmp_path):
    a = create_app({'TESTING': True, 'DATABASE': tmp_path / 'a.sqlite'})
    b = create_app({'TESTING': True, 'DATABASE': tmp_path / 'b.sqlite'})
    a.extensions['used_forms']['test'] = 1
    assert b.extensions['used_forms'] == {}
    assert a.secret_key != b.secret_key
