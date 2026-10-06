"""Exercise the learning lab through real local HTTP requests."""
from http.client import HTTPConnection
from pathlib import Path
import runpy
import sqlite3
from threading import Thread
from urllib.parse import urlencode

import pytest


LAB = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'learning-labs/phase06_multilingual_form/lab.py'))


@pytest.fixture
def server(tmp_path):
    server = LAB['make_server'](tmp_path / 'lab.sqlite', 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request(server, method='GET', path='/', values=None, headers=None):
    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        body = urlencode(values) if values is not None else None
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.read().decode('utf-8'), dict(response.getheaders())
    finally:
        connection.close()


def valid_values(server):
    return {'name': 'Demo مثال AP-123', 'date': '2026-09-20', 'synthetic': 'yes',
            'language': 'en', 'intent': 'save', 'csrf': server.token}


def test_http_validation_save_and_duplicate(server):
    status, body, _ = request(server, 'POST', values={'csrf': server.token})
    assert status == 422 and 'aria-invalid="true"' in body
    assert server.store.list_requests() == []
    values = valid_values(server)
    status, _, headers = request(server, 'POST', values=values)
    assert status == 303
    assert headers['Location'] == '/requests?lang=en&saved=1'
    assert request(server, path=headers['Location'])[0] == 200
    assert request(server, 'POST', values=values)[0] == 409
    assert len(server.store.list_requests()) == 1


def test_language_switch_preserves_invalid_input_without_saving(server):
    values = valid_values(server)
    values.update(language='ps', intent='language', date='invalid', had_errors='1')
    status, body, _ = request(server, 'POST', values=values)
    assert status == 200 and 'lang="ps" dir="rtl"' in body
    assert 'value="invalid"' in body and 'Demo مثال AP-123' in body
    assert 'aria-invalid="true"' in body
    assert '<bdi dir="ltr">2026-09-20</bdi>' in body
    assert server.store.list_requests() == []


def test_actual_storage_failure_preserves_input_and_hides_details(server, monkeypatch):
    def fail(values):
        raise sqlite3.OperationalError('private source text C:/private/location')
    monkeypatch.setattr(server.store, 'save', fail)
    status, body, _ = request(server, 'POST', values=valid_values(server))
    assert status == 503 and 'Demo مثال AP-123' in body
    assert 'private source' not in body and 'C:/private' not in body
    assert server.store.list_requests() == []


def test_actual_not_found_and_unexpected_failure(server, monkeypatch):
    assert request(server, path='/does-not-exist')[0] == 404
    def fail():
        raise RuntimeError('secret exception details')
    monkeypatch.setattr(server.store, 'list_requests', fail)
    status, body, headers = request(server, path='/requests')
    assert status == 500 and 'secret exception' not in body
    assert headers['Cache-Control'] == 'no-store'


def test_untrusted_posts_do_not_write(server):
    values = valid_values(server)
    values['csrf'] = 'wrong'
    assert request(server, 'POST', values=values)[0] == 403
    values['csrf'] = server.token
    assert request(server, 'POST', values=values, headers={'Origin': 'https://untrusted.example'})[0] == 403
    assert request(server, headers={'Host': 'untrusted.example'})[0] == 403
    assert server.store.list_requests() == []
