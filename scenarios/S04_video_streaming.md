# S04 – Xem video trực tuyến (Video Streaming)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic streaming: tải theo chunk, downlink lớn và kéo dài, thay đổi bitrate khi đổi chất lượng, khoảng dừng khi pause |
| **Cấu hình áp dụng** | Nhỏ (3 thiết bị chủ động) và Lớn (5 thiết bị chủ động) |
| **Kịch bản chạy kèm** | S08; camera ở trạng thái nền |
| **Thời lượng** | 30 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET  (YouTube, Netflix, TikTok, FPT Play...)
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
       ● LAPTOP01 .10  YouTube 1080p            ○ CAM01 .30   ○ IOT01 .40
       ● LAPTOP02 .11  phim (Netflix/FPT Play)  ○ CAM02 .31   ○ IOT02 .41
       ● PHONE01  .14  TikTok / Reels           ○ CAM03 .32   ○ IOT03 .42
       ○ PHONE02  .15  chờ
       [Lớn: ● LAPTOP03 .12 YouTube 4K/auto, ● PHONE03 .16 YouTube app; còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hoạt động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.1.1 | — | Cả hai | Gateway, capture |
| CAPTURE-SERVER | Server capture | 192.168.1.60 | LAN port | Cả hai | Capture |
| LAPTOP01 | Laptop | 192.168.1.10 | SmartHome | Cả hai | YouTube trên trình duyệt, chất lượng 1080p, seek và pause |
| LAPTOP02 | Laptop | 192.168.1.11 | SmartHome | Cả hai | Xem phim dài (Netflix/FPT Play/VieON), đổi tập |
| PHONE01 | Smartphone | 192.168.1.14 | SmartHome | Cả hai | Video ngắn (TikTok/Facebook Reels), vuốt liên tục |
| LAPTOP03 | Laptop | 192.168.1.12 | SmartHome | Lớn | YouTube chất lượng Auto/4K nếu màn hình hỗ trợ |
| PHONE03 | Smartphone | 192.168.1.16 | SmartHome | Lớn | App YouTube, đổi chất lượng 360p ↔ 1080p |
| Còn lại | — | — | SmartHome | Cả hai | Để chờ |
| CAM01–CAM03 | IP camera | 192.168.1.30–32 | SmartHome | Cả hai | Nền |
| IOT01–IOT03 | IoT MQTT | 192.168.1.40–42 | SmartHome | Cả hai | S08 |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Dung lượng PCAP ước tính | 2–6 GB (Nhỏ), 4–10 GB (Lớn) |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, thiết bị chờ |
| 02–08 | LAPTOP01 phát YouTube 1080p; LAPTOP02 bắt đầu phim |
| 08–10 | LAPTOP01 **pause 2 phút**; LAPTOP02 tiếp tục |
| 10–18 | LAPTOP01 resume, seek 2–3 lần; PHONE01 (PHONE03) bắt đầu video |
| 18–22 | Đổi chất lượng: LAPTOP01 1080p → 480p → Auto; PHONE03 360p → 1080p |
| 22–28 | Tất cả thiết bị chủ động phát đồng thời; LAPTOP02 chuyển tập/phim khác |
| 28–30 | Dừng phát, dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 12 GB; ưu tiên Cách B (`-G`) để tách file.
- [ ] Kiểm tra đường truyền Internet đủ cho các luồng đồng thời (≥ 50 Mbps với cấu hình Lớn).

### 4.2. Setup device
- [ ] Thiết bị chủ động kết nối SmartHome, đúng IP; tắt dữ liệu di động trên smartphone.
- [ ] Không dùng VPN; không tải trước video (chế độ offline/download).
- [ ] Đăng nhập sẵn tài khoản dịch vụ video; chuẩn bị sẵn danh sách video/phim.
- [ ] Tắt tự động cập nhật ứng dụng trong thời gian thu (nếu được).

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; ghi giờ pause/resume và đổi chất lượng vào nhật ký.
- [ ] Theo dõi CPU router từ CAPTURE-SERVER (`top -d 5`); ghi chú nếu > 90%.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S04;S08`, kèm nhật ký thao tác.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 28 phút (tổng các file), không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Mỗi thiết bị chủ động có downlink kéo dài ≥ 5 phút | Statistics → I/O Graph, lọc `ip.dst == <IP>` | [ ] |
| 4 | Có luồng QUIC/TLS tới CDN video (ví dụ `googlevideo.com`) | `tls.handshake.extensions_server_name contains "video"` hoặc `quic` | [ ] |
| 5 | Thấy khoảng giảm traffic khi LAPTOP01 pause (phút 08–10) | I/O Graph `ip.addr == 192.168.1.10` | [ ] |
| 6 | Thấy thay đổi throughput khi đổi chất lượng (phút 18–22) | I/O Graph | [ ] |
| 7 | MQTT nền vẫn đều đặn, không bị gián đoạn khi tải cao | `mqtt.msgtype == 3` | [ ] |
| 8 | CPU router không vượt 90% kéo dài | Nhật ký `top` | [ ] |
| 9 | Dòng `metadata.csv` và nhật ký thao tác đầy đủ | Mở file | [ ] |
