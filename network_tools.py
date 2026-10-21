"""Offline network calculations used by Layer 8 Toolkit."""

import ipaddress
import re


DHCP_COMMON_OPTIONS = {
    1: ("Subnet mask", "The client's IPv4 network mask.", "mask"),
    3: ("Default gateway", "One or more routers, in preference order.", "ipv4_list"),
    6: ("DNS servers", "IPv4 DNS resolver addresses, in preference order.", "ipv4_list"),
    12: ("Host name", "A host name suggested to the client.", "ascii"),
    15: ("Domain name", "The client's DNS domain name.", "ascii"),
    42: ("NTP servers", "IPv4 time-server addresses.", "ipv4_list"),
    43: ("Vendor-specific", "Vendor-defined information; Cisco WLC or custom TLV builder.", "option43"),
    51: ("Lease time", "IPv4 address lease duration, in seconds.", "seconds"),
    66: ("TFTP server name", "Boot/configuration server name or address as text.", "ascii"),
    67: ("Bootfile name", "Network boot filename/path as text.", "ascii"),
    121: ("Classless static routes", "IPv4 destination/gateway routes; supporting clients use these instead of Option 3.", "option121"),
    150: ("TFTP server addresses", "IPv4 TFTP server addresses; commonly used by IP phones.", "ipv4_list"),
}


_CISCO_TYPE7_KEY = b"dsfd;kfoA,.iyewrkldJKDHSUBsgvca69834ncxv9873254k;fg87"


def cisco_type7_decrypt(value):
    """Decode one Cisco Type 7 value or a config line ending in ``7 <value>``."""
    text = value.strip()
    if not text:
        raise ValueError("Enter a Cisco Type 7 value or a configuration line ending in '7 <value>'.")
    if re.fullmatch(r"[0-9A-Fa-f]+", text):
        encoded = text
    else:
        match = re.search(r"(?:^|\s)7\s+([0-9A-Fa-f]+)\s*$", text)
        if not match:
            raise ValueError("Enter a Type 7 hex value or a configuration line ending in '7 <value>'.")
        encoded = match.group(1)
    if len(encoded) < 4 or len(encoded) % 2:
        raise ValueError("Type 7 value needs a two-digit seed followed by complete hex byte pairs.")
    if not encoded[:2].isdigit() or not 0 <= int(encoded[:2]) <= 15:
        raise ValueError("Type 7 seed must be a decimal number from 00 through 15.")
    seed = int(encoded[:2])
    decoded = bytes(byte ^ _CISCO_TYPE7_KEY[(seed + index) % len(_CISCO_TYPE7_KEY)]
                    for index, byte in enumerate(bytes.fromhex(encoded[2:])))
    # Keep control bytes visible as escapes instead of placing them into the GUI.
    return "".join(f"\\x{ord(char):02X}" if ord(char) < 32 or ord(char) == 127 else char
                   for char in decoded.decode("utf-8", errors="backslashreplace"))


def _dhcp_option_result(code, payload, suboptions=()):
    if not 1 <= len(payload) <= 255:
        raise ValueError("DHCP option value must contain 1–255 bytes.")
    hex_payload = payload.hex()
    result = {
        "code": code,
        "hex": hex_payload,
        "wire_hex": bytes((code, len(payload))).hex() + hex_payload,
        "length": len(payload),
        "suboptions": [
            {"code": subcode, "length": len(value), "hex": value.hex()}
            for subcode, value in suboptions
        ],
    }
    if code == 43:
        result["ios"] = f"option 43 hex {hex_payload}"
    return result


