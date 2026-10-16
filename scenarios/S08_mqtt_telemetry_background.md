# S08 – MQTT telemetry nền (MQTT Background Telemetry)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Duy trì traffic MQTT bình thường của 3 thiết bị IoT xuyên suốt mọi phiên thu: publish định kỳ, publish theo sự kiện, keepalive |
| **Cấu hình áp dụng** | Mọi phiên, mọi cấu hình |
| **Cách chạy** | **Chạy nền liên tục**, có mặt trong `active_scenarios` của mọi phiên. Thêm 1 phiên riêng (S08 + S01) để có baseline MQTT sạch |
| **Thời lượng** | Toàn bộ thời gian các phiên; phiên riêng 60 phút |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.10.1
                 [DHCP/DNS/NTP]
                 [Mosquitto broker :1883]  <==== MQTT (TCP) ====+
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER .60     |
                                  |                             |
                               br-lan                           |
              +-------------------+--------------------+        |
              |                                        |        |
       SSID "SmartHome-User"                    SSID "SmartHome-IoT"   |
       ○ thiết bị người dùng                    ● IOT01 .40 ----+  telemetry định kỳ
       (theo kịch bản chính)                    ● IOT02 .41 ----+  sự kiện cửa/chuyển động
                                                ● IOT03 .42 ----+  trạng thái ổ cắm
                                                ○ CAM01–CAM03 .30–.32

Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

Broker chạy **trên ROUTER** nên mọi luồng IoT ↔ broker đều đi qua `br-lan`.

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Client ID MQTT | Publish | Subscribe | Chu kỳ / điều kiện | QoS |
|---|---|---|---|---|---|---|---|---|
| ROUTER | Broker Mosquitto | 192.168.10.1:1883 | — | — | — | — | — | — |
| IOT01 | Cảm biến môi trường | 192.168.10.40 | SmartHome-IoT | `iot01` | `smarthome/iot01/telemetry` | `smarthome/iot01/cmd` | Cố định 1 giá trị trong {5, 15, 30, 60} giây cho mỗi phiên | 0 |
| IOT02 | Cảm biến cửa / chuyển động | 192.168.10.41 | SmartHome-IoT | `iot02` | `smarthome/iot02/event` | `smarthome/iot02/cmd` | Khi có sự kiện (mở/đóng cửa, chuyển động) | 1 |
| IOT03 | Ổ cắm / công tắc | 192.168.10.42 | SmartHome-IoT | `iot03` | `smarthome/iot03/state`, `smarthome/iot03/ack` | `smarthome/iot03/cmd` | Khi đổi trạng thái + định kỳ 30–60 giây | 1 |

Tất cả thiết bị: keepalive 60 giây, Last Will `smarthome/<device_id>/status` = `offline` (retain), publish `online` (retain) sau khi kết nối.

**Payload mẫu**

```json
// smarthome/iot01/telemetry
{"ts":"2026-10-12T14:58:05+07:00","temp_c":28.4,"humidity":71.2}
// smarthome/iot02/event
{"ts":"2026-10-12T15:02:41+07:00","type":"door","value":"open"}
// smarthome/iot03/state
{"ts":"2026-10-12T15:03:00+07:00","relay":"on","power_w":12.5}
```

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời gian chạy | Bật trước phiên đầu tiên trong ngày, chạy liên tục đến hết ngày thu |
| Phiên riêng | 1 phiên 60 phút / cấu hình, chỉ S08 + S01 (người dùng không thao tác) |
| Chu kỳ IOT01 | Luân phiên giữa các ngày/phiên: 5 s → 15 s → 30 s → 60 s; ghi vào `notes` |
| Sự kiện IOT02 | Tự nhiên trong sinh hoạt; trong phiên riêng tạo 5–10 sự kiện cách nhau không đều (1–10 phút) |
| Dung lượng PCAP ước tính (phiên riêng) | 5–30 MB |

