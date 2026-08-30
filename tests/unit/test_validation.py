import pytest

from sehatraasta.domain.validation import validate_id


def test_no_error_is_raised():
    validate_id("PK-001")


def test_no_error_is_raised2():
    validate_id("SR-DEMO-001")


def test_no_error_is_raised3():
    validate_id("SR-AB-001")


def test_no_error_is_raised4():
    validate_id("SR-ELECTRONCEPHALOGRAPH-001")


def test_invalid_ID():
    with pytest.raises(ValueError, match="invalid ID"):
        validate_id(2)


def test_invalid_ID2():
    with pytest.raises(ValueError, match="invalid ID"):
        validate_id("pk-001")


def test_invalid_ID3():
    with pytest.raises(ValueError, match="invalid ID"):
        validate_id("SR-A-001")


def test_invalid_ID4():
    with pytest.raises(ValueError, match="invalid ID"):
        validate_id("SR-ELECTROENCEPHALOGRAPHY-001")


def test_missing_ID():
    with pytest.raises(ValueError, match="missing ID"):
        validate_id("")


def test_missing_ID2():
    with pytest.raises(ValueError, match="missing ID"):
        validate_id(" ")
