"""Android presentation changes must not remove desktop or offline features."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from sehatraasta.domain import CostCategory, Language, ReferralStatus
from sehatraasta.web import create_app


@pytest.fixture(params=[False, True], ids=['website', 'android'])
def phone(tmp_path, request):
    app = create_app({'TESTING': True, 'ANDROID_APP': request.param, 'DATABASE': tmp_path / 'phone.sqlite'})
    client = app.test_client()
    client.get('/patients')
    service = app.extensions['bundles']
    service.create_patient('PK-001', 'Theme Demo', 1980, Language.URDU)
    service.create_bundle('PK-001', 'SR-DEMO-001', datetime(2026, 10, 4, 10),
                          'Demo clinic', 'Demo hospital', ReferralStatus.DRAFT)
    service.add_medication('SR-DEMO-001', 'MD-001', 'Demo medicine', '10 mg', '1 tablet',
                           '', 'Once a day', '5 days', '', '')
    service.add_cost('SR-DEMO-001', 'CE-001', CostCategory.TRAVEL, Decimal('2500.10'),
                    date(2026, 10, 4), 'Demo interview', source_type='reported',
                    source_identifier='DEMO-001')
    return app, client


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_phone_logo_navigation_and_records(phone, language):
    app, client = phone
    response = client.get('/bundles?lang=' + language)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert ('android-app' if app.config['ANDROID_APP'] else 'web-app') in text
    assert '/static/interface.css' in text
    assert '/static/wordmark.svg' in text
    assert 'class="referral-card"' in text
    assert 'Theme Demo' in text and 'Demo hospital' in text
    assert 'class="app-menu"' in text
    assert '/backups?' in text and '/restore?' in text and '/passports/import?' in text
    assert '[Missing' not in text
    assert f'lang="{language}"' in text
    assert 'dir="rtl"' in text if language != 'en' else 'dir="ltr"' in text


def test_phone_keeps_records_exact_costs_and_exports(phone):
    _, client = phone
    text = client.get('/bundles/SR-DEMO-001').get_data(as_text=True)
    assert 'details class="record-section"' in text
    assert 'Demo medicine' in text and '2,500.10' in text
    assert 'class="help-disclosure"' in text
    for suffix in ['/context', '/reviews', '/print', '/audit', '/export', '/passport']:
        assert 'SR-DEMO-001' + suffix in text


def test_phone_print_keeps_full_records_visible(phone):
    _, client = phone
    text = client.get('/bundles/SR-DEMO-001/print').get_data(as_text=True)
    assert 'section class="record-section"' in text
    assert 'details class="record-section"' not in text
    assert 'Demo medicine' in text and '2,500.10' not in text and 'img class="qr"' in text
    text_with_costs = client.get('/patients/PK-001/print?preview=yes&visit=SR-DEMO-001&costs=yes').get_data(as_text=True)
    assert '2,500.10' in text_with_costs


@pytest.mark.parametrize('language', ['en', 'ur', 'ps'])
def test_phone_form_keeps_optional_groups_and_help(phone, language):
    _, client = phone
    response = client.get('/bundles/new?lang=' + language)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'class="help-disclosure field-help"' in text
    assert 'data-intake' in text and 'data-patient-mode="existing"' in text
    for group in ['medications', 'orders', 'results', 'imaging', 'instructions', 'costs']:
        assert 'data-repeat="' + group + '"' in text
    assert '[Missing' not in text


def test_desktop_shares_the_approved_presentation(tmp_path):
    client = create_app({'TESTING': True, 'DATABASE': tmp_path / 'desktop.sqlite'}).test_client()
    text = client.get('/bundles').get_data(as_text=True)
    assert '/static/wordmark.svg' in text
    assert '/static/android.css' not in text
    assert 'interface-app web-app' in text
    assert '/static/interface.css' in text
    assert 'class="app-menu"' in text
    assert '/backups?' in text and '/restore?' in text


@pytest.mark.parametrize('asset', ['interface.css', 'wordmark.svg', 'fonts/PublicSans.ttf',
                                 'fonts/LibreFranklin.ttf', 'fonts/NotoSansArabic.ttf'])
def test_phone_assets_available_offline(phone, asset):
    _, client = phone
    response = client.get('/static/' + asset)
    assert response.status_code == 200 and len(response.data) > 100
    assert "font-src 'self'" in response.headers['Content-Security-Policy']
