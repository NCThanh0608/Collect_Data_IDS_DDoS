# S06 – Gọi thoại và gọi video (Voice & Video Call)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic thời gian thực: luồng UDP hai chiều tốc độ gói ổn định, STUN/TURN, thay đổi bitrate khi bật/tắt camera và chia sẻ màn hình |
| **Cấu hình áp dụng** | Nhỏ (2 thiết bị chủ động) và Lớn (3 thiết bị chủ động) |
| **Kịch bản chạy kèm** | S08; camera ở trạng thái nền |
| **Thời lượng** | 30 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET  (Google Meet, Zoom, Teams, Zalo, Messenger)
                                  |                      \
                                (WAN)                     \__ Người nghe/nhóm họp
                 ROUTER OpenWrt  192.168.10.1                  BÊN NGOÀI mạng SmartHome (4G/mạng khác)
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.10.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       Người dùng                               Camera, IoT
       ● LAPTOP02 .11  họp video + share màn hình  ○ CAM01 .30   ○ IOT01 .40
       ● PHONE01  .14  gọi thoại/video Zalo        ○ CAM02 .31   ○ IOT02 .41
       ○ LAPTOP01 .10  chờ                         ○ CAM03 .32   ○ IOT03 .42
       ○ PHONE02  .15  chờ
       [Lớn: ● LAPTOP01 .10 tham gia họp nhóm; còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

> **Bên kia cuộc gọi phải ở ngoài mạng SmartHome** (dùng 4G hoặc mạng khác của lab). Nếu hai thiết bị trong mạng SmartHome gọi nhau, luồng P2P đi thẳng trong Wi-Fi và không xuất hiện trên `br-lan`.

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hoạt động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.10.1 | — | Cả hai | Gateway, capture |
| CAPTURE-SERVER | Server capture | 192.168.10.60 | LAN port | Cả hai | Capture |
| LAPTOP02 | Laptop | 192.168.10.11 | SmartHome | Cả hai | Google Meet/Zoom/Teams: bật camera, tắt camera, chia sẻ màn hình |
| PHONE01 | Smartphone | 192.168.10.14 | SmartHome | Cả hai | Gọi thoại rồi gọi video qua Zalo/Messenger |
| LAPTOP01 | Laptop | 192.168.10.10 | SmartHome | Lớn | Tham gia cuộc họp nhóm cùng LAPTOP02 (ứng dụng desktop) |
| Đối tác ngoài | Thiết bị bên ngoài | — | 4G/mạng khác | Cả hai | Đầu bên kia của cuộc gọi |
| Còn lại | — | — | SmartHome | Cả hai | Để chờ |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | SmartHome | Cả hai | Nền |
| IOT01–IOT03 | IoT MQTT | 192.168.10.40–42 | SmartHome | Cả hai | S08 |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2 lần mỗi cấu hình (đổi ứng dụng họp giữa các lần) |
| Dung lượng PCAP ước tính | 300 MB – 1,5 GB / lần |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, thiết bị chờ |
| 02–06 | LAPTOP02 vào phòng họp, bật camera + mic |
| 06–08 | LAPTOP02 **tắt camera**, giữ mic |
| 08–11 | LAPTOP02 bật lại camera, **chia sẻ màn hình** 3 phút |
| 11–12 | LAPTOP02 rời cuộc họp |
| 12–16 | PHONE01 gọi **thoại** Zalo/Messenger |
| 16–20 | PHONE01 chuyển sang gọi **video** |
| 20–28 | Họp nhóm: LAPTOP02 + LAPTOP01 (Lớn) + đối tác ngoài, bật/tắt camera một lần |
| 28–30 | Kết thúc cuộc gọi, dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 3 GB.

### 4.2. Setup device
- [ ] Cài và đăng nhập sẵn ứng dụng họp/gọi trên LAPTOP01, LAPTOP02, PHONE01.
- [ ] Chuẩn bị phòng họp/link họp và hẹn giờ với người ở ngoài mạng SmartHome.
- [ ] Xác nhận thiết bị bên kia **không** kết nối SSID SmartHome.
- [ ] PHONE01: tắt dữ liệu di động để cuộc gọi chắc chắn đi qua Wi-Fi.
- [ ] Không dùng VPN.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; ghi giờ bật/tắt camera, chia sẻ màn hình, đổi loại cuộc gọi.
- [ ] Ghi tên ứng dụng họp/gọi đã dùng.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S06;S08`, `notes` ghi ứng dụng sử dụng.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 28 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Có STUN/TURN khi bắt đầu cuộc gọi | `stun` hoặc `udp.port == 3478 \|\| udp.port == 19302` | [ ] |
| 4 | Có luồng UDP hai chiều kéo dài, tốc độ gói ổn định cho LAPTOP02 và PHONE01 | Statistics → Conversations → UDP, Duration ≥ 3 phút | [ ] |
| 5 | Thấy throughput giảm khi tắt camera (phút 06–08) và tăng khi share màn hình | I/O Graph `ip.addr == 192.168.10.11` | [ ] |
| 6 | Thấy khác biệt thoại (phút 12–16) và video (16–20) của PHONE01 | I/O Graph `ip.addr == 192.168.10.14` | [ ] |
| 7 | Không có luồng media đi trực tiếp giữa hai IP nội bộ (đối tác ở ngoài) | `ip.src == 192.168.10.0/24 && ip.dst == 192.168.10.0/24 && udp` → chỉ DNS/NTP/MQTT | [ ] |
| 8 | MQTT nền vẫn đều đặn | `mqtt.msgtype == 3` | [ ] |
| 9 | Dòng `metadata.csv` và nhật ký thao tác đầy đủ | Mở file | [ ] |
