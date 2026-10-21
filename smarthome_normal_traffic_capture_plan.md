# KỊCH BẢN THU THẬP NORMAL TRAFFIC – MẠNG SMART HOME

> **Phiên bản:** Smart Home (4–10 Laptop/Smartphone + 3 camera TCP/HTTP + 3 IoT MQTT)  
> **Môi trường:** Phòng lab mô phỏng mạng Smart Home; thành viên lab đóng vai người dùng  
> **Điểm thu:** Router OpenWrt, interface **`br-lan`**  
> **Phạm vi dữ liệu:** Chỉ lưu lượng hoạt động bình thường. **Không gán nhãn** packet, flow hoặc time window.  
> **Mục tiêu sử dụng:** Xây dựng baseline lưu lượng Smart Home, phục vụ phân tích flow và đặc trưng theo cửa sổ thời gian cho IDS.

## 1. Quy mô và nguyên tắc

### 1.1. Quy mô cố định và quy mô biến thiên

| Nhóm                    |                 Số lượng | Đặc điểm hoạt động                                                                   | Giao thức chính                            |
| ----------------------- | -----------------------: | ------------------------------------------------------------------------------------ | ------------------------------------------ |
| Laptop và Smartphone | **4–10** (tổng hai nhóm) | Duyệt web, xem video, tải file, họp online, đồng bộ dữ liệu, dùng app Smart Home     | DNS, HTTPS/TCP, QUIC/UDP, ICMP, NTP        |
| IP camera               |                    **3** | Xem trực tiếp, chụp snapshot, app/dashboard truy cập camera, kết nối lại bình thường | **TCP/HTTP** hoặc **HTTPS** (tùy thiết bị) |
| Thiết bị IoT            |                    **3** | Publish telemetry, nhận lệnh điều khiển, keepalive/reconnect                         | **MQTT** (`1883`)                          |
| Router thu thập         |                    **1** | Gateway, DHCP/DNS, MQTT broker (khuyến nghị), điểm capture `br-lan`                  | Các giao thức đi qua router                |
| Server capture          |                    **1** | SSH vào router, nhận và lưu PCAP                                                     | SSH (bị loại khỏi capture)                 |

**Tổng số client:** **10–16 thiết bị** (= 4–10 thiết bị người dùng + 3 camera + 3 thiết bị MQTT), **không tính router và server capture**.

Không cần bổ sung máy ảo để đạt đủ số lượng nếu đã có thiết bị thật. Nếu dùng VMware giả lập laptop, nên dùng **Bridged Network** và kiểm tra VM được router nhận diện bằng IP riêng.

### 1.2. Hai cấu hình phân bổ thiết bị người dùng

| Cấu hình | Laptop | Smartphone | Tổng thiết bị người dùng | Tổng client gồm camera + IoT |
| -------- | -----: | ---------: | -----------------------: | ---------------------------: |
| **Nhỏ**  |      2 |          2 |                    **4** |                       **10** |
| **Lớn**  |      4 |          6 |                   **10** |                       **16** |

Có thể dùng các mức trung gian 6 hoặc 8 thiết bị người dùng, nhưng 3 camera và 3 MQTT vẫn duy trì để so sánh nhất quán. Kịch bản **S12** chỉ chạy được với cấu hình có **≥ 8** thiết bị người dùng.

### 1.3. Nguyên tắc thu

- Chỉ thực hiện các hoạt động sử dụng mạng hợp lệ trong Smart Home; **không mô phỏng tấn công** trong các phiên này.
- Giữ lại **PCAP gốc**
- Thu các trạng thái **nhàn rỗi, sử dụng ít, sử dụng vừa, tải cao hợp lệ**, cùng tình huống nhiều thiết bị hoạt động đồng thời.
- **Khung giờ thu: chỉ ban ngày, 07:00–18:00.** Không thu buổi tối và ban đêm. Để bù lại, nên trải các phiên đều trong khung giờ (sáng, trưa, chiều) và trên nhiều ngày khác nhau. Dataset chỉ đại diện cho traffic ban ngày (xem [generalization_assessment.md](generalization_assessment.md)).
- Đảm bảo traffic thực sự **đi qua CPU router và hiện trên `br-lan`** (xem mục 2.2), tránh kết luận sai do traffic LAN-to-LAN được chuyển mạch trực tiếp trong switch chip hoặc driver Wi-Fi.
- PCAP có thể chứa dữ liệu cá nhân (tài khoản, DNS query, SNI): cần sự **đồng ý** của các thành viên lab tham gia, ưu tiên tài khoản thử nghiệm, và có phương án **ẩn danh hóa** (IP/MAC, DNS query, SNI) trước khi chia sẻ dataset.

