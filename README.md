# Victim Lab trên Raspberry Pi 4

Project chạy web HTTP và một máy chủ UDP Syslog thật trong network namespace `victim`. Dashboard giữ trang đăng nhập hiện có, hiển thị thẻ HTTP, thẻ Syslog và tối đa 20 bản tin gần nhất. Collector ghi chỉ số máy, mạng và Syslog để quan sát thí nghiệm trong WAN ảo.

## Cấu trúc

```text
src/victim_lab/http/       Flask, template và tài nguyên web
src/victim_lab/syslog/     Đọc chỉ số, đọc log và gửi bản tin thử
src/victim_lab/monitor/    Collector JSONL
deploy/rsyslog/            Cấu hình rsyslog riêng của lab
deploy/logrotate/          Xoay file thống kê rsyslog
deploy/systemd/           Các unit khởi động cùng Pi
scripts/                  Cài dependency, triển khai, xoay log, kiểm tra subnet
config/                   Subnet lab mặc định
tests/                    Kiểm thử ứng dụng và cấu hình mạng
requirements.txt          Dependency Python
```

## Cài và triển khai

Yêu cầu Raspberry Pi OS/Linux với `systemd` 248 trở lên, Python 3, quyền `sudo` và kết nối Internet khi cài dependency. Chạy từ thư mục project trên Pi:

```bash
sudo bash scripts/install_deps.sh
sudo bash scripts/setup_pi.sh
```

Trên Ubuntu có AppArmor, `setup_pi.sh` cài rule riêng cho rsyslog để đọc
`/opt/victim-lab/rsyslog/victim.conf` và ghi log của lab, rồi nạp lại profile
trước khi kiểm tra cấu hình. Nếu bản cài cũ báo `could not open config file ...
Permission denied`, cập nhật project và chạy lại `sudo bash scripts/setup_pi.sh`.
Không cần tắt AppArmor.

`install_deps.sh` cài rsyslog và dependency Python vào `/opt/victim-lab/.venv`; bước này không đổi mạng hoặc khởi động service. `setup_pi.sh` dựng hoặc kiểm tra namespace, chép mã, kiểm tra cấu hình rsyslog, cài unit và bật chúng khi Pi khởi động. Khi chỉ cập nhật mã hoặc giao diện, chạy lại `setup_pi.sh` là đủ. Bản triển khai mới dừng và gỡ unit CoAP cũ; các file metrics đã thu trước đó vẫn được giữ.

Nếu router hoặc client còn dùng IP LAN của Pi làm DNS, đổi sang máy chủ DNS khác đang hoạt động trước khi nâng cấp. Project không còn tiến trình phục vụ cổng 53.

Địa chỉ mặc định là `10.20.0.1/24` trên Pi host và `10.20.0.2/24` trong namespace `victim`. Script tự tạo cặp veth nếu chưa có namespace. Nếu topology WAN ảo riêng đã tạo namespace, cần gán sẵn IP máy đích và route phù hợp. Script từ chối dải mạng trùng route khác trên Pi.

Để đổi dải mạng:

```bash
sudo bash scripts/setup_pi.sh --subnet 10.30.0.0/24
```

Chọn dải IPv4 private `/24` chưa trùng. Script dùng `.1` cho Pi, `.2` cho victim và cập nhật địa chỉ bind của HTTP, Syslog. Nếu router có static route đến dải cũ, sửa route đến dải mới qua IP LAN ổn định của Pi.

## Truy cập web và gửi Syslog

Với dải mặc định, mở `http://10.20.0.2:8080/login`, đăng nhập `admin/admin`. Dashboard cập nhật khoảng 3 giây/lần. Thẻ Syslog cho biết số bản tin đã nhận, bản tin/giây, số bị rsyslog từ chối, số bị hàng đợi loại bỏ và lỗi nhận UDP của kernel trong namespace. Danh sách chỉ tải 20 log gần nhất; mỗi nội dung hiển thị tối đa 500 ký tự và được đưa vào trang dưới dạng văn bản.

Nút **Gửi thử bản tin Syslog** gửi UDP từ web server, rồi chờ thấy mã bản tin trong log mới báo “đã nhận”. Nó kiểm tra đường nội bộ web → Syslog. Để kiểm tra tuyến PC → router → victim, cấu hình client trên PC gửi Syslog đến `10.20.0.2:514/udp`.

Ví dụ Pi có LAN IP cố định `192.168.1.146` và router phục vụ `192.168.1.0/24`: đặt static route trên router với đích `10.20.0.0/24`, gateway `192.168.1.146`, interface LAN. Pi và namespace cần route hai chiều; script cấu hình phần này khi nó quản lý cặp veth. Trang web dùng TCP 8080; client gửi log trực tiếp dùng UDP 514. Chỉ cho phép các cổng này trong lab, không chuyển tiếp từ Internet công cộng. Không đặt IP Pi trong vùng DHCP có thể cấp cho máy khác.

Kiểm tra trên Pi:

```bash
sudo systemctl status victim-netns victim-http victim-syslog victim-monitor --no-pager
sudo systemctl is-enabled victim-netns victim-http victim-syslog victim-monitor
sudo rsyslogd -N1 -f /opt/victim-lab/rsyslog/victim.conf
sudo ip netns exec victim logger --udp --server 10.20.0.2 --port 514 --tag lab-test "hello from Pi"
```

