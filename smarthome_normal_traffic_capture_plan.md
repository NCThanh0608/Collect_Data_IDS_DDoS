# KỊCH BẢN THU THẬP NORMAL TRAFFIC – MẠNG SMART HOME

> **Phiên bản:** Smart Home (4–10 PC/Laptop/Smartphone + 3 camera TCP/HTTP + 3 IoT MQTT)  
> **Điểm thu:** Router OpenWrt, interface **`br-lan`**  
> **Phạm vi dữ liệu:** Chỉ lưu lượng hoạt động bình thường. **Không gán nhãn** packet, flow hoặc time window.  
> **Mục tiêu sử dụng:** Xây dựng baseline lưu lượng Smart Home, phục vụ phân tích flow và đặc trưng theo cửa sổ thời gian cho IDS.

## 1. Quy mô và nguyên tắc

### 1.1. Quy mô cố định và quy mô biến thiên

| Nhóm | Số lượng | Đặc điểm hoạt động | Giao thức chính |
|---|---:|---|---|
| PC/Laptop và Smartphone | **4–10** (tổng hai nhóm) | Duyệt web, xem video, tải file, họp online, đồng bộ dữ liệu, dùng app Smart Home | DNS, HTTPS/TCP, QUIC/UDP, ICMP, NTP |
| IP camera | **3** | Xem trực tiếp, chụp snapshot, app/dashboard truy cập camera, kết nối lại bình thường | **TCP/HTTP** hoặc **HTTPS** (tùy thiết bị) |
| Thiết bị IoT | **3** | Publish telemetry, nhận lệnh điều khiển, keepalive/reconnect | **MQTT/TCP** (`1883`), có thể dùng **MQTTS** (`8883`) |
| Router thu thập | **1** | Gateway, DHCP/DNS, MQTT broker (khuyến nghị), điểm capture `br-lan` | Các giao thức đi qua router |
| Server capture | **1** | SSH vào router, nhận và lưu PCAP | SSH (bị loại khỏi capture) |

**Tổng số client:** **10–16 thiết bị** (= 4–10 thiết bị người dùng + 3 camera + 3 thiết bị MQTT), **không tính router và server capture**.

Không cần bổ sung máy ảo để đạt đủ số lượng nếu đã có thiết bị thật. Nếu dùng VMware giả lập PC/laptop, nên dùng **Bridged Network** và kiểm tra VM được router nhận diện bằng IP riêng.

### 1.2. Hai cấu hình phân bổ thiết bị người dùng

| Cấu hình | PC/Laptop | Smartphone | Tổng thiết bị người dùng | Tổng client gồm camera + IoT |
|---|---:|---:|---:|---:|
| **Nhỏ** | 2 | 2 | **4** | **10** |
| **Lớn** | 5 | 5 | **10** | **16** |

Có thể dùng các mức trung gian 6 hoặc 8 thiết bị người dùng, nhưng 3 camera và 3 MQTT vẫn duy trì để so sánh nhất quán. Kịch bản **S12** chỉ chạy được với cấu hình có **≥ 8** thiết bị người dùng.

### 1.3. Nguyên tắc thu

- Chỉ thực hiện các hoạt động sử dụng mạng hợp lệ trong Smart Home; **không mô phỏng tấn công** trong các phiên này.
- Không tạo trường `label`, `class`, `attack_type` hoặc gán `Benign` cho từng bản ghi.
- Giữ lại **PCAP gốc**, có thể tách flow/time-window phục vụ phân tích sau; lưu metadata vận hành ở **cấp phiên thu** để biết đang có thiết bị và hoạt động nào.
- Thu các trạng thái **nhàn rỗi, sử dụng ít, sử dụng vừa, tải cao hợp lệ**, cùng tình huống nhiều thiết bị hoạt động đồng thời.
- **Khung giờ thu: chỉ ban ngày, 07:00–18:00.** Không thu buổi tối và ban đêm. Để bù lại, nên trải các phiên đều trong khung giờ (sáng, trưa, chiều) và trên cả ngày thường lẫn cuối tuần. Dataset chỉ đại diện cho traffic ban ngày (xem [generalization_assessment.md](generalization_assessment.md)).
- Đảm bảo traffic thực sự **đi qua CPU router và hiện trên `br-lan`** (xem mục 2.2), tránh kết luận sai do traffic LAN-to-LAN được chuyển mạch trực tiếp trong switch chip hoặc driver Wi-Fi.
- PCAP chứa dữ liệu cá nhân của người dùng thật: cần sự **đồng ý** của các thành viên trong nhà và có phương án **ẩn danh hóa** (IP/MAC, DNS query, SNI) trước khi chia sẻ dataset.

