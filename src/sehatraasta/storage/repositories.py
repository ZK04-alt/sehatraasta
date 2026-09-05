import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import shutil

from sehatraasta.domain import (
    Attachment,
    AuditEvent,
    CategoryReview,
    CostCategory,
    CostEntry,
    DiagnosticResult,
    Encounter,
    ImagingItem,
    Instruction,
    InvestigationOrder,
    InvestigationOrderStatus,
    Language,
    MedicationItem,
    Patient,
    PresenceState,
    ReferralBundle,
    ReferralStatus,
    ReviewCategory,
)


from .errors import StorageError
from .interfaces import PatientRepository


def medication_to_dict(item):
    return {
        "ID": item.ID,
        "name": item.name,
        "strength": item.strength,
        "dose": item.dose,
        "route": item.route,
        "frequency": item.frequency,
        "duration": item.duration,
        "instructions": item.instructions,
        "source": item.source,
    }


def order_to_dict(item):
    return {
        "name": item.name,
        "date": item.date.isoformat(),
        "source": item.source,
        "workflow_status": item.workflow_status.name,
    }


def bundle_to_dict(bundle):
    order_indexes = {
        id(order): index for index, order in enumerate(bundle.investigation_orders)
    }

    results = []
    for result in bundle.diagnostic_results:
        order_index = None
        if result.investigation_order is not None:
            order_index = order_indexes[id(result.investigation_order)]
        results.append(
            {
                "ID": result.ID,
                "name": result.name,
                "date": result.date.isoformat(),
                "source": result.source,
                "interpretation": result.interpretation,
                "investigation_order_index": order_index,
            }
        )

    return {
        "ID": bundle.ID,
        "creation_time": bundle.creation_time.isoformat(),
        "source_facility": bundle.source_facility,
        "destination": bundle.destination,
        "status": bundle.status.name,
        "encounters": [
            {
                "date": item.date.isoformat(),
                "facility": item.facility,
                "clinician_display_text": item.clinician_display_text,
                "source_note": item.source_note,
            }
            for item in bundle.encounters
        ],
        "medication_items": [
            medication_to_dict(item) for item in bundle.medication_item
        ],
        "instructions": [
            {
                "category": item.category,
                "language": item.language.name,
                "text": item.text,
                "source": item.source,
                "date": item.date.isoformat(),
            }
            for item in bundle.instructions
        ],
        "attachments": [
            {
                "ID": item.ID,
                "category": item.category,
                "name": item.name,
                "MIME_type": item.MIME_type,
                "sha": item.sha,
                "date": item.date.isoformat(),
                "source": item.source,
                "size": item.size,
                "generated_stored_name": item.generated_stored_name,
            }
            for item in bundle.attachments
        ],
        "imaging_items": [
            {
                "ID": item.ID,
                "modality": item.modality,
                "body_part": item.body_part,
                "date": item.date.isoformat(),
                "facility": item.facility,
                "report": item.report,
                "Attachment_ID": item.Attachment_ID,
            }
            for item in bundle.imaging_items
        ],
        "cost_entries": [
            {
                "ID": item.ID,
                "category": item.category.name,
                "amount_pkr": str(item.amount),
                "source_type": item.source_type,
                "source_identifier": item.source_identifier,
                "reported_by_label": item.reported_by_label,
                "date": item.date.isoformat(),
                "source": item.source,
                "note": item.note,
            }
            for item in bundle.cost_entries
        ],
        "category_reviews": [
            {
                "category": item.category.name,
                "state": item.state.name,
                "text": item.text,
                "time": item.time.isoformat(),
                "note": item.note,
            }
            for item in bundle.category_reviews
        ],
        "audit_events": [
            {
                "time": item.time.isoformat(),
                "action": item.action,
                "audit_type": item.audit_type,
                "ID": item.ID,
                "actor_label": item.actor_label,
                "result": item.result,
            }
            for item in bundle.audit_events
        ],
        "investigation_orders": [
            order_to_dict(item) for item in bundle.investigation_orders
        ],
        "diagnostic_results": results,
    }


def patient_to_dict(patient):
    return {
        "ID": patient.ID,
        "name": patient.name,
        "birth_year": patient.birth_year,
        "language": patient.language.name,
        "referral_bundles": [bundle_to_dict(item) for item in patient.referrals],
    }


def _order_from_dict(data):
    return InvestigationOrder(
        data["name"],
        date.fromisoformat(data["date"]),
        data["source"],
        InvestigationOrderStatus[data["workflow_status"]],
    )


