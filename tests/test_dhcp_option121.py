import unittest

from dhcp_option121 import decode_option121, encode_option121


class DhcpOption121Tests(unittest.TestCase):
    def test_rfc_destination_sizes_and_default_route(self):
        result = encode_option121(
            "0.0.0.0/0 192.0.2.1\n"
            "198.51.100.0/24 192.0.2.2\n"
            "10.229.0.128/25 via 192.0.2.3\n"
            "10.198.122.47/32 192.0.2.4")
        self.assertEqual(result["hex"],
                         "00c0000201"
                         "18c63364c0000202"
                         "190ae50080c0000203"
                         "200ac67a2fc0000204")
        self.assertEqual(result["wire_hex"], f"79{result['length']:02x}{result['hex']}")
        self.assertEqual(result["segments"], 1)
        self.assertEqual([route["destination"] for route in result["routes"]],
                         ["0.0.0.0/0", "198.51.100.0/24", "10.229.0.128/25",
                          "10.198.122.47/32"])

    def test_decodes_value_and_on_wire_hex(self):
        built = encode_option121("192.0.2.0/24 10.0.0.1\n0.0.0.0/0 10.0.0.254")
        value = decode_option121(built["hex"].upper())
        wire = decode_option121(":".join(built["wire_hex"][i:i + 2]
                                           for i in range(0, len(built["wire_hex"]), 2)),
                                on_wire=True)
        self.assertEqual(value["routes"], built["routes"])
        self.assertEqual(wire["routes"], built["routes"])
        self.assertEqual(wire["wire_hex"], built["wire_hex"])

    def test_long_values_are_concatenated(self):
        source = "\n".join(f"192.0.{index}.0/24 10.0.0.1" for index in range(40))
        built = encode_option121(source)
        self.assertEqual(built["length"], 320)
        self.assertEqual(built["segments"], 2)
        self.assertEqual(built["wire_hex"][:4], "79ff")
        self.assertEqual(built["wire_hex"][514:518], "7941")
        self.assertEqual(decode_option121(built["wire_hex"], on_wire=True)["routes"],
                         built["routes"])

    def test_decoder_zeroes_noncanonical_host_bits_with_warning(self):
        decoded = decode_option121("19c0000281c0000201")
        self.assertEqual(decoded["routes"][0]["destination"], "192.0.2.128/25")
        self.assertTrue(decoded["warnings"])

    def test_invalid_routes_and_hex_are_rejected(self):
        for source in ("", "192.0.2.4/24 10.0.0.1", "2001:db8::/32 10.0.0.1",
                       "192.0.2.0/24 bad", "192.0.2.0/24", "192.0.2.0/33 10.0.0.1"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                encode_option121(source)
        for source, on_wire in (("abc", False), ("gg", False), ("21c0000201", False),
                                ("18c00002", False), ("780500c0000201", True),
                                ("790500c00002", True), ("79", True), ("7900", True)):
            with self.subTest(source=source), self.assertRaises(ValueError):
                decode_option121(source, on_wire=on_wire)


if __name__ == "__main__":
    unittest.main()
