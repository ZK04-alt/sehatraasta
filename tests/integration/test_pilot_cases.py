from decimal import Decimal
from pathlib import Path
import runpy

import pytest

from sehatraasta.services.passport_service import PassportService
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.qr_service import QRService
from sehatraasta.storage import SQLiteRepository


def test_three_public_cases_import_from_clean_folder(tmp_path):
    helper = Path(__file__).resolve().parents[2] / 'scripts' / 'prepare_pilot_cases.py'
    generate = runpy.run_path(str(helper))['generate']
    output = generate(tmp_path / 'cases')
    receiver = tmp_path / 'receiving' / 'sehatraasta.sqlite'
    service = BundleService(SQLiteRepository(receiver))
    passport = PassportService(receiver)
    for index, expected in enumerate([Decimal('2500.10'), Decimal('1000.75'), Decimal('0')], start=1):
        bundle = passport.import_passport((output / f'case-{index}.zip').read_bytes(), confirmed=True)
        assert service.total_cost_pkr(bundle) == expected
        assert QRService(receiver).lookup(QRService(receiver).for_bundle(bundle)) == bundle
        assert 'data:image/png;base64,' in (output / f'case-{index}-print.html').read_text(encoding='utf-8')
    assert len(service.list_patients()) == len(service.list_bundles()) == 3
    before = (output / 'case-1.zip').read_bytes()
    with pytest.raises(ValueError, match='new output folder'):
        generate(output)
    assert (output / 'case-1.zip').read_bytes() == before
