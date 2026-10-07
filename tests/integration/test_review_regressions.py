"""Fictional regressions for reproduced review findings."""
from datetime import date
from io import BytesIO
import json
import re

import pytest
from test_corrections import case
from sehatraasta.domain import Encounter, Language, InvestigationOrderStatus
from sehatraasta.services.correction_service import CorrectionService
from sehatraasta.services.recovery_service import RecoveryService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.file_service import FileService
from sehatraasta.storage.db import connect_database
from sehatraasta.web import create_app


@pytest.mark.parametrize('path,data', [
    ('medications/new', {'name':'Fictional stale medicine','strength':'1 mg','dose':'1 tablet','route':'By mouth','frequency':'Once a day','duration':'3 days','instructions':'','source':''}),
    ('attachments/new', {'file':(BytesIO(b'%PDF-1.4\nFictional stale upload'),'stale.pdf'),'category':'OTHER','date':'','source_type':'NOT_SUPPLIED','source':'','source_identifier':'','link':''}),
    ('context', {'medical_history':'Fictional stale context'})])
def test_old_add_form_cannot_write_after_wrong_patient_reassignment(case,path,data):
    service,_=case
    client=create_app({'TESTING':True,'DATABASE':service.repository.path}).test_client()
    url='/bundles/RB-002/'+path
    page=client.get(url)
    csrf=re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
    CorrectionService(service.repository.path).visit('RB-002',service.get_patient('PK-002')._storage_revision,
        patient_id='PK-001',facility='',destination='',date_kind='unknown',date_value=None)
    response=client.post(url,data={'csrf':csrf,**data})
    assert response.status_code==409
    assert 'changed' in response.text
    assert service.get_bundle('RB-002').medication_item==[]
    assert service.get_bundle('RB-002').attachments==[]
    assert len(list(FileService(service.repository.path).root.iterdir()))==1


@pytest.mark.parametrize('kind', ['order','instruction','encounter'])
def test_removed_integer_ids_are_reserved_after_entry_and_restart(case,kind):
    service,_=case
    def add(label):
        if kind=='order': service.add_order('RB-002',label,date(2026,1,2),'',InvestigationOrderStatus.ORDERED)
        elif kind=='instruction': service.add_instruction('RB-002','Follow-up',Language.ENGLISH,label,'',date(2026,1,2))
        else:
            patient=service.get_patient('PK-002')
            patient.referrals[0].encounters.append(Encounter(date(2026,1,2),label,'Fictional clinician',''))
            service.repository.save_patient(patient)
    add('Fictional old')
    group={'order':'investigation_orders','instruction':'instructions','encounter':'encounters'}[kind]
    old=getattr(service.get_bundle('RB-002'),group)[0]
    old_id=old._storage_id
    recovery=RecoveryService(service.repository.path)
    removed=recovery.remove_record(kind,old_id,service.get_patient('PK-002')._storage_revision)
    add('Fictional new')
    assert getattr(service.get_bundle('RB-002'),group)[0]._storage_id!=old_id
    RecoveryService(service.repository.path).restore(removed)
    records=getattr(service.get_bundle('RB-002'),group)
    assert len(records)==2
    assert len({item._storage_id for item in records})==2


def test_wrong_patient_snapshot_rejected_before_recovery_and_backup(case,tmp_path):
    service,_=case
    service.add_medication('RB-001',None,'Fictional original','1 mg','1 tablet','By mouth','Once a day','3 days','','')
    medicine=service.get_bundle('RB-001').medication_item[0]
    recovery=RecoveryService(service.repository.path)
    removed=recovery.remove_record('medication',medicine.ID,service.get_patient('PK-001')._storage_revision)
    connection=connect_database(service.repository.path)
    with connection:
        data=json.loads(connection.execute('SELECT snapshot FROM removed_items WHERE item_id=?',(removed,)).fetchone()[0])
        data['tables']['medication_items'][0]['bundle_id']='RB-002'
        connection.execute('UPDATE removed_items SET snapshot=? WHERE item_id=?',(json.dumps(data),removed))
    connection.close()
    with pytest.raises(ValueError): recovery.restore(removed)
    assert service.get_bundle('RB-002').medication_item==[]
    with pytest.raises(ValueError): DatasetBackupService(service.repository.path).create(tmp_path/'exports')


@pytest.mark.parametrize('kind,identifier',[('document','AT-001'),('visit','RB-001'),('patient','PK-001')])
def test_passport_cannot_bypass_retained_original_reservation(case,kind,identifier):
    service,_=case
    passport=PassportService(service.repository.path)
    content=passport.export('RB-001')
    RecoveryService(service.repository.path).remove(kind,identifier,service.get_patient('PK-001')._storage_revision)
    before=len(service.list_patients()),len(service.list_bundles()),len(list(FileService(service.repository.path).root.iterdir()))
    with pytest.raises(ValueError): passport.import_passport(content,confirmed=True)
    assert before==(len(service.list_patients()),len(service.list_bundles()),len(list(FileService(service.repository.path).root.iterdir())))


def test_lzma_dictionary_rejected_before_native_constructor(monkeypatch):
    from sehatraasta.services import archive_reader
    def forbidden(*args,**kwargs): pytest.fail('oversized dictionary reached native constructor')
    monkeypatch.setattr(archive_reader.lzma,'LZMADecompressor',forbidden)
    decoder=archive_reader._BoundedLZMA()
    header=b'\x09\x04\x05\x00\x5d'+(1<<30).to_bytes(4,'little')+b'x'
    with pytest.raises(Exception,match='dictionary'): decoder.decompress(header,1)


