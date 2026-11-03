# Victim Lab trên Ubuntu Server

Project chạy web HTTP và một máy chủ UDP Syslog thật trong network namespace `victim`. Dashboard giữ trang đăng nhập hiện có, hiển thị thẻ HTTP, thẻ Syslog và tối đa 20 bản tin gần nhất. Collector ghi chỉ số máy, mạng và Syslog để quan sát thí nghiệm trong WAN ảo.

## Cấu trúc

```text
src/victim_lab/http/       Flask, template và tài nguyên web
src/victim_lab/syslog/     Đọc chỉ số, đọc log và gửi bản tin thử
src/victim_lab/monitor/    Collector JSONL
deploy/rsyslog/            Cấu hình rsyslog riêng của lab
deploy/logrotate/          Xoay file thống kê rsyslog
deploy/systemd/           Các unit khởi động cùng Ubuntu Server
scripts/                  Cài dependency, triển khai, xoay log, kiểm tra subnet
config/                   Subnet lab mặc định
tests/                    Kiểm thử ứng dụng và cấu hình mạng
requirements.txt          Dependency Python
```

## Cài và triển khai

Yêu cầu Ubuntu Server với `systemd` 248 trở lên, Python 3, quyền `sudo` và kết nối Internet khi cài dependency. Chạy từ thư mục project trên Ubuntu Server:

```bash
sudo bash scripts/install_deps.sh
sudo bash scripts/setup_pi.sh
```

Trên Ubuntu có AppArmor, `setup_pi.sh` cài rule riêng cho rsyslog để đọc
`/opt/victim-lab/rsyslog/victim.conf` và ghi log của lab, rồi nạp lại profile
trước khi kiểm tra cấu hình. Nếu bản cài cũ báo `could not open config file ...
Permission denied`, cập nhật project và chạy lại `sudo bash scripts/setup_pi.sh`.
Không cần tắt AppArmor.

`install_deps.sh` cài rsyslog và dependency Python vào `/opt/victim-lab/.venv`; bước này không đổi mạng hoặc khởi động service. `setup_pi.sh` dựng hoặc kiểm tra namespace, chép mã, kiểm tra cấu hình rsyslog, cài unit và bật chúng khi Ubuntu Server khởi động. Khi chỉ cập nhật mã hoặc giao diện, chạy lại `setup_pi.sh` là đủ. Bản triển khai mới dừng và gỡ unit CoAP cũ; các file metrics đã thu trước đó vẫn được giữ.

Nếu router hoặc client còn dùng IP LAN của Ubuntu Server làm DNS, đổi sang máy chủ DNS khác đang hoạt động trước khi nâng cấp. Project không còn tiến trình phục vụ cổng 53.

Địa chỉ mặc định là `10.20.0.1/24` trên host Ubuntu Server và `10.20.0.2/24` trong namespace `victim`. Script tự tạo cặp veth nếu chưa có namespace. Nếu topology WAN ảo riêng đã tạo namespace, cần gán sẵn IP máy đích và route phù hợp. Script từ chối dải mạng trùng route khác trên Ubuntu Server.

Để đổi dải mạng:

```bash
sudo bash scripts/setup_pi.sh --subnet 10.30.0.0/24
```

Chọn dải IPv4 private `/24` chưa trùng. Script dùng `.1` cho Ubuntu Server, `.2` cho victim và cập nhật địa chỉ bind của HTTP, Syslog. Nếu router có static route đến dải cũ, sửa route đến dải mới qua IP LAN ổn định của Ubuntu Server.

## Truy cập web và gửi Syslog

Với dải mặc định, mở `http://10.20.0.2:8080/login`, đăng nhập `admin/admin`. Dashboard cập nhật khoảng 3 giây/lần. Thẻ Syslog cho biết số bản tin đã nhận, bản tin/giây, số bị rsyslog từ chối, số bị hàng đợi loại bỏ và lỗi nhận UDP của kernel trong namespace. Thẻ ICMPv4 hiển thị số gói nhận trung bình mỗi giây, tính từ chênh lệch bộ đếm kernel `Icmp: InMsgs` giữa hai mẫu collector (mặc định cách nhau 5 giây). Đây là mọi loại ICMPv4 nhận trong namespace `victim`, không chỉ Echo Request; khi chưa có hai mẫu mới hoặc collector ngừng cập nhật, thẻ hiển thị `—`. Danh sách chỉ tải 20 log gần nhất; mỗi nội dung hiển thị tối đa 500 ký tự và được đưa vào trang dưới dạng văn bản.

