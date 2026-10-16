# S02 – Thiết bị kết nối mạng, DHCP/DNS (Device Onboarding)

| Thuộc tính | Giá trị |
|---|---|
| **Mục tiêu** | Ghi nhận quá trình thiết bị khởi động, kết nối Wi-Fi, nhận IP qua DHCP, truy vấn DNS đầu tiên, kết nối dịch vụ (MQTT CONNECT, cloud camera, push) |
| **Cấu hình áp dụng** | Nhỏ và Lớn |
| **Kịch bản chạy kèm** | S08 (bắt đầu ngay khi IoT kết nối lại) |
| **Thời lượng** | 15 phút / lần |
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
       ● PC01     .10  khởi động lại            ● CAM01 .30   ● IOT01 .40
       ● PC02     .11  bật Wi-Fi                ● CAM02 .31   ● IOT02 .41
       ● PHONE01  .15  bật Wi-Fi                ● CAM03 .32   ● IOT03 .42
       ● PHONE02  .16  bật Wi-Fi                (cấp nguồn lần lượt)
       [Lớn: + PC03 .12, PC04 .13, PC05 .14, PHONE03–05 .17–.19]

Chú thích: ● hoạt động chủ động   ○ chỉ có traffic nền
```

Thứ tự kết nối: **IoT → Camera → Thiết bị người dùng**, mỗi thiết bị cách nhau 30–60 giây để dễ đối chiếu.

## 2. Chi tiết thiết bị

| Device ID | Loại | IP (static lease) | Mạng | Cấu hình | Hành động trong kịch bản |
|---|---|---|---|---|---|
| ROUTER | Router OpenWrt | 192.168.10.1 | — | Cả hai | Cấp DHCP, DNS, broker; **không reboot** |
| CAPTURE-SERVER | Server capture | 192.168.10.60 | LAN port | Cả hai | Capture, bắt đầu **trước** khi thiết bị kết nối |
| IOT01–IOT03 | IoT MQTT | 192.168.10.40–42 | SmartHome-IoT | Cả hai | Tắt nguồn trước phiên, cấp nguồn lại lần lượt |
| CAM01–CAM03 | IP camera | 192.168.10.30–32 | SmartHome-IoT | Cả hai | Tắt nguồn trước phiên, cấp nguồn lại lần lượt |
| PC01–PC05 | PC/Laptop | 192.168.10.10–14 | SmartHome-User | PC03–PC05: Lớn | Tắt Wi-Fi (hoặc rút cáp mạng) trước phiên; khởi động lại hoặc bật Wi-Fi khi đến lượt |
| PHONE01–PHONE05 | Smartphone | 192.168.10.15–19 | SmartHome-User | PHONE03–05: Lớn | Tắt Wi-Fi trước phiên, bật lại |

> Thiết bị quay lại mạng với lease còn hạn thường chỉ gửi DHCP **Request/ACK**. Để có đủ chuỗi **Discover/Offer/Request/ACK**, chọn "Quên mạng" (forget network) trên 1–2 smartphone rồi kết nối lại. Ghi rõ thiết bị nào đã làm việc này vào `notes`.

## 3. Thời gian thu

| Hạng mục | Giá trị |
|---|---|
| Thời lượng một lần thu | 15 phút |
| Số lần thu | 2 lần mỗi cấu hình (khác ngày) |
| Dung lượng PCAP ước tính | 50–300 MB / lần (phụ thuộc cập nhật khi thiết bị khởi động) |

| Mốc (phút) | Hoạt động |
|---|---|
| 00–01 | Bắt đầu capture khi mọi client đã ngắt kết nối (chỉ còn ROUTER, CAPTURE-SERVER) |
| 01–03 | Cấp nguồn IOT01 → IOT02 → IOT03 (cách nhau 30–60 giây) |
| 03–05 | Cấp nguồn CAM01 → CAM02 → CAM03 |
| 05–11 | Thiết bị người dùng kết nối lần lượt: PC01, PC02, PHONE01, PHONE02 (Lớn: thêm PC03, PC04, PC05, PHONE03–05) |
| 11–14 | Không thao tác, quan sát traffic sau khi kết nối (đồng bộ, push, kiểm tra cập nhật) |
| 14–15 | Dừng capture |

Ghi lại giờ:phút:giây cấp nguồn/kết nối của từng thiết bị vào nhật ký phiên.

## 4. Checklist công việc

### 4.1. Setup hạ tầng
- [ ] Flow offloading đang tắt (`uci get firewall.@defaults[0].flow_offloading` = `0`).
- [ ] Đồng hồ ROUTER, CAPTURE-SERVER lệch ≤ 1 giây.
- [ ] Mosquitto đang chạy trên ROUTER.
- [ ] DHCP static lease đủ cho tất cả thiết bị; DHCP server trên ROUTER hoạt động bình thường.
- [ ] CAPTURE-SERVER cắm dây vào cổng LAN, luôn bật, còn trống ≥ 1 GB.

### 4.2. Setup device
- [ ] Tắt nguồn IOT01–IOT03 và CAM01–CAM03.
- [ ] Tắt Wi-Fi (hoặc rút cáp mạng) trên PC01–PC05 và PHONE01–PHONE05.
- [ ] Tắt dữ liệu di động trên smartphone để không lẫn sang 4G khi bật Wi-Fi.
- [ ] Kiểm tra LuCI → `Network → Wireless → Associated Stations` không còn client.
- [ ] Chuẩn bị bảng nhật ký thời gian (Device ID | giờ bật | ghi chú).

### 4.3. Thực hiện
- [ ] Tạo `session_id`, bắt đầu capture, ghi `start_time`.
- [ ] Bật lần lượt theo timeline mục 3, ghi giờ từng thiết bị.
- [ ] Sau mỗi thiết bị, xác nhận trên LuCI thiết bị đã nhận đúng IP.
- [ ] Nếu thiết bị nhận sai IP hoặc không vào mạng: ghi `notes`, không can thiệp cấu hình router giữa phiên.

### 4.4. Kết thúc phiên
- [ ] Dừng capture, ghi `end_time`, `packets captured`, `dropped by kernel`.
- [ ] Thêm dòng `metadata.csv` với `active_scenarios = S02;S08`, đính kèm nhật ký thời gian.

## 5. Checklist nghiệm thu

| # | Tiêu chí | Cách kiểm tra (Wireshark / công cụ) | Đạt |
|---|---|---|---|
| 1 | PCAP ≥ 14 phút, không rỗng, drop < 0,1% | `capinfos`, số liệu tcpdump | [ ] |
| 2 | Không có traffic SSH của CAPTURE-SERVER | `tcp.port == 22` → 0 gói | [ ] |
| 3 | Có DHCP Request/ACK cho **tất cả** thiết bị của cấu hình | `dhcp` → Statistics → Endpoints theo MAC | [ ] |
| 4 | Có ít nhất 1 chuỗi DHCP đầy đủ Discover/Offer/Request/ACK | `dhcp.option.dhcp == 1` (Discover) | [ ] |
| 5 | Có ARP/Gratuitous ARP khi thiết bị vào mạng | `arp` | [ ] |
| 6 | Có DNS query đầu tiên ngay sau DHCP của từng thiết bị | `dns && ip.src == <IP>` | [ ] |
| 7 | 3 IoT gửi MQTT CONNECT và nhận CONNACK | `mqtt.msgtype == 1` và `mqtt.msgtype == 2` | [ ] |
| 8 | Thứ tự xuất hiện thiết bị trong PCAP khớp nhật ký thời gian (sai lệch ≤ 5 giây) | So sánh thời gian gói DHCP đầu tiên | [ ] |
| 9 | Dòng `metadata.csv` và nhật ký thời gian đầy đủ | Mở file | [ ] |

> Bắt tay Wi-Fi (EAPOL/802.11) **không** xuất hiện trên `br-lan`; đây là giới hạn đã biết, không phải lỗi.
