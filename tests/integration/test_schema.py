import sqlite3
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "sehatraasta"
    / "storage"
    / "migrations"
    / "001_initial.sql"
)

EXPECTED_TABLES = {
    "schema_version",
    "patients",
    "referral_bundles",
    "audit_events",
    "instructions",
    "cost_entries",
    "attachments",
    "imaging_items",
    "medication_items",
    "encounters",
    "category_reviews",
    "investigation_orders",
    "diagnostic_results",
}


def create_database(tmp_path):
    database_path = tmp_path / "sehatraasta.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    connection.executescript(migration)
    return connection


def add_patient_and_bundle(connection):
    connection.execute(
        """
        INSERT INTO patients (
            patient_id, display_name, birth_year, language
        ) VALUES (?, ?, ?, ?)
        """,
        ("SR-DEMO-001", "Amina Demo", 1980, "URDU"),
    )
    connection.execute(
        """
        INSERT INTO referral_bundles (
            bundle_id,
            patient_id,
            creation_time,
            source_facility,
            destination,
            referral_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "RB-001",
            "SR-DEMO-001",
            "2026-09-02T10:00:00",
            "Demo BHU",
            "Demo District Hospital",
            "DRAFT",
        ),
    )
    connection.commit()


def test_initial_migration_creates_schema_and_version(tmp_path):
    connection = create_database(tmp_path)

    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    table_names = {row[0] for row in rows}
    version = connection.execute("SELECT version FROM schema_version").fetchone()[0]

    connection.close()

    assert table_names == EXPECTED_TABLES
    assert version == 1


def test_duplicate_patient_and_bundle_ids_are_rejected(tmp_path):
    connection = create_database(tmp_path)
    add_patient_and_bundle(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO patients (
                patient_id, display_name, birth_year, language
            ) VALUES (?, ?, ?, ?)
            """,
            ("SR-DEMO-001", "Another Demo", 1990, "ENGLISH"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO referral_bundles (
                bundle_id,
                patient_id,
                creation_time,
                source_facility,
                destination,
                referral_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "RB-001",
                "SR-DEMO-001",
                "2026-09-02T11:00:00",
                "Another Demo BHU",
                "Another Demo Hospital",
                "DRAFT",
            ),
        )

    connection.close()


def test_orphan_records_are_rejected(tmp_path):
    connection = create_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO referral_bundles (
                bundle_id,
                patient_id,
                creation_time,
                source_facility,
                destination,
                referral_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "RB-ORPHAN-001",
                "SR-MISSING-001",
                "2026-09-02T10:00:00",
                "Demo BHU",
                "Demo Hospital",
                "DRAFT",
            ),
        )
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO encounters (
                bundle_id, date, facility, clinician_display_text, source_note
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "RB-MISSING-001",
                "2026-09-02",
                "Demo Hospital",
                "Dr Demo",
                "Synthetic note",
            ),
        )

    connection.close()


def test_invalid_cost_entries_are_rejected(tmp_path):
    connection = create_database(tmp_path)
    add_patient_and_bundle(connection)

    invalid_costs = [
        ("CE-001", "TRAVEL", -1, "interview", "response-001"),
        ("CE-002", "FOOD", 250000, "interview", "response-001"),
        ("CE-003", "TRAVEL", 250000, "", "response-001"),
        ("CE-004", "TRAVEL", 250000, "interview", ""),
        ("CE-005", "TRAVEL", 250000, None, "response-001"),
        ("CE-006", "TRAVEL", 250000, "interview", None),
        ("CE-007", "TRAVEL", 1.5, "interview", "response-001"),
    ]

    for cost_id, category, amount, source_type, source_identifier in invalid_costs:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO cost_entries (
                    cost_entry_id,
                    bundle_id,
                    category,
                    amount_paisa,
                    date,
                    source,
                    source_type,
                    source_identifier,
                    reported_by_label,
                    note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cost_id,
                    "RB-001",
                    category,
                    amount,
                    "2026-09-02",
                    "Synthetic interview response",
                    source_type,
                    source_identifier,
                    "Amina Demo",
                    "Synthetic cost",
                ),
            )
        connection.rollback()

    connection.close()
