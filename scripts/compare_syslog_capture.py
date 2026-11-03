"""Compare router/victim UDP payloads and count rsyslog-written receipts.

Packet matching is exact at the UDP payload level. Without an ID supplied by
the sender, rsyslog records can only be compared by count and receive window.
"""

import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from scapy.all import IP, IPv6, IPv6ExtHdrFragment, UDP, PcapReader
except ImportError as exc:
    raise SystemExit("Install analysis dependencies: python -m pip install -r requirements-analysis.txt") from exc


LOG_NAME = re.compile(r"syslog\.jsonl(?:\.(?:[1-9]\d*|\d{8}T\d{6}Z\.\d+\.\d+))?\Z")
RECEIVED_AT = re.compile(rb'"received_at_utc":"([^"\\]+)"')
SOURCE_IP = re.compile(rb'"source_ip":"([^"\\]+)"')
SOURCE_PORT = re.compile(rb'"source_port":"([0-9]+)"')


def read_capture(path, destination_ip, database, side):
    """Count complete UDP payloads on disk without decoding their bytes."""
    if side not in {"router", "victim"}:
        raise ValueError("Capture side must be router or victim")
    insert = (
        f"INSERT INTO payloads (source_ip, source_port, digest, payload_bytes, {side}) "
        f"VALUES (?, ?, ?, ?, 1) "
        f"ON CONFLICT(source_ip, source_port, digest, payload_bytes) DO UPDATE SET {side}={side}+1"
    )
    total = 0
    first = None
    last = None
    incomplete = 0
    fragmented = 0
    with PcapReader(str(path)) as packets, database:
        for packet in packets:
            network = packet[IP] if IP in packet else packet[IPv6] if IPv6 in packet else None
            if network is None or UDP not in packet:
                continue
            udp = packet[UDP]
            if int(udp.dport) != 514 or network.dst != destination_ip:
                continue
            if (IP in packet and (bool(packet[IP].flags.MF) or packet[IP].frag)) or \
                    IPv6ExtHdrFragment in packet:
                fragmented += 1
                continue
            payload = bytes(udp.payload)
            if udp.len is None or int(udp.len) - 8 != len(payload):
                incomplete += 1
                continue
            database.execute(insert, (
                network.src, int(udp.sport), hashlib.sha256(payload).digest(), len(payload)
            ))
            if side == "victim":
                database.execute(
                    "INSERT OR IGNORE INTO sources (ip, port) VALUES (?, ?)",
                    (network.src, int(udp.sport)),
                )
            captured_at = float(packet.time)
            first = captured_at if first is None else min(first, captured_at)
            last = captured_at if last is None else max(last, captured_at)
            total += 1
    return {"packets": total, "first": first, "last": last,
            "issues": {"incomplete": incomplete, "fragmented": fragmented}}


def _log_paths(log_dir, window_start):
    paths = []
    for path in Path(log_dir).iterdir():
        if not LOG_NAME.fullmatch(path.name):
            continue
        try:
            if path.name == "syslog.jsonl" or path.stat().st_mtime >= window_start:
                paths.append(path)
        except FileNotFoundError:
            continue
    return sorted(paths)


def count_rsyslog_receipts(log_dir, start, end, database):
    """Count receipt metadata as bytes; arbitrary MSG bytes need no decoding."""
    written = 0
    missing_receipt_time = 0
    files = _log_paths(log_dir, start)
    for path in files:
        try:
            with path.open("rb") as handle:
                for line in handle:
                    received = RECEIVED_AT.search(line)
                    if not received:
                        missing_receipt_time += 1
                        continue
                    try:
                        stamp = received.group(1).decode("ascii").replace("Z", "+00:00")
                        parsed = datetime.fromisoformat(stamp)
                        if parsed.tzinfo is None:
                            raise ValueError("Timestamp has no timezone")
                        when = parsed.timestamp()
                    except (UnicodeDecodeError, ValueError):
                        missing_receipt_time += 1
                        continue
                    if not start <= when <= end:
                        continue
                    source_ip = SOURCE_IP.search(line)
                    source_port = SOURCE_PORT.search(line)
                    if source_ip and source_port:
                        source = (source_ip.group(1).decode("ascii"), int(source_port.group(1)))
                        if database.execute(
                            "SELECT 1 FROM sources WHERE ip=? AND port=?", source
                        ).fetchone():
                            written += 1
        except FileNotFoundError:
            # A live rsyslog rotation can move a file after the directory scan.
            continue
    return {
        "written_in_window": written,
        "log_files_scanned": len(files),
        "lines_without_receipt_time": missing_receipt_time,
    }


