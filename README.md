# Smart Home Normal Traffic Collection

Dự án thu thập **lưu lượng mạng bình thường (normal traffic)** của một mạng Smart Home **mô phỏng trong phòng lab**. Dữ liệu dùng làm **baseline** để xây dựng và đánh giá hệ thống phát hiện xâm nhập (IDS) dựa trên phát hiện bất thường.

## Mục tiêu

- Thu PCAP gốc khi mô phỏng các hoạt động hằng ngày của một ngôi nhà thông minh, do thành viên lab đóng vai người dùng: duyệt web, xem video, gọi điện, truyền file, xem camera, điều khiển thiết bị IoT.
- Bao phủ nhiều mức tải hợp lệ: nhàn rỗi, sử dụng ít, sử dụng vừa, giờ cao điểm.
- Ghi metadata ở **cấp phiên thu**, để biết trong mỗi phiên có thiết bị nào kết nối và hoạt động nào diễn ra.

## Phạm vi

| Hạng mục | Phạm vi |
|---|---|
| Môi trường | Phòng lab mô phỏng Smart Home; thành viên lab vận hành thiết bị theo kịch bản |
| Loại traffic | Chỉ traffic bình thường; **không** có tấn công |
| Gán nhãn | **Không gán nhãn** packet, flow hay time window |
| Khung giờ thu | Chỉ ban ngày, **07:00–18:00** |
| Điểm thu | Router OpenWrt, interface `br-lan` |
| Quy mô | 10–16 client: 4–10 Laptop/Smartphone, 3 IP camera (HTTP/HTTPS), 3 thiết bị IoT (MQTT) |

## Mô hình mạng

```text
                         INTERNET
                             |
          ROUTER OpenWrt 192.168.1.1  (DHCP/DNS, Mosquitto, tcpdump trên br-lan)
                             |
                          br-lan  <---- CAPTURE-SERVER 192.168.1.60 (SSH, lưu PCAP)
                             |
               SSID "SmartHome" (chung cho mọi thiết bị Wi-Fi)
     LAPTOP01–04   .10–.13          CAM01–CAM03   .30–.32
     PHONE01–06    .14–.19          IOT01–IOT03   .40–.42
```