Thay địa chỉ `.2` nếu đã đổi subnet. Sau khi gửi, kiểm tra thẻ Syslog hoặc `sudo tail /var/log/victim-lab/syslog.jsonl`. Nếu trang báo chưa có số liệu ngay sau khi khởi động, chờ chu kỳ `impstats` đầu tiên, khoảng 5 giây.

Nếu bộ đếm nhận tăng nhưng danh sách log trống, kiểm tra một bản tin gần nhất có phải JSON hợp lệ không:

```bash
sudo tail -n 1 /var/log/victim-lab/syslog.jsonl | python3 -m json.tool
```

Rsyslog 8.2504 cần mẫu ghi JSONL có dấu xuống dòng nằm ngoài object JSON. Bản cấu hình trước từng ghi dấu phẩy thừa và dấu `}` ở dòng riêng; bản đọc mới vẫn hiển thị được các bản tin cũ đó, còn bản ghi mới sẽ là một JSON hợp lệ trên mỗi dòng.

## Chỉ số và log

- `/var/log/victim-lab/syslog.jsonl`: bản tin Syslog dạng JSONL, xoay khi đạt khoảng 20 MiB. Giữ tối đa ba bản cũ `.1`–`.3`; mỗi lần xoay tiếp theo tự xóa bản cũ nhất.
- `/var/log/victim-lab/rsyslog-stats.log`: bộ đếm rsyslog, được thêm mỗi 5 giây; logrotate kiểm tra hàng ngày, xoay khi vượt 1 MiB và giữ ba bản cũ.
- `/var/log/victim-lab/metrics.jsonl`: collector ghi UTC timestamp, `experiment_id`, CPU/RAM/nhiệt độ, network RX/TX/drops, bộ đếm UDP/TCP và snapshot Syslog; xoay ở 20 MiB và giữ ba bản cũ.
- HTTP access log ở `sudo journalctl -u victim-http -o cat`. Log không chứa mật khẩu, cookie, request body hoặc query string.

`Bản tin đã nhận` là số rsyslog đưa vào pipeline, không phải số mà mọi client khẳng định đã gửi. UDP không có xác nhận; gói bị loại trước socket không nằm trong bộ đếm rsyslog. `Rsyslog từ chối` lấy từ các worker `imudp` (sẽ bằng 0 khi không cấu hình hạn chế nguồn); `Lỗi nhận UDP (kernel)` là bộ đếm của cả namespace, không chỉ riêng cổng 514.

Có thể sửa `EXPERIMENT_ID` và `COLLECT_INTERVAL` trong `/etc/victim-lab/experiment.env`, rồi restart `victim-http` và `victim-monitor`. Dừng ứng dụng bằng `sudo systemctl stop victim-monitor victim-http victim-syslog`. Namespace vẫn hoạt động để có thể khởi động lại dịch vụ.

Tài khoản `admin/admin` chỉ dành cho lab cô lập. Nếu mở web ra mạng khác, đổi mật khẩu và dùng TLS trước khi triển khai.

## Kiểm thử khi phát triển

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

# NOT AI
## Các device/network
`192.168.1.0/24`: Mạng LAN gồm các device IoT.
`192.168.1.1`: Router để định tuyến từ các device trong LAN -> WAN
`192.168.1.146`: Gateway trỏ đến WAN ảo
`10.20.0.0/24`: Mạng WAN ảo
`10.20.0.1`: đầu veth-pi ở Ubuntu host. Nó làm gateway cho máy ảo mạng.
`10.20.0.2`: đầu veth-vic trong network namespace victim. Web chạy tại `10.20.0.2:8080`, Syslog nhận tại `10.20.0.2:514`/UDP.
## Mô hình demo:
Các `device IoT` sẽ được kết nối tới `WAN server` thông qua 1 router có địa chỉ `192.168.1.1/24`.
Router phải được cấu hình định tuyến để trỏ tới mạng WAN ảo. Ở đây sử dụng `192.168.1.146/24` là cổng ethernet của `device WAN` làm gateway trỏ đến `10.20.0.0/24`. Device sẽ forward các gói tin nhận được từ router qua cổng ethernet đến WAN ảo
## Quy trình setup DEMO
```bash
sudo nano /etc/netplan/01-network-manager-all.yaml
```
Patse:
```nano
network:
    version: 2
    renderer: NetworkManager
    ethernets:
        `X`:
            dhcp4: false
            addresses:
                -   192.168.1.146/24
            routes:
                -   to: default
                    via 192.168.1.1
            nameservers:
                addresses:
                    -   8.8.8.8
                    -   1.1.1.1
```
Với `X` là tên interface ethernet

Restart lại network:
```bash
sudo netplan generate
sudo netplan try
```

Cấu hình ip forward:
```bash
sudo nano /etc/sysctl.d/99-ip-forward.conf
```
```nano
net.ipv4.ip_forward=1
```

Cấu hình static route trên router(192.168.1.1): Route tới 10.20.0.0/24 via 192.168.1.146