def dhcp_option_value(code, value_text):
    """Encode a supported common DHCPv4 option; return value and on-wire hex."""
    if code not in DHCP_COMMON_OPTIONS or code in (43, 121):
        raise ValueError("Choose a simple DHCP option; use the dedicated builder for Options 43 and 121.")
    kind = DHCP_COMMON_OPTIONS[code][2]
    value_text = value_text.strip()
    if not value_text:
        raise ValueError("Enter a value to generate this DHCP option.")
    if kind == "mask":
        try:
            payload = ipaddress.IPv4Network(f"0.0.0.0/{value_text}").netmask.packed
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as exc:
            raise ValueError("Enter a contiguous IPv4 subnet mask or prefix length.") from exc
    elif kind == "ipv4_list":
        payload = _ipv4_list_bytes(value_text)
    elif kind == "ascii":
        try:
            payload = value_text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("Enter ASCII text; non-ASCII characters are not supported.") from exc
        if any(byte < 32 or byte > 126 for byte in payload):
            raise ValueError("Enter printable ASCII text without control characters.")
    else:
        if not value_text.isdecimal():
            raise ValueError("Enter a whole number of seconds.")
        seconds = int(value_text)
        if not 1 <= seconds <= 0xFFFFFFFF:
            raise ValueError("Lease time must be between 1 and 4,294,967,295 seconds.")
        payload = seconds.to_bytes(4, "big")
    return _dhcp_option_result(code, payload)


def _option43_result(suboptions):
    payload = b"".join(bytes((code, len(value))) + value for code, value in suboptions)
    if len(payload) > 255:
        raise ValueError("Option 43 payload exceeds the 255-byte DHCP option limit.")
    return _dhcp_option_result(43, payload, suboptions)


def _ipv4_list_bytes(text):
    addresses = [item for item in re.split(r"[\s,;]+", text.strip()) if item]
    if not addresses:
        raise ValueError("Enter at least one IPv4 address.")
    try:
        return b"".join(ipaddress.IPv4Address(item).packed for item in addresses)
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid IPv4 address: {exc}") from exc


def dhcp_option43_cisco_wlc(addresses_text):
    """Build Cisco lightweight-AP WLC discovery suboption F1."""
    value = _ipv4_list_bytes(addresses_text)
    if len(value) > 252:
        raise ValueError("At most 63 controller addresses fit in one Option 43 payload.")
    return _option43_result([(0xF1, value)])


def dhcp_option43_raw_hex(value_text):
    """Use vendor-documented opaque bytes without adding suboption headers."""
    digits = re.sub(r"[\s:-]", "", value_text.strip())
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", digits):
        raise ValueError("Enter complete hexadecimal byte pairs for the vendor payload.")
    return _dhcp_option_result(43, bytes.fromhex(digits))


def dhcp_option43_tlv(lines_text):
    """Build vendor-defined suboptions from CODE=hex|ascii|ipv4:VALUE lines."""
    suboptions = []
    for line_number, raw_line in enumerate(lines_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"(0[xX][0-9a-fA-F]+|\d+)\s*=\s*(hex|ascii|ipv4)\s*:\s*(.*)",
                             line, re.IGNORECASE)
        if not match:
            raise ValueError(f"Line {line_number}: use CODE=hex|ascii|ipv4:VALUE.")
        code_text, encoding, value_text = match.groups()
        code = int(code_text, 16 if code_text.lower().startswith("0x") else 10)
        if not 1 <= code <= 254:
            raise ValueError(f"Line {line_number}: suboption code must be 1–254 (0 and 255 are reserved).")
        if not value_text.strip():
            raise ValueError(f"Line {line_number}: enter a value.")
        encoding = encoding.lower()
        if encoding == "hex":
            digits = re.sub(r"[\s:-]", "", value_text)
            if not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", digits):
                raise ValueError(f"Line {line_number}: hex value needs complete byte pairs.")
            value = bytes.fromhex(digits)
        elif encoding == "ascii":
            try:
                value = value_text.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError(f"Line {line_number}: ASCII value contains a non-ASCII character.") from exc
        else:
            try:
                value = _ipv4_list_bytes(value_text)
            except ValueError as exc:
                raise ValueError(f"Line {line_number}: {exc}") from exc
        if len(value) > 255:
            raise ValueError(f"Line {line_number}: suboption value exceeds 255 bytes.")
        suboptions.append((code, value))
    if not suboptions:
        raise ValueError("Enter at least one suboption line.")
    return _option43_result(suboptions)


