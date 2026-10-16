#!/usr/bin/env python3
"""Script thu PCAP dùng chung cho mọi kịch bản S01–S12, chạy trên Windows và Linux.

Dùng Wireshark CLI (dumpcap, capinfos, tshark) và ssh. Chỉ dùng thư viện chuẩn của Python (>= 3.8).

Các bước:
  1. Kiểm tra trước khi thu: công cụ, SSH tới router, flow offloading, Mosquitto, tcpdump,
     lệch đồng hồ, dung lượng ổ, khung giờ 07:00–18:00.
  2. Thu: ssh vào router chạy tcpdump trên br-lan (loại SSH của CAPTURE-SERVER), dữ liệu đẩy về
     dumpcap trên máy này, tự tách file theo thời gian, tự dừng khi hết thời lượng.
  3. Đổi tên file theo quy ước, đọc số liệu bằng capinfos, ghi metadata.csv.
  4. Chạy các bộ lọc nghiệm thu bằng tshark, in và lưu báo cáo PASS/FAIL.

Ví dụ:
  python tools/capture_session.py --scenarios S04 --n-user-devices 4 --config Nho
  python tools/capture_session.py --scenarios S05,S07 --n-user-devices 10 --notes "cuoi tuan"
  python tools/capture_session.py --scenarios S07 --check-only --session-id SES005
"""

import argparse
import csv
import datetime as dt
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

# ---------------------------------------------------------------------------
# Cấu hình theo kịch bản
# ---------------------------------------------------------------------------
# minutes: thời lượng mặc định; split_min: tách file mỗi N phút; disk_gb: dung lượng trống tối thiểu
SCENARIOS = {
    "S01": {"name": "Idle network",       "minutes": 30, "split_min": 60, "disk_gb": 1},
    "S02": {"name": "Device onboarding",  "minutes": 15, "split_min": 60, "disk_gb": 1},
    "S03": {"name": "Web browsing",       "minutes": 30, "split_min": 60, "disk_gb": 2},
    "S04": {"name": "Video streaming",    "minutes": 30, "split_min": 60, "disk_gb": 12},
    "S05": {"name": "File transfer",      "minutes": 25, "split_min": 60, "disk_gb": 3},
    "S06": {"name": "Voice/video call",   "minutes": 30, "split_min": 60, "disk_gb": 3},
    "S07": {"name": "IP camera",          "minutes": 30, "split_min": 60, "disk_gb": 4},
    "S08": {"name": "MQTT background",    "minutes": 60, "split_min": 60, "disk_gb": 1},
    "S09": {"name": "Smart home control", "minutes": 20, "split_min": 60, "disk_gb": 1},
    "S10": {"name": "Normal reconnect",   "minutes": 15, "split_min": 60, "disk_gb": 1},
    "S11": {"name": "Mixed household",    "minutes": 60, "split_min": 30, "disk_gb": 25},
    "S12": {"name": "Peak hour",          "minutes": 30, "split_min": 10, "disk_gb": 30},
}

CAMS = "192.168.10.30 192.168.10.31 192.168.10.32"
USERS = " ".join(f"192.168.10.{i}" for i in range(10, 20))

