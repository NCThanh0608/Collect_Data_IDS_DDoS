# Script thu chung – `capture_session.py`

Hướng dẫn chạy [capture_session.py](capture_session.py), script thu dùng chung cho mọi kịch bản S01–S12, chạy trên **Windows và Linux**. Mô tả dự án xem ở [README gốc](../README.md); chi tiết từng kịch bản xem trong [scenarios/](../scenarios/).

---

## 1. Script làm gì

Mỗi lần chạy là **một phiên thu**. Script làm lần lượt bốn bước:

1. **Kiểm tra trước khi thu**
   - Có đủ công cụ Wireshark CLI và `ssh` trên máy thu.
   - SSH được vào router.
   - Flow offloading đã tắt.
   - Mosquitto và tcpdump đang có trên router.
   - Đồng hồ router lệch ≤ 2 giây so với máy thu.
   - Ổ đĩa còn đủ dung lượng.
   - Phiên nằm trong khung 07:00–18:00.
2. **Thu PCAP:** router chạy `tcpdump` trên `br-lan`, đã loại traffic SSH của máy thu. Dữ liệu được đẩy qua SSH về `dumpcap` trên máy thu, tự tách file và tự dừng khi hết thời lượng.
3. **Ghi số liệu:** đổi tên file theo quy ước, đọc số liệu bằng `capinfos`, rồi thêm dòng vào `data/metadata.csv`.
4. **Nghiệm thu tự động:** chạy các bộ lọc bằng `tshark`, in bảng PASS/FAIL và lưu báo cáo.

Script chỉ dùng thư viện chuẩn của Python, không cần `pip install`.

---

## 2. Chuẩn bị (làm một lần)

### 2.1. Máy thu (CAPTURE-SERVER)

| Yêu cầu | Windows 10/11 | Linux (Ubuntu/Debian) |
|---|---|---|
| Python ≥ 3.8 | Cài từ python.org, tích *Add python to PATH* | Thường có sẵn (`python3 --version`) |
| Wireshark CLI: `dumpcap`, `tshark`, `capinfos` | Cài Wireshark vào thư mục mặc định `C:\Program Files\Wireshark` | `sudo apt install tshark` (kèm `dumpcap` và `capinfos`) |
| OpenSSH client | Kiểm tra `ssh -V`. Nếu thiếu: *Settings → Apps → Optional features → OpenSSH Client* | `sudo apt install openssh-client` |
| Kết nối mạng | Cắm dây vào cổng LAN của router, IP tĩnh `192.168.1.60` (DHCP static lease) | Như Windows |

Script tìm Wireshark CLI theo thứ tự: tham số `--wireshark-dir` → biến `PATH` → `C:\Program Files\Wireshark` (Windows).

> Script **không cần quyền root/Administrator**: `dumpcap` chỉ đọc dữ liệu từ đường ống, không mở card mạng của máy thu.

### 2.2. SSH key từ máy thu vào router

Script không nhập được mật khẩu, nên bắt buộc dùng SSH key.

**Windows (PowerShell):**
```powershell
ssh-keygen -t ed25519                     # Enter để chấp nhận mặc định, để trống passphrase
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"
ssh -o BatchMode=yes root@192.168.1.1 "echo OK"   # phải in OK mà không hỏi mật khẩu
```

**Linux:**
```sh
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"
ssh -o BatchMode=yes root@192.168.1.1 "echo OK"
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
- Cấu hình Mosquitto, SSID và static lease theo [kế hoạch thu](../smarthome_normal_traffic_capture_plan.md) và [S08](../scenarios/S08_mqtt_telemetry_background.md).

---

## 3. Cách chạy

Mở terminal tại **thư mục gốc của dự án** (thư mục cha của `tools/`). Mọi lệnh dưới đây chạy từ đó.

- **Windows:** dùng `python`.
- **Linux:** dùng `python3`.

Các ví dụ bên dưới viết `python`; trên Linux thay bằng `python3`.

### 3.1. Lệnh cơ bản

```sh
python tools/capture_session.py --scenarios <Sxx> --n-user-devices <số thiết bị> --config <Nho|Lon>
```

Xem toàn bộ tham số: `python tools/capture_session.py --help`.

### 3.2. Ví dụ theo từng kịch bản

```sh
# S01 – Mạng nhàn rỗi, cấu hình Nhỏ (4 thiết bị người dùng)
python tools/capture_session.py --scenarios S01 --n-user-devices 4 --config Nho --notes "buoi sang"

