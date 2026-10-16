# Thu Normal Traffic – Smart Home

Bộ tài liệu và công cụ thu lưu lượng bình thường (không gán nhãn) của mạng Smart Home tại router OpenWrt, interface `br-lan`.

| Thành phần | Nội dung |
|---|---|
| [smarthome_normal_traffic_capture_plan.md](smarthome_normal_traffic_capture_plan.md) | Kế hoạch thu tổng thể: topology, IP, thiết bị, nguyên tắc thu |
| [scenarios/](scenarios/) | 12 kịch bản S01–S12: topology, thiết bị, timeline, checklist công việc và nghiệm thu |
| [generalization_assessment.md](generalization_assessment.md) | Đánh giá tính tổng quát hóa của dataset |
| [tools/capture_session.ps1](tools/capture_session.ps1) | Script thu chung cho mọi kịch bản (hướng dẫn bên dưới) |

---

## 1. Script `capture_session.ps1` làm gì

Mỗi lần chạy là **một phiên thu**. Script làm lần lượt bốn bước:

1. **Kiểm tra trước khi thu**
   - Có đủ công cụ Wireshark CLI và `ssh` trên máy thu.
   - SSH được vào router.
   - Flow offloading đã tắt.
   - Mosquitto và tcpdump đang có trên router.
   - Đồng hồ router lệch ≤ 2 giây so với máy thu.
   - Ổ đĩa còn đủ dung lượng.
   - Phiên nằm trong khung 07:00–18:00.
2. **Thu PCAP:** router chạy `tcpdump` trên `br-lan`, đã loại traffic SSH của máy thu. Dữ liệu được đẩy về `dumpcap` trên máy thu, tự tách file và tự dừng khi hết thời lượng.
3. **Ghi số liệu:** đổi tên file theo quy ước, đọc số liệu bằng `capinfos`, rồi thêm dòng vào `data/metadata.csv`.
4. **Nghiệm thu tự động:** chạy các bộ lọc bằng `tshark`, in bảng PASS/FAIL và lưu báo cáo.

---

## 2. Chuẩn bị (làm một lần)

### 2.1. Máy thu (CAPTURE-SERVER)

| Yêu cầu | Ghi chú |
|---|---|
| Windows 10/11 | Có sẵn Windows PowerShell 5.1 |
| Wireshark | Cài vào thư mục mặc định `C:\Program Files\Wireshark`, cần `dumpcap.exe`, `tshark.exe`, `capinfos.exe`. Cài nơi khác thì dùng tham số `-WiresharkDir` |
| OpenSSH Client | Kiểm tra bằng lệnh `ssh -V`. Nếu thiếu: *Settings → Apps → Optional features → OpenSSH Client* |
| Kết nối mạng | Cắm dây vào cổng LAN của router, IP tĩnh `192.168.10.60` (DHCP static lease) |

### 2.2. SSH key từ máy thu vào router

Script không nhập được mật khẩu, nên bắt buộc dùng SSH key.

```powershell
# 1. Tạo key (Enter để chấp nhận mặc định, để trống passphrase)
ssh-keygen -t ed25519

# 2. Chép public key lên router (nhập mật khẩu root lần cuối)
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@192.168.10.1 "cat >> /etc/dropbear/authorized_keys"

# 3. Thử lại: phải vào được mà không hỏi mật khẩu
ssh -o BatchMode=yes root@192.168.10.1 "echo OK"
```

### 2.3. Router OpenWrt

```sh
opkg update
opkg install tcpdump mosquitto-nossl mosquitto-client-nossl

# Tắt flow offloading
uci set firewall.@defaults[0].flow_offloading='0'
uci set firewall.@defaults[0].flow_offloading_hw='0'
uci commit firewall
/etc/init.d/firewall restart

# Kiểm tra lệnh timeout (BusyBox) có sẵn
timeout 2 sleep 5; echo "exit=$?"
```

- Lệnh cuối phải in `exit=143` hoặc một mã khác 0. Nếu báo `not found`, cần dùng bản OpenWrt có BusyBox `timeout` (khuyến nghị OpenWrt ≥ 19.07).
- Cấu hình Mosquitto, SSID và static lease theo [kế hoạch thu](smarthome_normal_traffic_capture_plan.md) và [S08](scenarios/S08_mqtt_telemetry_background.md).

### 2.4. Cho phép chạy script

Không cần đổi chính sách của máy. Chỉ cần luôn chạy kèm `-ExecutionPolicy Bypass` như các ví dụ bên dưới.

---

## 3. Cách chạy

Mở **Command Prompt** hoặc **PowerShell** tại thư mục gốc của dự án (thư mục chứa file README này).

### 3.1. Lệnh cơ bản

```bat
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios <Sxx> -NUserDevices <số thiết bị> -Config <Nho|Lon>
```

### 3.2. Ví dụ theo từng kịch bản

