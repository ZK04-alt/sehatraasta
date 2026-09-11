from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from sehatraasta.cli import main
from sehatraasta.domain import (
    Attachment, AuditEvent, CategoryReview, CostCategory, CostEntry,
    DiagnosticResult, Encounter, ImagingItem, Instruction,
    InvestigationOrder, InvestigationOrderStatus, Language, MedicationItem,
    Patient, PresenceState, ReferralBundle, ReferralStatus, ReviewCategory,
)
from sehatraasta.services import BundleService, ExportService
from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.storage import db
from sehatraasta.storage.db import (
    backup_database, check_database, connect_database,
    initialize_database, restore_database,
)
from sehatraasta.storage.repositories import patient_to_dict
from sehatraasta.storage.sqlite_repository import amount_to_paisa


def make_patient():
    patient = Patient("SR-DEMO-001", "Amina Demo", 1980, Language.URDU)
    bundle = ReferralBundle(
        "RB-001", datetime(2026, 9, 5, 10), "Demo BHU",
        "Demo District Hospital", ReferralStatus.DRAFT,
    )
    patient.add_referral(bundle)
    bundle.add_encounter(Encounter(date(2026, 9, 5), "Demo BHU", "Dr Demo", "Demo note"))
    bundle.add_medication(MedicationItem(
        "Demo medicine", "10 mg", "one tablet", "oral", "once daily",
        "one day", "Fictional instructions", "Demo prescription", "MD-001",
    ))
    bundle.add_instruction(Instruction("follow-up", Language.URDU, "Demo text", "Demo source", date(2026, 9, 5)))
    bundle.add_attachment(Attachment(
        "AT-001", "imaging", "demo.png", "image/png", "a" * 64,
        date(2026, 9, 5), "Demo scan", 1200, "reserved-demo.png",
    ))
    bundle.add_imaging_item(ImagingItem(
        "X-ray", "knee", date(2026, 9, 5), "Demo BHU", "Demo report", "IM-001", "AT-001",
    ))
    order = InvestigationOrder("X-ray", date(2026, 9, 5), "Demo BHU", InvestigationOrderStatus.ORDERED)
    bundle.add_investigation_order(order)
    bundle.add_diagnostic_result(DiagnosticResult(
        "X-ray result", date(2026, 9, 5), "Demo source", "DR-001", "Demo report", order,
    ))
    bundle.add_cost_entry(CostEntry(
        "CO-001", CostCategory.TRAVEL, Decimal("2500.10"), date(2026, 9, 5),
        "Demo interview response", "", "interview", "SR-RESPONSE-001", "Demo respondent",
    ))
    bundle.add_cost_entry(CostEntry(
        "CO-002", CostCategory.CONSULTATION, Decimal("0.20"), date(2026, 9, 5), "Demo receipt",
    ))
    bundle.add_category_review(CategoryReview(
        ReviewCategory.MEDICATION_LIST, PresenceState.PRESENT, "Demo reviewer",
        datetime(2026, 9, 5, 11), "Demo review",
    ))
    bundle.add_audit_event(AuditEvent(datetime(2026, 9, 5, 12), "created", "bundle", "AU-001", "Demo user", "success"))
    return patient


def test_initialization_is_repeatable_and_foreign_keys_enabled(tmp_path):
    path = tmp_path / "new" / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    initialize_database(path)
    initialize_database(path)
    connection = connect_database(path)
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert [row[0] for row in connection.execute("SELECT version FROM schema_version ORDER BY version")] == [1, 2]
        assert connection.execute("SELECT count(*) FROM patients").fetchone()[0] == 1
        check_database(connection)
    finally:
        connection.close()


