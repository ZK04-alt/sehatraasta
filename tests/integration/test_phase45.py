import base64
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import re
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image
import zxingcpp

from sehatraasta.cli import main
from sehatraasta.domain import (
    AttachmentCategory, CostCategory, InvestigationOrderStatus, Language,
    PresenceState, Provenance, ProvenanceType, ReferralStatus, ReviewCategory,
)
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.dataset_backup import DatasetBackupService, read_tables
from sehatraasta.services.file_service import FileService
from sehatraasta.services.print_service import PrintService
from sehatraasta.services.qr_service import QRService, verify_payload
from sehatraasta.storage.db import connect_database, initialize_database, MIGRATION_PATH
from sehatraasta.storage.errors import StorageError
from sehatraasta.storage.sqlite_repository import SQLiteRepository


# Public synthetic test bytes, created only in pytest temporary directories.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")


@pytest.fixture
def case(tmp_path):
    database = tmp_path / "instance" / "sehatraasta.sqlite"
    bundles = BundleService(SQLiteRepository(database))
    bundles.create_patient("SR-DEMO-001", "Amina Demo", 1980, Language.URDU)
    bundles.create_bundle("SR-DEMO-001", "SR-DEMO-001", datetime(2026, 9, 12, 12),
                          "Demo BHU", "Demo District Hospital - Orthopaedics", ReferralStatus.DRAFT)
    bundles.add_medication("SR-DEMO-001", "MD-001", "Fictional example", "demo strength", "demo dose", "demo route", "demo frequency", "demo duration", "Fictional instructions only", "source not supplied")
    bundles.add_order("SR-DEMO-001", "Demo X-ray", date(2026, 9, 12), "source not supplied", InvestigationOrderStatus.ORDERED)
    bundles.add_result("SR-DEMO-001", "RS-001", "Demo result", date(2026, 9, 12), "Demo source", "Fictional result", "Demo X-ray")
    bundles.add_instruction("SR-DEMO-001", "demo", Language.ENGLISH, "Synthetic instruction", "source not supplied", date(2026, 9, 12))
    bundles.add_imaging("SR-DEMO-001", "IM-001", "X-ray", "Demo part", date(2026, 9, 12), "Demo facility", "Fictional report", None)
    bundles.add_cost("SR-DEMO-001", "CO-001", CostCategory.TRAVEL, Decimal("2500.10"), date(2026, 9, 12), "demo interview response")
    bundles.set_category_review("SR-DEMO-001", ReviewCategory.MEDICATION_LIST, PresenceState.PRESENT, "Demo reviewer", datetime(2026, 9, 12, 12), "Synthetic review")
    source = tmp_path / "PublicSynthetic.PNG"
    source.write_bytes(PNG)
    return database, bundles, FileService(database), source


def upload(case, **kwargs):
    database, bundles, files, source = case
    return files.import_file("SR-DEMO-001", "AT-001", source, AttachmentCategory.IMAGING_IMAGE,
                             date(2026, 9, 12), Provenance(ProvenanceType.NOT_SUPPLIED), synthetic=True, **kwargs)


def rows(database):
    connection = connect_database(database, read_only=True)
    try:
        return read_tables(connection)
    finally:
        connection.close()


def test_v1_upgrade_preserves_records(tmp_path):
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(MIGRATION_PATH.read_text())
    connection.execute("INSERT INTO patients(patient_id,display_name,birth_year,language) VALUES ('PK-001','Demo',1980,'URDU')")
    connection.commit()
    connection.close()
    initialize_database(database)
    initialize_database(database)
    assert SQLiteRepository(database).get_patient("PK-001").name == "Demo"
    assert [row["version"] for row in rows(database)["schema_version"]] == [1, 2]


@pytest.mark.parametrize("extension,content,mime", [
    ("pdf", b"%PDF-1.4\n% synthetic signature fixture", "application/pdf"),
    ("png", PNG, "image/png"),
    ("jpg", b"\xff\xd8\xff\xe0synthetic signature fixture", "image/jpeg"),
    ("jpeg", b"\xff\xd8\xff\xe0synthetic signature fixture", "image/jpeg"),
])
def test_allowed_intake_measures_hash_and_uses_generated_name(case, extension, content, mime):
    database, bundles, files, source = case
    source = source.with_suffix("." + extension)
    source.write_bytes(content)
    upload((database, bundles, files, source))
    attachment = bundles.get_bundle("SR-DEMO-001").attachments[0]
    assert attachment.name == source.name
    assert attachment.generated_stored_name != source.name
    assert attachment.sha == hashlib.sha256(content).hexdigest()
    assert attachment.size == len(content)
    assert files.retrieve("AT-001") == (content, mime)