### 1.4. Điều kiện thu trong phòng lab

Dữ liệu được thu trong **phòng lab mô phỏng một mạng Smart Home**, không phải trong một ngôi nhà thật. Thành viên lab vận hành thiết bị và đóng vai người dùng theo kịch bản. Điều kiện lab khác nhà thật ở nhiều điểm, nên cần kiểm soát các yếu tố sau:

| Yếu tố | Rủi ro trong lab | Cách xử lý |
|---|---|---|
| **Đường Internet (WAN)** | WAN của router nối vào mạng của lab/trường, có thể đi qua proxy, firewall hoặc NAT nhiều lớp. Một số dịch vụ có thể bị chặn (QUIC, STUN/TURN, P2P, mạng xã hội, cổng 8883) | Trước đợt thu, kiểm tra từng ứng dụng trong kịch bản chạy được qua WAN của lab. Ghi loại đường truyền và băng thông vào `notes`. Nếu được, dùng đường Internet riêng (modem nhà mạng hoặc router 4G/5G) để giống hộ gia đình |
| **Người dùng** | Thành viên lab thao tác theo kịch bản, đều đặn hơn người dùng thật | Mỗi người giữ một vai cố định trong suốt đợt thu (ví dụ "bố", "mẹ", "con"); để khoảng nghỉ tự nhiên, không thao tác máy móc theo từng giây |
| **Tài khoản** | Dùng tài khoản cá nhân thì PCAP chứa dữ liệu cá nhân; dùng tài khoản mới tạo thì feed, đồng bộ, thông báo ít hơn thực tế | Ưu tiên **tài khoản thử nghiệm riêng cho lab**, đã dùng trước một thời gian (có danh bạ, lịch sử, ảnh) để traffic nền gần thực tế |
| **Thiết bị** | Thiết bị mới cài hoặc máy dùng chung của lab có ít ứng dụng nền | Cài các ứng dụng phổ biến của hộ gia đình (Zalo, Facebook, YouTube, ngân hàng, cloud) và để chúng chạy nền như bình thường |
| **Wi-Fi** | Nhiều AP xung quanh gây nhiễu; tất cả thiết bị trong một phòng nên tín hiệu mạnh, ít roaming | Chọn kênh ít nhiễu, cố định kênh trong suốt đợt thu và ghi lại. Có thể đặt một số thiết bị xa router để có tín hiệu yếu như nhà thật |
| **Camera** | Camera hướng vào cảnh tĩnh trong lab nên bitrate thấp, ít sự kiện chuyển động | Hướng camera vào khu vực có người qua lại, hoặc tạo chuyển động trong các phiên S07, S11, S12 |
| **Thiết bị lạ** | Máy khác của lab vô tình kết nối SSID SmartHome, làm lẫn traffic | Đặt mật khẩu SSID riêng, chỉ cấp cho thiết bị trong `devices.csv`; bật lọc MAC nếu cần. Sau mỗi phiên, đối chiếu danh sách IP trong PCAP với `devices.csv` |
| **Lịch thu** | Phiên thu phụ thuộc giờ làm việc và số người có mặt ở lab | Lên lịch trước cho S11, S12 (cần đủ người vận hành); trải các phiên trên nhiều ngày khác nhau |

Ghi các điều kiện lab của mỗi đợt thu (đường WAN, kênh Wi-Fi, số người vận hành) vào cột `notes` của `metadata.csv` hoặc một file nhật ký đợt thu.

## 2. Kiến trúc mạng Smart Home

### 2.1. Topology

Tất cả thiết bị nằm trong **một subnet `192.168.1.0/24`** trên bridge `br-lan` của OpenWrt. Tất cả thiết bị Wi-Fi (người dùng, camera, IoT) dùng **chung một SSID "SmartHome"**, được bridge vào `br-lan`.

