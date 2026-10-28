"""Validated, per-user appearance and resolver preferences."""

import json
import os
import re
import tempfile
from pathlib import Path


THEMES = {
    "light": {
        "bg": "#f0f0f0", "panel_bg": "#f0f0f0", "fg": "#000000",
        "muted_fg": "#333333", "entry_bg": "#ffffff",
        "tool_input_bg": "#e8f1fa",
        "button_bg": "#f5f5f5", "button_active": "#e5e5e5",
        "button_pressed": "#d9d9d9", "border": "#b8b8b8",
        "tree_bg": "#ffffff", "tree_alt": "#f7f7f7",
        "heading_bg": "#eeeeee", "select_bg": "#0078d7",
        "select_fg": "#ffffff", "disabled_fg": "#6f6f6f",
        "insert": "#000000", "error_fg": "#b42318",
        "tooltip_bg": "#343c46", "tooltip_fg": "#ffffff",
    },
    "dark": {
        "bg": "#1f2227", "panel_bg": "#252a31", "fg": "#f1f5f9",
        "muted_fg": "#cbd5e1", "entry_bg": "#111827",
        "tool_input_bg": "#273c55",
        "button_bg": "#303741", "button_active": "#3b4450",
        "button_pressed": "#46515f", "border": "#46515f",
        "tree_bg": "#151a20", "tree_alt": "#1d232b",
        "heading_bg": "#2b323b", "select_bg": "#0f766e",
        "select_fg": "#ffffff", "disabled_fg": "#8b95a3",
        "insert": "#f8fafc", "error_fg": "#ef7777",
        "tooltip_bg": "#343c46", "tooltip_fg": "#f1f5f9",
    },
}

COLOR_LABELS = {
    "bg": "Window background", "panel_bg": "Panel / tab background",
    "fg": "Main text", "muted_fg": "Secondary text",
    "entry_bg": "Inputs / text areas", "tool_input_bg": "Tools editable inputs",
    "button_bg": "Buttons",
    "button_active": "Button hover", "button_pressed": "Button pressed",
    "border": "Borders / splitter", "tree_bg": "Result rows",
    "tree_alt": "Alternating rows", "heading_bg": "Table headings",
    "select_bg": "Accent / selection", "select_fg": "Selected text",
    "disabled_fg": "Disabled text", "insert": "Text cursor",
    "error_fg": "Error text", "tooltip_bg": "Tooltip background",
    "tooltip_fg": "Tooltip text",
}

MAC_FORMATS = ("As seen", "AA:BB:CC:DD:EE:FF", "AAAA.BBBB.CCCC")
STARTUP_PAGES = (
    "Resolver", "IPv4 Subnet", "Site Planner", "IPv6 Calculator", "IPv6 Planning",
    "Wildcard Checker", "Decimal IP", "DHCP Options", "MAC Formatter + OUI",
    "Type 7 Decrypter", "Port Reference", "DNS Records",
    "MTU Calculator", "Wi-Fi QR", "24-Hour Clock",
)
DEFAULT_GROUPS = (
    {"id": "ip_math", "name": "IP Math"},
    {"id": "reference", "name": "Reference"},
    {"id": "utilities", "name": "Utilities"},
)
DEFAULT_ASSIGNMENTS = {
    "IPv4 Subnet": "ip_math", "IPv6 Calculator": "ip_math",
    "Site Planner": "ip_math",
    "IPv6 Planning": "ip_math", "Wildcard Checker": "ip_math",
    "Decimal IP": "ip_math",
    "MTU Calculator": "ip_math",
    "DHCP Options": "reference", "Port Reference": "reference",
    "DNS Records": "reference",
    "MAC Formatter + OUI": "utilities", "Type 7 Decrypter": "utilities",
    "Wi-Fi QR": "utilities", "24-Hour Clock": "utilities",
}
LEGACY_DEFAULT_ASSIGNMENTS = {**DEFAULT_ASSIGNMENTS, "MAC Formatter + OUI": "reference"}
DEFAULT_OPTIONS = {
    "dark_mode": True, "auto_lookup_after_drop": True,
    "mac_fmt": "AA:BB:CC:DD:EE:FF", "exclude_po": True,
    "exclude_cpu": True, "only_ip": False, "startup_page": "Resolver",
}
DEFAULT_WINDOW = {"width": 1200, "height": 800, "x": None, "y": None, "split_ratio": 0.52}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def settings_path():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = Path.home() / ".config"
    return Path(base) / "Layer 8 Toolkit" / "settings.json"


