from io import BytesIO
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'integration'))
from test_corrections import case
from sehatraasta.web import create_app


def token(page):
    return re.search(r'name="csrf" value="([^"]+)"', page.text)[1]


def test_visit_edit_shows_identity_and_moves_honest_date(case):
    service, _ = case
    app = create_app({'TESTING': True, 'DATABASE': service.repository.path})
    client = app.test_client()
    url = '/bundles/RB-001/edit'
    page = client.get(url)
    assert 'Fictional PK-001' in page.text
    response = client.post(url, data={'csrf': token(page),
        'revision': service.get_patient('PK-001')._storage_revision, 'patient_id':'PK-002',
        'source_facility':'Fictional corrected', 'destination':'',
        'medical_date_kind':'approximate', 'medical_date_value':'2006'})
    assert response.status_code == 303
    assert service.get_bundle_owner('RB-001')[0].ID == 'PK-002'
    assert 'Approximate date: 2006' in client.get(response.location).text


def test_document_remove_is_recoverable_after_navigation_and_permanent_is_separate(case):
    service, original = case
    client = create_app({'TESTING': True, 'DATABASE': service.repository.path}).test_client()
    url = '/attachments/AT-001/delete'
    page = client.get(url)
    assert 'Fictional PK-001' in page.text
    response = client.post(url, data={'csrf':token(page), 'confirm':'yes',
        'revision':service.get_patient('PK-001')._storage_revision})
    assert response.status_code == 303
    assert client.get('/attachments/AT-001/content').status_code == 404
    page = client.get('/removed')
    assert 'fictional.pdf' in page.text
    from sehatraasta.services.recovery_service import RecoveryService
    item = RecoveryService(service.repository.path).list()[0]['item_id']
    restore_url = '/removed/' + item + '/restore'
    response = client.post(restore_url, data={'csrf':token(client.get(restore_url)), 'confirm':'yes'})
    assert response.status_code == 303
    assert client.get('/attachments/AT-001/content').data == original.read_bytes()


def test_document_edit_source_can_be_unknown_and_move_saves(case):
    service,original=case
    client=create_app({'TESTING':True,'DATABASE':service.repository.path}).test_client()
    response=client.get('/attachments/AT-001/edit')
    response=client.post('/attachments/AT-001/edit',data={'csrf':token(response),'revision':service.get_patient('PK-001')._storage_revision,
        'name':'Fictional renamed.pdf','category':'other','date':'','destination_visit':'RB-002','source_type':'NOT_SUPPLIED','source':'','source_identifier':''})
    assert response.status_code==303
    assert service.get_bundle('RB-002').attachments[0].name=='Fictional renamed.pdf'
