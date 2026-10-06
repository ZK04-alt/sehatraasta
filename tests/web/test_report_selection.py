"""Explicit disclosure uses real stored originals, not just metadata."""
from io import BytesIO
import re
from html import unescape
from urllib.parse import urlparse, parse_qs

from PIL import Image
import pytest
from test_routes import app, client, post
from test_doctor_report import visits
from sehatraasta.services.doctor_report_service import DoctorReportService
from sehatraasta.services.file_service import FileService
from sehatraasta.storage.db import connect_database


def attach(app, client, bundle='SR-DEMO-001', name='first.png', color='red'):
    stream = BytesIO()
    Image.new('RGB', (12, 12), color).save(stream, 'PNG')
    content = stream.getvalue()
    response = post(client, f'/bundles/{bundle}/attachments/new', {
        'file': (BytesIO(content), name), 'category': 'OTHER',
        'date': '2026-09-21', 'source_type': 'NOT_SUPPLIED'})
    assert response.status_code == 303
    item = app.extensions['bundles'].get_bundle(bundle).attachments[-1]
    return item.ID, content


def test_only_explicit_original_is_included(app, client):
    first, content = attach(app, client)
    second, _ = attach(app, client, name='second.png', color='blue')
    _, records = DoctorReportService(app.extensions['bundles']).collect(
        'PK-001', ['SR-DEMO-001'], document_ids=[first])
    assert [item.ID for item in records[0]['documents']] == [first]
    assert second not in [item.ID for item in records[0]['documents']]
    assert FileService(app.config['DATABASE']).retrieve(first)[0] == content


def test_explicit_empty_selection_never_means_all(app, client):
    attach(app, client)
    _, records = DoctorReportService(app.extensions['bundles']).collect(
        'PK-001', ['SR-DEMO-001'], document_ids=[])
    assert records[0]['documents'] == []


@pytest.mark.parametrize('bundle', ['RB-002', 'RB-004'])
def test_forged_or_unselected_original_rejected_before_file_access(app, client, bundle):
    visits(app)
    identifier, _ = attach(app, client, bundle)
    with pytest.raises(ValueError, match='document not found in selected visits'):
        DoctorReportService(app.extensions['bundles']).collect(
            'PK-001', ['SR-DEMO-001'], document_ids=[identifier])
    with connect_database(app.config['DATABASE']) as connection:
        count = connection.execute("SELECT COUNT(*) FROM file_audit_events WHERE action = 'retrieve'").fetchone()[0]
    assert count == 0


@pytest.mark.parametrize('selection', [['unknown'], ['unknown', 'unknown'], ['x'] * 31])
def test_invalid_document_selection_is_rejected(app, selection):
    with pytest.raises(ValueError):
        DoctorReportService(app.extensions['bundles']).collect(
            'PK-001', ['SR-DEMO-001'], document_ids=selection)


def test_new_selector_has_explicit_unchecked_document_choices(app, client):
    identifier, _ = attach(app, client)
    page = client.get('/patients/PK-001/print').text
    assert 'name="selection" value="individual"' in page
    assert re.search(fr'name="document" value="{identifier}"[^>]*>', page)
    assert 'first.png' in page
    assert 'name="documents"' not in page
    assert ' checked' not in page


def test_preview_retains_language_cost_and_original_selection(app, client):
    identifier, _ = attach(app, client)
    query = f'selection=individual&preview=yes&visit=SR-DEMO-001&document={identifier}&costs=yes&lang=ur'
    page = client.get('/patients/PK-001/print?' + query)
    assert page.status_code == 200
    assert 'data-document="image/png"' in page.text
    assert 'selection=individual' in page.text and f'document={identifier}' in page.text
    assert 'costs=yes' in page.text and 'lang=ur' in page.text
    assert f'/attachments/{identifier}/download' in page.text


