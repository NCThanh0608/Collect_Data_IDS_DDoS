import io
import json
import os
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["FLASK_SECRET_KEY"] = "test-only-secret"
os.environ["VICTIM_USERNAME"] = "labuser"
os.environ["VICTIM_PASSWORD_HASH"] = generate_password_hash("correct-password")
os.environ["EXPERIMENT_ID"] = "test-run"

from network_config import addresses  # noqa: E402
from victim_lab.http.app import access_logger, app  # noqa: E402
from victim_lab.monitor.collect import sample  # noqa: E402
from victim_lab.syslog.probe import send_probe  # noqa: E402
from victim_lab.syslog.reader import (  # noqa: E402
    read_kernel_udp_errors,
    read_rate,
    read_rsyslog_stats,
    recent_messages,
)


class HttpTests(unittest.TestCase):
    def test_health_and_login_flow(self):
        with app.test_client() as client:
            self.assertEqual(client.get("/healthz").json["status"], "ok")
            self.assertEqual(client.get("/dashboard").status_code, 302)
            self.assertEqual(
                client.post("/login", data={"username": "labuser", "password": "wrong"}).status_code,
                200,
            )
            response = client.post(
                "/login", data={"username": "labuser", "password": "correct-password"}
            )
            self.assertEqual(response.status_code, 302)
            page = client.get("/dashboard").get_data(as_text=True)
            self.assertIn("Syslog", page)
            self.assertIn("HTTP", page)
            self.assertEqual(client.post("/logout").status_code, 302)

    def test_access_log_does_not_include_query_or_password(self):
        stream = io.StringIO()
        handler = access_logger.handlers[0]
        previous_stream = handler.setStream(stream)
        try:
            with app.test_client() as client:
                response = client.post(
                    "/login?token=hidden-token",
                    data={"username": "labuser", "password": "secret-in-body"},
                )
            entry = json.loads(stream.getvalue().splitlines()[-1])
            self.assertEqual(entry["route"], "/login")
            self.assertEqual(response.headers["X-Request-ID"], entry["request_id"])
            self.assertNotIn("hidden-token", stream.getvalue())
            self.assertNotIn("secret-in-body", stream.getvalue())
        finally:
            handler.setStream(previous_stream)


class SyslogDashboardTests(unittest.TestCase):
    def test_status_and_probe_require_login(self):
        with app.test_client() as client:
            self.assertEqual(client.get("/api/syslog/status").status_code, 401)
            self.assertEqual(client.post("/api/syslog/probe").status_code, 401)
            client.post("/login", data={"username": "labuser", "password": "correct-password"})
            with patch("victim_lab.http.app.dashboard_status", return_value={"received_total": 4}), \
                 patch("victim_lab.http.app.send_probe", return_value="abc123"):
                self.assertEqual(client.get("/api/syslog/status").json["received_total"], 4)
                self.assertEqual(client.post("/api/syslog/probe").json["probe_id"], "abc123")

    def test_stale_stats_report_unavailable(self):
        with app.test_client() as client:
            client.post("/login", data={"username": "labuser", "password": "correct-password"})
            with patch("victim_lab.http.app.dashboard_status", side_effect=RuntimeError("stale")):
                self.assertEqual(client.get("/api/syslog/status").status_code, 503)


