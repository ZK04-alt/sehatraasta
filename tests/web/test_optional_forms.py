import pytest
from decimal import Decimal

from sehatraasta.storage import SQLiteRepository
from test_intake import app, values, row, post, csrf
from io import BytesIO


MEDICINE = dict(name='Fictional medicine', strength='10 mg', dose='1 tablet',
                frequency='Once a day', duration='5 days')
RECORDS = {
    'medications': MEDICINE,
    'orders': dict(name='Demo blood test', date='2026-09-22', workflow_status='ORDERED'),
    'results': dict(name='Demo blood result', date='2026-09-22'),
    'imaging': dict(modality='X-ray', body_part='Demo part', date='2026-09-22', facility='Demo centre'),
    'instructions': dict(category='Follow-up', language='ENGLISH', date='2026-09-22'),
    'costs': dict(category='TRAVEL', amount='2500.10', date='2026-09-22'),
}


def test_every_section_can_be_empty(app):
    data = values()
    for section in RECORDS:
        row(data, section, 0, {})
    response = post(app.test_client(), data)
    assert response.status_code == 303
    bundle = SQLiteRepository(app.config['DATABASE']).list_patients()[-1].referrals[0]
    for name in ('medication_item', 'investigation_orders', 'diagnostic_results',
                 'imaging_items', 'instructions', 'cost_entries'):
        assert getattr(bundle, name) == []


def test_all_optional_fields_can_be_omitted_and_survive_restart(app):
    data = values()
    for section, fields in RECORDS.items():
        row(data, section, 0, fields)
    response = post(app.test_client(), data)
    assert response.status_code == 303
    patient = next(p for p in SQLiteRepository(app.config['DATABASE']).list_patients() if p.ID != 'PK-001')
    bundle = patient.referrals[0]
    medicine = bundle.medication_item[0]
    assert medicine.route == medicine.instructions == ''
    assert medicine.source == bundle.investigation_orders[0].source == 'source not supplied'
    assert bundle.diagnostic_results[0].interpretation == ''
    assert bundle.imaging_items[0].report == ''
    assert bundle.instructions[0].text == ''
    cost = bundle.cost_entries[0]
    assert cost.source == cost.source_identifier == 'source not supplied'
    assert cost.source_type == 'not supplied'
    assert bundle.total_cost_pkr() == Decimal('2500.10')


@pytest.mark.parametrize('section,fields', RECORDS.items())
def test_partial_rows_require_remaining_essential_fields_and_save_nothing(app, section, fields):
    data = values()
    name = next(iter(fields))
    row(data, section, 0, {name: fields[name]})
    response = post(app.test_client(), data)
    assert response.status_code == 422
    assert b'error-summary' in response.data
    assert app.extensions['bundles'].list_bundles() == []


@pytest.mark.parametrize('section,fields', RECORDS.items())
def test_single_record_pages_accept_missing_optional_fields(app, section, fields):
    client = app.test_client()
    created = post(client, values('existing'))
    bundle_path = created.location.split('?')[0]
    path = bundle_path + '/' + section + '/new'
    data = dict(fields, csrf=csrf(client.get(path)))
    saved = client.post(path, data=data)
    assert saved.status_code == 303


@pytest.mark.parametrize('name', ['strength', 'dose', 'route', 'frequency', 'duration'])
def test_medicine_custom_choices_are_stored_exactly(app, name):
    client = app.test_client()
    data = values()
    fields = dict(MEDICINE)
    fields[name] = '__custom__'
    fields[name + '__custom'] = '  Original مثال ' + name
    row(data, 'medications', 0, fields)
    result = post(client, data)
    assert result.status_code == 303
    bundle_id = result.location.split('/bundles/')[1].split('?')[0]
    item = app.extensions['bundles'].get_bundle(bundle_id).medication_item[0]
    assert getattr(item, name) == '  Original مثال ' + name


