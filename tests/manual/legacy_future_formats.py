"""Prove archived baseline readers reject actual current archives atomically.

Run with PYTHONPATH=src. This uses isolated fictional databases and immutable
Git source, not the packaged APK. All generated artifacts stay in ignored tmp.
"""
from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp
from zipfile import ZipFile

from sehatraasta.domain import Language, Patient, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.repositories import JsonRepository
from sehatraasta.storage.errors import StorageError


def main():
    root=Path(mkdtemp(prefix='legacy-future-proof-',dir='tmp')).resolve()
    commit=json.loads(Path('tests/compatibility/v15_artifacts.json').read_text())['source_commit']
    archived=subprocess.check_output(['git','archive','--format=zip',commit,'src'])
    with ZipFile(BytesIO(archived)) as archive:
        archive.extractall(root/'legacy')  # trusted fixed Git tree, not user input
    database=root/'candidate'/'data.sqlite'
    service=BundleService(SQLiteRepository(database))
    service.create_patient('PK-001','Fictional future archive',None,Language.ENGLISH)
    service.create_bundle('PK-001','RB-001',datetime(2026,10,7),'','',ReferralStatus.DRAFT)
    backup=DatasetBackupService(database).create(root/'exports')
    backup=root/'exports'/backup
    passport=root/'passport.zip';passport.write_bytes(PassportService(database).export('RB-001'))
    development=root/'current-development.json'
    JsonRepository(development).add_patient(Patient('PK-002','Fictional development format',None,Language.ENGLISH))
    for version in (99,True):
        value=json.loads(development.read_text());value['format_version']=version
        future=root/('future-development-'+str(version)+'.json');future.write_text(json.dumps(value))
        before=future.read_bytes()
        try:JsonRepository(future)
        except StorageError:pass
        else:raise AssertionError('future development JSON accepted')
        assert future.read_bytes()==before
    code='''
from datetime import datetime
from pathlib import Path
import sys
from sehatraasta.domain import Language,ReferralStatus
from sehatraasta.storage import SQLiteRepository
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.storage.repositories import JsonRepository
from sehatraasta.storage.errors import StorageError
root=Path(sys.argv[1]);database=root/'old'/'data.sqlite'
s=BundleService(SQLiteRepository(database))
s.create_patient('PK-901','Fictional preserved baseline',1980,Language.ENGLISH)
s.create_bundle('PK-901','RB-901',datetime(2020,1,2),'Fictional legacy clinic','',ReferralStatus.DRAFT)
before=database.read_bytes()
for kind,operation in [
 ('backup',lambda:DatasetBackupService(database).restore(Path(sys.argv[2]),root/'rejected-restore',confirmed=True)),
 ('passport',lambda:PassportService(database).import_passport(Path(sys.argv[3]).read_bytes(),confirmed=True))]:
 try: operation()
 except ValueError: pass
 else: raise AssertionError(kind+' current archive accepted by baseline reader')
 assert database.read_bytes()==before
 assert s.get_patient('PK-901').name=='Fictional preserved baseline'
 assert not (root/'rejected-restore').exists()
 print('PASS: actual current '+kind+' rejected; baseline database unchanged')
development=Path(sys.argv[4]);before=development.read_bytes()
try:JsonRepository(development)
except StorageError:pass
else:raise AssertionError('current development JSON accepted by baseline reader')
assert development.read_bytes()==before
print('PASS: actual current development JSON rejected unchanged by baseline reader; current future/bool JSON guards also verified')
'''
    environment=os.environ.copy();environment['PYTHONPATH']=str(root/'legacy'/'src')
    subprocess.run([sys.executable,'-c',code,str(root),str(backup),str(passport),str(development)],env=environment,check=True)
    Path('tmp/current-future-proof-root.txt').write_text(str(root))
    print('Archived source commit:',commit,'Evidence directory:',root)


if __name__=='__main__':main()
