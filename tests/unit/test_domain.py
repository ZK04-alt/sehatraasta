import pytest
from datetime import date, datetime
from sehatraasta.domain import (
    Patient,
    Language,
    ReferralBundle,
    ReferralStatus,
    MedicationItem,
    Encounter,
    Attachment,
    InvestigationOrder,
    DiagnosticResult,
    ImagingItem,
)


def test_missing_id():
    with pytest.raises(ValueError, match="missing ID"):
        Patient("", "zunair", 2008, Language.ENGLISH)


def test_space_id():
    with pytest.raises(ValueError, match="missing ID"):
        Patient(" ", "zunair", 2008, Language.ENGLISH)


def test_int_id():
    with pytest.raises(ValueError, match="invalid ID"):
        Patient(1, "zunair", 2008, Language.ENGLISH)


def test_missing_name():
    with pytest.raises(ValueError, match="missing name"):
        Patient("PK-001", "", 2008, Language.ENGLISH)


def test_non_str_name():
    with pytest.raises(ValueError, match="invalid name"):
        Patient("PK-001", 12, 2008, Language.ENGLISH)


def test_invalid_id():
    with pytest.raises(ValueError, match="invalid ID"):
        Patient("f-01", "zunair", 2008, Language.ENGLISH)


def test_invalid_name():
    with pytest.raises(ValueError, match="invalid name"):
        Patient("PK-001", "01", 2008, Language.ENGLISH)


def test_non_int_birth_year():
    with pytest.raises(ValueError, match="birth year must be a number"):
        Patient("PK-001", "zunair", "hi", Language.ENGLISH)


def test_bool_birth_year():
    with pytest.raises(ValueError, match="birth year must be a number"):
        Patient("PK-001", "zunair", True, Language.ENGLISH)


def test_invalid_birth_year():
    with pytest.raises(ValueError, match="invalid birth year"):
        Patient("PK-001", "zunair", -1, Language.ENGLISH)


def test_unknown_language():
    with pytest.raises(ValueError, match="unknown language"):
        Patient("PK-001", "zunair", 2008, 4)


def test_list_len():
    patient = Patient("PK-001", "zunair", 2008, Language.ENGLISH)
    assert len(patient.referrals) == 0


def test_values():
    patient = Patient("PK-001", "zunair", 2008, Language.ENGLISH)
    assert patient.ID == "PK-001"
    assert patient.name == "zunair"
    assert patient.language == Language.ENGLISH
    assert patient.birth_year == 2008


def test_ref_values():
    dt = datetime(2026, 8, 27, 15, 30, 0)
    ref = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
    assert ref.ID == "PK-001"


def test_ref_lists_len():
    dt = datetime(2026, 8, 27, 15, 30, 0)
    ref = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
    assert len(ref.instructions) == 0
    assert len(ref.imaging_items) == 0
    assert len(ref.attachments) == 0


def test_ref_time():
    dt = "st"
    with pytest.raises(ValueError, match="invalid creation time"):
        ref = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)


def test_ref_missing_source():
    dt = datetime(2026, 8, 27, 15, 30, 0)
    with pytest.raises(ValueError, match="missing source facility"):
        ref = ReferralBundle("PK-001", dt, "", "karachi", ReferralStatus.DRAFT)


def test_ref_unknown_referral():
    dt = datetime(2026, 8, 27, 15, 30, 0)
    with pytest.raises(ValueError, match="unknown referral status"):
        ref = ReferralBundle("PK-001", dt, "lahore", "karachi", "GOON")


def test_ref_patient_relation():
    dt = datetime(2026, 8, 27, 15, 30, 0)
    ref1 = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
    ref2 = ReferralBundle("PK-002", dt, "lahore", "karachi", ReferralStatus.DRAFT)
    patient = Patient("PK-001", "zunair", 2008, Language.ENGLISH)
    patient.add_referral(ref1)
    patient.add_referral(ref2)

    assert patient.referrals[0].ID == "PK-001"
    assert len(patient.referrals) == 2


def test_ref_patient_dupe_id():
    with pytest.raises(ValueError, match="duplicate referral ID"):
        dt = datetime(2026, 8, 27, 15, 30, 0)
        ref1 = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
        ref2 = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
        patient = Patient("PK-001", "zunair", 2008, Language.ENGLISH)
        patient.add_referral(ref1)
        patient.add_referral(ref2)


def test_ref_patient_not_bundle():
    with pytest.raises(ValueError, match="invalid referral"):
        dt = datetime(2026, 8, 27, 15, 30, 0)
        ref1 = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
        ref2 = ReferralBundle("PK-001", dt, "lahore", "karachi", ReferralStatus.DRAFT)
        patient = Patient("PK-001", "zunair", 2008, Language.ENGLISH)
        grocery_list = ["mangoes", "strawberry", "coke"]
        patient.add_referral(ref1)
        patient.add_referral(grocery_list)


def test_valid_medication_item():
    medication = MedicationItem(
        "Amoxicillin",
        "500 mg",
        "1 capsule",
        "oral",
        "three times daily",
        "5 days",
        "Take after food",
        "Synthetic prescription",
        "MD-001",
    )

    assert medication.name == "Amoxicillin"
    assert medication.strength == "500 mg"
    assert medication.dose == "1 capsule"
    assert medication.route == "oral"
    assert medication.frequency == "three times daily"
    assert medication.duration == "5 days"
    assert medication.instructions == "Take after food"
    assert medication.source == "Synthetic prescription"
    assert medication.ID == "MD-001"


