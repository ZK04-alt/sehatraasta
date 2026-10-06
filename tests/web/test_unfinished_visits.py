"""Synthetic visits: leave, restart, resume, complete and recover."""
import json
import re
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib

import pytest

from test_intake import app, csrf, values, row, post
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.db import connect_database, initialize_database
from sehatraasta.web import create_app


def service(app):
    return UnfinishedVisitService(app.config['DATABASE'])


def later(client, data):
    data['intent'] = 'save_later'
    return post(client, data)


def test_destination_optional_and_progress_control_absent(app):
    client = app.test_client()
    text = client.get('/bundles/new').data.decode()
    assert 'name="status"' not in text
    assert 'New visit' in text
    data = values()
    data['destination'] = ''
    response = post(client, data)
    assert response.status_code == 303
    patient = next(p for p in SQLiteRepository(app.config['DATABASE']).list_patients() if p.ID != 'PK-001')
    assert patient.referrals[0].destination == ''
    edit = response.location.split('?')[0] + '/edit'
    response = client.post(edit, data={'csrf': csrf(client.get(edit)), 'source_facility': 'Demo hospital', 'destination': ''})
    assert response.status_code == 303
    assert patient.referrals[0].status.name == 'DRAFT'  # Existing storage format remains compatible.


def test_save_partial_does_not_create_completed_records_and_survives_restart(app):
    client = app.test_client()
    data = values()
    data['name'] = 'Partial Demo'
    data['birth_year'] = ''
    row(data, 'medications', 8, {'name': 'Unfinished medicine', 'dose': '__custom__', 'dose__custom': 'Original partial text'})
    assert later(client, data).status_code == 303
    drafts = service(app).list()
    assert len(drafts) == 1
    assert app.extensions['bundles'].list_bundles() == []
    restarted = create_app({'TESTING': True, 'DATABASE': app.config['DATABASE']}).test_client()
    queue = restarted.get('/bundles').data.decode()
    assert 'Unfinished' in queue and 'Partial Demo' in queue
    response = restarted.get('/bundles/new?unfinished=' + drafts[0]['draft_id'])
    text = response.data.decode()
    assert 'value="Partial Demo"' in text
    assert 'name="medications.rows" value="8"' in text
    assert 'Original partial text' in text


def test_finish_saved_visit_removes_unfinished_atomically(app):
    client = app.test_client()
    data = values()
    data['destination'] = ''
    assert later(client, data).status_code == 303
    saved = service(app).list()[0]
    data['intent'] = 'save'
    data['unfinished_id'] = saved['draft_id']
    data['unfinished_revision'] = str(saved['revision'])
    response = post(client, data)
    assert response.status_code == 303
    assert service(app).list() == []
    assert len(app.extensions['bundles'].list_bundles()) == 1
    # A replay cannot create a second visit after the unfinished entry is consumed.
    response = post(client, data)
    assert response.status_code == 422
    assert len(app.extensions['bundles'].list_bundles()) == 1


def test_invalid_finish_leaves_saved_partial_and_no_bundle(app):
    client = app.test_client()
    data = values()
    data['birth_year'] = ''
    later(client, data)
    saved = service(app).list()[0]
    data['intent'] = 'save'
    data['unfinished_id'] = saved['draft_id']
    data['unfinished_revision'] = str(saved['revision'])
    assert post(client, data).status_code == 422
    assert service(app).get(saved['draft_id'])['fields']['birth_year'] == ['']
    assert app.extensions['bundles'].list_bundles() == []


def test_mid_transaction_failure_retains_unfinished(app, monkeypatch):
    client = app.test_client()
    data = values()
    later(client, data)
    saved = service(app).list()[0]
    data['intent'] = 'save'
    data['unfinished_id'] = saved['draft_id']
    data['unfinished_revision'] = str(saved['revision'])
    def fail(*args):
        import sqlite3
        raise sqlite3.OperationalError('synthetic failure')
    monkeypatch.setattr(SQLiteRepository, '_write_bundle', fail)
    assert post(client, data).status_code == 503
    assert service(app).get(saved['draft_id'])['revision'] == 1
    assert len(SQLiteRepository(app.config['DATABASE']).list_patients()) == 1


