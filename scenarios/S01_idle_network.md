# S01 – Mạng nhàn rỗi (Idle Network)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic nền khi không ai chủ động sử dụng: keepalive, DNS, NTP, push notification, đồng bộ nền, MQTT nền |
| **Cấu hình áp dụng** | Nhỏ và Lớn (thu cả hai) |
| **Kịch bản chạy kèm** | S08 (MQTT nền) |
| **Thời lượng** | 30 phút / lần |
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
       ○ PC01     .10  chờ, không mở app        ○ CAM01 .30   ○ IOT01 .40
       ○ PC02     .11  chờ, không mở app        ○ CAM02 .31   ○ IOT02 .41
       ○ PHONE01  .15  khóa màn hình            ○ CAM03 .32   ○ IOT03 .42
       ○ PHONE02  .16  khóa màn hình
       [Lớn: + PC03 .12, PC04 .13, PC05 .14, PHONE03–05 .17–.19]

Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Trạng thái trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.10.1 | — | Cả hai | Gateway, DHCP/DNS/NTP, broker, capture `br-lan` |
| CAPTURE-SERVER | Server capture | 192.168.10.60 | LAN port | Cả hai | Nhận PCAP qua SSH, không dùng cho việc khác |
| PC01–PC02 | PC/Laptop | 192.168.10.10–11 | SmartHome-User | Cả hai | Bật, đăng nhập, đóng toàn bộ trình duyệt/app; laptop cắm sạc, không cho sleep |
| PC03–PC05 | PC/Laptop | 192.168.10.12–14 | SmartHome-User | Lớn | Như PC01 |
| PHONE01–PHONE02 | Smartphone | 192.168.10.15–16 | SmartHome-User | Cả hai | Khóa màn hình, giữ Wi-Fi, app chạy nền như thường ngày |
| PHONE03–PHONE05 | Smartphone | 192.168.10.17–19 | SmartHome-User | Lớn | Như PHONE01 |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | SmartHome-IoT | Cả hai | Bật, **không có ai xem** |
| IOT01–IOT03 | IoT MQTT | 192.168.10.40–42 | SmartHome-IoT | Cả hai | Chạy S08 bình thường |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2 lần mỗi cấu hình: 1 lần buổi sáng (07:00–11:00), 1 lần buổi chiều (13:00–18:00) |
| Dung lượng PCAP ước tính | 20–150 MB / lần |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, xác nhận có gói, không ai chạm vào thiết bị |
| 02–28 | Không thao tác. Chỉ quan sát CPU router từ CAPTURE-SERVER |
| 28–30 | Dừng capture, ghi số liệu |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading đang tắt: `uci get firewall.@defaults[0].flow_offloading` và `flow_offloading_hw` đều trả về `0`.
- [ ] Đồng hồ ROUTER, CAPTURE-SERVER, PC/laptop lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy trên ROUTER: `/etc/init.d/mosquitto status`.
- [ ] CAPTURE-SERVER còn trống ≥ 1 GB.
- [ ] Chỉ CAPTURE-SERVER được SSH vào router trong suốt phiên (SSH từ máy khác sẽ lọt vào PCAP).

### 4.2. Setup device
- [ ] Tất cả thiết bị của cấu hình đã kết nối đúng SSID và nhận đúng IP (kiểm tra `Network → DHCP Leases` trên LuCI).
- [ ] PC/laptop: đóng trình duyệt, app chat, app cloud **để nguyên trạng thái mặc định** (không tắt dịch vụ nền của hệ điều hành).
- [ ] PC/Laptop: tắt chế độ sleep trong thời gian thu.
- [ ] Smartphone: không bật chế độ máy bay/tiết kiệm dữ liệu; khóa màn hình trước khi bắt đầu.
- [ ] Camera: đóng toàn bộ app/tab xem camera trên mọi thiết bị.
- [ ] Thông báo người trong nhà không dùng mạng trong 30 phút.

### 4.3. Thực hiện
- [ ] Tạo `session_id` mới, bắt đầu capture (Cách A hoặc B, mục 5.2 tài liệu gốc), ghi `start_time`.
- [ ] Phút 2: kiểm tra Wireshark/tcpdump đang nhận gói.
- [ ] Không thao tác trên thiết bị đến hết phút 28. Nếu có người dùng thiết bị, ghi giờ và lý do vào `notes`.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng vào `metadata.csv` với `active_scenarios = S01;S08`.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | Thời lượng PCAP ≥ 28 phút, file không rỗng | `capinfos <file>.pcap` | [ ] |
| 2 | Dropped by kernel < 0,1% | Số liệu tcpdump lúc dừng | [ ] |
| 3 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 4 | Cả 3 IoT publish đều đặn | `mqtt.msgtype == 3` → có từ .40, .41 (nếu có sự kiện), .42 | [ ] |
| 5 | Có DNS và NTP | `dns`, `ntp` → có gói | [ ] |
| 6 | ≥ 90% thiết bị của cấu hình xuất hiện | Statistics → Endpoints → IPv4 | [ ] |
| 7 | Không có flow lớn bất thường (> 50 MB) từ thiết bị người dùng | Statistics → Conversations → sắp xếp theo Bytes | [ ] |
| 8 | Throughput trung bình thấp, không có đợt tải kéo dài | Statistics → I/O Graph | [ ] |
| 9 | Phiên nằm trong khung 07:00–18:00; dòng `metadata.csv` đầy đủ, khung giờ (sáng/chiều) ghi trong `notes` | Mở file | [ ] |

> Nếu tiêu chí 7 không đạt do cập nhật hệ điều hành tự động: ghi vào `notes` và thu lại phiên khác, không xóa file.