# Bộ lọc nghiệm thu: (tên, display filter, kỳ vọng "zero" = phải bằng 0 | "nonzero" = phải > 0)
COMMON_CHECKS = [
    ("Không có SSH của CAPTURE-SERVER", "tcp.port == 22", "zero"),
    ("Có DNS", "dns", "nonzero"),
    ("MQTT publish (S08)", "mqtt.msgtype == 3", "nonzero"),
    ("IOT01 xuất hiện", "ip.addr == 192.168.10.40", "nonzero"),
    ("IOT02 xuất hiện", "ip.addr == 192.168.10.41", "nonzero"),
    ("IOT03 xuất hiện", "ip.addr == 192.168.10.42", "nonzero"),
]
SCENARIO_CHECKS = {
    "S01": [("Có NTP", "ntp", "nonzero")],
    "S02": [("DHCP Request/ACK", "dhcp", "nonzero"),
            ("DHCP Discover", "dhcp.option.dhcp == 1", "nonzero"),
            ("ARP", "arp", "nonzero"),
            ("MQTT CONNECT", "mqtt.msgtype == 1", "nonzero")],
    "S03": [("TLS ClientHello", "tls.handshake.type == 1", "nonzero"),
            ("QUIC", "quic", "nonzero")],
    "S04": [("QUIC/TLS", "quic || tls", "nonzero")],
    "S05": [("TLS", "tls", "nonzero")],
    "S06": [("STUN/TURN", "stun || udp.port == 3478 || udp.port == 19302", "nonzero")],
    # SSID chung: luồng camera <-> viewer Wi-Fi trong LAN không đi qua br-lan, nên không kiểm tra
    "S07": [("CAM01 xuất hiện", "ip.addr == 192.168.10.30", "nonzero"),
            ("CAM02 xuất hiện", "ip.addr == 192.168.10.31", "nonzero"),
            ("CAM03 xuất hiện", "ip.addr == 192.168.10.32", "nonzero")],
    "S08": [("PUBACK (QoS 1)", "mqtt.msgtype == 4", "nonzero")],
    "S09": [("Lệnh /cmd", 'mqtt.topic contains "/cmd"', "nonzero"),
            ("Phản hồi IOT03", 'mqtt.topic contains "iot03"', "nonzero")],
    "S10": [("DHCP khi kết nối lại", "dhcp", "nonzero"),
            ("LWT IOT03", 'mqtt.topic == "smarthome/iot03/status"', "nonzero")],
    "S11": [("QUIC", "quic", "nonzero"),
            ("Camera có traffic", f"ip.addr in {{{CAMS}}}", "nonzero"),
            ("Lệnh IOT03", 'mqtt.topic contains "iot03"', "nonzero")],
    "S12": [("Không có iperf (5201)", "tcp.port == 5201", "zero"),
            ("QUIC", "quic", "nonzero")],
}

META_FIELDS = ["session_id", "pcap_file", "start_time", "end_time", "config", "n_user_devices",
               "active_scenarios", "pkts_captured", "pkts_dropped", "notes"]

# ---------------------------------------------------------------------------
# In ra màn hình
# ---------------------------------------------------------------------------
if IS_WINDOWS:
    os.system("")  # bật mã màu ANSI trên console Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def step(msg):
    print(f"\n\033[36m== {msg}\033[0m")


def ok(msg):
    print(f"  \033[32m[OK]  \033[0m {msg}")


def warn(msg):
    print(f"  \033[33m[WARN]\033[0m {msg}")


def fail(msg):
    print(f"  \033[31m[FAIL]\033[0m {msg}")


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def find_tool(name, wireshark_dir):
    """Tìm dumpcap/tshark/capinfos: thư mục chỉ định → PATH → thư mục cài mặc định trên Windows."""
    exe = name + (".exe" if IS_WINDOWS else "")
    candidates = []
    if wireshark_dir:
        candidates.append(Path(wireshark_dir) / exe)
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    if IS_WINDOWS:
        candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Wireshark" / exe)
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def ssh_base(args):
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"{args.router_user}@{args.router_ip}"]


def run_router(args, command):
    try:
        r = subprocess.run(ssh_base(args) + [command], capture_output=True, text=True, timeout=30)
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def next_session_id(meta_path):
    highest = 0
    for row in read_metadata(meta_path):
        m = re.fullmatch(r"SES(\d+)", row.get("session_id", ""))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"SES{highest + 1:03d}"