def legacy_settings_path():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = Path.home() / ".config"
    return Path(base) / "SwitchPort Resolver" / "settings.json"


def default_preferences():
    return {"options": DEFAULT_OPTIONS.copy(), "colors": {"dark": {}, "light": {}},
            "window": DEFAULT_WINDOW.copy(),
            "tabs": {"order": list(STARTUP_PAGES), "hidden": [],
                     "groups": [group.copy() for group in DEFAULT_GROUPS],
                     "assignments": DEFAULT_ASSIGNMENTS.copy()}}


def normalize_group_name(value):
    """Keep user-defined tab names short, legible, and safe for preferences."""
    if not isinstance(value, str):
        raise ValueError("Enter a group name.")
    name = " ".join(value.split())
    if not name or len(name) > 28 or any(ord(char) < 32 for char in name):
        raise ValueError("Group names must be 1–28 visible characters.")
    if name.casefold() == "ungrouped" or any(
            name.casefold() == label.casefold() for label in STARTUP_PAGES):
        raise ValueError("Choose a group name different from a tool or 'Ungrouped'.")
    return name


def normalize_color(value):
    if not isinstance(value, str) or not HEX_COLOR.fullmatch(value.strip()):
        raise ValueError("Use a 6-digit hex color, such as #1F2227.")
    return value.strip().lower()


