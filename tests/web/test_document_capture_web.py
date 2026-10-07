from io import BytesIO
import re
import pytest

from sehatraasta.domain import Language
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.web import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'DATABASE': tmp_path / 'data.sqlite', 'SECRET_KEY': 'fictional-test'})


def submit(client, values):
    page = client.get('/documents/new?lang=en')
    assert page.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    return client.post('/documents/new', data={'csrf': csrf, 'capture': 'paper', 'lang': 'en',
        'mode': 'new', 'medical_date_kind': 'unknown', **values})


def test_document_only_web_save_has_no_required_reconstruction(app):
    client = app.test_client()
    response = submit(client, {'name': 'Fictional caregiver',
        'file': (BytesIO(b'%PDF-1.4\n% fictional-only'), 'fictional-paper.pdf')})
    assert response.status_code == 303
    detail = client.get(response.location)
    assert 'Fictional caregiver' in detail.text
    assert 'Date not known' in detail.text
    assert 'fictional-paper.pdf' in detail.text
    assert 'None' not in detail.text


def test_capture_context_and_validation_do_not_lose_typed_work(app):
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    service.create_patient('PK-001', 'Fictional selected patient', None, Language.ENGLISH)
    client = app.test_client()
    page = client.get('/documents/new?patient_id=PK-001')
    assert page.status_code == 200
    assert 'Fictional selected patient' in page.text
    assert 'value="PK-001" selected' in page.text
    response = submit(client, {'mode': 'existing', 'patient_id': 'PK-001',
        'medical_date_kind': 'exact', 'medical_date_value': '2026-02-29',
        'source_facility': 'Fictional supplied clinic',
        'file': (BytesIO(b'%PDF-1.4\n% fictional-only'), 'fictional-paper.pdf')})
    assert response.status_code == 422
    assert 'Fictional supplied clinic' in response.text
    assert '2026-02-29' in response.text
    assert 'Fictional selected patient' in response.text
    assert service.list_bundles() == []


def test_supplied_precision_and_saved_time_are_separate_in_every_display(app):
    client = app.test_client()
    response = submit(client, {'name': 'Fictional historical paper',
        'medical_date_kind': 'approximate', 'medical_date_value': '1998-07',
        'file': (BytesIO(b'%PDF-1.4\n% fictional-only'), 'fictional-old-paper.pdf')})
    assert response.status_code == 303
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    patient, visit = service.list_bundles()[0]
    for url in ['/', f'/patients/{patient.ID}', response.location,
                f'/patients/{patient.ID}/print', f'/patients/{patient.ID}/print?preview=yes&visit={visit.ID}',
                f'/bundles/{visit.ID}/print']:
        page = client.get(url)
        assert page.status_code == 200
        assert 'Approximate date: 1998-07' in page.text
        assert '1998-07-01' not in page.text
        assert 'None' not in page.text
    detail = client.get(response.location)
    assert 'Saved on this device' in detail.text


def test_paper_draft_resumes_right_form_and_keeps_typed_fields(app):
    client = app.test_client()
    page = client.get('/documents/new')
    token = re.search(r'data-autosave-token="([^"]+)"', page.text)[1]
    response = client.post('/visits/unfinished', data={'csrf': token, 'capture': 'paper',
        'mode': 'new', 'name': 'Fictional interrupted', 'medical_date_kind': 'approximate',
        'medical_date_value': '2004', 'source_facility': 'Fictional remembered clinic'})
    assert response.status_code == 200
    assert '/documents/new?' in response.json['resume_url']
    reopened = client.get(response.json['resume_url'])
    assert 'Fictional interrupted' in reopened.text
    assert 'value="2004"' in reopened.text
    assert 'Fictional remembered clinic' in reopened.text
    queue = client.get('/')
    assert '/documents/new?' in queue.text
    assert 'Fictional interrupted' in queue.text
