# S05 – Truyền file và đồng bộ cloud (File Transfer & Cloud Sync)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận các flow dung lượng lớn một chiều: download, upload, backup ảnh, đồng bộ thư mục cloud |
| **Cấu hình áp dụng** | Nhỏ (2 thiết bị chủ động) và Lớn (3 thiết bị chủ động) |
| **Kịch bản chạy kèm** | S08; camera ở trạng thái nền |
| **Thời lượng** | 25 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET  (Google Drive, OneDrive, iCloud/Google Photos, server file)
                                  |
                                (WAN)
                 ROUTER OpenWrt  192.168.10.1
                 [DHCP/DNS/NTP] [Mosquitto :1883]
                 [tcpdump br-lan] <----SSH---- CAPTURE-SERVER 192.168.10.60 (LAN port)
                                  |
                               br-lan
              +-------------------+--------------------+
              |                                        |
       Người dùng                               Camera, IoT
       ● LAPTOP01 .10  download 5/50/200 MB     ○ CAM01 .30   ○ IOT01 .40
       ● LAPTOP02 .11  upload + sync thư mục    ○ CAM02 .31   ○ IOT02 .41
       ○ PHONE01  .14  chờ (Nhỏ)                ○ CAM03 .32   ○ IOT03 .42
       ○ PHONE02  .15  chờ
       [Lớn: ● PHONE01 .14 backup ảnh; còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hoạt động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.10.1 | — | Cả hai | Gateway, capture |
| CAPTURE-SERVER | Server capture | 192.168.10.60 | LAN port | Cả hai | Capture |
| LAPTOP01 | Laptop | 192.168.10.10 | SmartHome | Cả hai | Download qua trình duyệt 3 file 5 MB, 50 MB, 200 MB (lần lượt) |
| LAPTOP02 | Laptop | 192.168.10.11 | SmartHome | Cả hai | Upload 50 MB lên Google Drive/OneDrive; bật sync thư mục ~100 MB |
| PHONE01 | Smartphone | 192.168.10.14 | SmartHome | Lớn | Backup ~50–100 ảnh qua Google Photos/iCloud |
| Còn lại | — | — | SmartHome | Cả hai | Để chờ |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | SmartHome | Cả hai | Nền |
| IOT01–IOT03 | IoT MQTT | 192.168.10.40–42 | SmartHome | Cả hai | S08 |

**Nguồn file download:** file kiểm thử công khai qua HTTPS (ví dụ file test của nhà cung cấp hosting) hoặc file đặt sẵn trên cloud cá nhân. **Không** dùng công cụ đo băng thông dạng flood (iperf, speedtest đa luồng liên tục).

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 25 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Dung lượng PCAP ước tính | 0,8–1,5 GB (Nhỏ), 1,2–2 GB (Lớn) |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, thiết bị chờ |
| 02–09 | LAPTOP01 download 5 MB → nghỉ 30 giây → 50 MB → nghỉ 30 giây → 200 MB |
| 09–15 | LAPTOP02 upload file 50 MB lên cloud qua trình duyệt |
| 15–21 | PHONE01 backup ảnh (Lớn); LAPTOP02 thả thư mục ~100 MB vào thư mục sync |
| 21–23 | LAPTOP01 mở cloud xem file vừa tải lên, tải về lại 1 file nhỏ |
| 23–25 | Dừng hoạt động, dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 3 GB.

### 4.2. Setup device
- [ ] Chuẩn bị sẵn file 5/50/200 MB (link download) và file/thư mục upload; ghi tên file + dung lượng vào nhật ký.
- [ ] LAPTOP02 đã cài và đăng nhập client sync (Google Drive for Desktop/OneDrive), **tạm dừng sync** trước phiên.
- [ ] PHONE01: tắt backup tự động trước phiên, chuẩn bị album ảnh để backup; tắt dữ liệu di động.
- [ ] Xóa file đã tải ở phiên trước để tránh trình duyệt bỏ qua download.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; ghi giờ bắt đầu/kết thúc từng lần truyền file.
- [ ] Bật lại sync/backup đúng mốc thời gian, không bật sớm.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Tạm dừng lại sync/backup để không ảnh hưởng phiên sau.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S05;S08`, kèm nhật ký file.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 23 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Có 3 flow download của LAPTOP01 với dung lượng xấp xỉ 5/50/200 MB | Statistics → Conversations, lọc `ip.addr == 192.168.10.10`, sắp xếp Bytes B→A | [ ] |
| 4 | Có flow upload của LAPTOP02 với bytes chiều lên ≈ 50 MB | Conversations, cột Bytes A→B | [ ] |
| 5 | Có traffic sync thư mục / backup ảnh tới domain cloud | `tls.handshake.extensions_server_name` chứa `drive`/`onedrive`/`photos`/`icloud` | [ ] |
| 6 | Thời gian các đợt truyền khớp nhật ký (sai lệch ≤ 10 giây) | I/O Graph | [ ] |
| 7 | MQTT nền vẫn đều đặn trong lúc truyền file | `mqtt.msgtype == 3` | [ ] |
| 8 | Dòng `metadata.csv` và nhật ký file đầy đủ | Mở file | [ ] |
