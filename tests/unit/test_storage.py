import json
from datetime import datetime

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services import BundleService
from sehatraasta.storage import JsonRepository, StorageError
from sehatraasta.storage.repositories import write_json_safely


def test_missing_development_file_starts_empty(tmp_path):
    repository = JsonRepository(tmp_path / "development.json")

    assert repository.list_patients() == []


def test_three_synthetic_cases_can_be_created_from_clean_folder(tmp_path):
    path = tmp_path / "clean" / "development.json"
    repository = JsonRepository(path)
    service = BundleService(repository)
    cases = [
        ("SR-DEMO-001", "Amina Demo", 1980, Language.URDU, "RB-001"),
        ("SR-DEMO-002", "Bilal Demo", 1975, Language.PASHTO, "RB-002"),
        ("SR-DEMO-003", "Sara Demo", 1990, Language.ENGLISH, "RB-003"),
    ]
    for patient_id, name, birth_year, language, bundle_id in cases:
        service.create_patient(patient_id, name, birth_year, language)
        service.create_bundle(
            patient_id,
            bundle_id,
            datetime(2026, 8, 30, 10, 0),
            "Synthetic source clinic",
            "Synthetic destination hospital",
            ReferralStatus.DRAFT,
        )

    restarted = JsonRepository(path)

    assert [patient.ID for patient in restarted.list_patients()] == [
        "SR-DEMO-001",
        "SR-DEMO-002",
        "SR-DEMO-003",
    ]
    restarted_service = BundleService(restarted)
    assert [bundle.ID for _, bundle in restarted_service.list_bundles()] == [
        "RB-001",
        "RB-002",
        "RB-003",
    ]


def test_valid_file_is_backed_up_before_replacement(tmp_path):
    path = tmp_path / "development.json"
    first = {"format_version": 1, "synthetic_only": True, "patients": []}
    second = {
        "format_version": 1,
        "synthetic_only": True,
        "patients": [
            {
                "ID": "SR-DEMO-001",
                "name": "Amina Demo",
                "birth_year": 1980,
                "language": "URDU",
                "referral_bundles": [],
            }
        ],
    }
    write_json_safely(path, first)
    write_json_safely(path, second)

    backup = path.with_name(path.name + ".bak")

    assert json.loads(backup.read_text(encoding="utf-8")) == first
    assert json.loads(path.read_text(encoding="utf-8")) == second


def test_corrupt_file_is_rejected_and_not_overwritten(tmp_path):
    path = tmp_path / "development.json"
    path.write_text("not valid json", encoding="utf-8")

    with pytest.raises(StorageError, match="invalid or corrupt development file"):
        JsonRepository(path)

    assert path.read_text(encoding="utf-8") == "not valid json"


def test_safe_writer_does_not_replace_corrupt_existing_file(tmp_path):
    path = tmp_path / "export.json"
    path.write_text("last file is corrupt", encoding="utf-8")

    with pytest.raises(StorageError, match="could not safely write development file"):
        write_json_safely(path, {"replacement": True})

    assert path.read_text(encoding="utf-8") == "last file is corrupt"


def test_invalid_decimal_in_development_file_is_reported_as_storage_error(tmp_path):
    path = tmp_path / "development.json"
    document = {
        "format_version": 1,
        "synthetic_only": True,
        "patients": [
            {
                "ID": "SR-DEMO-001",
                "name": "Amina Demo",
                "birth_year": 1980,
                "language": "URDU",
                "referral_bundles": [
                    {
                        "ID": "RB-001",
                        "creation_time": "2026-08-30T10:00:00",
                        "source_facility": "Demo BHU",
                        "destination": "Demo Hospital",
                        "status": "DRAFT",
                        "cost_entries": [
                            {
                                "ID": "CO-001",
                                "category": "TRAVEL",
                                "amount_pkr": "not money",
                                "date": "2026-08-30",
                                "source": "synthetic source",
                                "note": "",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(StorageError, match="invalid or corrupt development file"):
        JsonRepository(path)
