import pytest

from parcel_tracker import Parcel, Status


def test_missing_id():
    with pytest.raises(ValueError, match="missing id"):
        Parcel("", "j", 9, Status.CREATED)
        Parcel("", "j", 67, Status.CREATED)


def test_missing_destination():
    with pytest.raises(ValueError, match="missing destination"):
        Parcel("pk01", "", 9, Status.CREATED)
        Parcel("pk02", "", 67, Status.CREATED)

def test_missing_weight():
    with pytest.raises(ValueError, match="missing weight"):
        Parcel("pk01", 'lahore',f'\n', Status.CREATED)
        Parcel("pk02", 'karachi',f'\n', Status.CREATED)

def test_non_positive_weight():
    with pytest.raises(ValueError, match="non positive weight"):
        Parcel("pk01", 'lahore', -20, Status.CREATED)
        Parcel("pk01", 'lahore', 0, Status.CREATED)