```bat
:: S01 – Mạng nhàn rỗi, cấu hình Nhỏ (4 thiết bị người dùng)
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S01 -NUserDevices 4 -Config Nho -Notes "buoi sang"

:: S04 – Video, cấu hình Lớn
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S04 -NUserDevices 10 -Config Lon

:: S05 + S07 chạy chồng nhau trong cùng một phiên (thời lượng lấy theo kịch bản đầu tiên: S05)
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S05,S07 -NUserDevices 10

:: S08 – Phiên MQTT riêng 60 phút
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S08 -NUserDevices 4 -Config Nho -Notes "IOT01 chu ky 15s"

:: S11 – Sinh hoạt tổng hợp, kéo dài 75 phút thay vì 60
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S11 -NUserDevices 10 -DurationMin 75 -Notes "cuoi tuan"

:: S12 – Giờ cao điểm (chỉ chạy với cấu hình Lớn)
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S12 -NUserDevices 10 -Config Lon
```

### 3.3. Thu thử lần đầu

Nên thu thử một phiên 2 phút để xác nhận cả chuỗi hoạt động trước khi thu thật:

```bat
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S10 -DurationMin 2 -Notes "thu thu"
```

Phiên thu thử vẫn được ghi vào `metadata.csv`. Sau khi kiểm tra xong, xóa dòng và file PCAP của phiên này.

### 3.4. Trong khi thu

- Script in giờ bắt đầu và giờ tự dừng. **Không đóng cửa sổ** cho đến khi script kết thúc.
- Thao tác thiết bị theo timeline trong file kịch bản (`scenarios\Sxx_*.md`, mục 3).
- Không SSH vào router từ máy khác trong lúc thu, vì traffic đó sẽ lọt vào PCAP.

### 3.5. Dừng sớm

Nhấn **Ctrl+C**. File PCAP đã thu vẫn được giữ, nhưng script không kịp ghi metadata và nghiệm thu. Khi đó chạy lại ở chế độ chỉ chấm:

```bat
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S07 -CheckOnly -SessionId SES005
```

- Script ghi `metadata.csv` nếu phiên chưa có trong đó, rồi chạy nghiệm thu.
- Phiên dừng sớm không có số gói bị router bỏ sót; mục "Drop" trong báo cáo sẽ là `CHECK`.
- Nên ghi lý do dừng sớm vào cột `notes` của `metadata.csv`.

---

## 4. Tham số

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `-Scenarios` | *(bắt buộc)* | Một hoặc nhiều kịch bản, ví dụ `S04` hoặc `S05,S07`. **S08 luôn được tự thêm** |
| `-NUserDevices` | `0` | Số thiết bị người dùng đang kết nối mạng trong phiên |
| `-Config` | `Lon` | `Nho` hoặc `Lon`. S12 bắt buộc `Lon` |
| `-DurationMin` | theo kịch bản | Thời lượng thu (phút). Để trống thì lấy theo kịch bản đầu tiên trong `-Scenarios` |
| `-Notes` | trống | Ghi chú đưa vào cột `notes` của `metadata.csv` |
| `-CheckOnly` | tắt | Không thu, chỉ ghi metadata (nếu thiếu) và nghiệm thu. Dùng kèm `-SessionId` |
| `-SessionId` | tự tăng | Mã phiên, ví dụ `SES005`. Khi thu mới, script tự lấy số tiếp theo trong `metadata.csv` |
| `-Force` | tắt | Vẫn thu dù kiểm tra trước khi thu có lỗi (ví dụ ngoài khung giờ). Chỉ dùng khi thử nghiệm |
| `-RouterIp` | `192.168.10.1` | IP router |
| `-RouterUser` | `root` | User SSH vào router |
| `-CaptureServerIp` | `192.168.10.60` | IP máy thu, dùng để loại traffic SSH khỏi PCAP |
| `-Interface` | `br-lan` | Interface thu trên router |
| `-OutDir` | `data\` | Thư mục lưu dữ liệu |
| `-WiresharkDir` | `C:\Program Files\Wireshark` | Thư mục cài Wireshark |

**Giá trị mặc định theo kịch bản:**

| Kịch bản | Thời lượng (phút) | Tách file mỗi (phút) | Ổ trống tối thiểu (GB) |
|---|---:|---:|---:|
| S01 Mạng nhàn rỗi | 30 | 60 | 1 |
| S02 Kết nối DHCP/DNS | 15 | 60 | 1 |
| S03 Duyệt web | 30 | 60 | 2 |
| S04 Video | 30 | 60 | 12 |
| S05 Truyền file | 25 | 60 | 3 |
| S06 Gọi thoại/video | 30 | 60 | 3 |
| S07 Camera | 30 | 60 | 4 |
| S08 MQTT (phiên riêng) | 60 | 60 | 1 |
| S09 Điều khiển | 20 | 60 | 1 |
| S10 Kết nối lại | 15 | 60 | 1 |
| S11 Sinh hoạt tổng hợp | 60 | 30 | 25 |
| S12 Giờ cao điểm | 30 | 10 | 30 |

Khi chạy nhiều kịch bản cùng lúc: tách file theo giá trị **nhỏ nhất**, dung lượng ổ theo giá trị **lớn nhất** trong các kịch bản.

---

## 5. Kết quả đầu ra

```text
data/
├── metadata.csv                         # mỗi file PCAP một dòng
├── pcap/
│   ├── SES001_20261012_090000.pcap
│   └── SES002_20261012_100500.pcap
└── logs/
    ├── SES001_tcpdump.log               # log tcpdump trên router (có số gói bị bỏ sót)
    ├── SES001_capture.cmd               # lệnh thu đã chạy (để đối chiếu)
    └── SES001_report.csv                # kết quả nghiệm thu