```text
                          INTERNET
                              |
                            (WAN)
                     ROUTER OpenWrt 192.168.1.1
                     - DHCP/DNS, NTP
                     - Mosquitto broker :1883
                     - tcpdump trên br-lan
                              |
                           br-lan
          +-------------------------------------------+-----------------+
          |                                           |                 |
   SSID "SmartHome" (chung cho mọi thiết bị Wi-Fi)                  LAN port
   4–10 Laptop/Phone     CAM01 CAM02 CAM03                    Server capture
   192.168.1.10–19       IOT01 IOT02 IOT03                    192.168.1.60
                         192.168.1.30–42
```

### 2.3. Kế hoạch IP mẫu

| Thiết bị             | Địa chỉ mẫu        | Mạng kết nối        | Vai trò                          |
| -------------------- | ------------------ | ------------------- | -------------------------------- |
| Router               | `192.168.1.1`     | —                   | Gateway, DHCP/DNS, broker, capture |
| Laptop/Smartphone | `192.168.1.10–19` | SSID "SmartHome"    | Người dùng: 4–10 thiết bị        |
| Camera 01–03         | `192.168.1.30–32` | SSID "SmartHome" (hoặc cổng LAN) | TCP/HTTP(S)                      |
| MQTT IoT 01–03       | `192.168.1.40–42` | SSID "SmartHome"     | Telemetry và nhận lệnh           |
| Broker riêng (tùy chọn) | `192.168.1.50` | Cổng LAN có dây    | Chỉ dùng nếu không chạy broker trên router |
| Server capture       | `192.168.1.60`    | Cổng LAN có dây     | SSH vào router, lưu PCAP         |

**Mã thiết bị chuẩn** (dùng thống nhất trong mọi file kịch bản):

| Device ID | Loại | IP | Mạng | Cấu hình Nhỏ | Cấu hình Lớn |
|---|---|---|---|:---:|:---:|
| ROUTER | Router OpenWrt | 192.168.1.1 | — | ✔ | ✔ |
| LAPTOP01 – LAPTOP04 | Laptop | .10 – .13 | SmartHome | LAPTOP01, LAPTOP02 | ✔ |
| PHONE01 – PHONE06 | Smartphone | .14 – .19 | SmartHome | PHONE01, PHONE02 | ✔ |
| CAM01 – CAM03 | IP camera | .30 – .32 | SmartHome | ✔ | ✔ |
| IOT01 – IOT03 | IoT MQTT | .40 – .42 | SmartHome | ✔ | ✔ |
| CAPTURE-SERVER | Server capture | .60 | LAN port | ✔ | ✔ |

Dùng **DHCP static lease** (reservation theo MAC) để IP ổn định, giúp đối chiếu thiết bị mà không cần gán nhãn dữ liệu. Ghi bảng MAC ↔ IP ↔ tên thiết bị vào `devices.csv` (mục 6).

## 3. Hành vi cụ thể của từng nhóm thiết bị

### 3.1. Nhóm 4–10 Laptop/Smartphone

**Laptop**
- Mở website, đọc nội dung, tìm kiếm và chuyển trang trong khoảng nghỉ tự nhiên.
- Xem YouTube/phim trực tuyến; thay đổi video, pause/resume và chất lượng.
- Download/upload file cá nhân (ví dụ 5 MB, 50 MB, 200 MB).
- Họp trực tuyến, gọi thoại, chia sẻ màn hình.

**Smartphone**
- Mở ứng dụng mạng xã hội, duyệt tin, xem video ngắn hoặc phát video.
- Gửi/nhận tin nhắn và cuộc gọi qua ứng dụng.
- Khóa/mở màn hình, chuyển Wi-Fi off/on rồi kết nối lại **trong thao tác sử dụng thông thường**, forget Wifi, đăng nhập .
- Dùng ứng dụng để mở dashboard Smart Home, xem camera, đọc sensor và điều khiển thiết bị MQTT qua backend hợp lệ.

> **Gợi ý quan trọng:** Smartphone khác laptop vì tạo nhiều đợt traffic ngắn theo thói quen mở app, thông báo đẩy, đồng bộ nền và sleep/wake. Nên ghi nhận cả thời gian để điện thoại ở trạng thái chờ, không chỉ liên tục phát video.

### 3.2. Nhóm 3 camera **TCP/HTTP**

Với mỗi camera, chỉ dùng các giao thức mà firmware **thực sự hỗ trợ**. Nếu camera truyền ảnh/video qua HTTP hoặc HTTPS, có thể thiết kế:

