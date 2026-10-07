from datetime import datetime, date
from decimal import Decimal
from io import BytesIO
import re

import pytest
from test_routes import app, client, post
from sehatraasta.domain import Language, ReferralStatus, CostCategory
from sehatraasta.services.doctor_report_service import DoctorReportService
from sehatraasta.services.visit_deletion_service import VisitDeletionService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.services.qr_service import QRService
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError


def visits(app):
    service = app.extensions['bundles']
    service.create_bundle('PK-001', 'RB-002', datetime(2026, 9, 1), 'Earlier Lahore clinic', '', ReferralStatus.DRAFT)
    service.create_bundle('PK-001', 'RB-003', datetime(2026, 10, 1), 'Karachi specialist', '', ReferralStatus.DRAFT)
    service.create_patient('PK-002', 'Other Person', 1990, Language.ENGLISH)
    service.create_bundle('PK-002', 'RB-004', datetime(2026, 10, 1), 'Other visit', '', ReferralStatus.DRAFT)
    return service


def confirmation(client, identifier='SR-DEMO-001'):
    page = client.get(f'/bundles/{identifier}/delete')
    return {key: re.search(fr'name="{key}" value="([^"]+)"', page.text)[1] for key in ('csrf', 'revision')}


def test_print_is_standalone_white_and_omits_blanks_and_ids(app, client):
    service = app.extensions['bundles']
    service.add_medication('SR-DEMO-001', 'MD-001', 'Fictional medicine', '10 mg', '1 tablet', '', 'Once a day', '5 days', '', 'source not supplied')
    ReferralContextService(app.config['DATABASE']).save('SR-DEMO-001', {'medical_history':'Reported history only'})
    page = client.get('/bundles/SR-DEMO-001/print').text
    assert 'Reported history only' in page and 'Fictional medicine' in page
    for forbidden in ('Not recorded', 'No records', 'source not supplied', 'MD-001', 'masthead', 'sidebar', 'site-footer', 'field.allergies'):
        assert forbidden not in page
    assert 'PK-001' not in re.sub('<[^>]+>', '', page)
    assert 'doctor-report.css' in page and 'doctor-report.js' in page
    assert 'Find this saved visit' in page
    assert 'omitted field is not a negative clinical finding' in page
    assert 'Medicine name' in page and 'Display name' not in page
    assert 'Prepared on' in page and 'continuation-identity' in page


def test_selected_visits_chronological_and_patient_scoped(app, client):
    visits(app)
    page = client.get('/patients/PK-001/print?preview=yes&visit=RB-003&visit=SR-DEMO-001&visit=RB-002').text
    assert page.index('Earlier Lahore clinic') < page.index('Demo BHU') < page.index('Karachi specialist')
    assert 'Other visit' not in page
    response = client.get('/patients/PK-001/print?preview=yes&visit=RB-004')
    assert response.status_code == 422 and 'Other Person' not in response.text


@pytest.mark.parametrize('query', ['preview=yes', 'preview=yes&visit=SR-DEMO-001&visit=SR-DEMO-001', 'preview=yes&visit=missing'])
def test_invalid_selection_has_safe_message(client, query):
    response = client.get('/patients/PK-001/print?'+query)
    assert response.status_code == 422 and 'Check your selection' in response.text


def test_costs_are_opt_in(app, client):
    app.extensions['bundles'].add_cost('SR-DEMO-001', 'CO-001', CostCategory.TRAVEL, Decimal('2500.10'), date(2026, 9, 21), 'Demo interview')
    assert '2,500.10' not in client.get('/bundles/SR-DEMO-001/print').text
    assert '2,500.10' in client.get('/patients/PK-001/print?preview=yes&visit=SR-DEMO-001&costs=yes').text


def upload(client):
    response = post(client, '/bundles/SR-DEMO-001/attachments/new', dict(file=(BytesIO(b'%PDF-1.4\nfixture'), 'report.pdf'), category='OTHER', date='2026-09-21', source_type='NOT_SUPPLIED'))
    assert response.status_code == 303


def test_print_documents_checked_and_content_private(app, client):
    upload(client)
    identifier = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    page = client.get('/bundles/SR-DEMO-001/print')
    assert 'data-document="application/pdf"' in page.text
    response = client.get(f'/attachments/{identifier}/content')
    assert response.data == b'%PDF-1.4\nfixture'
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'attachment;' not in response.headers.get('Content-Disposition','')
    with connect_database(app.config['DATABASE']) as connection:
        stored = connection.execute('SELECT stored_name FROM managed_attachments').fetchone()[0]
    (FileService(app.config['DATABASE']).root/stored).unlink()
    assert client.get('/bundles/SR-DEMO-001/print').status_code != 200
    response = client.get('/patients/PK-001/print?preview=yes&visit=SR-DEMO-001')
    assert response.status_code == 200 and 'data-document=' not in response.text


@pytest.mark.parametrize('language', ['en','ur','ps'])
def test_sharing_and_report_translated(client, language):
    for path in ('/sharing', '/patients/PK-001/print', '/bundles/SR-DEMO-001/print'):
        page = client.get(path+'?lang='+language)
        assert page.status_code == 200 and '[Missing translation:' not in page.text


def test_names_visible_ids_only_in_machine_references(client):
    for path in ('/patients', '/patients/PK-001', '/bundles/SR-DEMO-001', '/bundles', '/patients/PK-001/delete'):
        page = client.get(path).text
        text = re.sub('<[^>]+>', '', page)
        assert 'PK-001' not in text and 'SR-DEMO-001' not in text
        assert 'Amina Demo' in text