def _bundle_from_dict(data):
    attachments = [
        Attachment(
            item["ID"],
            item["category"],
            item["name"],
            item["MIME_type"],
            item["sha"],
            date.fromisoformat(item["date"]),
            item["source"],
            item["size"],
            item.get("generated_stored_name", ""),
        )
        for item in data.get("attachments", [])
    ]
    orders = [
        _order_from_dict(item) for item in data.get("investigation_orders", [])
    ]

    results = []
    for item in data.get("diagnostic_results", []):
        order = None
        order_index = item.get("investigation_order_index")
        if order_index is not None:
            order = orders[order_index]
        results.append(
            DiagnosticResult(
                item["name"],
                date.fromisoformat(item["date"]),
                item["source"],
                item["ID"],
                item["interpretation"],
                order,
            )
        )

    return ReferralBundle(
        ID=data["ID"],
        creation_time=datetime.fromisoformat(data["creation_time"]),
        source_facility=data["source_facility"],
        destination=data["destination"],
        status=ReferralStatus[data["status"]],
        encounters=[
            Encounter(
                date.fromisoformat(item["date"]),
                item["facility"],
                item["clinician_display_text"],
                item["source_note"],
            )
            for item in data.get("encounters", [])
        ],
        medication_item=[
            MedicationItem(
                item["name"],
                item["strength"],
                item["dose"],
                item["route"],
                item["frequency"],
                item["duration"],
                item["instructions"],
                item["source"],
                item["ID"],
            )
            for item in data.get("medication_items", [])
        ],
        instructions=[
            Instruction(
                item["category"],
                Language[item["language"]],
                item["text"],
                item["source"],
                date.fromisoformat(item["date"]),
            )
            for item in data.get("instructions", [])
        ],
        imaging_items=[
            ImagingItem(
                item["modality"],
                item["body_part"],
                date.fromisoformat(item["date"]),
                item["facility"],
                item["report"],
                item["ID"],
                item["Attachment_ID"],
            )
            for item in data.get("imaging_items", [])
        ],
        cost_entries=[
            CostEntry(
                item["ID"],
                CostCategory[item["category"]],
                Decimal(item["amount_pkr"]),
                date.fromisoformat(item["date"]),
                item["source"],
                item.get("note", ""),
                item.get("source_type", "reported"),
                item.get("source_identifier"),
                item.get("reported_by_label", ""),
            )
            for item in data.get("cost_entries", [])
        ],
        attachments=attachments,
        category_reviews=[
            CategoryReview(
                ReviewCategory[item["category"]],
                PresenceState[item["state"]],
                item["text"],
                datetime.fromisoformat(item["time"]),
                item["note"],
            )
            for item in data.get("category_reviews", [])
        ],
        audit_events=[
            AuditEvent(
                datetime.fromisoformat(item["time"]),
                item["action"],
                item["audit_type"],
                item["ID"],
                item["actor_label"],
                item["result"],
            )
            for item in data.get("audit_events", [])
        ],
        investigation_orders=orders,
        diagnostic_results=results,
    )


def _patient_from_dict(data):
    return Patient(
        data["ID"],
        data["name"],
        data["birth_year"],
        Language[data["language"]],
        [_bundle_from_dict(item) for item in data.get("referral_bundles", [])],
    )


def write_json_safely(path, payload):
    target = Path(path)
    temporary = target.with_name(target.name + ".tmp")
    backup = target.with_name(target.name + ".bak")
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        json.loads(temporary.read_text(encoding="utf-8"))

        if target.exists():
            json.loads(target.read_text(encoding="utf-8"))
            shutil.copy2(target, backup)

        os.replace(temporary, target)
    except (OSError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        if temporary.exists():
            temporary.unlink()
        raise StorageError("could not safely write development file") from error

    return target


class JsonRepository(PatientRepository):
    def __init__(self, path):
        self.path = Path(path)
        self.patients = self._load_patients()

    def _load_patients(self):
        if not self.path.exists():
            return []

        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("format_version") != 1:
                raise ValueError("unsupported development file version")
            if document.get("synthetic_only") is not True:
                raise ValueError("development file is not marked synthetic")
            return [
                _patient_from_dict(item) for item in document.get("patients", [])
            ]
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            IndexError,
            AttributeError,
            InvalidOperation,
        ) as error:
            raise StorageError("invalid or corrupt development file") from error

    def _save(self):
        if self.path.exists():
            self._load_patients()

        document = {
            "format_version": 1,
            "synthetic_only": True,
            "patients": [patient_to_dict(item) for item in self.patients],
        }
        write_json_safely(self.path, document)

    def add_patient(self, patient):
        if any(item.ID == patient.ID for item in self.patients):
            raise ValueError("duplicate patient ID")
        self.patients.append(patient)
        try:
            self._save()
        except StorageError:
            self.patients.remove(patient)
            raise

    def get_patient(self, patient_id):
        for patient in self.patients:
            if patient.ID == patient_id:
                return patient
        return None

    def list_patients(self):
        return list(self.patients)

    def save_patient(self, patient):
        if patient not in self.patients:
            raise ValueError("patient not found")
        self._save()