| Camera | Hoạt động nền | Hoạt động khi có người dùng |
|---|---|---|
| **CAM01** | Đăng nhập/kiểm tra trạng thái theo app | Smartphone 01 mở live view, dừng rồi mở lại |
| **CAM02** | HTTP(S) status hoặc snapshot định kỳ nếu hỗ trợ | Laptop truy cập live view/snapshot, đổi trang |
| **CAM03** | Keepalive hoặc liên hệ cloud theo cấu hình thật | Hai người dùng xem đồng thời nếu firmware cho phép |

- Nếu camera chỉ hỗ trợ **HTTP snapshot**, cho app/dashboard lấy snapshot ở chu kỳ vừa phải (ví dụ **2–10 giây**); **không coi đó là video stream**.
- Nếu camera hỗ trợ **MJPEG over HTTP** hoặc luồng HTTP(S) liên tục, thực hiện các phiên xem trực tiếp 5–20 phút, với 1–2 người xem nếu được phép.
- Nếu nhà sản xuất chỉ cung cấp cloud/P2P độc quyền, giữ luồng thực tế của app, **không tự giả định** là RTSP hoặc HTTP.
- Có thể thêm sự kiện hợp lệ: người dùng vào app, đổi camera, thoát app, camera reconnect sau gián đoạn Wi-Fi thông thường.
- Với SSID chung, luồng **camera ↔ người xem trong LAN** không xuất hiện trên `br-lan` khi cả hai dùng Wi-Fi. Muốn thu luồng này thì cắm dây camera (mục 2.1). Luồng camera ↔ cloud vẫn thu được.


-------- Cần update theo đặc điểm các camera ----------------

### 3.3. Nhóm 3 IoT **MQTT**

Quy ước topic: `smarthome/<device_id>/<message_type>`, chữ thường, không dấu cách.

| IoT       | Vai trò                     | Publish                                        | Subscribe / điều khiển |
| --------- | --------------------------- | ---------------------------------------------- | ---------------------- |
| **IOT01** | Cảm biến môi trường         | `smarthome/iot01/telemetry`                    | `smarthome/iot01/cmd`  |
| **IOT02** | Cảm biến cửa / chuyển động  | `smarthome/iot02/event`                        | `smarthome/iot02/cmd`  |
| **IOT03** | Ổ cắm / công tắc thông minh | `smarthome/iot03/state`, `smarthome/iot03/ack` | `smarthome/iot03/cmd`  |


**Tham số MQTT cố định cho mọi phiên** (ghi vào metadata nếu thay đổi):

| Tham số                    | Giá trị mẫu                                                 |
| -------------------------- | ----------------------------------------------------------- |
| Broker                     | `192.168.1.1:1883` (hoặc `8883` nếu dùng TLS)              |
| Keepalive                  | 60 giây                                                     |
| QoS telemetry / sự kiện    | 0 / 1                                                       |
| QoS lệnh điều khiển và ACK | 1                                                           |
| Retain                     | Chỉ bật cho `smarthome/+/status` và `smarthome/iot03/state` |

**Tải MQTT hợp lệ nên gồm:**
- IOT01 publish định kỳ **5, 15, 30 hoặc 60 giây**; payload JSON trung bình (ví dụ nhiệt độ, độ ẩm, timestamp).
- IOT02 publish **theo sự kiện**: cửa đóng/mở, phát hiện chuyển động; thời gian giữa các sự kiện không đều (vài giây đến vài chục phút). Ngoài sự kiện, chỉ có keepalive.
- IOT03 publish trạng thái khi có thay đổi và định kỳ **30–60 giây**; nhận lệnh bật/tắt từ dashboard và gửi acknowledgement/state.

## 4. Bộ kịch bản Normal Traffic cho Smart Home

