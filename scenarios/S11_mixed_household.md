# S11 – Mô phỏng sinh hoạt gia đình (Mixed Household Activity)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic khi nhiều hoạt động diễn ra đồng thời như lúc cả gia đình ở nhà vào ban ngày, do thành viên lab đóng vai: video, web, gọi, camera, điều khiển, đồng bộ |
| **Cấu hình áp dụng** | Nhỏ và Lớn |
| **Kịch bản chạy kèm** | S08 + các hoạt động của S03, S04, S05, S06, S07, S09 |
| **Thời lượng** | 60 phút / lần (cho phép 45–80 phút) |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.1.1
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.1.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       Người dùng                               Camera, IoT
       ● LAPTOP01 .10  video + web              ● CAM01 .30   ● IOT01 .40
       ● LAPTOP02 .11  họp / làm việc, sync     ● CAM02 .31   ● IOT02 .41
       ● PHONE01  .14  mạng xã hội, camera      ● CAM03 .32   ● IOT03 .42
       ● PHONE02  .15  video ngắn, điều khiển
       [Lớn: ● LAPTOP03 .12, LAPTOP04 .13, PHONE03–06 .16–.19]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

Mỗi thiết bị do một thành viên lab vận hành, đóng vai một "thành viên gia đình" có thói quen riêng. Giữ nguyên phân vai giữa các lần thu. Không cần thao tác đúng từng giây, chỉ cần theo khung hoạt động.

| Device ID | Loại | IP | Cấu hình | Vai trò giả định | Hoạt động chính |
|---|---|---|---|---|---|
| LAPTOP01 | Laptop | 192.168.1.10 | Cả hai | Bố | Xem tin tức, YouTube, duyệt web |
| LAPTOP02 | Laptop | 192.168.1.11 | Cả hai | Mẹ | Họp online 15 phút, email, upload tài liệu lên cloud |
| PHONE01 | Smartphone | 192.168.1.14 | Cả hai | Bố | Facebook, Zalo, xem CAM01 ngoài cổng |
| PHONE02 | Smartphone | 192.168.1.15 | Cả hai | Con | TikTok, nhắn tin, bật/tắt đèn (IOT03) |
| LAPTOP03 | Laptop | 192.168.1.12 | Lớn | Con lớn | Game online nhẹ / học online, tải tài liệu |
| LAPTOP04 | Laptop | 192.168.1.13 | Lớn | Con lớn | Phim trực tuyến |
| PHONE03 | Smartphone | 192.168.1.16 | Lớn | Mẹ | Backup ảnh, mua sắm online |
| PHONE04 | Smartphone | 192.168.1.17 | Lớn | Ông/bà | Xem video YouTube, gọi video Zalo (người nghe ở ngoài) |
| PHONE05 | Smartphone | 192.168.1.18 | Lớn | Khách | Mạng xã hội, chủ yếu ở trạng thái chờ |
| PHONE06 | Smartphone | 192.168.1.19 | Lớn | Khách | Web, email, nhắn tin |
| CAM01–CAM03 | IP camera | 192.168.1.30–32 | Cả hai | — | Nền + được xem theo khung giờ |
| IOT01–IOT03 | IoT MQTT | 192.168.1.40–42 | Cả hai | — | S08 + nhận lệnh điều khiển |
| ROUTER / CAPTURE-SERVER | Router / Server | .1 / .60 | Cả hai | — | Gateway / capture |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 60 phút |
| Số lần thu | 3 lần mỗi cấu hình trong khung 07:00–18:00, xếp lịch trước khi đủ người vận hành tất cả thiết bị |
| Dung lượng PCAP ước tính | 3–8 GB (Nhỏ), 8–20 GB (Lớn) |
| Cách lưu | Cách B (script), tách file khi đạt 1000 MB hoặc ngưỡng `--max-file-mb` đã chọn |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–05 | Bắt đầu capture; mọi người dùng nhẹ (đọc tin, nhắn tin) |
| 05–20 | LAPTOP01 YouTube; LAPTOP02 họp online; PHONE01 Facebook; PHONE02 TikTok. Lớn: LAPTOP04 phim, PHONE04 YouTube |
| 20–25 | PHONE01 xem CAM01; PHONE02 bật/tắt IOT03 2–3 lần |
| 25–40 | LAPTOP02 upload tài liệu + sync; LAPTOP01 duyệt web; Lớn: PHONE03 backup ảnh, LAPTOP03 tải tài liệu, PHONE04 gọi video |
| 40–50 | Mở/đóng cửa (IOT02 sự kiện); LAPTOP02 xem CAM02 snapshot; các thiết bị khác tiếp tục video/web |
| 50–58 | Hoạt động giảm dần: tắt video, khóa điện thoại; Lớn: PHONE05, PHONE06 vẫn duyệt nhẹ |
| 58–60 | Dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 25 GB; dùng Cách B để tách file theo dung lượng.
- [ ] Mở phiên SSH thứ hai từ CAPTURE-SERVER để theo dõi CPU/RAM router (`top -d 10`), lưu output.

### 4.2. Setup device
- [ ] Tất cả thiết bị của cấu hình đã kết nối đúng SSID và IP.
- [ ] Đã chuẩn bị tài khoản/app cho từng hoạt động (video, họp, cloud, camera, dashboard MQTT).
- [ ] Phân công người dùng cho từng thiết bị, phát bảng timeline cho mọi người.
- [ ] Người nghe cuộc gọi/họp ở ngoài mạng SmartHome đã hẹn giờ.
- [ ] Smartphone tắt dữ liệu di động; không dùng VPN.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo khung timeline; mỗi người ghi nhanh hoạt động chính của mình theo mốc 5 phút.
- [ ] Theo dõi CPU router; nếu > 90% kéo dài > 2 phút, ghi `notes`.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Tạm dừng sync/backup, trả IoT về trạng thái ban đầu.
- [ ] Thêm dòng `metadata.csv` cho từng file PCAP với `active_scenarios = S11;S03;S04;S05;S06;S07;S09;S08`, ghi số thiết bị và khung giờ vào `notes`.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | Tổng thời lượng các file ≥ 58 phút, liên tục (không hở giữa các file), drop < 0,1% | `capinfos` từng file, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | **Tất cả** thiết bị của cấu hình xuất hiện | Statistics → Endpoints → IPv4 | [ ] |
| 4 | Có đủ loại traffic: DNS, TLS/QUIC, UDP media, traffic camera, MQTT | `dns`, `quic`, `stun`, `ip.addr in {192.168.1.30 192.168.1.31 192.168.1.32}`, `mqtt` | [ ] |
| 5 | Có giai đoạn nhiều luồng đồng thời (phút 05–40) | I/O Graph tổng + theo từng IP | [ ] |
| 6 | Có lệnh điều khiển IOT03 và phản hồi | `mqtt.topic contains "iot03"` | [ ] |
| 7 | CPU router không vượt 90% kéo dài | Log `top` | [ ] |
| 8 | MQTT nền không bị gián đoạn khi tải cao | `mqtt.topic == "smarthome/iot01/telemetry"` delta time | [ ] |
| 9 | `metadata.csv` có đủ các file của phiên, nhật ký hoạt động đầy đủ | Mở file | [ ] |
