"""Sample host, network namespace and Syslog counters into rotating JSONL."""

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from victim_lab.syslog.reader import read_rsyslog_stats


def read_cpu_ticks():
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = [int(value) for value in fields]
    return sum(values), values[3] + values[4]


def read_memory():
    result = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"MemTotal", "MemAvailable"}:
            result[key] = int(value.strip().split()[0]) * 1024
    return result


def read_interfaces():
    result = {}
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, separator, counters = line.partition(":")
        if not separator:
            continue
        values = [int(value) for value in counters.split()]
        result[name.strip()] = {
            "rx_bytes": values[0],
            "rx_packets": values[1],
            "rx_dropped": values[3],
            "tx_bytes": values[8],
            "tx_packets": values[9],
            "tx_dropped": values[11],
        }
    return result


def read_udp_counters():
    lines = Path("/proc/net/snmp").read_text().splitlines()
    for header, values in zip(lines, lines[1:]):
        if header.startswith("Udp:") and values.startswith("Udp:"):
            keys = header.split()[1:]
            numbers = [int(value) for value in values.split()[1:]]
            return dict(zip(keys, numbers))
    return {}


def read_tcp_connections():
    result = {"total": 0, "established": 0}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in Path(path).read_text().splitlines()[1:]:
            fields = line.split()
            result["total"] += 1
            if fields[3] == "01":
                result["established"] += 1
    return result


def read_temperature():
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    return round(int(path.read_text().strip()) / 1000, 2) if path.exists() else None


def sample(previous_cpu, experiment_id, log_path):
    current_cpu = read_cpu_ticks()
    total_delta = current_cpu[0] - previous_cpu[0]
    idle_delta = current_cpu[1] - previous_cpu[1]
    cpu_percent = round(100 * (1 - idle_delta / total_delta), 2) if total_delta > 0 else None
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "cpu_percent": cpu_percent,
        "memory_bytes": read_memory(),
        "temperature_celsius": read_temperature(),
        "interfaces": read_interfaces(),
        "udp": read_udp_counters(),
        "tcp_connections": read_tcp_connections(),
        "disk_free_bytes": shutil.disk_usage(log_path.parent).free,
    }
    try:
        record["syslog"] = read_rsyslog_stats()
    except Exception as exc:
        record["syslog_error"] = str(exc)
    return current_cpu, record


def main():
    interval = float(os.environ.get("COLLECT_INTERVAL", "5"))
    if not 1 <= interval <= 60:
        raise ValueError("COLLECT_INTERVAL must be between 1 and 60 seconds")
    log_path = Path(os.environ.get("METRICS_LOG_PATH", "/var/log/victim-lab/metrics.jsonl"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("victim.metrics")
    logger.setLevel(logging.INFO)
    logger.addHandler(
        RotatingFileHandler(log_path, maxBytes=20 * 1024 * 1024, backupCount=3, encoding="utf-8")
    )
    previous_cpu = read_cpu_ticks()
    experiment_id = os.environ.get("EXPERIMENT_ID", "unlabeled")
    while True:
        time.sleep(interval)
        previous_cpu, record = sample(previous_cpu, experiment_id, log_path)
        logger.info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
