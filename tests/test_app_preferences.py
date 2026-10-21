import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_preferences import (
    STARTUP_PAGES, THEMES, contrast_ratio, default_preferences, effective_palette, load_preferences,
    legacy_settings_path, normalize_color, save_preferences, settings_path,
)


class PreferencesTests(unittest.TestCase):
    def test_legacy_settings_are_copied_once_into_separate_toolkit_location(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"LOCALAPPDATA": folder}):
            legacy = default_preferences()
            legacy["options"]["dark_mode"] = False
            save_preferences(legacy, legacy_settings_path())

            self.assertFalse(settings_path().exists())
            self.assertFalse(load_preferences()["options"]["dark_mode"])
            self.assertTrue(settings_path().exists())

            legacy["options"]["dark_mode"] = True
            save_preferences(legacy, legacy_settings_path())
            self.assertFalse(load_preferences()["options"]["dark_mode"])
            self.assertFalse(json.loads(settings_path().read_text(encoding="utf-8"))
                             ["options"]["dark_mode"])

    def test_custom_colors_and_options_survive_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            preferences = default_preferences()
            preferences["options"]["exclude_cpu"] = False
            preferences["options"]["mac_fmt"] = "AAAA.BBBB.CCCC"
            preferences["options"]["startup_page"] = "IPv6 Planning"
            preferences["colors"]["dark"]["bg"] = "#112233"
            preferences["colors"]["dark"]["tool_input_bg"] = "#234567"
            preferences["window"].update(width=1420, height=900, x=50, y=70, split_ratio=0.63)
            save_preferences(preferences, path)
            restored = load_preferences(path)
            self.assertEqual(restored, preferences)
            self.assertEqual(effective_palette(restored, "dark")["bg"], "#112233")
            self.assertEqual(effective_palette(restored, "dark")["tool_input_bg"], "#234567")
            self.assertEqual(effective_palette(restored, "light")["bg"], THEMES["light"]["bg"])

    def test_invalid_or_unknown_saved_values_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"options": {"exclude_po": "false", "mac_fmt": "bad",
                                                    "startup_page": "Settings"},
                                        "colors": {"dark": {"bg": "red", "fg": "#AABBCC",
                                                            "unknown": "#123456"}}}), encoding="utf-8")
            restored = load_preferences(path)
            self.assertTrue(restored["options"]["exclude_po"])
            self.assertEqual(restored["options"]["mac_fmt"], "AA:BB:CC:DD:EE:FF")
            self.assertEqual(restored["options"]["startup_page"], "Resolver")
            self.assertEqual(restored["colors"]["dark"], {"fg": "#aabbcc"})

    def test_invalid_window_geometry_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"window": {"width": -1, "height": "huge", "x": 999999,
                                                   "split_ratio": 0.99}}), encoding="utf-8")
            self.assertEqual(load_preferences(path)["window"], default_preferences()["window"])

    def test_old_tools_startup_choice_moves_to_first_tool_tab(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"options": {"startup_page": "Tools"}}), encoding="utf-8")
            self.assertEqual(load_preferences(path)["options"]["startup_page"], "IPv4 Subnet")

    def test_removed_subnet_check_is_dropped_from_saved_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            preferences = default_preferences()
            preferences["options"]["startup_page"] = "Subnet Check"
            preferences["tabs"]["order"].insert(0, "Subnet Check")
            preferences["tabs"]["hidden"].append("Subnet Check")
            preferences["tabs"]["assignments"]["Subnet Check"] = "ip_math"
            save_preferences(preferences, path)
            restored = load_preferences(path)
            self.assertEqual(restored["options"]["startup_page"], "Resolver")
            self.assertNotIn("Subnet Check", restored["tabs"]["order"])
            self.assertNotIn("Subnet Check", restored["tabs"]["hidden"])
            self.assertNotIn("Subnet Check", restored["tabs"]["assignments"])

    def test_tab_layout_is_normalized_and_hidden_startup_uses_visible_tab(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({
                "options": {"startup_page": "Resolver"},
                "tabs": {"order": ["DHCP Options", "DHCP Options", "unknown", "Resolver"],
                         "hidden": ["Resolver", "unknown"]},
            }), encoding="utf-8")
            restored = load_preferences(path)
            self.assertEqual(restored["tabs"]["order"][:2], ["DHCP Options", "Resolver"])
            self.assertEqual(set(restored["tabs"]["order"]), set(STARTUP_PAGES))
            self.assertEqual(restored["tabs"]["hidden"], ["Resolver"])
            self.assertEqual(restored["options"]["startup_page"], "DHCP Options")

    def test_new_site_planner_joins_old_ip_math_layout_without_overriding_custom_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            old = default_preferences()
            old["tabs"]["order"].remove("Site Planner")
            del old["tabs"]["assignments"]["Site Planner"]
            save_preferences(old, path)
            restored = load_preferences(path)
            self.assertEqual(restored["tabs"]["assignments"]["Site Planner"], "ip_math")
            self.assertEqual(restored["tabs"]["order"][2], "Site Planner")

            restored["tabs"]["assignments"].pop("Site Planner")
            save_preferences(restored, path)
            self.assertNotIn("Site Planner", load_preferences(path)["tabs"]["assignments"])

    def test_all_tabs_cannot_be_hidden_by_saved_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"tabs": {"hidden": list(STARTUP_PAGES)}}), encoding="utf-8")
            restored = load_preferences(path)
            self.assertNotIn(STARTUP_PAGES[0], restored["tabs"]["hidden"])
            self.assertEqual(len(restored["tabs"]["hidden"]), len(STARTUP_PAGES) - 1)

    def test_tab_groups_are_persistent_and_invalid_members_are_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            preferences = default_preferences()
            preferences["tabs"]["groups"] = [
                {"id": "ip", "name": "IP Tools"},
                {"id": "lookup", "name": "References"},
            ]
            preferences["tabs"]["assignments"] = {
                "IPv4 Subnet": "ip", "Wi-Fi QR": "ip", "Port Reference": "lookup"}
            save_preferences(preferences, path)
            self.assertEqual(load_preferences(path), preferences)
            path.write_text(json.dumps({"tabs": {
                "groups": [{"id": "ip", "name": " IP   Tools "},
                           {"id": "duplicate", "name": "ip tools"},
                           {"id": "bad space", "name": "Invalid"}],
                "assignments": {"IPv4 Subnet": "ip", "Resolver": "ip",
                                "Port Reference": "missing", "Wi-Fi QR": ["ip"]},
            }}), encoding="utf-8")
            restored = load_preferences(path)
            self.assertEqual(restored["tabs"]["groups"], [{"id": "ip", "name": "IP Tools"}])
            self.assertEqual(restored["tabs"]["assignments"], {"IPv4 Subnet": "ip"})

    def test_mac_formatter_moves_to_utilities_in_default_and_old_default_layouts(self):
        self.assertEqual(default_preferences()["tabs"]["assignments"]["MAC Formatter + OUI"],
                         "utilities")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            preferences = default_preferences()
            preferences["tabs"]["assignments"]["MAC Formatter + OUI"] = "reference"
            save_preferences(preferences, path)
            self.assertEqual(load_preferences(path)["tabs"]["assignments"]["MAC Formatter + OUI"],
                             "utilities")

    def test_custom_mac_formatter_group_is_not_migrated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            preferences = default_preferences()
            preferences["tabs"]["groups"].append({"id": "my_tools", "name": "My Tools"})
            preferences["tabs"]["assignments"]["MAC Formatter + OUI"] = "my_tools"
            save_preferences(preferences, path)
            self.assertEqual(load_preferences(path), preferences)

    def test_reset_defaults_and_hex_validation(self):
        self.assertEqual(normalize_color(" #Ab12EF "), "#ab12ef")
        for value in ("red", "#123", "#12345678", "123456", "#xxxxxx"):
            with self.assertRaises(ValueError):
                normalize_color(value)
        self.assertEqual(default_preferences()["colors"], {"dark": {}, "light": {}})
        self.assertAlmostEqual(contrast_ratio("#000000", "#ffffff"), 21)
        self.assertLess(contrast_ratio("#777777", "#888888"), 4.5)


if __name__ == "__main__":
    unittest.main()
