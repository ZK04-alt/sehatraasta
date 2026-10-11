"""Local browser transport, exercised against the real application/services."""
from datetime import datetime
from importlib import import_module, util
from io import BytesIO
import re
from urllib.parse import urlencode

import pytest
from werkzeug.test import EnvironBuilder

from sehatraasta.domain import Language, ReferralStatus


MOUNT = '/sehatraasta/iphone/app'
ORIGIN = 'https://zk04-alt.github.io'


def adapter(root):
    assert util.find_spec('sehatraasta.browser_runtime'), 'Browser application adapter is missing'
    return import_module('sehatraasta.browser_runtime').BrowserApplication(root)


@pytest.fixture
def runtime(tmp_path):
    return adapter(tmp_path / 'records')


def request(runtime, path='/', method='GET', data=None, headers=None):
    builder = EnvironBuilder(path=path, method=method, data=data)
    environ = builder.get_environ()
    body = environ['wsgi.input'].read()
    outgoing = list(headers or [])
    if environ.get('CONTENT_TYPE'):
        outgoing.append(('Content-Type', environ['CONTENT_TYPE']))
    builder.close()
    return runtime.handle(method, MOUNT + path, '', outgoing, body)


def csrf(runtime, path):
    page = request(runtime, path)
    assert page['status'] == 200
    return re.search(rb'name="csrf" value="([^"]+)"', page['body'])[1].decode()


def post(runtime, path, values):
    return request(runtime, path, 'POST', {'csrf': csrf(runtime, path), **values})


def seed(runtime):
    service = runtime.app.extensions['bundles']
    service.create_patient('PK-001', 'Amina Demo', 1980, Language.URDU)
    service.create_bundle('PK-001', 'SR-DEMO-001', datetime(2026, 10, 11, 9),
                          'Demo Clinic', '', ReferralStatus.DRAFT)
    return service


def test_browser_runtime_queue(runtime):
    response = request(runtime)
    assert response['status'] == 200
    assert b'No records yet' in response['body']
    headers = dict(response['headers'])
    assert headers['Cache-Control'] == 'no-store'
    assert headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert "frame-ancestors 'self'" in headers['Content-Security-Policy']
    assert not any(key.lower() == 'set-cookie' for key, _ in response['headers'])


def test_browser_runtime_mount_urls(runtime):
    page = request(runtime)['body'].decode()
    for target in ['/patients', '/lookup', '/terms', '/privacy', '/static/wordmark.svg']:
        assert MOUNT + target in page
    assert 'href="/terms' not in page and 'href="/privacy' not in page
    assert MOUNT + '/?lang=ur' in page
    qr = request(runtime, '/lookup')['body']
    assert b'data-scan-camera' in qr and b'data-scan-image' in qr


def test_browser_runtime_session_csrf(runtime):
    path = '/patients/new'
    values = {'name': 'Amina Demo', 'birth_year': '1980', 'language': 'URDU'}
    invalid = request(runtime, path, 'POST', values)
    assert invalid['status'] == 400
    token = csrf(runtime, path)
    forged = request(runtime, path, 'POST', {**values, 'csrf': token},
                     [('Origin', 'https://unrelated.example')])
    assert forged['status'] == 403
    result = request(runtime, path, 'POST', {**values, 'csrf': token}, [('Origin', ORIGIN)])
    assert result['status'] == 303
    assert dict(result['headers'])['Location'].startswith(MOUNT + '/patients?')
    assert len(runtime.app.extensions['bundles'].list_patients()) == 1
    assert request(runtime, path, 'POST', {**values, 'csrf': token})['status'] == 409


