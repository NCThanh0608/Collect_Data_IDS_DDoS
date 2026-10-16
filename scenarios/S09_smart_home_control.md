# S09 – Điều khiển Smart Home (Smart Home Control)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận luồng điều khiển: người dùng mở dashboard, gửi lệnh tới IoT qua broker, thiết bị phản hồi ACK/trạng thái |
| **Cấu hình áp dụng** | Nhỏ (2 thiết bị điều khiển) và Lớn (3 thiết bị điều khiển) |
| **Kịch bản chạy kèm** | S08 |
| **Thời lượng** | 20 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.10.1
                 [Mosquitto broker :1883]
                    ^  cmd ->            <- ack/state
                    |                        |
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.10.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       SSID "SmartHome-User"  (dashboard)       SSID "SmartHome-IoT"
       ● PHONE01  .15  app MQTT dashboard       ● IOT01 .40  nhận lệnh đổi chu kỳ
       ● PC02     .11  MQTT Explorer / web UI   ● IOT02 .41  nhận lệnh arm/disarm
       ○ PC01     .10  chờ                      ● IOT03 .42  nhận lệnh on/off
       ○ PHONE02  .16  chờ                      ○ CAM01–CAM03 .30–.32
       [Lớn: ● PHONE02 .16 dashboard thứ hai; còn lại ○]

Luồng lệnh:  Dashboard --PUBLISH cmd--> Broker --PUBLISH cmd--> IoT
             IoT --PUBLISH ack/state--> Broker --PUBLISH--> Dashboard
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Vai trò trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Broker Mosquitto | 192.168.10.1 | — | Cả hai | Chuyển tiếp lệnh/trạng thái, capture |
| CAPTURE-SERVER | Server capture | 192.168.10.60 | LAN port | Cả hai | Capture |
| PHONE01 | Smartphone | 192.168.10.15 | SmartHome-User | Cả hai | App dashboard MQTT (ví dụ IoT MQTT Panel), client ID `dashboard-phone01` |
| PC02 | PC/Laptop | 192.168.10.11 | SmartHome-User | Cả hai | MQTT Explorer hoặc dashboard web, client ID `dashboard-pc02` |
| PHONE02 | Smartphone | 192.168.10.16 | SmartHome-User | Lớn | Dashboard thứ hai, client ID `dashboard-phone02` |
| IOT01 | Cảm biến môi trường | 192.168.10.40 | SmartHome-IoT | Cả hai | Nhận lệnh đổi chu kỳ publish / yêu cầu đọc ngay |
| IOT02 | Cảm biến cửa / chuyển động | 192.168.10.41 | SmartHome-IoT | Cả hai | Nhận lệnh arm/disarm |
| IOT03 | Ổ cắm / công tắc | 192.168.10.42 | SmartHome-IoT | Cả hai | Nhận lệnh on/off, gửi `ack` và `state` |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | SmartHome-IoT | Cả hai | Nền |

**Lệnh mẫu** (topic `smarthome/<device_id>/cmd`, QoS 1):

| Thiết bị | Payload lệnh | Phản hồi mong đợi |
|---|---|---|
| IOT03 | `{"action":"set","relay":"on"}` / `"off"` | `smarthome/iot03/ack` + `smarthome/iot03/state` |
| IOT01 | `{"action":"read_now"}` | 1 bản tin `smarthome/iot01/telemetry` ngay lập tức |
| IOT02 | `{"action":"arm"}` / `{"action":"disarm"}` | Bản tin trạng thái trên `smarthome/iot02/event` |

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 20 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Số lệnh mỗi phiên | 20–30 lệnh, khoảng cách không đều (20 giây – 2 phút) |
| Dung lượng PCAP ước tính | 50–300 MB |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, dashboard chưa mở |
| 02–05 | PHONE01 mở dashboard (CONNECT, SUBSCRIBE), xem trạng thái, không gửi lệnh |
| 05–10 | PHONE01 bật/tắt IOT03 4–6 lần; gửi `read_now` cho IOT01 2 lần |
| 10–15 | PC02 mở dashboard, arm/disarm IOT02, bật/tắt IOT03 (Lớn: PHONE02 cùng theo dõi) |
| 15–18 | PHONE01 và PC02 xen kẽ gửi lệnh; PHONE01 chuyển app xuống nền rồi mở lại |
| 18–20 | Đóng mọi dashboard (DISCONNECT), dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto chạy, S08 hoạt động; đã tạo tài khoản cho client dashboard.
- [ ] Firewall cho phép SmartHome-User → `192.168.10.1:1883`.

### 4.2. Setup device
- [ ] Cài app dashboard trên PHONE01/PHONE02, MQTT Explorer trên PC02; cấu hình broker, client ID, tài khoản.
- [ ] Tạo sẵn nút/widget cho từng lệnh trong bảng lệnh mẫu.
- [ ] Xác nhận firmware IOT01–IOT03 xử lý được lệnh và gửi phản hồi (thử trước phiên, **không** trong lúc capture).
- [ ] Đóng app dashboard trước khi bắt đầu.
- [ ] Chuẩn bị nhật ký lệnh: giờ:phút:giây | thiết bị gửi | thiết bị nhận | lệnh.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline, ghi mọi lệnh vào nhật ký.
- [ ] Không gửi lệnh dồn dập (tối thiểu 20 giây giữa hai lệnh của cùng một người).

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Trả IOT03 về trạng thái ban đầu, IOT02 về trạng thái mặc định.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S09;S08`, kèm nhật ký lệnh.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 18 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Dashboard CONNECT và SUBSCRIBE từ PHONE01, PC02 (Lớn: PHONE02) | `mqtt.msgtype == 1 \|\| mqtt.msgtype == 8` | [ ] |
| 4 | Số PUBLISH lệnh khớp nhật ký lệnh | `mqtt.topic contains "/cmd"` | [ ] |
| 5 | Mỗi lệnh IOT03 có `ack`/`state` trong ≤ 2 giây | `mqtt.topic contains "iot03"` → so sánh thời gian | [ ] |
| 6 | Lệnh QoS 1 có PUBACK | `mqtt.msgtype == 4` | [ ] |
| 7 | Dashboard DISCONNECT khi đóng app (hoặc timeout keepalive) | `mqtt.msgtype == 14` | [ ] |
| 8 | Telemetry định kỳ của S08 không bị gián đoạn | `mqtt.topic == "smarthome/iot01/telemetry"` | [ ] |
| 9 | Dòng `metadata.csv` và nhật ký lệnh đầy đủ | Mở file | [ ] |
