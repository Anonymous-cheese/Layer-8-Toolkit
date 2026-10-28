"""Network utility tabs for Layer 8 Toolkit."""

import base64
import csv
import ipaddress
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from network_tools import (
    DHCP_COMMON_OPTIONS, cisco_type7_decrypt, decimal_ip_details, dhcp_option43_cisco_wlc,
    dhcp_option43_raw_hex,
    dhcp_option43_tlv, dhcp_option_value,
    ipv4_binary, ipv4_details, ipv6_binary, ipv6_details,
    ipv6_subnet_page,
    mac_details, wildcard_details,
)
from dns_helper import RECORD_TYPES, RECORD_USES, build_dns_record, reverse_ptr_owner, ttl_display
from dhcp_option121 import decode_option121, encode_option121
from clock_tools import clock_reference_rows, convert_clock_time
from mtu_helper import TUNNEL_OVERHEAD, calculate_mtu, mtu_summary
from port_reference import REGISTRY_DATE, load_port_registry, search_ports
from site_planner import plan_sites, site_plan_rows
from wifi_qr import (MIXED, OPEN, PERSONAL, SECURITY_CHOICES, WEP, WPA3,
                     copy_dib_to_clipboard, wifi_payload, wifi_qr_dib,
                     wifi_qr_png, wifi_qr_svg)

WORKSPACE_TOP_GAP = 10