@pytest.mark.parametrize("content", [b"", b"plain text", b"%PDF-wrong extension", PNG + b"x" * 5242880], ids=["empty", "text", "wrong-type", "oversized"])
def test_rejection_changes_no_rows_or_files(case, content):
    database, bundles, files, source = case
    source.write_bytes(content)
    before = rows(database)
    with pytest.raises(ValueError):
        upload(case)
    assert rows(database) == before
    assert not files.root.exists()


def test_synthetic_confirmation_required(case):
    database, bundles, files, source = case
    before = rows(database)
    with pytest.raises(ValueError, match="synthetic"):
        files.import_file("SR-DEMO-001", "AT-001", source, AttachmentCategory.OTHER, date.today(), Provenance(ProvenanceType.NOT_SUPPLIED))
    assert rows(database) == before


def test_duplicate_bytes_different_name_rejected(case):
    database, bundles, files, source = case
    upload(case)
    before = rows(database)
    another = source.with_name("Another.png")
    another.write_bytes(PNG)
    with pytest.raises(ValueError, match="duplicate attachment content"):
        files.import_file("SR-DEMO-001", "AT-002", another, AttachmentCategory.OTHER, date.today(), Provenance(ProvenanceType.NOT_SUPPLIED), True)
    assert rows(database) == before
    assert len(list(files.root.iterdir())) == 1


@pytest.mark.parametrize("link", ["order_id", "instruction_id", "result_id", "imaging_id", "medication_list"])
def test_links_and_audit_survive_normal_save_and_restart(case, link):
    database, bundles, files, source = case
    bundle = bundles.get_bundle("SR-DEMO-001")
    values = {"order_id": bundle.investigation_orders[0]._storage_id,
              "instruction_id": bundle.instructions[0]._storage_id,
              "result_id": "RS-001", "imaging_id": "IM-001", "medication_list": True}
    upload(case, **{link: values[link]})
    before = rows(database)["managed_attachments"]
    bundles.update_bundle(bundle.ID, "Demo new source", "Demo destination", ReferralStatus.DRAFT)
    assert rows(database)["managed_attachments"] == before
    assert len(FileService(database).audit.list_events(bundle.ID)) == 1
    assert FileService(database).retrieve("AT-001")[0] == PNG


def test_cross_bundle_link_and_two_targets_rejected(case):
    database, bundles, files, source = case
    bundles.create_bundle("SR-DEMO-001", "SR-DEMO-002", datetime.now(), "Demo", "Demo", ReferralStatus.DRAFT)
    bundles.add_order("SR-DEMO-002", "Other", date.today(), "Demo", InvestigationOrderStatus.ORDERED)
    other = bundles.get_bundle("SR-DEMO-002").investigation_orders[0]._storage_id
    before = rows(database)
    with pytest.raises(ValueError, match="link"):
        upload(case, order_id=other)
    with pytest.raises(ValueError, match="at most one"):
        upload(case, result_id="RS-001", medication_list=True)
    assert rows(database) == before
    assert not files.root.exists()


def test_interrupted_import_rolls_back_rows_and_file(case, monkeypatch):
    database, bundles, files, source = case
    before = rows(database)
    def fail(*args):
        raise sqlite3.OperationalError("injected failure")
    monkeypatch.setattr(files.audit, "record", fail)
    with pytest.raises(StorageError):
        upload(case)
    assert rows(database) == before
    assert list(files.root.iterdir()) == []


def test_missing_file_is_audited_on_read_and_delete(case):
    database, bundles, files, source = case
    upload(case)
    next(files.root.iterdir()).unlink()
    with pytest.raises(ValueError, match="missing"):
        files.retrieve("AT-001")
    assert files.delete("AT-001") == "missing"
    assert [row["outcome"] for row in files.audit.list_events("SR-DEMO-001")] == ["success", "missing", "missing"]
    assert bundles.get_bundle("SR-DEMO-001").attachments == []


