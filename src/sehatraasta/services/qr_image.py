"""Encode local lookup QR images without a native image-processing dependency."""
from io import BytesIO

import qrcode
from qrcode.image.pure import PyPNGImage


def render_qr_png(payload, *, box_size=10):
    """Return a black-on-white PNG; never decode an uploaded original."""
    image = qrcode.make(payload, image_factory=PyPNGImage,
                        error_correction=qrcode.constants.ERROR_CORRECT_M,
                        border=4, box_size=box_size)
    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue()