| ID      | Kịch bản                   | Thành phần tham gia                                | Mô tả chính                                                       |    Thời lượng gợi ý |
| ------- | -------------------------- | -------------------------------------------------- | ----------------------------------------------------------------- | ------------------: |
| **S01** | Mạng nhàn rỗi              | 3 camera, 3 IoT, 4–10 user device ở trạng thái chờ | Keepalive, DNS, NTP, push notification, MQTT nền                  |          20–30 phút |
| **S02** | Thiết bị kết nối, DHCP/DNS | User devices, IoT, camera                          | Khởi động, join Wi-Fi, nhận IP, truy vấn dịch vụ                  |          10–15 phút |
| **S03** | Duyệt web / app            | 2–6 Laptop/Phone                                   | Truy cập web, mạng xã hội, đọc tin                                |          20–30 phút |
| **S04** | Video online               | 2–5 user device                                    | Xem video, pause/resume, đổi độ phân giải                         |          20–30 phút |
| **S05** | Truyền file / cloud sync   | 1–3 Laptop/Phone                                   | Download/upload, backup ảnh, sync cloud                           |          15–25 phút |
| **S06** | Gọi video/voice            | 1–3 user device                                    | Call, meeting, bật/tắt camera hoặc màn hình                       |          15–30 phút |
| **S07** | Camera HTTP(S)             | 3 camera + 1–3 viewer                              | Xem live view nếu hỗ trợ, HTTP snapshot, truy cập dashboard       |          20–30 phút |
| **S08** | MQTT sensor định kỳ        | 3 IoT + broker                                     | Publish + keepalive bình thường                                   | **Chạy xuyên suốt** |
| **S09** | Điều khiển Smart Home      | Phone/Laptop + 3 IoT                               | Xem dashboard, gửi lệnh, nhận trạng thái/ACK                      |          15–20 phút |
| **S10** | Reconnect bình thường      | 1–3 smartphone, 1 IoT/camera tùy điều kiện         | Sleep/wake, Wi-Fi reconnect, retry bình thường                    |          10–15 phút |
| **S11** | Mixed: mô phỏng gia đình   | Toàn mạng                                          | Video + web + camera + MQTT + sync đồng thời                      |          45–80 phút |
| **S12** | Giờ cao điểm hợp lệ        | 8–10 user devices + 3 camera + 3 IoT               | Nhiều người truy cập song song, không dùng packet flood generator |          20–40 phút |

**Chi tiết từng kịch bản** (topology, thiết bị, thời gian thu, checklist công việc, checklist nghiệm thu):

| ID | File chi tiết |
|---|---|
| S01 | [S01_idle_network.md](scenarios/S01_idle_network.md) |
| S02 | [S02_device_onboarding_dhcp_dns.md](scenarios/S02_device_onboarding_dhcp_dns.md) |
| S03 | [S03_web_browsing.md](scenarios/S03_web_browsing.md) |
| S04 | [S04_video_streaming.md](scenarios/S04_video_streaming.md) |
| S05 | [S05_file_transfer_cloud_sync.md](scenarios/S05_file_transfer_cloud_sync.md) |
| S06 | [S06_voice_video_call.md](scenarios/S06_voice_video_call.md) |
| S07 | [S07_ip_camera_http.md](scenarios/S07_ip_camera_http.md) |
| S08 | [S08_mqtt_telemetry_background.md](scenarios/S08_mqtt_telemetry_background.md) |
| S09 | [S09_smart_home_control.md](scenarios/S09_smart_home_control.md) |
| S10 | [S10_normal_reconnect.md](scenarios/S10_normal_reconnect.md) |
| S11 | [S11_mixed_household.md](scenarios/S11_mixed_household.md) |
| S12 | [S12_peak_hour.md](scenarios/S12_peak_hour.md) |

**Cách chạy:** S08 là background liên tục; S01–S07 và S09–S12 là **các hoạt động trọng tâm**, có thể chồng lấn. Không cần mỗi kịch bản tương ứng một file PCAP và **không gán nhãn** theo ID kịch bản. ID chỉ có trong kế hoạch/nhật ký phiên thu (`metadata.csv`).

## 5. Capture trên Router

### 5.1. Chuẩn bị (một lần)

1. Tắt flow offloading (mục 2.2).
2. Cài công cụ trên router:
   ```sh
   opkg update && opkg install tcpdump
   ```
3. Đồng bộ thời gian: bật NTP client trên router (`System → Time Synchronization`), đảm bảo server capture và các laptop cũng đồng bộ NTP. Ghi timezone (mặc định `Asia/Ho_Chi_Minh`, UTC+7).
4. Chuẩn bị DHCP static lease và xuất `devices.csv` (mục 6.2).

### 5.2. Capture

Server capture (`192.168.1.60`) SSH vào router và nhận luồng capture từ **`br-lan`**. **Loại bỏ traffic SSH** giữa server và router bằng capture filter để không gây nhiễu dữ liệu.

