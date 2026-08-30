import json
from datetime import date, datetime
from decimal import Decimal

from sehatraasta.domain import (
    CostCategory,
    InvestigationOrderStatus,
    Language,
    PresenceState,
    ReferralStatus,
    ReviewCategory,
)
from sehatraasta.services import (
    AttachmentService,
    BundleService,
    CompletenessService,
    ExportService,
    SYNTHETIC_WARNING,
)
from sehatraasta.storage import JsonRepository


def make_service(tmp_path):
    repository = JsonRepository(tmp_path / "development.json")
    service = BundleService(repository)
    service.create_patient("SR-DEMO-001", "Amina Demo", 1980, Language.URDU)
    service.create_bundle(
        "SR-DEMO-001",
        "RB-001",
        datetime(2026, 8, 30, 10, 0),
        "Demo BHU",
        "Demo District Hospital - Orthopaedics",
        ReferralStatus.DRAFT,
    )
    return service


def test_service_creates_and_retains_patient_bundle(tmp_path):
    service = make_service(tmp_path)

    restarted = BundleService(JsonRepository(tmp_path / "development.json"))
    patient, bundle = restarted.get_bundle_owner("RB-001")

    assert patient.name == "Amina Demo"
    assert patient.language == Language.URDU
    assert bundle.source_facility == "Demo BHU"
    assert bundle.destination == "Demo District Hospital - Orthopaedics"


def test_service_adds_required_bundle_records(tmp_path):
    service = make_service(tmp_path)
    attachments = AttachmentService(service)
    order = service.add_order(
        "RB-001",
        "X-ray",
        date(2026, 8, 30),
        "Demo BHU",
        InvestigationOrderStatus.ORDERED,
    )
    service.add_medication(
        "RB-001",
        "MD-001",
        "Demo medicine",
        "10 mg",
        "one tablet",
        "oral",
        "once daily",
        "five days",
        "Take after a fictional meal.",
        "synthetic referral note",
    )
    service.add_result(
        "RB-001",
        "DR-001",
        "X-ray result",
        date(2026, 8, 30),
        "Demo District Hospital",
        "Pending",
        order.name,
    )
    service.add_instruction(
        "RB-001",
        "follow-up",
        Language.URDU,
        "Synthetic follow-up instruction",
        "synthetic referral note",
        date(2026, 8, 30),
    )
    attachments.add_metadata(
        "RB-001",
        "AT-001",
        "imaging",
        "demo-xray.png",
        "image/png",
        "a" * 64,
        date(2026, 8, 30),
        "synthetic attachment metadata",
        1200,
    )
    service.add_imaging(
        "RB-001",
        "IM-001",
        "X-ray",
        "knee",
        date(2026, 8, 30),
        "Demo District Hospital",
        "Pending",
        "AT-001",
    )

    restarted = BundleService(JsonRepository(tmp_path / "development.json"))
    bundle = restarted.get_bundle("RB-001")

    assert len(bundle.medication_item) == 1
    assert len(bundle.investigation_orders) == 1
    assert bundle.diagnostic_results[0].investigation_order.name == "X-ray"
    assert len(bundle.instructions) == 1
    assert len(bundle.attachments) == 1
    assert bundle.imaging_items[0].Attachment_ID == "AT-001"


def test_completeness_keeps_unreviewed_separate_from_missing(tmp_path):
    service = make_service(tmp_path)
    review_time = datetime(2026, 8, 30, 11, 0)
    service.set_category_review(
        "RB-001",
        ReviewCategory.MEDICATION_LIST,
        PresenceState.PRESENT,
        "Medication list reviewed",
        review_time,
        "synthetic review",
    )
    service.set_category_review(
        "RB-001",
        ReviewCategory.IMAGING_REPORTS,
        PresenceState.PENDING,
        "Imaging report pending",
        review_time,
        "synthetic review",
    )

    groups = CompletenessService().group_categories(service.get_bundle("RB-001"))

    assert ReviewCategory.MEDICATION_LIST in groups["present"]
    assert ReviewCategory.IMAGING_REPORTS in groups["pending"]
    assert ReviewCategory.COSTS in groups["not_reviewed"]
    assert groups["missing"] == []


def test_cost_service_uses_exact_decimal_total(tmp_path):
    service = make_service(tmp_path)
    service.add_cost(
        "RB-001",
        "CO-001",
        CostCategory.TRAVEL,
        Decimal("2500.10"),
        date(2026, 8, 30),
        "demo interview response",
    )
    service.add_cost(
        "RB-001",
        "CO-002",
        CostCategory.MEDICATION,
        Decimal("0.20"),
        date(2026, 8, 30),
        "synthetic receipt",
    )

    assert service.total_cost_pkr("RB-001") == Decimal("2500.30")
    assert [item.ID for item in service.list_cost_entries("RB-001")] == [
        "CO-001",
        "CO-002",
    ]


def test_export_is_human_readable_and_contains_synthetic_warning(tmp_path):
    service = make_service(tmp_path)
    service.add_cost(
        "RB-001",
        "CO-001",
        CostCategory.TRAVEL,
        Decimal("2500.00"),
        date(2026, 8, 30),
        "demo interview response",
    )
    output = tmp_path / "export.json"

    ExportService(service).export_bundle("RB-001", output)

    text = output.read_text(encoding="utf-8")
    document = json.loads(text)
    assert "\n  \"warning\"" in text
    assert document["warning"] == SYNTHETIC_WARNING
    assert document["bundle"]["destination"].endswith("Orthopaedics")
    assert document["total_cost_pkr"] == "2500.00"
