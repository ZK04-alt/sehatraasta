"""Generate public fictional passports in a new folder; never touch app data."""
import argparse
import base64
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

# Allow the helper to run directly from a checkout without a package install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sehatraasta.domain import (
    AttachmentCategory, CostCategory, InvestigationOrderStatus, Language,
    PresenceState, Provenance, ProvenanceType, ReferralStatus, ReviewCategory,
)
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.print_service import PrintService
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.storage import SQLiteRepository

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def generate(folder):
    folder = Path(folder)
    if folder.exists():
        raise ValueError('choose a new output folder; existing files will not be overwritten')
    folder.mkdir(parents=True)
    with TemporaryDirectory(prefix='sr-public-cases-') as name:
        root = Path(name)
        for index, (person, year, language, department) in enumerate([
            ('Amina Example', 1980, Language.URDU, 'Orthopaedics'),
            ('Bilal Example', 1975, Language.PASHTO, 'Outpatient clinic'),
            ('Sana Example', 1992, Language.ENGLISH, 'General outpatient clinic'),
        ], start=1):
            database = root / str(index) / 'sehatraasta.sqlite'
            service = BundleService(SQLiteRepository(database))
            key = f'SR-CASE-{index:03d}'
            service.create_patient(key, person, year, language)
            service.create_bundle(key, key, datetime(2026, 10, 2, 9), 'Example BHU' if index == 1 else 'Example RHC' if index == 2 else 'Example Clinic',
                'Example District Hospital' if index < 3 else 'Example Hospital', ReferralStatus.DRAFT)
            context = {'department': department, 'source': 'Public fictional case sheet'}
            if index == 1:
                context.update(medical_history='Example previous clinic visit; no real medical history.',
                    referral_reason='Example follow-up requested by the referring clinic.',
                    referral_notes='Bring the supplied example record to the next clinic.', follow_up_date='2026-10-16')
                service.add_medication(key, 'MD-001', 'Example medicine', 'example strength', 'as supplied', '', 'as supplied', 'as supplied',
                    'Fictional text copied from an example sheet. Not a prescription.', 'Public fictional case sheet')
                service.add_order(key, 'Example X-ray', date(2026, 10, 2), 'Public fictional case sheet', InvestigationOrderStatus.ORDERED)
                costs = [('2500.10', CostCategory.TRAVEL)]
                reviews = [(ReviewCategory.MEDICATION_LIST, PresenceState.PRESENT),
                    (ReviewCategory.DIAGNOSTIC_RESULTS, PresenceState.PENDING), (ReviewCategory.IMAGING_REPORTS, PresenceState.PENDING)]
            elif index == 2:
                context.update(medical_history='Fictional follow-up case.', referral_reason='Fictional follow-up case.')
                service.add_order(key, 'Example blood test', date(2026, 10, 2), 'Public fictional case sheet', InvestigationOrderStatus.COMPLETED)
                service.add_result(key, 'DR-001', 'Example blood test', date(2026, 10, 2), 'Public fictional case sheet',
                    'Fictional result; no clinical interpretation.', 'Example blood test')
                service.add_instruction(key, 'Follow-up', language, 'Carry the example report to the next visit.', 'Public fictional case sheet', date(2026, 10, 2))
                costs = [('400.25', CostCategory.TRAVEL), ('600.50', CostCategory.INVESTIGATION)]
                reviews = [(ReviewCategory.DIAGNOSTIC_RESULTS, PresenceState.PRESENT), (ReviewCategory.MEDICATION_LIST, PresenceState.NOT_APPLICABLE)]
            else:
                context['referral_reason'] = 'Details not supplied.'
                costs = []
                reviews = [(ReviewCategory.MEDICATION_LIST, PresenceState.MISSING), (ReviewCategory.DIAGNOSTIC_RESULTS, PresenceState.NOT_APPLICABLE)]
            ReferralContextService(database).save(key, context)
            for cost_index, (amount, category) in enumerate(costs, start=1):
                service.add_cost(key, f'CE-{cost_index:03d}', category, Decimal(amount), date(2026, 10, 2),
                    'Public fictional case sheet', '', 'reported', 'CASE-' + 'ABC'[index - 1])
            for category, state in reviews:
                service.set_category_review(key, category, state, 'Example reviewer', datetime(2026, 10, 2, 9), 'Public fictional review')
            source = root / f'public-synthetic-case-{index}.png'
            source.write_bytes(PNG + f'Public fictional case {index}'.encode())
            FileService(database).import_file(key, 'AT-001', source, AttachmentCategory.OTHER,
                date(2026, 10, 2), Provenance(ProvenanceType.NOT_SUPPLIED))
            passport = PassportService(database)
            content = passport.export(key)
            assert passport.preview(content)['patient'] == person
            (folder / f'case-{index}.zip').write_bytes(content)
            (folder / f'case-{index}-print.html').write_text(PrintService(service).render(key), encoding='utf-8')
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='output/pilot-kit/' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    destination = generate(parser.parse_args().output)
    print('Created three public fictional passports and print summaries in', destination)