def test_medication_missing_name():
    with pytest.raises(ValueError, match="missing name"):
        MedicationItem(
            "",
            "500 mg",
            "1 capsule",
            "oral",
            "three times daily",
            "5 days",
            "Take after food",
            "Synthetic prescription",
            "MD-001",
        )


def test_valid_encounter_date():
    encounter_date = date(2026, 8, 27)

    encounter = Encounter(
        encounter_date,
        "Synthetic Clinic",
        "Dr Synthetic",
        "Synthetic encounter note",
    )

    assert encounter.date == encounter_date
    assert encounter.facility == "Synthetic Clinic"
    assert encounter.clinician_display_text == "Dr Synthetic"
    assert encounter.source_note == "Synthetic encounter note"


def test_encounter_rejects_datetime():
    encounter_time = datetime(2026, 8, 27, 15, 30)

    with pytest.raises(ValueError, match="invalid date"):
        Encounter(
            encounter_time,
            "Synthetic Clinic",
            "Dr Synthetic",
            "Synthetic encounter note",
        )


def test_attachment_rejects_unsupported_mime_type():
    valid_sha = "a" * 64

    with pytest.raises(ValueError, match="unsupported MIME type"):
        Attachment(
            "AT-001",
            "report",
            "synthetic-report.txt",
            "text/plain",
            valid_sha,
            date(2026, 8, 27),
            "Synthetic Clinic",
            1024.0,
        )


def test_attachment_rejects_invalid_sha():
    with pytest.raises(ValueError, match="invalid sha"):
        Attachment(
            "AT-001",
            "report",
            "synthetic-report.pdf",
            "application/pdf",
            "not-a-valid-sha",
            date(2026, 8, 27),
            "Synthetic Clinic",
            1024.0,
        )


def _make_test_bundle():
    return ReferralBundle(
        "RB-001",
        datetime(2026, 8, 27, 15, 30),
        "Synthetic Clinic",
        "Synthetic Hospital",
        ReferralStatus.DRAFT,
    )


def _make_test_order(order_date):
    return InvestigationOrder(
        "Complete blood count",
        order_date,
        "Synthetic Clinic",
        "ordered",
    )


def _make_test_attachment():
    return Attachment(
        "AT-001",
        "report",
        "synthetic-image.pdf",
        "application/pdf",
        "a" * 64,
        date(2026, 8, 27),
        "Synthetic Clinic",
        1024.0,
    )


def _make_test_imaging_item():
    return ImagingItem(
        "X-ray",
        "chest",
        date(2026, 8, 27),
        "Synthetic Clinic",
        "Synthetic imaging report",
        "IM-001",
        "AT-001",
    )


def test_result_rejects_date_before_order():
    order = _make_test_order(date(2026, 8, 27))

    with pytest.raises(ValueError, match="result date before order date"):
        DiagnosticResult(
            "Complete blood count",
            date(2026, 8, 26),
            "Synthetic Laboratory",
            "DR-001",
            "Synthetic clinician note",
            order,
        )


def test_bundle_rejects_result_with_external_order():
    bundle = _make_test_bundle()
    external_order = _make_test_order(date(2026, 8, 26))

    result = DiagnosticResult(
        "Complete blood count",
        date(2026, 8, 27),
        "Synthetic Laboratory",
        "DR-001",
        "Synthetic clinician note",
        external_order,
    )

    with pytest.raises(
        ValueError,
        match="investigation order not found in bundle",
    ):
        bundle.add_diagnostic_result(result)


def test_bundle_accepts_order_and_linked_result():
    bundle = _make_test_bundle()
    order = _make_test_order(date(2026, 8, 26))

    result = DiagnosticResult(
        "Complete blood count",
        date(2026, 8, 27),
        "Synthetic Laboratory",
        "DR-001",
        "Synthetic clinician note",
        order,
    )

    bundle.add_investigation_order(order)
    bundle.add_diagnostic_result(result)

    assert len(bundle.investigation_orders) == 1
    assert len(bundle.diagnostic_results) == 1
    assert bundle.investigation_orders[0] is order
    assert bundle.diagnostic_results[0] is result


def test_bundle_rejects_imaging_without_attachment():
    bundle = _make_test_bundle()
    imaging_item = _make_test_imaging_item()

    with pytest.raises(ValueError, match="attachment not found in bundle"):
        bundle.add_imaging_item(imaging_item)


def test_bundle_accepts_attachment_and_imaging():
    bundle = _make_test_bundle()
    attachment = _make_test_attachment()
    imaging_item = _make_test_imaging_item()

    bundle.add_attachment(attachment)
    bundle.add_imaging_item(imaging_item)

    assert len(bundle.attachments) == 1
    assert len(bundle.imaging_items) == 1
    assert bundle.attachments[0] is attachment
    assert bundle.imaging_items[0] is imaging_item


def test_bundle_rejects_duplicate_attachment_id():
    bundle = _make_test_bundle()
    first_attachment = _make_test_attachment()
    second_attachment = _make_test_attachment()

    bundle.add_attachment(first_attachment)

    with pytest.raises(ValueError, match="duplicate attachment ID"):
        bundle.add_attachment(second_attachment)
