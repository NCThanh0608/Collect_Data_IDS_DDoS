# ĐÁNH GIÁ TÍNH TỔNG QUÁT HÓA CỦA BỘ KỊCH BẢN THU NORMAL TRAFFIC

> **Đối tượng đánh giá:** Bộ kịch bản trong [smarthome_normal_traffic_capture_plan.md](smarthome_normal_traffic_capture_plan.md) và 12 kịch bản chi tiết trong thư mục [scenarios/](scenarios/).  
> **Điều kiện thu:** chỉ thu ban ngày (07:00–18:00), không thu buổi tối và ban đêm.  
> **Câu hỏi đặt ra:** Mô hình AI train trên dữ liệu thu theo bộ kịch bản này sẽ chạy chính xác trong những tình huống nào, và sẽ kém chính xác ở đâu?

## 1. Tóm tắt

Mô hình sẽ chạy tốt khi **môi trường triển khai giống môi trường thu**: cùng ngôi nhà, cùng loại thiết bị, cùng điểm capture, **trong khung giờ ban ngày**, và tấn công tạo ra traffic khác rõ so với baseline.

Mô hình sẽ yếu trong bốn trường hợp:
- **Buổi tối và ban đêm**, vì dữ liệu không có khung giờ này.
- Mạng xuất hiện thiết bị hoặc ứng dụng mới chưa có trong baseline.
- Hành vi thật kéo dài và lộn xộn hơn các phiên thu theo kịch bản.
- Tấn công khéo ngụy trang thành traffic bình thường.

## 2. Bản chất của mô hình

Dữ liệu chỉ gồm traffic bình thường và **không gán nhãn**. Vì vậy mô hình thực chất là **phát hiện bất thường**: nó học "bình thường trông như thế nào", rồi cảnh báo mọi thứ lệch khỏi baseline.

Độ chính xác của mô hình phụ thuộc vào hai yếu tố:
1. Baseline có bao phủ đủ các hành vi bình thường ở nơi triển khai hay không. Thiếu thì sinh **báo nhầm** (false positive).
2. Tấn công có tạo ra traffic khác baseline hay không. Không khác thì sinh **bỏ sót** (false negative).

## 3. Tình huống mô hình chạy chính xác

| Tình huống | Mức tin cậy | Lý do |
|---|---|---|
| Cùng ngôi nhà, cùng thiết bị, capture trên `br-lan`, **07:00–18:00**, trong vài tuần đến vài tháng sau khi thu | **Cao** | Phân phối dữ liệu gần như trùng với lúc train |
| Phân đoạn **camera và IoT** | **Cao nhất** | Hành vi rất đều đặn: chu kỳ MQTT, keepalive, đích kết nối cố định. Lệch nhỏ cũng dễ phát hiện |
| Nhà tương tự: 4–16 client, OpenWrt, cùng nhóm thiết bị, ứng dụng phổ biến ở Việt Nam (Zalo, YouTube, FPT Play) | **Khá** | Nằm trong khoảng tải và loại ứng dụng đã thu |
| Tấn công tạo traffic **khác rõ** baseline | **Cao** | Xem mục 3.1 |

### 3.1. Nhóm tấn công phát hiện tốt

| Nhóm tấn công | Vì sao khác baseline | Kịch bản làm mốc |
|---|---|---|
| Quét mạng: port scan, ARP scan, quét dịch vụ camera hoặc MQTT | Baseline không có kiểu một IP kết nối tới rất nhiều cổng hoặc nhiều host | S01, S02 |
| Flood / DoS | Vượt rất xa mức tải hợp lệ cao nhất; S12 không có packet flood | S12 |
| Brute force đăng nhập web camera hoặc MQTT CONNECT | Baseline chỉ có vài lần CONNECT hoặc đăng nhập mỗi phiên | S07, S09, S10 |
| IoT hoặc camera bị chiếm quyền | Kết nối tới đích lạ, cổng lạ, publish dồn dập, topic lạ | S08 |
| Di chuyển ngang trong mạng | Thiết bị người dùng truy cập camera hoặc IoT qua cổng không có trong baseline | S07, S09 |

## 4. Tình huống dễ báo nhầm (false positive)

### 4.1. Buổi tối và ban đêm (18:00–07:00)

