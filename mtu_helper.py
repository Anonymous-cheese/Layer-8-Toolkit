"""Conservative, offline MTU and common encapsulation arithmetic."""


TUNNEL_OVERHEAD = {
    "None": 0,
    "GRE over IPv4": 24,       # 20-byte outer IPv4 + 4-byte base GRE
    "GRE over IPv6": 44,       # 40-byte outer IPv6 + 4-byte base GRE
    "VXLAN over IPv4": 50,     # 20 IPv4 + 8 UDP + 8 VXLAN + 14 inner Ethernet
    "VXLAN over IPv6": 70,     # 40 IPv6 + 8 UDP + 8 VXLAN + 14 inner Ethernet
}


def calculate_mtu(ethernet_payload, *, pppoe=False, vlan_tags=0,
                  tunnel="None", inner_family="IPv4"):
    """Budget inner L3 MTU from an Ethernet payload limit.

    Header sizes are base/minimum sizes; tunnel keys, checksums, optional
    headers, IP options, IPv6 extensions, and TCP options are excluded.
    """
    if isinstance(ethernet_payload, bool):
        raise ValueError("Ethernet payload budget must be 68–65,535 bytes.")
    try:
        budget = int(str(ethernet_payload).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("Ethernet payload budget must be 68–65,535 bytes.") from error
    if str(ethernet_payload).strip() != str(budget) or not 68 <= budget <= 65535:
        raise ValueError("Ethernet payload budget must be 68–65,535 bytes.")
    if type(vlan_tags) is not int or vlan_tags not in (0, 1, 2):
        raise ValueError("Select 0, 1, or 2 VLAN tags.")
    if tunnel not in TUNNEL_OVERHEAD:
        raise ValueError("Choose a supported tunnel.")
    if inner_family not in ("IPv4", "IPv6"):
        raise ValueError("Choose IPv4 or IPv6 for the inner packet.")

    pppoe_bytes = 8 if pppoe else 0
    underlay_ip_mtu = budget - pppoe_bytes
    tunnel_bytes = TUNNEL_OVERHEAD[tunnel]
    inner_ip_mtu = underlay_ip_mtu - tunnel_bytes
    ip_header = 20 if inner_family == "IPv4" else 40
    if inner_ip_mtu <= ip_header + 20:
        raise ValueError("The chosen overhead leaves no room for an IP/TCP payload.")
    warnings = []
    if inner_family == "IPv6" and inner_ip_mtu < 1280:
        warnings.append("Below the IPv6 minimum link MTU of 1,280 bytes; do not use this as a normal IPv6 path MTU.")
    return {
        "ethernet_payload": budget,
        "pppoe_bytes": pppoe_bytes,
        "vlan_tags": vlan_tags,
        "vlan_wire_bytes": 4 * vlan_tags,
        "tunnel": tunnel,
        "tunnel_bytes": tunnel_bytes,
        "underlay_ip_mtu": underlay_ip_mtu,
        "inner_family": inner_family,
        "inner_ip_mtu": inner_ip_mtu,
        "ip_header": ip_header,
        "tcp_mss": inner_ip_mtu - ip_header - 20,
        "udp_payload": inner_ip_mtu - ip_header - 8,
        "ethernet_frame_bytes": budget + 14 + 4 * vlan_tags + 4,
        "warnings": warnings,
    }


def mtu_summary(result):
    lines = [
        f"Ethernet payload budget: {result['ethernet_payload']} bytes",
        f"PPPoE/PPP overhead: {result['pppoe_bytes']} bytes",
        f"Underlay IP MTU: {result['underlay_ip_mtu']} bytes",
        f"Tunnel: {result['tunnel']} ({result['tunnel_bytes']} bytes)",
        f"Inner {result['inner_family']} MTU: {result['inner_ip_mtu']} bytes",
        f"TCP MSS (base headers): {result['tcp_mss']} bytes",
        f"UDP data (base headers): {result['udp_payload']} bytes",
        f"VLAN tag wire overhead: {result['vlan_wire_bytes']} bytes",
        f"Ethernet frame, including FCS: {result['ethernet_frame_bytes']} bytes",
    ]
    lines.extend(result["warnings"])
    return "\n".join(lines)