# S04 – Video, cấu hình Lớn
python tools/capture_session.py --scenarios S04 --n-user-devices 10 --config Lon

# S05 + S07 chạy chồng nhau trong cùng một phiên (thời lượng lấy theo kịch bản đầu tiên: S05)
python tools/capture_session.py --scenarios S05,S07 --n-user-devices 10

# S08 – Phiên MQTT riêng 60 phút
python tools/capture_session.py --scenarios S08 --n-user-devices 4 --config Nho --notes "IOT01 chu ky 15s"

# S11 – Sinh hoạt tổng hợp, kéo dài 75 phút thay vì 60
python tools/capture_session.py --scenarios S11 --n-user-devices 10 --duration-min 75 --notes "cuoi tuan"

# S12 – Giờ cao điểm (chỉ chạy với cấu hình Lớn)
python tools/capture_session.py --scenarios S12 --n-user-devices 10 --config Lon
```

### 3.3. Thu thử lần đầu

Nên thu thử một phiên 2 phút để xác nhận cả chuỗi hoạt động trước khi thu thật:

```sh
python tools/capture_session.py --scenarios S10 --duration-min 2 --notes "thu thu"
```

Phiên thu thử vẫn được ghi vào `metadata.csv`. Sau khi kiểm tra xong, xóa dòng và file PCAP của phiên này.

### 3.4. Trong khi thu

- Script in giờ bắt đầu và giờ tự dừng. **Không đóng cửa sổ terminal** cho đến khi script kết thúc.
- Thao tác thiết bị theo timeline trong file kịch bản (`scenarios/Sxx_*.md`, mục 3).
- Không SSH vào router từ máy khác trong lúc thu, vì traffic đó sẽ lọt vào PCAP.
- Trên Linux, nếu thu qua SSH từ xa vào máy thu, nên chạy trong `tmux` hoặc `screen` để phiên không bị ngắt khi mất kết nối.

### 3.5. Dừng sớm

Nhấn **Ctrl+C**.
- Script chờ `dumpcap` ghi nốt dữ liệu, rồi vẫn ghi metadata (kèm ghi chú `dung som bang Ctrl+C`) và chạy nghiệm thu như bình thường.
- Phiên dừng sớm thường không có số gói bị router bỏ sót, nên mục "Drop" trong báo cáo sẽ là `CHECK`.

Nếu script bị ngắt hẳn (đóng terminal, mất điện), chạy lại ở chế độ chỉ chấm:

```sh
python tools/capture_session.py --scenarios S07 --check-only --session-id SES005
```

Script ghi `metadata.csv` nếu phiên chưa có trong đó, rồi chạy nghiệm thu.

---

## 4. Tham số

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--scenarios` | *(bắt buộc)* | Một hoặc nhiều kịch bản, ví dụ `S04`, `S05,S07` hoặc `S05 S07`. **S08 luôn được tự thêm** |
| `--n-user-devices` | `0` | Số thiết bị người dùng đang kết nối mạng trong phiên |
| `--config` | `Lon` | `Nho` hoặc `Lon`. S12 bắt buộc `Lon` |
| `--duration-min` | theo kịch bản | Thời lượng thu (phút). Để trống thì lấy theo kịch bản đầu tiên trong `--scenarios` |
| `--notes` | trống | Ghi chú đưa vào cột `notes` của `metadata.csv` |
| `--check-only` | tắt | Không thu, chỉ ghi metadata (nếu thiếu) và nghiệm thu. Dùng kèm `--session-id` |
| `--session-id` | tự tăng | Mã phiên, ví dụ `SES005`. Khi thu mới, script tự lấy số tiếp theo trong `metadata.csv` |
| `--force` | tắt | Vẫn thu dù kiểm tra trước khi thu có lỗi (ví dụ ngoài khung giờ). Chỉ dùng khi thử nghiệm |
| `--router-ip` | `192.168.1.1` | IP router |
| `--router-user` | `root` | User SSH vào router |
| `--capture-server-ip` | `192.168.1.60` | IP máy thu, dùng để loại traffic SSH khỏi PCAP |
| `--interface` | `br-lan` | Interface thu trên router |
| `--out-dir` | `data/` | Thư mục lưu dữ liệu |
| `--wireshark-dir` | tự tìm | Thư mục chứa `dumpcap`/`tshark`/`capinfos` nếu không nằm trong `PATH` |

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
    └── SES001_report.csv                # kết quả nghiệm thu