Nút **Gửi thử bản tin Syslog** gửi UDP từ web server, rồi chờ thấy mã bản tin trong log mới báo “đã nhận”. Nó kiểm tra đường nội bộ web → Syslog. Để kiểm tra tuyến PC → router → victim, cấu hình client trên PC gửi Syslog đến `10.20.0.2:514/udp`.

Ví dụ Ubuntu Server có LAN IP cố định `192.168.1.146` và router phục vụ `192.168.1.0/24`: đặt static route trên router với đích `10.20.0.0/24`, gateway `192.168.1.146`, interface LAN. Ubuntu Server và namespace cần route hai chiều; script cấu hình phần này khi nó quản lý cặp veth. Trang web dùng TCP 8080; client gửi log trực tiếp dùng UDP 514. Chỉ cho phép các cổng này trong lab, không chuyển tiếp từ Internet công cộng. Không đặt IP Ubuntu Server trong vùng DHCP có thể cấp cho máy khác.

Kiểm tra trên Ubuntu Server:

```bash
sudo systemctl status victim-netns victim-http victim-syslog victim-monitor --no-pager
sudo systemctl is-enabled victim-netns victim-http victim-syslog victim-monitor
sudo rsyslogd -N1 -f /opt/victim-lab/rsyslog/victim.conf
sudo ip netns exec victim logger --udp --server 10.20.0.2 --port 514 --tag lab-test "hello from Ubuntu Server"
```

Thay địa chỉ `.2` nếu đã đổi subnet. Sau khi gửi, kiểm tra thẻ Syslog hoặc `sudo tail /var/log/victim-lab/syslog.jsonl`. Nếu trang báo chưa có số liệu ngay sau khi khởi động, chờ chu kỳ `impstats` đầu tiên, khoảng 5 giây.

Nếu bộ đếm nhận tăng nhưng danh sách log trống, kiểm tra một bản tin gần nhất có phải JSON hợp lệ không:

```bash
sudo tail -n 1 /var/log/victim-lab/syslog.jsonl | python3 -m json.tool
```

Rsyslog 8.2504 cần mẫu ghi JSONL có dấu xuống dòng nằm ngoài object JSON. Bản cấu hình trước từng ghi dấu phẩy thừa và dấu `}` ở dòng riêng; bản đọc mới vẫn hiển thị được các bản tin cũ đó, còn bản ghi mới sẽ là một JSON hợp lệ trên mỗi dòng.

## Đối chiếu PCAP router với Syslog

Nếu không sửa được thiết bị gửi, không dùng trường `msg` làm khóa đối chiếu: trường này có thể rỗng, chứa byte không phải UTF-8 hoặc đã bị rsyslog biến đổi. Bản ghi mới có thêm `received_at_utc` (thời điểm rsyslog nhận) và `source_port`. Để đối chiếu payload, thu PCAP ở cả cổng ra router và cổng vào namespace victim trong cùng khoảng thời gian.

Trên Ubuntu Server, từ thư mục project chạy lại setup để áp dụng mẫu log mới. Cài `tcpdump` trên Ubuntu Server và router nếu chưa có (lệnh dưới đây dành cho Debian/Ubuntu):

```bash
sudo bash scripts/setup_pi.sh
sudo apt-get install tcpdump
```

Trên router Linux, dùng `ip route get 10.20.0.2` để tìm interface đi tới Ubuntu Server, rồi thay `<egress-iface>` trong lệnh sau:

```bash
sudo tcpdump -i <egress-iface> -Q out -s 0 -w /tmp/router-syslog.pcap 'udp and dst host 10.20.0.2 and dst port 514'
```

Đồng thời trên Ubuntu Server:

```bash
sudo ip netns exec victim tcpdump -i veth-vic -Q in -s 0 -w /tmp/victim-syslog.pcap 'udp and dst host 10.20.0.2 and dst port 514'
```

Dừng cả hai lệnh bằng Ctrl+C sau thí nghiệm, rồi chép `/tmp/router-syslog.pcap` từ router sang `/tmp/router-syslog.pcap` trên Ubuntu Server. Từ thư mục project trên Ubuntu Server, tạo môi trường phân tích riêng và chạy:

```bash
python3 -m venv .venv-analysis
.venv-analysis/bin/pip install -r requirements-analysis.txt
sudo .venv-analysis/bin/python scripts/compare_syslog_capture.py \
  --router /tmp/router-syslog.pcap \
  --victim /tmp/victim-syslog.pcap \
  --log-dir /var/log/victim-lab \
  --dst-ip 10.20.0.2
```