def test_autosave_csrf_and_stale_tab_protection(app):
    client = app.test_client()
    page = client.get('/bundles/new').data.decode()
    token = re.search(r'data-autosave-token="([^"]+)"', page)[1]
    data = values()
    data['csrf'] = token
    assert client.post('/visits/unfinished', data=values()).status_code == 400
    saved = client.post('/visits/unfinished', data=data)
    assert saved.status_code == 200
    result = saved.json
    data['unfinished_id'] = result['draft_id']
    data['unfinished_revision'] = str(result['revision'])
    data['name'] = 'Updated Demo'
    assert client.post('/visits/unfinished', data=data).status_code == 200
    data['name'] = 'Stale Demo'
    assert client.post('/visits/unfinished', data=data).status_code == 409
    assert service(app).get(result['draft_id'])['fields']['name'] == ['Updated Demo']
    assert 'csrf' not in service(app).get(result['draft_id'])['fields']


def test_stale_save_later_preserves_input_on_error_page(app):
    client = app.test_client()
    data = values()
    later(client, data)
    saved = service(app).list()[0]
    service(app).save({'name': ['Newer Demo']}, saved['draft_id'], saved['revision'])
    data['unfinished_id'] = saved['draft_id']
    data['unfinished_revision'] = str(saved['revision'])
    data['name'] = 'Stale but preserved Demo'
    response = later(client, data)
    assert response.status_code == 409
    assert b'Stale but preserved Demo' in response.data
    assert service(app).get(saved['draft_id'])['fields']['name'] == ['Newer Demo']


@pytest.mark.parametrize('fields', [ {'name': []}, {'unknown': ['text']}, {'name': ['a', 'b']}, {'name': [2]}, {'name': ['a' * 65537]} ])
def test_malformed_unfinished_input_rejected_without_changes(app, fields):
    with pytest.raises(ValueError):
        service(app).save(fields)
    assert service(app).list() == []


def test_backup_and_restore_include_unfinished(app, tmp_path):
    saved = service(app).save({'name': ['Recover Demo'], 'medications.rows': ['8', '2'], 'medications.2.name': ['Partial medicine']})
    backup = DatasetBackupService(app.config['DATABASE'])
    folder = tmp_path / 'backups'
    archive = folder / backup.create(folder)
    assert backup.dry_run(archive)['unfinished'] == 1
    destination = tmp_path / 'restored'
    backup.restore(archive, destination, confirmed=True)
    restored = UnfinishedVisitService(destination / 'sehatraasta.sqlite').get(saved['draft_id'])
    assert restored['fields']['medications.rows'] == ['8', '2']
    assert restored['fields']['name'] == ['Recover Demo']


@pytest.mark.parametrize('version', [2, 3])
def test_old_backups_restore_into_new_schema(app, tmp_path, version):
    backup = DatasetBackupService(app.config['DATABASE'])
    folder = tmp_path / 'backups'
    source = folder / backup.create(folder)
    with ZipFile(source) as archive:
        document = json.loads(archive.read('dataset.json'))
    tables = document['tables']
    tables.pop('visit_drafts'); tables.pop('visit_draft_fields')
    if version == 2:
        tables.pop('referral_context')
    tables['schema_version'] = [item for item in tables['schema_version'] if item['version'] <= version]
    content = json.dumps(document).encode()
    legacy = tmp_path / 'legacy.zip'
    with ZipFile(legacy, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('dataset.json', content)
        archive.writestr('manifest.json', json.dumps({'dataset.json': hashlib.sha256(content).hexdigest()}))
    destination = tmp_path / 'restored'
    backup.restore(legacy, destination, confirmed=True)
    assert UnfinishedVisitService(destination / 'sehatraasta.sqlite').list() == []
    assert len(SQLiteRepository(destination / 'sehatraasta.sqlite').list_patients()) == 1


def test_version_three_database_upgrades_without_losing_patient(app):
    connection = connect_database(app.config['DATABASE'])
    with connection:
        connection.execute('DROP TABLE visit_draft_fields')
        connection.execute('DROP TABLE visit_drafts')
        connection.execute('DELETE FROM schema_version WHERE version = 4')
    connection.close()
    initialize_database(app.config['DATABASE'])
    assert SQLiteRepository(app.config['DATABASE']).list_patients()[0].name == 'Existing Demo'
    assert service(app).list() == []
