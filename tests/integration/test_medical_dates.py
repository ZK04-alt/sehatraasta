from datetime import date, datetime
import pytest

from sehatraasta.domain import AttachmentCategory, Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.db import connect_database


def test_optional_birth_year_and_facility_round_trip_without_invention(tmp_path):
    service = BundleService(SQLiteRepository(tmp_path / 'records.sqlite'))
    service.create_patient('PK-001', 'Fictional caregiver', None, Language.ENGLISH)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 10, 7), '', '', ReferralStatus.DRAFT)
    loaded = BundleService(SQLiteRepository(service.repository.path))
    assert loaded.get_patient('PK-001').birth_year is None
    assert loaded.get_bundle('RB-001').source_facility == ''
    assert loaded.get_bundle('RB-001').medical_date_kind == 'unknown'
    assert loaded.get_bundle('RB-001').medical_date_value is None


@pytest.mark.parametrize('kind,value', [('exact', '2026-09-12'), ('approximate', '2020'),
    ('approximate', '2020-02'), ('approximate', '2020-02-29'), ('unknown', None)])
def test_medical_date_keeps_only_supplied_precision(kind, value):
    from sehatraasta.domain.medical_dates import validate_medical_date
    assert validate_medical_date(kind, value) == (kind, value)


@pytest.mark.parametrize('kind,value', [('exact', None), ('exact', '2020'),
    ('exact', '2020-02'), ('exact', '2026-02-29'), ('unknown', '2026-10-07'),
    ('approximate', None), ('approximate', '2020-13'), ('approximate', '0000'),
    ('approximate', '20'), ('approximate', '2020-2'), ('estimated', '2020')])
def test_invalid_or_contradictory_date_is_rejected(kind, value):
    from sehatraasta.domain.medical_dates import validate_medical_date
    with pytest.raises(ValueError):
        validate_medical_date(kind, value)


def test_v15_timestamp_not_reinterpreted_as_medical_date(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[1] / 'compatibility'))
    from legacy_fixtures import database
    path = database(tmp_path / 'legacy')
    before = connect_database(path)
    stamp = before.execute('SELECT creation_time FROM referral_bundles WHERE bundle_id=?', ('RB-001',)).fetchone()[0]
    before.close()
    visit = BundleService(SQLiteRepository(path)).get_bundle('RB-001')
    assert visit.creation_time.isoformat() == stamp
    assert visit.medical_date_kind == 'unknown'
    assert visit.medical_date_value is None
    assert visit.attachments[0].date == date(2026, 9, 12)


def test_new_archives_have_explicit_versions_and_keep_uncertain_date(tmp_path):
    from io import BytesIO
    import json
    from zipfile import ZipFile
    from sehatraasta.services.dataset_backup import DatasetBackupService
    from sehatraasta.services.passport_service import PassportService
    path = tmp_path / 'records.sqlite'
    service = BundleService(SQLiteRepository(path))
    service.create_patient('PK-001', 'Fictional', None, Language.ENGLISH)
    service.create_bundle('PK-001', 'RB-001', datetime(2026, 10, 7), '', '', ReferralStatus.DRAFT)
    patient = service.get_patient('PK-001')
    patient.referrals[0].medical_date_kind = 'approximate'
    patient.referrals[0].medical_date_value = '2020-02'
    service.repository.save_patient(patient)
    passport = PassportService(path).export('RB-001')
    with ZipFile(BytesIO(passport)) as archive:
        assert json.loads(archive.read('passport.json'))['version'] == 3
    receiver = tmp_path / 'receiver.sqlite'
    SQLiteRepository(receiver)
    imported = PassportService(receiver).import_passport(passport, confirmed=True)
    visit = BundleService(SQLiteRepository(receiver)).get_bundle(imported)
    assert (visit.medical_date_kind, visit.medical_date_value) == ('approximate', '2020-02')
    backup = DatasetBackupService(path)
    name = backup.create(tmp_path / 'exports')
    with ZipFile(tmp_path / 'exports' / name) as archive:
        document = json.loads(archive.read('dataset.json'))
        assert document['version'] == 4
        assert document['format'] == 'sehatraasta-backup'
    backup.restore(tmp_path / 'exports' / name, tmp_path / 'restore', confirmed=True)
    visit = BundleService(SQLiteRepository(tmp_path / 'restore/sehatraasta.sqlite')).get_bundle('RB-001')
    assert (visit.medical_date_kind, visit.medical_date_value) == ('approximate', '2020-02')


def test_json_archive_new_writer_declares_version_and_reads_legacy(tmp_path):
    import json
    from sehatraasta.storage.repositories import JsonRepository
    path = tmp_path / 'fictional.json'
    path.write_text(json.dumps({'format_version': 1, 'synthetic_only': True, 'patients': []}))
    service = BundleService(JsonRepository(path))
    service.create_patient('PK-001', 'Fictional no demographics', None, Language.ENGLISH)
    document = json.loads(path.read_text())
    assert document['format_version'] == 2
    assert JsonRepository(path).get_patient('PK-001').birth_year is None
    document['format_version'] = 99
    path.write_text(json.dumps(document))
    before = path.read_bytes()
    from sehatraasta.storage.errors import StorageError
    with pytest.raises(StorageError):
        JsonRepository(path)
    assert path.read_bytes() == before
