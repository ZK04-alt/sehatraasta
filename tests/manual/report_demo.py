"""Isolated fictional dataset for automated browser checks; never normal instance."""
from datetime import datetime, date
from pathlib import Path
from tempfile import mkdtemp
from io import BytesIO

from PIL import Image
from sehatraasta.domain import Language, ReferralStatus, Provenance, ProvenanceType, AttachmentCategory
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.file_service import FileService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.web import create_app


def demo():
    Path('tmp').mkdir(exist_ok=True)
    root = Path(mkdtemp(prefix='report-fictional-', dir='tmp')).resolve()
    database = root / 'instance' / 'data.sqlite'
    service = BundleService(SQLiteRepository(database))
    service.create_patient('PK-001', 'Amina Demo', 1980, Language.URDU)
    service.create_patient('PK-002', 'Amina Demo', 1990, Language.ENGLISH)
    provenance = Provenance(ProvenanceType.NOT_SUPPLIED, None, None)
    for number in (1, 2, 3):
        visit = f'RB-00{number}'
        service.create_bundle('PK-001', visit, datetime(2026, 10, number, 10),
                              f'Demo clinic {number}', '', ReferralStatus.DRAFT)
    service.create_bundle('PK-002', 'RB-004', datetime(2026, 10, 4, 10),
                          'Other fictional patient clinic', '', ReferralStatus.DRAFT)
    for number, visit in ((1, 'RB-001'), (2, 'RB-001'), (3, 'RB-002'), (4, 'RB-004')):
        content = BytesIO()
        Image.new('RGB', (300, 400), (250, 250, 250 - number)).save(content, format='PNG')
        source = root / f'fictional-document-{number}.png'
        source.write_bytes(content.getvalue())
        FileService(database).import_file(visit, f'AT-00{number}', source,
            AttachmentCategory.OTHER, date(2026, 10, number), provenance)
    return create_app({'DATABASE': database, 'TESTING': False})


if __name__ == '__main__':
    demo().run(host='127.0.0.1', port=5091, debug=False, use_reloader=False)
