"""Read bounded rsyslog statistics and recent messages for the dashboard."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path("/var/log/victim-lab")
STATS_FILE = LOG_DIR / "rsyslog-stats.log"
MESSAGES_FILE = LOG_DIR / "syslog.jsonl"
METRICS_FILE = LOG_DIR / "metrics.jsonl"
MAX_TAIL_BYTES = 256 * 1024


def _tail_lines(path, max_bytes=MAX_TAIL_BYTES):
    path = Path(path)
    with path.open("rb") as handle:
        handle.seek(0, 2)
        length = handle.tell()
        start = max(0, length - max_bytes)
        handle.seek(start)
        data = handle.read()
    if start:
        data = data.partition(b"\n")[2]
    return data.decode("utf-8", errors="replace").splitlines()


def _json_records(path):
    for line in _tail_lines(path):
        start = line.find("{")
        if start < 0:
            continue
        try:
            value = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield line[:start], value


def _json_objects(path):
    for _, value in _json_records(path):
        yield value


def read_rsyslog_stats(path=STATS_FILE, max_age_seconds=15):
    path = Path(path)
    age = time.time() - path.stat().st_mtime
    if age > max_age_seconds:
        raise RuntimeError("Rsyslog statistics are stale")
    listener = None
    queue = None
    disallowed_total = 0
    snapshot = None
    for prefix, item in _json_records(path):
        if snapshot != prefix:
            snapshot = prefix
            listener = None
            queue = None
            disallowed_total = 0
        if item.get("origin") == "imudp" and str(item.get("name", "")).startswith("lab_syslog("):
            listener = item
        elif item.get("origin") == "imudp" and str(item.get("name", "")).startswith("imudp(w"):
            disallowed_total += int(item.get("disallowed", 0))
        elif item.get("origin") == "core.queue" and item.get("name") in {"main Q", "main queue"}:
            queue = item
    if listener is None:
        raise RuntimeError("Rsyslog UDP listener statistics are missing")
    queue = queue or {}
    return {
        "received_total": int(listener.get("submitted", 0)),
        "disallowed_total": disallowed_total,
        "queue_discarded_total": int(queue.get("discarded.full", 0)) + int(queue.get("discarded.nf", 0)),
        "stats_age_seconds": round(max(0, age), 1),
    }


def _display_text(value, limit):
    value = str(value or "")
    return "".join(character if character.isprintable() else " " for character in value)[:limit]


def recent_messages(path=MESSAGES_FILE, limit=20):
    path = Path(path)
    records = []
    for candidate in (path, Path(str(path) + ".1")):
        try:
            lines = _tail_lines(candidate)
        except FileNotFoundError:
            continue
        legacy_closing_brace = False
        for line in reversed(lines):
            if line.strip() == "}":
                legacy_closing_brace = True
                continue
            candidate = line
            if legacy_closing_brace:
                # Older deployments wrote a trailing comma and the closing brace on
                # a separate line. Read those records without rewriting the log.
                stripped = line.rstrip()
                if stripped.endswith(","):
                    candidate = stripped[:-1] + "}"
                legacy_closing_brace = False
            try:
                item = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            records.append({
                "timestamp_utc": _display_text(item.get("timestamp_utc"), 64),
                "source_ip": _display_text(item.get("source_ip"), 64),
                "hostname": _display_text(item.get("hostname"), 100),
                "app": _display_text(item.get("app"), 100),
                "severity": _display_text(item.get("severity"), 24),
                "message": _display_text(item.get("message"), 500),
            })
            if len(records) >= limit:
                return records
    return records


def _fresh_monitor_samples(path, max_age_seconds=20):
    try:
        samples = list(_json_objects(path))
    except FileNotFoundError:
        return []
    if not samples:
        return []
    try:
        latest = datetime.fromisoformat(samples[-1]["timestamp_utc"])
        if latest.tzinfo is None or (datetime.now(timezone.utc) - latest).total_seconds() > max_age_seconds:
            return []
    except (KeyError, TypeError, ValueError):
        return []
    return samples


def read_rate(path=METRICS_FILE):
    samples = [item for item in _fresh_monitor_samples(path) if isinstance(item.get("syslog"), dict)]
    if len(samples) < 2:
        return None
    before, after = samples[-2:]
    try:
        seconds = (
            datetime.fromisoformat(after["timestamp_utc"])
            - datetime.fromisoformat(before["timestamp_utc"])
        ).total_seconds()
        delta = int(after["syslog"]["received_total"]) - int(before["syslog"]["received_total"])
    except (KeyError, TypeError, ValueError):
        return None
    return round(delta / seconds, 1) if seconds > 0 and delta >= 0 else None


def read_kernel_udp_errors(path=METRICS_FILE):
    samples = _fresh_monitor_samples(path)
    if not samples:
        return None
    try:
        return int(samples[-1]["udp"]["InErrors"])
    except (KeyError, TypeError, ValueError):
        return None


def dashboard_status():
    stats = read_rsyslog_stats()
    try:
        messages = recent_messages()
    except OSError:
        messages = []
    return {
        **stats,
        "status": "online",
        "rate_per_second": read_rate(),
        "kernel_udp_errors": read_kernel_udp_errors(),
        "messages": messages,
    }
