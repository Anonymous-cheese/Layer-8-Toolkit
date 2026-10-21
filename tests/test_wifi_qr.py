import struct
import unittest
from xml.etree import ElementTree

from wifi_qr import (MIXED, OPEN, PERSONAL, WEP, WPA2, WPA3, wifi_payload,
                     wifi_qr_dib, wifi_qr_png, wifi_qr_svg)


class WifiQrTests(unittest.TestCase):
    def test_personal_and_open_payloads_escape_special_characters(self):
        self.assertEqual(wifi_payload('Guest;Net', 'pass:word', PERSONAL, True),
                         r'WIFI:T:WPA;S:Guest\;Net;P:pass\:word;H:true;;')
        self.assertEqual(wifi_payload('Open,Guest', '', OPEN),
                         r'WIFI:T:nopass;S:Open\,Guest;;')

    def test_validation(self):
        for args in (("", "password", PERSONAL), ("x" * 33, "password", PERSONAL),
                     ("Guest", "short", PERSONAL), ("Guest", "password", OPEN),
                     ("Guest", "password", "unsupported")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                wifi_payload(*args)
        self.assertIn("P:", wifi_payload("Guest", "A" * 64, PERSONAL))

    def test_png_is_generated_in_memory(self):
        image = wifi_qr_png(wifi_payload("Guest", "password123"))
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", image[16:24])
        self.assertGreater(width, 100)
        self.assertEqual(width, height)

    def test_security_choices_use_compatible_payload_tokens(self):
        for security in (PERSONAL, WPA2, WPA3, MIXED):
            with self.subTest(security=security):
                self.assertIn("T:WPA", wifi_payload("Guest", "password123", security))
        self.assertIn("T:WEP", wifi_payload("Old", "abcde", WEP))
        self.assertIn("T:nopass", wifi_payload("Guest", "", OPEN))
        for password in ("four", "not-hex-10"):
            with self.assertRaises(ValueError):
                wifi_payload("Old", password, WEP)

    def test_exact_print_size_dpi_and_error_correction(self):
        payload = wifi_payload("Guest", "password123")
        for ecc in ("L", "M", "Q", "H"):
            with self.subTest(ecc=ecc):
                image = wifi_qr_png(payload, pixel_size=600, dpi=300,
                                    error_correction=ecc, border=4)
                self.assertEqual(struct.unpack(">II", image[16:24]), (600, 600))
                self.assertIn(b"pHYs", image)
        with self.assertRaises(ValueError):
            wifi_qr_png(payload, pixel_size=5000)
        with self.assertRaises(ValueError):
            wifi_qr_png(payload, pixel_size=600, border=21)

    def test_svg_and_windows_clipboard_image_bytes(self):
        payload = wifi_payload("Guest", "password123")
        svg = wifi_qr_svg(payload, error_correction="Q", border=4)
        root = ElementTree.fromstring(svg)
        self.assertEqual(root.tag,
                         "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(root[0].attrib["fill"], "white")
        dib = wifi_qr_dib(payload, pixel_size=600)
        self.assertEqual(struct.unpack("<IiiHH", dib[:16]), (40, 600, 600, 1, 24))
        self.assertEqual(len(dib), 40 + 600 * 600 * 3)


if __name__ == "__main__":
    unittest.main()
