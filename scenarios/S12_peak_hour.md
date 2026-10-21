# S12 – Giờ cao điểm hợp lệ (Legitimate Peak Hour)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận mức tải cao nhất **hợp lệ** của mạng: 8–10 thiết bị người dùng hoạt động nặng cùng lúc, cùng camera và IoT. Dùng làm cận trên của baseline |
| **Cấu hình áp dụng** | **Chỉ cấu hình Lớn** (≥ 8 thiết bị người dùng) |
| **Kịch bản chạy kèm** | S08 + S04, S05, S06, S07, S09 cường độ cao |
| **Thời lượng** | 30 phút / lần (cho phép 20–40 phút) |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET
                                  |
                                (WAN)  ≥ 100 Mbps khuyến nghị
                 ROUTER OpenWrt  192.168.1.1
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.1.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       Người dùng                               Camera, IoT
       ● LAPTOP01 .10  YouTube 1080p            ● CAM01 .30  live view
       ● LAPTOP02 .11  họp video                ● CAM02 .31  snapshot
       ● LAPTOP03 .12  download lớn             ● CAM03 .32  2 viewer
       ● LAPTOP04 .13  phim 1080p               ● IOT01 .40  telemetry 5 s
       ● PHONE01  .14  xem camera               ● IOT02 .41  sự kiện
       ● PHONE02  .15  TikTok                   ● IOT03 .42  nhận lệnh
       ● PHONE03  .16  backup ảnh
       ● PHONE04  .17  gọi video Zalo
       ● PHONE05  .18  dashboard + web
       ● PHONE06  .19  upload video cloud

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Hoạt động trong kịch bản | Nhóm tải |
|---|---|---|---|---|
| LAPTOP01 | Laptop | 192.168.1.10 | YouTube 1080p liên tục | Video |
| LAPTOP02 | Laptop | 192.168.1.11 | Họp video Meet/Zoom, share màn hình 5 phút | Gọi video |
| LAPTOP03 | Laptop | 192.168.1.12 | Download file 200 MB × 2 (tuần tự, qua trình duyệt) | Truyền file |
| LAPTOP04 | Laptop | 192.168.1.13 | Phim trực tuyến 1080p | Video |
| PHONE01 | Smartphone | 192.168.1.14 | Live view CAM01, đổi sang CAM03 | Camera |
| PHONE02 | Smartphone | 192.168.1.15 | TikTok/Reels liên tục | Video |
| PHONE03 | Smartphone | 192.168.1.16 | Backup 100–200 ảnh | Truyền file |
| PHONE04 | Smartphone | 192.168.1.17 | Gọi video Zalo/Messenger (người nghe ở ngoài) | Gọi video |
| PHONE05 | Smartphone | 192.168.1.18 | Dashboard MQTT, điều khiển IOT03; duyệt web | Điều khiển + web |
| PHONE06 | Smartphone | 192.168.1.19 | Upload video ~200 MB lên Google Drive/YouTube | Truyền file |
| CAM01–CAM03 | IP camera | 192.168.1.30–32 | Có viewer trong phần lớn phiên | Camera |
| IOT01 | IoT MQTT | 192.168.1.40 | Telemetry chu kỳ **5 giây** (mức cao nhất của S08) | MQTT |
| IOT02–IOT03 | IoT MQTT | 192.168.1.41–42 | Sự kiện / nhận lệnh | MQTT |
| ROUTER / CAPTURE-SERVER | Router / Server | .1 / .60 | Gateway / capture | — |

