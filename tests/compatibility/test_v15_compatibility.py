from datetime import datetime
from decimal import Decimal
import json

from legacy_fixtures import archive, database, fixture
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.repositories import _bundle_from_dict


def assert_legacy_information(path, visit_id='RB-001'):
    service = BundleService(SQLiteRepository(path))
    patient, visit = service.get_bundle_owner(visit_id)
    assert patient.name == 'Amina Fictional Legacy'
    assert patient.birth_year == 1980
    assert visit.creation_time == datetime(2026, 9, 12, 12, 34)
    assert visit.medication_item[0].name == 'Fictional medicine'
    assert visit.diagnostic_results[0].investigation_order is visit.investigation_orders[0]
    assert visit.total_cost_pkr() == Decimal('25.10')
    assert FileService(path).retrieve(visit.attachments[0].ID)[0].startswith(b'\x89PNG')


def test_actual_v15_database_and_unfinished_work_read_before_and_after_upgrade(tmp_path):
    path = database(tmp_path / 'legacy')
    assert_legacy_information(path)
    assert_legacy_information(path)  # migration/startup is idempotent
    drafts = UnfinishedVisitService(path).list()
    assert len(drafts) == 1
    fields = UnfinishedVisitService(path).get(drafts[0]['draft_id'])['fields']
    assert fields['medications.0.name'] == ['Fictional unfinished text']


def test_actual_v15_backup_restores_records_original_and_draft(tmp_path):
    source = tmp_path / 'backup-v15.zip'
    source.write_bytes(archive('backup'))
    candidate = tmp_path / 'active.sqlite'
    SQLiteRepository(candidate)
    service = DatasetBackupService(candidate)
    service.dry_run(source)
    destination = tmp_path / 'restored'
    service.restore(source, destination, confirmed=True)
    assert_legacy_information(destination / 'sehatraasta.sqlite')
    assert len(UnfinishedVisitService(destination / 'sehatraasta.sqlite').list()) == 1


def test_actual_v15_passport_imports_without_merging_or_losing_original(tmp_path):
    path = tmp_path / 'receiver.sqlite'
    SQLiteRepository(path)
    service = PassportService(path)
    content = archive('passport')
    assert service.preview(content)['patient'] == 'Amina Fictional Legacy'
    imported = service.import_passport(content, confirmed=True)
    assert_legacy_information(path, imported)
    assert UnfinishedVisitService(path).list() == []


def test_actual_v15_json_export_domain_reading_preserves_supplied_information():
    exported = fixture()['export']
    visit = _bundle_from_dict(exported['bundle'])
    assert visit.creation_time.isoformat() == '2026-09-12T12:34:00'
    assert visit.attachments[0].name == 'fictional-original.png'
    assert visit.total_cost_pkr() == Decimal('25.10')
