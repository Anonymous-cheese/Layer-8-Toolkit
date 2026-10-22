# Changelog

## 1.1.1 — 2026-10-22

- Added a compact, in-page `?` guide to Site Planner with the required input format, VLAN example, and Auto-versus-growth site-block explanation.

## 1.1.0 — 2026-10-21

- Added an offline IPv4 Site Planner. Enter an aligned parent network, a reusable VLAN ID/name/prefix template, a site block prefix (or Auto), and the number of sites to generate. It shows the tightest fitting site block, maximum site count, per-site unused space, exact VLAN CIDRs, and remaining free CIDRs; plans can be copied or exported to CSV.
- The new tab joins IP Math by default, including for existing default tab layouts, without overriding deliberate custom grouping.

## 1.0.0 — 2026-10-21

First full release of Layer 8 Toolkit. It combines the switchport/ARP resolver with offline IP, DHCP, DNS, MTU, MAC, port-reference, Type 7, and Wi-Fi QR tools in one customizable Windows application.

- Resolver search, sorting, input report, explicit sessions, and CSV/Excel export, including filterable MAC-only Excel output.
- Reorderable, hideable, groupable tabs; persistent startup tab and customizable dark/light colors.
- One-file Windows EXE with bundled QR dependencies, OUI data, IANA port snapshot, and third-party notices.