def test_browser_runtime_multipart_import(runtime):
    service = seed(runtime)
    content = b'%PDF-1.4\nFictional browser attachment\n%%EOF'
    result = post(runtime, '/bundles/SR-DEMO-001/attachments/new', {
        'file': (BytesIO(content), 'Demo Report.pdf'), 'category': 'OTHER',
        'date': '2026-10-11', 'source_type': 'NOT_SUPPLIED', 'synthetic': 'yes',
    })
    assert result['status'] == 303
    document = service.get_bundle('SR-DEMO-001').attachments[0]
    exported = request(runtime, '/attachments/' + document.ID + '/download')
    assert exported['status'] == 200 and exported['body'] == content
    assert 'attachment;' in dict(exported['headers'])['Content-Disposition']
    files = dict(runtime.collect_files())
    assert content in files.values()
    assert all(not name.startswith('/') and '..' not in name.split('/') for name in files)


def test_browser_runtime_restore_activation(runtime):
    service = seed(runtime)
    content = b'%PDF-1.4\nBackup original\n%%EOF'
    assert post(runtime, '/bundles/SR-DEMO-001/attachments/new', {
        'file': (BytesIO(content), 'Original.pdf'), 'category': 'OTHER',
        'date': '2026-10-11', 'source_type': 'NOT_SUPPLIED', 'synthetic': 'yes',
    })['status'] == 303
    backup = post(runtime, '/backups', {'confirm': 'yes'})
    assert backup['status'] == 200 and backup['body'].startswith(b'PK')
    service.create_patient('PK-002', 'Later Demo', 1990, Language.ENGLISH)
    old_token = csrf(runtime, '/patients/new')
    for intent in ['check', 'restore']:
        result = post(runtime, '/restore', {
            'archive': (BytesIO(backup['body']), 'backup.zip'), 'intent': intent,
        })
        assert result['status'] == 200
    assert b'Backup restored and opened.' in result['body']
    assert runtime.app.config['DATABASE'].parent.name != 'records'
    assert len(runtime.app.extensions['bundles'].list_patients()) == 1
    assert content in dict(runtime.collect_files()).values()
    stale = request(runtime, '/patients/new', 'POST', {
        'csrf': old_token, 'name': 'Old form', 'language': 'ENGLISH',
    })
    assert stale['status'] == 409
    reopened = adapter(runtime.root)
    assert len(reopened.app.extensions['bundles'].list_patients()) == 1
    assert b'Amina Demo' in request(reopened, '/patients')['body']


@pytest.mark.parametrize('path', [
    '/patients', MOUNT + '/../patients', MOUNT + '/%2e%2e/patients',
    MOUNT + '/%252e%252e/patients', MOUNT + '/%2f%2fother', MOUNT + '\\patients',
])
def test_browser_runtime_rejects_scope_escape(runtime, path):
    result = runtime.handle('POST', path, '', [('Content-Type', 'text/plain')], b'private text')
    assert result['status'] == 400
    assert b'private text' not in result['body']
    assert not runtime.app.extensions['bundles'].list_patients()


def test_browser_runtime_binary_static_and_cookie_survive_reopen(runtime):
    asset = request(runtime, '/static/wordmark.svg')
    assert asset['status'] == 200 and b'<svg' in asset['body']
    path = '/patients/new'
    token = csrf(runtime, path)
    reopened = adapter(runtime.root)
    result = request(reopened, path, 'POST', {
        'csrf': token, 'name': 'Reopened Demo', 'language': 'ENGLISH',
    })
    # A cold start invalidates stale forms while keeping language/cookies.
    assert result['status'] == 409
    urdu = runtime.handle('GET', MOUNT + '/patients', urlencode({'lang': 'ur'}), [], b'')
    assert b'dir="rtl"' in urdu['body']
    assert b'lang="ur"' in request(adapter(runtime.root), '/patients')['body']


def test_browser_runtime_never_uses_native_form_submission(runtime):
    result = request(runtime, '/patients/new')
    headers = dict(result['headers'])
    assert "form-action 'none'" in headers['Content-Security-Policy']
    assert b'/sehatraasta/iphone/bridge.js' in result['body']
    assert b'browser-app' in result['body']
