import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response
from sehatraasta.android_runtime import PrivateSession


def test_local_transport_requires_private_cookie():
    def app(environ, start):
        start('200 OK', [('Content-Type', 'text/plain')])
        return [b'private records']
    client = Client(PrivateSession(app, 'test-secret'), Response)
    assert client.get('/').status_code == 403
    client.set_cookie('sr_device', 'wrong')
    assert client.get('/').status_code == 403
    client.set_cookie('sr_device', 'test-secret')
    assert client.get('/').data == b'private records'


def test_phone_runtime_serves_real_app_only_after_authentication(tmp_path):
    from sehatraasta import android_runtime as runtime
    info = json.loads(runtime.start(tmp_path))
    try:
        with pytest.raises(HTTPError) as denied:
            urlopen(info['origin'] + '/patients', timeout=5)
        assert denied.value.code == 403
        denied.value.close()
        request = Request(info['origin'] + '/patients', headers={'Cookie': 'sr_device=' + info['token']})
        with urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert b'SehatRaasta' in response.read()
        assert (tmp_path / 'records/sehatraasta.sqlite').exists()
        assert json.loads(runtime.start(tmp_path)) == info
    finally:
        runtime._server.shutdown()
        runtime._server.server_close()
        runtime._server = runtime._connection = None


def test_restored_dataset_is_activated_and_survives_restart(tmp_path):
    from pathlib import Path
    from werkzeug.datastructures import FileStorage
    from io import BytesIO
    from sehatraasta import android_runtime as runtime
    from sehatraasta.domain import Language
    from sehatraasta.services.bundle_service import BundleService
    from sehatraasta.services.web_transfer_service import WebTransferService
    from sehatraasta.storage import SQLiteRepository
    runtime.start(tmp_path)
    try:
        app = runtime._server.app.app
        old_database = app.config['DATABASE']
        original = BundleService(SQLiteRepository(old_database))
        original.create_patient('PK-001', 'Before backup', 1990, Language.ENGLISH)
        archive = WebTransferService(original).backup()
        original.create_patient('PK-002', 'After backup', 1991, Language.ENGLISH)
        summary, name = WebTransferService(original).restore(FileStorage(BytesIO(archive)), confirm=True)
        app.config['ACTIVATE_RESTORE'](name)
        assert [p.ID for p in app.extensions['bundles'].list_patients()] == ['PK-001']
        assert len(original.list_patients()) == 2
        assert app.config['DATABASE'] != old_database
        runtime._server.shutdown()
        runtime._server.server_close()
        runtime._server = runtime._connection = None
        runtime.start(tmp_path)
        app = runtime._server.app.app
        assert len(BundleService(SQLiteRepository(app.config['DATABASE'])).list_patients()) == 1
    finally:
        runtime._server.shutdown()
        runtime._server.server_close()
        runtime._server = runtime._connection = None


def test_old_form_cannot_write_into_restored_dataset_with_same_ids(tmp_path):
    """A revision match does not establish identity after a dataset switch."""
    import re
    from datetime import datetime
    from io import BytesIO
    from werkzeug.datastructures import FileStorage
    from sehatraasta import android_runtime as runtime
    from sehatraasta.domain import Language, ReferralStatus
    from sehatraasta.services.bundle_service import BundleService
    from sehatraasta.services.web_transfer_service import WebTransferService
    from sehatraasta.storage import SQLiteRepository
    runtime.start(tmp_path)
    try:
        app = runtime._server.app.app
        original = BundleService(SQLiteRepository(app.config['DATABASE']))
        donor = BundleService(SQLiteRepository(tmp_path / 'donor.sqlite'))
        for service, name in [(original, 'Fictional original A'), (donor, 'Fictional restored B')]:
            service.create_patient('PK-001', name, None, Language.ENGLISH)
            service.create_bundle('PK-001', 'RB-001', datetime(2026, 10, 7), '', '', ReferralStatus.DRAFT)
        client = app.test_client()
        url = '/bundles/RB-001/medications/new'
        token = re.search(r'name="csrf" value="([^"]+)"', client.get(url).text)[1]
        _, restored = WebTransferService(original).restore(
            FileStorage(BytesIO(WebTransferService(donor).backup()), filename='fictional.zip'), confirm=True)
        app.config['ACTIVATE_RESTORE'](restored)
        data = dict(name='Fictional stale A medicine', strength='1 mg', dose='1 tablet',
                    route='By mouth', frequency='Once a day', duration='3 days', instructions='', source='')
        response = client.post(url, data={'csrf': token, **data})
        assert response.status_code == 409
        assert 'records changed' in response.text
        active = app.extensions['bundles']
        assert active.get_patient('PK-001').name == 'Fictional restored B'
        assert active.get_bundle('RB-001').medication_item == []
        fresh = re.search(r'name="csrf" value="([^"]+)"', client.get(url).text)[1]
        assert client.post(url, data={'csrf': fresh, **data}).status_code == 303
        assert original.get_bundle('RB-001').medication_item == []
    finally:
        runtime._server.shutdown()
        runtime._server.server_close()
        runtime._server = runtime._connection = None
