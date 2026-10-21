"""Offline, repeatable IPv4 site/VLAN address planning."""

import csv
import ipaddress
import re


MAX_SITES = 512
MAX_VLAN_ROWS = 5000


def parse_vlan_template(text):
    """Parse one ``VLAN, name, /prefix`` entry per line."""
    vlans = []
    seen_ids = set()
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        try:
            fields = next(csv.reader([raw_line], strict=True))
        except csv.Error as exc:
            raise ValueError(f"Line {line_number}: invalid CSV-style VLAN entry.") from exc
        if len(fields) != 3:
            raise ValueError(f"Line {line_number}: use VLAN, name, /prefix (for example 10, Utility, /25).")
        vlan_text, name, prefix_text = (field.strip() for field in fields)
        if not vlan_text.isdecimal() or not 1 <= int(vlan_text) <= 4094:
            raise ValueError(f"Line {line_number}: VLAN ID must be 1–4094.")
        vlan_id = int(vlan_text)
        if vlan_id in seen_ids:
            raise ValueError(f"Line {line_number}: VLAN {vlan_id} is listed more than once.")
        if not name or len(name) > 64 or any(ord(character) < 32 for character in name):
            raise ValueError(f"Line {line_number}: name must be 1–64 visible characters.")
        if not re.fullmatch(r"/?\d{1,2}", prefix_text):
            raise ValueError(f"Line {line_number}: enter a CIDR prefix such as /24.")
        prefix = int(prefix_text.lstrip("/"))
        if not 0 <= prefix <= 32:
            raise ValueError(f"Line {line_number}: IPv4 prefix must be /0–/32.")
        seen_ids.add(vlan_id)
        vlans.append({"vlan": vlan_id, "name": name, "prefix": prefix,
                      "addresses": 1 << (32 - prefix)})
    if not vlans:
        raise ValueError("Enter at least one VLAN template line.")
    return vlans


def plan_sites(parent_text, template_text, site_prefix_text="auto", site_count_text="1"):
    """Fit a repeated VLAN template into aligned, non-overlapping site blocks.

    Larger VLAN networks are placed first so every subnet stays aligned. The
    displayed VLAN order follows the entered template, not placement order.
    """
    try:
        parent = ipaddress.IPv4Network(parent_text.strip(), strict=True)
    except ValueError as exc:
        raise ValueError("Enter an aligned IPv4 parent CIDR, such as 10.0.0.0/16.") from exc
    vlans = parse_vlan_template(template_text)
    required = sum(vlan["addresses"] for vlan in vlans)
    if required > parent.num_addresses:
        raise ValueError(f"The VLAN template needs {required:,} addresses, more than {parent} contains.")
    minimum_prefix = 32 - (required - 1).bit_length()
    prefix_text = str(site_prefix_text).strip().lstrip("/")
    if not prefix_text or prefix_text.casefold() == "auto":
        site_prefix = minimum_prefix
    elif prefix_text.isdecimal() and 0 <= int(prefix_text) <= 32:
        site_prefix = int(prefix_text)
    else:
        raise ValueError("Site block must be Auto or an IPv4 prefix such as /21.")
    if site_prefix < parent.prefixlen:
        raise ValueError(f"A /{site_prefix} site block is larger than the {parent} parent network.")
    if site_prefix > minimum_prefix:
        raise ValueError(f"The template needs at least a /{minimum_prefix} site block; /{site_prefix} is too small.")
    max_sites = 1 << (site_prefix - parent.prefixlen)
    count_text = str(site_count_text).strip()
    if not count_text.isdecimal() or int(count_text) < 1:
        raise ValueError("Sites to generate must be a positive whole number.")
    count = int(count_text)
    if count > max_sites:
        raise ValueError(f"Only {max_sites:,} /{site_prefix} site blocks fit in {parent}.")
    if count > MAX_SITES or count * len(vlans) > MAX_VLAN_ROWS:
        raise ValueError(f"Generate at most {MAX_SITES:,} sites and {MAX_VLAN_ROWS:,} VLAN rows at once.")

    site_size = 1 << (32 - site_prefix)
    placement_order = sorted(enumerate(vlans), key=lambda item: (item[1]["prefix"], item[0]))
    sites = []
    for index in range(count):
        start = int(parent.network_address) + index * site_size
        site_network = ipaddress.IPv4Network((start, site_prefix))
        cursor = start
        placed = [None] * len(vlans)
        for original_index, vlan in placement_order:
            vlan_network = ipaddress.IPv4Network((cursor, vlan["prefix"]))
            if not vlan_network.subnet_of(site_network):
                raise ValueError(f"VLAN {vlan['vlan']} does not fit within {site_network}.")
            usable = vlan["addresses"] if vlan["prefix"] >= 31 else vlan["addresses"] - 2
            placed[original_index] = {**vlan, "network": vlan_network, "usable": usable}
            cursor += vlan["addresses"]
        free_networks = list(ipaddress.summarize_address_range(
            ipaddress.IPv4Address(cursor), site_network.broadcast_address
        )) if cursor <= int(site_network.broadcast_address) else []
        sites.append({"number": index + 1, "network": site_network,
                      "vlans": placed, "free_networks": free_networks})
    return {"parent": parent, "vlans": vlans, "required_per_site": required,
            "minimum_site_prefix": minimum_prefix, "site_prefix": site_prefix,
            "site_capacity": site_size, "free_per_site": site_size - required,
            "max_sites": max_sites, "generated_sites": count, "sites": sites}


def site_plan_rows(plan):
    """Yield copy/export-ready rows with both summary and VLAN CIDRs."""
    for site in plan["sites"]:
        for vlan in site["vlans"]:
            yield (site["number"], str(site["network"]), vlan["vlan"],
                   vlan["name"], str(vlan["network"]), vlan["addresses"], vlan["usable"])
        for network in site["free_networks"]:
            yield (site["number"], str(site["network"]), "", "Unallocated",
                   str(network), network.num_addresses, "")
