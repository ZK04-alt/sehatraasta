from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import re
import runpy
import sqlite3

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.presentation import catalogs
from sehatraasta.presentation.errors import UIError, error_from_exception
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage.errors import StorageError
from sehatraasta.storage.sqlite_repository import SQLiteRepository
from sehatraasta.web.errors import error_response


ROOT = Path(__file__).resolve().parents[2]
LAB = runpy.run_path(str(ROOT / 'learning-labs/phase06_multilingual_form/lab.py'))


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_catalogs_complete_with_honest_review_status(language):
    catalogs.validate_catalogs()
    entries = catalogs.load_catalog(language)
    assert entries.keys() == catalogs.load_catalog('en').keys()
    for entry in entries.values():
        assert entry['text'].strip()
        assert entry['review_status'] == ('reviewed' if language == 'en' else 'review_pending')
        if language != 'en':
            assert entry['reviewer'] is None


def test_missing_key_visible_and_empty_translation_fails(monkeypatch):
    assert catalogs.translate('does.not.exist', 'ps') == '[Missing translation: does.not.exist]'
    monkeypatch.setitem(catalogs.MESSAGES, 'bad', ('text', '', 'text'))
    with pytest.raises(ValueError, match='incomplete'):
        catalogs.validate_catalogs()
    assert catalogs.translate('bad', 'ur') == '[Missing translation: bad]'


def test_contract_message_keys_exist():
    contract = (ROOT / 'docs/decisions/ui-contract.md').read_text(encoding='utf-8')
    for key in re.findall(r'`((?:page|action|error|warning|status|state)\.[a-z_]+)`', contract):
        assert key in catalogs.load_catalog('en'), key


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
@pytest.mark.parametrize('state', LAB['STATES'])
def test_every_state_has_correct_structure(language, state):
    html, status = LAB['state_page'](language, state, 'demo-token')
    parsed = Markup(html)
    assert ('html', {'lang': language, 'dir': catalogs.LANGUAGES[language][1]}) in parsed.tags
    assert any(tag == 'h1' for tag, attributes in parsed.tags)
    assert catalogs.translate('lab.warning', language) in html
    assert '[Missing translation:' not in html
    assert '<script' not in html
    ids = [attributes['id'] for _, attributes in parsed.tags if 'id' in attributes]
    assert len(ids) == len(set(ids))
    for tag, attributes in parsed.tags:
        if attributes.get('aria-invalid') == 'true':
            assert any(t == 'label' and a.get('for') == attributes['id'] for t, a in parsed.tags)
            assert any(t == 'a' and a.get('href') == '#' + attributes['id'] for t, a in parsed.tags)
            assert all(ref in ids for ref in attributes['aria-describedby'].split())
    if state == 'success':
        assert 'role="status"' in html
    if state in ('unavailable', '404', '500'):
        assert status in (503, 404, 500)


def test_save_duplicate_and_validation(tmp_path):
    store = LAB['AppointmentStore'](tmp_path / 'lab.sqlite')
    valid = {'name': 'Demo مثال AP-001', 'date': '2026-09-20', 'synthetic': 'yes'}
    assert len(store.save({})) == 3
    assert store.list_requests() == []
    assert store.save(valid) == []
    assert store.save(valid)[0].code == 'error.duplicate'
    assert store.list_requests() == [(1, valid['name'], valid['date'])]


def test_lab_refuses_application_database(tmp_path):
    path = tmp_path / 'app.sqlite'
    SQLiteRepository(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='separate'):
        LAB['AppointmentStore'](path)
    assert path.read_bytes() == before


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_language_rendering_does_not_change_original_text(tmp_path, language):
    repository = SQLiteRepository(tmp_path / 'app.sqlite')
    service = BundleService(repository)
    service.create_patient('PK-001', 'Demo مثال', 1980, Language.URDU)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 9, 20), 'اصل متن ABC-12', 'Demo', ReferralStatus.DRAFT)
    before = repository.path.read_bytes()
    text = service.get_bundle('RB-001').source_facility
    html = LAB['listing'](language, [(1, text, '2026-09-20')])
    assert '<bdi dir="auto">اصل متن ABC-12</bdi>' in html
    assert '<bdi dir="ltr">AP-001</bdi>' in html
    assert repository.path.read_bytes() == before


@pytest.mark.parametrize('error,code,status', [
    (ValueError('missing name'), 'error.required', 422),
    (ValueError('invalid ID'), 'error.id', 422),
    (ValueError('duplicate ID'), 'error.duplicate', 409),
    (ValueError('bundle not found'), 'error.not_found', 404),
    (StorageError('C:/secret/patient-data'), 'error.unavailable', 503),
    (RuntimeError('private clinical text'), 'error.unexpected', 500),
])
def test_shared_errors_are_safe_and_consistent(error, code, status):
    presented = error_from_exception(error, 'name')
    payload, http_status = error_response(error, 'ur', 'name')
    assert presented.code == code
    assert presented.status == http_status == status
    assert payload['message'] == presented.message('ur')
    assert 'secret' not in str(payload) and 'clinical text' not in str(payload)


def test_escaping_and_logical_css():
    html = LAB['form']('ur', 'demo', {'name': '<script>bad()</script>'})
    assert '<script>' not in html and '&lt;script&gt;' in html
    css = (ROOT / 'src/sehatraasta/presentation/tokens.css').read_text()
    assert 'margin-inline' in css and 'border-inline-start' in css
    assert 'outline: 3px' in css and '@media print' in css
    assert not re.search(r'(margin|padding|border)-(left|right)', css)


def test_color_contrast():
    def luminance(color):
        channels = [int(color[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    for color in ('17212b', '465465', '1649a0', '9b1c1c'):
        assert 1.05 / (luminance(color) + .05) >= 4.5
    assert 1.05 / (luminance('667085') + .05) >= 3


def test_cli_error_keeps_known_field_but_not_arbitrary_exception_text():
    assert error_from_exception(ValueError('missing name')).as_text() == 'Display name: Enter a value in this field.'
    result = error_from_exception(ValueError('missing private patient text')).as_text()
    assert 'private patient' not in result