def contrast_ratio(first, second):
    """Return relative luminance contrast for two validated #RRGGBB colors."""
    def luminance(value):
        channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        channels = [channel / 12.92 if channel <= 0.04045 else
                    ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722)))
    lighter, darker = sorted((luminance(normalize_color(first)), luminance(normalize_color(second))), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def effective_palette(preferences, theme):
    return {**THEMES[theme], **preferences["colors"][theme]}


def load_preferences(path=None):
    preferences = default_preferences()
    target = Path(path) if path is not None else settings_path()
    migrate = path is None and not target.exists() and legacy_settings_path().is_file()
    source = legacy_settings_path() if migrate else target
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return preferences
        options = data.get("options", {})
        if isinstance(options, dict):
            for key, default in DEFAULT_OPTIONS.items():
                value = options.get(key)
                if isinstance(default, bool) and type(value) is bool:
                    preferences["options"][key] = value
                elif key == "mac_fmt" and value in MAC_FORMATS:
                    preferences["options"][key] = value
                elif key == "startup_page" and value in STARTUP_PAGES:
                    preferences["options"][key] = value
                elif key == "startup_page" and value == "Tools":
                    # Existing users who chose Tools now open the first tool tab.
                    preferences["options"][key] = "IPv4 Subnet"
        colors = data.get("colors", {})
        if isinstance(colors, dict):
            for theme in THEMES:
                overrides = colors.get(theme, {})
                if not isinstance(overrides, dict):
                    continue
                for key, value in overrides.items():
                    if key in THEMES[theme]:
                        try:
                            preferences["colors"][theme][key] = normalize_color(value)
                        except ValueError:
                            pass
        window = data.get("window", {})
        if isinstance(window, dict):
            for key in ("width", "height"):
                value = window.get(key)
                if type(value) is int and 600 <= value <= 10000:
                    preferences["window"][key] = value
            for key in ("x", "y"):
                value = window.get(key)
                if type(value) is int and -10000 <= value <= 10000:
                    preferences["window"][key] = value
            ratio = window.get("split_ratio")
            if type(ratio) in (int, float) and 0.15 <= ratio <= 0.85:
                preferences["window"]["split_ratio"] = float(ratio)
        tabs = data.get("tabs", {})
        if isinstance(tabs, dict):
            stored_order = tabs.get("order", [])
            if isinstance(stored_order, list):
                order = []
                for label in stored_order:
                    if isinstance(label, str) and label in STARTUP_PAGES and label not in order:
                        order.append(label)
                if "Site Planner" not in order and "IPv4 Subnet" in order:
                    order.insert(order.index("IPv4 Subnet") + 1, "Site Planner")
                if "24-Hour Clock" not in order and "Wi-Fi QR" in order:
                    order.insert(order.index("Wi-Fi QR") + 1, "24-Hour Clock")
                preferences["tabs"]["order"] = order + [label for label in STARTUP_PAGES if label not in order]
            stored_hidden = tabs.get("hidden", [])
            if isinstance(stored_hidden, list):
                hidden = [label for label in preferences["tabs"]["order"]
                          if label in stored_hidden]
                if len(hidden) == len(STARTUP_PAGES):
                    hidden.remove(preferences["tabs"]["order"][0])
                preferences["tabs"]["hidden"] = hidden
            stored_groups = tabs.get("groups")
            if isinstance(stored_groups, list):
                preferences["tabs"]["groups"] = []
                known_ids = set()
                known_names = set()
                for group in stored_groups[:32]:
                    if not isinstance(group, dict):
                        continue
                    group_id = group.get("id")
                    if not isinstance(group_id, str) or not re.fullmatch(r"[a-z0-9_-]{1,32}", group_id):
                        continue
                    try:
                        name = normalize_group_name(group.get("name"))
                    except ValueError:
                        continue
                    if group_id in known_ids or name.casefold() in known_names:
                        continue
                    preferences["tabs"]["groups"].append({"id": group_id, "name": name})
                    known_ids.add(group_id)
                    known_names.add(name.casefold())
            else:
                known_ids = {group["id"] for group in preferences["tabs"]["groups"]}
            stored_assignments = tabs.get("assignments")
            if isinstance(stored_assignments, dict):
                preferences["tabs"]["assignments"] = {
                    label: group_id for label, group_id in stored_assignments.items()
                    if isinstance(label, str) and isinstance(group_id, str)
                    and label in STARTUP_PAGES and label != "Resolver" and group_id in known_ids
                }
                # Move the old default layout forward without changing custom group choices.
                old_defaults = tuple(
                    {label: group_id for label, group_id in LEGACY_DEFAULT_ASSIGNMENTS.items()
                     if label not in omitted}
                    for omitted in ((), ("Site Planner",), ("24-Hour Clock",),
                                    ("Site Planner", "24-Hour Clock")))
                if (preferences["tabs"]["assignments"] in old_defaults
                        and {group["id"]: group["name"] for group in preferences["tabs"]["groups"]}
                        == {group["id"]: group["name"] for group in DEFAULT_GROUPS}):
                    preferences["tabs"]["assignments"]["MAC Formatter + OUI"] = "utilities"
                if ("Site Planner" not in stored_assignments
                        and (not isinstance(stored_order, list) or "Site Planner" not in stored_order)
                        and "ip_math" in known_ids):
                    preferences["tabs"]["assignments"]["Site Planner"] = "ip_math"
                if ("24-Hour Clock" not in stored_assignments
                        and (not isinstance(stored_order, list) or "24-Hour Clock" not in stored_order)
                        and "utilities" in known_ids):
                    preferences["tabs"]["assignments"]["24-Hour Clock"] = "utilities"
            elif isinstance(stored_groups, list):
                preferences["tabs"]["assignments"] = {}
        if preferences["options"]["startup_page"] in preferences["tabs"]["hidden"]:
            preferences["options"]["startup_page"] = next(
                label for label in preferences["tabs"]["order"]
                if label not in preferences["tabs"]["hidden"])
    except (OSError, ValueError, TypeError):
        pass
    if migrate:
        try:
            save_preferences(preferences, target)
        except OSError:
            pass
    return preferences


def save_preferences(preferences, path=None):
    path = Path(path or settings_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="settings-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(preferences, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
