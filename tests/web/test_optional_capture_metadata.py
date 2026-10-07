from io import BytesIO
import re

from sehatraasta.storage import SQLiteRepository
from sehatraasta.web import create_app


def token(page):
    return re.search(r'name="csrf" value="([^"]+)"', page.text)[1]


def test_patient_form_accepts_name_without_birth_year(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'records.sqlite'})
    client = app.test_client()
    response = client.post('/patients/new', data={'csrf': token(client.get('/patients/new')),
        'name': 'Fictional minimal person', 'birth_year': '', 'language': 'ENGLISH'})
    assert response.status_code == 303
    assert SQLiteRepository(app.config['DATABASE']).list_patients()[0].birth_year is None


def test_existing_visit_accepts_original_without_date_or_category(tmp_path):
    from datetime import datetime
    from sehatraasta.domain import Language, ReferralStatus
    from sehatraasta.services.bundle_service import BundleService
    app = create_app({'TESTING': True, 'DATABASE': tmp_path / 'records.sqlite'})
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    service.create_patient('PK-001', 'Fictional minimal person', None, Language.ENGLISH)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 10, 7), '', '', ReferralStatus.DRAFT)
    client = app.test_client()
    url = '/bundles/RB-001/attachments/new'
    response = client.post(url, data={'csrf': token(client.get(url)),
        'file': (BytesIO(b'%PDF-1.4\nFictional-only original'), 'fictional.pdf')})
    assert response.status_code == 303
    original = service.get_bundle('RB-001').attachments[0]
    assert original.date is None
    assert original.category == 'other'
