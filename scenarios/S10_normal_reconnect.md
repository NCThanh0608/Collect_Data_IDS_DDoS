# S10 – Kết nối lại bình thường (Normal Reconnect)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận hành vi khi thiết bị ngủ/thức, tắt/bật Wi-Fi, mất nguồn ngắn: DHCP lại, DNS lại, TCP/MQTT reconnect, LWT `offline`/`online` |
| **Cấu hình áp dụng** | Nhỏ và Lớn |
| **Kịch bản chạy kèm** | S08 |
| **Thời lượng** | 15 phút / lần |
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
       ● PHONE01  .14  khóa/mở màn hình         ● IOT03 .42  ngắt nguồn 2 phút
       ● PHONE02  .15  tắt/bật Wi-Fi            ● CAM02 .31  khởi động lại
       ○ LAPTOP01 .10  chờ                      ○ CAM01, CAM03, IOT01, IOT02
       ○ LAPTOP02 .11  chờ
       [Lớn: ● PHONE03 .16 tắt/bật Wi-Fi; còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hành động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.1.1 | — | Cả hai | DHCP, broker (phát LWT), capture |
| CAPTURE-SERVER | Server capture | 192.168.1.60 | LAN port | Cả hai | Capture |
| PHONE01 | Smartphone | 192.168.1.14 | SmartHome | Cả hai | Khóa màn hình 2 phút → mở, lặp 2 lần |
| PHONE02 | Smartphone | 192.168.1.15 | SmartHome | Cả hai | Tắt Wi-Fi 60 giây → bật lại |
| PHONE03 | Smartphone | 192.168.1.16 | SmartHome | Lớn | Tắt Wi-Fi 60 giây → bật lại (lệch 1 phút so với PHONE02) |
| IOT03 | Ổ cắm / công tắc | 192.168.1.42 | SmartHome | Cả hai | Rút nguồn **2 phút** (> 1,5 × keepalive để broker phát LWT) → cắm lại |
| CAM02 | IP camera | 192.168.1.31 | SmartHome | Cả hai | Khởi động lại từ app/web UI (nếu firmware hỗ trợ) hoặc rút nguồn 1 phút |
| Còn lại | — | — | — | Cả hai | Nền |

> Chỉ thực hiện mức gián đoạn của sinh hoạt bình thường. **Không** tắt/bật liên tục với tần suất cao, không gây mất kết nối cho thiết bị khác.

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 15 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Dung lượng PCAP ước tính | 30–200 MB |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–01 | Bắt đầu capture, mọi thiết bị đang kết nối bình thường |
| 01–03 | PHONE01 khóa màn hình |
| 03–04 | PHONE01 mở màn hình, mở 1 app bất kỳ |
| 04–06 | PHONE01 khóa màn hình lần 2, rồi mở lại |
| 06–08 | PHONE02 tắt Wi-Fi 60 giây → bật lại (Lớn: PHONE03 tắt ở phút 07, bật ở phút 08) |
| 08–10 | IOT03 rút nguồn |
| 10–11 | IOT03 cắm lại nguồn, chờ reconnect |
| 11–13 | CAM02 khởi động lại |
| 13–15 | Quan sát tất cả thiết bị trở lại bình thường; dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto chạy, S08 hoạt động; LWT đã cấu hình cho IOT03 (keepalive 60 giây).
- [ ] CAPTURE-SERVER còn trống ≥ 1 GB.

### 4.2. Setup device
- [ ] Tất cả thiết bị đã kết nối ổn định ≥ 5 phút trước phiên.
- [ ] Smartphone: tắt dữ liệu di động (tránh chuyển sang 4G khi tắt Wi-Fi).
- [ ] Xác định cách khởi động lại CAM02 (nút trong app/web UI hay rút nguồn), ghi vào nhật ký.
- [ ] IOT03 cắm qua ổ có công tắc để thao tác ngắt nguồn dễ dàng.
- [ ] Chuẩn bị nhật ký thời gian (giờ:phút:giây | thiết bị | hành động).

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline, ghi giờ chính xác từng thao tác.
- [ ] Xác nhận trên LuCI các thiết bị đã quay lại mạng với đúng IP.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S10;S08`, kèm nhật ký thời gian.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 14 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | PHONE01: thấy traffic giảm khi khóa màn hình và tăng (push/sync) khi mở | I/O Graph `ip.addr == 192.168.1.14` | [ ] |
| 4 | PHONE02 (PHONE03): có DHCP Request/ACK sau khi bật Wi-Fi | `dhcp && eth.addr == <MAC>` | [ ] |
| 5 | Broker phát LWT `offline` cho IOT03 khoảng 90 giây sau khi rút nguồn | `mqtt.topic == "smarthome/iot03/status"` | [ ] |
| 6 | IOT03 có DHCP, MQTT CONNECT và `online` sau khi cắm lại | `ip.addr == 192.168.1.42 && (dhcp \|\| mqtt.msgtype == 1)` | [ ] |
| 7 | CAM02 có khoảng im lặng rồi xuất hiện lại (DHCP/DNS/kết nối cloud) | I/O Graph `ip.addr == 192.168.1.31` | [ ] |
| 8 | Thời gian các sự kiện khớp nhật ký (sai lệch ≤ 5 giây) | So sánh nhật ký | [ ] |
| 9 | Dòng `metadata.csv` và nhật ký thời gian đầy đủ | Mở file | [ ] |
