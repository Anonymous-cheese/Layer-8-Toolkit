import ipaddress
import unittest

from site_planner import parse_vlan_template, plan_sites, site_plan_rows


TEMPLATE = """10, Utility, /25
11, Data, /24
12, Voice, /24
13, Wi-Fi, /24
14, Guest, /25"""


class SitePlannerTests(unittest.TestCase):
    def test_example_exact_fit_and_all_64_sites(self):
        plan = plan_sites("10.0.0.0/16", TEMPLATE, "auto", "64")
        self.assertEqual(plan["minimum_site_prefix"], 22)
        self.assertEqual(plan["site_prefix"], 22)
        self.assertEqual(plan["required_per_site"], 1024)
        self.assertEqual(plan["max_sites"], 64)
        self.assertEqual(plan["free_per_site"], 0)
        self.assertEqual(str(plan["sites"][0]["network"]), "10.0.0.0/22")
        self.assertEqual(str(plan["sites"][1]["network"]), "10.0.4.0/22")
        self.assertEqual(str(plan["sites"][-1]["network"]), "10.0.252.0/22")
        self.assertEqual([vlan["vlan"] for vlan in plan["sites"][0]["vlans"]],
                         [10, 11, 12, 13, 14])
        self.assertEqual(str(plan["sites"][0]["vlans"][0]["network"]), "10.0.3.0/25")
        self.assertEqual(str(plan["sites"][0]["vlans"][4]["network"]), "10.0.3.128/25")
        self.assertEqual(plan["sites"][0]["free_networks"], [])

    def test_growth_block_and_export_rows(self):
        plan = plan_sites("10.0.0.0/16", TEMPLATE, "/21", "32")
        self.assertEqual(plan["max_sites"], 32)
        self.assertEqual(plan["free_per_site"], 1024)
        self.assertEqual(str(plan["sites"][1]["network"]), "10.0.8.0/21")
        self.assertEqual([str(network) for network in plan["sites"][0]["free_networks"]],
                         ["10.0.4.0/22"])
        rows = list(site_plan_rows(plan))
        self.assertEqual(len(rows), 32 * 6)
        self.assertEqual(rows[0][:4], (1, "10.0.0.0/21", 10, "Utility"))
        self.assertEqual(rows[5][3:6], ("Unallocated", "10.0.4.0/22", 1024))

    def test_allocations_are_aligned_nonoverlapping_and_inside_site(self):
        plan = plan_sites("10.0.0.0/16", "1, Small, /27\n2, Large, /24\n3, Medium, /26", "/23", "3")
        self.assertEqual(plan["minimum_site_prefix"], 23)
        self.assertEqual(plan["free_per_site"], 160)
        for site in plan["sites"]:
            allocated = [vlan["network"] for vlan in site["vlans"]]
            self.assertTrue(all(network.subnet_of(site["network"]) for network in allocated))
            self.assertTrue(all(not left.overlaps(right) for index, left in enumerate(allocated)
                                for right in allocated[index + 1:]))
            free = site["free_networks"]
            self.assertEqual(sum(network.num_addresses for network in free), 160)
            self.assertTrue(all(not network.overlaps(vlan) for network in free for vlan in allocated))

    def test_template_csv_and_validation(self):
        parsed = parse_vlan_template('# comment\n10,"Data, staff", /24\n11, Guest, 25')
        self.assertEqual(parsed[0]["name"], "Data, staff")
        self.assertEqual(parsed[1]["prefix"], 25)
        for text in ("", "10, Name", "0, Name, /24", "4095, Name, /24",
                     "10, Name, /33", "10, Name, /24\n10, Other, /25"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_vlan_template(text)

    def test_parent_fit_count_and_size_validation(self):
        invalid = (
            ("10.0.1.0/16", TEMPLATE, "auto", "1"),
            ("2001:db8::/32", TEMPLATE, "auto", "1"),
            ("10.0.0.0/24", TEMPLATE, "auto", "1"),
            ("10.0.0.0/16", TEMPLATE, "/23", "1"),
            ("10.0.0.0/16", TEMPLATE, "/15", "1"),
            ("10.0.0.0/16", TEMPLATE, "/21", "33"),
            ("10.0.0.0/16", TEMPLATE, "nonsense", "1"),
            ("10.0.0.0/16", TEMPLATE, "auto", "0"),
            ("10.0.0.0/16", TEMPLATE, "auto", "1.5"),
            ("10.0.0.0/8", "1, Tiny, /32", "/24", "513"),
        )
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                plan_sites(*args)

    def test_single_address_prefix_and_multi_block_spare(self):
        plan = plan_sites("192.0.2.0/24", "10, Host, /32", "/29", "2")
        self.assertEqual(plan["minimum_site_prefix"], 32)
        self.assertEqual(plan["sites"][0]["vlans"][0]["usable"], 1)
        self.assertEqual(plan["sites"][0]["free_networks"],
                         [ipaddress.IPv4Network("192.0.2.1/32"),
                          ipaddress.IPv4Network("192.0.2.2/31"),
                          ipaddress.IPv4Network("192.0.2.4/30")])


if __name__ == "__main__":
    unittest.main()
