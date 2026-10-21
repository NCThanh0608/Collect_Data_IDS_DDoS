# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

Bộ tài liệu và công cụ **thu normal traffic (không gán nhãn)** của một mạng Smart Home, làm baseline cho IDS phát hiện bất thường. Dữ liệu được thu trong **phòng lab mô phỏng Smart Home** (thành viên lab đóng vai người dùng); điểm thu là router OpenWrt, interface `br-lan`. Không có mã ứng dụng; repo gồm tài liệu Markdown tiếng Việt và một script Python.

| Đường dẫn | Vai trò |
|---|---|
| `smarthome_normal_traffic_capture_plan.md` | Tài liệu gốc: quy mô, nguyên tắc, topology, IP, MQTT, danh sách S01–S12, capture, đầu ra, checklist |
| `scenarios/Sxx_<ten_tieng_anh>.md` | 12 kịch bản chi tiết |
| `generalization_assessment.md` | Đánh giá tính tổng quát hóa của dataset |
| `tools/capture_session.py` | Script thu chung (Windows và Linux): kiểm tra trước → thu → metadata → nghiệm thu |
| `README.md` | Mô tả dự án: mục tiêu, phạm vi, mô hình mạng, bộ kịch bản, đầu ra, trạng thái |
| `tools/README.md` | Hướng dẫn chạy script: chuẩn bị, tham số, đầu ra, xử lý sự cố |
| `data/` | Đầu ra khi thu (PCAP, `metadata.csv`, logs). Bị gitignore, không commit |

## Quy ước bắt buộc (giữ nhất quán giữa mọi file)

- **Ngôn ngữ:** nội dung tài liệu bằng tiếng Việt; tên file và tên thư mục bằng tiếng Anh, chữ thường, dùng `_`.
- **Môi trường lab:** viết "thành viên lab", "người vận hành", "ngoài mạng SmartHome"; không viết như thể thu ở nhà thật ("người trong nhà", "ngoài mạng nhà"). Vai "bố/mẹ/con" chỉ là vai mô phỏng. Điều kiện lab nằm ở mục 1.4 tài liệu gốc.
- **Không gán nhãn:** không thêm trường `label`, `class`, `attack_type`, `Benign`. ID kịch bản chỉ xuất hiện trong `metadata.csv` (cột `active_scenarios`), không phải nhãn.
- **Khung giờ thu: chỉ 07:00–18:00.** Không đưa buổi tối hoặc ban đêm vào ví dụ, timeline hay khung giờ thu.
- **Mạng:** một subnet `192.168.1.0/24` trên `br-lan`, **một SSID chung `SmartHome`** cho mọi thiết bị Wi-Fi (người dùng đã quyết định bỏ hai SSID riêng).
  - Hệ quả đã chấp nhận: unicast giữa hai thiết bị Wi-Fi (ví dụ viewer ↔ camera trong LAN) không đi qua `br-lan` nên không thu được. Không đưa tiêu chí nghiệm thu nào đòi hỏi luồng này, trừ khi camera cắm dây.
  - Không đặt tên viết tắt khó nhớ kiểu `SH-`.
- **Mã thiết bị và IP:**

  | Mã | IP | SSID / kết nối |
  |---|---|---|
  | `ROUTER` | .1 | — (chạy broker Mosquitto :1883 và tcpdump) |
  | `LAPTOP01`–`LAPTOP04` | .10–.13 | SmartHome |
  | `PHONE01`–`PHONE06` | .14–.19 | SmartHome |
  | `CAM01`–`CAM03` | .30–.32 | SmartHome (hoặc cổng LAN) |
  | `IOT01`–`IOT03` | .40–.42 | SmartHome |
  | `CAPTURE-SERVER` | .60 | Cổng LAN có dây |

- **Cấu hình:**
  - Nhỏ = `LAPTOP01–LAPTOP02` + `PHONE01–PHONE02` (cột "Cả hai").
  - Lớn = `LAPTOP01–LAPTOP04` + `PHONE01–PHONE06` (4 laptop + 6 smartphone).
  - Giá trị của `--config` và cột `config` trong metadata là `small` hoặc `large` (chữ thường); tên Nhỏ/Lớn chỉ dùng trong phần mô tả tiếng Việt.
  - Camera và IoT luôn đủ 3 + 3.
  - S12 chỉ chạy với cấu hình Lớn.
- **MQTT:**
  - Topic theo dạng `smarthome/<device_id>/<message_type>` (`telemetry`, `event`, `state`, `ack`, `cmd`, `status`).
  - LWT `smarthome/<device_id>/status`, keepalive 60 giây.
  - S08 chạy nền trong mọi phiên.
- **Bộ lọc Wireshark cho nhiều IP:** dùng `ip.addr in {192.168.1.30 192.168.1.31 192.168.1.32}`. Không dùng CIDR như `/30`, vì `/30` lệch dải.
- **Metadata:**
  - Thời gian theo ISO 8601 có timezone `+07:00`.
  - Tên PCAP dạng `SESxxx_YYYYMMDD_HHMMSS.pcap`; nếu nhiều file được tách trong cùng một giây, các file sau thêm số thứ tự của `dumpcap` trước `.pcap` (ví dụ `_00002`) để tránh trùng tên.
  - Cột: `session_id,pcap_file,start_time,end_time,config,n_user_devices,active_scenarios,pkts_captured,pkts_dropped,notes`.

