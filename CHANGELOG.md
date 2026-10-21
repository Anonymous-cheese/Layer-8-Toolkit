# Changelog

## 4.6.0-preview — preview

- Removed Subnet Check from the app and migrated saved tab/startup preferences to the remaining tools.
- Expanded Wi-Fi QR with legacy WEP and WPA3/mixed compatibility labels, SVG export, image/payload copy, print presets, custom size/DPI, error correction, quiet-zone width, and optional live preview.
- Kept generation and exports offline; no Wi-Fi profiles or passwords are persisted.
- Split Layer 8 Toolkit into its own repository; it copies legacy settings once, then keeps its own preferences and logs separate from SwitchPort Resolver.
- Aligned the header across Resolver, tool groups, and Settings; improved compact-window readability and removed the redundant top-bar Tabs menu.

## 4.5.0-preview — development only

- Added an offline DHCP Option 121 classless-route builder and decoder to the DHCP Options tab.
- Accepts canonical IPv4 CIDR/gateway pairs or pasted value/on-wire hex; displays each decoded route and copy-ready hex.
- Handles RFC 3396 concatenation for values longer than one DHCP option field and flags malformed or noncanonical inputs.
- Moved MAC Formatter + OUI into Utilities for default layouts while preserving custom tab groups.

## 4.3.0-preview — development only

- Added an offline subnet overlap/duplicate checker and exact CIDR union.
- Bundled a dated IANA port registry for offline search by number, service, or common use.
- Added local Wi-Fi QR generation with explicit PNG export for personal/open networks.
- Added a Tabs jump menu for crowded windows and in-app third-party notices.

## 4.2.0-preview — development only

- Renamed the application to Layer 8 Toolkit and refreshed its icon.
- Merged Resolver and network tools into one tab strip, with Resolver first.
- Startup settings can select any tab; older Tools preferences open the IPv4 Subnet tab.
- Added a DHCP Options tab with common-option explanations, value encoding, and Cisco WLC/custom/raw Option 43 builders.
- Gave editable tool inputs a distinct customizable fill and a clearer Option 43 entry prompt.
- Added per-user tab ordering and visibility controls in Settings → Tabs; at least one tab stays visible.
- Added a local Cisco Type 7 decrypter with masked output, explicit reveal/copy, and input validation.

## 4.1.0 — 2026-10-20

- Search, IP filtering, heading sorting, visible-row export, and per-device input report.
- Confirmed Clear All with in-memory undo; explicit save/open session; persisted window and splitter layout.
- Latest-request-only lookup results and regression coverage for sample parser formats.
- Local AppData logging and sanitized diagnostic summary; keyboard shortcuts, contrast warning, and Windows dark title-bar request.
- Aligned Resolver/Tools workspace bezels and spacing, with a matching blue Tools surface.
- Team and deployment guides.

## 4.0.0-preview — development only

- Introduced Tools workspace, subnet/IP/MAC utilities, in-app Settings, and customizable palettes.