```

### 5.1. Đọc báo cáo nghiệm thu

Cuối mỗi phiên, script in một bảng như sau:

```text
  Check                            Filter                       Value  Result
  -------------------------------  ---------------------------  -----  ------
  PCAP không rỗng                  capinfos                    182340  PASS
  Thời lượng >= 93% kế hoạch       capinfos                    1801 s  PASS
  Drop < 0.1%                      tcpdump                     0.000%  PASS
  Không có SSH của CAPTURE-SERVER  tcp.port == 22                   0  PASS
  Có DNS                           dns                           2215  PASS
  MQTT publish (S08)               mqtt.msgtype == 3              412  PASS
  ...
```

| Kết quả | Ý nghĩa | Việc cần làm |
|---|---|---|
| `PASS` | Đạt | — |
| `FAIL` | Không đạt | Xem mục 6, sửa nguyên nhân, thu lại phiên. Không xóa file, ghi lý do vào `notes` |
| `CHECK` | Không đủ số liệu để chấm tự động | Kiểm tra bằng tay |

- Script trả mã thoát `0` nếu không có tiêu chí `FAIL`, ngược lại trả `1`. Có thể dùng mã này khi gọi script từ chương trình khác.
- Báo cáo chỉ gồm các tiêu chí kiểm tra được bằng bộ lọc. Các tiêu chí cần nhìn bằng mắt vẫn phải tự kiểm tra theo **mục 5 của từng file kịch bản**: I/O Graph, đối chiếu nhật ký thao tác, thời điểm sự kiện.

---

## 6. Xử lý sự cố

| Thông báo | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Không tìm thấy dumpcap/tshark/capinfos` | Chưa cài Wireshark CLI hoặc không nằm trong `PATH` | Cài theo mục 2.1, hoặc chỉ đường bằng `--wireshark-dir` |
| `Không SSH được vào root@192.168.1.1` | Chưa cài SSH key, sai IP, máy thu chưa vào mạng | Làm lại mục 2.2; thử `ssh -o BatchMode=yes root@192.168.1.1 "echo OK"` |
| `Flow offloading đang bật` | Chưa tắt offloading | Chạy lệnh tắt ở mục 2.3 |
| `Mosquitto không chạy` | Broker chưa khởi động | `/etc/init.d/mosquitto start` trên router |
| `Lệch đồng hồ router` | NTP chưa đồng bộ | Bật NTP trên router và máy thu, đợi vài phút rồi chạy lại |
| `nằm ngoài khung 07:00-18:00` | Giờ bắt đầu cộng thời lượng vượt 18:00 | Thu vào khung giờ khác, hoặc giảm `--duration-min` |
| `Ổ đĩa còn ... GB` | Ổ không đủ chỗ | Dọn ổ hoặc đổi `--out-dir` sang ổ khác |
| `Không có file PCAP nào` | Pipe SSH bị ngắt ngay từ đầu | Xem `data/logs/<session>_tcpdump.log`; thử chạy tay `ssh root@192.168.1.1 "tcpdump -i br-lan -c 5"` |
| `timeout: not found` trong log tcpdump | BusyBox không có `timeout` | Nâng cấp OpenWrt hoặc cài bản BusyBox có `timeout` |
| FAIL `Không có SSH của CAPTURE-SERVER` | Có máy khác SSH vào router, hoặc sai `--capture-server-ip` | Kiểm tra IP máy thu; không SSH từ máy khác khi đang thu |
| FAIL `IOT0x xuất hiện` | Thiết bị IoT mất kết nối hoặc sai IP | Kiểm tra static lease, nguồn, Wi-Fi của thiết bị |
| FAIL `CAM0x xuất hiện` (S07) | Camera mất kết nối, sai IP, hoặc không có traffic nào đi qua router | Kiểm tra static lease, nguồn và Wi-Fi của camera |
| Drop > 0.1% | Router quá tải | Giảm số luồng tải nặng, ghi chú và thu lại |

---

## 7. Giới hạn hiện tại

- Bước thu thật qua SSH tới router **chưa được kiểm thử trên phần cứng thật**. Trên Windows mới chạy thử bằng một chương trình giả lập ssh; trên Linux chưa chạy thử.
- Mục "Drop" chỉ có số liệu khi phiên kết thúc đúng hạn. Phiên dừng bằng Ctrl+C thường thiếu số liệu này.
- Số gói bị bỏ sót được tính cho **cả phiên** và ghi giống nhau ở mọi file của phiên đó.
- Nghiệm thu tự động không thay thế được kiểm tra bằng mắt theo mục 5 của từng kịch bản.