> **Không** dùng công cụ tạo tải nhân tạo (iperf, packet generator, speedtest lặp liên tục, nhiều luồng download song song bằng download manager). Mọi tải phải đến từ ứng dụng người dùng thật.

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2–3 lần trong khung 07:00–18:00, xếp lịch trước khi đủ 10 người vận hành thiết bị |
| Dung lượng PCAP ước tính | 10–25 GB / lần |
| Cách lưu | Cách B (script), tách file khi đạt 1000 MB hoặc ngưỡng `--max-file-mb` đã chọn |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, mọi thiết bị đã mở sẵn app nhưng chưa phát |
| 02–05 | Tăng dần: LAPTOP01, LAPTOP04, PHONE02 bắt đầu video |
| 05–10 | LAPTOP02 vào họp; PHONE04 gọi video; PHONE01 xem CAM01 |
| 10–22 | **Đỉnh tải:** LAPTOP03 download, PHONE06 upload, PHONE03 backup; mọi luồng video/gọi tiếp tục; PHONE05 gửi lệnh IOT03 mỗi 1–2 phút; PHONE01 + LAPTOP02 xem CAM03 |
| 22–27 | Giảm dần: kết thúc họp, gọi; truyền file kết thúc tự nhiên |
| 27–30 | Dừng video, dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Xác nhận đang chạy cấu hình Lớn, đủ 10 thiết bị người dùng.
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Đo nhanh khả năng router: CPU khi nhàn rỗi, RAM trống ≥ 30%.
- [ ] Mosquitto chạy, S08 hoạt động, IOT01 đã đặt chu kỳ 5 giây.
- [ ] CAPTURE-SERVER còn trống ≥ 30 GB, ổ ghi đủ nhanh (SSD); CAPTURE-SERVER cắm dây Gigabit.
- [ ] Mở phiên SSH thứ hai từ CAPTURE-SERVER theo dõi `top -d 5`, lưu output.

### 4.2. Setup device
- [ ] Tất cả 16 client đã kết nối đúng SSID/IP ≥ 5 phút trước phiên.
- [ ] Chuẩn bị nội dung: video, phim, file 200 MB, album ảnh, phòng họp, người nghe ngoài mạng SmartHome.
- [ ] Dashboard MQTT trên PHONE05 đã cấu hình sẵn.
- [ ] Phân công người dùng, phát timeline; thống nhất tín hiệu bắt đầu đỉnh tải (phút 10).
- [ ] Smartphone tắt dữ liệu di động; không dùng VPN.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; người điều phối ghi mốc bắt đầu/kết thúc từng nhóm tải.
- [ ] Theo dõi CPU router và drop. Nếu CPU = 100% kéo dài > 2 phút hoặc thấy drop tăng: ghi `notes`, giảm 1–2 luồng video, **không** dừng phiên giữa chừng.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Đặt lại chu kỳ IOT01 theo kế hoạch S08, tạm dừng sync/backup.
- [ ] Thêm dòng `metadata.csv` cho từng file với `active_scenarios = S12;S04;S05;S06;S07;S09;S08`, `n_user_devices = 10`, kèm log CPU.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | Tổng thời lượng ≥ 28 phút, các file liên tục | `capinfos` từng file | [ ] |
| 2 | Drop < 0,1%; nếu vượt, phiên được đánh dấu trong `notes` và thu lại | Số liệu tcpdump | [ ] |
| 3 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 4 | Đủ 16 client xuất hiện | Statistics → Endpoints → IPv4 | [ ] |
| 5 | Throughput đỉnh (phút 10–22) cao hơn đỉnh của S11 cùng cấu hình | I/O Graph, so sánh với S11 | [ ] |
| 6 | Không có dấu hiệu tải nhân tạo: không có iperf (cổng 5201), không có flood gói nhỏ từ một IP | `tcp.port == 5201`; Statistics → Conversations sắp theo Packets | [ ] |
| 7 | IOT01 publish đúng chu kỳ 5 giây cả lúc đỉnh tải | `mqtt.topic == "smarthome/iot01/telemetry"` delta time | [ ] |
| 8 | Lệnh IOT03 có phản hồi ≤ 2 giây cả lúc đỉnh tải | `mqtt.topic contains "iot03"` | [ ] |
| 9 | Log CPU/RAM router được lưu cùng PCAP | Thư mục dữ liệu | [ ] |
| 10 | `metadata.csv` đầy đủ cho mọi file của phiên | Mở file | [ ] |
