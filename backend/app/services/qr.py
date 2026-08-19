"""QR kodu uretimi (qrcode + pillow, ikisi de izin verilen lisanslarda)."""

from __future__ import annotations

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_png(payload: str, *, box_size: int = 8, border: int = 2) -> bytes:
    """Verilen icerigi PNG bayt dizisi olarak QR koda cevirir."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#3B0A14", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