def test_custom_choice_alone_is_not_silently_discarded(app):
    data = values()
    row(data, 'medications', 0, {'route': '__custom__'})
    result = post(app.test_client(), data)
    assert result.status_code == 422
    assert b'href="#medications-0-name"' in result.data
    assert app.extensions['bundles'].list_bundles() == []


def test_custom_values_survive_validation_and_language_change(app):
    client = app.test_client()
    data = values()
    row(data, 'imaging', 0, dict(modality='__custom__', modality__custom='Original custom مثال'))
    response = post(client, data)
    assert response.status_code == 422
    assert 'value="Original custom مثال"' in response.data.decode()
    for key, value in dict(csrf=csrf(response), lang='ur', intent='language', had_errors='1').items():
        data[key] = value
    response = client.post('/bundles/new', data=data)
    assert response.status_code == 200
    assert 'value="Original custom مثال"' in response.data.decode()


@pytest.mark.parametrize('source,reference', [('', ''), ('Demo clinic', ''), ('', 'DOC-1'), ('Demo clinic', 'DOC-1')])
def test_attachment_source_type_and_details_are_independently_optional(app, source, reference):
    client = app.test_client()
    bundle_path = post(client, values('existing')).location.split('?')[0]
    path = bundle_path + '/attachments/new'
    response = client.post(path, data=dict(csrf=csrf(client.get(path)),
        file=(BytesIO(b'%PDF-1.4\nSynthetic only'), 'demo.pdf'),
        category='OTHER', date='2026-09-22', synthetic='yes',
        source=source, source_identifier=reference))
    assert response.status_code == 303
    bundle_id = bundle_path.rsplit('/', 1)[1]
    saved = app.extensions['bundles'].get_bundle(bundle_id).attachments[0]
    assert saved.source == (source or 'source not supplied')


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_year_picker_and_choices_have_labels_and_no_missing_translations(app, language):
    page = app.test_client().get('/bundles/new?lang=' + language)
    assert page.status_code == 200
    assert b'data-year-picker' in page.data
    assert b'name="birth_year"' in page.data
    assert b'name="date_of_birth"' not in page.data
    assert b'[Missing translation:' not in page.data
    assert b'data-preset' in page.data
    assert b'optional-tag' in page.data


def test_optional_details_and_exact_cost_survive_full_backup_restore(app, tmp_path):
    from sehatraasta.services.dataset_backup import DatasetBackupService
    from sehatraasta.services.file_service import FileService
    from sehatraasta.services.bundle_service import BundleService

    client = app.test_client()
    data = values()
    for section, fields in RECORDS.items():
        row(data, section, 0, fields)
    response = post(client, data)
    assert response.status_code == 303
    bundle_path = response.location.split('?')[0]
    bundle_id = bundle_path.rsplit('/', 1)[1]
    path = bundle_path + '/attachments/new'
    content = b'%PDF-1.4\nSynthetic backup regression only'
    upload = client.post(path, data=dict(csrf=csrf(client.get(path)),
        file=(BytesIO(content), 'demo.pdf'), category='OTHER', date='2026-09-22',
        synthetic='yes', source='Demo clinic', source_identifier=''))
    assert upload.status_code == 303

    backup = DatasetBackupService(app.config['DATABASE'])
    folder = tmp_path / 'backup-check'
    name = backup.create(folder)
    summary = backup.dry_run(folder / name)
    assert summary['total_paisa'] == 250010
    destination = tmp_path / 'restored-check'
    assert backup.restore(folder / name, destination, True) == summary
    service = BundleService(SQLiteRepository(destination / 'sehatraasta.sqlite'))
    restored = service.get_bundle(bundle_id)
    assert restored.total_cost_pkr() == Decimal('2500.10')
    assert restored.cost_entries[0].source_type == 'not supplied'
    assert restored.medication_item[0].route == restored.medication_item[0].instructions == ''
    assert restored.instructions[0].text == restored.imaging_items[0].report == ''
    attachment = restored.attachments[0]
    assert attachment.source == 'Demo clinic'
    assert FileService(destination / 'sehatraasta.sqlite').retrieve(attachment.ID)[0] == content
