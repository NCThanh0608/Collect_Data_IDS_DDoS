import hashlib
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from scapy.all import Ether, IP, UDP, Raw, wrpcap
except ImportError:
    Ether = None

if Ether is not None:
    from compare_syslog_capture import compare


@unittest.skipIf(Ether is None, "Scapy analysis dependency is not installed")
class CaptureCompareTests(unittest.TestCase):
    def test_binary_and_empty_msg_compare_by_payload_and_occurrence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            router_pcap = root / "router.pcap"
            victim_pcap = root / "victim.pcap"
            now = datetime.now(timezone.utc)
            header = b"<134>1 2026-11-03T00:00:00Z host app - - -"
            empty_msg = header
            binary_msg = header + b" \xff\x00\xfe"

            def packet(payload, index):
                item = Ether(dst="02:00:00:00:00:01") / IP(src="192.168.1.50", dst="10.20.0.2") / \
                    UDP(sport=42000, dport=514) / Raw(payload)
                item.time = now.timestamp() + index * 0.01
                return item

            wrpcap(str(router_pcap), [
                packet(empty_msg, 0), packet(empty_msg, 1), packet(binary_msg, 2),
            ])
            wrpcap(str(victim_pcap), [packet(empty_msg, 0), packet(binary_msg, 2)])
            receipts = [
                b'{"received_at_utc":"' + now.isoformat().replace("+00:00", "Z").encode("ascii") +
                b'","source_ip":"192.168.1.50","source_port":"42000","message":"' +
                message + b'"}\n'
                for message in (b"", b"\xff\x00\xfe")
            ]
            (root / "syslog.jsonl").write_bytes(b'{"message":"old format"}\n' + receipts[0])
            (root / "syslog.jsonl.20261103T081000Z.123.456").write_bytes(receipts[1])

            report = compare(router_pcap, victim_pcap, root, "10.20.0.2")
            self.assertEqual(report["router_packets"], 3)
            self.assertEqual(report["victim_packets"], 2)
            self.assertEqual(report["payload_matches"], 2)
            self.assertEqual(report["router_only"], 1)
            self.assertEqual(report["victim_only"], 0)
            self.assertEqual(report["rsyslog"]["written_in_window"], 2)
            self.assertEqual(report["rsyslog"]["lines_without_receipt_time"], 1)
            self.assertEqual(report["router_only_payloads"][0]["sha256"],
                             hashlib.sha256(empty_msg).hexdigest())

    def test_truncated_capture_is_reported_instead_of_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "short.pcap"
            item = Ether(dst="02:00:00:00:00:01") / IP(src="192.168.1.50", dst="10.20.0.2") / \
                UDP(sport=42000, dport=514) / Raw(b"payload")
            wrpcap(str(path), [item])
            data = bytearray(path.read_bytes())
            captured_length = 14 + 20 + 8 + 2
            struct.pack_into("<I", data, 32, captured_length)
            path.write_bytes(data[:40 + captured_length])
            report = compare(path, path, root, "10.20.0.2")
            self.assertEqual(report["router_packets"], 0)
            self.assertEqual(report["router_capture_issues"]["incomplete"], 1)

    def test_identical_payload_from_different_sources_does_not_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            router_pcap = root / "router.pcap"
            victim_pcap = root / "victim.pcap"
            def packet(source):
                return Ether(dst="02:00:00:00:00:01") / \
                    IP(src=source, dst="10.20.0.2") / \
                    UDP(sport=42000, dport=514) / Raw(b"same")

            wrpcap(str(router_pcap), [packet("192.168.1.50")])
            wrpcap(str(victim_pcap), [packet("192.168.1.51")])
            report = compare(router_pcap, victim_pcap, root, "10.20.0.2")
            self.assertEqual(report["payload_matches"], 0)
            self.assertEqual(report["router_only"], 1)
            self.assertEqual(report["victim_only"], 1)


if __name__ == "__main__":
    unittest.main()