def test_nested_record_cannot_invent_missing_visit(case,tmp_path):
    service,_=case
    service.add_medication('RB-002',None,'Fictional nested','1 mg','1 tablet','By mouth','Once a day','3 days','','')
    recovery=RecoveryService(service.repository.path)
    recovery.remove_record('medication',service.get_bundle('RB-002').medication_item[0].ID,service.get_patient('PK-002')._storage_revision)
    parent=recovery.remove('patient','PK-002',service.get_patient('PK-002')._storage_revision)
    connection=connect_database(service.repository.path)
    with connection:
        data=json.loads(connection.execute('SELECT snapshot FROM removed_items WHERE item_id=?',(parent,)).fetchone()[0])
        child=data['tables']['removed_items'][0]
        child['parent_visit']='RB-999'
        nested=json.loads(child['snapshot']);nested['tables']['medication_items'][0]['bundle_id']='RB-999'
        child['snapshot']=json.dumps(nested)
        connection.execute('UPDATE removed_items SET snapshot=? WHERE item_id=?',(json.dumps(data),parent))
    connection.close()
    with pytest.raises(ValueError): recovery.restore(parent)
    with pytest.raises(ValueError):DatasetBackupService(service.repository.path).create(tmp_path/'exports')


def test_parent_removal_waits_for_partial_permanent_cleanup(case,tmp_path,monkeypatch):
    from pathlib import Path
    from datetime import datetime
    from sehatraasta.domain import AttachmentCategory,Provenance,ProvenanceType,ReferralStatus
    service,_=case;database=service.repository.path
    paper=tmp_path/'second.pdf';paper.write_bytes(b'%PDF-1.4\nFictional second original')
    FileService(database).import_file('RB-001','AT-002',paper,AttachmentCategory.OTHER,None,Provenance(ProvenanceType.NOT_SUPPLIED))
    service.create_bundle('PK-001','RB-003',datetime(2026,10,7),'','',ReferralStatus.DRAFT)
    service.add_medication('RB-003',None,'Fictional intact medicine','1 mg','1 tablet','By mouth','Once a day','3 days','','')
    recovery=RecoveryService(database)
    visit=recovery.remove('visit','RB-001',service.get_patient('PK-001')._storage_revision)
    connection=connect_database(database)
    originals=recovery.retained_files(connection);connection.close()
    locked=FileService(database)._path(originals[1]['stored_name'])
    original_unlink=Path.unlink
    def fail_one(path,*args,**kwargs):
        if path==locked: raise OSError('fictional locked file')
        return original_unlink(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',fail_one)
        assert recovery.permanent(visit)==1
    assert len(list(FileService(database).root.iterdir()))==1
    with pytest.raises(ValueError,match='cleanup'):
        recovery.remove('patient','PK-001',service.get_patient('PK-001')._storage_revision)
    assert recovery.list()[0]['state']=='purging'
    assert service.get_bundle('RB-003').medication_item[0].name=='Fictional intact medicine'
    assert recovery.permanent(visit)==0
    patient=recovery.remove('patient','PK-001',service.get_patient('PK-001')._storage_revision)
    recovery.restore(patient)
    assert service.get_bundle('RB-003').medication_item[0].name=='Fictional intact medicine'


def test_invalid_removed_domain_value_cannot_pass_backup(case,tmp_path):
    service,_=case
    service.add_medication('RB-002',None,'Fictional valid name','1 mg','1 tablet','By mouth','Once a day','3 days','','')
    recovery=RecoveryService(service.repository.path)
    removed=recovery.remove_record('medication',service.get_bundle('RB-002').medication_item[0].ID,service.get_patient('PK-002')._storage_revision)
    connection=connect_database(service.repository.path)
    with connection:
        data=json.loads(connection.execute('SELECT snapshot FROM removed_items WHERE item_id=?',(removed,)).fetchone()[0])
        data['tables']['medication_items'][0]['verbatim_name']=''
        connection.execute('UPDATE removed_items SET snapshot=? WHERE item_id=?',(json.dumps(data),removed))
    connection.close()
    with pytest.raises(ValueError):DatasetBackupService(service.repository.path).create(tmp_path/'exports')


def test_retained_result_and_order_dates_validated_together(case,tmp_path):
    service,_=case
    service.add_order('RB-002','Fictional linked order',date(2026,1,2),'',InvestigationOrderStatus.ORDERED)
    order=service.get_bundle('RB-002').investigation_orders[0]
    service.add_result('RB-002',None,'Fictional linked result',date(2026,1,2),'','',order.name)
    recovery=RecoveryService(service.repository.path)
    removed=recovery.remove('visit','RB-002',service.get_patient('PK-002')._storage_revision)
    connection=connect_database(service.repository.path)
    with connection:
        data=json.loads(connection.execute('SELECT snapshot FROM removed_items WHERE item_id=?',(removed,)).fetchone()[0])
        data['tables']['diagnostic_results'][0]['result_date']='2026-01-01'
        connection.execute('UPDATE removed_items SET snapshot=? WHERE item_id=?',(json.dumps(data),removed))
    connection.close()
    with pytest.raises(ValueError):DatasetBackupService(service.repository.path).create(tmp_path/'exports')