```

### 5.1. Đọc báo cáo nghiệm thu

Cuối mỗi phiên, script in một bảng như sau:

```text
Check                           Filter                       Value Result
-----                           ------                       ----- ------
PCAP khong rong                 capinfos                    182340 PASS
Thoi luong >= 93% ke hoach      capinfos                    1801 s PASS
Drop < 0.1%                     tcpdump                     0.000% PASS
Khong co SSH cua CAPTURE-SERVER tcp.port == 22                   0 PASS
Co DNS                          dns                           2215 PASS
MQTT publish (S08)              mqtt.msgtype == 3              412 PASS
...
```

| Kết quả | Ý nghĩa | Việc cần làm |
|---|---|---|
| `PASS` | Đạt | — |
| `FAIL` | Không đạt | Xem mục 6, sửa nguyên nhân, thu lại phiên. Không xóa file, ghi lý do vào `notes` |
| `CHECK` | Không đủ số liệu để chấm tự động | Kiểm tra bằng tay |

Báo cáo chỉ gồm các tiêu chí kiểm tra được bằng bộ lọc. Các tiêu chí cần nhìn bằng mắt vẫn phải tự kiểm tra theo **mục 5 của từng file kịch bản**: I/O Graph, đối chiếu nhật ký thao tác, thời điểm sự kiện.

---

## 6. Xử lý sự cố

| Thông báo | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Khong SSH duoc vao root@192.168.10.1` | Chưa cài SSH key, sai IP, máy thu chưa vào mạng | Làm lại mục 2.2; thử `ssh -o BatchMode=yes root@192.168.10.1 "echo OK"` |
| `Flow offloading dang bat` | Chưa tắt offloading | Chạy lệnh tắt ở mục 2.3 |
| `Mosquitto khong chay` | Broker chưa khởi động | `/etc/init.d/mosquitto start` trên router |
| `Lech dong ho router` | NTP chưa đồng bộ | Bật NTP trên router và máy thu, đợi vài phút rồi chạy lại |
| `nam ngoai khung 07:00-18:00` | Giờ bắt đầu cộng thời lượng vượt 18:00 | Thu vào khung giờ khác, hoặc giảm `-DurationMin` |
| `O dia con ... GB` | Ổ không đủ chỗ | Dọn ổ hoặc đổi `-OutDir` sang ổ khác |
| `Khong co file PCAP nao` | Pipe SSH bị ngắt ngay từ đầu | Xem `data\logs\<session>_tcpdump.log`; thử chạy tay `ssh root@192.168.10.1 "tcpdump -i br-lan -c 5"` |
| `timeout: not found` trong log tcpdump | BusyBox không có `timeout` | Nâng cấp OpenWrt hoặc cài bản BusyBox có `timeout` |
| FAIL `Khong co SSH cua CAPTURE-SERVER` | Có máy khác SSH vào router, hoặc sai `-CaptureServerIp` | Kiểm tra IP máy thu; không SSH từ máy khác khi đang thu |
| FAIL `IOT0x xuat hien` | Thiết bị IoT mất kết nối hoặc sai IP | Kiểm tra static lease, nguồn, Wi-Fi của thiết bị |
| FAIL `Camera <-> viewer LAN` (S07) | Viewer và camera cùng SSID, hoặc camera chỉ dùng cloud | Viewer phải ở SmartHome-User, camera ở SmartHome-IoT; nếu camera dùng cloud, ghi chú và bỏ qua tiêu chí này |
| Drop > 0.1% | Router quá tải | Giảm số luồng tải nặng, ghi chú và thu lại |

---

## 7. Giới hạn hiện tại

- Script chỉ chạy trên Windows (PowerShell 5.1 trở lên).
- Mục "Drop" chỉ có số liệu khi phiên kết thúc đúng hạn. Phiên dừng bằng Ctrl+C sẽ thiếu số liệu này.
- Số gói bị bỏ sót được tính cho **cả phiên** và ghi giống nhau ở mọi file của phiên đó.
- Nghiệm thu tự động không thay thế được kiểm tra bằng mắt theo mục 5 của từng kịch bản.