def test_removes_just_one_visit_files_tokens_and_links(app, client):
    service = visits(app)
    upload(client)
    QRService(app.config['DATABASE']).for_bundle('SR-DEMO-001')
    response = client.post('/bundles/SR-DEMO-001/delete', data={**confirmation(client), 'confirm':'yes'})
    assert response.status_code == 303
    assert service.get_patient('PK-001').name == 'Amina Demo'
    assert len(service.get_patient('PK-001').referrals) == 2
    assert service.get_bundle('RB-004').source_facility == 'Other visit'
    assert client.get('/bundles/SR-DEMO-001').status_code == 404
    from sehatraasta.services.recovery_service import RecoveryService
    recovery = RecoveryService(app.config['DATABASE'])
    assert len(list(FileService(app.config['DATABASE']).root.iterdir())) == 1  # retained for recovery
    assert recovery.permanent(recovery.list()[0]['item_id']) == 0
    assert list(FileService(app.config['DATABASE']).root.iterdir()) == []
    with connect_database(app.config['DATABASE']) as connection:
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('SELECT COUNT(*) FROM bundle_tokens WHERE bundle_id=?',('SR-DEMO-001',)).fetchone()[0] == 0


def test_delete_requires_confirmation_csrf_and_fresh_revision(app, client):
    data = confirmation(client)
    assert client.post('/bundles/SR-DEMO-001/delete', data={'confirm':'yes'}).status_code == 400
    assert client.post('/bundles/SR-DEMO-001/delete', data=data).status_code == 422
    visits(app)
    assert client.post('/bundles/SR-DEMO-001/delete', data={**data,'confirm':'yes'}).status_code == 409
    assert client.get('/bundles/SR-DEMO-001').status_code == 200


def test_delete_database_error_rolls_back_and_preserves_bytes(app, client):
    upload(client)
    database = app.config['DATABASE']
    with connect_database(database) as connection:
        connection.execute("CREATE TRIGGER stop_visit_delete BEFORE DELETE ON referral_bundles BEGIN SELECT RAISE(ABORT,'blocked'); END")
    revision = app.extensions['bundles'].get_patient('PK-001')._storage_revision
    with pytest.raises(StorageError):
        VisitDeletionService(database).delete('SR-DEMO-001', revision)
    identifier = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    assert FileService(database).retrieve(identifier)[0] == b'%PDF-1.4\nfixture'


def test_pdf_assets_bundled_and_eval_disabled(client):
    for path in ('pdf.min.mjs','pdf.worker.min.mjs','LICENSE'):
        assert client.get('/static/vendor/pdfjs/'+path).status_code == 200
    js = client.get('/static/doctor-report.js').text
    assert 'isEvalSupported:false' in js and 'https://' not in js


def test_native_pdf_pages_are_private_and_fail_safely(app, client):
    upload(client)
    identifier = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    path = f'/attachments/{identifier}/print-pages'
    assert client.get(path).status_code == 404
    received = []
    def renderer(content):
        received.append(content)
        return ['data:image/png;base64,fixture']
    app.config['RENDER_REPORT_PDF'] = renderer
    response = client.get(path)
    assert response.status_code == 200
    assert response.json['pages'] == ['data:image/png;base64,fixture']
    assert received == [b'%PDF-1.4\nfixture']
    assert response.headers['Cache-Control'] == 'no-store'
    def broken(content):
        raise ValueError('private report text must not leak')
    app.config['RENDER_REPORT_PDF'] = broken
    response = client.get(path)
    assert response.status_code == 422
    assert response.json == {'error':'report.failed'}
    assert 'private report text' not in response.text


def test_native_pdf_pages_reject_image(app, client):
    from PIL import Image
    content = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(content, format='PNG')
    content.seek(0)
    assert post(client, '/bundles/SR-DEMO-001/attachments/new', dict(file=(content,'image.png'), category='OTHER', date='2026-09-21',source_type='NOT_SUPPLIED')).status_code == 303
    identifier = app.extensions['bundles'].get_bundle('SR-DEMO-001').attachments[0].ID
    app.config['RENDER_REPORT_PDF'] = lambda content: pytest.fail('image sent to PDF renderer')
    assert client.get(f'/attachments/{identifier}/print-pages').status_code == 422


def test_visit_cleanup_failure_can_be_reconciled(app, client, monkeypatch):
    from pathlib import Path
    upload(client)
    database = app.config['DATABASE']
    files = FileService(database)
    original = Path.unlink
    def blocked(path, *args, **kwargs):
        if path.parent == files.root:
            raise PermissionError('locked file')
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', blocked)
        revision = app.extensions['bundles'].get_patient('PK-001')._storage_revision
        assert VisitDeletionService(database).delete('SR-DEMO-001', revision) == 1
    assert app.extensions['bundles'].get_patient('PK-001').referrals == []
    assert len(list(files.root.iterdir())) == 1
    assert files.reconcile() == 1
    assert list(files.root.iterdir()) == []


def test_report_print_css_cannot_inherit_mobile_padding(client):
    css = client.get('/static/doctor-report.css').text
    assert '@media screen and (max-width:480px)' in css
    assert '@media(max-width:480px)' not in css
    assert 'background:#fff!important' in css
    assert 'position:fixed' in css


def test_test_records_have_specific_labels(app, client):
    from sehatraasta.domain import InvestigationOrderStatus
    app.extensions['bundles'].add_order('SR-DEMO-001', 'Fictional X-ray', date(2026, 10, 5), 'Demo clinic', InvestigationOrderStatus.ORDERED)
    page = client.get('/bundles/SR-DEMO-001/print').text
    assert 'Test name' in page and 'Fictional X-ray' in page
    assert 'Display name' not in page