Mọi thiết bị Wi-Fi dùng chung một SSID, bridge vào `br-lan`. Thu được traffic thiết bị ↔ Internet và thiết bị ↔ router (DNS, DHCP, MQTT). **Không** thu được unicast trực tiếp giữa hai thiết bị Wi-Fi, ví dụ điện thoại xem camera qua LAN. Chi tiết xem [kế hoạch thu](smarthome_normal_traffic_capture_plan.md#2-kiến-trúc-mạng-smart-home).

## Bộ kịch bản

| ID | Kịch bản | Thời lượng |
|---|---|---|
| [S01](scenarios/S01_idle_network.md) | Mạng nhàn rỗi | 30 phút |
| [S02](scenarios/S02_device_onboarding_dhcp_dns.md) | Thiết bị kết nối mạng, DHCP/DNS | 15 phút |
| [S03](scenarios/S03_web_browsing.md) | Duyệt web và ứng dụng | 30 phút |
| [S04](scenarios/S04_video_streaming.md) | Xem video trực tuyến | 30 phút |
| [S05](scenarios/S05_file_transfer_cloud_sync.md) | Truyền file và đồng bộ cloud | 25 phút |
| [S06](scenarios/S06_voice_video_call.md) | Gọi thoại và gọi video | 30 phút |
| [S07](scenarios/S07_ip_camera_http.md) | Xem camera IP qua HTTP(S) | 30 phút |
| [S08](scenarios/S08_mqtt_telemetry_background.md) | MQTT telemetry nền (chạy trong mọi phiên) | Xuyên suốt |
| [S09](scenarios/S09_smart_home_control.md) | Điều khiển Smart Home | 20 phút |
| [S10](scenarios/S10_normal_reconnect.md) | Kết nối lại bình thường | 15 phút |
| [S11](scenarios/S11_mixed_household.md) | Mô phỏng sinh hoạt gia đình | 60 phút |
| [S12](scenarios/S12_peak_hour.md) | Giờ cao điểm hợp lệ | 30 phút |

Mỗi file kịch bản gồm: topology, chi tiết thiết bị, thời gian thu, checklist công việc và checklist nghiệm thu.

## Quy trình thu

1. **Chuẩn bị hạ tầng một lần:** router OpenWrt, SSID SmartHome, static lease, Mosquitto, tắt flow offloading, SSH key từ máy thu vào router.
2. **Chọn kịch bản** và chuẩn bị thiết bị theo checklist trong file kịch bản.
3. **Chạy script thu:**
   ```bat
   python tools/capture_session.py --scenarios S04 --n-user-devices 4 --config Nho
   ```
   Script chạy được trên cả **Windows và Linux** (trên Linux dùng `python3`).
   Script tự kiểm tra trước khi thu, thu PCAP, ghi metadata và chấm nghiệm thu tự động.
4. **Hoàn tất nghiệm thu bằng tay** theo mục 5 của file kịch bản: I/O Graph, đối chiếu nhật ký thao tác.

Hướng dẫn đầy đủ về script, tham số và xử lý sự cố: [tools/README.md](tools/README.md).

## Dữ liệu đầu ra

| File | Nội dung |
|---|---|
| `data/pcap/SESxxx_YYYYMMDD_HHMMSS.pcap` | PCAP gốc thu trên `br-lan` |
| `data/metadata.csv` | Mô tả từng phiên: thời gian, cấu hình, số thiết bị, các kịch bản đã chạy, số gói thu được và bị bỏ sót |
| `data/logs/` | Log tcpdump và báo cáo nghiệm thu của từng phiên |
| `devices.csv` | Bảng đối chiếu MAC ↔ IP ↔ mã thiết bị |

> Thư mục `data/` **không được đưa lên git**, vì dữ liệu nặng và chứa thông tin cá nhân (IP, MAC, tên miền truy cập). Việc thu cần có sự đồng ý của các thành viên lab tham gia; ưu tiên dùng tài khoản thử nghiệm. Trước khi chia sẻ dataset phải ẩn danh hóa dữ liệu.

## Cấu trúc thư mục

```text
.
├── README.md                                  # Mô tả dự án (file này)
├── smarthome_normal_traffic_capture_plan.md   # Kế hoạch thu tổng thể
├── generalization_assessment.md               # Đánh giá tính tổng quát hóa của dataset
├── scenarios/                                 # 12 kịch bản chi tiết S01–S12
├── tools/
│   ├── capture_session.py                     # Script thu chung (Windows và Linux)
│   └── README.md                              # Hướng dẫn chạy script
├── CLAUDE.md                                  # Quy ước cho Claude Code
└── data/                                      # Đầu ra khi thu (không commit)
```

## Giới hạn của dataset

- Dữ liệu được **mô phỏng trong lab**, một topology, chỉ ban ngày (07:00–18:00). Hành vi do người đóng vai và đường Internet của lab có thể khác hộ gia đình thật.
- Các phiên thu ngắn và theo kịch bản, nên chưa có nhịp sinh hoạt liên tục cả ngày.
- Mô hình train trên dataset này đáng tin cậy nhất với phân đoạn camera/IoT và với các tấn công tạo traffic khác rõ baseline (quét mạng, flood, brute force).

Phân tích đầy đủ xem [generalization_assessment.md](generalization_assessment.md).

## Trạng thái

- [x] Kế hoạch thu và 12 kịch bản chi tiết
- [x] Script thu và nghiệm thu tự động (phần xử lý sau khi thu đã chạy thử bằng PCAP giả)
- [ ] Thu thử trên router thật
- [ ] Thu đủ các phiên theo kế hoạch