## 2. Kiến trúc mạng Smart Home

### 2.1. Topology

Tất cả thiết bị nằm trong **một subnet `192.168.10.0/24`** trên bridge `br-lan` của OpenWrt. Thiết bị người dùng và camera/IoT dùng **hai SSID khác nhau** nhưng cùng được bridge vào `br-lan`.

```text
                          INTERNET
                              |
                            (WAN)
                     ROUTER OpenWrt 192.168.10.1
                     - DHCP/DNS, NTP
                     - Mosquitto broker :1883
                     - tcpdump trên br-lan
                              |
                           br-lan
          +-------------------+-------------------+-----------------+
          |                                       |                 |
   SSID "SmartHome-User"                   SSID "SmartHome-IoT"     LAN port
   4–10 PC/Laptop/Phone                    CAM01 CAM02 CAM03   Server capture
   192.168.10.10–19                        IOT01 IOT02 IOT03   192.168.10.60
                                           192.168.10.30–42
```

- **SmartHome-User**: SSID cho thiết bị người dùng. **SmartHome-IoT**: SSID cho camera và thiết bị IoT. Cả hai cùng bridge vào `br-lan`.

- Nếu không thể chạy broker trên router, đặt broker ở máy riêng `192.168.10.50` và kết nối vào SSID **"SmartHome-User"** (khác SSID với IoT) để luồng IoT → broker đi qua bridge.

### 2.2. Điều kiện để traffic hiện trên `br-lan`

Capture trên `br-lan` thấy được: traffic client ↔ Internet (trước NAT, còn nguyên IP nội bộ), traffic client ↔ router (DNS, DHCP, MQTT broker trên router) và traffic giữa các cổng của bridge mà CPU xử lý. Các trường hợp sau **không** hiện trên `br-lan` và cần xử lý:

| Trường hợp | Nguyên nhân | Cách xử lý |
|---|---|---|
| Hai client cùng một SSID nói chuyện với nhau | Driver Wi-Fi (mac80211) chuyển gói nội bộ trong BSS, không qua bridge | Tách SSID SmartHome-User / SmartHome-IoT; broker đặt trên router |
| Hai thiết bị cắm dây cùng switch chip | Switch chip chuyển mạch phần cứng | Hạn chế thiết bị có dây; thiết bị có dây chỉ nói chuyện với Internet/router |
| Flow offloading bật | Gói của kết nối đã thiết lập bỏ qua đường xử lý thông thường, có thể không thấy trong capture | **Tắt** software và hardware flow offloading |
| Traffic do chính router tạo ra ra WAN | Không đi qua `br-lan` | Không thuộc phạm vi thu (chấp nhận) |

Tắt flow offloading:

```sh
uci set firewall.@defaults[0].flow_offloading='0'
uci set firewall.@defaults[0].flow_offloading_hw='0'
uci commit firewall
/etc/init.d/firewall restart
```

Firewall: chỉ cho phép các luồng cần thiết (User → camera, IoT → broker, client → Internet); không mở truy cập ngoài ý muốn.

### 2.3. Kế hoạch IP mẫu

| Thiết bị             | Địa chỉ mẫu        | Mạng kết nối        | Vai trò                          |
| -------------------- | ------------------ | ------------------- | -------------------------------- |
| Router               | `192.168.10.1`     | —                   | Gateway, DHCP/DNS, broker, capture |
| PC/Laptop/Smartphone | `192.168.10.10–19` | SSID "SmartHome-User"    | Người dùng: 4–10 thiết bị        |
| Camera 01–03         | `192.168.10.30–32` | SSID "SmartHome-IoT"     | TCP/HTTP(S)                      |
| MQTT IoT 01–03       | `192.168.10.40–42` | SSID "SmartHome-IoT"     | Telemetry và nhận lệnh           |
| Broker riêng (tùy chọn) | `192.168.10.50` | SSID "SmartHome-User"    | Chỉ dùng nếu không chạy broker trên router |
| Server capture       | `192.168.10.60`    | Cổng LAN có dây     | SSH vào router, lưu PCAP         |

