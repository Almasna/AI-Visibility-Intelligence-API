from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit


DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def normalize_domain(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Domain must not be empty.")

    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Domain is invalid.")

    hostname = hostname.rstrip(".").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Domain is invalid.") from exc

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not accepted as business domains.")

    labels = hostname.split(".")
    if (
        len(labels) < 2
        or len(hostname) > 253
        or any(not DOMAIN_LABEL.fullmatch(label) for label in labels)
        or len(labels[-1]) < 2
    ):
        raise ValueError("Domain is invalid.")
    return hostname


def domains_match(source: str, target: str) -> bool:
    try:
        source_domain = normalize_domain(source)
        target_domain = normalize_domain(target)
    except ValueError:
        return False
    return source_domain == target_domain or source_domain.endswith(f".{target_domain}")
