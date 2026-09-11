import pytest

from sehatraasta.services.attachment_validation import (
    validate_attachment_filename,
    validate_attachment_signature,
    validate_attachment_size,
)


def test_pdf_filename():
    assert validate_attachment_filename("demo.pdf") == ".pdf"


def test_png_filename():
    assert validate_attachment_filename("demo.png") == ".png"


def test_jpg_filename():
    assert validate_attachment_filename("demo.jpg") == ".jpg"


def test_jpeg_filename():
    assert validate_attachment_filename("demo.jpeg") == ".jpeg"


def test_uppercase_extension():
    assert validate_attachment_filename("Report.PDF") == ".pdf"


def test_extra_dot_in_filename():
    assert validate_attachment_filename("demo.report.pdf") == ".pdf"


def test_spaces_inside_filename():
    assert validate_attachment_filename("demo report.pdf") == ".pdf"


def test_numeric_filename_with_extension():
    assert validate_attachment_filename("123.pdf") == ".pdf"


def test_empty_filename():
    with pytest.raises(ValueError, match="^missing attachment filename$"):
        validate_attachment_filename("")


def test_whitespace_only_filename():
    with pytest.raises(ValueError, match="^missing attachment filename$"):
        validate_attachment_filename("   ")


def test_tab_only_filename():
    with pytest.raises(ValueError, match="^missing attachment filename$"):
        validate_attachment_filename("\t")


def test_non_string_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename(123)


def test_none_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename(None)


def test_missing_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_filename("demo-report")


def test_numeric_filename_without_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_filename("123")


def test_unsupported_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_filename("demo.txt")


def test_disguised_executable_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_filename("demo.pdf.exe")


def test_forward_slash_in_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("../demo.pdf")


def test_single_backslash_in_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("folder\\demo.pdf")


def test_tab_inside_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("demo\treport.pdf")


def test_newline_inside_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("demo\nreport.pdf")


def test_null_character_inside_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("demo\x00report.pdf")


def test_carriage_return_inside_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("demo\rreport.pdf")


def test_other_control_character_inside_filename():
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename("demo\x01report.pdf")


def test_filename_at_length_limit():
    name = "a" * 146 + ".pdf"
    assert len(name) == 150
    assert validate_attachment_filename(name) == ".pdf"


def test_filename_over_length_limit():
    name = "a" * 147 + ".pdf"
    with pytest.raises(ValueError, match="^invalid attachment filename$"):
        validate_attachment_filename(name)


def test_original_unicode_filename_at_length_limit():
    # Capital dotted I expands to two characters when lowercased.
    # The limit applies to the supplied name, not a lowercased replacement.
    name = "\u0130" * 146 + ".pdf"
    assert len(name) == 150
    assert validate_attachment_filename(name) == ".pdf"


def test_minimum_file_size():
    assert validate_attachment_size(1) is None


def test_small_file_size():
    assert validate_attachment_size(2500) is None


def test_file_size_just_below_limit():
    assert validate_attachment_size(5242879) is None


def test_file_size_at_limit():
    assert validate_attachment_size(5242880) is None


def test_file_size_above_limit():
    with pytest.raises(ValueError, match="^file too large$"):
        validate_attachment_size(5242881)


def test_zero_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size(0)


def test_negative_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size(-1)


def test_string_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size("2500")


def test_float_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size(2500.0)


def test_true_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size(True)


def test_false_file_size():
    with pytest.raises(ValueError, match="^invalid file size$"):
        validate_attachment_size(False)


def test_pdf_signature():
    assert validate_attachment_signature(".pdf", b"%PDF-1.7") == "application/pdf"


def test_png_signature():
    assert validate_attachment_signature(".png", b"\x89PNG\r\n\x1a\n") == "image/png"


def test_jpg_signature():
    assert validate_attachment_signature(".jpg", b"\xff\xd8\xff\xe0") == "image/jpeg"


def test_jpeg_signature():
    assert validate_attachment_signature(".jpeg", b"\xff\xd8\xff\xe1") == "image/jpeg"


def test_signature_with_additional_bytes():
    header = b"\x89PNG\r\n\x1a\nfictional test bytes"
    assert validate_attachment_signature(".png", header) == "image/png"


def test_signature_does_not_match_extension():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".pdf", b"\x89PNG\r\n\x1a\n")


def test_ordinary_text_is_not_pdf_signature():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".pdf", b"Fictional club notice")


def test_incomplete_png_signature():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".png", b"\x89PN")


def test_incomplete_pdf_signature():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".pdf", b"%PDF")


def test_incomplete_jpeg_signature():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".jpeg", b"\xff\xd8")


def test_empty_signature():
    with pytest.raises(ValueError, match="^file type does not match extension$"):
        validate_attachment_signature(".pdf", b"")


def test_header_must_be_bytes():
    with pytest.raises(ValueError, match="^invalid file header$"):
        validate_attachment_signature(".pdf", "%PDF-1.7")


def test_none_header():
    with pytest.raises(ValueError, match="^invalid file header$"):
        validate_attachment_signature(".png", None)


def test_signature_unsupported_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_signature(".exe", b"%PDF-1.7")


def test_signature_non_string_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_signature(123, b"%PDF-1.7")


def test_signature_requires_normalized_extension():
    with pytest.raises(ValueError, match="^unsupported file extension$"):
        validate_attachment_signature(".PDF", b"%PDF-1.7")