class Tooltip:
    def __init__(self, widget, message, palette_getter):
        self.widget, self.message = widget, message
        self.palette_getter = palette_getter
        self.popup = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self.job = self.widget.after(600, self._show)

    def _show(self):
        if self.popup or not self.widget.winfo_exists():
            return
        self.popup = tk.Toplevel(self.widget)
        self.popup.wm_overrideredirect(True)
        self.popup.wm_geometry(f"+{self.widget.winfo_rootx() + 16}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 6}")
        palette = self.palette_getter()
        tk.Label(self.popup, text=self.message, background=palette["tooltip_bg"], foreground=palette["tooltip_fg"],
                 padx=9, pady=5, relief="solid", borderwidth=1).pack()

    def _hide(self, _event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.popup:
            self.popup.destroy()
            self.popup = None


class NetworkToolsView(ttk.Frame):
    def __init__(self, parent, vendor_lookup, status_callback, palette_getter,
                 groups=(), assignments=None):
        super().__init__(parent)
        self.vendor_lookup = vendor_lookup
        self.status_callback = status_callback
        self.palette_getter = palette_getter
        self.palette = None
        self.ipv4_result = None
        self.ipv6_result = None
        self._change_job = None
        self.group_names = {group["id"]: group["name"] for group in groups}
        self.assignments = dict(assignments or {})
        self.group_frames = {}
        self.group_tabs = {}
        self.page_frames = {}
        self._build()

    def _build(self):
        self.tabs = ttk.Notebook(self)
        # The Resolver tab is inserted first by the main application.
        self.tabs.pack(fill="both", expand=True, pady=(WORKSPACE_TOP_GAP, 0))
        self._build_ipv4()
        self._build_site_planner()
        self._build_ipv6()
        self._build_ipv6_planner()
        self._build_wildcard()
        self._build_decimal()
        self._build_dhcp()
        self._build_mac()
        self._build_type7()
        self._build_port_reference()
        self._build_dns_records()
        self._build_mtu()
        self._build_wifi_qr()
        self._build_clock()
        self._style_surface_widgets()

    def _style_surface_widgets(self):
        """Give every Tools container/label a scoped surface style.

        Keeping this scoped means Resolver and Settings retain their own palette
        while custom user colors continue to flow through apply_theme().
        """
        label_styles = {
            "": "ToolsSurface.TLabel",
            "TLabel": "ToolsSurface.TLabel",
            "Muted.TLabel": "ToolsMuted.TLabel",
            "Value.TLabel": "ToolsValue.TLabel",
            "Mono.TLabel": "ToolsMono.TLabel",
            "Error.TLabel": "ToolsError.TLabel",
        }

        def visit(widget):
            if isinstance(widget, ttk.Notebook):
                widget.configure(style="ToolsSurface.TNotebook")
            elif isinstance(widget, ttk.LabelFrame):
                widget.configure(style="ToolsSurface.TLabelframe")
            elif isinstance(widget, ttk.Frame):
                widget.configure(style="ToolsSurface.TFrame")
            elif isinstance(widget, ttk.Checkbutton):
                widget.configure(style="ToolsSurface.TCheckbutton")
            elif isinstance(widget, ttk.Label):
                widget.configure(style=label_styles.get(widget.cget("style"), "ToolsSurface.TLabel"))
            for child in widget.winfo_children():
                visit(child)

        visit(self)

    def _page(self, title):
        group_id = self.assignments.get(title)
        if group_id in self.group_names:
            if group_id not in self.group_tabs:
                group_frame = ttk.Frame(self.tabs)
                group_tabs = ttk.Notebook(group_frame)
                group_tabs.pack(fill="both", expand=True)
                self.group_frames[group_id] = group_frame
                self.group_tabs[group_id] = group_tabs
                self.tabs.add(group_frame, text=self.group_names[group_id])
            parent = self.group_tabs[group_id]
        else:
            parent = self.tabs
        page = ttk.Frame(parent, padding=12)
        parent.add(page, text=title)
        self.page_frames[title] = page
        return page

    def _field(self, parent, label, variable, width=24):
        box = ttk.Frame(parent)
        box.pack(side="left", padx=(0, 12))
        ttk.Label(box, text=label, style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(box, textvariable=variable, width=width, style="ToolsInput.TEntry")
        entry.pack(anchor="w", ipady=4)
        return entry

    def _button(self, parent, text, command, tooltip=None, style=None):
        button = ttk.Button(parent, text=text, command=command, style=style or "TButton")
        button.pack(side="left", padx=(0, 8), pady=(18, 0))
        if tooltip:
            Tooltip(button, tooltip, self.palette_getter)
        return button

    def _section(self, parent, title):
        section = ttk.LabelFrame(parent, text=title, padding=12)
        section.pack(fill="x", pady=(0, 11))
        return section

    def _result_rows(self, section, labels):
        values = {}
        grid = ttk.Frame(section)
        grid.pack(fill="x")
        for row, label in enumerate(labels):
            ttk.Label(grid, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=4)
            variable = tk.StringVar(value="—")
            ttk.Label(grid, textvariable=variable, style="Value.TLabel").grid(
                row=row, column=1, sticky="w", pady=4)
            copy = ttk.Button(grid, text="Copy", width=6, style="Compact.TButton",
                              command=lambda v=variable: self._copy(v.get()))
            copy.grid(row=row, column=2, sticky="e", padx=(18, 0), pady=1)
            Tooltip(copy, f"Copy {label.lower()}", self.palette_getter)
            values[label] = variable
        grid.columnconfigure(1, weight=1)
        return values

    def _copy(self, text):
        if not text or text == "—":
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_callback("Copied to clipboard")

    def _error(self, variable, error):
        variable.set(str(error))
        self.status_callback(str(error))

    def _build_ipv4(self):
        page = self._page("IPv4 Subnet")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 9))
        self.ipv4_address = tk.StringVar(value="10.3.3.3")
        self.ipv4_mask = tk.StringVar(value="24")
        self._field(row, "IP ADDRESS", self.ipv4_address, 27)
        self._field(row, "PREFIX OR SUBNET MASK", self.ipv4_mask, 24)
        self._button(row, "Calculate", self.calculate_ipv4, "Calculate this IPv4 subnet", "Accent.TButton")
        self.ipv4_error = tk.StringVar()
        ttk.Label(page, textvariable=self.ipv4_error, style="Error.TLabel").pack(anchor="w")

        columns = ttk.Frame(page)
        columns.pack(fill="x")
        mask_section = ttk.LabelFrame(columns, text="MASK DETAILS", padding=12)
        mask_section.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=(0, 11))
        line = ttk.Frame(mask_section)
        line.pack(fill="x")
        ttk.Label(line, text="Prefix length", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(line, text="−", width=3, command=lambda: self._step_prefix(-1)).pack(side="left")
        self.prefix_scale = tk.Scale(line, from_=0, to=32, orient="horizontal", showvalue=False,
                                     variable=tk.IntVar(value=24), length=210, resolution=1,
                                     command=self._slide_prefix, borderwidth=0, highlightthickness=0)
        self.prefix_scale.pack(side="left", padx=8)
        ttk.Button(line, text="+", width=3, command=lambda: self._step_prefix(1)).pack(side="left")
        self.ipv4_mask_details = self._result_rows(mask_section, [
            "Address class", "Subnet mask", "Wildcard mask", "Subnet bits",
            "Maximum subnets", "Host bits", "Total addresses", "Usable hosts",
        ])

        address_section = ttk.LabelFrame(columns, text="ADDRESSES", padding=12)
        address_section.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 11))
        self.ipv4_addresses = self._result_rows(address_section, [
            "Current network", "CIDR", "First usable", "Last usable", "Broadcast", "Host range",
        ])

        detail = self._section(page, "SUBNET DETAILS")
        nav = ttk.Frame(detail)
        nav.pack(fill="x", pady=(0, 8))
        self.previous_ipv4 = ttk.Button(nav, text="← Previous subnet", command=lambda: self._move_ipv4(-1))
        self.previous_ipv4.pack(side="left")
        self.current_ipv4 = tk.StringVar(value="")
        ttk.Label(nav, textvariable=self.current_ipv4, style="Value.TLabel").pack(side="left", expand=True)
        self.next_ipv4 = ttk.Button(nav, text="Next subnet →", command=lambda: self._move_ipv4(1))
        self.next_ipv4.pack(side="right")
        ttk.Button(nav, text="Copy summary", command=self._copy_ipv4_summary).pack(side="right", padx=(0, 8))
        self.ipv4_binary = tk.StringVar()
        ttk.Label(detail, textvariable=self.ipv4_binary, style="Mono.TLabel", justify="left").pack(anchor="w")
        self.calculate_ipv4()

    def _slide_prefix(self, value):
        self.ipv4_mask.set(str(int(float(value))))
        self.calculate_ipv4()

    def _step_prefix(self, delta):
        try:
            current = int(self.ipv4_mask.get().lstrip("/"))
        except ValueError:
            current = 24
        self.ipv4_mask.set(str(max(0, min(32, current + delta))))
        self.calculate_ipv4()

    def calculate_ipv4(self):
        try:
            result = ipv4_details(self.ipv4_address.get(), self.ipv4_mask.get())
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as error:
            self.ipv4_result = None
            self._error(self.ipv4_error, error)
            return
        self.ipv4_result = result
        self.ipv4_error.set("")
        self.ipv4_mask.set(str(result["prefix"]))
        self.prefix_scale.set(result["prefix"])
        info = {
            "Address class": f"Class {result['class']}",
            "Subnet mask": str(result["mask"]), "Wildcard mask": str(result["wildcard"]),
            "Subnet bits": str(result["subnet_bits"]) if result["subnet_bits"] is not None else "N/A",
            "Maximum subnets": f"{result['max_subnets']:,}" if result["max_subnets"] is not None else "N/A",
            "Host bits": str(result["host_bits"]), "Total addresses": f"{result['total']:,}",
            "Usable hosts": f"{result['usable']:,}",
        }
        for key, value in info.items():
            self.ipv4_mask_details[key].set(value)
        info = {
            "Current network": str(result["network"].network_address),
            "CIDR": str(result["network"]), "First usable": str(result["first"]),
            "Last usable": str(result["last"]), "Broadcast": str(result["broadcast"]),
            "Host range": f"{result['first']} – {result['last']}",
        }
        for key, value in info.items():
            self.ipv4_addresses[key].set(value)
        self.current_ipv4.set(str(result["network"]))
        self.previous_ipv4.configure(state="normal" if result["previous"] else "disabled")
        self.next_ipv4.configure(state="normal" if result["next"] else "disabled")
        self.ipv4_binary.set("\n".join([
            f"Host       {ipv4_binary(result['address'])}",
            f"Mask       {ipv4_binary(result['mask'])}",
            f"Subnet     {ipv4_binary(result['network'].network_address)}",
            f"Broadcast  {ipv4_binary(result['broadcast'])}",
        ]))
        self.status_callback(f"IPv4 subnet: {result['network']}")

    def _move_ipv4(self, direction):
        if not self.ipv4_result:
            return
        address = self.ipv4_result["previous" if direction < 0 else "next"]
        if address:
            self.ipv4_address.set(str(address))
            self.calculate_ipv4()

    def _copy_ipv4_summary(self):
        if not self.ipv4_result:
            return
        rows = [f"{key}: {value.get()}" for key, value in
                {**self.ipv4_mask_details, **self.ipv4_addresses}.items()]
        self._copy("\n".join(rows))

    def _build_site_planner(self):
        page = self._page("Site Planner")
        introduction = ttk.Frame(page)
        introduction.pack(fill="x", pady=(0, 8))
        ttk.Label(introduction, text="Repeat a VLAN template inside aligned site blocks. Planning stays offline; no network is contacted.",
                  style="Muted.TLabel").pack(side="left")
        self.site_help_button = ttk.Button(introduction, text="?", width=3,
                                           style="Compact.TButton", command=self._toggle_site_help)
        self.site_help_button.pack(side="right")
        Tooltip(self.site_help_button, "How to fill out Site Planner", self.palette_getter)

        self.site_help = ttk.LabelFrame(page, text="HOW TO FILL OUT SITE PLANNER", padding=10)
        help_lines = (
            "Parent network: Enter an aligned IPv4 CIDR, such as 10.0.0.0/16 (not a host address like 10.0.0.1/16).",
            "Site block: Auto picks the smallest fit; enter /21 for growth. Sites to generate must be a positive whole number within capacity.",
            "VLAN template: One line per VLAN, separated by commas: ID, name, /prefix. Example: 10, Utility, /25. Use unique IDs from 1 to 4094.",
            "The five example rows below need 1,024 addresses per site. Auto uses /22; /21 leaves 1,024 spare addresses per site.",
        )
        for line in help_lines:
            ttk.Label(self.site_help, text=line, style="Muted.TLabel", wraplength=850,
                      justify="left").pack(anchor="w", pady=(0, 4))
        fields = ttk.Frame(page)
        fields.pack(fill="x", pady=(0, 8))
        self.site_help_fields = fields
        self.site_parent = tk.StringVar(value="10.0.0.0/16")
        self.site_block_prefix = tk.StringVar(value="Auto")
        self.site_count = tk.StringVar(value="4")
        self._field(fields, "PARENT NETWORK", self.site_parent, 22)
        self._field(fields, "SITE BLOCK (AUTO OR /PREFIX)", self.site_block_prefix, 21)
        self._field(fields, "SITES TO GENERATE", self.site_count, 16)
        self._button(fields, "Generate plan", self._generate_site_plan,
                     "Allocate every VLAN within each site block", "Accent.TButton")
        ttk.Label(page, text="VLAN TEMPLATE — one line per VLAN: ID, name, /prefix. Larger networks are placed first.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.site_template = tk.Text(page, height=5, wrap="none")
        self.site_template.pack(fill="x", pady=(0, 8))
        self.site_template.insert("1.0", "10, Utility, /25\n11, Data, /24\n12, Voice, /24\n13, Wi-Fi, /24\n14, Guest, /25")
        self.site_template.edit_modified(False)
        self.site_error = tk.StringVar()
        ttk.Label(page, textvariable=self.site_error, style="Error.TLabel").pack(anchor="w")

        summary = self._section(page, "CAPACITY")
        self.site_capacity_summary = tk.StringVar()
        self.site_space_summary = tk.StringVar()
        ttk.Label(summary, textvariable=self.site_capacity_summary, style="Value.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(summary, textvariable=self.site_space_summary, style="Muted.TLabel").pack(anchor="w")

        results = ttk.LabelFrame(page, text="SITE AND VLAN PLAN", padding=10)
        results.pack(fill="both", expand=True)
        actions = ttk.Frame(results)
        actions.pack(fill="x", pady=(0, 7))
        self.site_copy_network_button = ttk.Button(actions, text="Copy selected CIDR", command=self._copy_site_cidr)
        self.site_copy_network_button.pack(side="left", padx=(0, 8))
        self.site_copy_plan_button = ttk.Button(actions, text="Copy full plan", command=self._copy_site_plan)
        self.site_copy_plan_button.pack(side="left", padx=(0, 8))
        self.site_export_button = ttk.Button(actions, text="Export CSV", command=self._export_site_plan)
        self.site_export_button.pack(side="left")
        table = ttk.Frame(results)
        table.pack(fill="both", expand=True)
        columns = ("vlan", "name", "network", "addresses", "usable")
        self.site_tree = ttk.Treeview(table, columns=columns, show="tree headings", height=10)
        self.site_tree.heading("#0", text="Site")
        self.site_tree.column("#0", width=86, minwidth=70, stretch=False)
        for column, label, width in (("vlan", "VLAN", 60), ("name", "Name", 140),
                                     ("network", "Network", 150), ("addresses", "Addresses", 95),
                                     ("usable", "Usable / free", 105)):
            self.site_tree.heading(column, text=label)
            self.site_tree.column(column, width=width, anchor="w")
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.site_tree.yview)
        xscroll = ttk.Scrollbar(table, orient="horizontal", command=self.site_tree.xview)
        self.site_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.site_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.site_plan = None
        for variable in (self.site_parent, self.site_block_prefix, self.site_count):
            variable.trace_add("write", self._invalidate_site_plan)
        self.site_template.bind("<<Modified>>", self._site_template_changed)
        self._generate_site_plan()

    def _toggle_site_help(self):
        if self.site_help.winfo_manager():
            self.site_help.pack_forget()
        else:
            self.site_help.pack(fill="x", pady=(0, 8), before=self.site_help_fields)

    def _site_template_changed(self, _event=None):
        if self.site_template.edit_modified():
            self.site_template.edit_modified(False)
            self._invalidate_site_plan()

    def _invalidate_site_plan(self, *_args):
        self.site_plan = None
        self.site_error.set("")
        self.site_capacity_summary.set("")
        self.site_space_summary.set("")
        for item in self.site_tree.get_children():
            self.site_tree.delete(item)
        for button in (self.site_copy_network_button, self.site_copy_plan_button, self.site_export_button):
            button.configure(state="disabled")

    def _generate_site_plan(self):
        self._invalidate_site_plan()
        try:
            plan = plan_sites(self.site_parent.get(), self.site_template.get("1.0", "end"),
                              self.site_block_prefix.get(), self.site_count.get())
        except ValueError as error:
            self._error(self.site_error, error)
            return
        self.site_plan = plan
        self.site_capacity_summary.set(
            f"Minimum /{plan['minimum_site_prefix']}  •  selected /{plan['site_prefix']}  •  "
            f"{plan['max_sites']:,} sites fit in {plan['parent']}  •  {plan['generated_sites']:,} generated")
        free = plan["free_per_site"]
        equivalent = f" ({free // 256:,} × /24 equivalent)" if free and free % 256 == 0 else ""
        self.site_space_summary.set(
            f"Per site: {plan['required_per_site']:,} assigned / {plan['site_capacity']:,} total  •  "
            f"{free:,} unallocated{equivalent}")
        for site in plan["sites"]:
            parent = self.site_tree.insert("", "end", text=f"Site {site['number']}",
                                           values=("", "Site block", str(site["network"]),
                                                   f"{plan['site_capacity']:,}", f"{free:,} free"),
                                           open=site["number"] == 1)
            for vlan in site["vlans"]:
                self.site_tree.insert(parent, "end", values=(vlan["vlan"], vlan["name"],
                                    str(vlan["network"]), f"{vlan['addresses']:,}",
                                    f"{vlan['usable']:,}"))
            for network in site["free_networks"]:
                self.site_tree.insert(parent, "end", values=("", "Unallocated", str(network),
                                    f"{network.num_addresses:,}", "—"))
        for button in (self.site_copy_network_button, self.site_copy_plan_button, self.site_export_button):
            button.configure(state="normal")
        self.status_callback(f"Planned {plan['generated_sites']:,} site blocks within {plan['parent']}")

    def _copy_site_cidr(self):
        selected = self.site_tree.selection()
        if selected:
            self._copy(self.site_tree.item(selected[0], "values")[2])

    def _copy_site_plan(self):
        if self.site_plan is None:
            return
        header = ("Site", "Site CIDR", "VLAN", "Name", "Network", "Addresses", "Usable")
        lines = ["\t".join(header)]
        lines.extend("\t".join(map(str, row)) for row in site_plan_rows(self.site_plan))
        self._copy("\n".join(lines))

    def _export_site_plan(self):
        if self.site_plan is None:
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Export site plan",
                                            initialfile="site-plan.csv", defaultextension=".csv",
                                            filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("Site", "Site CIDR", "VLAN", "Name", "Network", "Addresses", "Usable"))
                writer.writerows(site_plan_rows(self.site_plan))
        except OSError as error:
            self._error(self.site_error, f"Could not export site plan: {error}")
            return
        self.status_callback("Site plan exported to CSV")

    def _build_ipv6(self):
        page = self._page("IPv6 Calculator")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 8))
        self.ipv6_address = tk.StringVar(value="2001:db8:1234::1")
        self.ipv6_prefix = tk.StringVar(value="64")
        self._field(row, "IPv6 ADDRESS", self.ipv6_address, 38)
        self._field(row, "PREFIX LENGTH", self.ipv6_prefix, 13)
        self._button(row, "Calculate", self.calculate_ipv6, "Calculate this IPv6 prefix", "Accent.TButton")
        self.ipv6_error = tk.StringVar()
        ttk.Label(page, textvariable=self.ipv6_error, style="Error.TLabel").pack(anchor="w")
        details = self._section(page, "IPv6 PREFIX DETAILS")
        self.ipv6_values = self._result_rows(details, [
            "Compressed address", "Expanded address", "Network", "Prefix mask",
            "First address", "Last address", "Host bits", "Total addresses", "Address type",
        ])
        self.ipv6_bits = tk.StringVar()
        ttk.Label(page, textvariable=self.ipv6_bits, style="Mono.TLabel", justify="left").pack(anchor="w", pady=(0, 7))
        nav = ttk.Frame(page)
        nav.pack(fill="x", pady=(4, 0))
        self.previous_ipv6 = ttk.Button(nav, text="← Previous prefix", command=lambda: self._move_ipv6(-1))
        self.previous_ipv6.pack(side="left", padx=(0, 8))
        self.next_ipv6 = ttk.Button(nav, text="Next prefix →", command=lambda: self._move_ipv6(1))
        self.next_ipv6.pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Copy summary", command=self._copy_ipv6_summary).pack(side="left")
        ttk.Button(nav, text="Plan smaller prefixes →", command=self._open_ipv6_planner).pack(side="right")
        self.calculate_ipv6()

    def calculate_ipv6(self):
        try:
            result = ipv6_details(self.ipv6_address.get(), self.ipv6_prefix.get())
        except ValueError as error:
            self.ipv6_result = None
            self._error(self.ipv6_error, error)
            return
        self.ipv6_result = result
        self.ipv6_error.set("")
        self.ipv6_prefix.set(str(result["prefix"]))
        info = {
            "Compressed address": str(result["address"]), "Expanded address": result["expanded"],
            "Network": str(result["network"]), "Prefix mask": str(result["prefix_mask"]),
            "First address": str(result["first"]), "Last address": str(result["last"]),
            "Host bits": str(result["host_bits"]), "Total addresses": f"{result['total']:,}",
            "Address type": result["type"].title(),
        }
        for key, value in info.items():
            self.ipv6_values[key].set(value)
        self.ipv6_bits.set(
            f"Address  {ipv6_binary(result['address'])}\n"
            f"Mask     {ipv6_binary(result['prefix_mask'])}"
        )
        self.previous_ipv6.configure(state="normal" if result["previous"] else "disabled")
        self.next_ipv6.configure(state="normal" if result["next"] else "disabled")
        self.status_callback(f"IPv6 prefix: {result['network']}")

    def _move_ipv6(self, direction):
        if not self.ipv6_result:
            return
        address = self.ipv6_result["previous" if direction < 0 else "next"]
        if address:
            self.ipv6_address.set(str(address))
            self.calculate_ipv6()

    def _copy_ipv6_summary(self):
        if self.ipv6_result:
            self._copy("\n".join(f"{key}: {value.get()}" for key, value in self.ipv6_values.items()))

    def _build_ipv6_planner(self):
        page = self._page("IPv6 Planning")
        self.ipv6_plan_page = page
        ttk.Label(page, text="Plan child prefixes without generating the full address space.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 6))
        self.plan_parent = tk.StringVar(value="2001:db8:1234::/64")
        self.plan_child = tk.StringVar(value="68")
        self._field(row, "PARENT NETWORK", self.plan_parent, 38)
        self._field(row, "CHILD PREFIX", self.plan_child, 14)
        self._button(row, "Plan subnets", self._reset_ipv6_plan, "List smaller networks in this IPv6 range", "Accent.TButton")
        self.plan_error = tk.StringVar()
        ttk.Label(page, textvariable=self.plan_error, style="Error.TLabel").pack(anchor="w")
        box = self._section(page, "CHILD NETWORKS")
        navigation = ttk.Frame(box)
        navigation.pack(fill="x", pady=(0, 7))
        self.plan_previous = ttk.Button(navigation, text="← Previous page", command=lambda: self._page_ipv6(-1))
        self.plan_previous.pack(side="left", padx=(0, 8))
        self.plan_next = ttk.Button(navigation, text="Next page →", command=lambda: self._page_ipv6(1))
        self.plan_next.pack(side="left")
        self.plan_status = tk.StringVar()
        ttk.Label(navigation, textvariable=self.plan_status, style="Muted.TLabel").pack(side="right")
        table_frame = ttk.Frame(box)
        table_frame.pack(fill="both", expand=True)
        self.plan_tree = ttk.Treeview(table_frame, columns=("number", "network", "range"),
                                      show="headings", height=10)
        for column, label, width in (("number", "#", 75), ("network", "Child network", 340),
                                     ("range", "Address range", 620)):
            self.plan_tree.heading(column, text=label)
            self.plan_tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.plan_tree.yview)
        self.plan_tree.configure(yscrollcommand=scroll.set)
        self.plan_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        ttk.Label(page, text="Double-click a child network to copy its CIDR.", style="Muted.TLabel").pack(anchor="w")
        self.plan_tree.bind("<Double-1>", self._copy_planned_network)
        self.plan_index = 0
        self.plan_ipv6()

    def _open_ipv6_planner(self):
        if str(self.ipv6_plan_page) not in self.tabs.tabs():
            self.status_callback("IPv6 Planning is hidden; show it in Settings → Tabs")
            return
        if self.ipv6_result:
            self.plan_parent.set(str(self.ipv6_result["network"]))
            self.plan_child.set(str(min(128, self.ipv6_result["prefix"] + 4)))
            self._reset_ipv6_plan()
        self.tabs.select(self.ipv6_plan_page)

    def _reset_ipv6_plan(self):
        self.plan_index = 0
        self.plan_ipv6()

    def plan_ipv6(self):
        try:
            network = ipaddress.IPv6Network(self.plan_parent.get().strip(), strict=False)
            plan = ipv6_subnet_page(network, self.plan_child.get(), self.plan_index)
        except ValueError as error:
            self._error(self.plan_error, error)
            return
        self.plan_error.set("")
        for item in self.plan_tree.get_children():
            self.plan_tree.delete(item)
        for number, child in plan["rows"]:
            first = child.network_address
            last = ipaddress.IPv6Address(int(first) + child.num_addresses - 1)
            self.plan_tree.insert("", "end", values=(number, str(child), f"{first} – {last}"))
        self.plan_status.set(f"{plan['count']:,} child networks  •  page {plan['page'] + 1:,} of {plan['pages']:,}")
        self.plan_previous.configure(state="normal" if plan["page"] > 0 else "disabled")
        self.plan_next.configure(state="normal" if plan["page"] + 1 < plan["pages"] else "disabled")
        self.status_callback(f"Planned {plan['count']:,} IPv6 child networks")

    def _page_ipv6(self, step):
        self.plan_index += step
        self.plan_ipv6()

    def _copy_planned_network(self, event):
        row = self.plan_tree.identify_row(event.y)
        if row:
            self._copy(str(self.plan_tree.item(row, "values")[1]))

    def _build_wildcard(self):
        page = self._page("Wildcard Checker")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 8))
        self.wildcard_address = tk.StringVar(value="10.3.3.0")
        self.wildcard_mask = tk.StringVar(value="0.0.0.255")
        self.wildcard_candidate = tk.StringVar(value="10.3.3.42")
        self._field(row, "BASE IP ADDRESS", self.wildcard_address, 20)
        self._field(row, "WILDCARD MASK", self.wildcard_mask, 20)
        self._field(row, "TEST IP (OPTIONAL)", self.wildcard_candidate, 20)
        self._button(row, "Check", self.calculate_wildcard, "Check Cisco wildcard matching", "Accent.TButton")
        self.wildcard_error = tk.StringVar()
        ttk.Label(page, textvariable=self.wildcard_error, style="Error.TLabel").pack(anchor="w")
        details = self._section(page, "WILDCARD DETAILS")
        self.wildcard_values = self._result_rows(details, [
            "Match pattern", "Lowest matching IP", "Highest matching IP", "Matching addresses",
            "Inverse mask", "Equivalent CIDR", "Test IP result", "Wildcard binary",
        ])
        ttk.Label(page, text="Non-contiguous wildcards are supported; lowest and highest IPs do not imply every address between them matches.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Button(page, text="Copy summary", command=lambda: self._copy(
            "\n".join(f"{key}: {value.get()}" for key, value in self.wildcard_values.items()))).pack(anchor="w")
        self.calculate_wildcard()

    def calculate_wildcard(self):
        try:
            result = wildcard_details(self.wildcard_address.get(), self.wildcard_mask.get(),
                                      self.wildcard_candidate.get())
        except ValueError as error:
            self._error(self.wildcard_error, error)
            return
        self.wildcard_error.set("")
        info = {
            "Match pattern": f"{result['base']}  {result['wildcard']}",
            "Lowest matching IP": str(result["base"]),
            "Highest matching IP": str(result["upper"]),
            "Matching addresses": f"{result['count']:,}",
            "Inverse mask": str(result["mask"]),
            "Equivalent CIDR": f"{result['base']}/{result['prefix']}" if result["prefix"] is not None else "Not a contiguous subnet",
            "Test IP result": "Matches" if result["matched"] is True else
            "Does not match" if result["matched"] is False else "No test IP entered",
            "Wildcard binary": ipv4_binary(result["wildcard"]),
        }
        for key, value in info.items():
            self.wildcard_values[key].set(value)
        self.status_callback("Wildcard check complete")

    def _build_decimal(self):
        page = self._page("Decimal IP")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 8))
        self.decimal_input = tk.StringVar(value="10.3.3.3")
        self._field(row, "DOTTED IP, UNSIGNED INTEGER, OR 0x HEX", self.decimal_input, 42)
        self._button(row, "Convert", self.calculate_decimal, "Convert an IPv4 address to other representations", "Accent.TButton")
        self.decimal_error = tk.StringVar()
        ttk.Label(page, textvariable=self.decimal_error, style="Error.TLabel").pack(anchor="w")
        details = self._section(page, "IPv4 ADDRESS FORMATS")
        self.decimal_values = self._result_rows(details, ["Dotted decimal", "Unsigned decimal", "Hexadecimal", "Binary"])
        self.calculate_decimal()

    def calculate_decimal(self):
        try:
            result = decimal_ip_details(self.decimal_input.get())
        except (ValueError, OverflowError) as error:
            self._error(self.decimal_error, error)
            return
        self.decimal_error.set("")
        for key, value in {
            "Dotted decimal": result["address"], "Unsigned decimal": result["integer"],
            "Hexadecimal": result["hex"], "Binary": result["binary"],
        }.items():
            self.decimal_values[key].set(str(value))
        self.status_callback("IPv4 conversion complete")

    def _build_dhcp(self):
        page = self._page("DHCP Options")
        ttk.Label(page, text="Common DHCPv4 options and copy-ready values.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 8))
        choices = [f"{code} — {name}" for code, (name, _use, _kind)
                   in DHCP_COMMON_OPTIONS.items()]
        self.dhcp_choice = tk.StringVar(value=next(item for item in choices if item.startswith("43 —")))
        selector = ttk.Frame(page)
        selector.pack(fill="x", pady=(0, 8))
        ttk.Label(selector, text="Option:", style="ToolsMuted.TLabel").pack(side="left", padx=(0, 8))
        combo = ttk.Combobox(selector, textvariable=self.dhcp_choice, values=choices,
                             state="readonly", width=33)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self._switch_dhcp_option)
        self.dhcp_use = tk.StringVar()
        ttk.Label(page, textvariable=self.dhcp_use, style="ToolsMuted.TLabel",
                  wraplength=900).pack(anchor="w", pady=(0, 10))

        self.dhcp_simple_frame = ttk.LabelFrame(page, text="VALUE", padding=12)
        self.dhcp_hint = tk.StringVar()
        ttk.Label(self.dhcp_simple_frame, textvariable=self.dhcp_hint,
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.dhcp_input = tk.Text(self.dhcp_simple_frame, height=3, wrap="word")
        self.dhcp_input.pack(fill="x")

        self.dhcp_43_frame = ttk.LabelFrame(page, text="OPTION 43 — VENDOR-SPECIFIC VALUE", padding=12)
        mode_row = ttk.Frame(self.dhcp_43_frame)
        mode_row.pack(fill="x", pady=(0, 8))
        ttk.Label(mode_row, text="Format:", style="ToolsMuted.TLabel").pack(side="left", padx=(0, 8))
        self.dhcp_43_mode = tk.StringVar(value="Cisco WLC (F1)")
        mode = ttk.Combobox(mode_row, textvariable=self.dhcp_43_mode,
                            values=("Cisco WLC (F1)", "Custom TLV", "Raw hex"),
                            state="readonly", width=20)
        mode.pack(side="left")
        mode.bind("<<ComboboxSelected>>", self._switch_dhcp_43_mode)
        self.dhcp_wlc_frame = ttk.Frame(self.dhcp_43_frame)
        ttk.Label(self.dhcp_wlc_frame, text="Type or paste controller IPv4 addresses below (one per line or comma-separated):",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.dhcp_wlc_input = tk.Text(self.dhcp_wlc_frame, height=4, wrap="word")
        self.dhcp_wlc_input.pack(fill="x")
        ttk.Label(self.dhcp_wlc_frame, text="Example: 192.168.10.5, 192.168.10.20",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(5, 0))
        self.dhcp_custom_frame = ttk.Frame(self.dhcp_43_frame)
        ttk.Label(self.dhcp_custom_frame,
                  text="One suboption per line: CODE=hex:BYTES, CODE=ascii:TEXT, or CODE=ipv4:ADDRESSES",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(self.dhcp_custom_frame, text="Example: 0xF1=ipv4:192.168.10.5,192.168.10.20",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.dhcp_custom_input = tk.Text(self.dhcp_custom_frame, height=5, wrap="word")
        self.dhcp_custom_input.pack(fill="x")
        self.dhcp_raw_frame = ttk.Frame(self.dhcp_43_frame)
        ttk.Label(self.dhcp_raw_frame, text="Vendor-documented hex bytes, without an added suboption header:",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.dhcp_raw_input = tk.Text(self.dhcp_raw_frame, height=4, wrap="word")
        self.dhcp_raw_input.pack(fill="x")
        self._switch_dhcp_43_mode()

        self.dhcp_121_frame = ttk.LabelFrame(page, text="OPTION 121 — CLASSLESS STATIC ROUTES", padding=12)
        route_mode_row = ttk.Frame(self.dhcp_121_frame)
        route_mode_row.pack(fill="x", pady=(0, 7))
        ttk.Label(route_mode_row, text="Mode:", style="ToolsMuted.TLabel").pack(side="left", padx=(0, 8))
        self.dhcp_121_mode = tk.StringVar(value="Build routes")
        route_mode = ttk.Combobox(route_mode_row, textvariable=self.dhcp_121_mode,
                                  values=("Build routes", "Decode value hex", "Decode on-wire hex"),
                                  state="readonly", width=22)
        route_mode.pack(side="left")
        route_mode.bind("<<ComboboxSelected>>", self._switch_dhcp_121_mode)
        self.dhcp_121_build_frame = ttk.Frame(self.dhcp_121_frame)
        ttk.Label(self.dhcp_121_build_frame,
                  text="One route per line: DESTINATION/PREFIX GATEWAY (or DESTINATION/PREFIX via GATEWAY).",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 5))
        self.dhcp_121_build_input = tk.Text(self.dhcp_121_build_frame, height=3, wrap="word")
        self.dhcp_121_build_input.pack(fill="x")
        ttk.Label(self.dhcp_121_build_frame,
                  text="Example: 0.0.0.0/0 192.0.2.1     198.51.100.0/24 192.0.2.2 (on separate lines)",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(5, 0))
        self.dhcp_121_decode_frame = ttk.Frame(self.dhcp_121_frame)
        self.dhcp_121_decode_hint = tk.StringVar()
        ttk.Label(self.dhcp_121_decode_frame, textvariable=self.dhcp_121_decode_hint,
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 5))
        self.dhcp_121_decode_input = tk.Text(self.dhcp_121_decode_frame, height=3, wrap="word")
        self.dhcp_121_decode_input.pack(fill="x")
        self._switch_dhcp_121_mode()

        self.dhcp_actions = ttk.Frame(page)
        self.dhcp_actions.pack(fill="x", pady=(8, 4))
        self.dhcp_generate_button = ttk.Button(self.dhcp_actions, text="Generate", style="Accent.TButton",
                                                command=self.generate_dhcp)
        self.dhcp_generate_button.pack(side="left", padx=(0, 8))
        self.dhcp_error = tk.StringVar()
        ttk.Label(page, textvariable=self.dhcp_error, style="ToolsError.TLabel",
                  wraplength=900).pack(anchor="w", pady=(0, 5))

        output = ttk.LabelFrame(page, text="ENCODED OPTION", padding=12)
        output.pack(fill="x", pady=(4, 8))
        self.dhcp_output = output
        self.dhcp_hex = tk.StringVar()
        self.dhcp_wire = tk.StringVar()
        self.dhcp_ios = tk.StringVar()
        self.dhcp_length = tk.StringVar(value="No value generated")
        for label, variable in (("Value hex (for DHCP server configuration)", self.dhcp_hex),
                                ("On-wire hex (option + length + value)", self.dhcp_wire)):
            row = ttk.Frame(output)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="ToolsMuted.TLabel", width=39).pack(side="left")
            ttk.Entry(row, textvariable=variable, state="readonly").pack(side="left", fill="x", expand=True, padx=(4, 8))
            ttk.Button(row, text="Copy", width=6, style="Compact.TButton",
                       command=lambda value=variable: self._copy(value.get())).pack(side="right")
        self.dhcp_ios_row = ttk.Frame(output)
        self.dhcp_ios_row.pack(fill="x", pady=3)
        ttk.Label(self.dhcp_ios_row, text="Cisco IOS DHCP command (Option 43)",
                  style="ToolsMuted.TLabel", width=39).pack(side="left")
        ttk.Entry(self.dhcp_ios_row, textvariable=self.dhcp_ios, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(4, 8))
        ttk.Button(self.dhcp_ios_row, text="Copy", width=6, style="Compact.TButton",
                   command=lambda: self._copy(self.dhcp_ios.get())).pack(side="right")
        self.dhcp_length_label = ttk.Label(output, textvariable=self.dhcp_length,
                                            style="ToolsMuted.TLabel")
        self.dhcp_length_label.pack(anchor="w", pady=(6, 0))
        self.dhcp_breakdown = ttk.Treeview(output, columns=("code", "length", "value"),
                                            show="headings", height=4)
        for column, label, width in (("code", "Suboption", 100),
                                     ("length", "Bytes", 70), ("value", "Value hex", 600)):
            self.dhcp_breakdown.heading(column, text=label)
            self.dhcp_breakdown.column(column, width=width, anchor="w")
        self.dhcp_breakdown.pack(fill="x", pady=(8, 0))
        ttk.Label(page, text="Verify the target device/vendor format. Server UIs may expect decoded values rather than hex.",
                  style="ToolsMuted.TLabel", wraplength=900).pack(anchor="w")
        self._switch_dhcp_option()

    def _selected_dhcp_code(self):
        return int(self.dhcp_choice.get().split(" ", 1)[0])

    def _switch_dhcp_option(self, _event=None):
        code = self._selected_dhcp_code()
        _name, use, kind = DHCP_COMMON_OPTIONS[code]
        self.dhcp_use.set(f"Common use: {use}")
        self.dhcp_simple_frame.pack_forget()
        self.dhcp_43_frame.pack_forget()
        self.dhcp_121_frame.pack_forget()
        self.dhcp_output.configure(text="ENCODED OPTION")
        self.dhcp_generate_button.configure(text="Generate")
        if kind == "option43":
            self.dhcp_43_frame.pack(fill="x", pady=(0, 4), before=self.dhcp_actions)
            self.dhcp_ios_row.pack(fill="x", pady=3, before=self.dhcp_length_label)
            self.dhcp_breakdown.pack(fill="x", pady=(8, 0))
            self._configure_dhcp_breakdown(routes=False)
        elif kind == "option121":
            self.dhcp_121_frame.pack(fill="x", pady=(0, 4), before=self.dhcp_actions)
            self.dhcp_output.configure(text="OPTION 121 VALUE AND ROUTES")
            self.dhcp_generate_button.configure(
                text="Build routes" if self.dhcp_121_mode.get() == "Build routes" else "Decode hex")
            self.dhcp_ios_row.pack_forget()
            self.dhcp_breakdown.pack(fill="x", pady=(8, 0))
            self._configure_dhcp_breakdown(routes=True)
        else:
            hints = {
                "mask": "Enter a dotted subnet mask or prefix length, such as 255.255.255.0 or 24.",
                "ipv4_list": "Enter one or more IPv4 addresses, separated by commas or lines.",
                "ascii": "Enter printable ASCII text.",
                "seconds": "Enter the lease time as a whole number of seconds.",
            }
            self.dhcp_hint.set(hints[kind])
            self.dhcp_simple_frame.pack(fill="x", pady=(0, 4), before=self.dhcp_actions)
            self.dhcp_ios_row.pack_forget()
            self.dhcp_breakdown.pack_forget()
        self._clear_dhcp_output()

    def _configure_dhcp_breakdown(self, *, routes):
        labels = (("Destination", "Prefix", "Gateway") if routes
                  else ("Suboption", "Bytes", "Value hex"))
        widths = ((225, 85, 225) if routes else (100, 70, 600))
        for column, label, width in zip(("code", "length", "value"), labels, widths):
            self.dhcp_breakdown.heading(column, text=label)
            self.dhcp_breakdown.column(column, width=width)

    def _switch_dhcp_121_mode(self, _event=None):
        self.dhcp_121_build_frame.pack_forget()
        self.dhcp_121_decode_frame.pack_forget()
        if self.dhcp_121_mode.get() == "Build routes":
            self.dhcp_121_build_frame.pack(fill="x")
        else:
            self.dhcp_121_decode_hint.set(
                "Paste one or more complete Option 121 fields (0x79 + length + value)."
                if self.dhcp_121_mode.get() == "Decode on-wire hex"
                else "Paste Option 121 value hex only, without the option code or length byte.")
            self.dhcp_121_decode_frame.pack(fill="x")
        if hasattr(self, "dhcp_hex"):
            self.dhcp_generate_button.configure(
                text="Build routes" if self.dhcp_121_mode.get() == "Build routes" else "Decode hex")
            self._clear_dhcp_output()

    def _switch_dhcp_43_mode(self, _event=None):
        self.dhcp_wlc_frame.pack_forget()
        self.dhcp_custom_frame.pack_forget()
        self.dhcp_raw_frame.pack_forget()
        target = {"Cisco WLC (F1)": self.dhcp_wlc_frame,
                  "Custom TLV": self.dhcp_custom_frame,
                  "Raw hex": self.dhcp_raw_frame}[self.dhcp_43_mode.get()]
        target.pack(fill="x")
        if hasattr(self, "dhcp_hex"):
            self._clear_dhcp_output()

    def _clear_dhcp_output(self):
        self.dhcp_hex.set("")
        self.dhcp_wire.set("")
        self.dhcp_ios.set("")
        self.dhcp_length.set("No value generated")
        self.dhcp_error.set("")
        for item in self.dhcp_breakdown.get_children():
            self.dhcp_breakdown.delete(item)

    def generate_dhcp(self):
        self._clear_dhcp_output()
        code = self._selected_dhcp_code()
        try:
            if code == 43:
                if self.dhcp_43_mode.get() == "Cisco WLC (F1)":
                    result = dhcp_option43_cisco_wlc(self.dhcp_wlc_input.get("1.0", "end"))
                elif self.dhcp_43_mode.get() == "Custom TLV":
                    result = dhcp_option43_tlv(self.dhcp_custom_input.get("1.0", "end"))
                else:
                    result = dhcp_option43_raw_hex(self.dhcp_raw_input.get("1.0", "end"))
            elif code == 121:
                if self.dhcp_121_mode.get() == "Build routes":
                    result = encode_option121(self.dhcp_121_build_input.get("1.0", "end"))
                else:
                    result = decode_option121(
                        self.dhcp_121_decode_input.get("1.0", "end"),
                        on_wire=self.dhcp_121_mode.get() == "Decode on-wire hex")
            else:
                result = dhcp_option_value(code, self.dhcp_input.get("1.0", "end"))
        except ValueError as error:
            self.dhcp_error.set(str(error))
            self.status_callback("DHCP option input needs correction")
            return
        self.dhcp_hex.set(result["hex"])
        self.dhcp_wire.set(result["wire_hex"])
        self.dhcp_ios.set(result.get("ios", ""))
        if code == 121:
            self.dhcp_length.set(
                f"Option 121: {len(result['routes'])} route(s), {result['length']} value byte(s), "
                f"{result['segments']} on-wire field(s)."
                + (" Warning: " + " ".join(result["warnings"]) if result["warnings"] else ""))
            for route in result["routes"]:
                self.dhcp_breakdown.insert("", "end", values=(route["destination"],
                                                               f"/{route['prefix']}", route["gateway"]))
        else:
            self.dhcp_length.set(f"Option {code}: {result['length']} value byte(s). Hex output excludes DHCP packet headers.")
            for item in result["suboptions"]:
                self.dhcp_breakdown.insert("", "end", values=(f"0x{item['code']:02X}",
                                                               item["length"], item["hex"]))
        self.status_callback(f"DHCP option {code} {'decoded' if code == 121 and self.dhcp_121_mode.get() != 'Build routes' else 'generated'}")

    def _build_mac(self):
        page = self._page("MAC Formatter + OUI")
        ttk.Label(page, text="Paste one or more MAC addresses (one per line).", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.mac_input = tk.Text(page, height=5, wrap="none")
        self.mac_input.pack(fill="x")
        self.mac_input.insert("1.0", "aabb.ccdd.eeff")
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(8, 8))
        ttk.Button(actions, text="Format + look up", command=self.calculate_macs, style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Copy all results", command=self._copy_mac_results).pack(side="left")
        self.mac_error = tk.StringVar()
        ttk.Label(page, textvariable=self.mac_error, style="Error.TLabel").pack(anchor="w")
        self.mac_records = {}
        columns = ("input", "vendor", "oui", "assignment")
        table_frame = ttk.Frame(page)
        table_frame.pack(fill="both", expand=True, pady=(5, 10))
        self.mac_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=7)
        labels = ("Input", "Vendor", "OUI", "Assignment")
        widths = (180, 430, 140, 200)
        minimums = (120, 180, 100, 130)
        for col, label, width, minimum in zip(columns, labels, widths, minimums):
            self.mac_tree.heading(col, text=label)
            self.mac_tree.column(col, width=width, minwidth=minimum, anchor="w", stretch=True)
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.mac_tree.yview)
        self.mac_tree.configure(yscrollcommand=vertical.set)
        self.mac_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        details = ttk.LabelFrame(page, text="Selected MAC — click Copy beside any value", padding=10)
        details.pack(fill="x")
        self.mac_detail_values = {}
        detail_fields = (
            ("cisco", "Cisco"), ("colon", "Colon"),
            ("colon_lower", "Lowercase"), ("hyphen", "Hyphen"),
            ("plain", "Plain"), ("oui", "OUI"),
            ("vendor", "Vendor"), ("assignment", "Assignment"),
            ("delivery", "Delivery"),
        )
        for index, (key, label) in enumerate(detail_fields):
            column, row_index = (0, index) if index < 5 else (1, index - 5)
            row = ttk.Frame(details)
            row.grid(row=row_index, column=column, sticky="ew", padx=(0, 18), pady=3)
            ttk.Label(row, text=label, width=13, style="Muted.TLabel").pack(side="left")
            value = tk.StringVar(value="—")
            self.mac_detail_values[key] = value
            ttk.Button(row, text="Copy", width=6, style="Compact.TButton",
                       command=lambda v=value: self._copy(v.get()) if v.get() != "—" else None).pack(side="right")
            ttk.Label(row, textvariable=value, style="Value.TLabel", wraplength=310).pack(
                side="left", fill="x", expand=True)
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)
        ttk.Label(page, text="Select a row to see all formats. Double-click a table cell to copy it.",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.mac_tree.bind("<Double-1>", self._copy_mac_cell)
        self.mac_tree.bind("<<TreeviewSelect>>", self._show_mac_details)
        self.calculate_macs()

    def calculate_macs(self):
        for item in self.mac_tree.get_children():
            self.mac_tree.delete(item)
        self.mac_records.clear()
        self.mac_error.set("")
        lines = [line.strip() for line in self.mac_input.get("1.0", "end").splitlines() if line.strip()]
        errors = []
        for line in lines:
            try:
                result = mac_details(line, self.vendor_lookup)
            except ValueError:
                errors.append(line)
                continue
            item = self.mac_tree.insert("", "end", values=(
                result["input"], result["vendor"], result["oui"], result["assignment"],
            ))
            self.mac_records[item] = result
        if errors:
            self.mac_error.set(f"Skipped {len(errors)} invalid MAC address(es): {', '.join(errors[:2])}")
        items = self.mac_tree.get_children()
        if items:
            self.mac_tree.selection_set(items[0])
            self.mac_tree.focus(items[0])
        self._show_mac_details()
        self.status_callback(f"Formatted {len(self.mac_tree.get_children())} MAC address(es)")

    def _show_mac_details(self, _event=None):
        selection = self.mac_tree.selection()
        result = self.mac_records.get(selection[0]) if selection else None
        for key, value in self.mac_detail_values.items():
            value.set(str(result[key]) if result else "—")

    def _copy_mac_cell(self, event):
        row = self.mac_tree.identify_row(event.y)
        column = self.mac_tree.identify_column(event.x)
        if row and column:
            index = int(column[1:]) - 1
            self._copy(str(self.mac_tree.item(row, "values")[index]))

    def _copy_mac_results(self):
        fields = ("input", "cisco", "colon", "colon_lower", "hyphen", "plain",
                  "oui", "vendor", "assignment", "delivery")
        labels = ("Input", "Cisco", "Colon", "Lowercase", "Hyphen", "Plain",
                  "OUI", "Vendor", "Assignment", "Delivery")
        rows = ["\t".join(labels)]
        rows.extend("\t".join(str(self.mac_records[item][field]) for field in fields)
                    for item in self.mac_tree.get_children())
        if len(rows) > 1:
            self._copy("\n".join(rows))

    def _build_type7(self):
        page = self._page("Type 7 Decrypter")
        ttk.Label(page, text="Decode a Cisco Type 7 password from a hex value or configuration line.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 12))
        source = self._section(page, "TYPE 7 VALUE")
        ttk.Label(source, text="Paste a value such as 02050D480809, or a line ending in password 7 <value>.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.type7_input = tk.StringVar()
        self.type7_input_entry = ttk.Entry(source, textvariable=self.type7_input,
                                           style="ToolsInput.TEntry")
        self.type7_input_entry.pack(fill="x", ipady=5)
        self.type7_input_entry.bind("<Return>", self._decrypt_type7)

        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(actions, text="Decrypt", style="Accent.TButton",
                   command=self._decrypt_type7).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Clear", command=self._clear_type7).pack(side="left")
        self.type7_error = tk.StringVar()
        ttk.Label(page, textvariable=self.type7_error, style="ToolsError.TLabel").pack(
            anchor="w", pady=(0, 8))

        result = self._section(page, "PLAINTEXT")
        self.type7_output = tk.StringVar()
        self.type7_output_entry = ttk.Entry(result, textvariable=self.type7_output,
                                            state="readonly", show="•")
        self.type7_output_entry.pack(fill="x", ipady=5, pady=(0, 8))
        result_actions = ttk.Frame(result)
        result_actions.pack(fill="x")
        self.type7_visible = tk.BooleanVar(value=False)
        ttk.Checkbutton(result_actions, text="Show plaintext", variable=self.type7_visible,
                        command=self._toggle_type7_reveal).pack(side="left", padx=(0, 12))
        ttk.Button(result_actions, text="Copy plaintext",
                   command=lambda: self._copy(self.type7_output.get())).pack(side="left")
        ttk.Label(page, text="Type 7 is reversible obfuscation. Treat the result as a real password. "
                  "Values stay local and are not saved; copying places plaintext on the clipboard.",
                  style="ToolsMuted.TLabel", wraplength=850).pack(anchor="w")
        self.type7_input.trace_add("write", self._clear_type7_result)

    def _clear_type7_result(self, *_args):
        self.type7_output.set("")
        self.type7_error.set("")
        self.type7_visible.set(False)
        self._toggle_type7_reveal()

    def _clear_type7(self):
        self.type7_input.set("")
        self._clear_type7_result()
        self.status_callback("Type 7 fields cleared")

    def _toggle_type7_reveal(self):
        self.type7_output_entry.configure(show="" if self.type7_visible.get() else "•")

    def _decrypt_type7(self, _event=None):
        self._clear_type7_result()
        try:
            self.type7_output.set(cisco_type7_decrypt(self.type7_input.get()))
        except ValueError as error:
            self.type7_error.set(str(error))
            self.status_callback("Type 7 input needs correction")
            return
        self.status_callback("Type 7 value decoded locally")

    def _build_clock(self):
        page = self._page("24-Hour Clock")
        ttk.Label(page, text="Convert between 12-hour and 24-hour notation. This does not change the date or time zone.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 9))

        controls = ttk.Frame(page)
        controls.pack(fill="x", pady=(0, 4))
        self.clock_input = tk.StringVar(value="2:30 PM")
        entry = self._field(controls, "TIME", self.clock_input, 28)
        entry.bind("<Return>", self._convert_clock)
        self._button(controls, "Convert", self._convert_clock,
                     "Convert 12-hour and 24-hour clock notation", "Accent.TButton")
        ttk.Label(page, text="Try 2:30 PM, 14:30, or 1430. Without AM/PM, input is treated as 24-hour time.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.clock_error = tk.StringVar()
        ttk.Label(page, textvariable=self.clock_error, style="Error.TLabel").pack(anchor="w")

        result = self._section(page, "CONVERSION")
        self.clock_values = self._result_rows(result, ("24-hour", "12-hour"))

        reference = self._section(page, "24-HOUR REFERENCE")
        ttk.Label(reference, text="Whole hours at a glance; enter any minutes above for an exact conversion.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 7))
        columns = ("morning_24", "morning_12", "afternoon_24", "afternoon_12")
        self.clock_tree = ttk.Treeview(reference, columns=columns, show="headings",
                                       height=12, selectmode="none")
        for column, label in zip(columns, ("24-hour", "12-hour", "24-hour", "12-hour")):
            self.clock_tree.heading(column, text=label)
            self.clock_tree.column(column, width=120, minwidth=80, anchor="center")
        for row in clock_reference_rows():
            self.clock_tree.insert("", "end", values=row)
        self.clock_tree.pack(fill="x")
        self.clock_input.trace_add("write", self._clear_clock_result)
        self._convert_clock()

    def _clear_clock_result(self, *_args):
        for variable in self.clock_values.values():
            variable.set("—")
        self.clock_error.set("")

    def _convert_clock(self, _event=None):
        self._clear_clock_result()
        try:
            twenty_four, twelve = convert_clock_time(self.clock_input.get())
        except ValueError as error:
            self._error(self.clock_error, error)
            return
        self.clock_values["24-hour"].set(twenty_four)
        self.clock_values["12-hour"].set(twelve)
        self.status_callback("Clock time converted locally")

    def _build_port_reference(self):
        page = self._page("Port Reference")
        ttk.Label(page, text=f"Offline IANA service/port registry snapshot: {REGISTRY_DATE}. Search by number, name, or use.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 8))
        controls = ttk.Frame(page)
        controls.pack(fill="x", pady=(0, 8))
        self.port_query = tk.StringVar()
        self.port_query_entry = ttk.Entry(controls, textvariable=self.port_query,
                                          style="ToolsInput.TEntry", width=44)
        self.port_query_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 9))
        self.port_protocol = tk.StringVar(value="All")
        ttk.Combobox(controls, textvariable=self.port_protocol,
                     values=("All", "tcp", "udp", "sctp", "dccp"), state="readonly",
                     width=9).pack(side="left")
        ttk.Button(controls, text="Clear", command=lambda: self.port_query.set("")).pack(
            side="left", padx=(9, 0))
        self.port_status = tk.StringVar()
        ttk.Label(page, textvariable=self.port_status, style="ToolsMuted.TLabel").pack(
            anchor="w", pady=(0, 7))
        table = ttk.Frame(page)
        table.pack(fill="both", expand=True)
        self.port_tree = ttk.Treeview(table, columns=("port", "protocol", "service", "use", "description"),
                                       show="headings", height=17)
        for key, label, width in (("port", "Port", 95), ("protocol", "Transport", 85),
                                  ("service", "IANA service", 165), ("use", "Common use", 260),
                                  ("description", "IANA description", 430)):
            self.port_tree.heading(key, text=label)
            self.port_tree.column(key, width=width, anchor="w")
        self.port_tree.pack(side="left", fill="both", expand=True)
        port_scroll = ttk.Scrollbar(table, orient="vertical", command=self.port_tree.yview)
        port_scroll.pack(side="right", fill="y")
        self.port_tree.configure(yscrollcommand=port_scroll.set)
        self.port_detail = tk.StringVar(value="Select a result to see its full description.")
        ttk.Label(page, textvariable=self.port_detail, style="ToolsMuted.TLabel",
                  wraplength=960).pack(anchor="w", pady=(8, 5))
        ttk.Button(page, text="Copy selected", command=self._copy_port_selection).pack(anchor="w")
        ttk.Label(page, text="A registered port is a reference, not proof of what traffic actually uses it. "
                  "This snapshot never updates or queries the network.",
                  style="ToolsMuted.TLabel", wraplength=960).pack(anchor="w", pady=(8, 0))
        self.port_tree.bind("<<TreeviewSelect>>", self._show_port_detail)
        try:
            self.port_records = load_port_registry()
            self.port_load_error = ""
        except OSError:
            self.port_records = ()
            self.port_load_error = "Bundled port registry could not be loaded. Rebuild the EXE with the data file."
        self.port_visible_records = []
        self.port_query.trace_add("write", self._schedule_port_search)
        self.port_protocol.trace_add("write", self._schedule_port_search)
        self._refresh_port_results()

    def _schedule_port_search(self, *_args):
        job = getattr(self, "_port_search_job", None)
        if job:
            self.after_cancel(job)
        self._port_search_job = self.after(120, self._refresh_port_results)

    def _refresh_port_results(self):
        self._port_search_job = None
        self.port_visible_records = []
        for item in self.port_tree.get_children():
            self.port_tree.delete(item)
        self.port_detail.set("Select a result to see its full description.")
        if self.port_load_error:
            self.port_status.set(self.port_load_error)
            return
        try:
            shown, total = search_ports(self.port_records, self.port_query.get(),
                                        self.port_protocol.get())
        except ValueError as error:
            self.port_status.set(str(error))
            return
        self.port_visible_records = shown
        for index, record in enumerate(shown):
            self.port_tree.insert("", "end", iid=str(index), values=(
                record.port, record.protocol or "—", record.service or "—",
                record.common_use or "—", record.description or "—"))
        if not self.port_query.get().strip():
            self.port_status.set(f"Common examples shown; search covers {len(self.port_records):,} bundled IANA entries.")
        else:
            self.port_status.set(f"{total:,} match(es) • showing {len(shown):,}" if total else "No matching IANA entries")

    def _selected_port(self):
        selection = self.port_tree.selection()
        if not selection:
            return None
        index = int(selection[0])
        return self.port_visible_records[index] if index < len(self.port_visible_records) else None

    def _show_port_detail(self, _event=None):
        record = self._selected_port()
        if record:
            self.port_detail.set(
                f"{record.port}/{record.protocol or '—'} — {record.service or '—'}: "
                f"{record.description or 'No description'}"
                + (f"  Reference: {record.reference}" if record.reference else ""))

    def _copy_port_selection(self):
        record = self._selected_port()
        if record:
            self._copy(f"{record.port}/{record.protocol} — {record.service} — "
                       f"{record.common_use or record.description}")

    def _build_dns_records(self):
        page = self._page("DNS Records")
        ttk.Label(page, text="Build common DNS records and reverse names locally; no DNS queries are sent.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 8))
        panels = ttk.Frame(page)
        panels.pack(fill="both", expand=True)
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)
        form = ttk.LabelFrame(panels, text="RECORD BUILDER", padding=12)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        results = ttk.Frame(panels)
        results.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.dns_owner = tk.StringVar()
        self.dns_type = tk.StringVar(value="A")
        self.dns_ttl = tk.StringVar(value="300")
        self.dns_value = tk.StringVar()
        self.dns_priority = tk.StringVar(value="10")
        self.dns_weight = tk.StringVar(value="0")
        self.dns_port = tk.StringVar(value="5060")
        self.dns_caa_flags = tk.StringVar(value="0")
        self.dns_caa_tag = tk.StringVar(value="issue")
        for row, label in enumerate(("Owner / name", "Record type", "TTL (seconds)")):
            ttk.Label(form, text=label, style="ToolsMuted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(form, textvariable=self.dns_owner, style="ToolsInput.TEntry", width=37).grid(
            row=0, column=1, sticky="w", ipady=4, pady=5)
        type_row = ttk.Frame(form)
        type_row.grid(row=1, column=1, sticky="w", pady=5)
        chooser = ttk.Combobox(type_row, textvariable=self.dns_type, values=RECORD_TYPES,
                                state="readonly", width=12)
        chooser.pack(side="left", padx=(0, 12))
        chooser.bind("<<ComboboxSelected>>", self._dns_type_changed)
        self.dns_type_use = tk.StringVar()
        ttk.Label(type_row, textvariable=self.dns_type_use,
                  style="ToolsMuted.TLabel").pack(side="left")
        ttk.Entry(form, textvariable=self.dns_ttl, style="ToolsInput.TEntry", width=15).grid(
            row=2, column=1, sticky="w", ipady=4, pady=5)
        self.dns_value_label = ttk.Label(form, text="Value / target", style="ToolsMuted.TLabel")
        self.dns_value_label.grid(row=3, column=0, sticky="w", padx=(0, 14), pady=5)
        ttk.Entry(form, textvariable=self.dns_value, style="ToolsInput.TEntry", width=37).grid(
            row=3, column=1, sticky="w", ipady=4, pady=5)
        self.dns_extra = ttk.Frame(form)
        self.dns_extra.grid(row=4, column=1, sticky="w", pady=(4, 0))
        self.dns_priority_frame = ttk.Frame(self.dns_extra)
        ttk.Label(self.dns_priority_frame, text="Priority", style="ToolsMuted.TLabel").pack(
            side="left", padx=(0, 6))
        ttk.Entry(self.dns_priority_frame, textvariable=self.dns_priority,
                  style="ToolsInput.TEntry", width=7).pack(side="left", padx=(0, 14))
        self.dns_weight_frame = ttk.Frame(self.dns_extra)
        ttk.Label(self.dns_weight_frame, text="Weight", style="ToolsMuted.TLabel").pack(
            side="left", padx=(0, 6))
        ttk.Entry(self.dns_weight_frame, textvariable=self.dns_weight,
                  style="ToolsInput.TEntry", width=7).pack(side="left", padx=(0, 14))
        self.dns_port_frame = ttk.Frame(self.dns_extra)
        ttk.Label(self.dns_port_frame, text="Port", style="ToolsMuted.TLabel").pack(
            side="left", padx=(0, 6))
        ttk.Entry(self.dns_port_frame, textvariable=self.dns_port,
                  style="ToolsInput.TEntry", width=7).pack(side="left")
        self.dns_caa_frame = ttk.Frame(self.dns_extra)
        ttk.Label(self.dns_caa_frame, text="Flags", style="ToolsMuted.TLabel").pack(
            side="left", padx=(0, 6))
        ttk.Combobox(self.dns_caa_frame, textvariable=self.dns_caa_flags,
                     values=("0", "128"), state="readonly", width=5).pack(side="left", padx=(0, 14))
        ttk.Label(self.dns_caa_frame, text="Tag", style="ToolsMuted.TLabel").pack(
            side="left", padx=(0, 6))
        ttk.Combobox(self.dns_caa_frame, textvariable=self.dns_caa_tag,
                     values=("issue", "issuewild", "iodef"), state="readonly", width=13).pack(side="left")
        self._dns_type_changed()
        ttk.Label(form, text="Use @ for the zone apex. Owner names are used as typed; add a final dot for an absolute owner. "
                  "Domain targets receive a final dot automatically.",
                  style="ToolsMuted.TLabel", wraplength=330).grid(
                      row=5, column=0, columnspan=2, sticky="w", pady=(12, 8))
        actions = ttk.Frame(form)
        actions.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Button(actions, text="Build record", style="Accent.TButton",
                   command=self._generate_dns_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Clear", command=self._clear_dns_record).pack(side="left")
        self.dns_error = tk.StringVar()
        ttk.Label(form, textvariable=self.dns_error, style="ToolsError.TLabel",
                  wraplength=330).grid(row=7, column=0, columnspan=2, sticky="w")
        output = self._section(results, "COPY-READY ZONE RECORD")
        self.dns_record = tk.StringVar(value="Enter a record and click Build record.")
        ttk.Label(output, textvariable=self.dns_record, style="ToolsMono.TLabel",
                  wraplength=340).pack(anchor="w", pady=(0, 8))
        output_row = ttk.Frame(output)
        output_row.pack(fill="x")
        ttk.Button(output_row, text="Copy record", command=lambda: self._copy(
            self.dns_record.get() if self.dns_record_valid else "")).pack(side="left", padx=(0, 12))
        self.dns_ttl_display = tk.StringVar(value="TTL: 5 minutes")
        ttk.Label(output_row, textvariable=self.dns_ttl_display,
                  style="ToolsMuted.TLabel").pack(side="left")
        self.dns_record_valid = False

        reverse = self._section(results, "REVERSE DNS NAME")
        reverse_row = ttk.Frame(reverse)
        reverse_row.pack(fill="x")
        ttk.Label(reverse_row, text="IP address", style="ToolsMuted.TLabel").pack(side="left", padx=(0, 10))
        self.dns_reverse_ip = tk.StringVar()
        ttk.Entry(reverse_row, textvariable=self.dns_reverse_ip,
                  style="ToolsInput.TEntry", width=28).pack(side="left", ipady=4, padx=(0, 8))
        ttk.Button(reverse_row, text="Generate",
                   command=self._generate_reverse_name).pack(side="left")
        self.dns_reverse_name = tk.StringVar(value="—")
        ttk.Label(reverse, textvariable=self.dns_reverse_name, style="ToolsMono.TLabel",
                  wraplength=340).pack(anchor="w", pady=(8, 5))
        ttk.Button(reverse, text="Copy PTR name", command=lambda: self._copy(
            self.dns_reverse_name.get())).pack(anchor="w")
        for variable in (self.dns_owner, self.dns_type, self.dns_ttl, self.dns_value,
                         self.dns_priority, self.dns_weight, self.dns_port,
                         self.dns_caa_flags, self.dns_caa_tag):
            variable.trace_add("write", self._invalidate_dns_record)
        self.dns_reverse_ip.trace_add("write", lambda *_: self.dns_reverse_name.set("—"))

    def _invalidate_dns_record(self, *_args):
        self.dns_record_valid = False
        self.dns_record.set("Enter a record and click Build record.")
        self.dns_error.set("")

    def _dns_type_changed(self, _event=None):
        record_type = self.dns_type.get()
        self.dns_type_use.set(RECORD_USES.get(record_type, ""))
        self.dns_value_label.configure(text={
            "A": "IPv4 address", "AAAA": "IPv6 address", "TXT": "Text value",
            "CAA": "CA / report value"}.get(record_type, "Target DNS name"))
        for frame in (self.dns_priority_frame, self.dns_weight_frame,
                      self.dns_port_frame, self.dns_caa_frame):
            frame.pack_forget()
        if record_type in ("MX", "SRV"):
            self.dns_priority_frame.pack(side="left")
        if record_type == "SRV":
            self.dns_weight_frame.pack(side="left")
            self.dns_port_frame.pack(side="left")
        if record_type == "CAA":
            self.dns_caa_frame.pack(side="left")
        if hasattr(self, "dns_record_valid"):
            self.dns_record_valid = False
            self.dns_record.set("Enter a record and click Build record.")

    def _generate_dns_record(self):
        self.dns_record_valid = False
        self.dns_error.set("")
        try:
            record = build_dns_record(
                self.dns_owner.get(), self.dns_type.get(), self.dns_ttl.get(),
                self.dns_value.get(), priority=self.dns_priority.get(),
                weight=self.dns_weight.get(), port=self.dns_port.get(),
                caa_flags=self.dns_caa_flags.get(), caa_tag=self.dns_caa_tag.get())
            ttl_text = ttl_display(self.dns_ttl.get())
        except ValueError as error:
            self.dns_record.set("Enter a valid record and click Build record.")
            self.dns_error.set(str(error))
            self.status_callback("DNS record needs correction")
            return
        self.dns_record.set(record)
        self.dns_ttl_display.set(f"TTL: {ttl_text}")
        self.dns_record_valid = True
        self.status_callback("DNS record built locally")

    def _clear_dns_record(self):
        self.dns_owner.set("")
        self.dns_type.set("A")
        self.dns_ttl.set("300")
        self.dns_value.set("")
        self.dns_record.set("Enter a record and click Build record.")
        self.dns_record_valid = False
        self.dns_ttl_display.set("TTL: 5 minutes")
        self.dns_error.set("")
        self._dns_type_changed()

    def _generate_reverse_name(self):
        try:
            self.dns_reverse_name.set(reverse_ptr_owner(self.dns_reverse_ip.get()))
            self.dns_error.set("")
            self.status_callback("Reverse DNS name generated locally")
        except ValueError as error:
            self.dns_reverse_name.set("—")
            self.dns_error.set(str(error))

    def _build_mtu(self):
        page = self._page("MTU Calculator")
        ttk.Label(page, text="Estimate payload limits for common encapsulations without touching the network.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 8))
        panels = ttk.Frame(page)
        panels.pack(fill="x", pady=(0, 8))
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)
        inputs = ttk.LabelFrame(panels, text="LINK AND ENCAPSULATION", padding=12)
        inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.mtu_budget = tk.StringVar(value="1500")
        self.mtu_pppoe = tk.BooleanVar(value=False)
        self.mtu_vlan_tags = tk.StringVar(value="0")
        self.mtu_tunnel = tk.StringVar(value="None")
        self.mtu_family = tk.StringVar(value="IPv4")
        for row, label in enumerate(("Ethernet payload budget (bytes)", "PPPoE / PPP", "VLAN tags on outer frame",
                                      "Tunnel", "Inner IP family")):
            ttk.Label(inputs, text=label, style="ToolsMuted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=5)
        ttk.Entry(inputs, textvariable=self.mtu_budget,
                  style="ToolsInput.TEntry", width=14).grid(row=0, column=1, sticky="w", ipady=4, pady=5)
        ttk.Checkbutton(inputs, text="Enabled (8 bytes)", variable=self.mtu_pppoe).grid(
            row=1, column=1, sticky="w", pady=5)
        ttk.Combobox(inputs, textvariable=self.mtu_vlan_tags, values=("0", "1", "2"),
                     state="readonly", width=11).grid(row=2, column=1, sticky="w", pady=5)
        ttk.Combobox(inputs, textvariable=self.mtu_tunnel, values=tuple(TUNNEL_OVERHEAD),
                     state="readonly", width=24).grid(row=3, column=1, sticky="w", pady=5)
        ttk.Combobox(inputs, textvariable=self.mtu_family, values=("IPv4", "IPv6"),
                     state="readonly", width=11).grid(row=4, column=1, sticky="w", pady=5)
        actions = ttk.Frame(inputs)
        actions.grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 6))
        ttk.Button(actions, text="Calculate", style="Accent.TButton",
                   command=self._calculate_mtu).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Copy summary", command=self._copy_mtu_summary).pack(side="left")
        self.mtu_error = tk.StringVar()
        ttk.Label(inputs, textvariable=self.mtu_error, style="ToolsError.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w")
        output = ttk.LabelFrame(panels, text="SIZE BUDGET", padding=12)
        output.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        rows = (("Underlay IP MTU", "underlay_ip_mtu"),
                ("PPPoE / PPP overhead", "pppoe_bytes"),
                ("Tunnel overhead", "tunnel_bytes"),
                ("Inner IP MTU", "inner_ip_mtu"),
                ("TCP MSS (base headers)", "tcp_mss"),
                ("UDP data (base headers)", "udp_payload"),
                ("VLAN tag wire overhead", "vlan_wire_bytes"),
                ("Ethernet frame with FCS", "ethernet_frame_bytes"))
        self.mtu_values = {}
        for row, (label, key) in enumerate(rows):
            ttk.Label(output, text=label, style="ToolsMuted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 18), pady=4)
            variable = tk.StringVar(value="—")
            self.mtu_values[key] = variable
            ttk.Label(output, textvariable=variable, style="ToolsValue.TLabel").grid(
                row=row, column=1, sticky="w", pady=4)
        self.mtu_warning = tk.StringVar()
        ttk.Label(output, textvariable=self.mtu_warning, style="ToolsError.TLabel",
                  wraplength=350).grid(row=len(rows), column=0, columnspan=2, sticky="w")
        ttk.Label(page, text="VLAN tags add wire bytes but do not automatically lower IP MTU. "
                  "Assumes minimum IP/TCP headers and base GRE/VXLAN; options, extensions, tunnel keys, IPsec, "
                  "and a smaller path MTU are not included.",
                  style="ToolsMuted.TLabel", wraplength=700).pack(anchor="w")
        self.mtu_result = None
        self._calculate_mtu()
        for variable in (self.mtu_budget, self.mtu_pppoe, self.mtu_vlan_tags,
                         self.mtu_tunnel, self.mtu_family):
            variable.trace_add("write", self._invalidate_mtu_result)

    def _invalidate_mtu_result(self, *_args):
        self.mtu_result = None
        for variable in self.mtu_values.values():
            variable.set("—")
        self.mtu_warning.set("Inputs changed — click Calculate to refresh the budget.")
        self.mtu_error.set("")

    def _calculate_mtu(self):
        self.mtu_error.set("")
        self.mtu_warning.set("")
        try:
            result = calculate_mtu(
                self.mtu_budget.get(), pppoe=self.mtu_pppoe.get(),
                vlan_tags=int(self.mtu_vlan_tags.get()), tunnel=self.mtu_tunnel.get(),
                inner_family=self.mtu_family.get())
        except ValueError as error:
            self.mtu_result = None
            for variable in self.mtu_values.values():
                variable.set("—")
            self.mtu_error.set(str(error))
            self.status_callback("MTU inputs need correction")
            return
        self.mtu_result = result
        for key, variable in self.mtu_values.items():
            variable.set(f"{result[key]:,} bytes")
        self.mtu_warning.set(" ".join(result["warnings"]))
        self.status_callback("MTU budget calculated locally")

    def _copy_mtu_summary(self):
        if self.mtu_result:
            self._copy(mtu_summary(self.mtu_result))

    def _build_wifi_qr(self):
        page = self._page("Wi-Fi QR")
        ttk.Label(page, text="Create and export a Wi-Fi join code locally. No profiles or passwords are saved.",
                  style="ToolsMuted.TLabel").pack(anchor="w", pady=(0, 8))
        inputs = self._section(page, "NETWORK DETAILS")
        self.wifi_ssid = tk.StringVar()
        self.wifi_password = tk.StringVar()
        self.wifi_security = tk.StringVar(value=PERSONAL)
        self.wifi_hidden = tk.BooleanVar(value=False)
        self.wifi_show_password = tk.BooleanVar(value=False)
        self.wifi_security_note = tk.StringVar()
        for row, label in enumerate(("Network name (SSID)", "Security", "Password")):
            ttk.Label(inputs, text=label, style="ToolsMuted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        self.wifi_ssid_entry = ttk.Entry(inputs, textvariable=self.wifi_ssid,
                                         style="ToolsInput.TEntry", width=41)
        self.wifi_ssid_entry.grid(row=0, column=1, sticky="w", ipady=4, pady=4)
        ttk.Combobox(inputs, textvariable=self.wifi_security,
                     values=SECURITY_CHOICES, state="readonly", width=38).grid(
                         row=1, column=1, sticky="w", pady=4)
        ttk.Checkbutton(inputs, text="Hidden SSID", variable=self.wifi_hidden).grid(
            row=1, column=2, sticky="w", padx=(12, 0), pady=4)
        self.wifi_password_entry = ttk.Entry(inputs, textvariable=self.wifi_password,
                                             style="ToolsInput.TEntry", show="•", width=41)
        self.wifi_password_entry.grid(row=2, column=1, sticky="w", ipady=4, pady=4)
        ttk.Checkbutton(inputs, text="Show", variable=self.wifi_show_password,
                        command=self._toggle_wifi_password).grid(
                            row=2, column=2, sticky="w", padx=(12, 0), pady=4)
        ttk.Label(inputs, textvariable=self.wifi_security_note, style="ToolsMuted.TLabel",
                  wraplength=680).grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(0, 7))
        ttk.Button(actions, text="Generate QR", style="Accent.TButton",
                   command=self.generate_wifi_qr).pack(side="left", padx=(0, 8))
        self.wifi_save_button = ttk.Button(actions, text="Save PNG", command=self._save_wifi_qr)
        self.wifi_save_button.pack(side="left", padx=(0, 8))
        self.wifi_svg_button = ttk.Button(actions, text="Save SVG", command=self._save_wifi_svg)
        self.wifi_svg_button.pack(side="left", padx=(0, 8))
        self.wifi_copy_image_button = ttk.Button(actions, text="Copy image", command=self._copy_wifi_image)
        self.wifi_copy_image_button.pack(side="left", padx=(0, 8))
        self.wifi_copy_payload_button = ttk.Button(actions, text="Copy payload", command=self._copy_wifi_payload)
        self.wifi_copy_payload_button.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Clear", command=self._clear_wifi_fields).pack(side="left")
        self.wifi_error = tk.StringVar()
        ttk.Label(page, textvariable=self.wifi_error, style="ToolsError.TLabel").pack(anchor="w", pady=(0, 4))

        self.wifi_advanced_button = ttk.Button(page, text="Show advanced options ▾",
                                               command=self._toggle_wifi_advanced)
        self.wifi_advanced_button.pack(anchor="w", pady=(0, 7))
        lower = ttk.Frame(page)
        lower.pack(fill="both", expand=True)
        self.wifi_advanced = ttk.LabelFrame(lower, text="PRINT AND QR OPTIONS", padding=10)
        self.wifi_preset = tk.StringVar(value="2 × 2 in @ 300 DPI")
        self.wifi_size_mode = tk.StringVar(value="Inches + DPI")
        self.wifi_inches = tk.StringVar(value="2")
        self.wifi_dpi = tk.StringVar(value="300")
        self.wifi_pixels = tk.StringVar(value="600")
        self.wifi_ecc = tk.StringVar(value="M")
        self.wifi_border = tk.StringVar(value="4")
        self.wifi_live = tk.BooleanVar(value=False)
        self.wifi_live_job = None
        self.wifi_advanced.columnconfigure(1, weight=1)
        for row, label in enumerate(("Export preset", "Size mode", "Inches", "DPI", "Pixels", "Error correction", "Quiet zone (modules)")):
            ttk.Label(self.wifi_advanced, text=label, style="ToolsMuted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 9), pady=3)
        ttk.Combobox(self.wifi_advanced, textvariable=self.wifi_preset,
                     values=("2 × 2 in @ 300 DPI", "2 × 2 in @ 600 DPI", "Custom"),
                     state="readonly", width=24).grid(row=0, column=1, sticky="ew", pady=3)
        self.wifi_mode_box = ttk.Combobox(self.wifi_advanced, textvariable=self.wifi_size_mode,
                                          values=("Inches + DPI", "Pixels"), state="readonly", width=24)
        self.wifi_mode_box.grid(row=1, column=1, sticky="ew", pady=3)
        self.wifi_inches_entry = ttk.Entry(self.wifi_advanced, textvariable=self.wifi_inches,
                                           style="ToolsInput.TEntry", width=12)
        self.wifi_inches_entry.grid(row=2, column=1, sticky="w", pady=3)
        self.wifi_dpi_entry = ttk.Entry(self.wifi_advanced, textvariable=self.wifi_dpi,
                                        style="ToolsInput.TEntry", width=12)
        self.wifi_dpi_entry.grid(row=3, column=1, sticky="w", pady=3)
        self.wifi_pixels_entry = ttk.Entry(self.wifi_advanced, textvariable=self.wifi_pixels,
                                           style="ToolsInput.TEntry", width=12)
        self.wifi_pixels_entry.grid(row=4, column=1, sticky="w", pady=3)
        ecc_box = ttk.Combobox(self.wifi_advanced, textvariable=self.wifi_ecc,
                               values=("L", "M", "Q", "H"), state="readonly", width=10)
        ecc_box.grid(row=5, column=1, sticky="w", pady=3)
        Tooltip(ecc_box, "L ≈ 7%, M ≈ 15%, Q ≈ 25%, H ≈ 30% recovery. Higher levels make a denser QR.",
                self.palette_getter)
        border_entry = ttk.Entry(self.wifi_advanced, textvariable=self.wifi_border,
                                  style="ToolsInput.TEntry", width=12)
        border_entry.grid(row=6, column=1, sticky="w", pady=3)
        Tooltip(border_entry, "White margin measured in QR modules; four is the recommended default.",
                self.palette_getter)
        ttk.Checkbutton(self.wifi_advanced, text="Live preview as I type", variable=self.wifi_live).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(6, 2))
        ttk.Label(self.wifi_advanced, text="M is balanced; Q/H add redundancy. Keep a 4-module quiet zone for reliable scans.",
                  style="ToolsMuted.TLabel", wraplength=360).grid(
                      row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))

        preview = ttk.LabelFrame(lower, text="QR PREVIEW", padding=10)
        preview.pack(side="right", fill="both", expand=True)
        self.wifi_preview = ttk.Label(preview, text="Enter details and click Generate QR.",
                                      style="ToolsMuted.TLabel")
        self.wifi_preview.pack(anchor="center", pady=(4, 8))
        self.wifi_size_info = tk.StringVar(value="Export size shown after generation")
        ttk.Label(preview, textvariable=self.wifi_size_info, style="ToolsMuted.TLabel").pack(anchor="w")
        self.wifi_show_payload = tk.BooleanVar(value=False)
        ttk.Checkbutton(preview, text="Show raw payload (includes password)",
                        variable=self.wifi_show_payload, command=self._refresh_wifi_payload_display).pack(
                            anchor="w", pady=(7, 3))
        self.wifi_payload_display = tk.StringVar(value="Generate a QR to view its payload.")
        ttk.Entry(preview, textvariable=self.wifi_payload_display, state="readonly",
                  width=42).pack(fill="x")
        ttk.Label(page, text="The QR, SVG, PNG, raw payload, and image clipboard expose the Wi-Fi password. "
                  "Nothing is saved until you export; test a code on the intended device.",
                  style="ToolsMuted.TLabel", wraplength=720).pack(anchor="w", pady=(6, 0))
        self.wifi_qr_image = None
        self.wifi_qr_payload = None
        self.wifi_export_settings = None
        for button in (self.wifi_save_button, self.wifi_svg_button,
                       self.wifi_copy_image_button, self.wifi_copy_payload_button):
            button.configure(state="disabled")
        for variable in (self.wifi_ssid, self.wifi_password, self.wifi_security,
                         self.wifi_hidden, self.wifi_preset, self.wifi_size_mode,
                         self.wifi_inches, self.wifi_dpi, self.wifi_pixels,
                         self.wifi_ecc, self.wifi_border, self.wifi_live):
            variable.trace_add("write", self._wifi_fields_changed)
        self.wifi_security.trace_add("write", self._wifi_security_changed)
        self.wifi_preset.trace_add("write", self._wifi_preset_changed)
        self.wifi_size_mode.trace_add("write", self._wifi_mode_changed)
        self._wifi_security_changed()
        self._wifi_mode_changed()

    def _toggle_wifi_advanced(self):
        if self.wifi_advanced.winfo_manager():
            self.wifi_advanced.pack_forget()
            self.wifi_advanced_button.configure(text="Show advanced options ▾")
        else:
            self.wifi_advanced.pack(side="left", fill="y", padx=(0, 8),
                                    before=self.wifi_preview.master)
            self.wifi_advanced_button.configure(text="Hide advanced options ▴")
        if self.wifi_qr_payload is not None:
            self._render_wifi_preview_image()

    def _wifi_preset_changed(self, *_args):
        preset = self.wifi_preset.get()
        if preset != "Custom":
            dpi = "600" if "600 DPI" in preset else "300"
            self.wifi_size_mode.set("Inches + DPI")
            self.wifi_inches.set("2")
            self.wifi_dpi.set(dpi)
            self.wifi_pixels.set("1200" if dpi == "600" else "600")
        self._wifi_mode_changed()

    def _wifi_mode_changed(self, *_args):
        custom = self.wifi_preset.get() == "Custom"
        self.wifi_mode_box.configure(state="readonly" if custom else "disabled")
        self.wifi_inches_entry.configure(state="normal" if custom and self.wifi_size_mode.get() == "Inches + DPI" else "disabled")
        self.wifi_pixels_entry.configure(state="normal" if custom and self.wifi_size_mode.get() == "Pixels" else "disabled")
        self.wifi_dpi_entry.configure(state="normal" if custom else "disabled")

    def _wifi_security_changed(self, *_args):
        if self.wifi_security.get() == OPEN:
            self.wifi_password.set("")
            self.wifi_password_entry.configure(state="disabled")
        else:
            self.wifi_password_entry.configure(state="normal")
        security = self.wifi_security.get()
        if security == WEP:
            note = "WEP is obsolete and insecure; use only for legacy compatibility."
        elif security in (WPA3, MIXED):
            note = "Compatibility QR: encoded as T:WPA; the QR cannot enforce WPA3 or mixed mode. Test on your device."
        else:
            note = "Select the security mode configured on the network."
        self.wifi_security_note.set(note)

    def _toggle_wifi_password(self):
        self.wifi_password_entry.configure(show="" if self.wifi_show_password.get() else "•")

    def _wifi_fields_changed(self, *_args):
        self._clear_wifi_preview()
        if self.wifi_live.get():
            self.wifi_live_job = self.after(350, lambda: self.generate_wifi_qr(quiet=True))

    def _clear_wifi_preview(self, *_args):
        if self.wifi_live_job is not None:
            self.after_cancel(self.wifi_live_job)
            self.wifi_live_job = None
        self.wifi_qr_payload = None
        self.wifi_qr_image = None
        self.wifi_export_settings = None
        self.wifi_preview.configure(image="", text="Enter details and click Generate QR.")
        for button in (self.wifi_save_button, self.wifi_svg_button,
                       self.wifi_copy_image_button, self.wifi_copy_payload_button):
            button.configure(state="disabled")
        self.wifi_size_info.set("Export size shown after generation")
        self._refresh_wifi_payload_display()
        self.wifi_error.set("")

    def _refresh_wifi_payload_display(self):
        if self.wifi_qr_payload is None:
            self.wifi_payload_display.set("Generate a QR to view its payload.")
        elif self.wifi_show_payload.get():
            self.wifi_payload_display.set(self.wifi_qr_payload)
        else:
            self.wifi_payload_display.set("Hidden — click Show raw payload to reveal")

    def _wifi_render_settings(self):
        preset = self.wifi_preset.get()
        if preset == "2 × 2 in @ 300 DPI":
            size, dpi = 600, 300
        elif preset == "2 × 2 in @ 600 DPI":
            size, dpi = 1200, 600
        elif preset == "Custom":
            try:
                dpi = int(self.wifi_dpi.get())
                if self.wifi_size_mode.get() == "Pixels":
                    size = int(self.wifi_pixels.get())
                else:
                    inches = float(self.wifi_inches.get())
                    if not math.isfinite(inches) or not 0.5 <= inches <= 10:
                        raise ValueError
                    size = round(inches * dpi)
            except ValueError as error:
                raise ValueError("Enter a valid custom size (0.5–10 inches or 128–4096 pixels) and DPI.") from error
        else:
            raise ValueError("Choose an export preset.")
        if not 72 <= dpi <= 1200 or not 128 <= size <= 4096:
            raise ValueError("Use 72–1200 DPI and an export size of 128–4096 pixels.")
        try:
            border = int(self.wifi_border.get())
        except ValueError as error:
            raise ValueError("Quiet zone must be 0–20 modules.") from error
        if not 0 <= border <= 20:
            raise ValueError("Quiet zone must be 0–20 modules.")
        ecc = self.wifi_ecc.get()
        if ecc not in ("L", "M", "Q", "H"):
            raise ValueError("Choose QR error correction L, M, Q, or H.")
        return size, dpi, ecc, border

    def _clear_wifi_fields(self):
        self.wifi_live.set(False)
        self.wifi_ssid.set("")
        self.wifi_password.set("")
        self.wifi_security.set(PERSONAL)
        self.wifi_hidden.set(False)
        self.wifi_show_password.set(False)
        self.wifi_show_payload.set(False)
        self.wifi_preset.set("2 × 2 in @ 300 DPI")
        self.wifi_ecc.set("M")
        self.wifi_border.set("4")
        self._toggle_wifi_password()
        self._clear_wifi_preview()
        self.status_callback("Wi-Fi QR fields cleared")

    def generate_wifi_qr(self, quiet=False):
        self._clear_wifi_preview()
        try:
            payload = wifi_payload(self.wifi_ssid.get(), self.wifi_password.get(),
                                   self.wifi_security.get(), self.wifi_hidden.get())
            size, dpi, ecc, border = self._wifi_render_settings()
        except ValueError as error:
            if not quiet:
                self.wifi_error.set(str(error))
                self.status_callback("Wi-Fi QR input needs correction")
            return
        self.wifi_qr_payload = payload
        self.wifi_export_settings = (size, dpi, ecc, border)
        self._render_wifi_preview_image()
        self.wifi_size_info.set(f"Export: {size:,} × {size:,} px at {dpi} DPI")
        for button in (self.wifi_save_button, self.wifi_svg_button,
                       self.wifi_copy_image_button, self.wifi_copy_payload_button):
            button.configure(state="normal")
        self._refresh_wifi_payload_display()
        if not quiet:
            self.status_callback("Wi-Fi QR generated locally")

    def _render_wifi_preview_image(self):
        _size, _dpi, ecc, border = self.wifi_export_settings
        preview_size = 205 if self.wifi_advanced.winfo_manager() else 260
        png = wifi_qr_png(self.wifi_qr_payload, pixel_size=preview_size,
                          error_correction=ecc, border=border)
        image = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
        self.wifi_qr_image = image
        self.wifi_preview.configure(image=image, text="")

    def _save_wifi_qr(self):
        if self.wifi_qr_payload is None:
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(),
                                            title="Save Wi-Fi QR code",
                                            initialfile="wifi-qr.png", defaultextension=".png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            size, dpi, ecc, border = self.wifi_export_settings
            Path(path).write_bytes(wifi_qr_png(self.wifi_qr_payload, pixel_size=size,
                                               dpi=dpi, error_correction=ecc, border=border))
        except (OSError, ValueError) as error:
            self.wifi_error.set(f"Could not save PNG: {error}")
            self.status_callback("Wi-Fi QR save failed")
            return
        self.status_callback("Wi-Fi QR saved to the selected file")

    def _save_wifi_svg(self):
        if self.wifi_qr_payload is None:
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(),
                                            title="Save Wi-Fi QR vector image",
                                            initialfile="wifi-qr.svg", defaultextension=".svg",
                                            filetypes=[("SVG image", "*.svg")])
        if not path:
            return
        try:
            _size, _dpi, ecc, border = self.wifi_export_settings
            Path(path).write_bytes(wifi_qr_svg(self.wifi_qr_payload,
                                               error_correction=ecc, border=border))
        except (OSError, ValueError) as error:
            self.wifi_error.set(f"Could not save SVG: {error}")
            self.status_callback("Wi-Fi QR save failed")
            return
        self.status_callback("Wi-Fi QR SVG saved to the selected file")

    def _copy_wifi_image(self):
        if self.wifi_qr_payload is None:
            return
        try:
            size, _dpi, ecc, border = self.wifi_export_settings
            dib = wifi_qr_dib(self.wifi_qr_payload, pixel_size=size,
                              error_correction=ecc, border=border)
            copy_dib_to_clipboard(dib, self.winfo_toplevel().winfo_id())
        except (OSError, ValueError, MemoryError) as error:
            self.wifi_error.set(f"Could not copy QR image: {error}")
            self.status_callback("Wi-Fi QR image copy failed")
            return
        self.status_callback("Wi-Fi QR image copied to clipboard")

    def _copy_wifi_payload(self):
        if self.wifi_qr_payload is not None:
            self._copy(self.wifi_qr_payload)

    def apply_theme(self, palette):
        self.palette = palette
        if hasattr(self, "prefix_scale"):
            self.prefix_scale.configure(
                background=palette["entry_bg"], foreground=palette["fg"],
                troughcolor=palette["button_bg"], activebackground=palette["select_bg"],
            )
        for widget_name in ("site_template", "mac_input", "dhcp_input", "dhcp_wlc_input",
                            "dhcp_custom_input", "dhcp_raw_input", "dhcp_121_build_input",
                            "dhcp_121_decode_input"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            widget.configure(
                background=palette["tool_input_bg"], foreground=palette["fg"],
                insertbackground=palette["insert"], selectbackground=palette["select_bg"],
                selectforeground=palette["select_fg"],
                highlightbackground=palette["border"], highlightcolor=palette["select_bg"],
                highlightthickness=2, relief="solid", borderwidth=1,
            )
