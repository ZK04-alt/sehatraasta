"""The Android runtime must keep PNG lookup codes without Pillow installed."""
import base64
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image
import pytest
import zxingcpp

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.qr_service import QRService
from sehatraasta.storage.sqlite_repository import SQLiteRepository


@pytest.fixture
def lookup_case(tmp_path):
    database = tmp_path / "instance" / "lookup.sqlite"
    bundles = BundleService(SQLiteRepository(database))
    bundles.create_patient("PT-001", "Fictional QR patient", 1980, Language.ENGLISH)
    bundles.create_bundle("PT-001", "RB-001", datetime(2026, 10, 7),
                          "Fictional clinic", "", ReferralStatus.DRAFT)
    return database


def render_without_pillow(database, surface):
    # A fresh process prevents earlier fixture imports from hiding a PIL dependency.
    script = r'''
import importlib.abc
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "src"))
class NoPillow(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "PIL" or fullname.startswith("PIL.") or fullname == "qrcode.image.pil":
            raise ImportError("Pillow is unavailable in the Android runtime")
sys.meta_path.insert(0, NoPillow())

if sys.argv[2] == "standalone":
    from sehatraasta.services.bundle_service import BundleService
    from sehatraasta.services.print_service import PrintService
    from sehatraasta.storage.sqlite_repository import SQLiteRepository
    html = PrintService(BundleService(SQLiteRepository(sys.argv[1]))).render("RB-001")
else:
    from sehatraasta.web import create_app
    app = create_app({"TESTING": True, "DATABASE": Path(sys.argv[1]), "SECRET_KEY": "test-only"})
    response = app.test_client().get("/bundles/RB-001/print")
    assert response.status_code == 200, (response.status_code, response.text)
    html = response.text
assert not any(name == "PIL" or name.startswith("PIL.") for name in sys.modules)
sys.stdout.write(html)
'''
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script, str(database), surface],
                            cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("surface", ["standalone", "web"])
def test_printed_png_lookup_independently_decodes_without_pillow(lookup_case, surface):
    html = render_without_pillow(lookup_case, surface)
    encoded = re.search(r'data:image/png;base64,([^"\s]+)', html).group(1)
    png = base64.b64decode(encoded, validate=True)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(png)) as image:
        decoded = zxingcpp.read_barcode(image.convert("L"))
        assert decoded is not None
        # Four white modules on every side preserve the existing scan quiet zone.
        border = 4 * (8 if surface == "standalone" else 10)
        for point in ((0, 0), (border - 1, image.height // 2),
                      (image.width - border, image.height // 2)):
            assert image.convert("L").getpixel(point) == 255
    service = QRService(lookup_case)
    assert decoded.text == service.for_bundle("RB-001")
    assert service.lookup(decoded.text) == "RB-001"
    assert service.lookup_short(json.loads(decoded.text)["id"][:12]) == "RB-001"
    assert "Fictional" not in decoded.text
