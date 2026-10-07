"""Future archives must fail before current records or files change."""
from datetime import datetime
from io import BytesIO
import hashlib
import json
from zipfile import ZipFile,ZIP_DEFLATED
import pytest
from sehatraasta.domain import Language,ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.storage import SQLiteRepository


@pytest.mark.parametrize('kind',['backup','passport'])
@pytest.mark.parametrize('version',[99,True,1])
def test_future_or_contradictory_format_is_atomic(tmp_path,kind,version):
    database=tmp_path/'instance'/'data.sqlite'
    service=BundleService(SQLiteRepository(database))
    service.create_patient('PK-001','Fictional version guard',None,Language.ENGLISH)
    service.create_bundle('PK-001','RB-001',datetime(2026,10,7),'','',ReferralStatus.DRAFT)
    if kind=='backup':
        name=DatasetBackupService(database).create(tmp_path/'exports')
        raw=(tmp_path/'exports'/name).read_bytes()
    else: raw=PassportService(database).export('RB-001')
    with ZipFile(BytesIO(raw)) as archive:
        members={name:archive.read(name) for name in archive.namelist() if name!='manifest.json'}
    key='dataset.json' if kind=='backup' else 'passport.json'
    data=json.loads(members[key]);data['version']=version
    members[key]=json.dumps(data).encode()
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps({name:hashlib.sha256(content).hexdigest() for name,content in members.items()}))
        for name,content in members.items():archive.writestr(name,content)
    before=database.read_bytes()
    if kind=='backup':
        path=tmp_path/'future.zip';path.write_bytes(output.getvalue())
        with pytest.raises(ValueError):DatasetBackupService(database).restore(path,tmp_path/'restored',confirmed=True)
        assert not (tmp_path/'restored').exists()
    else:
        with pytest.raises(ValueError):PassportService(database).import_passport(output.getvalue(),confirmed=True)
    assert database.read_bytes()==before
    assert len(service.list_patients())==1