Đây là giới hạn lớn nhất do điều kiện thu. Traffic ban đêm khác ban ngày theo ba hướng, và cả ba đều có thể gây báo nhầm:

- **Cao hơn ban ngày:** buổi tối là giờ cao điểm thật của gia đình. Nhiều người cùng xem video, chơi game, gọi điện trong thời gian dài.
- **Có hoạt động chỉ chạy về đêm:** cập nhật hệ điều hành và ứng dụng theo lịch, backup ảnh khi điện thoại đang sạc, đồng bộ cloud, camera chuyển sang hồng ngoại hoặc ghi theo chuyển động.
- **Thấp hơn ban ngày:** sau nửa đêm gần như chỉ còn traffic nền. Mô hình chưa từng thấy khoảng im lặng kéo dài nhiều giờ.

**Khuyến nghị khi triển khai:** chỉ bật cảnh báo trong khung 07:00–18:00. Ngoài khung này, chỉ dùng mô hình cho phân đoạn camera/IoT, vì hành vi của nhóm này ít phụ thuộc giờ trong ngày. Đồng thời ghi rõ giới hạn khi công bố kết quả.

### 4.2. Hành vi bình thường chưa có trong kịch bản

- **Thiết bị mới** như Smart TV, máy chơi game, NAS, loa thông minh. Ví dụ Smart TV phát 4K suốt nhiều giờ.
- **Ứng dụng hoặc giao thức chưa thu:** game online (UDP dày đặc), BitTorrent/P2P, VPN, truy cập từ xa, IPv6 (kịch bản không có kế hoạch riêng cho IPv6).
- **Cập nhật hệ điều hành hoặc firmware.** S01 yêu cầu loại các phiên có cập nhật tự động, nên baseline không có các đợt download lớn bất chợt. Khi triển khai thật, Windows Update hay cập nhật iOS rất dễ bị cảnh báo. Cập nhật firmware OTA của camera/IoT cũng chưa được thu.
- **Sự kiện hợp lệ nhưng hiếm:**
  - Mất điện khiến tất cả thiết bị khởi động **cùng lúc** (S02 cho thiết bị vào mạng lần lượt).
  - Router reboot, mất kết nối Internet, DHCP lease hết hạn.
  - Khách đến nhà kết nối Wi-Fi.

### 4.3. Khác biệt do cách thu theo kịch bản

- **Phiên thu ngắn** (15–80 phút), thao tác theo timeline nên đều đặn hơn đời thực. Sinh hoạt thật kéo dài liên tục nhiều giờ, xen kẽ ngẫu nhiên.
- **Flow dài bị cắt** ở ranh giới phiên. Baseline thiếu các kết nối sống nhiều giờ, ví dụ stream liên tục nhiều giờ, kết nối cloud của camera.
- **Không có chu kỳ ngày/tuần liên tục.** Dữ liệu chỉ là các mảnh rời trong khung ban ngày, nên mô hình không học được nhịp sinh hoạt cả ngày, ví dụ "tối thứ Bảy luôn đông".

### 4.4. Môi trường triển khai khác lúc thu

- Mạng chia VLAN, Wi-Fi mesh, router của nhà mạng thay cho OpenWrt, hoặc capture ở WAN (sau NAT).
- Bật flow offloading, hoặc mọi thiết bị chung một SSID. Khi đó luồng nội bộ biến mất và đặc trưng bị lệch.
- Camera dùng RTSP hoặc cloud P2P, IoT dùng MQTTS 8883 thay vì 1883, hoặc thiết bị qua hub Zigbee.
- Mạng lớn hơn 16 client, hoặc băng thông Internet khác nhiều.

### 4.5. Trôi dữ liệu theo thời gian (concept drift)

Ứng dụng cập nhật làm thay đổi kiểu traffic, giao thức mới xuất hiện (QUIC, ECH), thói quen thay đổi theo mùa và dịp lễ. Sau vài tháng nên thu bổ sung và train lại.

## 5. Tình huống dễ bỏ sót tấn công (false negative)

### 5.1. Tấn công ngụy trang thành hành vi đã có trong baseline