**Cách A – Wireshark SSH remote capture (sshdump):**

| Trường | Giá trị |
|---|---|
| Remote SSH server | `192.168.1.1`, port `22`, user `root` (dùng SSH key) |
| Remote interface | `br-lan` |
| Remote capture command | để trống (dùng tcpdump mặc định) |
| Remote capture filter | `not (host 192.168.1.60 and port 22)` |
| Snaplen | `0` (lấy đủ gói) |

Lưu output dưới dạng `.pcap` hoặc `.pcapng` theo quy ước đặt tên ở mục 6.

**Cách B – SSH + tcpdump, ghi xoay vòng trên server (khuyến nghị cho phiên dài/S11, S12):**

```sh
ssh root@192.168.1.1 \
  "tcpdump -i br-lan -s 0 -U -w - 'not (host 192.168.1.60 and port 22)'" \
  | tcpdump -r - -w "pcap/<session_id>_%Y%m%d_%H%M%S.pcap" -G 3600
```

- `-G 3600`: tách file mỗi 1 giờ để tránh file quá lớn.
- Khi dừng capture (Ctrl+C), tcpdump trên router in số liệu `packets captured / received by filter / dropped by kernel`. Ghi lại các con số này vào metadata.

**Cách C – Script chung cho mọi kịch bản (khuyến nghị):** [tools/capture_session.py](tools/capture_session.py), chạy trên CAPTURE-SERVER **Windows hoặc Linux** (cần Python ≥ 3.8, Wireshark CLI, OpenSSH client, SSH vào router bằng key). Hướng dẫn đầy đủ: [tools/README.md](tools/README.md).

```sh
# Thu một kịch bản (S08 tự được thêm), 4 thiết bị người dùng  (Linux: dùng python3)
python tools/capture_session.py --scenarios S04 --n-user-devices 4 --config Nho

# Nhiều kịch bản chạy chồng, kèm ghi chú
python tools/capture_session.py --scenarios S05,S07 --n-user-devices 10 --notes "cuoi tuan"

# Chấm lại nghiệm thu / ghi metadata cho phiên bị ngắt giữa chừng
python tools/capture_session.py --scenarios S07 --check-only --session-id SES005
```

Script tự thực hiện:
1. Kiểm tra trước khi thu: flow offloading, Mosquitto, tcpdump trên router, lệch đồng hồ, dung lượng ổ, khung giờ 07:00–18:00.
2. Thu bằng `tcpdump` trên router, đẩy về `dumpcap`. Thời lượng và chu kỳ tách file lấy theo kịch bản. Tự dừng khi hết giờ.
3. Đổi tên file theo quy ước, đọc số liệu bằng `capinfos`, ghi `data/metadata.csv`.
4. Chạy các bộ lọc nghiệm thu tự động bằng `tshark`, xuất `data/logs/<session_id>_report.csv`. Các tiêu chí cần xem bằng mắt (I/O Graph, đối chiếu nhật ký) vẫn làm theo mục 5 của từng file kịch bản.

> Không lưu PCAP trên flash của router: bộ nhớ trong của OpenWrt rất nhỏ. Mọi PCAP được lưu trên **server capture**.

------------ UPDATE LẠI SAU KHI ĐÃ CHẠY THÀNH CÔNG -------------------------
### 5.3. Kiểm tra khi thu
- Theo dõi CPU/RAM router (`top`, `free`). Nếu CPU thường xuyên > 90% trong S11/S12, giảm số thiết bị hoặc ghi chú trong metadata.
- `dropped by kernel` = 0 hoặc rất nhỏ (< 0,1% số gói). Phiên có drop lớn phải ghi chú hoặc thu lại.
- Kiểm tra nhanh sau mỗi phiên: không có PCAP rỗng; có đủ các luồng dự kiến (DNS tới router, MQTT tới `:1883`, HTTP(S) camera ↔ viewer, traffic Internet của user); không có gói SSH của server capture.
- Rà soát sự kiện ngoài dự kiến; phiên có traffic không đúng giả thiết thí nghiệm nên được cách ly/thu lại

## 6. Dữ liệu đầu ra (không nhãn)

| Tầng dữ liệu  | Định dạng           | Nội dung                               |
| ------------- | ------------------- | -------------------------------------- |
| **Packet**    | `.pcap` / `.pcapng` | Dữ liệu gốc từ `br-lan`                |
| **Phiên thu** | `metadata.csv`      | Mô tả từng phiên thu (không phải nhãn) |
| **Thiết bị**  | `devices.csv`       | Bảng đối chiếu MAC ↔ IP ↔ tên thiết bị |


