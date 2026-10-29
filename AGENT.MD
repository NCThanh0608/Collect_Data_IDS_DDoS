# AGENT.MD — Victim Lab HTTP và UDP Syslog

## Mục tiêu

Duy trì máy đích Raspberry Pi 4 trong WAN ảo do người vận hành kiểm soát. HTTP và UDP Syslog là hai dịch vụ ứng dụng; dashboard hiển thị trạng thái Syslog và bản tin mới ngay trên web. Dữ liệu được thu để phân tích hiệu năng và lỗi trong các lần thử tải có phạm vi xác định. File này là đặc tả phát triển, không phải kịch bản tạo lưu lượng tấn công.

## Bố cục project

- `src/victim_lab/http/`: Flask, đăng nhập, dashboard và API đã xác thực.
- `src/victim_lab/syslog/`: đọc chỉ số rsyslog, tail log có giới hạn và gửi bản tin thử UDP.
- `src/victim_lab/monitor/`: collector định kỳ ghi JSONL có xoay vòng.
- `deploy/rsyslog/`: cấu hình `imudp` chỉ bind IP victim, ruleset riêng và `impstats`.
- `deploy/logrotate/`: giới hạn dung lượng file thống kê rsyslog.
- `deploy/systemd/`: namespace, HTTP, Syslog và collector; các unit được bật khi Pi khởi động.
- `scripts/install_deps.sh`: chỉ cài dependency; `scripts/setup_pi.sh`: triển khai mã, mạng và unit.
- `config/lab-network.env`: subnet private `/24` mặc định; `tests/`: kiểm thử.

## Yêu cầu triển khai

1. Bind HTTP tại IP victim cổng TCP 8080 và rsyslog tại IP victim cổng UDP 514 trong namespace. Script kiểm tra route trùng trước khi cấu hình mạng; router cần static route qua Pi nếu client LAN truy cập dải victim.
2. Rsyslog dùng cấu hình riêng và chỉ nhận đầu vào `imudp` của lab. Log gửi đến được lưu thành JSONL với tên file cố định, không lấy đường dẫn file từ nội dung do sender cung cấp. Xoay log theo dung lượng và giữ ba bản cũ.
3. `impstats` xuất bộ đếm định kỳ ra file riêng, không đẩy lại vào luồng Syslog. Dashboard trình bày rõ `received`, `disallowed`, queue drops và lỗi nhận UDP của kernel là các bộ đếm khác nhau. File thống kê được logrotate xoay vòng.
4. Dashboard giữ đăng nhập, header và logout hiện có; có thẻ HTTP, thẻ Syslog và tối đa 20 bản tin gần nhất. API chỉ trả dữ liệu cho phiên đã đăng nhập. Giới hạn độ dài từng trường và hiển thị bằng văn bản đã escape; không render log như HTML.
5. Nút thử gửi một bản tin Syslog UDP có mã ngẫu nhiên. Giao diện chỉ báo “đã nhận” sau khi thấy mã trong log; thao tác `sendto` thành công chỉ là “đã gửi”.
6. Collector ghi UTC timestamp, `experiment_id`, CPU/RAM/nhiệt độ, network RX/TX/drops, UDP/TCP và snapshot Syslog. Nếu Syslog lỗi, ghi `syslog_error` và tiếp tục lấy mẫu. Giới hạn dung lượng metrics bằng rotation.
7. HTTP chạy qua Gunicorn bằng user `victimlab`. Access log không ghi mật khẩu, cookie, request body hay query string. Các cổng chỉ dùng trong lab, không chuyển tiếp từ Internet công cộng.

## Tiêu chí kiểm tra

- Hai bước `install_deps.sh` và `setup_pi.sh` vẫn độc lập. Setup gỡ unit cũ, kiểm tra cấu hình rsyslog và bật các unit mới khi Pi boot.
- Trang `/healthz` và đăng nhập hoạt động. Nút thử làm bản tin xuất hiện trong danh sách, bộ đếm nhận tăng sau chu kỳ thống kê. Khi Syslog dừng, web vẫn hoạt động và báo dữ liệu Syslog không sẵn sàng.
- Gửi từ PC qua router đến victim cũng xuất hiện trên web. Log dài được cắt ngắn; chuỗi HTML trong log hiện thành chữ, không được thực thi.
- Chạy `python -m unittest discover -s tests -v`; trên Pi, chạy `rsyslogd -N1` và thử gửi UDP 514, kiểm tra sau reboot.

## Tài liệu

- [rsyslog imudp](https://docs.rsyslog.com/doc/configuration/modules/imudp.html)
- [rsyslog impstats](https://docs.rsyslog.com/doc/configuration/modules/impstats.html)
- [rsyslog JSON templates](https://docs.rsyslog.com/doc/configuration/templates.html)
- [Syslog over UDP RFC 5426](https://www.rfc-editor.org/rfc/rfc5426.html)