def compare(router_path, victim_path, log_dir, destination_ip, margin_seconds=2):
    with TemporaryDirectory(prefix="victim-syslog-compare-") as directory:
        with closing(sqlite3.connect(Path(directory) / "capture.sqlite")) as database:
            database.execute("CREATE TABLE payloads (source_ip TEXT NOT NULL, "
                             "source_port INTEGER NOT NULL, digest BLOB NOT NULL, "
                             "payload_bytes INTEGER NOT NULL, "
                             "router INTEGER NOT NULL DEFAULT 0, victim INTEGER NOT NULL DEFAULT 0, "
                             "PRIMARY KEY (source_ip, source_port, digest, payload_bytes)) WITHOUT ROWID")
            database.execute("CREATE TABLE sources (ip TEXT NOT NULL, port INTEGER NOT NULL, "
                             "PRIMARY KEY (ip, port)) WITHOUT ROWID")
            router = read_capture(router_path, destination_ip, database, "router")
            victim = read_capture(victim_path, destination_ip, database, "victim")
            window_start = victim["first"]
            window_end = victim["last"]
            receipts = (
                count_rsyslog_receipts(
                    log_dir, window_start - margin_seconds, window_end + margin_seconds, database
                )
                if window_start is not None else {
                    "written_in_window": 0,
                    "log_files_scanned": 0,
                    "lines_without_receipt_time": 0,
                }
            )
            matched, router_only, victim_only = database.execute(
                "SELECT COALESCE(SUM(MIN(router, victim)), 0), "
                "COALESCE(SUM(MAX(router - victim, 0)), 0), "
                "COALESCE(SUM(MAX(victim - router, 0)), 0) FROM payloads"
            ).fetchone()
            router_only_payloads = [
                {"source_ip": source_ip, "source_port": source_port,
                 "bytes": length, "sha256": digest.hex(), "count": count}
                for source_ip, source_port, digest, length, count in database.execute(
                    "SELECT source_ip, source_port, digest, payload_bytes, router - victim AS missing "
                    "FROM payloads WHERE router > victim ORDER BY missing DESC LIMIT 20"
                )
            ]
            victim_only_payloads = [
                {"source_ip": source_ip, "source_port": source_port,
                 "bytes": length, "sha256": digest.hex(), "count": count}
                for source_ip, source_port, digest, length, count in database.execute(
                    "SELECT source_ip, source_port, digest, payload_bytes, victim - router AS extra "
                    "FROM payloads WHERE victim > router ORDER BY extra DESC LIMIT 20"
                )
            ]
            return {
                "router_packets": router["packets"],
                "victim_packets": victim["packets"],
                "payload_matches": matched,
                "router_only": router_only,
                "victim_only": victim_only,
                "router_capture_issues": router["issues"],
                "victim_capture_issues": victim["issues"],
                "rsyslog": receipts,
                "receipt_window_utc": None if window_start is None else {
                    "start": datetime.fromtimestamp(window_start - margin_seconds, timezone.utc).isoformat(),
                    "end": datetime.fromtimestamp(window_end + margin_seconds, timezone.utc).isoformat(),
                },
                "victim_minus_rsyslog_count": victim["packets"] - receipts["written_in_window"],
                "router_only_payloads": router_only_payloads,
                "victim_only_payloads": victim_only_payloads,
                "capture_complete": not any(router["issues"].values()) and not any(victim["issues"].values()),
                "note": "PCAP matches use source IP/port and exact payload hash; rsyslog comparison is count-only without a sender ID.",
            }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router", type=Path, required=True, help="PCAP from router egress")
    parser.add_argument("--victim", type=Path, required=True, help="PCAP from victim ingress")
    parser.add_argument("--log-dir", type=Path, required=True, help="Directory with syslog.jsonl files")
    parser.add_argument("--dst-ip", default="10.20.0.2", help="Victim destination IP")
    parser.add_argument("--margin-seconds", type=float, default=2,
                        help="Time margin around victim PCAP for rsyslog receipts")
    args = parser.parse_args(argv)
    if not math.isfinite(args.margin_seconds) or args.margin_seconds < 0:
        parser.error("--margin-seconds must be a finite nonnegative number")
    try:
        report = compare(args.router, args.victim, args.log_dir, args.dst_ip, args.margin_seconds)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
