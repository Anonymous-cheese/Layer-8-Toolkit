import importlib.machinery
import importlib.util
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from app_preferences import default_preferences


ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("switchport_ui_app", str(ROOT / "oui_offline.pyw"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
APP = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(APP)


def destroy_test_root(root):
    for job in root.tk.call("after", "info"):
        root.after_cancel(job)
    root.destroy()


class ResolverUiTests(unittest.TestCase):
    def test_device_source_status_fits_at_compact_window_width(self):
        root = tk.Tk()
        try:
            with patch.object(APP, "load_preferences", return_value=default_preferences()), \
                 patch.object(APP, "save_preferences"), \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                root.geometry("800x830")
                for block in (app.router_blocks[0], app.switch_blocks[0]):
                    app.notebook.select(block["frame"])
                    root.update()
                    source = block["source_label"]
                    right_edge = source.winfo_rootx() + source.winfo_width()
                    parent_right_edge = source.master.winfo_rootx() + source.master.winfo_width()
                    self.assertGreater(source.winfo_width(), 1)
                    self.assertLessEqual(right_edge, parent_right_edge)
        finally:
            destroy_test_root(root)

    def test_header_and_tab_strip_stay_aligned_across_workspaces(self):
        root = tk.Tk()
        try:
            with patch.object(APP, "load_preferences", return_value=default_preferences()), \
                 patch.object(APP, "save_preferences"), \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                root.update()
                header = app.settings_nav.master
                expected_header_height = header.winfo_height()
                expected_tab_position = (app.main_tabs.winfo_rootx(),
                                         app.main_tabs.winfo_rooty())

                for label in ("IPv4 Subnet", "DHCP Options", "MAC Formatter + OUI",
                              "Wi-Fi QR", "Resolver"):
                    app._select_main_tab(label)
                    root.update()
                    self.assertEqual(header.winfo_height(), expected_header_height, label)
                    self.assertEqual((app.main_tabs.winfo_rootx(),
                                      app.main_tabs.winfo_rooty()),
                                     expected_tab_position, label)

                app._open_settings()
                root.update()
                self.assertEqual(header.winfo_height(), expected_header_height)
                self.assertEqual((app.settings_tabs.winfo_rootx(),
                                  app.settings_tabs.winfo_rooty()),
                                 expected_tab_position)
        finally:
            destroy_test_root(root)

    def test_custom_groups_nest_tools_and_keep_leaf_navigation(self):
        root = tk.Tk()
        try:
            preferences = default_preferences()
            preferences["tabs"]["groups"] = [{"id": "ip", "name": "IP Tools"}]
            preferences["tabs"]["assignments"] = {
                "IPv4 Subnet": "ip", "Wi-Fi QR": "ip"}
            preferences["options"]["startup_page"] = "Wi-Fi QR"
            with patch.object(APP, "load_preferences", return_value=preferences), \
                 patch.object(APP, "save_preferences") as save, \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                self.assertEqual(app.main_tabs.tab(app.main_tabs.tabs()[1], "text"),
                                 "IP Tools")
                group_tabs = app.tools_workspace.group_tabs["ip"]
                self.assertEqual([group_tabs.tab(tab, "text") for tab in group_tabs.tabs()],
                                 ["IPv4 Subnet", "Wi-Fi QR"])
                self.assertEqual(app._selected_leaf_tab(), "Wi-Fi QR")
                app._jump_to_tab("IPv4 Subnet")
                self.assertEqual(app._selected_leaf_tab(), "IPv4 Subnet")
                app.tab_tree.selection_set("Wi-Fi QR")
                app._toggle_tab_visibility()
                self.assertEqual([group_tabs.tab(tab, "text") for tab in group_tabs.tabs()],
                                 ["IPv4 Subnet"])
                app.group_choice.set("Ungrouped")
                app._assign_selected_group()
                self.assertNotIn("Wi-Fi QR", app.preferences["tabs"]["assignments"])
                self.assertEqual(save.call_args.args[0]["tabs"]["assignments"],
                                 {"IPv4 Subnet": "ip"})
        finally:
            destroy_test_root(root)

    def test_tabs_can_be_reordered_hidden_and_restored(self):
        root = tk.Tk()
        try:
            preferences = default_preferences()
            preferences["tabs"]["groups"] = []
            preferences["tabs"]["assignments"] = {}
            with patch.object(APP, "load_preferences", return_value=preferences), \
                 patch.object(APP, "save_preferences") as save, \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                self.assertFalse(hasattr(app, "tab_nav"))
                self.assertEqual(app.settings_tabs.tab(app.settings_tabs.tabs()[1], "text"),
                                 "Tabs")
                self.assertEqual(len(app.main_tabs.tabs()), len(app._visible_tab_labels()))
                app._jump_to_tab("Wi-Fi QR")
                self.assertEqual(app.main_tabs.tab(app.main_tabs.select(), "text"), "Wi-Fi QR")
                app.tab_tree.selection_set("DHCP Options")
                app._move_tab(-1)
                order = [app.main_tabs.tab(tab, "text") for tab in app.main_tabs.tabs()]
                self.assertLess(order.index("DHCP Options"), order.index("Decimal IP"))
                self.assertEqual(app.tab_tree.selection()[0], "DHCP Options")

                app.tab_tree.selection_set("Resolver")
                app._toggle_tab_visibility()
                self.assertEqual(len(app.main_tabs.tabs()), len(app._visible_tab_labels()))
                self.assertNotIn("Resolver", [app.main_tabs.tab(tab, "text")
                                               for tab in app.main_tabs.tabs()])
                self.assertEqual(app.startup_page.get(), "IPv4 Subnet")
                self.assertNotIn("Resolver", app.startup_combo.cget("values"))
                self.assertEqual(save.call_args.args[0]["tabs"]["hidden"], ["Resolver"])
                app._show_workspace("resolver")
                self.assertEqual(app.current_workspace, "tools")

                app.tab_tree.selection_set("Resolver")
                app._toggle_tab_visibility()
                self.assertIn("Resolver", [app.main_tabs.tab(tab, "text")
                                            for tab in app.main_tabs.tabs()])
                for label in list(app.preferences["tabs"]["order"])[:-1]:
                    if label not in app.preferences["tabs"]["hidden"]:
                        app.tab_tree.selection_set(label)
                        app._toggle_tab_visibility()
                remaining = app.preferences["tabs"]["order"][-1]
                app.tab_tree.selection_set(remaining)
                with patch.object(APP.messagebox, "showinfo") as info:
                    app._toggle_tab_visibility()
                info.assert_called_once()
                self.assertEqual(len(app.main_tabs.tabs()), 1)
        finally:
            destroy_test_root(root)

    def test_startup_tab_setting_opens_tool_and_resets_to_resolver(self):
        root = tk.Tk()
        try:
            preferences = default_preferences()
            preferences["options"]["startup_page"] = "IPv4 Subnet"
            with patch.object(APP, "load_preferences", return_value=preferences), \
                 patch.object(APP, "save_preferences") as save, \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                self.assertTrue(root.title().startswith("Layer 8 Toolkit"))
                self.assertEqual(app.main_tabs.tab(app.main_tabs.tabs()[0], "text"), "Resolver")
                self.assertEqual([app.main_tabs.tab(tab, "text") for tab in app.main_tabs.tabs()],
                                 ["Resolver", "IP Math", "Reference", "Utilities"])
                self.assertEqual(app.current_workspace, "tools")
                self.assertEqual(app.startup_page.get(), "IPv4 Subnet")
                app._select_main_tab("MAC Formatter + OUI")
                app._open_settings()
                app._close_settings()
                self.assertEqual(app._selected_leaf_tab(), "MAC Formatter + OUI")
                self.assertEqual(app.lookup_button.winfo_manager(), "")
                app.main_tabs.select(app.resolver_workspace)
                root.update()
                self.assertEqual(app.current_workspace, "resolver")
                self.assertEqual(app.lookup_button.winfo_manager(), "pack")
                app.startup_page.set("Resolver")
                self.assertEqual(save.call_args.args[0]["options"]["startup_page"], "Resolver")
                with patch.object(APP.messagebox, "askyesno", return_value=True):
                    app._reset_preferences()
                self.assertEqual(app.startup_page.get(), "Resolver")
        finally:
            destroy_test_root(root)

    def test_lookup_filter_report_and_undo_clear(self):
        root = tk.Tk()
        try:
            with patch.object(APP, "load_preferences", return_value=default_preferences()), \
                 patch.object(APP, "save_preferences"), \
                 patch.object(APP.WindowsFileDropManager, "register"):
                app = APP.App(root)
                app.switch_blocks[0]["txt"].insert("1.0", (ROOT / "samples" / "sample-switch-mac.txt").read_text())
                app.router_blocks[0]["txt"].insert("1.0", (ROOT / "samples" / "sample-router-arp.txt").read_text())
                app.lookup()
                deadline = time.monotonic() + 3
                while not app.last_rows and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertEqual(len(app.last_rows), 3)
                self.assertEqual(app.input_report["mac_parsed"], 4)
                app.result_query.set("Gi1/0/2")
                self.assertEqual(len(app.visible_rows), 1)
                app.result_query.set("")
                app.result_ip_filter.set("No IP")
                self.assertEqual(len(app.visible_rows), 0)
                app.result_ip_filter.set("All rows")
                with patch.object(APP.messagebox, "askyesno", return_value=True):
                    app.clear_all()
                self.assertEqual(len(app.last_rows), 0)
                app.undo_clear_all()
                self.assertEqual(len(app.last_rows), 3)
                self.assertIn("aabb.ccdd.eeff", app.switch_blocks[0]["txt"].get("1.0", "end"))
        finally:
            destroy_test_root(root)


if __name__ == "__main__":
    unittest.main()