def read_metadata(meta_path):
    if not meta_path.exists():
        return []
    with open(meta_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def append_metadata(meta_path, rows):
    new_file = not meta_path.exists()
    # utf-8-sig cho file mới để Excel đọc đúng tiếng Việt
    with open(meta_path, "a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=META_FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)


def capinfos_stats(capinfos, pcap):
    """Trả về (packets, duration_s, first_epoch, last_epoch)."""
    # -T -r -M -S: bảng không tiêu đề, số chính xác, thời gian dạng epoch. Cột: file, packets, duration, first, last
    out = subprocess.run([capinfos, "-T", "-r", "-M", "-S", "-c", "-u", "-a", "-e", str(pcap)],
                         capture_output=True, text=True, check=True).stdout
    cols = out.strip().splitlines()[-1].split("\t")
    return int(cols[1]), float(cols[2]), float(cols[3]), float(cols[4])


def filter_counts(tshark, pcap, filters):
    """Đếm số gói khớp với nhiều bộ lọc trong MỘT lần đọc file (tshark -z io,stat,0,...)."""
    z = "io,stat,0," + ",".join(filters)
    r = subprocess.run([tshark, "-n", "-q", "-r", str(pcap), "-z", z], capture_output=True, text=True)
    if r.returncode != 0:
        warn(f"tshark lỗi với {pcap.name}: {r.stderr.strip()}")
    rows = [line for line in r.stdout.splitlines() if "<>" in line]
    if not rows:
        return [0] * len(filters)
    cells = [c.strip() for c in rows[-1].split("|")[2:] if c.strip()]
    # Mỗi bộ lọc có 2 cột: Frames, Bytes
    return [int(cells[2 * i]) for i in range(len(filters))]


def iso_local(epoch):
    return dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Các bước chính
# ---------------------------------------------------------------------------
def precheck(args, tools, duration_min, disk_gb):
    step("Kiểm tra trước khi thu")
    problems = 0

    for name, path in tools.items():
        if path:
            ok(f"Tìm thấy {name}: {path}")
        else:
            fail(f"Không tìm thấy {name} (cài Wireshark CLI hoặc dùng --wireshark-dir)")
            problems += 1
    if shutil.which("ssh"):
        ok("Tìm thấy ssh")
    else:
        fail("Chưa cài OpenSSH client")
        problems += 1

    now = dt.datetime.now()
    end = now + dt.timedelta(minutes=duration_min)
    if now.hour < 7 or end > now.replace(hour=18, minute=0, second=0, microsecond=0):
        fail(f"Phiên {now:%H:%M}-{end:%H:%M} nằm ngoài khung 07:00-18:00")
        problems += 1
    else:
        ok(f"Khung giờ {now:%H:%M}-{end:%H:%M}")

    free_gb = shutil.disk_usage(args.out_dir).free / 1024 ** 3
    if free_gb >= disk_gb:
        ok(f"Ổ đĩa còn trống {free_gb:.1f} GB (cần >= {disk_gb} GB)")
    else:
        fail(f"Ổ đĩa còn {free_gb:.1f} GB, cần >= {disk_gb} GB")
        problems += 1

    probe = run_router(args, "echo SSH_OK; "
                             "echo OFFLOAD=$(uci -q get firewall.@defaults[0].flow_offloading); "
                             "echo OFFLOAD_HW=$(uci -q get firewall.@defaults[0].flow_offloading_hw); "
                             "/etc/init.d/mosquitto running && echo MQ_OK; "
                             "which tcpdump; echo EPOCH=$(date +%s)")
    if "SSH_OK" not in probe:
        fail(f"Không SSH được vào {args.router_user}@{args.router_ip} (cần SSH key, không dùng mật khẩu)")
        problems += 1
    else:
        ok("SSH vào router")
        if re.search(r"OFFLOAD(_HW)?=1", probe):
            fail("Flow offloading đang bật")
            problems += 1
        else:
            ok("Flow offloading đã tắt")
        if "MQ_OK" in probe:
            ok("Mosquitto đang chạy")
        else:
            fail("Mosquitto không chạy")
            problems += 1
        if "tcpdump" in probe:
            ok("Router có tcpdump")
        else:
            fail("Router chưa cài tcpdump")
            problems += 1
        m = re.search(r"EPOCH=(\d+)", probe)
        if m:
            skew = abs(int(m.group(1)) - int(time.time()))
            if skew <= 2:
                ok(f"Lệch đồng hồ router: {skew} s")
            else:
                fail(f"Lệch đồng hồ router: {skew} s (> 2 s)")
                problems += 1

    if problems and not args.force:
        sys.exit(f"\nCó {problems} lỗi kiểm tra trước khi thu. Sửa lỗi hoặc chạy lại với --force.")


def capture(args, tools, session_id, duration_min, split_min, pcap_dir, tcpdump_log):
    step("Thu PCAP")
    duration_s = duration_min * 60
    bpf = f"not (host {args.capture_server_ip} and port 22)"
    remote = f"timeout {duration_s} tcpdump -i {args.interface} -s 0 -U -B 4096 -w - '{bpf}'"
    ssh_cmd = ssh_base(args)[:]
    ssh_cmd[ssh_cmd.index("ConnectTimeout=5")] = "ServerAliveInterval=15"
    ssh_cmd.append(remote)
    dumpcap_cmd = [tools["dumpcap"], "-q", "-i", "-", "-F", "pcap",
                   "-b", f"duration:{split_min * 60}", "-w", str(pcap_dir / f"{session_id}.pcap")]

    start = dt.datetime.now()
    print(f"Bắt đầu {start:%H:%M:%S}, tự dừng lúc {start + dt.timedelta(seconds=duration_s):%H:%M:%S}. "
          "Nhấn Ctrl+C để dừng sớm (dữ liệu đã thu vẫn được xử lý).")

    with open(tcpdump_log, "wb") as log:
        ssh = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=log)
        dumpcap = subprocess.Popen(dumpcap_cmd, stdin=ssh.stdout)
        ssh.stdout.close()  # để dumpcap nhận EOF khi ssh kết thúc
        try:
            dumpcap.wait()
            ssh.wait()
        except KeyboardInterrupt:
            warn("Dừng sớm theo yêu cầu, đang chờ dumpcap ghi nốt dữ liệu...")
            for p in (ssh, dumpcap):
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.terminate()
            args.notes = "; ".join(x for x in (args.notes, "dung som bang Ctrl+C") if x)
    print(f"Kết thúc {dt.datetime.now():%H:%M:%S}")

    # Đổi tên: SES001_00001_20261012145800.pcap -> SES001_20261012_145800.pcap
    for f in pcap_dir.glob(f"{session_id}_*.pcap"):
        m = re.fullmatch(rf"({session_id})_\d{{5}}_(\d{{8}})(\d{{6}})\.pcap", f.name)
        if m:
            f.rename(f.with_name(f"{m.group(1)}_{m.group(2)}_{m.group(3)}.pcap"))


def main():
    p = argparse.ArgumentParser(description="Thu PCAP chung cho các kịch bản S01–S12.")
    p.add_argument("--scenarios", required=True, nargs="+",
                   help="Một hoặc nhiều kịch bản, ví dụ: S04  hoặc  S05,S07  (S08 luôn được thêm)")
    p.add_argument("--n-user-devices", type=int, default=0, help="Số thiết bị người dùng đang kết nối")
    p.add_argument("--config", choices=["Nho", "Lon"], default="Lon")
    p.add_argument("--duration-min", type=int, default=0, help="0 = dùng thời lượng mặc định của kịch bản")
    p.add_argument("--notes", default="")
    p.add_argument("--router-ip", default="192.168.10.1")
    p.add_argument("--router-user", default="root")
    p.add_argument("--capture-server-ip", default="192.168.10.60")
    p.add_argument("--interface", default="br-lan")
    p.add_argument("--out-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    p.add_argument("--wireshark-dir", default="", help="Thư mục chứa dumpcap/tshark/capinfos nếu không nằm trong PATH")
    p.add_argument("--check-only", action="store_true", help="Bỏ qua thu, chỉ ghi metadata (nếu thiếu) và nghiệm thu")
    p.add_argument("--session-id", default="", help="Dùng với --check-only")
    p.add_argument("--force", action="store_true", help="Vẫn thu dù kiểm tra trước khi thu có lỗi")
    args = p.parse_args()

    # Chuẩn hóa danh sách kịch bản
    scenarios = []
    for item in args.scenarios:
        for s in re.split(r"[,; ]+", item.upper()):
            if s and s not in scenarios:
                scenarios.append(s)
    for s in scenarios:
        if s not in SCENARIOS:
            sys.exit(f"Kịch bản không hợp lệ: {s}")
    if "S08" not in scenarios:
        scenarios.append("S08")
    main_sc = next((s for s in scenarios if s != "S08"), "S08")
    if "S12" in scenarios and args.config != "Lon":
        sys.exit("S12 chỉ chạy với cấu hình Lon.")
    if args.check_only and not args.session_id:
        sys.exit("--check-only cần kèm --session-id")

    duration_min = args.duration_min or SCENARIOS[main_sc]["minutes"]
    split_min = min(SCENARIOS[s]["split_min"] for s in scenarios)
    disk_gb = max(SCENARIOS[s]["disk_gb"] for s in scenarios)
    active = ";".join([main_sc] + sorted(s for s in scenarios if s != main_sc))

    out_dir = Path(args.out_dir)
    pcap_dir, log_dir = out_dir / "pcap", out_dir / "logs"
    pcap_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "metadata.csv"
    tools = {name: find_tool(name, args.wireshark_dir) for name in ("dumpcap", "tshark", "capinfos")}

    session_id = args.session_id or next_session_id(meta_path)
    tcpdump_log = log_dir / f"{session_id}_tcpdump.log"
    print(f"Phiên: {session_id} | Kịch bản: {active} | Thời lượng: {duration_min} phút | "
          f"Tách file: {split_min} phút | Cấu hình: {args.config}")
    print(f"Chi tiết kịch bản: scenarios/{main_sc}_*.md")

    # 1–2. Kiểm tra và thu
    if not args.check_only:
        precheck(args, tools, duration_min, disk_gb)
        capture(args, tools, session_id, duration_min, split_min, pcap_dir, tcpdump_log)
    elif not (tools["capinfos"] and tools["tshark"]):
        sys.exit("Không tìm thấy capinfos/tshark (cài Wireshark CLI hoặc dùng --wireshark-dir)")

    # 3. Số liệu và metadata
    step("Số liệu phiên")
    files = sorted(pcap_dir.glob(f"{session_id}_*.pcap"))
    if not files:
        sys.exit(f"Không có file PCAP nào cho {session_id} trong {pcap_dir}")

    kernel_dropped = None
    if tcpdump_log.exists():
        m = re.search(r"(\d+) packets? dropped by kernel", tcpdump_log.read_text(errors="replace"))
        if m:
            kernel_dropped = int(m.group(1))

    stats = []
    for f in files:
        packets, duration, first, last = capinfos_stats(tools["capinfos"], f)
        stats.append((f, packets, duration, first, last))
        print(f"  {f.name}: {packets} gói, {duration:,.0f} s")
    total_packets = sum(s[1] for s in stats)
    total_duration = sum(s[2] for s in stats)
    drop_pct = (100.0 * kernel_dropped / (kernel_dropped + total_packets)
                if kernel_dropped is not None and total_packets else None)

    # Ghi metadata nếu phiên chưa có (kể cả khi chạy lại bằng --check-only)
    if not any(r.get("session_id") == session_id for r in read_metadata(meta_path)):
        notes = "; ".join(x for x in (args.notes, "drop tinh cho ca phien") if x)
        rows = [{"session_id": session_id, "pcap_file": f.name, "start_time": iso_local(first),
                 "end_time": iso_local(last), "config": args.config, "n_user_devices": args.n_user_devices,
                 "active_scenarios": active, "pkts_captured": packets,
                 "pkts_dropped": "" if kernel_dropped is None else kernel_dropped, "notes": notes}
                for f, packets, _, first, last in stats]
        append_metadata(meta_path, rows)
        ok(f"Đã ghi {len(rows)} dòng vào {meta_path}")

    # 4. Nghiệm thu
    step("Nghiệm thu")
    checks = COMMON_CHECKS + [c for s in scenarios for c in SCENARIO_CHECKS.get(s, [])]
    filters = [c[1] for c in checks]
    totals = [0] * len(filters)
    for f, *_ in stats:
        for i, n in enumerate(filter_counts(tools["tshark"], f, filters)):
            totals[i] += n

    report = [
        ("PCAP không rỗng", "capinfos", str(total_packets), "PASS" if total_packets > 0 else "FAIL"),
        ("Thời lượng >= 93% kế hoạch", "capinfos", f"{total_duration:,.0f} s",
         "PASS" if total_duration >= duration_min * 60 * 0.93 else "FAIL"),
        ("Drop < 0.1%", "tcpdump", "không có số liệu" if drop_pct is None else f"{drop_pct:.3f}%",
         "CHECK" if drop_pct is None else ("PASS" if drop_pct < 0.1 else "FAIL")),
    ]
    for (name, flt, expect), n in zip(checks, totals):
        passed = n == 0 if expect == "zero" else n > 0
        report.append((name, flt, str(n), "PASS" if passed else "FAIL"))

    widths = [max(len(r[i]) for r in report + [("Check", "Filter", "Value", "Result")]) for i in range(4)]
    header = ("Check", "Filter", "Value", "Result")
    print("  " + "  ".join(h.ljust(w) for h, w in zip(header, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    colors = {"PASS": "\033[32m", "FAIL": "\033[31m", "CHECK": "\033[33m"}
    for r in report:
        cells = [r[0].ljust(widths[0]), r[1].ljust(widths[1]), r[2].rjust(widths[2])]
        print("  " + "  ".join(cells) + f"  {colors[r[3]]}{r[3]}\033[0m")

    report_path = log_dir / f"{session_id}_report.csv"
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(report)

    fails = sum(1 for r in report if r[3] == "FAIL")
    print()
    if fails == 0:
        ok(f"Tất cả tiêu chí tự động đều đạt. Báo cáo: {report_path}")
    else:
        fail(f"{fails} tiêu chí không đạt. Báo cáo: {report_path}")
    print(f"Các tiêu chí cần nhìn bằng mắt (I/O Graph, đối chiếu nhật ký) xem trong scenarios/{main_sc}_*.md mục 5.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
