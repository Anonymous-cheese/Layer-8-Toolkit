import socket
import unittest
import urllib.request
from unittest.mock import patch

from port_reference import load_port_registry, search_ports
from dns_helper import build_dns_record
from mtu_helper import calculate_mtu
from wifi_qr import wifi_payload, wifi_qr_png


class OfflineReferenceToolsTests(unittest.TestCase):
    def test_all_new_tools_work_with_network_calls_blocked(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network call")), \
             patch.object(urllib.request, "urlopen", side_effect=AssertionError("network call")):
            records = load_port_registry()
            self.assertEqual(search_ports(records, "53/tcp")[0][0].service, "domain")
            self.assertEqual(build_dns_record("www", "A", 300, "192.0.2.1"),
                             "www 300 IN A 192.0.2.1")
            self.assertEqual(calculate_mtu(1500)["tcp_mss"], 1460)
            self.assertTrue(wifi_qr_png(wifi_payload("Guest", "password123")).startswith(
                b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
