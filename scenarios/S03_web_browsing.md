# S03 – Duyệt web và ứng dụng (Web & App Browsing)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận traffic duyệt web, mạng xã hội, đọc tin: nhiều DNS query, nhiều kết nối HTTPS/QUIC ngắn, có khoảng nghỉ đọc nội dung |
| **Cấu hình áp dụng** | Nhỏ (4 thiết bị chủ động) và Lớn (6 thiết bị chủ động) |
| **Kịch bản chạy kèm** | S08; camera ở trạng thái nền |
| **Thời lượng** | 30 phút / lần |
| **Tài liệu gốc** | [smarthome_normal_traffic_capture_plan.md](../smarthome_normal_traffic_capture_plan.md) |

## 1. Topology

```text
                              INTERNET  (web, mạng xã hội, CDN)
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
       ● LAPTOP01 .10  web tin tức, tìm kiếm    ○ CAM01 .30   ○ IOT01 .40
       ● LAPTOP02 .11  web, thương mại điện tử  ○ CAM02 .31   ○ IOT02 .41
       ● PHONE01  .14  Facebook / Instagram     ○ CAM03 .32   ○ IOT03 .42
       ● PHONE02  .15  báo điện tử / TikTok đọc
       [Lớn: ● LAPTOP04 .13, ● PHONE03 .16; các thiết bị còn lại ○]

Tất cả thiết bị Wi-Fi dùng chung SSID "SmartHome".
Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

## 2. Chi tiết thiết bị

| Device ID | Loại | IP | Mạng | Cấu hình | Hoạt động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.1.1 | — | Cả hai | Gateway, DNS resolver, capture |
| CAPTURE-SERVER | Server capture | 192.168.1.60 | LAN port | Cả hai | Capture |
| LAPTOP01 | Laptop | 192.168.1.10 | SmartHome | Cả hai | Trình duyệt: báo điện tử, Google Search, Wikipedia |
| LAPTOP02 | Laptop | 192.168.1.11 | SmartHome | Cả hai | Trình duyệt: Shopee/Lazada/Tiki, so sánh sản phẩm, đọc review |
| LAPTOP04 | Laptop | 192.168.1.13 | SmartHome | Lớn | Trình duyệt: diễn đàn, tài liệu kỹ thuật, email web |
| PHONE01 | Smartphone | 192.168.1.14 | SmartHome | Cả hai | App Facebook/Instagram: lướt feed, xem ảnh, bình luận |
| PHONE02 | Smartphone | 192.168.1.15 | SmartHome | Cả hai | App báo điện tử, Google News, đọc bài |
| PHONE03 | Smartphone | 192.168.1.16 | SmartHome | Lớn | App Zalo/Messenger nhắn tin, mở link chia sẻ |
| Còn lại (LAPTOP03, PHONE04–06) | — | — | SmartHome | Lớn | Để chờ, không thao tác |
| CAM01–CAM03 | IP camera | 192.168.1.30–32 | SmartHome | Cả hai | Nền, không ai xem |
| IOT01–IOT03 | IoT MQTT | 192.168.1.40–42 | SmartHome | Cả hai | S08 |

**Quy tắc thao tác:** mỗi trang đọc 10–60 giây trước khi chuyển; mỗi thiết bị truy cập ≥ 10 trang/domain khác nhau trong phiên; không tải file lớn, không xem video dài (> 1 phút).

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 30 phút |
| Số lần thu | 2 lần mỗi cấu hình |
| Dung lượng PCAP ước tính | 200 MB – 1 GB / lần |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–02 | Bắt đầu capture, mọi thiết bị chờ |
| 02–10 | LAPTOP01, LAPTOP02 (LAPTOP04) duyệt web |
| 10–20 | PHONE01, PHONE02 (PHONE03) dùng app; laptop đọc chậm, thỉnh thoảng chuyển trang |
| 20–28 | Tất cả thiết bị chủ động cùng duyệt |
| 28–30 | Đóng trình duyệt/app, dừng capture |

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading tắt; đồng hồ các máy lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy, S08 hoạt động.
- [ ] CAPTURE-SERVER còn trống ≥ 2 GB.

### 4.2. Setup device
- [ ] Thiết bị chủ động đã kết nối SmartHome, đúng IP.
- [ ] Trình duyệt laptop: dùng cấu hình mặc định (Chrome/Edge/Firefox), **không** bật VPN hoặc proxy.
- [ ] Smartphone: tắt dữ liệu di động, tắt VPN/Private Relay, đã đăng nhập sẵn app mạng xã hội.
- [ ] Chuẩn bị danh sách website/app cho từng người (không cần cố định, chỉ để đảm bảo đa dạng).
- [ ] Đóng app/tab không liên quan trước khi bắt đầu.

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Thực hiện theo timeline; giữ khoảng nghỉ đọc tự nhiên.
- [ ] Ghi chú nếu có video tự phát dài hoặc tải file ngoài ý muốn.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S03;S08`, ghi số thiết bị chủ động vào `notes`.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 28 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Mỗi thiết bị chủ động có DNS query tới ≥ 10 domain khác nhau | `dns.flags.response == 0 && ip.src == <IP>` | [ ] |
| 4 | Có TLS ClientHello với SNI đa dạng (≥ 30 SNI khác nhau toàn phiên) | `tls.handshake.type == 1` → cột `tls.handshake.extensions_server_name` | [ ] |
| 5 | Có traffic QUIC (UDP 443) | `quic` | [ ] |
| 6 | Traffic dạng bùng nổ ngắn xen khoảng nghỉ, không có đợt tải liên tục > 1 phút | Statistics → I/O Graph theo từng IP | [ ] |
| 7 | Không có flow đơn lẻ > 100 MB | Statistics → Conversations → Bytes | [ ] |
| 8 | MQTT nền vẫn hiện diện | `mqtt.msgtype == 3` | [ ] |
| 9 | Dòng `metadata.csv` đầy đủ | Mở file | [ ] |
