# Layer 8 Toolkit

Version 4.6.0-preview

A portable Windows toolkit for network engineers. It combines a switchport/ARP resolver with offline subnet, DHCP, DNS, MTU, MAC, port-reference, and Wi-Fi QR utilities. The original resolver-only app remains separately available as [SwitchPort Resolver Final (3.0.2)](https://github.com/Anonymous-cheese/SwitchPort-Resolver/releases/tag/3.0.2).

---

## In this preview

- One tab strip puts Resolver first, followed by all network tools; the separate Resolver and Tools navigation buttons are gone.
- Settings can open any tab automatically when the app starts. Existing Tools startup choices open IPv4 Subnet.
- The app and preview EXE are named Layer 8 Toolkit, with a refreshed icon. On first run, existing SwitchPort Resolver settings are copied into the Toolkit's own settings location; the two apps then keep separate preferences and logs. Explicitly saved session files remain compatible.
- A DHCP Options tab explains common option numbers and generates hex values for options 1, 3, 6, 12, 15, 42, 43, 51, 66, 67, 121, and 150. Option 43 includes a Cisco WLC F1 preset, custom TLVs, and raw vendor hex. Option 121 builds classless routes from CIDR/gateway pairs and decodes value or on-wire hex back into routes.
- Editable tool fields have a distinct background and focus outline, with their fill color customizable in Settings → Colors.
- Settings → Tabs can reorder or hide unused tabs and create named groups containing multiple tools. The layout is saved per user; new group assignments appear when the app is reopened.
- A Type 7 Decrypter tab decodes Cisco Type 7 values locally. Plaintext starts masked and is copied only on request.
- Port Reference searches a bundled IANA registry snapshot by port number, service name, or purpose, including common engineering aliases; no lookup request is sent.
- DNS Records builds copy-ready A, AAAA, CNAME, MX, TXT, SRV, PTR, NS, and CAA zone-file lines, explains TTLs, and creates reverse-DNS names without querying DNS.
- MTU Calculator shows PPPoE, GRE/VXLAN, VLAN wire overhead, resulting inner IP MTU, TCP MSS, and UDP data limits with assumptions visible alongside the answer.
- Wi-Fi QR supports personal, legacy WEP, and open-network join codes; PNG/SVG export, image/payload copy, print sizing, error correction, quiet-zone settings, and optional live preview all work offline. No profiles are saved.
- Tab order, visibility, and groups are managed in Settings → Tabs; the extra top-bar Tabs menu has been removed.

---

## What's new in 4.1.0

- Resolver results can be searched across all columns, filtered by IP match, and sorted by clicking headings. CSV/Excel exports include the **visible filtered rows**.
- Input report shows parsed, excluded, matched, and unmatched counts per device, with warnings for unrecognized or unmatched data.
- Clear All asks first and has an in-memory Undo. Sessions can be explicitly saved/opened; raw device output is never auto-saved.
- Window size, position, and splitter ratio are remembered per user. The dark theme requests a matching Windows title bar where supported.
- Resolver and Tools now share aligned outer spacing and bezels; Tools uses the same darker blue work-surface color as Resolver, including custom palettes.
- Overlapping lookups cannot replace newer results. Sample parser and workflow tests guard common switch/router formats.
- Settings includes a sanitized diagnostic summary and local log-folder access; logs are stored under Local AppData rather than on the Desktop.
- Team use, data handling, and update guidance: [Team guide](docs/TEAM_GUIDE.md) and [Deployment guide](docs/DEPLOYMENT.md).

## New tools introduced in 4.1.0

- A cleaner Resolver toolbar with separate Tools and in-app Settings workspaces plus an Export menu.
- Resolver-only Lookup, Export, and Clear All actions stay out of the Tools and Settings workspaces.
- Resolver MAC formatting and filter options now live in Settings. Dark and light palettes can be customized by hex value for every color role, saved per user, or reset to defaults.
- IPv4 subnet calculator with CIDR or dotted mask input, prefix slider, classful subnet and host counts, usable range, binary details, and previous/next subnet navigation.
- IPv6 prefix calculator with expanded address, network range, address count, bit breakdown, previous/next navigation, and paged subnet planning.
- Wildcard checker for contiguous and non-contiguous masks, including an optional test IP.
- Decimal IP converter for dotted IPv4, unsigned decimal, hexadecimal, and binary representations.
- Multiline MAC formatter with a compact result list, selected-address format details, copy buttons, and offline OUI vendor lookup.

The DHCP generator follows the [IANA DHCPv4 option registry](https://www.iana.org/assignments/bootp-dhcp-parameters/), [RFC 2132](https://www.rfc-editor.org/rfc/rfc2132), [RFC 5859 for option 150](https://www.rfc-editor.org/rfc/rfc5859), and [Cisco's option 43 WLC format](https://www.cisco.com/c/en/us/support/docs/wireless-mobility/wireless-lan-wlan/97066-dhcp-option-43-00.html). Vendor-specific values must be verified against the target device documentation before deployment.

Option 121 follows [RFC 3442](https://www.rfc-editor.org/rfc/rfc3442): enter one canonical IPv4 destination/prefix and gateway per line (for example `0.0.0.0/0 192.0.2.1`), or switch the mode to decode value hex or complete on-wire Option 121 fields. Long values are split and reassembled using [RFC 3396 DHCP option concatenation](https://www.rfc-editor.org/rfc/rfc3396). Supporting clients use Option 121 routes instead of the Option 3 router value; verify the server's expected input representation and client behavior before deployment. No DHCP server is contacted.

Cisco [describes Type 7 as reversible and insecure](https://www.cisco.com/c/en/us/about/trust-center/resilient-infrastructure/protecting-secrets.html). Decoded values are sensitive credentials; the tool does not save or log them, but copying one places it on the Windows clipboard.

The port reference bundles an [IANA service-name and port-number registry](https://www.iana.org/assignments/service-names-port-numbers/) snapshot downloaded on 2026-10-20. It does not update at runtime. Common-use search aliases are our own guide, shown separately from official IANA fields. A registration is not proof that traffic on that port actually uses the named service. Source details and checksum are in [data/SOURCE.md](data/SOURCE.md).

The DNS builder follows the [IANA DNS record-type registry](https://www.iana.org/assignments/dns-parameters/), [RFC 1035 master-file format](https://www.rfc-editor.org/rfc/rfc1035), [RFC 2181 TTL limits](https://www.rfc-editor.org/rfc/rfc2181), [RFC 2782 SRV fields](https://www.rfc-editor.org/rfc/rfc2782), and [RFC 8659 CAA format](https://www.rfc-editor.org/rfc/rfc8659). Owner names are preserved as typed; use `@` for the zone apex or a final dot for an absolute owner. Domain targets are made absolute automatically. Generated text should still be reviewed for the destination DNS server's zone-file syntax.

The MTU calculator uses base/minimum header sizes: [PPPoE/PPP](https://www.rfc-editor.org/rfc/rfc2516) (8 bytes), [GRE](https://www.rfc-editor.org/rfc/rfc2784) (4-byte base header plus outer IP), and [VXLAN](https://www.rfc-editor.org/rfc/rfc7348) (outer IP, UDP, VXLAN, and inner Ethernet). [RFC 8200](https://www.rfc-editor.org/rfc/rfc8200) explains the IPv6 minimum MTU and TCP MSS calculation. It does not discover actual path MTU or account for optional headers, IPsec, tunnel extensions, or device-specific frame limits.

The Wi-Fi QR tool uses the [ZXing Wi-Fi payload format](https://github.com/zxing/zxing/wiki/Barcode-Contents). WPA2, WPA3, and mixed personal choices all use its compatibility `T:WPA` token; the code cannot enforce a particular security mode, so test on the intended device. WEP is legacy/insecure. Export presets produce 2-inch PNGs at 300 or 600 DPI; Custom supports 128–4096 pixels or 0.5–10 inches at 72–1200 DPI. SVG is scalable. Error correction (L/M/Q/H) and quiet-zone width are configurable; a 4-module border is the default. The QR image, payload, and clipboard contain the password in recoverable form. No network profiles or passwords are persisted. Source builds need the pinned packages in [requirements-build.txt](requirements-build.txt); the Windows EXE includes them and requires no separate install. Licenses are available in Settings → Notices and [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

The release EXE and source are available from the GitHub Releases page. See the [team guide](docs/TEAM_GUIDE.md) before saving sessions containing device output.

---

## Improvements in 3.0.2

- Added a draggable horizontal splitter between the device input pane and the results table.

---

## Improvements in 3.0.1

- MAC-only Excel exports now use a focused five-column table with filter/sort dropdowns when no router ARP data is loaded.

---

## Improvements in 3.0

- Added Excel `.xlsx` export with filter/sort dropdowns on every column, with VLAN values written as numbers for proper sorting.
- Added default hostname-based filenames for CSV and Excel exports while still allowing the filename to be edited.
- Added Windows drag/drop loading for saved MAC table and ARP text files.
- Added per-tab loaded-source labels and a **Clear Tab** button.
- Moved router ARP tabs before switch tabs.
- Added **Auto lookup after paste/load/drop** in Settings, including ARP-only lookup status showing loaded ARP entry counts.
- Added sample MAC and ARP test files under `samples/`.
- Added crash/debug logging to help diagnose future issues (moved to Local AppData in 4.1).

---

##  Features

###  Multi-Device Parsing  
- Parse up to **5 switch MAC tables** (`show mac address-table`)  
- Parse up to **2 router ARP tables** (`show ip arp`, with or without VRF)

###  MAC ↔ ARP Correlation  
- Automatically correlate MAC entries from switches with ARP entries from routers  
- Displays:
  - Switch name  
  - VLAN  
  - Interface  
  - MAC (user-selected formatting)  
  - Vendor (OUI)  
  - IP address  
  - Router name  
  - ARP interface  

###  Intelligent Hostname Detection  
- Automatically reads device hostnames from CLI prompts in pasted text  
- Hostname fields are pre-populated with tab defaults and replaced when a real hostname is detected
- Example supported prompts:  
  ```
  00-00-SW01
  00-00-RT01#
  RTR01(config)# do show ip arp
  100-01-SW02#
  Switch01>
  ```

###  GUI-Based Workflow  
- Clean, simple Tkinter interface  
- Starts in dark mode, with the toggle available in Settings
- Resolver is the first app tab and contains the 7 device input tabs; Settings is in the top-right corner
- Settings includes tag and app version
- Settings can choose which app tab opens at startup
- Settings → Tabs can reorder, hide, and group tools under named parent tabs; the layout persists per user
- Paste/output directly or load text files from SecureCRT, PuTTY, etc.

### Filters & Options  
- **MAC format selector:**  
  - As seen  
  - `AA:BB:CC:DD:EE:FF`  
  - `AAAA.BBBB.CCCC`  
- **Exclude Port-Channels (Po*)**  
- **Only show rows with ARP match**  
- **Exclude CPU MACs**  
- All filters are optional and non-destructive

### CSV and Excel export
- Export automatically refreshes the lookup first, so files use the current pasted data and resolver settings.
- Both formats include the rows visible under the in-app search/IP filter, in the current heading-sort order. Clear filters first to export all rows.
- Excel files contain a filterable table, including a focused five-column table for MAC-only data.

###  Offline + Online OUI Lookup  
- Offline lookup using Wireshark’s `manuf` database  
- Automatic online pull when needed  
- Caches results locally (`~/.oui_lookup/manuf`)

###  Windows EXE Packaging
- Built with PyInstaller as `dist/Layer 8 Toolkit.exe`
- Uses `icon.ico` as the app icon; the full-resolution artwork is in `assets/icon-source.png`
- Bundles `manuf` so vendor lookup works offline

---

##  How to Use

### 1. Paste or Load Device Outputs  
For each tab (`SW1`…`SW5`, `RT1-ARP`, `RT2-ARP`):

- Paste output from:
  ```
  show mac address-table
  show ip arp
  show ip arp vrf FVRF
  ```
- or click **Load File** to import saved text.

### 2. Adjust Options (Optional)  
- Choose your preferred MAC formatting  
- Enable/disable filters  
- Keep CPU MAC filtering and ARP-only filtering as needed

### 3. Click **Lookup** or **Export**
The results table populates with every MAC → IP correlation.

### 4. Export as CSV or Excel
Search/filter as needed, then use **Export** to refresh the lookup and save the visible results.

---

##  Example Workflows

### ➤ Troubleshooting a client on a 3-switch stack and dual routers
1. Paste MAC table from all switches (`SW1–SW3`)  
2. Paste ARP from both routers (`RT1`, `RT2`)  
3. Click **Lookup** → instantly see which switch/port and which router/IP  
4. Export CSV for documentation

### ➤ Identifying rogue devices  
- Use **OUI lookup** for unknown MAC prefixes  
- Filter for **only IP-matched entries**  
- CPU MACs excluded to reduce noise

---

## 🛠️ Requirements

- Python 3.10+  
- Windows 10/11 recommended  
- No external dependencies beyond standard libraries  
- Optional: PyInstaller to build `.exe`

---

## 📜 License

This project is licensed under the MIT License.
You are free to use, modify, and contribute to this project, provided the original license and copyright notice are included.
