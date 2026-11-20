"""
Defensive security guards for external read-only database connectors:
- SSRF host/IP validation (blocks loopback, RFC1918 private, link-local, AWS IMDS 169.254.169.254)
- Strict read-only SQL validation (blocks DML/DDL, stacked queries, COPY, and catalog credential tables)
"""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Tuple

BLOCKED_SQL_KEYWORDS = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|EXECUTE|EXEC|"
    r"CALL|DO|VACUUM|REINDEX|CLUSTER|LOCK|MERGE|REPLACE|SET\s+ROLE|SET\s+SESSION|"
    r"PG_SLEEP|LO_IMPORT|LO_EXPORT|DBLINK|PG_READ_FILE|PG_LS_DIR"
    r")\b",
    re.IGNORECASE,
)

BLOCKED_SYSTEM_TABLES = re.compile(
    r"\b(pg_shadow|pg_authid|pg_user|pg_roles|pg_stat_activity|mysql\.user|information_schema\.user_privileges)\b",
    re.IGNORECASE,
)


def validate_db_host_ssrf(hostname: str) -> Tuple[bool, str]:
    """Validate that a user-supplied database host does not resolve to private/internal/metadata IPs."""
    host = (hostname or "").strip().lower()
    if not host:
        return False, "Database hostname is required."
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
        return False, f"Blocked internal hostname: {host}"

    def _is_forbidden_ip(ip_str: str) -> bool:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or ip_str == "169.254.169.254"
        )

    # Direct IP literal check
    try:
        if _is_forbidden_ip(host):
            return False, f"Blocked private/internal IP address: {host}"
        return True, "ok"
    except ValueError:
        pass

    # DNS resolution check (all A/AAAA records must be public)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"Could not resolve hostname: {host}"

    for info in infos:
        resolved_ip = info[4][0]
        if _is_forbidden_ip(resolved_ip):
            return False, f"Hostname {host} resolves to forbidden internal IP {resolved_ip}"

    return True, "ok"


def validate_readonly_sql(sql: str, max_length: int = 4000) -> Tuple[bool, str]:
    """Validate that an AI-generated or user-supplied SQL query is strictly single-statement read-only SELECT."""
    cleaned = (sql or "").strip()
    if not cleaned:
        return False, "SQL query cannot be empty."
    if len(cleaned) > max_length:
        return False, f"SQL query exceeds maximum length of {max_length} characters."

    # Strip SQL comments before keyword inspection
    no_comments = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    no_comments = re.sub(r"--[^\n]*", " ", no_comments).strip()

    # Reject stacked queries (semicolon anywhere except optional trailing semicolon)
    body = no_comments[:-1] if no_comments.endswith(";") else no_comments
    if ";" in body:
        return False, "Stacked SQL queries are not allowed."

    if not re.match(r"^(SELECT|WITH)\b", body, flags=re.IGNORECASE):
        return False, "Only read-only SELECT / WITH queries are permitted."

    if BLOCKED_SQL_KEYWORDS.search(body):
        return False, "Query contains forbidden write, DDL, or system-execution keywords."

    if BLOCKED_SYSTEM_TABLES.search(body):
        return False, "Access to database credential or system catalog tables is forbidden."

    return True, "ok"
