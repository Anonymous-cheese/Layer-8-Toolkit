import struct
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from app_preferences import THEMES
from tools_ui import NetworkToolsView
from wifi_qr import OPEN, WPA3


class MacFormatterUiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.view = NetworkToolsView(
            self.root, lambda _mac: "Example Vendor", lambda _status: None,
            lambda: THEMES["dark"],
        )

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_compact_list_and_full_detail_copy(self):
        self.view.mac_input.delete("1.0", "end")
        self.view.mac_input.insert("1.0", "aabb.ccdd.eeff\n0000.0c12.3456")
        self.view.calculate_macs()
        items = self.view.mac_tree.get_children()
        self.assertEqual(len(items), 2)
        self.assertEqual(self.view.mac_tree["columns"],
                         ("input", "vendor", "oui", "assignment"))
        self.assertEqual(self.view.mac_detail_values["cisco"].get(), "AABB.CCDD.EEFF")

        self.view.mac_tree.selection_set(items[1])
        self.view._show_mac_details()
        self.assertEqual(self.view.mac_detail_values["cisco"].get(), "0000.0C12.3456")
        self.assertEqual(self.view.mac_detail_values["vendor"].get(), "Example Vendor")

        copied = []
        self.view._copy = copied.append
        self.view._copy_mac_results()
        rows = copied[0].splitlines()
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0].split("\t")), 10)
        self.assertIn("0000.0C12.3456", rows[2])

    def test_tools_surface_styles_and_outer_spacing(self):
        self.assertEqual(self.view.cget("style"), "ToolsSurface.TFrame")
        self.assertEqual(self.view.tabs.cget("style"), "ToolsSurface.TNotebook")
        self.assertEqual(int(self.view.tabs.pack_info()["padx"]), 0)
        page = self.view.tabs.nametowidget(self.view.tabs.tabs()[0])
        self.assertEqual(page.cget("style"), "ToolsSurface.TFrame")
        labels = [child for child in page.winfo_children() if isinstance(child, tk.Widget)
                  and child.winfo_class() == "TLabel"]
        self.assertTrue(all(label.cget("style").startswith("Tools") for label in labels))

    def test_dhcp_option_selector_and_generators(self):
        self.view.dhcp_wlc_input.insert("1.0", "192.168.10.5,192.168.10.20")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_hex.get(), "f108c0a80a05c0a80a14")
        self.assertEqual(len(self.view.dhcp_breakdown.get_children()), 1)
        self.view.dhcp_choice.set("6 — DNS servers")
        self.view._switch_dhcp_option()
        self.assertEqual(self.view.dhcp_ios_row.winfo_manager(), "")
        self.view.dhcp_input.insert("1.0", "10.1.1.1")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_wire.get(), "06040a010101")
        self.view.dhcp_input.delete("1.0", "end")
        self.view.dhcp_input.insert("1.0", "bad")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_hex.get(), "")
        self.assertTrue(self.view.dhcp_error.get())
        self.view.dhcp_choice.set("43 — Vendor-specific")
        self.view._switch_dhcp_option()
        self.view.dhcp_43_mode.set("Raw hex")
        self.view._switch_dhcp_43_mode()
        self.view.dhcp_raw_input.insert("1.0", "01:02:AA:BB")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_wire.get(), "2b040102aabb")

    def test_dhcp_editable_inputs_are_visually_distinct(self):
        self.view.apply_theme(THEMES["dark"])
        self.assertNotEqual(self.view.dhcp_wlc_input.cget("background"), THEMES["dark"]["entry_bg"])
        self.assertEqual(self.view.dhcp_wlc_input.cget("background"), THEMES["dark"]["tool_input_bg"])
        self.assertEqual(int(self.view.dhcp_wlc_input.cget("highlightthickness")), 2)
        self.assertEqual(self.view.dhcp_input.cget("background"), THEMES["dark"]["tool_input_bg"])
        self.assertEqual(self.view.dhcp_121_build_input.cget("background"), THEMES["dark"]["tool_input_bg"])
        self.assertEqual(self.view.dhcp_121_decode_input.cget("background"), THEMES["dark"]["tool_input_bg"])
        self.view.apply_theme(THEMES["light"])
        self.assertEqual(self.view.dhcp_wlc_input.cget("background"), THEMES["light"]["tool_input_bg"])

    def test_site_planner_capacity_copy_export_and_stale_results(self):
        self.assertIn("Site Planner", self.view.page_frames)
        self.view.site_block_prefix.set("/21")
        self.view.site_count.set("2")
        self.view._generate_site_plan()
        self.assertEqual(self.view.site_plan["max_sites"], 32)
        self.assertEqual(self.view.site_plan["free_per_site"], 1024)
        self.assertEqual(len(self.view.site_tree.get_children()), 2)
        first = self.view.site_tree.get_children()[0]
        self.assertEqual(len(self.view.site_tree.get_children(first)), 6)
        self.assertIn("4 × /24 equivalent", self.view.site_space_summary.get())

        copied = []
        self.view._copy = copied.append
        self.view.site_tree.selection_set(first)
        self.view._copy_site_cidr()
        self.assertEqual(copied[-1], "10.0.0.0/21")
        self.view._copy_site_plan()
        self.assertIn("10.0.4.0/22", copied[-1])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "site-plan.csv"
            with patch("tools_ui.filedialog.asksaveasfilename", return_value=str(path)):
                self.view._export_site_plan()
            self.assertIn("10.0.4.0/22", path.read_text(encoding="utf-8-sig"))

        self.view.site_count.set("bad")
        self.assertIsNone(self.view.site_plan)
        self.assertFalse(self.view.site_tree.get_children())
        self.assertEqual(str(self.view.site_copy_plan_button.cget("state")), "disabled")
        self.view._generate_site_plan()
        self.assertTrue(self.view.site_error.get())

    def test_site_template_uses_customizable_input_color(self):
        self.view.apply_theme(THEMES["dark"])
        self.assertEqual(self.view.site_template.cget("background"), THEMES["dark"]["tool_input_bg"])

    def test_site_planner_help_expands_inside_page(self):
        self.assertEqual(self.view.site_help.winfo_manager(), "")
        self.view.site_help_button.invoke()
        self.assertEqual(self.view.site_help.winfo_manager(), "pack")
        self.assertIn(self.view.site_help, self.view.page_frames["Site Planner"].winfo_children())
        help_text = "\n".join(label.cget("text") for label in self.view.site_help.winfo_children())
        self.assertIn("Example: 10, Utility, /25", help_text)
        self.assertIn("Auto uses /22", help_text)
        self.view.site_help_button.invoke()
        self.assertEqual(self.view.site_help.winfo_manager(), "")

    def test_option121_builder_and_decoder_modes(self):
        self.view.dhcp_choice.set("121 — Classless static routes")
        self.view._switch_dhcp_option()
        self.assertEqual(self.view.dhcp_121_frame.winfo_manager(), "pack")
        self.assertEqual(self.view.dhcp_43_frame.winfo_manager(), "")
        self.assertEqual(self.view.dhcp_breakdown.heading("code")["text"], "Destination")
        self.view.dhcp_121_build_input.insert("1.0", "0.0.0.0/0 192.0.2.1\n198.51.100.0/24 192.0.2.2")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_hex.get(), "00c000020118c63364c0000202")
        self.assertEqual(len(self.view.dhcp_breakdown.get_children()), 2)
        self.assertIn("2 route(s)", self.view.dhcp_length.get())
        self.view.dhcp_121_mode.set("Decode value hex")
        self.view._switch_dhcp_121_mode()
        self.assertEqual(self.view.dhcp_hex.get(), "")
        self.assertEqual(self.view.dhcp_generate_button.cget("text"), "Decode hex")
        self.view.dhcp_121_decode_input.insert("1.0", "00c000020118c63364c0000202")
        self.view.generate_dhcp()
        self.assertEqual(len(self.view.dhcp_breakdown.get_children()), 2)
        self.assertEqual(self.view.dhcp_breakdown.item(
            self.view.dhcp_breakdown.get_children()[1], "values")[2], "192.0.2.2")
        self.view.dhcp_121_mode.set("Decode on-wire hex")
        self.view._switch_dhcp_121_mode()
        self.view.dhcp_121_decode_input.delete("1.0", "end")
        self.view.dhcp_121_decode_input.insert("1.0", "790d00c000020118c63364c0000202")
        self.view.generate_dhcp()
        self.assertEqual(self.view.dhcp_error.get(), "")
        self.assertEqual(self.view.dhcp_wire.get(), "790d00c000020118c63364c0000202")

    def test_type7_decoder_masks_plaintext_and_clears_stale_results(self):
        self.view.type7_input.set("02050D480809")
        self.view._decrypt_type7()
        self.assertEqual(self.view.type7_output.get(), "cisco")
        self.assertEqual(self.view.type7_output_entry.cget("show"), "•")
        self.view.type7_visible.set(True)
        self.view._toggle_type7_reveal()
        self.assertEqual(self.view.type7_output_entry.cget("show"), "")
        self.view.type7_input.set("bad")
        self.assertEqual(self.view.type7_output.get(), "")
        self.assertEqual(self.view.type7_output_entry.cget("show"), "•")
        self.view._decrypt_type7()
        self.assertTrue(self.view.type7_error.get())
        self.view._clear_type7()
        self.assertEqual(self.view.type7_input.get(), "")
        self.assertEqual(self.view.type7_error.get(), "")

    def test_port_reference(self):
        self.view.port_query.set("remote desktop")
        self.view._refresh_port_results()
        self.assertEqual(self.view.port_visible_records[0].port, "3389")
        self.assertTrue(self.view.port_tree.get_children())

    def test_wifi_qr_preview_is_local_and_clears_on_edit(self):
        self.view.wifi_ssid.set("Guest")
        self.view.wifi_password.set("password123")
        self.view.generate_wifi_qr()
        self.assertTrue(self.view.wifi_qr_payload.startswith("WIFI:T:WPA;"))
        self.assertGreater(self.view.wifi_qr_image.width(), 100)
        self.assertEqual(str(self.view.wifi_save_button.cget("state")), "normal")
        self.view.wifi_ssid.set("Guest2")
        self.assertIsNone(self.view.wifi_qr_payload)
        self.assertEqual(str(self.view.wifi_save_button.cget("state")), "disabled")
        self.view.wifi_security.set(OPEN)
        self.assertEqual(self.view.wifi_password.get(), "")
        self.view.generate_wifi_qr()
        self.assertIn("T:nopass", self.view.wifi_qr_payload)

    def test_wifi_advanced_controls_and_security_notes(self):
        self.view.wifi_ssid.set("Guest")
        self.view.wifi_password.set("password123")
        self.view.wifi_security.set(WPA3)
        self.assertIn("compatibility", self.view.wifi_security_note.get().lower())
        self.view._toggle_wifi_advanced()
        self.assertEqual(self.view.wifi_advanced.winfo_manager(), "pack")
        self.view.wifi_preset.set("Custom")
        self.view.wifi_size_mode.set("Pixels")
        self.view.wifi_pixels.set("512")
        self.view.wifi_dpi.set("300")
        self.view.wifi_ecc.set("H")
        self.view.generate_wifi_qr()
        self.assertEqual(self.view.wifi_export_settings, (512, 300, "H", 4))
        self.assertEqual(self.view.wifi_qr_image.width(), 205)
        self.assertEqual(str(self.view.wifi_svg_button.cget("state")), "normal")
        self.assertEqual(str(self.view.wifi_copy_image_button.cget("state")), "normal")
        self.assertNotIn("password123", self.view.wifi_payload_display.get())
        self.view.wifi_show_payload.set(True)
        self.view._refresh_wifi_payload_display()
        self.assertIn("password123", self.view.wifi_payload_display.get())
        self.view.wifi_border.set("2")
        self.assertIsNone(self.view.wifi_qr_payload)
        self.assertEqual(str(self.view.wifi_svg_button.cget("state")), "disabled")

    def test_wifi_exports_and_image_copy_use_generated_settings(self):
        self.view.wifi_ssid.set("Guest")
        self.view.wifi_password.set("password123")
        self.view.generate_wifi_qr()
        with tempfile.TemporaryDirectory() as folder:
            png_path = Path(folder) / "guest.png"
            svg_path = Path(folder) / "guest.svg"
            with patch("tools_ui.filedialog.asksaveasfilename", return_value=str(png_path)):
                self.view._save_wifi_qr()
            self.assertEqual(struct.unpack(">II", png_path.read_bytes()[16:24]), (600, 600))
            with patch("tools_ui.filedialog.asksaveasfilename", return_value=str(svg_path)):
                self.view._save_wifi_svg()
            self.assertEqual(ElementTree.fromstring(svg_path.read_bytes()).tag,
                             "{http://www.w3.org/2000/svg}svg")
        with patch("tools_ui.copy_dib_to_clipboard") as copy_image:
            self.view._copy_wifi_image()
            dib, window = copy_image.call_args.args
            self.assertEqual(struct.unpack("<Iii", dib[:12]), (40, 600, 600))
            self.assertIsInstance(window, int)
        copied = []
        self.view._copy = copied.append
        self.view._copy_wifi_payload()
        self.assertEqual(copied, [self.view.wifi_qr_payload])

    def test_dns_record_and_mtu_pages_clear_stale_outputs(self):
        self.view.dns_owner.set("www")
        self.view.dns_value.set("192.0.2.10")
        self.view._generate_dns_record()
        self.assertEqual(self.view.dns_record.get(), "www 300 IN A 192.0.2.10")
        self.assertTrue(self.view.dns_record_valid)
        self.view.dns_value.set("192.0.2.11")
        self.assertFalse(self.view.dns_record_valid)
        self.view.dns_reverse_ip.set("192.0.2.10")
        self.view._generate_reverse_name()
        self.assertEqual(self.view.dns_reverse_name.get(), "10.2.0.192.in-addr.arpa.")
        self.assertEqual(self.view.mtu_values["tcp_mss"].get(), "1,460 bytes")
        self.view.mtu_tunnel.set("VXLAN over IPv4")
        self.assertIsNone(self.view.mtu_result)
        self.view._calculate_mtu()
        self.assertEqual(self.view.mtu_values["inner_ip_mtu"].get(), "1,450 bytes")


if __name__ == "__main__":
    unittest.main()
