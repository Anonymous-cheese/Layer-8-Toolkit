"""Offline DHCPv4 Option 121 classless-route encoding and decoding.

RFC 3442 encodes each route as a prefix width, the significant network
octets, and a four-byte IPv4 router. RFC 3396 concatenates long options.
"""

import ipaddress
import re


OPTION_CODE = 121
MAX_PAYLOAD_BYTES = 4096


def _parse_hex(text):
    digits = re.sub(r"[\s:,\-]", "", text.strip())
    if digits.lower().startswith("0x"):
        digits = digits[2:]
    if not digits or len(digits) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", digits):
        raise ValueError("Enter complete hexadecimal byte pairs (spaces, colons, and hyphens are allowed).")
    return bytes.fromhex(digits)


def _decode_routes(payload):
    if not payload:
        raise ValueError("Option 121 needs at least one route.")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"Option 121 value exceeds the {MAX_PAYLOAD_BYTES}-byte preview limit.")
    routes = []
    warnings = []
    position = 0
    while position < len(payload):
        route_number = len(routes) + 1
        prefix = payload[position]
        position += 1
        if prefix > 32:
            raise ValueError(f"Route {route_number}: prefix length {prefix} is outside 0–32.")
        network_octets = (prefix + 7) // 8
        if len(payload) - position < network_octets + 4:
            raise ValueError(f"Route {route_number}: incomplete destination or four-byte router.")
        significant = payload[position:position + network_octets]
        position += network_octets
        router_bytes = payload[position:position + 4]
        position += 4
        raw_address = ipaddress.IPv4Address(significant.ljust(4, b"\x00"))
        network = ipaddress.IPv4Network((raw_address, prefix), strict=False)
        if raw_address != network.network_address:
            warnings.append(f"Route {route_number}: non-network host bits were zeroed for display.")
        routes.append({
            "destination": str(network),
            "gateway": str(ipaddress.IPv4Address(router_bytes)),
            "prefix": prefix,
        })
    return routes, warnings


def _wire_chunks(payload):
    return b"".join(bytes((OPTION_CODE, len(chunk))) + chunk
                    for offset in range(0, len(payload), 255)
                    if (chunk := payload[offset:offset + 255]))


def _result(payload, wire=None, segments=None):
    routes, warnings = _decode_routes(payload)
    wire = wire if wire is not None else _wire_chunks(payload)
    return {
        "code": OPTION_CODE,
        "hex": payload.hex(),
        "wire_hex": wire.hex(),
        "length": len(payload),
        "segments": segments if segments is not None else (len(payload) + 254) // 255,
        "routes": routes,
        "warnings": warnings,
        "suboptions": [],
    }


def encode_option121(routes_text):
    """Encode one CIDR and IPv4 gateway per line, preserving route order."""
    payload = bytearray()
    for line_number, raw_line in enumerate(routes_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 3 and parts[1].lower() == "via":
            parts = [parts[0], parts[2]]
        if len(parts) != 2:
            raise ValueError(f"Line {line_number}: use DESTINATION/PREFIX GATEWAY, one route per line.")
        try:
            network = ipaddress.IPv4Network(parts[0], strict=True)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
            raise ValueError(f"Line {line_number}: enter a canonical IPv4 CIDR destination (host bits must be zero).") from exc
        try:
            router = ipaddress.IPv4Address(parts[1])
        except ipaddress.AddressValueError as exc:
            raise ValueError(f"Line {line_number}: enter an IPv4 gateway address.") from exc
        significant_count = (network.prefixlen + 7) // 8
        payload.extend(bytes((network.prefixlen,)) + network.network_address.packed[:significant_count]
                       + router.packed)
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Option 121 value exceeds the {MAX_PAYLOAD_BYTES}-byte preview limit.")
    if not payload:
        raise ValueError("Enter at least one destination and gateway route.")
    return _result(bytes(payload))


def decode_option121(hex_text, *, on_wire=False):
    """Decode value hex or concatenated Option 121 TLVs, preserving input bytes."""
    data = _parse_hex(hex_text)
    if not on_wire:
        return _result(data)
    payload = bytearray()
    position = 0
    segments = 0
    while position < len(data):
        if len(data) - position < 2:
            raise ValueError("On-wire hex ends before an Option 121 length byte.")
        code, length = data[position:position + 2]
        position += 2
        if code != OPTION_CODE:
            raise ValueError(f"Expected Option 121 (0x79), found option {code}.")
        if length == 0 or len(data) - position < length:
            raise ValueError("On-wire Option 121 has an empty or truncated value.")
        payload.extend(data[position:position + length])
        position += length
        segments += 1
    return _result(bytes(payload), wire=data, segments=segments)