**Mã thiết bị chuẩn** (dùng thống nhất trong mọi file kịch bản):

| Device ID | Loại | IP | Mạng | Cấu hình Nhỏ | Cấu hình Lớn |
|---|---|---|---|:---:|:---:|
| ROUTER | Router OpenWrt | 192.168.10.1 | — | ✔ | ✔ |
| PC01 – PC05 | PC/Laptop | .10 – .14 | SmartHome-User | PC01, PC02 | ✔ |
| PHONE01 – PHONE05 | Smartphone | .15 – .19 | SmartHome-User | PHONE01, PHONE02 | ✔ |
| CAM01 – CAM03 | IP camera | .30 – .32 | SmartHome-IoT | ✔ | ✔ |
| IOT01 – IOT03 | IoT MQTT | .40 – .42 | SmartHome-IoT | ✔ | ✔ |
| CAPTURE-SERVER | Server capture | .60 | LAN port | ✔ | ✔ |

Dùng **DHCP static lease** (reservation theo MAC) để IP ổn định, giúp đối chiếu thiết bị mà không cần gán nhãn dữ liệu. Ghi bảng MAC ↔ IP ↔ tên thiết bị vào `devices.csv` (mục 6).

## 3. Hành vi cụ thể của từng nhóm thiết bị

### 3.1. Nhóm 4–10 PC/Laptop/Smartphone

**PC/Laptop**
- Mở website, đọc nội dung, tìm kiếm và chuyển trang trong khoảng nghỉ tự nhiên.
- Xem YouTube/phim trực tuyến; thay đổi video, pause/resume và chất lượng.
- Download/upload file cá nhân hoặc file kiểm thử hợp lệ (ví dụ 5 MB, 50 MB, 200 MB).
- Họp trực tuyến, gọi thoại, chia sẻ màn hình.
- Đồng bộ cloud, cập nhật ứng dụng/hệ điều hành nếu có và quản trị thiết bị trong mạng.

**Smartphone**
- Mở ứng dụng mạng xã hội, duyệt tin, xem video ngắn hoặc phát video.
- Gửi/nhận tin nhắn và cuộc gọi qua ứng dụng, đồng bộ ảnh/backup.
- Khóa/mở màn hình, chuyển foreground/background, chuyển Wi-Fi off/on rồi kết nối lại **trong thao tác sử dụng thông thường**.
- Dùng ứng dụng để mở dashboard Smart Home, xem camera, đọc sensor và điều khiển thiết bị MQTT qua backend hợp lệ.

> **Gợi ý quan trọng:** Smartphone khác PC vì tạo nhiều đợt traffic ngắn theo thói quen mở app, thông báo đẩy, đồng bộ nền và sleep/wake. Nên ghi nhận cả thời gian để điện thoại ở trạng thái chờ, không chỉ liên tục phát video.

### 3.2. Nhóm 3 camera **TCP/HTTP**

Với mỗi camera, chỉ dùng các giao thức mà firmware **thực sự hỗ trợ**. Nếu camera truyền ảnh/video qua HTTP hoặc HTTPS, có thể thiết kế:

| Camera | Hoạt động nền | Hoạt động khi có người dùng |
|---|---|---|
| **CAM01** | Đăng nhập/kiểm tra trạng thái theo app | Smartphone 01 mở live view, dừng rồi mở lại |
| **CAM02** | HTTP(S) status hoặc snapshot định kỳ nếu hỗ trợ | PC/Laptop truy cập live view/snapshot, đổi trang |
| **CAM03** | Keepalive hoặc liên hệ cloud theo cấu hình thật | Hai người dùng xem đồng thời nếu firmware cho phép |

