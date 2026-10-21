import ipaddress
import unittest

from network_tools import (
    DHCP_COMMON_OPTIONS, cisco_type7_decrypt, decimal_ip_details, dhcp_option43_cisco_wlc,
    dhcp_option43_raw_hex, dhcp_option43_tlv, dhcp_option_value,
    ipv4_details, ipv6_details, ipv6_subnet_page, mac_details, wildcard_details,
)


class NetworkToolsTests(unittest.TestCase):
    def test_cisco_type7_known_value_and_config_line(self):
        self.assertEqual(cisco_type7_decrypt("02050D480809"), "cisco")
        self.assertEqual(cisco_type7_decrypt("username admin password 7 02050d480809"), "cisco")
        self.assertEqual(cisco_type7_decrypt(" 7 02050D480809 "), "cisco")
        self.assertEqual(cisco_type7_decrypt(
            "username jdoe password 7 07362E590E1B1C041B1E124C0A2F2E206832752E1A01134D"),
            "You really need a life.")

    def test_cisco_type7_rejects_invalid_values(self):
        for value in ("", "02", "02050", "16050D480809", "AA050D480809",
                      "password 5 02050D480809", "password 7 02050D4808GG"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cisco_type7_decrypt(value)

    def test_boson_ipv4_example_and_navigation(self):
        result = ipv4_details("10.3.3.3", "24")
        self.assertEqual(str(result["network"]), "10.3.3.0/24")
        self.assertEqual(str(result["first"]), "10.3.3.1")
        self.assertEqual(str(result["last"]), "10.3.3.254")
        self.assertEqual(result["subnet_bits"], 16)
        self.assertEqual(result["max_subnets"], 65536)
        self.assertEqual(str(result["previous"]), "10.3.2.0")
        self.assertEqual(str(result["next"]), "10.3.4.0")

    def test_ipv4_edge_prefixes_and_mask_input(self):
        self.assertEqual(ipv4_details("192.0.2.4", "255.255.255.254")["usable"], 2)
        self.assertEqual(ipv4_details("192.0.2.4/32")["usable"], 1)
        self.assertIsNone(ipv4_details("0.0.0.0/0")["previous"])
        self.assertIsNone(ipv4_details("255.255.255.255/32")["next"])

    def test_ipv6_network_and_navigation(self):
        result = ipv6_details("2001:db8:1234::1/64")
        self.assertEqual(str(result["network"]), "2001:db8:1234::/64")
        self.assertEqual(str(result["next"]), "2001:db8:1234:1::")
        self.assertEqual(result["host_bits"], 64)
        self.assertEqual(result["total"], 2 ** 64)
        self.assertEqual(result["type"], "documentation")
        self.assertEqual(ipv6_details("fc00::1/64")["type"], "unique local")

    def test_ipv6_subnet_planning_is_bounded(self):
        parent = ipaddress.IPv6Network("2001:db8::/32")
        plan = ipv6_subnet_page(parent, 48, page=1)
        self.assertEqual(plan["count"], 65536)
        self.assertEqual(plan["pages"], 8192)
        self.assertEqual(plan["rows"][0][1], ipaddress.IPv6Network("2001:db8:8::/48"))
        with self.assertRaises(ValueError):
            ipv6_subnet_page(parent, 31)

    def test_wildcard_noncontiguous_matching(self):
        match = wildcard_details("10.2.3.4", "0.0.0.254", "10.2.3.100")
        miss = wildcard_details("10.2.3.4", "0.0.0.254", "10.2.3.101")
        self.assertTrue(match["matched"])
        self.assertFalse(miss["matched"])
        self.assertIsNone(match["prefix"])
        self.assertEqual(match["count"], 128)

    def test_decimal_roundtrip(self):
        dotted = decimal_ip_details("10.3.3.3")
        self.assertEqual(decimal_ip_details(str(dotted["integer"]))["address"], dotted["address"])
        self.assertEqual(decimal_ip_details(dotted["hex"])["address"], dotted["address"])
        with self.assertRaises(ipaddress.AddressValueError):
            decimal_ip_details("4294967296")

    def test_mac_formats_and_vendor_lookup(self):
        result = mac_details("aabb.ccdd.eeff", lambda _mac: "Example Vendor")
        self.assertEqual(result["colon"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(result["hyphen"], "AA-BB-CC-DD-EE-FF")
        self.assertEqual(result["oui"], "AA:BB:CC")
        self.assertEqual(result["vendor"], "Example Vendor")
        self.assertEqual(result["assignment"], "Locally administered")
        with self.assertRaises(ValueError):
            mac_details("aa:bb:cc", lambda _mac: "")

    def test_common_dhcp_option_values(self):
        self.assertEqual(dhcp_option_value(1, "24")["wire_hex"], "0104ffffff00")
        self.assertEqual(dhcp_option_value(3, "192.0.2.1, 192.0.2.2")["hex"],
                         "c0000201c0000202")
        self.assertEqual(dhcp_option_value(6, "10.0.0.1")["hex"], "0a000001")
        self.assertEqual(dhcp_option_value(15, "example.com")["hex"],
                         "6578616d706c652e636f6d")
        self.assertEqual(dhcp_option_value(51, "3600")["wire_hex"], "330400000e10")
        self.assertEqual(dhcp_option_value(150, "10.1.1.1")["wire_hex"], "96040a010101")
        self.assertIn(43, DHCP_COMMON_OPTIONS)
        self.assertIn(121, DHCP_COMMON_OPTIONS)
        with self.assertRaises(ValueError):
            dhcp_option_value(121, "0.0.0.0/0 192.0.2.1")
        for code, value in ((1, "255.0.255.0"), (3, "not-an-ip"),
                            (15, "café"), (51, "0"), (51, "4294967296")):
            with self.subTest(code=code, value=value), self.assertRaises(ValueError):
                dhcp_option_value(code, value)

    def test_option43_cisco_wlc_and_vendor_payloads(self):
        cisco = dhcp_option43_cisco_wlc("192.168.10.5, 192.168.10.20")
        self.assertEqual(cisco["hex"], "f108c0a80a05c0a80a14")
        self.assertEqual(cisco["wire_hex"], "2b0af108c0a80a05c0a80a14")
        self.assertEqual(cisco["ios"], "option 43 hex f108c0a80a05c0a80a14")
        self.assertEqual(cisco["suboptions"][0]["length"], 8)
        custom = dhcp_option43_tlv("1=hex:DE AD\n2=ascii:Hi\n3=ipv4:192.0.2.1")
        self.assertEqual(custom["hex"], "0102dead020248690304c0000201")
        self.assertEqual(custom["length"], 14)
        self.assertEqual(dhcp_option43_raw_hex("F1:04:C0:A8:01:0A")["hex"],
                         "f104c0a8010a")
        self.assertEqual(dhcp_option43_raw_hex("F1:04:C0:A8:01:0A")["suboptions"], [])

    def test_option43_rejects_invalid_or_oversize_data(self):
        for builder, text in (
            (dhcp_option43_cisco_wlc, ""),
            (dhcp_option43_cisco_wlc, "192.0.2.999"),
            (dhcp_option43_cisco_wlc, " ".join(["192.0.2.1"] * 64)),
            (dhcp_option43_tlv, "0=hex:01"),
            (dhcp_option43_tlv, "255=hex:01"),
            (dhcp_option43_tlv, "1=hex:ABC"),
            (dhcp_option43_tlv, "1=ascii:café"),
            (dhcp_option43_tlv, "1=hex:" + "AA" * 254),
            (dhcp_option43_raw_hex, "GG"),
            (dhcp_option43_raw_hex, "AA" * 256),
        ):
            with self.subTest(builder=builder.__name__, text=text[:20]), self.assertRaises(ValueError):
                builder(text)


if __name__ == "__main__":
    unittest.main()
