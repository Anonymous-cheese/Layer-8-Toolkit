"""Offline Wi-Fi QR payloads and image formats; credentials are never persisted."""

import ctypes
from io import BytesIO
import re
import struct
import sys

import png
import qrcode
from qrcode.image.svg import SvgPathImage


OPEN = "Open (no password)"
WEP = "WEP (legacy)"
PERSONAL = "WPA/WPA2 Personal"
WPA2 = "WPA2 Personal"
WPA3 = "WPA3 Personal (compatibility QR)"
MIXED = "WPA2/WPA3 Mixed (compatibility QR)"
SECURITY_CHOICES = (PERSONAL, WPA2, WPA3, MIXED, WEP, OPEN)
ERROR_CORRECTION = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def _escape(value):
    return re.sub(r'([\\;,":])', r"\\\1", value)


def wifi_payload(ssid, password, security=PERSONAL, hidden=False):
    """Build a ZXing-compatible WIFI: payload for personal, WEP, or open Wi-Fi."""
    if not ssid or not ssid.strip():
        raise ValueError("Enter a network name (SSID).")
    if len(ssid.encode("utf-8")) > 32:
        raise ValueError("SSID must be at most 32 UTF-8 bytes.")
    if any(ord(char) < 32 or ord(char) == 127 for char in ssid):
        raise ValueError("SSID cannot contain control characters.")
    if security not in SECURITY_CHOICES:
        raise ValueError("Choose a supported Wi-Fi security type.")
    if security == OPEN:
        if password:
            raise ValueError("Clear the password for an open network.")
        token = "nopass"
    elif security == WEP:
        if not (len(password) in (5, 13, 16) and password.isascii()
                or len(password) in (10, 26, 32) and re.fullmatch(r"[0-9a-fA-F]+", password)):
            raise ValueError("WEP key must be 5, 13, or 16 ASCII characters, or 10, 26, or 32 hex digits.")
        token = "WEP"
    else:
        if not (8 <= len(password) <= 63 or
                len(password) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", password)):
            raise ValueError("Personal Wi-Fi password must be 8–63 characters or 64 hex digits.")
        token = "WPA"
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ValueError("Password cannot contain control characters.")
    fields = [f"T:{token}", f"S:{_escape(ssid)}"]
    if security != OPEN:
        fields.append(f"P:{_escape(password)}")
    if hidden:
        fields.append("H:true")
    return "WIFI:" + ";".join(fields) + ";;"


def _qr_matrix(payload, error_correction="M", border=4):
    if error_correction not in ERROR_CORRECTION:
        raise ValueError("Choose QR error correction L, M, Q, or H.")
    if type(border) is not int or not 0 <= border <= 20:
        raise ValueError("Quiet zone must be 0–20 modules.")
    qr = qrcode.QRCode(error_correction=ERROR_CORRECTION[error_correction], border=border)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr, qr.get_matrix()


def _pixel_size(matrix, box_size, pixel_size):
    if pixel_size is None:
        if type(box_size) is not int or not 1 <= box_size <= 100:
            raise ValueError("QR box size must be 1–100 pixels.")
        pixel_size = len(matrix) * box_size
    if type(pixel_size) is not int or not 128 <= pixel_size <= 4096:
        raise ValueError("QR image size must be 128–4096 pixels.")
    return pixel_size


def wifi_qr_png(payload, box_size=8, *, pixel_size=None, dpi=None,
                error_correction="M", border=4):
    """Return an exact-size black/white PNG with optional print DPI metadata."""
    _qr, matrix = _qr_matrix(payload, error_correction, border)
    size = _pixel_size(matrix, box_size, pixel_size)
    if dpi is not None and (type(dpi) is not int or not 72 <= dpi <= 1200):
        raise ValueError("Print DPI must be 72–1200.")
    modules = len(matrix)
    columns = [x * modules // size for x in range(size)]

    def rows():
        for y in range(size):
            source = matrix[y * modules // size]
            yield [0 if source[column] else 1 for column in columns]

    output = BytesIO()
    pixels_per_meter = round(dpi / 0.0254) if dpi else None
    png.Writer(width=size, height=size, greyscale=True, bitdepth=1,
               x_pixels_per_unit=pixels_per_meter,
               y_pixels_per_unit=pixels_per_meter,
               unit_is_meter=dpi is not None).write(output, rows())
    return output.getvalue()


def wifi_qr_svg(payload, *, error_correction="M", border=4):
    """Return a scalable SVG with an opaque white quiet zone."""
    qr, _matrix = _qr_matrix(payload, error_correction, border)
    svg = qr.make_image(image_factory=SvgPathImage).to_string()
    root, contents = svg.split(b">", 1)
    return root + b'><rect width="100%" height="100%" fill="white"/>' + contents


def wifi_qr_dib(payload, *, pixel_size=600, error_correction="M", border=4):
    """Return a 24-bit Windows DIB suitable for copying an image to the clipboard."""
    _qr, matrix = _qr_matrix(payload, error_correction, border)
    size = _pixel_size(matrix, 8, pixel_size)
    modules = len(matrix)
    columns = [x * modules // size for x in range(size)]
    padding = b"\0" * ((4 - size * 3 % 4) % 4)
    black, white = b"\0\0\0", b"\xff\xff\xff"
    rows = []
    for y in range(size - 1, -1, -1):
        source = matrix[y * modules // size]
        rows.append(b"".join(black if source[column] else white for column in columns) + padding)
    pixels = b"".join(rows)
    header = struct.pack("<IiiHHIIiiII", 40, size, size, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    return header + pixels


def copy_dib_to_clipboard(dib, window_handle):
    """Copy a DIB image using Windows APIs without an extra package dependency."""
    if sys.platform != "win32":
        raise OSError("Image clipboard copy is available only on Windows.")
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    if not user32.OpenClipboard(window_handle):
        raise OSError("Windows clipboard is busy. Try again.")
    memory = None
    try:
        if not user32.EmptyClipboard():
            raise OSError("Could not clear the Windows clipboard.")
        memory = kernel32.GlobalAlloc(0x0002, len(dib))  # GMEM_MOVEABLE
        if not memory:
            raise MemoryError("Could not allocate clipboard image memory.")
        pointer = kernel32.GlobalLock(memory)
        if not pointer:
            raise OSError("Could not lock clipboard image memory.")
        ctypes.memmove(pointer, dib, len(dib))
        kernel32.GlobalUnlock(memory)
        if not user32.SetClipboardData(8, memory):  # CF_DIB
            raise OSError("Could not place the QR image on the clipboard.")
        memory = None  # Windows owns the memory after SetClipboardData succeeds.
    finally:
        if memory:
            kernel32.GlobalFree(memory)
        user32.CloseClipboard()