def test_tampered_file_not_returned(case):
    database, bundles, files, source = case
    upload(case)
    next(files.root.iterdir()).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        files.retrieve("AT-001")
    assert files.audit.list_events("SR-DEMO-001")[-1]["outcome"] == "integrity failure"


def test_reconciliation_removes_only_generated_orphans(case):
    database, bundles, files, source = case
    upload(case)
    orphan = files.root / ("a" * 32 + ".pdf")
    orphan.write_bytes(b"interrupted write")
    unrelated = files.root / "do-not-touch.txt"
    unrelated.write_text("unrelated")
    assert files.reconcile() == 1
    assert unrelated.read_text() == "unrelated"
    assert files.retrieve("AT-001")[0] == PNG


def test_interrupted_delete_is_reconciled(case, monkeypatch):
    database, bundles, files, source = case
    upload(case)
    original = Path.unlink
    def fail(path, *args, **kwargs):
        if path.parent == files.root:
            raise OSError("injected failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail)
    with pytest.raises(StorageError, match="reconciliation"):
        files.delete("AT-001")
    assert bundles.get_bundle("SR-DEMO-001").attachments == []
    monkeypatch.setattr(Path, "unlink", original)
    assert files.reconcile() == 1


def test_audit_has_no_content_filename_or_path(case):
    database, bundles, files, source = case
    upload(case)
    files.retrieve("AT-001")
    text = json.dumps(files.audit.list_events("SR-DEMO-001"))
    for forbidden in ("Amina", "PublicSynthetic", str(source), "Fictional", "Demo District"):
        assert forbidden not in text


def test_qr_payload_is_nonsensitive_and_stable(case):
    database, bundles, files, source = case
    service = QRService(database)
    payload = service.for_bundle("SR-DEMO-001")
    assert payload == service.for_bundle("SR-DEMO-001")
    data = json.loads(payload)
    assert set(data) == {"id", "v", "check"}
    assert len(data["id"]) == 32
    assert service.lookup(payload) == "SR-DEMO-001"
    assert service.lookup_short(data["id"][:12]) == "SR-DEMO-001"
    for forbidden in ("Amina", "1980", "SR-DEMO", "Hospital", str(database)):
        assert forbidden not in payload
    data["id"] = ("0" if data["id"][0] != "0" else "1") + data["id"][1:]
    with pytest.raises(ValueError, match="altered"):
        verify_payload(json.dumps(data))


@pytest.mark.parametrize("payload", ["", "{}", "null", "[]", "not json", '{"v":true,"id":"x","check":"x"}'])
def test_invalid_qr_rejected(payload):
    with pytest.raises(ValueError):
        verify_payload(payload)


def test_print_is_offline_escaped_and_exact(case, tmp_path):
    database, bundles, files, source = case
    upload(case, medication_list=True)
    patient = bundles.get_patient("SR-DEMO-001")
    patient.referrals[0].instructions[0].text = "<script>alert('x')</script> " + "long fictional text " * 100
    bundles.repository.save_patient(patient)
    output = tmp_path / "summary.html"
    PrintService(bundles).export("SR-DEMO-001", output)
    html = output.read_text(encoding="utf-8")
    assert "PKR 2,500.10" in html
    assert "not reviewed" in html and "present" in html
    assert "AT-001" in html and "source document not supplied" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "width:30mm" in html and "data:image/png;base64," in html
    assert "@media print" in html and "@page" in html
    assert html.count("SYNTHETIC ONLY") == html.count('<section class="page">')
    assert "http://" not in html and "https://" not in html and str(database.parent) not in html


def test_backup_dry_run_restore_all_rows_hashes_and_tokens(case, tmp_path):
    database, bundles, files, source = case
    upload(case, result_id="RS-001")
    token = QRService(database).for_bundle("SR-DEMO-001")
    backup = DatasetBackupService(database)
    folder = tmp_path / "backups"
    name = backup.create(folder)
    name2 = backup.create(folder)
    assert name != name2
    before = rows(database)
    summary = backup.dry_run(folder / name)
    assert summary["total_paisa"] == 250010
    assert summary["attachments"] == 1
    assert rows(database) == before
    destination = tmp_path / "restored"
    assert backup.restore(folder / name, destination, True) == summary
    restored = destination / "sehatraasta.sqlite"
    assert rows(restored) == before
    assert QRService(restored).lookup(token) == "SR-DEMO-001"
    assert FileService(restored).retrieve("AT-001")[0] == PNG
    new_bundles = BundleService(SQLiteRepository(restored))
    assert new_bundles.total_cost_pkr("SR-DEMO-001") == Decimal("2500.10")
    assert "PKR 2,500.10" in PrintService(new_bundles).render("SR-DEMO-001")


@pytest.mark.parametrize("attack", ["badzip", "tamper", "traversal", "duplicate", "unknown-table"])
def test_corrupt_backup_preserves_current_data(case, tmp_path, attack):
    database, bundles, files, source = case
    upload(case)
    service = DatasetBackupService(database)
    folder = tmp_path / "backups"
    archive = folder / service.create(folder)
    with ZipFile(archive) as original:
        members = {name: original.read(name) for name in original.namelist()}
    if attack == "badzip":
        archive.write_bytes(b"invalid")
    else:
        if attack == "tamper":
            members["dataset.json"] += b"x"
        if attack == "traversal":
            members["../escape.txt"] = b"bad"
        if attack == "unknown-table":
            document = json.loads(members["dataset.json"])
            document["tables"]["patients; DROP TABLE patients"] = []
            members["dataset.json"] = json.dumps(document).encode()
            manifest = json.loads(members["manifest.json"])
            manifest["dataset.json"] = hashlib.sha256(members["dataset.json"]).hexdigest()
            members["manifest.json"] = json.dumps(manifest).encode()
        with ZipFile(archive, "w") as changed:
            for name, content in members.items():
                changed.writestr(name, content)
            if attack == "duplicate":
                with pytest.warns(UserWarning):
                    changed.writestr("dataset.json", members["dataset.json"])
    before = rows(database)
    with pytest.raises(ValueError):
        service.dry_run(archive)
    with pytest.raises(ValueError):
        service.restore(archive, tmp_path / "bad-restore", True)
    assert rows(database) == before
    assert not (tmp_path / "bad-restore").exists()
    assert FileService(database).retrieve("AT-001")[0] == PNG


def test_cli_no_storage_paths_and_source_not_supplied(case, tmp_path, capsys):
    database, bundles, files, source = case
    base = ["--database", str(database)]
    assert main(base + ["import-file", "--bundle-id", "SR-DEMO-001", "--id", "AT-001", "--file", str(source), "--category", "other", "--date", "2026-09-12", "--synthetic"]) == 0
    assert main(base + ["list-files", "--bundle-id", "SR-DEMO-001"]) == 0
    assert main(base + ["download-file", "--id", "AT-001", "--output", str(tmp_path / "download.png")]) == 0
    assert main(base + ["print-bundle", "--bundle-id", "SR-DEMO-001", "--output", str(tmp_path / "print.html")]) == 0
    captured = capsys.readouterr()
    assert str(database.parent) not in captured.out + captured.err
    assert "source not supplied" in captured.out


def test_qr_image_independently_decodes_in_grayscale(case):
    database, bundles, files, source = case
    html = PrintService(bundles).render("SR-DEMO-001")
    image = Image.open(BytesIO(base64.b64decode(re.search(r"base64,([^\"]+)", html).group(1)))).convert("L")
    decoded = zxingcpp.read_barcode(image)
    assert decoded is not None
    assert QRService(database).lookup(decoded.text) == "SR-DEMO-001"


@pytest.mark.parametrize("name", ["CON.pdf", "report.pdf.png", "report.exe.pdf", "LPT1.png", "test:stream.pdf", "report.png.jpg"])
def test_reserved_and_double_extension_names_rejected(name):
    from sehatraasta.services.attachment_validation import validate_attachment_filename
    with pytest.raises(ValueError):
        validate_attachment_filename(name)


def test_import_disk_failure_rolls_back(case, monkeypatch):
    database, bundles, files, source = case
    before = rows(database)
    import sehatraasta.services.file_service as module
    def fail(*args):
        raise OSError("injected flush failure")
    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(StorageError):
        upload(case)
    assert rows(database) == before
    assert list(files.root.iterdir()) == []


def test_failed_cleanup_can_be_reconciled(case, monkeypatch):
    database, bundles, files, source = case
    before = rows(database)
    original = Path.unlink
    def fail_audit(*args):
        raise sqlite3.OperationalError("injected")
    def fail_unlink(path, *args, **kwargs):
        if path.parent == files.root:
            raise OSError("injected")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(files.audit, "record", fail_audit)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(StorageError):
        upload(case)
    assert rows(database) == before
    assert len(list(files.root.iterdir())) == 1
    monkeypatch.setattr(Path, "unlink", original)
    assert files.reconcile() == 1


def test_ordinary_save_cannot_erase_link_target_or_change_file_metadata(case):
    database, bundles, files, source = case
    target = bundles.get_bundle("SR-DEMO-001").instructions[0]._storage_id
    upload(case, instruction_id=target)
    before = rows(database)
    patient = bundles.get_patient("SR-DEMO-001")
    patient.referrals[0].instructions.clear()
    with pytest.raises(ValueError):
        bundles.repository.save_patient(patient)
    assert rows(database) == before
    patient = bundles.get_patient("SR-DEMO-001")
    patient.referrals[0].attachments[0].size += 1
    with pytest.raises(ValueError, match="metadata"):
        bundles.repository.save_patient(patient)
    assert rows(database) == before


def test_old_patient_snapshot_cannot_overwrite_new_attachment(case):
    database, bundles, files, source = case
    patient = bundles.get_patient("SR-DEMO-001")
    upload(case)
    with pytest.raises(ValueError, match="reload"):
        bundles.repository.save_patient(patient)
    assert files.retrieve("AT-001")[0] == PNG


def test_backup_missing_file_rejected_without_partial_archive(case, tmp_path):
    database, bundles, files, source = case
    upload(case)
    next(files.root.iterdir()).unlink()
    folder = tmp_path / "backups"
    with pytest.raises(StorageError):
        DatasetBackupService(database).create(folder)
    assert list(folder.iterdir()) == []


def test_restore_requires_confirmation_and_new_folder(case, tmp_path):
    database, bundles, files, source = case
    backup = DatasetBackupService(database)
    folder = tmp_path / "backups"
    archive = folder / backup.create(folder)
    with pytest.raises(ValueError, match="confirm"):
        backup.restore(archive, tmp_path / "new")
    with pytest.raises(ValueError, match="new folder"):
        backup.restore(archive, database.parent, True)


def test_three_cases_exact_totals_after_restore(case, tmp_path):
    database, bundles, files, source = case
    for number, amount in [(2, "0.10"), (3, "123.45")]:
        ID = f"SR-DEMO-00{number}"
        bundles.create_patient(ID, "Fictional Person", 1980, Language.ENGLISH)
        bundles.create_bundle(ID, ID, datetime.now(), "Demo clinic", "Demo hospital", ReferralStatus.DRAFT)
        bundles.add_cost(ID, f"CO-00{number}", CostCategory.TRAVEL, Decimal(amount), date.today(), "Demo interview")
    backup = DatasetBackupService(database)
    folder = tmp_path / "backups"
    archive = folder / backup.create(folder)
    backup.restore(archive, tmp_path / "restored", True)
    restored = BundleService(SQLiteRepository(tmp_path / "restored" / "sehatraasta.sqlite"))
    for number, amount in [(1, "2500.10"), (2, "0.10"), (3, "123.45")]:
        ID = f"SR-DEMO-00{number}"
        assert restored.total_cost_pkr(ID) == Decimal(amount)
        assert f"PKR {Decimal(amount):,.2f}" in PrintService(restored).render(ID)


def test_linked_storage_folder_rejected(case, monkeypatch):
    database, bundles, files, source = case
    before = rows(database)
    original = Path.is_junction
    monkeypatch.setattr(Path, "is_junction", lambda path: path == files.root or original(path))
    with pytest.raises(StorageError, match="unsafe"):
        upload(case)
    assert rows(database) == before


def test_extended_attachment_id_round_trips(case):
    database, bundles, files, source = case
    files.import_file("SR-DEMO-001", "AT-DEMO-001", source, AttachmentCategory.OTHER,
                      date.today(), Provenance(ProvenanceType.NOT_SUPPLIED), True)
    assert bundles.get_bundle("SR-DEMO-001").attachments[0].ID == "AT-DEMO-001"
