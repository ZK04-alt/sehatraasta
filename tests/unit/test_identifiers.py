from types import SimpleNamespace
import re

import pytest

from sehatraasta.domain.validation import validate_id, validate_record_id
from sehatraasta.services.identifiers import IDAllocator, PREFIXES
from sehatraasta.storage.errors import StorageError


@pytest.mark.parametrize('kind,prefix', PREFIXES.items())
def test_compact_identifiers_have_entity_prefix_and_unambiguous_suffix(kind, prefix):
    allocator = IDAllocator(SimpleNamespace(list_patients=lambda: []))
    ID = allocator.allocate(kind)
    assert re.fullmatch(prefix + r'-[2-9A-HJ-NP-Z]{6}', ID)
    assert len(ID) == 9
    validate_record_id(ID, prefix)
    with pytest.raises(ValueError):
        validate_id(ID)  # The bundle contract was not shortened.


@pytest.mark.parametrize('ID', ['PT-000000', 'PT-OOOOOO', 'PT-111111', 'PT-IIIIII',
                             'PT-ABC12', 'PT-ABCDEFG', 'MD-ABCDEF', 'pt-ABCDEF'])
def test_wrong_prefix_ambiguous_characters_and_wrong_lengths_are_rejected(ID):
    with pytest.raises(ValueError, match='invalid ID'):
        validate_record_id(ID, 'PT', extended=True)


@pytest.mark.parametrize('ID', ['PK-001', 'SR-DEMO-001'])
def test_legacy_patient_identifiers_remain_valid(ID):
    validate_record_id(ID, 'PT', extended=True)


def test_ten_collisions_in_existing_patient_table_do_not_allocate(monkeypatch):
    patient = SimpleNamespace(ID='PT-AAAAAA', referrals=[])
    allocator = IDAllocator(SimpleNamespace(list_patients=lambda: [patient]))
    calls = []
    def choice(_):
        calls.append(1)
        return 'A'
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', choice)
    with pytest.raises(StorageError):
        allocator.allocate('patient')
    assert len(calls) == 60
