"""Search a bundled, read-only snapshot of IANA's service/port registry."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path


REGISTRY_DATE = "2026-10-20"
REGISTRY_FILE = Path(__file__).resolve().parent / "data" / "iana-service-names-port-numbers.csv"
RESULT_LIMIT = 200

# Editorial search terms for common engineering questions; official IANA names
# and descriptions remain separate in the displayed results.
COMMON_USES = {
    20: "FTP data transfer", 21: "FTP file transfer control", 22: "SSH secure remote login",
    23: "Telnet remote login", 25: "SMTP email transfer", 53: "DNS domain name resolution",
    67: "DHCP server", 68: "DHCP client", 69: "TFTP file transfer",
    80: "HTTP web browsing", 110: "POP3 email", 123: "NTP time synchronization",
    143: "IMAP email", 161: "SNMP network monitoring", 162: "SNMP traps",
    389: "LDAP directory", 443: "HTTPS secure web TLS", 445: "SMB Windows file sharing",
    514: "Syslog logging", 587: "SMTP email submission", 636: "LDAPS secure directory",
    993: "IMAPS secure email", 995: "POP3S secure email",
    1433: "Microsoft SQL Server database", 3306: "MySQL database",
    3389: "RDP Remote Desktop", 5060: "SIP VoIP signaling",
    5061: "SIP secure VoIP TLS", 5432: "PostgreSQL database",
    5900: "VNC remote desktop", 8080: "Alternate HTTP web proxy",
    8443: "Alternate HTTPS secure web",
}


@dataclass(frozen=True)
class PortRecord:
    port: str
    first: int
    last: int
    protocol: str
    service: str
    description: str
    common_use: str
    reference: str


def load_port_registry(path=REGISTRY_FILE):
    records = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            port = (row.get("Port Number") or "").strip()
            if re.fullmatch(r"\d{1,5}", port):
                first = last = int(port)
            else:
                match = re.fullmatch(r"(\d{1,5})-(\d{1,5})", port)
                if not match:
                    continue
                first, last = map(int, match.groups())
            if first > last or last > 65535:
                continue
            records.append(PortRecord(
                port=port, first=first, last=last,
                protocol=(row.get("Transport Protocol") or "").strip().lower(),
                service=(row.get("Service Name") or "").strip(),
                description=(row.get("Description") or "").strip(),
                common_use=COMMON_USES.get(first, "") if first == last else "",
                reference=(row.get("Reference") or "").strip(),
            ))
    return tuple(records)


def search_ports(records, query="", protocol="All", limit=RESULT_LIMIT):
    """Search exact port/range membership or all words in name, use, description."""
    if protocol not in {"All", "tcp", "udp", "sctp", "dccp"}:
        raise ValueError("Choose a supported transport protocol.")
    query = query.strip()
    number = re.fullmatch(r"(\d{1,5})(?:\s*/\s*(tcp|udp|sctp|dccp))?", query, re.I)
    inline_protocol = number.group(2).lower() if number and number.group(2) else None
    port_number = int(number.group(1)) if number else None
    if port_number is not None and port_number > 65535:
        raise ValueError("Port numbers range from 0 through 65535.")
    selected_protocol = inline_protocol or protocol
    terms = query.casefold().split()
    found = []
    for record in records:
        if selected_protocol != "All" and record.protocol != selected_protocol:
            continue
        if port_number is not None:
            if not record.first <= port_number <= record.last:
                continue
        elif query:
            haystack = " ".join((record.service, record.description,
                                 record.common_use, record.reference)).casefold()
            if not all(term in haystack for term in terms):
                continue
        elif record.first != record.last or record.first not in COMMON_USES:
            continue
        found.append(record)

    def rank(record):
        if port_number is not None:
            match_rank = 0 if record.first == record.last == port_number else 1
        elif not query:
            match_rank = 0
        else:
            search = query.casefold()
            match_rank = (0 if record.service.casefold() == search else
                          1 if search in record.common_use.casefold() else
                          2 if record.service.casefold().startswith(search) else 3)
        return (match_rank, record.first, record.last, record.protocol != "tcp", record.protocol)

    found.sort(key=rank)
    return found[:limit], len(found)
