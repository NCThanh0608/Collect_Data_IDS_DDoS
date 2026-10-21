# S07 – Camera IP qua HTTP(S) (IP Camera Viewing)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic camera: trạng thái nền, live view, HTTP snapshot định kỳ, nhiều người xem đồng thời, truy cập dashboard |
| **Cấu hình áp dụng** | Nhỏ (2 viewer) và Lớn (3 viewer) |
| **Kịch bản chạy kèm** | S08 |
| **Thời lượng** | 30 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET  (cloud của hãng camera, nếu có)
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.1.1
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.1.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       Người dùng  (viewer)                     Camera, IoT
       ● PHONE01  .14  app camera  ---------->  ● CAM01 .30  live view
       ● LAPTOP02 .11  trình duyệt ---------->  ● CAM02 .31  snapshot / live
       ○ LAPTOP01 .10  chờ          (cả hai)->  ● CAM03 .32  2 người xem
       ○ PHONE02  .15  chờ                      ○ IOT01–IOT03 .40–.42
       [Lớn: ● PHONE02 .15 xem CAM03 cùng LAPTOP02; còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

> **Giới hạn của SSID chung:** khi viewer và camera đều dùng Wi-Fi, luồng xem camera trực tiếp trong LAN **không xuất hiện trên `br-lan`**. PCAP vẫn có: DNS/DHCP/NTP của camera, kết nối camera ↔ cloud, app viewer ↔ cloud của hãng. Muốn thu luồng LAN camera ↔ viewer thì cắm dây camera vào cổng LAN của router và ghi vào `devices.csv`.

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hoạt động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.1.1 | — | Cả hai | Gateway, capture |
| CAPTURE-SERVER | Server capture | 192.168.1.60 | LAN port | Cả hai | Capture |
| CAM01 | IP camera | 192.168.1.30 | SmartHome | Cả hai | Nền: kiểm tra trạng thái theo app. Chủ động: PHONE01 live view |
| CAM02 | IP camera | 192.168.1.31 | SmartHome | Cả hai | Nền: HTTP status/snapshot. Chủ động: LAPTOP02 xem snapshot (2–10 giây) hoặc live view |
| CAM03 | IP camera | 192.168.1.32 | SmartHome | Cả hai | Nền: keepalive/cloud. Chủ động: 2 người xem đồng thời nếu firmware cho phép |
| PHONE01 | Smartphone | 192.168.1.14 | SmartHome | Cả hai | App của hãng camera hoặc app xem HTTP/MJPEG |
| LAPTOP02 | Laptop | 192.168.1.11 | SmartHome | Cả hai | Trình duyệt truy cập web UI camera / dashboard |
| PHONE02 | Smartphone | 192.168.1.15 | SmartHome | Lớn | Viewer thứ hai cho CAM03 |
| Còn lại | — | — | SmartHome | Cả hai | Để chờ |
| IOT01–IOT03 | IoT MQTT | 192.168.1.40–42 | SmartHome | Cả hai | S08 |

**Ghi nhận trước phiên (một lần):** với mỗi camera, ghi vào `devices.csv` (`notes`) giao thức thực tế: `HTTP snapshot` / `MJPEG over HTTP` / `HTTPS` / `Cloud P2P`, cổng sử dụng, có hỗ trợ nhiều viewer không. Chỉ dùng chức năng firmware thực sự hỗ trợ.

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Dung lượng PCAP ước tính | 0,5–3 GB / lần (phụ thuộc độ phân giải camera) |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, camera chạy nền, không ai xem |
| 02–06 | PHONE01 mở live view CAM01 |
| 06–07 | PHONE01 thoát live view |
| 07–10 | PHONE01 mở lại live view CAM01, rồi đổi sang CAM02 |
| 10–18 | LAPTOP02 mở web UI CAM02: xem snapshot (tự refresh 2–10 giây) hoặc live view, chuyển trang cấu hình/trạng thái 2–3 lần |
| 18–26 | LAPTOP02 + PHONE01 (Lớn: + PHONE02) cùng xem CAM03 |
| 26–30 | Thoát mọi app/tab camera, camera về trạng thái nền; dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy, S08 hoạt động.
- [ ] Viewer mở được app/web UI của từng camera (thử trước phiên, không trong lúc capture).
- [ ] CAPTURE-SERVER còn trống ≥ 4 GB.

### 4.2. Setup device
- [ ] CAM01–CAM03 bật, kết nối SmartHome, đúng IP; đã ghi giao thức thực tế vào `devices.csv`.
- [ ] PHONE01/PHONE02 cài và đăng nhập app camera; tắt dữ liệu di động.
- [ ] LAPTOP02 lưu sẵn URL web UI camera (ví dụ `http://192.168.1.31/`), đã đăng nhập thử.
- [ ] Đóng toàn bộ app/tab xem camera trước khi bắt đầu.
- [ ] Nếu camera chỉ dùng cloud/P2P: ghi rõ vào `notes`, chấp nhận luồng đi qua Internet.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; ghi giờ mở/đóng live view, đổi camera.
- [ ] Không thay đổi cấu hình camera (độ phân giải, bitrate) trong phiên.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S07;S08`, kèm nhật ký thao tác.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 28 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Camera cắm dây: thấy luồng camera ↔ viewer trong LAN. Camera Wi-Fi: **không áp dụng** (ghi chú trong `notes`) | `ip.addr == 192.168.1.30 && ip.addr == 192.168.1.14` | [ ] |
| 4 | Có HTTP request snapshot/stream tới CAM02 với chu kỳ đều | `http.request && ip.dst == 192.168.1.31` | [ ] |
| 5 | Có ≥ 2 viewer đồng thời với CAM03 (phút 18–26) | Conversations lọc `ip.addr == 192.168.1.32` | [ ] |
| 6 | Thấy traffic camera giảm về mức nền khi thoát app (phút 26–30) | I/O Graph `ip.src in {192.168.1.30 192.168.1.31 192.168.1.32}` | [ ] |
| 7 | Cả 3 camera đều xuất hiện trong PCAP | Statistics → Endpoints | [ ] |
| 8 | MQTT nền vẫn đều đặn | `mqtt.msgtype == 3` | [ ] |
| 9 | Dòng `metadata.csv`, nhật ký và `devices.csv` (giao thức camera) đầy đủ | Mở file | [ ] |

> Nếu camera cắm dây mà tiêu chí 3 vẫn không đạt: kiểm tra flow offloading và cổng LAN của camera, sau đó thu lại.
