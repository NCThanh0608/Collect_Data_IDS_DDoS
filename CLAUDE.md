# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

Bộ tài liệu và công cụ **thu normal traffic (không gán nhãn)** của một mạng Smart Home, làm baseline cho IDS phát hiện bất thường. Điểm thu là router OpenWrt, interface `br-lan`. Không có mã ứng dụng; repo gồm tài liệu Markdown tiếng Việt và một script PowerShell.

| Đường dẫn | Vai trò |
|---|---|
| `smarthome_normal_traffic_capture_plan.md` | Tài liệu gốc: quy mô, nguyên tắc, topology, IP, MQTT, danh sách S01–S12, capture, đầu ra, checklist |
| `scenarios/Sxx_<ten_tieng_anh>.md` | 12 kịch bản chi tiết |
| `generalization_assessment.md` | Đánh giá tính tổng quát hóa của dataset |
| `tools/capture_session.ps1` | Script thu chung: kiểm tra trước → thu → metadata → nghiệm thu |
| `README.md` | Hướng dẫn chạy script |
| `data/` | Đầu ra khi thu (PCAP, `metadata.csv`, logs). Bị gitignore, không commit |

## Quy ước bắt buộc (giữ nhất quán giữa mọi file)

- **Ngôn ngữ:** nội dung tài liệu bằng tiếng Việt; tên file và tên thư mục bằng tiếng Anh, chữ thường, dùng `_`.
- **Không gán nhãn:** không thêm trường `label`, `class`, `attack_type`, `Benign`. ID kịch bản chỉ xuất hiện trong `metadata.csv` (cột `active_scenarios`), không phải nhãn.
- **Khung giờ thu: chỉ 07:00–18:00.** Không đưa buổi tối hoặc ban đêm vào ví dụ, timeline hay khung giờ thu.
- **Mạng:** một subnet `192.168.10.0/24` trên `br-lan`, hai SSID cùng bridge vào `br-lan`:
  - `SmartHome-User`: thiết bị người dùng.
  - `SmartHome-IoT`: camera và IoT.
  - Không đặt tên viết tắt khó nhớ kiểu `SH-`.
- **Mã thiết bị và IP:**

  | Mã | IP | SSID / kết nối |
  |---|---|---|
  | `ROUTER` | .1 | — (chạy broker Mosquitto :1883 và tcpdump) |
  | `PC01`–`PC05` (PC và laptop gộp chung một nhóm "PC/Laptop") | .10–.14 | SmartHome-User |
  | `PHONE01`–`PHONE05` | .15–.19 | SmartHome-User |
  | `CAM01`–`CAM03` | .30–.32 | SmartHome-IoT |
  | `IOT01`–`IOT03` | .40–.42 | SmartHome-IoT |
  | `CAPTURE-SERVER` | .60 | Cổng LAN có dây |

- **Cấu hình:**
  - Nhỏ = `PC01–PC02` + `PHONE01–PHONE02` (cột "Cả hai").
  - Lớn = `PC01–PC05` + `PHONE01–PHONE05`.
  - Camera và IoT luôn đủ 3 + 3.
  - S12 chỉ chạy với cấu hình Lớn.
- **MQTT:**
  - Topic theo dạng `smarthome/<device_id>/<message_type>` (`telemetry`, `event`, `state`, `ack`, `cmd`, `status`).
  - LWT `smarthome/<device_id>/status`, keepalive 60 giây.
  - S08 chạy nền trong mọi phiên.
- **Bộ lọc Wireshark cho nhiều IP:** dùng `ip.addr in {192.168.10.30 192.168.10.31 192.168.10.32}`. Không dùng CIDR như `/30`, vì `/30` lệch dải.
- **Metadata:**
  - Thời gian theo ISO 8601 có timezone `+07:00`.
  - Tên PCAP dạng `SESxxx_YYYYMMDD_HHMMSS.pcap`.
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
  - `README.md`.
  - `tools/capture_session.ps1` (các bảng `$ScenarioInfo`, `$CommonChecks`, `$ScenarioChecks`).
- Sau khi sửa hàng loạt, `grep` lại tên cũ để chắc không còn sót.
- Trong sơ đồ ASCII, giữ thẳng cột khi đổi độ dài tên.
- Thay đổi thời lượng, chu kỳ tách file hoặc dung lượng ổ của kịch bản phải cập nhật cả `$ScenarioInfo` trong script và bảng mặc định trong `README.md`.

## Script `tools/capture_session.ps1`

Script phải chạy được trên **Windows PowerShell 5.1**. Các bẫy đã gặp:

- **Encoding:** lưu file dạng **UTF-8 có BOM**; thiếu BOM thì PowerShell 5.1 đọc sai chú thích tiếng Việt. Chuỗi in ra console để không dấu (ASCII).
- **Pipe nhị phân:** PowerShell 5.1 làm hỏng dữ liệu khi pipe giữa hai chương trình ngoài. Đường ống `ssh … | dumpcap -i -` được ghi vào file `.cmd` rồi chạy bằng `cmd.exe /c`.
- **Tham số có dấu `"`:** PowerShell 5.1 truyền sai. `tshark` được gọi qua `System.Diagnostics.ProcessStartInfo`, chuỗi tham số tự dựng và escape `\"`.
- **Mảng một phần tử:** bọc kết quả pipeline trong `@(...)` trước khi dùng `+=` hoặc `.Count`.
- Dùng `dumpcap -F pcap`; không dùng `-P` vì đã lỗi thời.
- Trên router dùng BusyBox `timeout <giây> tcpdump …` để tcpdump tự dừng và in số gói bị bỏ sót (`dropped by kernel`) vào log.

**Kiểm thử không cần router:**
- Tạo PCAP giả (ví dụ bằng Python, gồm gói DNS và MQTT tới :1883) trong thư mục `<OutDir>\pcap\SES900_YYYYMMDD_HHMMSS.pcap`.
- Chạy `-CheckOnly -SessionId SES900 -OutDir <thư mục tạm>`.
- Kiểm tra pipe bằng `type file.pcap | dumpcap -i - -F pcap -b duration:3600 -w out.pcap` trong `cmd`.
- Đặt file thử trong thư mục scratchpad, không đặt trong `data/`.

Phần thu thật qua SSH tới router **chưa được kiểm thử** trên phần cứng thật.

## Không làm

- Không commit dữ liệu trong `data/`, PCAP, `devices.csv` thật, SSH key hay mật khẩu MQTT.
- Không thêm kịch bản tấn công hoặc công cụ tạo tải nhân tạo (iperf, packet flood) vào bộ normal traffic.
- Không tự đổi quy ước ở trên khi chưa được người dùng yêu cầu.