def test_missing_original_names_failure_and_preserves_choices(app, client):
    identifier, _ = attach(app, client, name='missing-report.png')
    with connect_database(app.config['DATABASE']) as connection:
        stored = connection.execute('SELECT stored_name FROM managed_attachments WHERE attachment_id = ?', (identifier,)).fetchone()[0]
    (FileService(app.config['DATABASE']).root / stored).unlink()
    page = client.get(f'/patients/PK-001/print?selection=individual&preview=yes&visit=SR-DEMO-001&document={identifier}&costs=yes&lang=en')
    assert page.status_code == 422
    assert 'missing-report.png' in re.search(r'<p role="alert".*?</p>', page.text, re.S)[0]
    assert re.search(fr'name="document" value="{identifier}"[^>]*checked', page.text)
    assert re.search(r'name="costs"[^>]*checked', page.text)
    assert str(app.config['DATABASE'].parent) not in page.text
    response = client.get('/patients/PK-001/print?selection=individual&preview=yes&visit=SR-DEMO-001')
    assert response.status_code == 200 and 'data-document=' not in response.text


def remove_original(app, identifier):
    with connect_database(app.config['DATABASE']) as connection:
        stored = connection.execute('SELECT stored_name FROM managed_attachments WHERE attachment_id = ?', (identifier,)).fetchone()[0]
    (FileService(app.config['DATABASE']).root / stored).unlink()


@pytest.mark.parametrize('path', ['/bundles/SR-DEMO-001/print',
    '/patients/PK-001/print?preview=yes&visit=SR-DEMO-001&documents=yes&costs=yes'])
def test_legacy_failure_retains_effective_original_choices(app, client, path):
    identifier, _ = attach(app, client, name='legacy-missing.png')
    remove_original(app, identifier)
    page = client.get(path)
    assert page.status_code == 422
    assert 'legacy-missing.png' in re.search(r'<p role="alert".*?</p>', page.text, re.S)[0]
    assert re.search(fr'name="document" value="{identifier}"[^>]*checked', page.text)
    assert re.search(r'name="visit" value="SR-DEMO-001"[^>]*checked', page.text)


def test_language_links_keep_all_query_choices(app, client):
    visits(app)
    first, _ = attach(app, client)
    second, _ = attach(app, client, 'RB-002', 'second.png', 'blue')
    page = client.get(f'/patients/PK-001/print?selection=individual&visit=SR-DEMO-001&visit=RB-002&document={first}&document={second}&costs=yes&lang=en').text
    link = unescape(re.search(r'href="([^"]+)" lang="ur"', page)[1])
    choices = parse_qs(urlparse(link).query)
    assert choices['visit'] == ['SR-DEMO-001', 'RB-002']
    assert choices['document'] == [first, second]
    assert choices['costs'] == ['yes'] and choices['lang'] == ['ur']


@pytest.mark.parametrize('selected_visit', ['&visit=SR-DEMO-001', ''])
def test_document_without_parent_visit_explains_recovery(app, client, selected_visit):
    visits(app)
    identifier, _ = attach(app, client, 'RB-002', 'healthy.png')
    page = client.get(f'/patients/PK-001/print?selection=individual&preview=yes{selected_visit}&document={identifier}&lang=en')
    assert page.status_code == 422
    message = re.search(r'<p role="alert".*?</p>', page.text, re.S)[0]
    assert 'Include the visit for this document' in message and 'healthy.png' in message
    assert 'Restore unavailable' not in message


def test_report_marks_entered_information_as_historical(client):
    page = client.get('/bundles/SR-DEMO-001/print?lang=en').text
    assert 'Historical entries do not confirm current treatment' in page


def test_empty_selection_has_focused_actionable_error(client):
    page = client.get('/patients/PK-001/print?preview=yes&selection=individual&lang=en')
    assert page.status_code == 422
    assert 'Choose at least one visit' in page.text
    assert 'id="errors" tabindex="-1"' in page.text