## Cấu trúc file kịch bản

Mọi file `scenarios/Sxx_*.md` theo cùng khung:

1. Bảng thuộc tính: mục tiêu, cấu hình áp dụng, kịch bản chạy kèm, thời lượng, link về tài liệu gốc.
2. Topology dạng ASCII. Đánh dấu `●` cho thiết bị hoạt động chủ động, `○` cho thiết bị chỉ có traffic nền.
3. Chi tiết thiết bị.
4. Thời gian thu: tham số và timeline theo phút.
5. Checklist công việc: 4.1 Setup hạ tầng, 4.2 Setup device, 4.3 Thực hiện, 4.4 Kết thúc phiên.
6. Checklist nghiệm thu: bảng `# | Tiêu chí | Cách kiểm tra | Đạt`.

## Khi sửa tài liệu

- Một thay đổi về quy ước (tên, IP, SSID, khung giờ, tham số MQTT) thường phải sửa **đồng bộ** ở:
  - Tài liệu gốc.
  - Cả 12 file kịch bản.
  - `generalization_assessment.md`.
  - `README.md` và `tools/README.md`.
  - `tools/capture_session.py` (các bảng `SCENARIOS`, `COMMON_CHECKS`, `SCENARIO_CHECKS`).
- Sau khi sửa hàng loạt, `grep` lại tên cũ để chắc không còn sót.
- Trong sơ đồ ASCII, giữ thẳng cột khi đổi độ dài tên.
- Thay đổi thời lượng hoặc dung lượng ổ của kịch bản phải cập nhật cả `SCENARIOS` trong script và bảng mặc định trong `tools/README.md`. Ngưỡng tách theo dung lượng dùng chung cho mọi kịch bản.

## Script `tools/capture_session.py`

- Chạy trên **Windows và Linux**, Python ≥ 3.8, **chỉ dùng thư viện chuẩn**. Không thêm phụ thuộc pip.
- Gọi Wireshark CLI (`dumpcap`, `tshark`, `capinfos`) và `ssh` bằng `subprocess` với **danh sách tham số**, không dùng `shell=True`. Như vậy bộ lọc có dấu `"` hay dấu cách được truyền đúng trên cả hai hệ điều hành.
- **Tìm công cụ** qua `find_tool()`, theo thứ tự: `--wireshark-dir` → `PATH` → `C:\Program Files\Wireshark` (Windows). Không hard-code đường dẫn ở chỗ khác.
- **Đường ống thu:** `subprocess.Popen(ssh) → stdout → Popen(dumpcap -i - -F pcap -b filesize:K)`. `K` là ngưỡng theo kB, mặc định 1.000.000 kB (1000 MB), có thể đổi bằng `--max-file-mb`. Chỉ tách file khi đạt ngưỡng dung lượng; thời lượng phiên chỉ quyết định lúc dừng thu. Python truyền dữ liệu nhị phân an toàn. Đóng `ssh.stdout` ở tiến trình cha để `dumpcap` nhận EOF.
- **Ctrl+C:** bắt `KeyboardInterrupt`, chờ `dumpcap` ghi nốt rồi vẫn ghi metadata và nghiệm thu.
- **Router:** dùng BusyBox `timeout <giây> tcpdump …` để tcpdump tự dừng và in `dropped by kernel` ra stderr; stderr của ssh được ghi vào `data/logs/<session>_tcpdump.log`.
- **Tên file:** `dumpcap` ghi `SES001_00001_YYYYMMDDhhmmss.pcap`, script đổi thành `SES001_YYYYMMDD_hhmmss.pcap` hoặc thêm hậu tố thứ tự khi trùng giây. Không ghi đè PCAP đã tồn tại.
- **Đầu ra console:** stdout được ép UTF-8 để in tiếng Việt cả khi output bị chuyển hướng trên Windows. Màu dùng mã ANSI; `os.system("")` bật ANSI trên console Windows.
- **CSV:** ghi bằng `utf-8-sig` khi tạo file mới để Excel đọc đúng tiếng Việt.
- **Mã thoát:** `0` nếu không có tiêu chí FAIL, `1` nếu có.

**Kiểm thử không cần router:**
- Tạo PCAP giả (ví dụ bằng Python, gồm gói DNS và MQTT tới :1883) tại `<out-dir>/pcap/SES900_YYYYMMDD_HHMMSS.pcap`, rồi chạy `--check-only --session-id SES900 --out-dir <thư mục tạm>`.
- Thử bước thu: import module, gán đè `ssh_base` thành một chương trình Python giả, đẩy PCAP ra stdout và in số liệu kiểu tcpdump ra stderr. Sau đó gọi `capture()`.
- Đặt file thử trong thư mục scratchpad, không đặt trong `data/`.

**Trạng thái kiểm thử:**
- Trên Windows đã chạy thử với ssh giả.
- **Chưa chạy thử trên Linux.**
- **Chưa chạy thử với router thật.**

## Không làm

- Không commit dữ liệu trong `data/`, PCAP, `devices.csv` thật, SSH key hay mật khẩu MQTT.
- Không thêm kịch bản tấn công hoặc công cụ tạo tải nhân tạo (iperf, packet flood) vào bộ normal traffic.
- Không tự đổi quy ước ở trên khi chưa được người dùng yêu cầu.