| Tấn công | Trông giống | Kịch bản tương ứng |
|---|---|---|
| Rò rỉ dữ liệu qua HTTPS lên cloud | Upload, đồng bộ cloud | S05 |
| Mã độc liên lạc với máy chủ điều khiển (C2) qua HTTPS theo chu kỳ | Push notification, keepalive | S01 |
| Lệnh MQTT giả mạo dùng **đúng topic và tần suất** | Người dùng điều khiển thiết bị | S09 |
| Brute force hoặc dò mật khẩu rất chậm | Reconnect bình thường | S10 |
| Tấn công có tải thấp hơn mức cao điểm | Giờ cao điểm hợp lệ | S12 |

Với lệnh MQTT giả mạo, mô hình dựa trên flow không phân biệt được lệnh của người dùng với lệnh của kẻ tấn công.

### 5.2. Vùng mà điểm thu không nhìn thấy

- Tấn công tầng Wi-Fi như deauth, evil twin, crack WPA: không xuất hiện trên `br-lan`.
- Traffic giữa hai thiết bị **cùng SSID**: không đi qua bridge.
- Nội dung đã mã hóa: mô hình chỉ thấy metadata của flow.

### 5.3. Không đo được độ chính xác thật

Dữ liệu không có traffic tấn công, nên không tính được detection rate hay tỷ lệ báo nhầm trên tấn công. Cần một tập test tấn công riêng, thu trên cùng môi trường, để đánh giá.

## 6. Bảng đánh giá tổng hợp

| Khía cạnh | Đánh giá | Ghi chú |
|---|---|---|
| Độ phủ loại hoạt động bình thường | **Tốt** | 12 kịch bản phủ đủ các nhóm chính của Smart Home |
| Độ phủ mức tải | **Tốt** | Từ nhàn rỗi (S01) đến cao điểm hợp lệ (S12) |
| Độ phủ thời gian | **Yếu** | Chỉ 07:00–18:00; phiên ngắn, rời rạc; không có buổi tối, ban đêm |
| Độ phủ thiết bị và ứng dụng | **Trung bình** | Thiếu TV, console, cập nhật, OTA, IPv6 |
| Độ phủ sự kiện hiếm hợp lệ | **Yếu** | Thiếu mất điện đồng loạt, router reboot, mất mạng ISP, khách |
| Khả năng chuyển sang nhà khác | **Hạn chế** | Dữ liệu từ một ngôi nhà, một topology |
| Độ tin cậy riêng cho camera/IoT | **Cao** | Hành vi đều đặn, dễ xác lập baseline |

## 7. Khuyến nghị cải thiện

Không cần đổi khung kịch bản. Ba việc mang lại nhiều nhất, theo thứ tự ưu tiên:

1. **Thu liên tục nhiều giờ trong khung 07:00–18:00** ở nhiều ngày khác nhau (ngày thường và cuối tuần), không theo kịch bản, chỉ sinh hoạt tự nhiên. Việc này bù một phần độ phủ thời gian và các flow dài. Nếu sau này thu được buổi tối/ban đêm, đó là bổ sung có giá trị nhất.
2. **Giữ lại các phiên có cập nhật OS/firmware** và thêm vài sự kiện hiếm hợp lệ (mất điện đồng loạt, router reboot, mất mạng ISP, khách kết nối), thay vì loại bỏ chúng.
3. **Chuẩn bị một tập tấn công riêng để test**, thu trên cùng hạ tầng, để đo được độ chính xác thật của mô hình.

Các khuyến nghị bổ sung cho giai đoạn xây dựng mô hình:

- **Ưu tiên đặc trưng theo từng host hoặc tỷ lệ**, ví dụ số byte trên mỗi thiết bị, thay cho tổng tuyệt đối của cả mạng. Như vậy mô hình ít phụ thuộc vào số thiết bị trong mạng.
- **Chia train/test theo phiên hoặc theo ngày**, không chia ngẫu nhiên theo flow. Chia ngẫu nhiên làm kết quả đánh giá đẹp giả tạo.
- **Ghi rõ phạm vi áp dụng khi công bố kết quả:** một ngôi nhà, 10–16 client, OpenWrt, capture trên `br-lan`, **chỉ ban ngày 07:00–18:00**, khoảng thời gian thu cụ thể.
- **Lên kế hoạch thu bổ sung và train lại định kỳ** (ví dụ 3–6 tháng) để xử lý concept drift.
