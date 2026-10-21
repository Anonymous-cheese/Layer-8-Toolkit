import unittest

from dns_helper import build_dns_record, reverse_ptr_owner, ttl_display
from mtu_helper import calculate_mtu, mtu_summary


class DnsHelperTests(unittest.TestCase):
    def test_common_records_and_ptr_names(self):
        self.assertEqual(build_dns_record("www", "A", "300", "192.0.2.10"),
                         "www 300 IN A 192.0.2.10")
        self.assertEqual(build_dns_record("@", "MX", 3600, "mail.example.com", priority=10),
                         "@ 3600 IN MX 10 mail.example.com.")
        self.assertEqual(build_dns_record("_sip._tcp", "SRV", 60, "sip.example.com",
                                          priority=10, weight=5, port=5060),
                         "_sip._tcp 60 IN SRV 10 5 5060 sip.example.com.")
        self.assertEqual(build_dns_record("@", "CAA", 300, "letsencrypt.org", caa_tag="issue"),
                         '@ 300 IN CAA 0 issue "letsencrypt.org"')
        self.assertEqual(reverse_ptr_owner("192.0.2.10"), "10.2.0.192.in-addr.arpa.")
        self.assertTrue(reverse_ptr_owner("2001:db8::1").endswith(".ip6.arpa."))
        self.assertEqual(ttl_display(3661), "1 hour, 1 minute, 1 second")

    def test_txt_escaping_and_chunking(self):
        line = build_dns_record("@", "TXT", 300, 'a"b\\c')
        self.assertEqual(line, '@ 300 IN TXT "a\\"b\\\\c"')
        long_line = build_dns_record("@", "TXT", 300, "x" * 300)
        self.assertIn('"' + "x" * 255 + '" "' + "x" * 45 + '"', long_line)

    def test_invalid_values_are_rejected(self):
        for args in (("bad name", "A", 300, "192.0.2.1"),
                     ("www", "A", 300, "2001:db8::1"),
                     ("www", "AAAA", 300, "192.0.2.1"),
                     ("www", "TXT", -1, "text"),
                     ("www", "CNAME", 300, "")):
            with self.assertRaises(ValueError):
                build_dns_record(*args)
        with self.assertRaises(ValueError):
            reverse_ptr_owner("not-an-ip")


class MtuHelperTests(unittest.TestCase):
    def test_baseline_and_encapsulation(self):
        plain = calculate_mtu(1500)
        self.assertEqual((plain["inner_ip_mtu"], plain["tcp_mss"], plain["udp_payload"]),
                         (1500, 1460, 1472))
        self.assertEqual(plain["ethernet_frame_bytes"], 1518)
        pppoe = calculate_mtu(1500, pppoe=True, vlan_tags=1)
        self.assertEqual((pppoe["underlay_ip_mtu"], pppoe["tcp_mss"],
                          pppoe["ethernet_frame_bytes"]), (1492, 1452, 1522))
        vxlan = calculate_mtu(1500, tunnel="VXLAN over IPv4", inner_family="IPv6")
        self.assertEqual((vxlan["inner_ip_mtu"], vxlan["tcp_mss"]), (1450, 1390))
        self.assertIn("1450", mtu_summary(vxlan))

    def test_limits_and_ipv6_warning(self):
        with self.assertRaises(ValueError):
            calculate_mtu("not a number")
        with self.assertRaises(ValueError):
            calculate_mtu(67)
        with self.assertRaises(ValueError):
            calculate_mtu(1500, vlan_tags=3)
        result = calculate_mtu(1280, pppoe=True, tunnel="GRE over IPv4", inner_family="IPv6")
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
