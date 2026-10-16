# S11 – Sinh hoạt gia đình tổng hợp (Mixed Household Activity)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic khi nhiều hoạt động diễn ra đồng thời như lúc cả gia đình ở nhà vào ban ngày (ví dụ cuối tuần): video, web, gọi, camera, điều khiển, đồng bộ |
| **Cấu hình áp dụng** | Nhỏ và Lớn |
| **Kịch bản chạy kèm** | S08 + các hoạt động của S03, S04, S05, S06, S07, S09 |
| **Thời lượng** | 60 phút / lần (cho phép 45–80 phút) |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.10.1
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.10.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       SSID "SmartHome-User"                    SSID "SmartHome-IoT"
       ● PC01     .10  video + web              ● CAM01 .30   ● IOT01 .40
       ● PC02     .11  họp / làm việc, sync     ● CAM02 .31   ● IOT02 .41
       ● PHONE01  .15  mạng xã hội, camera      ● CAM03 .32   ● IOT03 .42
       ● PHONE02  .16  video ngắn, điều khiển
       [Lớn: ● PC03 .12, PC04 .13, PC05 .14, PHONE03–05 .17–.19]

Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

Mỗi thiết bị gắn với một "thành viên gia đình" có thói quen riêng. Không cần thao tác đúng từng giây, chỉ cần theo khung hoạt động.

| Device ID | Loại | IP | Cấu hình | Vai trò giả định | Hoạt động chính |
|---|---|---|---|---|---|
| PC01 | PC/Laptop | 192.168.10.10 | Cả hai | Bố | Xem tin tức, YouTube, duyệt web |
| PC02 | PC/Laptop | 192.168.10.11 | Cả hai | Mẹ | Họp online 15 phút, email, upload tài liệu lên cloud |
| PHONE01 | Smartphone | 192.168.10.15 | Cả hai | Bố | Facebook, Zalo, xem CAM01 ngoài cổng |
| PHONE02 | Smartphone | 192.168.10.16 | Cả hai | Con | TikTok, nhắn tin, bật/tắt đèn (IOT03) |
| PC03 | PC/Laptop | 192.168.10.12 | Lớn | Con lớn | Game online nhẹ / học online, tải tài liệu |
| PC04 | PC/Laptop | 192.168.10.13 | Lớn | Con lớn | Phim trực tuyến |
| PC05 | PC/Laptop | 192.168.10.14 | Lớn | Khách | Web, email |
| PHONE03 | Smartphone | 192.168.10.17 | Lớn | Mẹ | Backup ảnh, mua sắm online |
| PHONE04 | Smartphone | 192.168.10.18 | Lớn | Ông/bà | Xem video YouTube, gọi video Zalo (người nghe ở ngoài) |
| PHONE05 | Smartphone | 192.168.10.19 | Lớn | Khách | Mạng xã hội, chủ yếu ở trạng thái chờ |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | Cả hai | — | Nền + được xem theo khung giờ |
| IOT01–IOT03 | IoT MQTT | 192.168.10.40–42 | Cả hai | — | S08 + nhận lệnh điều khiển |
| ROUTER / CAPTURE-SERVER | Router / Server | .1 / .60 | Cả hai | — | Gateway / capture |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 60 phút |
| Số lần thu | 3 lần mỗi cấu hình trong khung 07:00–18:00, ưu tiên cuối tuần hoặc ngày nghỉ khi đông người ở nhà |
| Dung lượng PCAP ước tính | 3–8 GB (Nhỏ), 8–20 GB (Lớn) |
| Cách lưu | Cách B, tách file mỗi 30 phút (`-G 1800`) |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–05 | Bắt đầu capture; mọi người dùng nhẹ (đọc tin, nhắn tin) |
| 05–20 | PC01 YouTube; PC02 họp online; PHONE01 Facebook; PHONE02 TikTok. Lớn: PC04 phim, PHONE04 YouTube |
| 20–25 | PHONE01 xem CAM01; PHONE02 bật/tắt IOT03 2–3 lần |
| 25–40 | PC02 upload tài liệu + sync; PC01 duyệt web; Lớn: PHONE03 backup ảnh, PC03 tải tài liệu, PHONE04 gọi video |
| 40–50 | Mở/đóng cửa (IOT02 sự kiện); PC02 xem CAM02 snapshot; các thiết bị khác tiếp tục video/web |
| 50–58 | Hoạt động giảm dần: tắt video, khóa điện thoại; Lớn: PC05, PHONE05 vẫn duyệt nhẹ |
| 58–60 | Dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 25 GB; dùng Cách B với `-G 1800`.
- [ ] Mở phiên SSH thứ hai từ CAPTURE-SERVER để theo dõi CPU/RAM router (`top -d 10`), lưu output.

### 4.2. Setup device
- [ ] Tất cả thiết bị của cấu hình đã kết nối đúng SSID và IP.
- [ ] Đã chuẩn bị tài khoản/app cho từng hoạt động (video, họp, cloud, camera, dashboard MQTT).
- [ ] Phân công người dùng cho từng thiết bị, phát bảng timeline cho mọi người.
- [ ] Người nghe cuộc gọi/họp ở ngoài mạng nhà đã hẹn giờ.
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
| 4 | Có đủ loại traffic: DNS, TLS/QUIC, UDP media, HTTP camera nội bộ, MQTT | `dns`, `quic`, `stun`, `http && ip.addr in {192.168.10.30 192.168.10.31 192.168.10.32}`, `mqtt` | [ ] |
| 5 | Có giai đoạn nhiều luồng đồng thời (phút 05–40) | I/O Graph tổng + theo từng IP | [ ] |
| 6 | Có lệnh điều khiển IOT03 và phản hồi | `mqtt.topic contains "iot03"` | [ ] |
| 7 | CPU router không vượt 90% kéo dài | Log `top` | [ ] |
| 8 | MQTT nền không bị gián đoạn khi tải cao | `mqtt.topic == "smarthome/iot01/telemetry"` delta time | [ ] |
| 9 | `metadata.csv` có đủ các file của phiên, nhật ký hoạt động đầy đủ | Mở file | [ ] |
