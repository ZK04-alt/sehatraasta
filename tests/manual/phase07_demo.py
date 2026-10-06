"""Create three fictional cases in a NEW database. Never overwrite a dataset."""
import argparse
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sehatraasta.domain import Language, ReferralStatus, ReviewCategory, PresenceState, CostCategory, InvestigationOrderStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository


def create_demo(database):
    database = Path(database)
    if database.exists():
        raise ValueError('Choose a new database filename. Existing data was not changed.')
    service = BundleService(SQLiteRepository(database))
    cases = [('PK-001', 'SR-DEMO-001', 'Amina Demo', Language.URDU),
             ('PK-002', 'SR-DEMO-002', 'Bilal Demo', Language.PASHTO),
             ('PK-003', 'SR-DEMO-003', 'Sara Demo', Language.ENGLISH)]
    for patient_id, bundle_id, name, language in cases:
        service.create_patient(patient_id, name, 1980, language)
        service.create_bundle(patient_id, bundle_id, datetime(2026, 9, 21, 9),
            'Demo BHU', 'Demo District Hospital - Orthopaedics', ReferralStatus.DRAFT)
    service.add_medication('SR-DEMO-001', 'MD-001', 'Fictional medicine A', 'As written',
        'Fictional dose text', 'As written', 'As written', 'As written',
        'Synthetic wording only. Not a medication instruction for real use.', 'Demo prescription sheet')
    service.add_order('SR-DEMO-001', 'Demo X-ray', date(2026, 9, 21), 'Demo sheet', InvestigationOrderStatus.ORDERED)
    for category, state in [(ReviewCategory.MEDICATION_LIST, PresenceState.PRESENT),
                            (ReviewCategory.DIAGNOSTIC_RESULTS, PresenceState.PENDING),
                            (ReviewCategory.IMAGING_REPORTS, PresenceState.PENDING)]:
        service.set_category_review('SR-DEMO-001', category, state, 'Demo reviewer', datetime(2026, 9, 21, 10), 'Fictional review')
    service.add_cost('SR-DEMO-001', 'CE-001', CostCategory.TRAVEL, Decimal('2500.00'), date(2026, 9, 21),
                     'demo interview response', source_type='reported', source_identifier='DEMO-INTERVIEW-001')
    service.add_instruction('SR-DEMO-002', 'Demo note', Language.URDU,
        'اصل متن ABC-123. دا یوه فرضي بېلګه ده. ' + 'Long fictional source wording. ' * 35,
        'Synthetic source only', date(2026, 9, 21))
    service.set_category_review('SR-DEMO-002', ReviewCategory.ATTACHMENTS, PresenceState.MISSING,
                               'Demo reviewer', datetime(2026, 9, 21, 10), 'No synthetic copy supplied')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    create_demo(args.database)
    print('Three fictional cases created. No existing database was overwritten.')
