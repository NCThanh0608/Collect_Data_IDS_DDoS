"""Send a single RFC 5424 UDP Syslog message for dashboard verification."""

import socket
import uuid
from datetime import datetime, timezone


def send_probe(host, port=514):
    probe_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    message = f"<134>1 {timestamp} victim-web lab-probe - - - VICTIM_LAB_PROBE id={probe_id}"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(message.encode("ascii"), (host, port))
    return probe_id
