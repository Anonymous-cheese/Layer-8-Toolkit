import tempfile
import unittest
from pathlib import Path

from port_reference import load_port_registry, search_ports


class PortReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_port_registry()

    def test_bundled_iana_snapshot_searches_number_and_use(self):
        self.assertGreater(len(self.records), 10000)
        dns, total = search_ports(self.records, "53/tcp")
        self.assertGreaterEqual(total, 1)
        self.assertEqual((dns[0].port, dns[0].protocol, dns[0].service),
                         ("53", "tcp", "domain"))
        rdp, total = search_ports(self.records, "remote desktop")
        self.assertGreaterEqual(total, 2)
        self.assertEqual(rdp[0].port, "3389")
        self.assertIn("RDP", rdp[0].common_use)
        web, _total = search_ports(self.records, "secure web")
        self.assertEqual(web[0].port, "443")

    def test_protocol_filter_and_port_range(self):
        udp, total = search_ports(self.records, "53", protocol="udp")
        self.assertGreaterEqual(total, 1)
        self.assertTrue(all(record.protocol == "udp" for record in udp))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ports.csv"
            path.write_text("Service Name,Port Number,Transport Protocol,Description\n"
                            "sample,100-110,tcp,Sample range\n", encoding="utf-8")
            rows = load_port_registry(path)
            self.assertEqual(search_ports(rows, "105")[0][0].port, "100-110")
        with self.assertRaisesRegex(ValueError, "0 through 65535"):
            search_ports(self.records, "65536")


if __name__ == "__main__":
    unittest.main()