class SyslogReaderTests(unittest.TestCase):
    def test_stats_and_recent_messages_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stats = root / "stats.log"
            stats.write_text("\n".join([
                'old: {"name":"lab_syslog(10.20.0.2:514)","origin":"imudp","submitted":8}',
                'old: {"name":"imudp(w0)","origin":"imudp","disallowed":9}',
                'new: {"name":"lab_syslog(10.20.0.2:514)","origin":"imudp","submitted":12}',
                'new: {"name":"imudp(w0)","origin":"imudp","disallowed":2}',
                'new: {"name":"imudp(w1)","origin":"imudp","disallowed":1}',
                'new: {"name":"main Q","origin":"core.queue","discarded.full":3,"discarded.nf":1}',
            ]), encoding="utf-8")
            result = read_rsyslog_stats(stats)
            self.assertEqual(result["received_total"], 12)
            self.assertEqual(result["disallowed_total"], 3)
            self.assertEqual(result["queue_discarded_total"], 4)

            logs = root / "syslog.jsonl"
            logs.write_text(json.dumps({
                "timestamp_utc": "2026-10-27T00:00:00Z",
                "source_ip": "192.168.1.174",
                "message": "<script>alert(1)</script>\n" + "x" * 1000,
            }) + "\n", encoding="utf-8")
            messages = recent_messages(logs)
            self.assertEqual(len(messages), 1)
            self.assertIn("<script>", messages[0]["message"])
            self.assertNotIn("\n", messages[0]["message"])
            self.assertLessEqual(len(messages[0]["message"]), 500)

    def test_rate_and_kernel_errors_expire_with_monitor_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            metrics = Path(directory) / "metrics.jsonl"
            now = datetime.now(timezone.utc)
            records = [
                {"timestamp_utc": (now - timedelta(seconds=5)).isoformat(),
                 "syslog": {"received_total": 10}, "udp": {"InErrors": 2}},
                {"timestamp_utc": now.isoformat(),
                 "syslog": {"received_total": 20}, "udp": {"InErrors": 4}},
            ]
            metrics.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
            self.assertEqual(read_rate(metrics), 2.0)
            self.assertEqual(read_kernel_udp_errors(metrics), 4)
            records[-1]["timestamp_utc"] = (now - timedelta(seconds=30)).isoformat()
            metrics.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
            self.assertIsNone(read_rate(metrics))
            self.assertIsNone(read_kernel_udp_errors(metrics))

    def test_probe_sends_real_udp_datagram(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            probe_id = send_probe("127.0.0.1", receiver.getsockname()[1])
            payload, _ = receiver.recvfrom(2048)
        self.assertIn(probe_id.encode("ascii"), payload)
        self.assertTrue(payload.startswith(b"<134>1 "))

    def test_recent_messages_recovers_old_multiline_json(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory) / "syslog.jsonl"
            logs.write_text(
                '{"timestamp_utc":"2026-10-27T09:49:12+00:00",'
                '"message":"VICTIM_LAB_PROBE id=old",\n}\n'
                '{"timestamp_utc":"2026-10-27T09:50:00+00:00",'
                '"message":"VICTIM_LAB_PROBE id=new"}\n',
                encoding="utf-8",
            )
            messages = recent_messages(logs)
            self.assertEqual([item["message"] for item in messages], [
                "VICTIM_LAB_PROBE id=new",
                "VICTIM_LAB_PROBE id=old",
            ])


class MonitorTests(unittest.TestCase):
    def test_sample_includes_syslog_counters(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("victim_lab.monitor.collect.read_cpu_ticks", return_value=(120, 40)), \
             patch("victim_lab.monitor.collect.read_memory", return_value={}), \
             patch("victim_lab.monitor.collect.read_interfaces", return_value={}), \
             patch("victim_lab.monitor.collect.read_udp_counters", return_value={}), \
             patch("victim_lab.monitor.collect.read_tcp_connections", return_value={}), \
             patch("victim_lab.monitor.collect.read_temperature", return_value=None), \
             patch("victim_lab.monitor.collect.read_rsyslog_stats", return_value={"received_total": 7}):
            _, record = sample((100, 30), "run-1", Path(directory) / "metrics.jsonl")
        self.assertEqual(record["syslog"]["received_total"], 7)


class NetworkConfigTests(unittest.TestCase):
    def test_private_lab_subnet(self):
        self.assertEqual(
            addresses("10.30.0.0/24"),
            ("10.30.0.0/24", "10.30.0.1", "10.30.0.2"),
        )

    def test_rejects_public_or_non_24_subnet(self):
        for subnet in ("8.8.8.0/24", "127.0.0.0/24", "10.30.0.0/16", "10.30.0.1/24"):
            with self.subTest(subnet=subnet), self.assertRaises(ValueError):
                addresses(subnet)


if __name__ == "__main__":
    unittest.main()