def ipv4_class(address):
    first = int(str(address).split(".")[0])
    if first < 128:
        return "A", 8
    if first < 192:
        return "B", 16
    if first < 224:
        return "C", 24
    if first < 240:
        return "D (multicast)", None
    return "E (reserved)", None


def ipv4_details(address_text, mask_text="24"):
    """Accept CIDR, a prefix, or a dotted mask; retain the supplied host."""
    address_text = address_text.strip()
    if "/" in address_text:
        address_text, mask_text = address_text.split("/", 1)
    address = ipaddress.IPv4Address(address_text.strip())
    mask_text = str(mask_text).strip().lstrip("/")
    if not mask_text:
        raise ValueError("Enter a prefix length or subnet mask.")
    network = ipaddress.IPv4Network(f"{address}/{mask_text}", strict=False)
    prefix = network.prefixlen
    count = network.num_addresses
    if prefix == 32:
        first = last = network.network_address
        usable = 1
    elif prefix == 31:
        first, last = network.network_address, network.broadcast_address
        usable = 2
    else:
        first = network.network_address + 1
        last = network.broadcast_address - 1
        usable = count - 2
    address_class, class_prefix = ipv4_class(address)
    subnet_bits = max(0, prefix - class_prefix) if class_prefix is not None else None
    return {
        "address": address,
        "network": network,
        "class": address_class,
        "prefix": prefix,
        "mask": network.netmask,
        "wildcard": network.hostmask,
        "subnet_bits": subnet_bits,
        "max_subnets": 2 ** subnet_bits if subnet_bits is not None else None,
        "host_bits": 32 - prefix,
        "total": count,
        "usable": usable,
        "first": first,
        "last": last,
        "broadcast": network.broadcast_address,
        "previous": ipaddress.IPv4Address(int(network.network_address) - count)
        if int(network.network_address) >= count else None,
        "next": ipaddress.IPv4Address(int(network.network_address) + count)
        if int(network.network_address) + count < 2 ** 32 else None,
    }


def ipv4_binary(address):
    return " ".join(f"{int(octet):08b}" for octet in str(address).split("."))


def ipv6_details(address_text, prefix_text="64"):
    address_text = address_text.strip()
    if "/" in address_text:
        address_text, prefix_text = address_text.split("/", 1)
    address = ipaddress.IPv6Address(address_text.strip())
    prefix = int(str(prefix_text).strip().lstrip("/"))
    network = ipaddress.IPv6Network((address, prefix), strict=False)
    size = network.num_addresses
    start = network.network_address
    end = ipaddress.IPv6Address(int(start) + size - 1)
    if address.is_unspecified:
        address_type = "unspecified"
    elif address.is_loopback:
        address_type = "loopback"
    elif address.is_multicast:
        address_type = "multicast"
    elif address.is_link_local:
        address_type = "link local"
    elif address in ipaddress.IPv6Network("2001:db8::/32"):
        address_type = "documentation"
    elif address in ipaddress.IPv6Network("fc00::/7"):
        address_type = "unique local"
    elif address.is_private:
        address_type = "non-global"
    else:
        address_type = "global"
    return {
        "address": address,
        "expanded": address.exploded,
        "network": network,
        "prefix": prefix,
        "prefix_mask": network.netmask,
        "host_bits": 128 - prefix,
        "total": size,
        "first": start,
        "last": end,
        "type": address_type,
        "previous": ipaddress.IPv6Address(int(start) - size)
        if int(start) >= size else None,
        "next": ipaddress.IPv6Address(int(start) + size)
        if int(start) + size < 2 ** 128 else None,
    }


