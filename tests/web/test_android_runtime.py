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