def test_every_record_round_trips_after_restart(tmp_path):
    path = tmp_path / "database.sqlite"
    original = make_patient()
    SQLiteRepository(path).add_patient(original)
    restored = SQLiteRepository(path).get_patient(original.ID)
    assert patient_to_dict(restored) == patient_to_dict(original)
    bundle = restored.referrals[0]
    assert bundle.diagnostic_results[0].investigation_order is bundle.investigation_orders[0]
    assert bundle.total_cost_pkr() == Decimal("2500.30")
    assert isinstance(bundle.cost_entries[0].amount, Decimal)


def test_update_and_list_survive_new_repository(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    service = BundleService(SQLiteRepository(path))
    service.update_bundle("RB-001", "Updated Demo BHU", "Updated Demo Hospital", ReferralStatus.READY_FOR_REVIEW)
    service.create_bundle("SR-DEMO-001", "RB-002", datetime(2026, 9, 5), "Second Demo BHU", "Second Demo Hospital", ReferralStatus.DRAFT)
    restarted = BundleService(SQLiteRepository(path))
    assert [bundle.ID for _, bundle in restarted.list_bundles()] == ["RB-001", "RB-002"]
    assert restarted.get_bundle("RB-001").destination == "Updated Demo Hospital"
    assert restarted.get_bundle("RB-001").status == ReferralStatus.READY_FOR_REVIEW
    assert restarted.total_cost_pkr("RB-001") == Decimal("2500.30")


def test_stale_save_is_rejected(tmp_path):
    path = tmp_path / "database.sqlite"
    repository = SQLiteRepository(path)
    repository.add_patient(make_patient())
    first = repository.get_patient("SR-DEMO-001")
    stale = repository.get_patient("SR-DEMO-001")
    first.name = "Updated Demo"
    repository.save_patient(first)
    stale.name = "Stale Demo"
    with pytest.raises(ValueError, match="reload"):
        SQLiteRepository(path).save_patient(stale)
    assert repository.get_patient(first.ID).name == "Updated Demo"


def test_failed_multi_bundle_save_rolls_back_every_record(tmp_path, monkeypatch):
    path = tmp_path / "database.sqlite"
    repository = SQLiteRepository(path)
    repository.add_patient(make_patient())
    before = patient_to_dict(repository.get_patient("SR-DEMO-001"))
    original_writer = repository._write_bundle

    def fail_after_writing(connection, patient_id, bundle):
        original_writer(connection, patient_id, bundle)
        raise sqlite3.OperationalError("synthetic medical text must not enter logs")

    monkeypatch.setattr(repository, "_write_bundle", fail_after_writing)
    service = BundleService(repository)
    with pytest.raises(StorageError, match="no changes"):
        service.create_bundle("SR-DEMO-001", "RB-002", datetime(2026, 9, 5), "Demo", "Demo", ReferralStatus.DRAFT)
    assert patient_to_dict(SQLiteRepository(path).get_patient("SR-DEMO-001")) == before
    log = (tmp_path / "storage-errors.log").read_text()
    assert "OperationalError" in log
    assert "save_patient" in log
    assert "medical text" not in log
    assert "Amina" not in log


def test_failed_new_patient_save_leaves_no_partial_patient(tmp_path, monkeypatch):
    repository = SQLiteRepository(tmp_path / "database.sqlite")
    original_writer = repository._write_bundle

    def fail_after_writing(connection, patient_id, bundle):
        original_writer(connection, patient_id, bundle)
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(repository, "_write_bundle", fail_after_writing)
    with pytest.raises(StorageError):
        repository.add_patient(make_patient())
    assert repository.list_patients() == []


def test_failed_migration_leaves_no_partial_schema(tmp_path, monkeypatch):
    migration = tmp_path / "broken.sql"
    migration.write_text("BEGIN TRANSACTION;\nCREATE TABLE partial (id INTEGER);\nINVALID SQL;\nCOMMIT;\n")
    monkeypatch.setattr(db, "MIGRATION_PATH", migration)
    path = tmp_path / "database.sqlite"
    with pytest.raises(StorageError):
        initialize_database(path)
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    finally:
        connection.close()


def test_backup_restore_preserves_all_records_and_exact_costs(tmp_path):
    source = tmp_path / "database.sqlite"
    repository = SQLiteRepository(source)
    repository.add_patient(make_patient())
    before = patient_to_dict(repository.get_patient("SR-DEMO-001"))
    backup = backup_database(source, tmp_path / "backups" / "first.sqlite")
    BundleService(repository).add_cost("RB-001", "CO-003", CostCategory.TRAVEL, Decimal("1.23"), date(2026, 9, 5), "Demo source")
    restored = restore_database(backup, tmp_path / "restored.sqlite")
    for path in (backup, restored):
        result = SQLiteRepository(path).get_patient("SR-DEMO-001")
        assert patient_to_dict(result) == before
        assert result.referrals[0].total_cost_pkr() == Decimal("2500.30")
        connection = connect_database(path, read_only=True)
        try:
            check_database(connection)
            assert connection.execute("SELECT sum(amount_paisa) FROM cost_entries").fetchone()[0] == 250030
        finally:
            connection.close()
    assert BundleService(repository).total_cost_pkr("RB-001") == Decimal("2501.53")


def test_restore_rejects_corrupt_backup_without_touching_current_data(tmp_path):
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"synthetic corrupt data")
    current = tmp_path / "current.sqlite"
    SQLiteRepository(current).add_patient(make_patient())
    before = current.read_bytes()
    with pytest.raises(ValueError):
        restore_database(corrupt, current)
    new = tmp_path / "new.sqlite"
    with pytest.raises(StorageError):
        restore_database(corrupt, new)
    assert not new.exists()
    assert current.read_bytes() == before
    assert corrupt.read_bytes() == b"synthetic corrupt data"