def ipv6_subnet_page(network, child_prefix, page=0, page_size=8):
    """Return a bounded page of child networks without enumerating huge ranges."""
    if not isinstance(network, ipaddress.IPv6Network):
        network = ipaddress.IPv6Network(network, strict=False)
    child_prefix = int(child_prefix)
    if not network.prefixlen <= child_prefix <= 128:
        raise ValueError(f"Child prefix must be between /{network.prefixlen} and /128.")
    count = 1 << (child_prefix - network.prefixlen)
    pages = (count + page_size - 1) // page_size
    if not 0 <= page < pages:
        raise ValueError("Subnet page is out of range.")
    size = 1 << (128 - child_prefix)
    first_index = page * page_size
    rows = []
    for index in range(first_index, min(first_index + page_size, count)):
        address = ipaddress.IPv6Address(int(network.network_address) + index * size)
        rows.append((index + 1, ipaddress.IPv6Network((address, child_prefix))))
    return {"count": count, "pages": pages, "page": page, "rows": rows}


def ipv6_binary(address):
    bits = f"{int(address):0128b}"
    return " ".join(bits[i:i + 16] for i in range(0, 128, 16))


def wildcard_details(address_text, wildcard_text, candidate_text=""):
    """Cisco wildcard semantics: 0 bits must match; 1 bits are ignored."""
    address = ipaddress.IPv4Address(address_text.strip())
    wildcard = ipaddress.IPv4Address(wildcard_text.strip())
    mask = ipaddress.IPv4Address((2 ** 32 - 1) ^ int(wildcard))
    base = ipaddress.IPv4Address(int(address) & int(mask))
    upper = ipaddress.IPv4Address(int(base) | int(wildcard))
    candidate = ipaddress.IPv4Address(candidate_text.strip()) if candidate_text.strip() else None
    matched = (int(candidate) & int(mask)) == int(base) if candidate is not None else None
    try:
        prefix = ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
    except ipaddress.NetmaskValueError:
        prefix = None
    return {
        "address": address, "wildcard": wildcard, "mask": mask,
        "base": base, "upper": upper, "count": 2 ** int(wildcard).bit_count(),
        "prefix": prefix, "candidate": candidate, "matched": matched,
    }


def decimal_ip_details(value):
    """Convert IPv4 dotted decimal, unsigned integer, or 0x hexadecimal."""
    value = value.strip()
    if "." in value:
        address = ipaddress.IPv4Address(value)
    elif value.lower().startswith("0x"):
        address = ipaddress.IPv4Address(int(value, 16))
    elif re.fullmatch(r"\d+", value):
        address = ipaddress.IPv4Address(int(value, 10))
    else:
        raise ValueError("Enter an IPv4 address, unsigned integer, or 0x hexadecimal value.")
    return {
        "address": address,
        "integer": int(address),
        "hex": f"0x{int(address):08X}",
        "binary": ipv4_binary(address),
    }


def mac_details(value, vendor_lookup):
    """Normalize one 48-bit MAC address and reuse the app's OUI lookup."""
    value = value.strip()
    if not re.fullmatch(
        r"(?:[0-9a-fA-F]{12}|[0-9a-fA-F]{4}(?:\.[0-9a-fA-F]{4}){2}|"
        r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}|"
        r"[0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})", value,
    ):
        raise ValueError("Enter a complete 12-digit MAC address.")
    raw = re.sub(r"[^0-9a-fA-F]", "", value).upper()
    first_byte = int(raw[:2], 16)
    return {
        "input": value,
        "cisco": ".".join(raw[i:i + 4] for i in range(0, 12, 4)),
        "colon": ":".join(raw[i:i + 2] for i in range(0, 12, 2)),
        "colon_lower": ":".join(raw[i:i + 2] for i in range(0, 12, 2)).lower(),
        "hyphen": "-".join(raw[i:i + 2] for i in range(0, 12, 2)),
        "plain": raw,
        "oui": ":".join(raw[i:i + 2] for i in range(0, 6, 2)),
        "vendor": vendor_lookup(raw) or "Unknown / not in local database",
        "assignment": "Locally administered" if first_byte & 2 else "Universally administered",
        "delivery": "Multicast" if first_byte & 1 else "Unicast",
    }
