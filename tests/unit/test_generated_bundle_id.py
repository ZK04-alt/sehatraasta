from datetime import datetime
import re

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.cli import main


def service_at(path):
    service = BundleService(SQLiteRepository(path))
    service.create_patient('PK-001', 'Amina Demo', 1980, Language.URDU)
    return service


def create(service, ID=None):
    return service.create_bundle('PK-001', ID, datetime(2026, 9, 22),
                                 'Demo BHU', 'Demo Hospital', ReferralStatus.DRAFT)


def test_generated_ids_survive_restart(tmp_path):
    path = tmp_path / 'demo.sqlite'
    service = service_at(path)
    first = create(service)
    second = create(service)
    assert first.ID != second.ID
    assert re.fullmatch(r'SR-[A-Z]{12}-[0-9]{3}', first.ID)
    restarted = BundleService(SQLiteRepository(path))
    assert [bundle.ID for bundle in restarted.get_patient('PK-001').referrals] == [first.ID, second.ID]


def test_collision_tries_another_id(tmp_path, monkeypatch):
    service = service_at(tmp_path / 'demo.sqlite')
    create(service, 'SR-AAAAAAAAAAAA-000')
    letters = iter('A' * 12 + 'B' * 12)
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: next(letters))
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.randbelow', lambda _: 0)
    assert create(service).ID == 'SR-BBBBBBBBBBBB-000'
    assert len(service.list_bundles()) == 2


def test_repeated_collision_is_bounded_and_keeps_existing_data(tmp_path, monkeypatch):
    service = service_at(tmp_path / 'demo.sqlite')
    create(service, 'SR-AAAAAAAAAAAA-000')
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: 'A')
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.randbelow', lambda _: 0)
    with pytest.raises(StorageError):
        create(service)
    assert len(service.list_bundles()) == 1


def test_cli_can_omit_bundle_id(tmp_path, capsys):
    path = tmp_path / 'demo.sqlite'
    service = service_at(path)
    assert main(['--database', str(path), 'create-bundle', '--patient-id', 'PK-001',
                 '--created', '2026-09-22T12:00', '--source', 'Demo BHU',
                 '--destination', 'Demo Hospital']) == 0
    bundle = service.list_bundles()[0][1]
    assert bundle.ID in capsys.readouterr().out