Nếu phân tích trên PC, chép `syslog.jsonl` và các bản xoay vào một thư mục rồi truyền thư mục đó qua `--log-dir`. Công cụ so IP/port nguồn cùng SHA-256 của toàn bộ UDP payload theo số lần xuất hiện; không giải mã `msg`. Vì vậy cần capture tại cổng ra router sau NAT và cổng vào victim, trước khi có thiết bị khác sửa IP/port. `router_only` là số datagram thấy ở router nhưng không thấy ở victim. `rsyslog.written_in_window` là số dòng log có thời điểm nhận và cặp IP/port nguồn trùng với PCAP victim trong khoảng đo (mặc định cộng biên 2 giây). Điều chỉnh `--margin-seconds` nếu cần. File log cũ chưa có `received_at_utc` không thể đối chiếu theo thời điểm nhận. Nếu capture bị cắt ngắn hoặc có IP fragment, công cụ báo số lượng và bỏ chúng khỏi phép so.

Không có ID do sender gắn vào thì nhiều datagram có payload giống hệt nhau chỉ so được theo số lượng, và không thể khẳng định dòng rsyslog nào ứng với datagram cụ thể nào. `maxMessageSize` hiện là 2 KiB nên nội dung bản tin dài hơn có thể bị cắt trong rsyslog; PCAP vẫn giữ byte gốc nếu dùng `-s 0`.

## Chỉ số và log

- `/var/log/victim-lab/syslog.jsonl`: bản tin Syslog dạng JSONL, xoay khi đạt khoảng 20 MiB. Bản cũ có hậu tố thời gian UTC và mã duy nhất; không tự xóa bản nào. Các bản `.1`–`.3` từ trước vẫn được giữ.
- `/var/log/victim-lab/rsyslog-stats.log`: bộ đếm rsyslog, được thêm mỗi 5 giây; logrotate kiểm tra hàng ngày, xoay khi vượt 1 MiB và giữ không giới hạn bản cũ.
- `/var/log/victim-lab/metrics.jsonl`: collector ghi UTC timestamp, `experiment_id`, CPU/RAM/nhiệt độ, network RX/TX/drops, bộ đếm UDP/TCP và snapshot Syslog; xoay ở 20 MiB và giữ không giới hạn bản cũ.
- HTTP access log ở `sudo journalctl -u victim-http -o cat`. Log không chứa mật khẩu, cookie, request body hoặc query string.

Trên dashboard, nút **Xóa toàn bộ Syslog** yêu cầu xác nhận rồi xóa nội dung `syslog.jsonl`, `rsyslog-stats.log` và các bản xoay của hai file này. Nút không xóa `metrics.jsonl` hay system journal. File đang được rsyslog mở được cắt về 0 byte tại chỗ, nên dịch vụ tiếp tục ghi bản tin mới. Bộ đếm trong tiến trình rsyslog vẫn tiếp tục tăng; dashboard có thể tạm báo thiếu thống kê cho đến chu kỳ `impstats` tiếp theo (khoảng 5 giây). API xóa yêu cầu phiên đăng nhập và mã CSRF của phiên đó. Để cập nhật bản triển khai hiện có, chạy lại `sudo bash scripts/setup_pi.sh`.

Không còn giới hạn số bản xoay, nên tổng dung lượng các file log có thể tăng đến khi đầy ổ đĩa. Nút xóa Syslog chỉ dọn bản tin và thống kê Syslog; các bản metrics cũ cần được quản lý riêng khi không còn cần cho thí nghiệm.

`Bản tin đã nhận` là số rsyslog đưa vào pipeline, không phải số mà mọi client khẳng định đã gửi. UDP không có xác nhận; gói bị loại trước socket không nằm trong bộ đếm rsyslog. `Nguồn bị chặn` lấy từ các worker `imudp` và luôn bằng 0 khi không cấu hình hạn chế nguồn. `Hàng đợi loại bỏ` chỉ đếm bản tin bị loại ở hàng đợi, không đếm lỗi ghi file. `Lỗi ghi log` lấy từ action `lab_messages`; nếu file chạm ngưỡng 20 MiB mà không xoay được, trạng thái Syslog báo lỗi ghi log. `Lỗi nhận UDP (kernel)` là bộ đếm của cả namespace, không chỉ riêng cổng 514.

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
`10.20.0.1`: đầu `veth-pi` trên host Ubuntu Server. Nó làm gateway cho máy ảo mạng.
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