def test_backup_rejects_existing_destination(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    with pytest.raises(ValueError):
        backup_database(path, path)
    existing = tmp_path / "keep.sqlite"
    existing.write_bytes(b"keep")
    with pytest.raises(ValueError):
        backup_database(path, existing)
    assert existing.read_bytes() == b"keep"


@pytest.mark.parametrize("content", [b"corrupt", b'{"format_version":1,"synthetic_only":true,"patients":[]}'])
def test_non_sqlite_file_is_preserved(tmp_path, content):
    path = tmp_path / "database.sqlite"
    path.write_bytes(content)
    with pytest.raises(StorageError):
        SQLiteRepository(path)
    assert path.read_bytes() == content


def test_future_version_is_rejected_without_reinitialization(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    connection = sqlite3.connect(path)
    with connection:
        connection.execute("UPDATE schema_version SET version = 99 WHERE version = 2")
    connection.close()
    before = path.read_bytes()
    with pytest.raises(StorageError):
        SQLiteRepository(path)
    assert path.read_bytes() == before


def test_sql_injection_text_is_stored_as_text(tmp_path):
    repository = SQLiteRepository(tmp_path / "database.sqlite")
    patient = make_patient()
    patient.name = "Demo'); DROP TABLE patients; --"
    repository.add_patient(patient)
    assert repository.get_patient(patient.ID).name == patient.name
    assert repository.get_patient("' OR 1=1 --") is None
    assert len(repository.list_patients()) == 1


@pytest.mark.parametrize("value", [Decimal("0.001"), Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("92233720368547758.08"), Decimal("1E+999999"), Decimal("1E-999999"), 1.5, True])
def test_amount_conversion_rejects_invalid_or_inexact_values(value):
    with pytest.raises(ValueError):
        amount_to_paisa(value)


def test_amount_conversion_is_exact_at_integer_limit():
    assert amount_to_paisa(Decimal("92233720368547758.07")) == 9223372036854775807
    assert amount_to_paisa(Decimal("0.10")) == 10


def test_invalid_cost_save_preserves_previous_records(tmp_path):
    repository = SQLiteRepository(tmp_path / "database.sqlite")
    repository.add_patient(make_patient())
    service = BundleService(repository)
    with pytest.raises(ValueError, match="whole paisa"):
        service.add_cost("RB-001", "CO-003", CostCategory.TRAVEL, Decimal("1.001"), date(2026, 9, 5), "Demo")
    assert service.total_cost_pkr("RB-001") == Decimal("2500.30")


def test_optional_links_become_null_and_remaining_records_can_be_loaded(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    connection = connect_database(path)
    try:
        with connection:
            connection.execute("DELETE FROM attachments WHERE attachment_id = ?", ("AT-001",))
            connection.execute("DELETE FROM investigation_orders WHERE bundle_id = ?", ("RB-001",))
    finally:
        connection.close()
    bundle = SQLiteRepository(path).get_patient("SR-DEMO-001").referrals[0]
    assert bundle.imaging_items[0].Attachment_ID is None
    assert bundle.diagnostic_results[0].investigation_order is None


def test_patient_delete_cascades_to_all_owned_records(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    connection = connect_database(path)
    try:
        with connection:
            connection.execute("DELETE FROM patients WHERE patient_id = ?", ("SR-DEMO-001",))
        for table in db.TABLE_NAMES - {"schema_version"}:
            # Table names come only from the fixed developer-owned schema list.
            assert connection.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_cross_bundle_links_rejected(tmp_path):
    path = tmp_path / "database.sqlite"
    repository = SQLiteRepository(path)
    repository.add_patient(make_patient())
    BundleService(repository).create_bundle("SR-DEMO-001", "RB-002", datetime(2026, 9, 5), "Demo", "Demo", ReferralStatus.DRAFT)
    connection = connect_database(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE imaging_items SET bundle_id = ? WHERE imaging_id = ?", ("RB-002", "IM-001"))
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE diagnostic_results SET bundle_id = ? WHERE result_id = ?", ("RB-002", "DR-001"))
    finally:
        connection.close()


def test_cli_maintenance_and_export(tmp_path, capsys):
    path = tmp_path / "database.sqlite"
    args = ["--database", str(path)]
    assert main(args + ["init-db"]) == 0
    SQLiteRepository(path).add_patient(make_patient())
    output = tmp_path / "export.json"
    assert main(args + ["export-bundle", "--bundle-id", "RB-001", "--output", str(output)]) == 0
    payload = json.loads(output.read_text())
    assert Decimal(payload["total_cost_pkr"]) == Decimal("2500.30")
    assert payload["bundle"]["cost_entries"][0]["source_identifier"] == "SR-RESPONSE-001"
    assert main(args + ["export-bundle", "--bundle-id", "RB-001", "--output", str(path)]) == 2
    backup = tmp_path / "backup.sqlite"
    assert main(args + ["backup-db", "--output", str(backup)]) == 0
    restored = tmp_path / "restored.sqlite"
    assert main(args + ["restore-db", "--backup", str(backup), "--output", str(restored)]) == 0
    assert main(args + ["update-bundle", "--bundle-id", "RB-001", "--source", "Demo", "--destination", "Updated Demo", "--status", "archived"]) == 0
    assert BundleService(SQLiteRepository(path)).get_bundle("RB-001").destination == "Updated Demo"
    assert BundleService(SQLiteRepository(restored)).get_bundle("RB-001").destination == "Demo District Hospital"


def test_three_cases_survive_a_separate_python_process(tmp_path):
    path = tmp_path / "database.sqlite"
    service = BundleService(SQLiteRepository(path))
    for number, name in enumerate(("Amina Demo", "Bilal Demo", "Sara Demo"), start=1):
        patient_id = f"SR-DEMO-{number:03d}"
        service.create_patient(patient_id, name, 1980, Language.URDU)
        service.create_bundle(patient_id, f"RB-{number:03d}", datetime(2026, 9, 5), "Demo BHU", "Demo Hospital", ReferralStatus.DRAFT)
    result = subprocess.run(
        [sys.executable, "-m", "sehatraasta.cli", "--database", str(path), "list-bundles"],
        cwd=Path(__file__).parents[2] / "src", capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert all(f"RB-{number:03d}" in result.stdout for number in (1, 2, 3))


def test_snapshot_matches_migration():
    assert db.MIGRATION_PATH.read_bytes() == db.MIGRATION_PATH.parent.parent.joinpath("schema.sql").read_bytes()


def test_locked_database_returns_storage_exit_code(tmp_path, capsys):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    connection = connect_database(path)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        assert main(["--database", str(path), "list-bundles"]) == 3
        error = capsys.readouterr().err
        assert "Storage error:" in error
        assert "Amina" not in error
    finally:
        connection.rollback()
        connection.close()
    assert len(SQLiteRepository(path).list_patients()) == 1
    assert "SQLITE_BUSY" in (tmp_path / "storage-errors.log").read_text()


def test_nullable_text_ids_and_fractional_paisa_are_rejected(tmp_path):
    path = tmp_path / "database.sqlite"
    SQLiteRepository(path).add_patient(make_patient())
    connection = connect_database(path)
    try:
        for value in (None,):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO patients (patient_id, display_name, birth_year, language) VALUES (?, ?, ?, ?)", (value, "Demo", 1980, "URDU"))
            connection.rollback()
        for value in (1.5, "not a number", -1):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("UPDATE cost_entries SET amount_paisa = ? WHERE cost_entry_id = ?", (value, "CO-001"))
            connection.rollback()
        assert connection.execute("SELECT amount_paisa FROM cost_entries WHERE cost_entry_id = 'CO-001'").fetchone()[0] == 250010
    finally:
        connection.close()


def test_duplicate_child_id_does_not_remove_existing_bundles(tmp_path):
    repository = SQLiteRepository(tmp_path / "database.sqlite")
    repository.add_patient(make_patient())
    patient = repository.get_patient("SR-DEMO-001")
    second = ReferralBundle("RB-002", datetime(2026, 9, 5), "Demo", "Demo", ReferralStatus.DRAFT)
    second.add_medication(patient.referrals[0].medication_item[0])
    patient.add_referral(second)
    with pytest.raises(ValueError, match="duplicate ID"):
        repository.save_patient(patient)
    restored = repository.get_patient(patient.ID)
    assert [bundle.ID for bundle in restored.referrals] == ["RB-001"]
    assert restored.referrals[0].medication_item[0].ID == "MD-001"


def test_parent_move_cannot_create_cross_bundle_links(tmp_path):
    path = tmp_path / "database.sqlite"
    repository = SQLiteRepository(path)
    repository.add_patient(make_patient())
    BundleService(repository).create_bundle("SR-DEMO-001", "RB-002", datetime(2026, 9, 5), "Demo", "Demo", ReferralStatus.DRAFT)
    connection = connect_database(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE attachments SET bundle_id = ?", ("RB-002",))
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE investigation_orders SET bundle_id = ?", ("RB-002",))
    finally:
        connection.close()


def test_backup_missing_source_does_not_create_empty_database(tmp_path):
    source = tmp_path / "missing.sqlite"
    target = tmp_path / "backup.sqlite"
    with pytest.raises(StorageError):
        backup_database(source, target)
    assert not source.exists()
    assert not target.exists()


def test_export_cannot_replace_database_through_a_hardlink(tmp_path):
    database = tmp_path / "database.sqlite"
    repository = SQLiteRepository(database)
    repository.add_patient(make_patient())
    alias = tmp_path / "alias.json"
    alias.hardlink_to(database)
    with pytest.raises(ValueError, match="separate"):
        ExportService(BundleService(repository)).export_bundle("RB-001", alias)
    assert repository.get_patient("SR-DEMO-001") is not None
