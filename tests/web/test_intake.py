from html.parser import HTMLParser
from io import BytesIO
import re

import pytest
from werkzeug.datastructures import MultiDict

from sehatraasta.domain import Language
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.identifiers import IDAllocator
from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.web import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'test.sqlite'})
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    service.create_patient('PK-001', 'Existing Demo', 1980, Language.URDU)
    app.extensions['bundles'] = service
    return app


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.data.decode())[1]


def values(mode='new'):
    return MultiDict(dict(mode=mode, patient_id='PK-001', name='New Demo مثال', birth_year='1980', language='URDU',
        creation_time='2026-09-22T12:00', source_facility='Demo BHU', destination='Demo Hospital', status='DRAFT'))


def row(data, section, key, fields):
    data.add(section + '.rows', str(key))
    for name, value in fields.items():
        data[section + '.' + str(key) + '.' + name] = value


def post(client, data):
    data['csrf'] = csrf(client.get('/bundles/new'))
    return client.post('/bundles/new', data=data)


class Controls(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.labels, self.values = set(), [], [], {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href', '').startswith('#'):
            self.links.append(attrs['href'][1:])
        if tag == 'label':
            self.labels.append(attrs['for'])
        if tag == 'input':
            self.values[attrs.get('name')] = attrs.get('value')


@pytest.mark.parametrize('mode', ['new', 'existing'])
def test_both_modes_create_one_referral_and_attachment_followup(app, mode):
    client = app.test_client()
    data = values(mode)
    if mode == 'existing':
        data['birth_year'] = 'inactive data must be ignored'
    row(data, 'orders', 5, dict(name='Demo test', date='2026-09-22', source='Demo source', workflow_status='ORDERED'))
    row(data, 'results', 2, dict(name='Demo result', date='2026-09-22', source='Demo source', interpretation='Demo text', order_key='5'))
    response = post(client, data)
    assert response.status_code == 303
    bundle_id = response.location.split('/bundles/')[1].split('?')[0]
    service = app.extensions['bundles']
    assert len(service.list_patients()) == (2 if mode == 'new' else 1)
    owner, bundle = service.get_bundle_owner(bundle_id)
    assert owner.name == ('New Demo مثال' if mode == 'new' else 'Existing Demo')
    assert bundle.diagnostic_results[0].investigation_order is bundle.investigation_orders[0]
    attachment_path = '/bundles/' + bundle_id + '/attachments/new'
    uploaded = client.post(attachment_path, data=dict(csrf=csrf(client.get(attachment_path)),
        file=(BytesIO(b'%PDF-1.4\nSynthetic test only'), 'demo.pdf'), category='OTHER', date='2026-09-22',
        source_type='NOT_SUPPLIED', synthetic='yes'))
    assert uploaded.status_code == 303
    attachment_id = service.get_bundle(bundle_id).attachments[0].ID
    assert re.fullmatch(r'AT-[2-9A-HJ-NP-Z]{6}', attachment_id)
    assert client.get('/attachments/' + attachment_id + '/download').status_code == 200


def test_invalid_multirow_preserves_all_sections_order_and_error_links(app):
    client = app.test_client()
    data = values('existing')
    for key, name in [(8, 'First preserved'), (2, 'Second preserved')]:
        row(data, 'medications', key, dict(name=name, strength='Original', dose='' if key == 2 else 'Original', route='Original',
            frequency='Original', duration='Original', instructions='Keep مثال <script>no</script>', source='' if key == 2 else 'Demo'))
    for section in ('orders', 'results', 'imaging', 'instructions', 'costs'):
        field = 'facility' if section == 'imaging' else 'source'
        row(data, section, 3, {field: 'Original ' + section})
    response = post(client, data)
    assert response.status_code == 422
    text = response.data.decode()
    assert 'value="existing" selected' in text
    assert text.index('value="First preserved"') < text.index('value="Second preserved"')
    assert '&lt;script&gt;no&lt;/script&gt;' in text
    assert 'href="#medications-2-dose"' in text
    assert 'id="medications-2-dose"' in text
    for section in ('orders', 'results', 'imaging', 'instructions', 'costs'):
        assert 'Original ' + section in text
    controls = Controls(text)
    assert all(target in controls.ids for target in controls.links + controls.labels)
    assert app.extensions['bundles'].list_bundles() == []
    for key, value in dict(csrf=csrf(response), lang='ps', intent='language', had_errors='1').items():
        data[key] = value
    translated = client.post('/bundles/new', data=data)
    assert translated.status_code == 200 and b'dir="rtl"' in translated.data
    assert b'href="#medications-2-dose"' in translated.data
    assert b'Second preserved' in translated.data
    assert app.extensions['bundles'].list_bundles() == []


def test_storage_failure_is_global_and_preserves_the_entire_form(app, monkeypatch):
    client = app.test_client()
    data = values()
    row(data, 'instructions', 4, dict(text='Original retained', source='Demo', category='Demo', language='URDU', date='2026-09-22'))
    data['csrf'] = csrf(client.get('/bundles/new'))
    def fail(*args):
        raise StorageError('PRIVATE source C:/secret')
    monkeypatch.setattr(IDAllocator, 'allocate', fail)
    response = client.post('/bundles/new', data=data)
    assert response.status_code == 503
    assert b'href="#intake-form"' in response.data
    assert b'Original retained' in response.data and b'PRIVATE' not in response.data
    assert b'name="ID"' not in response.data
    assert app.extensions['bundles'].list_bundles() == []


def test_parseable_business_errors_map_to_exact_fields(app):
    client = app.test_client()
    data = values()
    data['birth_year'] = '-1'
    row(data, 'costs', 0, dict(category='TRAVEL', amount='0.001', date='2026-09-22', source='Demo', source_type='receipt', source_identifier='Demo'))
    response = post(client, data)
    assert response.status_code == 422
    assert b'href="#birth_year"' in response.data
    assert b'href="#costs-0-amount"' in response.data


def test_unparseable_date_is_visible_not_silently_blank(app):
    client = app.test_client()
    data = values()
    data['creation_time'] = 'not a time'
    response = post(client, data)
    assert b'type="text"' in response.data and b'value="not a time"' in response.data


def test_storage_error_retains_unparseable_native_input_values(app, monkeypatch):
    client = app.test_client()
    data = values()
    data['creation_time'], data['birth_year'] = 'not a time', 'not a number'
    data['csrf'] = csrf(client.get('/bundles/new'))
    def unavailable(*args):
        raise StorageError('Unavailable')
    monkeypatch.setattr(BundleService, 'list_patients', unavailable)
    response = client.post('/bundles/new', data=data)
    assert response.status_code == 503
    assert b'id="creation_time" name="creation_time" type="text"' in response.data
    assert b'value="not a time"' in response.data
    assert b'id="birth_year" name="birth_year" type="text"' in response.data
    assert b'value="not a number"' in response.data


def test_nonce_replay_expiry_and_wrong_form_still_rejected(app):
    client = app.test_client()
    data = values()
    data['csrf'] = csrf(client.get('/patients/new'))
    assert client.post('/bundles/new', data=data).status_code == 400
    response = post(client, data)
    assert response.status_code == 303
    assert client.post('/bundles/new', data=data).status_code == 409
    assert len(app.extensions['bundles'].list_bundles()) == 1
    app.config['FORM_MAX_AGE'] = -1
    assert post(client, values()).status_code == 400


@pytest.mark.parametrize('path', ['/patients/new', '/bundles/new'])
def test_no_manual_identifier_input_and_no_inline_code(app, path):
    response = app.test_client().get(path)
    assert b'name="ID"' not in response.data
    assert b'<script>' not in response.data and b'<style>' not in response.data
    assert b'onclick=' not in response.data and b'style=' not in response.data


def test_no_javascript_contract_and_empty_rows(app):
    client = app.test_client()
    text = client.get('/bundles/new').data.decode()
    assert '<noscript>' in text and 'data-patient-mode="new"' in text and 'data-patient-mode="existing"' in text
    assert 'attachment_id' not in text
    data = values()
    for section in ('medications', 'orders', 'results', 'imaging', 'instructions', 'costs'):
        row(data, section, 0, {})
    assert post(client, data).status_code == 303


def test_removed_row_errors_do_not_reappear_on_language_switch(app):
    client = app.test_client()
    data = values()
    row(data, 'medications', 3, {'name': 'Partial demo'})
    response = post(client, data)
    assert response.status_code == 422
    del data['medications.rows']
    data['csrf'] = csrf(response)
    data['lang'], data['intent'], data['had_errors'] = 'ur', 'language', '1'
    response = client.post('/bundles/new', data=data)
    assert response.status_code == 200
    assert b'href="#medications-3-' not in response.data
    assert app.extensions['bundles'].list_bundles() == []


@pytest.mark.parametrize('key', ['01', '-1', 'word', '10000000'])
def test_invalid_local_row_keys_are_rejected_without_writes(app, key):
    client = app.test_client()
    data = values()
    row(data, 'orders', key, {})
    response = post(client, data)
    assert response.status_code == 422
    assert b'href="#intake-form"' in response.data
    assert app.extensions['bundles'].list_bundles() == []


@pytest.mark.parametrize('section', ['medications', 'results', 'imaging', 'costs', 'attachments'])
def test_individual_followup_forms_have_no_manual_identifier(app, section):
    client = app.test_client()
    created = post(client, values())
    bundle_path = created.location.split('?')[0]
    response = client.get(bundle_path + '/' + section + '/new')
    assert response.status_code == 200
    assert b'name="ID"' not in response.data