- Nếu camera chỉ hỗ trợ **HTTP snapshot**, cho app/dashboard lấy snapshot ở chu kỳ vừa phải (ví dụ **2–10 giây**); **không coi đó là video stream**.
- Nếu camera hỗ trợ **MJPEG over HTTP** hoặc luồng HTTP(S) liên tục, thực hiện các phiên xem trực tiếp 5–20 phút, với 1–2 người xem nếu được phép.
- Nếu nhà sản xuất chỉ cung cấp cloud/P2P độc quyền, giữ luồng thực tế của app, **không tự giả định** là RTSP hoặc HTTP.
- Có thể thêm sự kiện hợp lệ: người dùng vào app, đổi camera, thoát app, camera reconnect sau gián đoạn Wi-Fi thông thường.
- Viewer phải ở SSID "SmartHome-User", camera ở SSID "SmartHome-IoT" để luồng **camera → viewer** đi qua `br-lan` (mục 2.2).

### 3.3. Nhóm 3 IoT **MQTT**

Quy ước topic: `smarthome/<device_id>/<message_type>`, chữ thường, không dấu cách.

| IoT       | Vai trò                      | Publish                                                    | Subscribe / điều khiển  |
| --------- | ---------------------------- | ---------------------------------------------------------- | ----------------------- |
| **IOT01** | Cảm biến môi trường          | `smarthome/iot01/telemetry`                                | `smarthome/iot01/cmd`   |
| **IOT02** | Cảm biến cửa / chuyển động   | `smarthome/iot02/event`                                    | `smarthome/iot02/cmd`   |
| **IOT03** | Ổ cắm / công tắc thông minh  | `smarthome/iot03/state`, `smarthome/iot03/ack`             | `smarthome/iot03/cmd`   |

Mọi thiết bị đều có thêm topic `smarthome/<device_id>/status` (`online`/`offline`), dùng làm Last Will (LWT) khi mất kết nối.

**Tham số MQTT cố định cho mọi phiên** (ghi vào metadata nếu thay đổi):

| Tham số | Giá trị mẫu |
|---|---|
| Broker | `192.168.10.1:1883` (hoặc `8883` nếu dùng TLS) |
| Keepalive | 60 giây |
| QoS telemetry / sự kiện | 0 / 1 |
| QoS lệnh điều khiển và ACK | 1 |
| Retain | Chỉ bật cho `smarthome/+/status` và `smarthome/iot03/state` |

**Tải MQTT hợp lệ nên gồm:**
- IOT01 publish định kỳ **5, 15, 30 hoặc 60 giây**; payload JSON trung bình (ví dụ nhiệt độ, độ ẩm, timestamp).
- IOT02 publish **theo sự kiện**: cửa đóng/mở, phát hiện chuyển động; thời gian giữa các sự kiện không đều (vài giây đến vài chục phút). Ngoài sự kiện, chỉ có keepalive.
- IOT03 publish trạng thái khi có thay đổi và định kỳ **30–60 giây**; nhận lệnh bật/tắt từ dashboard và gửi acknowledgement/state.

## 4. Bộ kịch bản Normal Traffic cho Smart Home

| ID      | Kịch bản                   | Thành phần tham gia                                | Mô tả chính                                                       |    Thời lượng gợi ý |
| ------- | -------------------------- | -------------------------------------------------- | ----------------------------------------------------------------- | ------------------: |
| **S01** | Mạng nhàn rỗi              | 3 camera, 3 IoT, 4–10 user device ở trạng thái chờ | Keepalive, DNS, NTP, push notification, MQTT nền                  |          20–30 phút |
| **S02** | Thiết bị kết nối, DHCP/DNS | User devices, IoT, camera                          | Khởi động, join Wi-Fi, nhận IP, truy vấn dịch vụ                  |          10–15 phút |
| **S03** | Duyệt web / app            | 2–6 PC/Laptop/Phone                                | Truy cập web, mạng xã hội, đọc tin                                |          20–30 phút |
| **S04** | Video online               | 2–5 user device                                    | Xem video, pause/resume, đổi độ phân giải                         |          20–30 phút |
| **S05** | Truyền file / cloud sync   | 1–3 PC/Laptop/Phone                                | Download/upload, backup ảnh, sync cloud                           |          15–25 phút |
| **S06** | Gọi video/voice            | 1–3 user device                                    | Call, meeting, bật/tắt camera hoặc màn hình                       |          15–30 phút |
| **S07** | Camera HTTP(S)             | 3 camera + 1–3 viewer                              | Xem live view nếu hỗ trợ, HTTP snapshot, truy cập dashboard       |          20–30 phút |
| **S08** | MQTT sensor định kỳ        | 3 IoT + broker                                     | Publish + keepalive bình thường                                   | **Chạy xuyên suốt** |
| **S09** | Điều khiển Smart Home      | Phone/PC + 3 IoT                                   | Xem dashboard, gửi lệnh, nhận trạng thái/ACK                      |          15–20 phút |
| **S10** | Reconnect bình thường      | 1–3 smartphone, 1 IoT/camera tùy điều kiện         | Sleep/wake, Wi-Fi reconnect, retry bình thường                    |          10–15 phút |
| **S11** | Mixed: sinh hoạt gia đình  | Toàn mạng                                          | Video + web + camera + MQTT + sync đồng thời                      |          45–80 phút |
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
3. Đồng bộ thời gian: bật NTP client trên router (`System → Time Synchronization`), đảm bảo server capture và các PC/laptop cũng đồng bộ NTP. Ghi timezone (mặc định `Asia/Ho_Chi_Minh`, UTC+7).
4. Chuẩn bị DHCP static lease và xuất `devices.csv` (mục 6.2).

