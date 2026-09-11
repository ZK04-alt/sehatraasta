import pytest

from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType
from sehatraasta.domain.validation import validate_attachment_category


def test_attachment_category_values():
    assert AttachmentCategory.REFERRAL_LETTER.value == "referral letter"
    assert AttachmentCategory.PRESCRIPTION.value == "prescription"
    assert AttachmentCategory.MEDICATION_LIST.value == "medication list"
    assert AttachmentCategory.INVESTIGATION_ORDER.value == "investigation order"
    assert AttachmentCategory.DIAGNOSTIC_RESULT.value == "diagnostic result"
    assert AttachmentCategory.IMAGING_REPORT.value == "imaging report"
    assert AttachmentCategory.IMAGING_IMAGE.value == "imaging image"
    assert AttachmentCategory.INSTRUCTION.value == "instruction"
    assert AttachmentCategory.OTHER.value == "other"
    assert len(AttachmentCategory) == 9


def test_all_attachment_categories_are_accepted():
    for category in AttachmentCategory:
        assert validate_attachment_category(category) is None


def test_unknown_category_string():
    with pytest.raises(ValueError, match="^unsupported attachment category$"):
        validate_attachment_category("unknown")


def test_category_value_is_not_an_enum_member():
    with pytest.raises(ValueError, match="^unsupported attachment category$"):
        validate_attachment_category("prescription")


def test_none_category():
    with pytest.raises(ValueError, match="^unsupported attachment category$"):
        validate_attachment_category(None)


def test_numeric_category():
    with pytest.raises(ValueError, match="^unsupported attachment category$"):
        validate_attachment_category(123)


def test_wrong_enum_for_category():
    with pytest.raises(ValueError, match="^unsupported attachment category$"):
        validate_attachment_category(ProvenanceType.DOCUMENT)


def test_provenance_type_values():
    assert ProvenanceType.DOCUMENT.value == "document"
    assert ProvenanceType.REPORTED.value == "reported"
    assert ProvenanceType.NOT_SUPPLIED.value == "not supplied"
    assert len(ProvenanceType) == 3


def test_document_provenance_retains_values():
    provenance = Provenance(
        ProvenanceType.DOCUMENT, "Demo Clinic referral letter", "DOC-001"
    )
    assert provenance.source_type == ProvenanceType.DOCUMENT
    assert provenance.source == "Demo Clinic referral letter"
    assert provenance.source_identifier == "DOC-001"


def test_reported_provenance_retains_values():
    provenance = Provenance(
        ProvenanceType.REPORTED, "Fictional caregiver interview", "INTERVIEW-003"
    )
    assert provenance.source_type == ProvenanceType.REPORTED
    assert provenance.source == "Fictional caregiver interview"
    assert provenance.source_identifier == "INTERVIEW-003"


def test_not_supplied_defaults():
    provenance = Provenance(ProvenanceType.NOT_SUPPLIED)
    assert provenance.source_type == ProvenanceType.NOT_SUPPLIED
    assert provenance.source is None
    assert provenance.source_identifier is None


def test_not_supplied_explicit_none():
    provenance = Provenance(ProvenanceType.NOT_SUPPLIED, None, None)
    assert provenance.source is None
    assert provenance.source_identifier is None


def test_unknown_provenance_type():
    with pytest.raises(ValueError, match="^unknown provenance type$"):
        Provenance("unknown", "Demo source", "DOC-001")


def test_provenance_value_is_not_an_enum_member():
    with pytest.raises(ValueError, match="^unknown provenance type$"):
        Provenance("document", "Demo source", "DOC-001")


def test_none_provenance_type():
    with pytest.raises(ValueError, match="^unknown provenance type$"):
        Provenance(None, "Demo source", "DOC-001")


def test_wrong_enum_for_provenance_type():
    with pytest.raises(ValueError, match="^unknown provenance type$"):
        Provenance(AttachmentCategory.PRESCRIPTION, "Demo source", "DOC-001")


def test_missing_source_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source$"):
            Provenance(source_type, None, "REF-001")


def test_empty_source_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source$"):
            Provenance(source_type, "", "REF-001")


def test_blank_source_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source$"):
            Provenance(source_type, " \t\n ", "REF-001")


def test_wrong_source_type_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^invalid source$"):
            Provenance(source_type, 123, "REF-001")


def test_boolean_source_is_invalid():
    with pytest.raises(ValueError, match="^invalid source$"):
        Provenance(ProvenanceType.REPORTED, False, "REF-001")


def test_missing_identifier_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source identifier$"):
            Provenance(source_type, "Demo source", None)


def test_empty_identifier_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source identifier$"):
            Provenance(source_type, "Demo source", "")


def test_blank_identifier_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^missing source identifier$"):
            Provenance(source_type, "Demo source", " \t\n ")


def test_wrong_identifier_type_for_document_and_reported():
    for source_type in [ProvenanceType.DOCUMENT, ProvenanceType.REPORTED]:
        with pytest.raises(ValueError, match="^invalid source identifier$"):
            Provenance(source_type, "Demo source", 123)


def test_boolean_identifier_is_invalid():
    with pytest.raises(ValueError, match="^invalid source identifier$"):
        Provenance(ProvenanceType.DOCUMENT, "Demo source", True)


def test_identifier_does_not_use_patient_id_pattern():
    provenance = Provenance(
        ProvenanceType.DOCUMENT, "Demo notice", "notice reference 2026/A"
    )
    assert provenance.source_identifier == "notice reference 2026/A"


def test_source_text_is_preserved_without_rewriting():
    provenance = Provenance(
        ProvenanceType.REPORTED, "  Fictional Interview  ", "  Demo-Ref  "
    )
    assert provenance.source == "  Fictional Interview  "
    assert provenance.source_identifier == "  Demo-Ref  "


def test_not_supplied_rejects_source():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, "Demo source", None)


def test_not_supplied_rejects_identifier():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, None, "DOC-001")


def test_not_supplied_rejects_both_details():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, "Demo source", "DOC-001")


def test_not_supplied_rejects_empty_source():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, "", None)


def test_not_supplied_rejects_empty_identifier():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, None, "")


def test_not_supplied_rejects_false_source():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, False, None)


def test_not_supplied_rejects_zero_identifier():
    with pytest.raises(ValueError, match="^source details conflict with not supplied$"):
        Provenance(ProvenanceType.NOT_SUPPLIED, None, 0)