| Mốc (phút, phiên riêng) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture |
| 02–58 | IoT chạy bình thường; mở/đóng cửa hoặc đi qua cảm biến 5–10 lần, ghi giờ |
| 58–60 | Dừng capture |

## 4. Checklist công việc

### 4.1. Setup broker trên ROUTER (một lần)
- [ ] Cài Mosquitto: `opkg update && opkg install mosquitto-nossl mosquitto-client-nossl` (dùng bản `-ssl` nếu triển khai MQTTS 8883).
- [ ] Cấu hình `/etc/mosquitto/mosquitto.conf`: `listener 1883 0.0.0.0`; bật xác thực (`password_file`) cho `iot01`–`iot03` và client dashboard.
- [ ] `/etc/init.d/mosquitto enable && /etc/init.d/mosquitto start`.
- [ ] Firewall: chỉ cho phép zone LAN truy cập cổng 1883 của router.

### 4.2. Setup device
- [ ] IOT01–IOT03 cấu hình broker `192.168.10.1:1883`, client ID, user/password, topic, QoS, keepalive, LWT đúng bảng mục 2.
- [ ] Đồng bộ thời gian trên thiết bị IoT (NTP về ROUTER) để trường `ts` chính xác.
- [ ] Đặt chu kỳ IOT01 cho phiên/ngày hiện tại và ghi lại.
- [ ] Kiểm tra từ ROUTER (qua SSH của CAPTURE-SERVER, không tạo traffic trên `br-lan`):
  ```sh
  mosquitto_sub -h 127.0.0.1 -u <user> -P <pass> -t 'smarthome/#' -v
  ```
  Thấy đủ `status = online` của 3 thiết bị và telemetry của IOT01.

### 4.3. Thực hiện (mỗi ngày thu)
- [ ] Bật IoT trước phiên đầu tiên ít nhất 5 phút.
- [ ] Không khởi động lại broker trong ngày thu (trừ khi ghi vào `notes`).
- [ ] Mỗi phiên: ghi `S08` vào `active_scenarios` và chu kỳ IOT01 vào `notes`.
- [ ] Phiên riêng: thực hiện timeline mục 3, ghi giờ các sự kiện IOT02.

### 4.4. Kết thúc ngày thu
- [ ] Lưu log Mosquitto của ngày (`logread | grep mosquitto`) cùng thư mục PCAP.
- [ ] Ghi chú mọi lần thiết bị IoT mất kết nối ngoài kế hoạch.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | **Mọi PCAP** trong ngày đều có traffic MQTT của cả 3 IoT | `tcp.port == 1883` → Endpoints có .40, .41, .42 | [ ] |
| 2 | IOT01 publish đúng chu kỳ đã cấu hình (sai lệch ≤ 10%) | `mqtt.msgtype == 3 && ip.src == 192.168.10.40` → cột delta time | [ ] |
| 3 | IOT02 publish khớp nhật ký sự kiện (phiên riêng) | `mqtt.topic == "smarthome/iot02/event"` | [ ] |
| 4 | IOT03 publish trạng thái định kỳ 30–60 giây | `mqtt.topic == "smarthome/iot03/state"` | [ ] |
| 5 | Có PINGREQ/PINGRESP khi thiết bị không publish trong 60 giây (IOT02) | `mqtt.msgtype == 12 \|\| mqtt.msgtype == 13` | [ ] |
| 6 | QoS 1 có PUBACK tương ứng | `mqtt.msgtype == 4` | [ ] |
| 7 | Không có DISCONNECT/CONNECT ngoài kế hoạch | `mqtt.msgtype == 1 \|\| mqtt.msgtype == 14` → đối chiếu nhật ký | [ ] |
| 8 | Log Mosquitto và chu kỳ IOT01 được lưu cho từng ngày | Thư mục dữ liệu, `metadata.csv` | [ ] |

> MQTT trên 1883 là bản rõ, Wireshark giải mã được topic/payload. Nếu dùng MQTTS (8883), chỉ kiểm tra được ở mức TLS flow; tiêu chí 2–7 kiểm tra bằng log broker.
