"""Identical isolated fictional starting states for five automated browser scenarios.

The fixture is test tooling, not shipped app behavior. No reset control is
exposed in the product; each persona receives its own fresh server/database.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Thread
from time import sleep
from PIL import Image, ImageDraw
from werkzeug.serving import make_server
from report_demo import demo
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.services.correction_service import CorrectionService
from sehatraasta.services.recovery_service import RecoveryService
from sehatraasta.services.file_service import FileService
from sehatraasta.domain import CostCategory


def fixture():
    app = demo()
    service = BundleService(SQLiteRepository(app.config['DATABASE']))
    edits = CorrectionService(service.repository.path)
    for visit, facility, kind, value in [('RB-001', 'Fictional Clinic', 'exact', '2024-05-12'),
                                         ('RB-002', 'Fictional Clinic', 'approximate', '2024-06')]:
        edits.visit(visit, service.get_patient('PK-001')._storage_revision,
                    patient_id='PK-001', facility=facility, destination='', date_kind=kind, date_value=value)
    for identifier, name, destination in [('AT-001', 'older-note.png', 'RB-001'),
                                           ('AT-002', 'followup-note.png', 'RB-002'),
                                           ('AT-003', 'accidentally-removed.png', 'RB-002'),
                                           ('AT-004', 'wrong-family-paper.png', 'RB-004')]:
        owner = 'PK-002' if identifier == 'AT-004' else 'PK-001'
        edits.document(identifier, service.get_patient(owner)._storage_revision,
                       name=name, category='other', document_date=None, destination_visit=destination)
    recovery = RecoveryService(service.repository.path)
    recovery.remove('document', 'AT-003', service.get_patient('PK-001')._storage_revision)
    service.add_cost('RB-001', 'CE-001', CostCategory.TRAVEL, Decimal('125.50'), date(2024, 5, 12), '', 'Fictional unrelated cost')
    return app


if __name__ == '__main__':
    upload = Path('tmp/final-persona-undated.png')
    paper = Image.new('RGB', (420, 600), 'white')
    ImageDraw.Draw(paper).text((20, 30), 'FICTIONAL PAPER\nAmina Demo, born 1980\nDate unreadable', fill='black')
    paper.save(upload)
    for port in range(5092, 5097):
        server = make_server('127.0.0.1', port, fixture())
        Thread(target=server.serve_forever, daemon=True).start()
        print(f'Fresh fictional persona fixture: http://127.0.0.1:{port}', flush=True)
    while True:
        sleep(1)
