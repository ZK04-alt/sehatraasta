from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3

from .db import connect_database, initialize_database
from .errors import StorageError, log_storage_error
from .interfaces import PatientRepository
from .repositories import _patient_from_dict


def amount_to_paisa(amount):
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
        raise ValueError("invalid amount")
    if amount > Decimal("92233720368547758.07"):
        raise ValueError("amount is too large")
    if 0 < amount < Decimal("0.01"):
        raise ValueError("amount must use whole paisa (at most two decimal places)")
    with localcontext() as context:
        context.prec = max(30, len(amount.as_tuple().digits) + 3)
        paisa = amount * 100
        if paisa != paisa.to_integral_value():
            raise ValueError("amount must use whole paisa (at most two decimal places)")
        if paisa > 9223372036854775807:
            raise ValueError("amount is too large")
        return int(paisa)


class SQLiteRepository(PatientRepository):
    """Load fresh patient objects and save their records in one transaction."""

    def __init__(self, path):
        self.path = Path(path)
        initialize_database(self.path)

    def add_patient(self, patient):
        self._save(patient, adding=True)

    def save_patient(self, patient):
        self._save(patient, adding=False)

    def _save(self, patient, adding):
        patient.checks()
        if patient.birth_year > 9223372036854775807:
            raise ValueError("birth year is too large")
        for bundle in patient.referrals:
            bundle.checks()
        connection = connect_database(self.path)
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if adding:
                    connection.execute(
                        "INSERT INTO patients (patient_id, display_name, birth_year, language) VALUES (?, ?, ?, ?)",
                        (patient.ID, patient.name, patient.birth_year, patient.language.name),
                    )
                    revision = 0
                else:
                    revision = getattr(patient, "_storage_revision", None)
                    if revision is None:
                        raise ValueError("load the patient before saving")
                    updated = connection.execute(
                        "UPDATE patients SET display_name = ?, birth_year = ?, language = ?, revision = revision + 1 WHERE patient_id = ? AND revision = ?",
                        (patient.name, patient.birth_year, patient.language.name, patient.ID, revision),
                    )
                    if updated.rowcount != 1:
                        raise ValueError("patient changed or was removed; reload before saving")
                    revision += 1
                    # Bundle IDs stay the same. Replacing their child rows inside
                    # the transaction keeps this implementation simple and atomic.
                    connection.execute("DELETE FROM referral_bundles WHERE patient_id = ?", (patient.ID,))
                for bundle in patient.referrals:
                    self._write_bundle(connection, patient.ID, bundle)
            patient._storage_revision = revision
        except sqlite3.IntegrityError as error:
            log_storage_error(self.path, "save_patient", error)
            raise ValueError("duplicate ID or invalid database relationship/field") from error
        except (sqlite3.Error, OSError) as error:
            log_storage_error(self.path, "save_patient", error)
            raise StorageError("could not save records; no changes were saved") from error
        finally:
            connection.close()

    def _write_bundle(self, connection, patient_id, bundle):
        connection.execute(
            "INSERT INTO referral_bundles VALUES (?, ?, ?, ?, ?, ?)",
            (bundle.ID, patient_id, bundle.creation_time.isoformat(), bundle.source_facility, bundle.destination, bundle.status.name),
        )
        for item in bundle.encounters:
            item.checks()
            connection.execute(
                "INSERT INTO encounters (bundle_id, date, facility, clinician_display_text, source_note) VALUES (?, ?, ?, ?, ?)",
                (bundle.ID, item.date.isoformat(), item.facility, item.clinician_display_text, item.source_note),
            )
        for item in bundle.medication_item:
            item.checks()
            connection.execute(
                "INSERT INTO medication_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.ID, bundle.ID, item.name, item.strength, item.dose, item.route, item.frequency, item.duration, item.instructions, item.source),
            )
        for item in bundle.instructions:
            item.checks()
            connection.execute(
                "INSERT INTO instructions (bundle_id, category, language, verbatim_text, author_source, date) VALUES (?, ?, ?, ?, ?, ?)",
                (bundle.ID, item.category, item.language.name, item.text, item.source, item.date.isoformat()),
            )
        for item in bundle.attachments:
            item.checks()
            if not float(item.size).is_integer() or item.size > 9223372036854775807:
                raise ValueError("attachment size must be whole bytes within the storage limit")
            connection.execute(
                "INSERT INTO attachments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.ID, bundle.ID, item.category, item.name, item.generated_stored_name, item.MIME_type, int(item.size), item.sha, item.date.isoformat(), item.source),
            )
        for item in bundle.imaging_items:
            item.checks()
            connection.execute(
                "INSERT INTO imaging_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item.ID, bundle.ID, item.Attachment_ID, item.modality, item.body_part, item.date.isoformat(), item.facility, item.report),
            )
        for item in bundle.cost_entries:
            item.checks()
            connection.execute(
                "INSERT INTO cost_entries (cost_entry_id, bundle_id, category, amount_paisa, date, source, source_type, source_identifier, reported_by_label, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.ID, bundle.ID, item.category.name, amount_to_paisa(item.amount), item.date.isoformat(), item.source, item.source_type, item.source_identifier, item.reported_by_label, item.note),
            )
        for item in bundle.category_reviews:
            item.checks()
            connection.execute(
                "INSERT INTO category_reviews (bundle_id, category, presence_state, reviewer_text, reviewed_time, note) VALUES (?, ?, ?, ?, ?, ?)",
                (bundle.ID, item.category.name, item.state.name, item.text, item.time.isoformat(), item.note),
            )
        for item in bundle.audit_events:
            item.checks()
            connection.execute(
                "INSERT INTO audit_events (bundle_id, timestamp, action, entity_type, entity_id, actor_label, result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bundle.ID, item.time.isoformat(), item.action, item.audit_type, item.ID, item.actor_label, item.result),
            )
        order_ids = {}
        for item in bundle.investigation_orders:
            item.checks()
            cursor = connection.execute(
                "INSERT INTO investigation_orders (bundle_id, test_name, order_date, ordering_source, workflow_status) VALUES (?, ?, ?, ?, ?)",
                (bundle.ID, item.name, item.date.isoformat(), item.source, item.workflow_status.name),
            )
            order_ids[id(item)] = cursor.lastrowid
        for item in bundle.diagnostic_results:
            item.checks()
            order_id = None
            if item.investigation_order is not None:
                order_id = order_ids.get(id(item.investigation_order))
                if order_id is None:
                    raise ValueError("investigation order not found in bundle")
            connection.execute(
                "INSERT INTO diagnostic_results VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item.ID, bundle.ID, order_id, item.name, item.date.isoformat(), item.source, item.interpretation),
            )

    def get_patient(self, patient_id):
        patients = self._read_patients(patient_id)
        return patients[0] if patients else None

    def list_patients(self):
        return self._read_patients(None)

    def _read_patients(self, patient_id):
        connection = connect_database(self.path, read_only=True)
        try:
            # All queries in one read snapshot, even during concurrent updates.
            connection.execute("BEGIN")
            if patient_id is None:
                rows = connection.execute("SELECT * FROM patients ORDER BY rowid").fetchall()
            else:
                rows = connection.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchall()
            patients = []
            for row in rows:
                bundles = connection.execute("SELECT * FROM referral_bundles WHERE patient_id = ? ORDER BY rowid", (row["patient_id"],)).fetchall()
                data = {
                    "ID": row["patient_id"], "name": row["display_name"],
                    "birth_year": row["birth_year"], "language": row["language"],
                    "referral_bundles": [self._read_bundle(connection, bundle) for bundle in bundles],
                }
                patient = _patient_from_dict(data)
                patient._storage_revision = row["revision"]
                patients.append(patient)
            return patients
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            log_storage_error(self.path, "read_patients", error)
            raise StorageError("could not read database records") from error
        finally:
            connection.close()

    def _read_bundle(self, connection, row):
        bundle_id = row["bundle_id"]
        data = {
            "ID": bundle_id, "creation_time": row["creation_time"],
            "source_facility": row["source_facility"], "destination": row["destination"],
            "status": row["referral_status"],
        }
        data["encounters"] = [dict(item) for item in connection.execute(
            "SELECT date, facility, clinician_display_text, source_note FROM encounters WHERE bundle_id = ? ORDER BY encounter_id", (bundle_id,))]
        data["medication_items"] = [dict(item) for item in connection.execute(
            "SELECT medication_id AS ID, verbatim_name AS name, strength, dose_text AS dose, route_text AS route, frequency_text AS frequency, duration_text AS duration, instructions, source FROM medication_items WHERE bundle_id = ? ORDER BY rowid", (bundle_id,))]
        data["instructions"] = [dict(item) for item in connection.execute(
            "SELECT category, language, verbatim_text AS text, author_source AS source, date FROM instructions WHERE bundle_id = ? ORDER BY instruction_id", (bundle_id,))]
        data["attachments"] = [dict(item) for item in connection.execute(
            "SELECT attachment_id AS ID, category, original_display_name AS name, generated_stored_name, mime_type AS MIME_type, sha256 AS sha, date, source, size_bytes AS size FROM attachments WHERE bundle_id = ? ORDER BY rowid", (bundle_id,))]
        data["imaging_items"] = [dict(item) for item in connection.execute(
            "SELECT imaging_id AS ID, modality, body_part, date, facility, report, attachment_id AS Attachment_ID FROM imaging_items WHERE bundle_id = ? ORDER BY rowid", (bundle_id,))]
        data["category_reviews"] = [dict(item) for item in connection.execute(
            "SELECT category, presence_state AS state, reviewer_text AS text, reviewed_time AS time, note FROM category_reviews WHERE bundle_id = ? ORDER BY review_id", (bundle_id,))]
        data["audit_events"] = [dict(item) for item in connection.execute(
            "SELECT timestamp AS time, action, entity_type AS audit_type, entity_id AS ID, actor_label, result FROM audit_events WHERE bundle_id = ? ORDER BY audit_event_id", (bundle_id,))]
        data["cost_entries"] = []
        for item in connection.execute("SELECT * FROM cost_entries WHERE bundle_id = ? ORDER BY rowid", (bundle_id,)):
            # Build the decimal text using integers, without float conversion.
            paisa = item["amount_paisa"]
            amount = f"{paisa // 100}.{paisa % 100:02d}"
            if paisa % 100 == 0:
                amount = str(paisa // 100)
            data["cost_entries"].append({
                "ID": item["cost_entry_id"], "category": item["category"],
                "amount_pkr": amount, "date": item["date"], "source": item["source"],
                "source_type": item["source_type"], "source_identifier": item["source_identifier"],
                "note": item["note"],
                "reported_by_label": item["reported_by_label"],
            })
        orders = connection.execute("SELECT * FROM investigation_orders WHERE bundle_id = ? ORDER BY order_id", (bundle_id,)).fetchall()
        order_indexes = {}
        data["investigation_orders"] = []
        for index, item in enumerate(orders):
            order_indexes[item["order_id"]] = index
            data["investigation_orders"].append({
                "name": item["test_name"], "date": item["order_date"],
                "source": item["ordering_source"], "workflow_status": item["workflow_status"],
            })
        data["diagnostic_results"] = []
        for item in connection.execute("SELECT * FROM diagnostic_results WHERE bundle_id = ? ORDER BY rowid", (bundle_id,)):
            order_index = None
            if item["investigation_order_id"] is not None:
                order_index = order_indexes[item["investigation_order_id"]]
            data["diagnostic_results"].append({
                "ID": item["result_id"], "name": item["test_name"], "date": item["result_date"],
                "source": item["source_summary"], "interpretation": item["interpretation_note"],
                "investigation_order_index": order_index,
            })
        return data
