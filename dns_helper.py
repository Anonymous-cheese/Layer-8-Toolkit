"""Offline DNS record formatting and reverse-name helpers (no lookups)."""

import ipaddress
import re


RECORD_USES = {
    "A": "IPv4 address",
    "AAAA": "IPv6 address",
    "CNAME": "Alias to another DNS name",
    "MX": "Mail exchanger with preference",
    "TXT": "Text, including SPF and verification values",
    "SRV": "Service location with priority, weight, and port",
    "PTR": "Reverse-DNS pointer",
    "NS": "Authoritative name server",
    "CAA": "Certificate authority authorization",
}
RECORD_TYPES = tuple(RECORD_USES)
NAME_LABEL = re.compile(r"[A-Za-z0-9_-]{1,63}\Z")


def _number(value, label, maximum):
    text = str(value).strip()
    if not text.isdecimal():
        raise ValueError(f"{label} must be a whole number from 0 to {maximum:,}.")
    number = int(text)
    if number > maximum:
        raise ValueError(f"{label} must be a whole number from 0 to {maximum:,}.")
    return number


def _name(value, label, absolute=False):
    name = str(value).strip()
    if name == "@" and not absolute:
        return name
    without_dot = name.rstrip(".")
    if not without_dot or len(without_dot.encode("ascii", errors="ignore")) != len(without_dot):
        raise ValueError(f"{label} needs an ASCII DNS name.")
    if len(without_dot) > 253 or any(
            not (part == "*" and index == 0) and not NAME_LABEL.fullmatch(part)
            for index, part in enumerate(without_dot.split("."))):
        raise ValueError(f"{label} has an invalid DNS label.")
    if name.endswith(".."):
        raise ValueError(f"{label} has an invalid DNS label.")
    return without_dot + "." if absolute else name


def _quoted(value):
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Text values cannot contain control characters.")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _txt_chunks(value):
    if not value:
        raise ValueError("Enter a TXT value.")
    chunks = []
    chunk = ""
    size = 0
    for char in value:
        encoded = len(char.encode("utf-8"))
        if size + encoded > 255:
            chunks.append(chunk)
            chunk, size = "", 0
        chunk += char
        size += encoded
    if chunk:
        chunks.append(chunk)
    return " ".join(_quoted(item) for item in chunks)


def ttl_display(value):
    seconds = _number(value, "TTL", 2_147_483_647)
    if seconds == 0:
        return "0 seconds (do not cache)"
    units = (("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1))
    parts = []
    for name, unit in units:
        amount, seconds = divmod(seconds, unit)
        if amount:
            parts.append(f"{amount} {name}{'' if amount == 1 else 's'}")
    return ", ".join(parts)


def build_dns_record(owner, record_type, ttl, value, *, priority=0, weight=0,
                     port=0, caa_flags=0, caa_tag="issue"):
    """Return a copy-ready IN-class zone-file record with explicit TTL."""
    owner = _name(owner, "Owner")
    record_type = str(record_type).upper().strip()
    if record_type not in RECORD_USES:
        raise ValueError("Choose a supported DNS record type.")
    ttl = _number(ttl, "TTL", 2_147_483_647)
    value = str(value).strip()
    if record_type == "A":
        try:
            data = str(ipaddress.IPv4Address(value))
        except ipaddress.AddressValueError as error:
            raise ValueError("A records need an IPv4 address.") from error
    elif record_type == "AAAA":
        try:
            data = str(ipaddress.IPv6Address(value))
        except ipaddress.AddressValueError as error:
            raise ValueError("AAAA records need an IPv6 address.") from error
    elif record_type in {"CNAME", "NS", "PTR"}:
        data = _name(value, "Target", absolute=True)
    elif record_type == "MX":
        data = f"{_number(priority, 'Priority', 65535)} {_name(value, 'Mail host', absolute=True)}"
    elif record_type == "SRV":
        data = (f"{_number(priority, 'Priority', 65535)} "
                f"{_number(weight, 'Weight', 65535)} "
                f"{_number(port, 'Port', 65535)} "
                f"{_name(value, 'Target', absolute=True)}")
    elif record_type == "TXT":
        data = _txt_chunks(value)
    else:
        flags = _number(caa_flags, "CAA flags", 255)
        if flags not in (0, 128):
            raise ValueError("CAA flags should be 0 or 128; other bits are reserved.")
        tag = str(caa_tag).strip().lower()
        if tag not in {"issue", "issuewild", "iodef"}:
            raise ValueError("Choose issue, issuewild, or iodef for the CAA tag.")
        if not value:
            raise ValueError("Enter a CAA value.")
        data = f"{flags} {tag} {_quoted(value)}"
    return f"{owner} {ttl} IN {record_type} {data}"


def reverse_ptr_owner(address):
    try:
        return ipaddress.ip_address(str(address).strip()).reverse_pointer + "."
    except ValueError as error:
        raise ValueError("Enter one IPv4 or IPv6 address for the PTR owner.") from error
