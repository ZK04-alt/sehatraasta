"""Capture fictional compatibility inputs using immutable v1.5 source only.

Run with PYTHONPATH=tmp/v15-source/src after git archive of the baseline tag.
The committed fixture is text. SQLite/ZIP artifacts stay in ignored tmp/.
"""
import base64
from datetime import date, datetime
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from sehatraasta.domain import (AttachmentCategory, CostCategory,
    InvestigationOrderStatus, Language, Provenance, ProvenanceType, ReferralStatus)
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.export_service import ExportService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService
from sehatraasta.storage import SQLiteRepository

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def archive_text(content):
    with ZipFile(BytesIO(content)) as archive:
        return {name: json.loads(archive.read(name)) if name.endswith('.json') else
                {'hex': archive.read(name).hex()} for name in archive.namelist()}


def capture():
    import sehatraasta
    source = Path(sehatraasta.__file__).resolve().parent
    if source.parts[-3:] != ('v15-source', 'src', 'sehatraasta'):
        raise RuntimeError('Use the archived baseline source, never the candidate')
    root = Path('tmp/v15-compatibility').resolve()
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'records.sqlite'
    service = BundleService(SQLiteRepository(database))
    service.create_patient('PK-001', 'Amina Fictional Legacy', 1980, Language.URDU)
    service.create_patient('PK-002', 'Family Fictional Legacy', 1990, Language.ENGLISH)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 9, 12, 12, 34),
                          'Fictional legacy clinic', '', ReferralStatus.DRAFT)
    service.create_bundle('PK-001', 'RB-002', datetime(2026, 9, 19, 9),
                          'Fictional later clinic', 'Fictional hospital', ReferralStatus.DRAFT)
    service.add_medication('RB-001', 'MD-001', 'Fictional medicine', '10 mg', '1 tablet',
                           '', 'As supplied', 'As supplied', '', '')
    service.add_order('RB-001', 'Fictional test', date(2026, 9, 12), '', InvestigationOrderStatus.ORDERED)
    service.add_result('RB-001', 'RS-001', 'Fictional result', date(2026, 9, 12), '',
                       'Fictional supplied text', 'Fictional test')
    service.add_instruction('RB-001', 'Fictional instruction', Language.ENGLISH,
                            'Fictional text only', '', date(2026, 9, 12))
    service.add_imaging('RB-001', 'IM-001', 'X-ray', 'Fictional part', date(2026, 9, 12),
                       'Fictional clinic', 'Fictional report', None)
    service.add_cost('RB-001', 'CO-001', CostCategory.TRAVEL, Decimal('25.10'),
                    date(2026, 9, 12), 'Fictional supplied source')
    original = root / 'fictional-original.png'
    original.write_bytes(PNG)
    FileService(database).import_file('RB-001', 'AT-001', original,
        AttachmentCategory.OTHER, date(2026, 9, 12), Provenance(ProvenanceType.NOT_SUPPLIED))
    ReferralContextService(database).save('RB-001', {'medical_history': 'Fictional legacy history'})
    UnfinishedVisitService(database).save({'mode': ['existing'], 'patient_id': ['PK-001'],
        'source_facility': ['Interrupted fictional visit'], 'medications.rows': ['0'],
        'medications.0.name': ['Fictional unfinished text']})
    passport = PassportService(database).export('RB-001')
    (root / 'passport-v15.zip').write_bytes(passport)
    backup_name = DatasetBackupService(database).create(root / 'exports')
    export = ExportService(service).export_bundle('RB-001', root / 'export-v15.json')
    fixture = {'source_commit': '0b29581c0df6ea0cdcbeef9d6f0a71148816387f',
        'baseline_apk_sha256': '5ec0fd925def500fb7250234e54f22f2fecaf207d68c2918fc7ee7fb6c8631f0',
        'migrations': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((source / 'storage/migrations').glob('00*.sql'))},
        'migrations_lf': {path.name: hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for path in sorted((source / 'storage/migrations').glob('00*.sql'))},
        'backup': archive_text((root / 'exports' / backup_name).read_bytes()),
        'passport': archive_text(passport), 'export': json.loads(export.read_text(encoding='utf-8'))}
    target = Path('tests/compatibility/v15_artifacts.json')
    target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Captured v1.5 database, backup, passport, JSON export and unfinished work; fictional text fixture:', target)


if __name__ == '__main__':
    capture()
