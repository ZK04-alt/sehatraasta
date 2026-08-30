from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import re

from .enums import (
    CostCategory,
    InvestigationOrderStatus,
    Language,
    PresenceState,
    ReferralStatus,
    ReviewCategory,
)
from .validation import validate_id


@dataclass
class MedicationItem:
    name: str
    strength: str
    dose: str
    route: str
    frequency: str
    duration: str
    instructions: str
    source: str
    ID: str

    def checks(self):
        if not isinstance(self.name, str):
            raise ValueError("invalid name")
        if not self.name.strip():
            raise ValueError("missing name")
        if not isinstance(self.strength, str):
            raise ValueError("invalid strength")
        if not self.strength.strip():
            raise ValueError("missing strength")
        if not isinstance(self.dose, str):
            raise ValueError("invalid dose")
        if not self.dose.strip():
            raise ValueError("missing dose")
        if not isinstance(self.route, str):
            raise ValueError("invalid route")
        if not self.route.strip():
            raise ValueError("missing route")
        if not isinstance(self.frequency, str):
            raise ValueError("invalid frequency")
        if not self.frequency.strip():
            raise ValueError("missing frequency")
        if not isinstance(self.duration, str):
            raise ValueError("invalid duration")
        if not self.duration.strip():
            raise ValueError("missing duration")
        if not isinstance(self.instructions, str):
            raise ValueError("invalid instructions")
        if not self.instructions.strip():
            raise ValueError("missing instructions")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if not isinstance(self.ID, str):
            raise ValueError("invalid ID")
        if not self.ID.strip():
            raise ValueError("missing ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.ID):
            raise ValueError("invalid ID")

    def __post_init__(self):
        self.checks()


@dataclass
class Encounter:
    date: date
    facility: str
    clinician_display_text: str
    source_note: str

    def checks(self):
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.facility, str):
            raise ValueError("invalid facility")
        if not self.facility.strip():
            raise ValueError("missing facility")
        if not isinstance(self.clinician_display_text, str):
            raise ValueError("invalid clinician display text")
        if not self.clinician_display_text.strip():
            raise ValueError("missing clinician display text")
        if not isinstance(self.source_note, str):
            raise ValueError("invalid source note")
        if not self.source_note.strip():
            raise ValueError("missing source note")

    def __post_init__(self):
        self.checks()


@dataclass
class Instruction:
    category: str
    language: Language
    text: str
    source: str
    date: date

    def checks(self):
        if not isinstance(self.category, str):
            raise ValueError("invalid category")
        if not self.category.strip():
            raise ValueError("missing category")
        if not isinstance(self.language, Language):
            raise ValueError("unknown language")
        if not isinstance(self.text, str):
            raise ValueError("invalid text")
        if not self.text.strip():
            raise ValueError("missing text")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")

    def __post_init__(self):
        self.checks()