### 5.2. Capture

Server capture (`192.168.10.60`) SSH vào router và nhận luồng capture từ **`br-lan`**. **Loại bỏ traffic SSH** giữa server và router bằng capture filter để không gây nhiễu dữ liệu.

**Cách A – Wireshark SSH remote capture (sshdump):**

| Trường | Giá trị |
|---|---|
| Remote SSH server | `192.168.10.1`, port `22`, user `root` (dùng SSH key) |
| Remote interface | `br-lan` |
| Remote capture command | để trống (dùng tcpdump mặc định) |
| Remote capture filter | `not (host 192.168.10.60 and port 22)` |
| Snaplen | `0` (lấy đủ gói) |

Lưu output dưới dạng `.pcap` hoặc `.pcapng` theo quy ước đặt tên ở mục 6.

**Cách B – SSH + tcpdump, ghi xoay vòng trên server (khuyến nghị cho phiên dài/S11, S12):**

```sh
ssh root@192.168.10.1 \
  "tcpdump -i br-lan -s 0 -U -w - 'not (host 192.168.10.60 and port 22)'" \
  | tcpdump -r - -w "pcap/<session_id>_%Y%m%d_%H%M%S.pcap" -G 3600
```

- `-G 3600`: tách file mỗi 1 giờ để tránh file quá lớn.
- Khi dừng capture (Ctrl+C), tcpdump trên router in số liệu `packets captured / received by filter / dropped by kernel`. Ghi lại các con số này vào metadata.

**Cách C – Script chung cho mọi kịch bản (khuyến nghị):** [tools/capture_session.ps1](tools/capture_session.ps1), chạy trên CAPTURE-SERVER (Windows, đã cài Wireshark và OpenSSH client, SSH vào router bằng key).

```bat
:: Thu một kịch bản (S08 tự được thêm), 4 thiết bị người dùng
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S04 -NUserDevices 4 -Config Nho

:: Nhiều kịch bản chạy chồng, kèm ghi chú
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S05,S07 -NUserDevices 10 -Notes "cuoi tuan"

:: Chấm lại nghiệm thu / ghi metadata cho phiên đã dừng sớm
powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S07 -CheckOnly -SessionId SES005
```

Script tự thực hiện:
1. Kiểm tra trước khi thu: flow offloading, Mosquitto, tcpdump trên router, lệch đồng hồ, dung lượng ổ, khung giờ 07:00–18:00.
2. Thu bằng `tcpdump` trên router, đẩy về `dumpcap`. Thời lượng và chu kỳ tách file lấy theo kịch bản. Tự dừng khi hết giờ.
3. Đổi tên file theo quy ước, đọc số liệu bằng `capinfos`, ghi `data/metadata.csv`.
4. Chạy các bộ lọc nghiệm thu tự động bằng `tshark`, xuất `data/logs/<session_id>_report.csv`. Các tiêu chí cần xem bằng mắt (I/O Graph, đối chiếu nhật ký) vẫn làm theo mục 5 của từng file kịch bản.

