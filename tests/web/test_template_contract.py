"""Presentation contract: labels, language, local assets, safe output and states."""
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.web import create_app


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def client(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'data.sqlite'})
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    service.create_patient('PK-001', 'Demo <script>text</script> مثال', 1980, Language.URDU)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 9, 21), 'Demo BHU', 'Demo Hospital', ReferralStatus.DRAFT)
    app.extensions['bundles'] = service
    return app.test_client()


@pytest.mark.parametrize('language,direction', [('en', 'ltr'), ('ur', 'rtl'), ('ps', 'rtl')])
@pytest.mark.parametrize('path', ['/', '/patients', '/patients/PK-001', '/patients/new', '/bundles/new',
    '/bundles/RB-001', '/bundles/RB-001/costs/new', '/bundles/RB-001/attachments/new',
    '/bundles/RB-001/reviews', '/bundles/RB-001/print', '/restore', '/privacy', '/terms', '/not-found'])
def test_language_semantics_and_local_assets(client, language, direction, path):
    response = client.get(path + '?lang=' + language)
    text = response.data.decode()
    markup = Markup(text)
    assert ('html', {'lang': language, 'dir': direction}) in markup.elements
    assert '[Missing translation:' not in text
    assert '<script>text</script>' not in text
    assert any(tag == 'main' and attrs.get('id') == 'main' for tag, attrs in markup.elements)
    assert any(tag == 'a' and attrs.get('href') == '/privacy?lang=' + language for tag, attrs in markup.elements)
    assert any(tag == 'a' and attrs.get('href') == '/terms?lang=' + language for tag, attrs in markup.elements)
    ids = [attrs['id'] for _, attrs in markup.elements if 'id' in attrs]
    assert len(ids) == len(set(ids))
    for tag, attrs in markup.elements:
        if tag in ('script', 'img', 'link'):
            source = attrs.get('src', attrs.get('href', ''))
            assert source.startswith(('/', 'data:')) and not source.startswith('//')
        if tag == 'label':
            assert attrs['for'] in ids
    assert "default-src 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Referrer-Policy'] == 'same-origin'


def test_field_errors_link_to_inputs_and_preserve_text(client):
    text = client.get('/patients/new').data.decode()
    csrf = re.search(r'name="csrf" value="([^"]+)"', text)[1]
    response = client.post('/patients/new', data={'csrf': csrf, 'name': 'Original مثال', 'birth_year': 'bad'})
    assert response.status_code == 422
    text = response.data.decode()
    assert 'Original مثال' in text
    markup = Markup(text)
    ids = {attrs['id'] for _, attrs in markup.elements if 'id' in attrs}
    assert any(attrs.get('id') == 'errors' and attrs.get('tabindex') == '-1' for _, attrs in markup.elements)
    for tag, attrs in markup.elements:
        if tag == 'a' and attrs.get('href', '').startswith('#'):
            assert attrs['href'][1:] in ids
        if attrs.get('aria-invalid') == 'true':
            assert attrs.get('aria-describedby')
            assert all(value in ids for value in attrs['aria-describedby'].split())


def test_favicon_policies_and_skeleton(client):
    icon = client.get('/favicon.ico')
    assert icon.status_code == 200 and b'<svg' in icon.data
    privacy = client.get('/privacy').data
    assert b'no user accounts' in privacy and b'application-level encryption' in privacy
    assert b'fictional' not in client.get('/terms').data
    form = client.get('/patients/new').data
    assert b'class="skeleton"' in form and b'role="status"' in form
    script = client.get('/static/app.js').data
    assert b'aria-busy' in script


def test_clean_shell_and_local_wordmark(client):
    page = client.get('/bundles').data
    assert b'DEVELOPMENT VERSION' not in page
    assert b'Local referral workspace' not in page
    assert b'Synthetic examples only' not in page
    assert b'alt="SehatRaasta"' in page
    logo = client.get('/static/wordmark.svg')
    assert logo.status_code == 200 and b'<svg' in logo.data
    assert b'Synthetic examples only' not in client.get('/bundles/RB-001/print').data


def test_patient_and_file_forms_do_not_contain_development_prompts(client):
    for path in ['/patients/new', '/bundles/RB-001/attachments/new', '/privacy', '/terms']:
        response = client.get(path)
        assert response.status_code == 200
        text = response.text.lower()
        for phrase in ('made-up name', 'synthetic content', 'development version', 'fictional', 'prototype'):
            assert phrase not in text


def test_visual_constraints_and_print_rules():
    root = Path(__file__).parents[2] / 'src/sehatraasta/web'
    css = (root / 'static/app.css').read_text(encoding='utf-8')
    assert '@media print' in css and '@media (prefers-reduced-motion: reduce)' in css
    assert 'inset-inline-start' in css and ':focus-visible' in css
    assert 'gradient(' not in css and 'box-shadow:' not in css and '@import' not in css
    assert 'border-radius: 0' in css
    for path in (root / 'templates').glob('*.html'):
        text = path.read_text(encoding='utf-8')
        assert '|safe' not in text
        assert '<iframe' not in text


def test_contrast_for_text_and_control_tokens():
    def luminance(hex_color):
        rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))
    for text in ('#19323f', '#465650', '#185b59', '#8e2922'):
        for background in ('#f1efe7', '#f8f6ef'):
            assert (luminance(background) + .05) / (luminance(text) + .05) >= 4.5