@dataclass
class ImagingItem:
    modality: str
    body_part: str
    date: date
    facility: str
    report: str
    ID: str
    Attachment_ID: str

    def checks(self):
        if not isinstance(self.modality, str):
            raise ValueError("invalid modality")
        if not self.modality.strip():
            raise ValueError("missing modality")
        if not isinstance(self.body_part, str):
            raise ValueError("invalid body part")
        if not self.body_part.strip():
            raise ValueError("missing body part")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.facility, str):
            raise ValueError("invalid facility")
        if not self.facility.strip():
            raise ValueError("missing facility")
        if not isinstance(self.report, str):
            raise ValueError("invalid report")
        if not self.report.strip():
            raise ValueError("missing report")
        if not isinstance(self.ID, str):
            raise ValueError("invalid ID")
        if not self.ID.strip():
            raise ValueError("missing ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.ID):
            raise ValueError("invalid ID")
        if not isinstance(self.Attachment_ID, str):
            raise ValueError("invalid attachment ID")
        if not self.Attachment_ID.strip():
            raise ValueError("missing attachment ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.Attachment_ID):
            raise ValueError("invalid attachment ID")

    def __post_init__(self):
        self.checks()


@dataclass
class InvestigationOrder:
    name: str
    date: date
    source: str
    workflow_status: InvestigationOrderStatus

    def checks(self):
        if not isinstance(self.name, str):
            raise ValueError("invalid name")
        if not self.name.strip():
            raise ValueError("missing name")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if not isinstance(self.workflow_status, InvestigationOrderStatus):
            raise ValueError("unknown investigation order status")
        if not self.workflow_status:
            raise ValueError("missing investigation order status")

    def __post_init__(self):
        self.checks()


@dataclass
class DiagnosticResult:
    name: str
    date: date
    source: str
    ID: str
    interpretation: str
    investigation_order: InvestigationOrder | None = None

    def checks(self):
        if not isinstance(self.name, str):
            raise ValueError("invalid name")
        if not self.name.strip():
            raise ValueError("missing name")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if not isinstance(self.ID, str):
            raise ValueError("invalid ID")
        if not self.ID.strip():
            raise ValueError("missing ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.ID):
            raise ValueError("invalid ID")
        if not isinstance(self.interpretation, str):
            raise ValueError("invalid interpretation")
        if not self.interpretation.strip():
            raise ValueError("missing interpretation")
        if self.investigation_order is not None:
            if not isinstance(self.investigation_order, InvestigationOrder):
                raise ValueError("invalid investigation order")
            if self.date < self.investigation_order.date:
                raise ValueError("result date before order date")

    def __post_init__(self):
        self.checks()


@dataclass
class CategoryReview:
    category: ReviewCategory
    state: PresenceState
    text: str
    time: datetime
    note: str

    def checks(self):
        if not isinstance(self.category, ReviewCategory):
            raise ValueError("unknown review category")
        if not isinstance(self.state, PresenceState):
            raise ValueError("unknown presence state")
        if not isinstance(self.text, str):
            raise ValueError("invalid text")
        if not self.text.strip():
            raise ValueError("missing text")
        if not isinstance(self.time, datetime):
            raise ValueError("invalid time")
        if not isinstance(self.note, str):
            raise ValueError("invalid note")
        if not self.note.strip():
            raise ValueError("missing note")

    def __post_init__(self):
        self.checks()


@dataclass
class Attachment:
    ID: str
    category: str
    name: str
    MIME_type: str
    sha: str
    date: date
    source: str
    size: float

    _ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}

    def checks(self):
        if not isinstance(self.ID, str):
            raise ValueError("invalid ID")
        if not self.ID.strip():
            raise ValueError("missing ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.ID):
            raise ValueError("invalid ID")
        if not isinstance(self.category, str):
            raise ValueError("invalid category")
        if not self.category.strip():
            raise ValueError("missing category")
        if not isinstance(self.name, str):
            raise ValueError("invalid name")
        if not self.name.strip():
            raise ValueError("missing name")
        if not isinstance(self.MIME_type, str):
            raise ValueError("invalid MIME type")
        if self.MIME_type not in self._ALLOWED_MIME_TYPES:
            raise ValueError("unsupported MIME type")
        if not isinstance(self.sha, str):
            raise ValueError("invalid sha")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.sha):
            raise ValueError("invalid sha")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if isinstance(self.size, bool) or not isinstance(self.size, (int, float)):
            raise ValueError("invalid size")
        if self.size <= 0:
            raise ValueError("invalid size")

    def __post_init__(self):
        self.checks()


@dataclass
class CostEntry:
    ID: str
    category: CostCategory
    amount: Decimal
    date: date
    source: str
    note: str = ""

    def checks(self):
        validate_id(self.ID)
        if not isinstance(self.category, CostCategory):
            raise ValueError("unsupported cost category")
        if isinstance(self.amount, bool) or not isinstance(self.amount, Decimal):
            raise ValueError("invalid amount")
        if not self.amount.is_finite():
            raise ValueError("invalid amount")
        if self.amount <= 0:
            raise ValueError("invalid amount")
        if isinstance(self.date, datetime):
            raise ValueError("invalid date")
        if not isinstance(self.date, date):
            raise ValueError("invalid date")
        if not isinstance(self.source, str):
            raise ValueError("invalid source")
        if not self.source.strip():
            raise ValueError("missing source")
        if not isinstance(self.note, str):
            raise ValueError("invalid note")

    def __post_init__(self):
        self.checks()


@dataclass
class AuditEvent:
    time: datetime
    action: str
    audit_type: str
    ID: str
    actor_label: str
    result: str

    def checks(self):
        if not isinstance(self.time, datetime):
            raise ValueError("invalid time")
        if not isinstance(self.action, str):
            raise ValueError("invalid action")
        if not self.action.strip():
            raise ValueError("missing action")
        if not isinstance(self.audit_type, str):
            raise ValueError("invalid audit type")
        if not self.audit_type.strip():
            raise ValueError("missing audit type")
        if not isinstance(self.ID, str):
            raise ValueError("invalid ID")
        if not self.ID.strip():
            raise ValueError("missing ID")
        if not re.fullmatch(r"[A-Z]{2}-\d{3}", self.ID):
            raise ValueError("invalid ID")
        if not isinstance(self.actor_label, str):
            raise ValueError("invalid actor label")
        if not self.actor_label.strip():
            raise ValueError("missing actor label")
        if not isinstance(self.result, str):
            raise ValueError("invalid result")
        if not self.result.strip():
            raise ValueError("missing result")

    def __post_init__(self):
        self.checks()


@dataclass
class ReferralBundle:
    ID: str
    creation_time: datetime
    source_facility: str
    destination: str
    status: ReferralStatus
    encounters: list[Encounter] = field(default_factory=list)
    medication_item: list[MedicationItem] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)
    imaging_items: list[ImagingItem] = field(default_factory=list)
    cost_entries: list[CostEntry] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    category_reviews: list[CategoryReview] = field(default_factory=list)
    audit_events: list[AuditEvent] = field(default_factory=list)
    investigation_orders: list[InvestigationOrder] = field(default_factory=list)
    diagnostic_results: list[DiagnosticResult] = field(default_factory=list)

    @staticmethod
    def _has_duplicate_ids(items):
        ids = [item.ID for item in items]
        return len(ids) != len(set(ids))

    def checks(self):
        validate_id(self.ID)

        if not isinstance(self.creation_time, datetime):
            raise ValueError("invalid creation time")
        if not isinstance(self.source_facility, str):
            raise ValueError("invalid source facility")
        if not self.source_facility.strip():
            raise ValueError("missing source facility")
        if not isinstance(self.destination, str):
            raise ValueError("invalid destination")
        if not self.destination.strip():
            raise ValueError("missing destination")
        if not isinstance(self.status, ReferralStatus):
            raise ValueError("unknown referral status")
        if not isinstance(self.encounters, list):
            raise ValueError("invalid encounters")
        if any(not isinstance(item, Encounter) for item in self.encounters):
            raise ValueError("invalid encounter entry")
        if not isinstance(self.medication_item, list):
            raise ValueError("invalid medication items")
        if any(not isinstance(item, MedicationItem) for item in self.medication_item):
            raise ValueError("invalid medication entry")
        if self._has_duplicate_ids(self.medication_item):
            raise ValueError("duplicate medication ID")
        if not isinstance(self.instructions, list):
            raise ValueError("invalid instructions")
        if any(not isinstance(item, Instruction) for item in self.instructions):
            raise ValueError("invalid instruction entry")
        if not isinstance(self.imaging_items, list):
            raise ValueError("invalid imaging items")
        if any(not isinstance(item, ImagingItem) for item in self.imaging_items):
            raise ValueError("invalid imaging entry")
        if self._has_duplicate_ids(self.imaging_items):
            raise ValueError("duplicate imaging item ID")
        if not isinstance(self.cost_entries, list):
            raise ValueError("invalid cost entries")
        if any(not isinstance(item, CostEntry) for item in self.cost_entries):
            raise ValueError("invalid cost entry")
        if self._has_duplicate_ids(self.cost_entries):
            raise ValueError("duplicate cost entry ID")
        if not isinstance(self.attachments, list):
            raise ValueError("invalid attachments")
        if any(not isinstance(item, Attachment) for item in self.attachments):
            raise ValueError("invalid attachment entry")
        if self._has_duplicate_ids(self.attachments):
            raise ValueError("duplicate attachment ID")
        if not isinstance(self.category_reviews, list):
            raise ValueError("invalid category reviews")
        if any(not isinstance(item, CategoryReview) for item in self.category_reviews):
            raise ValueError("invalid category review entry")
        if not isinstance(self.audit_events, list):
            raise ValueError("invalid audit events")
        if any(not isinstance(item, AuditEvent) for item in self.audit_events):
            raise ValueError("invalid audit event entry")
        if self._has_duplicate_ids(self.audit_events):
            raise ValueError("duplicate audit event ID")
        if not isinstance(self.investigation_orders, list):
            raise ValueError("invalid investigation orders")
        if any(
            not isinstance(item, InvestigationOrder)
            for item in self.investigation_orders
        ):
            raise ValueError("invalid investigation order entry")
        if not isinstance(self.diagnostic_results, list):
            raise ValueError("invalid diagnostic results")
        if any(
            not isinstance(item, DiagnosticResult) for item in self.diagnostic_results
        ):
            raise ValueError("invalid diagnostic result entry")
        if self._has_duplicate_ids(self.diagnostic_results):
            raise ValueError("duplicate diagnostic result ID")
        attachment_ids = [a.ID for a in self.attachments]
        if any(item.Attachment_ID not in attachment_ids for item in self.imaging_items):
            raise ValueError("attachment not found in bundle")
        if any(
            item.investigation_order is not None
            and item.investigation_order not in self.investigation_orders
            for item in self.diagnostic_results
        ):
            raise ValueError("investigation order not found in bundle")

    def __post_init__(self):
        self.checks()

    def add_encounter(self, encounter):
        if not isinstance(encounter, Encounter):
            raise ValueError("invalid encounter")
        self.encounters.append(encounter)

    def add_medication(self, medication):
        if not isinstance(medication, MedicationItem):
            raise ValueError("invalid medication")
        if medication.ID in [item.ID for item in self.medication_item]:
            raise ValueError("duplicate medication ID")
        self.medication_item.append(medication)

    def add_instruction(self, instruction):
        if not isinstance(instruction, Instruction):
            raise ValueError("invalid instruction")
        self.instructions.append(instruction)

    def add_imaging_item(self, imaging_item):
        if not isinstance(imaging_item, ImagingItem):
            raise ValueError("invalid imaging item")
        if imaging_item.ID in [item.ID for item in self.imaging_items]:
            raise ValueError("duplicate imaging item ID")
        if imaging_item.Attachment_ID not in [item.ID for item in self.attachments]:
            raise ValueError("attachment not found in bundle")
        self.imaging_items.append(imaging_item)

    def add_cost_entry(self, cost_entry):
        if not isinstance(cost_entry, CostEntry):
            raise ValueError("invalid cost entry")
        if cost_entry.ID in [item.ID for item in self.cost_entries]:
            raise ValueError("duplicate cost entry ID")
        self.cost_entries.append(cost_entry)

    def total_cost_pkr(self) -> Decimal:
        return sum(
            (cost_entry.amount for cost_entry in self.cost_entries),
            Decimal("0"),
        )

    def add_attachment(self, attachment):
        if not isinstance(attachment, Attachment):
            raise ValueError("invalid attachment")
        if attachment.ID in [item.ID for item in self.attachments]:
            raise ValueError("duplicate attachment ID")
        self.attachments.append(attachment)

    def add_category_review(self, category_review):
        if not isinstance(category_review, CategoryReview):
            raise ValueError("invalid category review")
        self.category_reviews.append(category_review)

    def add_audit_event(self, audit_event):
        if not isinstance(audit_event, AuditEvent):
            raise ValueError("invalid audit event")
        if audit_event.ID in [item.ID for item in self.audit_events]:
            raise ValueError("duplicate audit event ID")
        self.audit_events.append(audit_event)

    def add_investigation_order(self, investigation_order):
        if not isinstance(investigation_order, InvestigationOrder):
            raise ValueError("invalid investigation order")
        self.investigation_orders.append(investigation_order)

    def add_diagnostic_result(self, result):
        if not isinstance(result, DiagnosticResult):
            raise ValueError("invalid diagnostic result")
        if result.ID in [item.ID for item in self.diagnostic_results]:
            raise ValueError("duplicate diagnostic result ID")
        if (
            result.investigation_order is not None
            and result.investigation_order not in self.investigation_orders
        ):
            raise ValueError("investigation order not found in bundle")
        self.diagnostic_results.append(result)


@dataclass
class Patient:
    ID: str
    name: str
    birth_year: int
    language: Language
    referrals: list[ReferralBundle] = field(default_factory=list)

    def add_referral(self, referral):
        if not isinstance(referral, ReferralBundle):
            raise ValueError("invalid referral")
        if referral.ID in [item.ID for item in self.referrals]:
            raise ValueError("duplicate referral ID")
        self.referrals.append(referral)

    def checks(self):
        if not isinstance(self.name, str) or self.name.isnumeric():
            raise ValueError("invalid name")
        validate_id(self.ID)
        if not self.name.strip():
            raise ValueError("missing name")
        if not isinstance(self.birth_year, int) or isinstance(self.birth_year, bool):
            raise ValueError("birth year must be a number")
        if self.birth_year <= 0:
            raise ValueError("invalid birth year")
        if not isinstance(self.language, Language) or self.language not in [
            Language.ENGLISH,
            Language.URDU,
            Language.PASHTO,
        ]:
            raise ValueError("unknown language")
        if not isinstance(self.referrals, list):
            raise ValueError("invalid referrals")
        if any(not isinstance(item, ReferralBundle) for item in self.referrals):
            raise ValueError("invalid referral entry")
        if ReferralBundle._has_duplicate_ids(self.referrals):
            raise ValueError("duplicate referral ID")

    def __post_init__(self):
        self.checks()