> Không lưu PCAP trên flash của router: bộ nhớ trong của OpenWrt rất nhỏ. Mọi PCAP được lưu trên **server capture**.

### 5.3. Kiểm tra khi thu

- Đồng hồ router, server capture, PC/laptop và broker lệch nhau không quá 1 giây.
- Theo dõi CPU/RAM router (`top`, `free`). Nếu CPU thường xuyên > 90% trong S11/S12, giảm số thiết bị hoặc ghi chú trong metadata.
- `dropped by kernel` = 0 hoặc rất nhỏ (< 0,1% số gói). Phiên có drop lớn phải ghi chú hoặc thu lại.
- Kiểm tra nhanh sau mỗi phiên: không có PCAP rỗng; có đủ các luồng dự kiến (DNS tới router, MQTT tới `:1883`, HTTP(S) camera ↔ viewer, traffic Internet của user); không có gói SSH của server capture.
- Rà soát sự kiện ngoài dự kiến; phiên có traffic không đúng giả thiết thí nghiệm nên được cách ly/thu lại, thay vì gán nhãn attack.

## 6. Dữ liệu đầu ra (không nhãn)

| Tầng dữ liệu | Định dạng | Nội dung |
| ------------ | --------- | -------- |
| **Packet**   | `.pcap` / `.pcapng` | Dữ liệu gốc từ `br-lan` |
| **Phiên thu** | `metadata.csv` | Mô tả từng phiên thu (không phải nhãn) |
| **Thiết bị** | `devices.csv` | Bảng đối chiếu MAC ↔ IP ↔ tên thiết bị |

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
PC01,PC/Laptop,aa:bb:cc:00:00:01,192.168.10.10,SmartHome-User,
PHONE01,Smartphone,aa:bb:cc:00:00:15,192.168.10.15,SmartHome-User,Random MAC tắt
CAM01,Camera,aa:bb:cc:00:00:30,192.168.10.30,SmartHome-IoT,HTTP snapshot
IOT01,MQTT,aa:bb:cc:00:00:40,192.168.10.40,SmartHome-IoT,Cảm biến môi trường
CAPTURE-SERVER,Capture,aa:bb:cc:00:00:60,192.168.10.60,LAN port,Bị loại khỏi capture
```

> Smartphone thường dùng **MAC ngẫu nhiên** theo từng SSID: tắt tính năng này cho SSID "SmartHome-User", hoặc ghi lại MAC thực tế mà thiết bị dùng.

## 7. Checklist nghiệm thu

**Chuẩn bị**
- [ ] Có đủ 4–10 thiết bị người dùng (PC/Laptop và Smartphone), **3 camera TCP/HTTP(S)** và **3 IoT MQTT**.
- [ ] Đã tách SSID "SmartHome-User" / "SmartHome-IoT", broker đặt trên router (hoặc khác SSID với IoT).
- [ ] Đã **tắt flow offloading** (software + hardware).
- [ ] Đã cấu hình DHCP static lease, có `devices.csv`, đã xử lý MAC ngẫu nhiên của smartphone.
- [ ] Router, server capture, PC/laptop đã đồng bộ NTP.
- [ ] Có sự đồng ý của người dùng trong nhà về việc thu traffic.

**Sau khi thu**
- [ ] Có PCAP cho tất cả kịch bản S01–S12 (S12 chỉ với cấu hình ≥ 8 thiết bị người dùng); S08 có mặt trong mọi phiên.
- [ ] Phủ đủ các mức tải: nhàn rỗi, ít, vừa, cao hợp lệ; cả cấu hình Nhỏ và Lớn.
- [ ] Mọi phiên nằm trong khung 07:00–18:00; các phiên trải đều sáng / trưa / chiều, có cả ngày thường và cuối tuần.
- [ ] Đã kiểm tra packet drop, CPU/RAM router; số liệu được ghi vào `metadata.csv`.
- [ ] PCAP không chứa traffic SSH của server capture; có đủ luồng camera ↔ viewer và IoT ↔ broker.
- [ ] `metadata.csv` có thời gian ISO 8601 + timezone, khớp với timestamp trong PCAP.