Quy ước tên file PCAP: `<session_id>_<YYYYMMDD>_<HHMMSS>.pcap`, ví dụ `SES001_20261012_145800.pcap`.

### 6.1. Metadata mẫu (chỉ mô tả phiên thu)

`metadata.csv` (thời gian theo ISO 8601, có timezone):

```csv
session_id,pcap_file,start_time,end_time,config,n_user_devices,active_scenarios,pkts_captured,pkts_dropped,notes
SES001,SES001_20261012_145800.pcap,2026-10-12T14:58:00+07:00,2026-10-12T15:12:00+07:00,Nho,4,S02;S08,,,
SES002,SES002_20261012_170800.pcap,2026-10-12T17:08:00+07:00,2026-10-12T17:35:00+07:00,Nho,4,S04;S08,,,
SES003,SES003_20261013_093000.pcap,2026-10-13T09:30:00+07:00,2026-10-13T09:52:00+07:00,Lon,10,S05;S07;S08,,,
SES004,SES004_20261013_134500.pcap,2026-10-13T13:45:00+07:00,2026-10-13T14:14:00+07:00,Lon,10,S03;S08,,,
```

- `active_scenarios`: liệt kê mọi kịch bản chạy trong phiên, ngăn cách bằng `;` (S08 luôn có).
- Nếu một phiên bị tách thành nhiều file bởi `-G`, ghi một dòng cho mỗi file với cùng `session_id`.

### 6.2. Bảng thiết bị

`devices.csv`:

```csv
device_id,type,mac,ip,network,notes
LAPTOP01,Laptop,aa:bb:cc:00:00:01,192.168.1.10,SmartHome,
PHONE01,Smartphone,aa:bb:cc:00:00:15,192.168.1.14,SmartHome,Random MAC tắt
CAM01,Camera,aa:bb:cc:00:00:30,192.168.1.30,SmartHome,HTTP snapshot
IOT01,MQTT,aa:bb:cc:00:00:40,192.168.1.40,SmartHome,Cảm biến môi trường
CAPTURE-SERVER,Capture,aa:bb:cc:00:00:60,192.168.1.60,LAN port,Bị loại khỏi capture
```

> Smartphone thường dùng **MAC ngẫu nhiên** theo từng SSID: tắt tính năng này cho SSID "SmartHome", hoặc ghi lại MAC thực tế mà thiết bị dùng.

## 7. Checklist nghiệm thu

**Chuẩn bị**
- [ ] Có đủ 4–10 thiết bị người dùng (Laptop và Smartphone), **3 camera TCP/HTTP(S)** và **3 IoT MQTT**.
- [ ] Mọi thiết bị Wi-Fi dùng SSID "SmartHome"; broker đặt trên router (hoặc máy riêng cắm dây); đã ghi camera nào cắm dây.
- [ ] Đã **tắt flow offloading** (software + hardware).
- [ ] Đã cấu hình DHCP static lease, có `devices.csv`.
- [ ] Đã kiểm tra đường Internet của lab cho phép các ứng dụng trong kịch bản (QUIC, STUN, mạng xã hội, cloud, video).
- [ ] SSID SmartHome có mật khẩu riêng, chỉ thiết bị trong `devices.csv` được kết nối; kênh Wi-Fi đã cố định và ghi lại.

**Sau khi thu**
- [ ] Có PCAP cho tất cả kịch bản S01–S12 (S12 chỉ với cấu hình ≥ 8 thiết bị người dùng); S08 có mặt trong mọi phiên.
- [ ] Phủ đủ các mức tải: nhàn rỗi, ít, vừa, cao hợp lệ; cả cấu hình Nhỏ và Lớn.
- [ ] Đã kiểm tra packet drop, CPU/RAM router; số liệu được ghi vào `metadata.csv`.
- [ ] PCAP không chứa traffic SSH của server capture; có đủ luồng camera ↔ viewer và IoT ↔ broker.
- [ ] `metadata.csv` có thời gian ISO 8601 + timezone, khớp với timestamp trong PCAP.
- [ ] Danh sách IP trong PCAP khớp `devices.csv`, không có thiết bị lạ của lab.
