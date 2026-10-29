#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script with sudo." >&2
    exit 1
fi

systemd_version=$(systemctl --version | awk 'NR == 1 { print $2 }')
if [[ ! "$systemd_version" =~ ^[0-9]+$ ]] || (( systemd_version < 248 )); then
    echo "systemd 248 or newer is required for NetworkNamespacePath." >&2
    exit 1
fi

source_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
install_dir=/opt/victim-lab
network_only=0
requested_subnet=""
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --network-only) network_only=1 ;;
        --subnet)
            shift
            if [[ "$#" -eq 0 ]]; then
                echo "--subnet requires a private IPv4 /24 value." >&2
                exit 2
            fi
            requested_subnet="$1"
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
    shift
done
if (( network_only )) && [[ -n "$requested_subnet" ]]; then
    echo "--subnet must be used with full setup." >&2
    exit 2
fi

if ! command -v ip >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    echo "iproute2 and Python 3 are required. Run scripts/install_deps.sh first." >&2
    exit 1
fi
if (( ! network_only )); then
    if ! command -v rsyslogd >/dev/null 2>&1 ||
       [[ ! -x "$install_dir/.venv/bin/python" ||
          ! -x "$install_dir/.venv/bin/gunicorn" ]] ||
       ! "$install_dir/.venv/bin/python" -c 'import flask, gunicorn, werkzeug' >/dev/null 2>&1; then
        echo "Rsyslog or Python requirements are missing. Run scripts/install_deps.sh first." >&2
        exit 1
    fi
fi

install -d -m 0700 /etc/victim-lab
network_file=/etc/victim-lab/network.env
if [[ ! -f "$network_file" ]]; then
    install -m 0600 "$source_dir/config/lab-network.env" "$network_file"
fi
if [[ -n "$requested_subnet" ]]; then
    lab_subnet="$requested_subnet"
else
    lab_subnet=$(awk -F= '$1 == "LAB_SUBNET" { print substr($0, index($0, "=") + 1); exit }' "$network_file")
fi
network_values=$(python3 "$source_dir/scripts/network_config.py" "$lab_subnet")
read -r lab_subnet lab_host_ip lab_victim_ip <<< "$network_values"
lab_host_cidr="$lab_host_ip/24"
lab_victim_cidr="$lab_victim_ip/24"

route_conflicts() {
    local excluded_device="$1"
    ip -4 route show table main | python3 -c '
import ipaddress
import sys
target = ipaddress.ip_network(sys.argv[1])
excluded = sys.argv[2]
for line in sys.stdin:
    fields = line.split()
    if not fields or fields[0] == "default":
        continue
    prefix = fields[1] if fields[0] in {"blackhole", "unreachable", "prohibit", "throw"} else fields[0]
    try:
        route = ipaddress.ip_network(prefix, strict=False)
    except ValueError:
        continue
    if excluded and "dev" in fields and fields[fields.index("dev") + 1] == excluded:
        continue
    if target.overlaps(route):
        print(line.strip())
' "$lab_subnet" "$excluded_device"
}

if ! ip netns list | awk '$1 == "victim" { found = 1 } END { exit !found }'; then
    restore_wan0=0
    created_namespace=0
    cleanup_partial_namespace() {
        if (( created_namespace )); then
            ip link delete veth-pi 2>/dev/null || true
            ip netns delete victim 2>/dev/null || true
        fi
        if (( restore_wan0 )); then
            ip -4 addr add 10.20.0.1/24 dev wan0 2>/dev/null || true
        fi
    }
    trap cleanup_partial_namespace ERR

    if ip link show dev veth-pi >/dev/null 2>&1; then
        old_address=$(ip -o -4 addr show dev veth-pi | awk '{ print $4 }')
        old_routes=$(ip -4 route show dev veth-pi | awk '{ print $1 }')
        if [[ "$old_address" == "10.20.0.1/24" && "$old_routes" == "10.20.0.0/24" ]]; then
            ip link delete veth-pi
            echo "Removed stale lab veth-pi and its 10.20.0.0/24 route."
        else
            echo "veth-pi exists but does not match the old lab link; leaving it unchanged." >&2
            ip -4 addr show dev veth-pi >&2
            ip -4 route show dev veth-pi >&2
            exit 1
        fi
    fi
    if ip link show dev veth-vic >/dev/null 2>&1; then
        echo "veth-vic already exists outside namespace victim; inspect the Pi network first." >&2
        exit 1
    fi

    overlapping_routes=$(route_conflicts "")
    if [[ "$lab_subnet" == "10.20.0.0/24" && "$overlapping_routes" == "10.20.0.0/24 dev wan0 proto kernel scope link src 10.20.0.1" ]]; then
        if ip -4 route show default | awk '
            $1 == "default" {
                for (i = 1; i < NF; i++) {
                    if ($i == "dev" && $(i + 1) == "wan0") found = 1
                }
            }
            END { exit !found }
        '; then
            echo "wan0 carries a default route; refusing to remove its lab address." >&2
            exit 1
        fi
        wan0_addresses=$(ip -o -4 addr show dev wan0 | awk '{ print $4 }')
        if [[ "$wan0_addresses" != "10.20.0.1/24" ]]; then
            echo "wan0 has unexpected IPv4 addresses; leaving it unchanged: $wan0_addresses" >&2
            exit 1
        fi
        ip -4 addr del 10.20.0.1/24 dev wan0
        restore_wan0=1
        if ip -4 route show table main | awk '$1 == "10.20.0.0/24" { found = 1 } END { exit !found }'; then
            echo "10.20.0.0/24 still exists after removing the wan0 address; restoring it and stopping." >&2
            cleanup_partial_namespace
            exit 1
        fi
        echo "Removed 10.20.0.1/24 from wan0; wan0 itself remains."
        overlapping_routes=""
    fi
    if [[ -n "$overlapping_routes" ]]; then
        echo "Cannot use $lab_subnet: the following Pi route overlaps it:" >&2
        echo "$overlapping_routes" >&2
        echo "Deleting it could disconnect the Pi or another network. Check the interface before removing it." >&2
        exit 1
    fi

    ip netns add victim
    created_namespace=1
    ip link add veth-pi type veth peer name veth-vic
    ip link set veth-vic netns victim
    ip addr add "$lab_host_cidr" dev veth-pi
    ip link set veth-pi up
    ip -n victim addr add "$lab_victim_cidr" dev veth-vic
    ip -n victim link set veth-vic up
    ip -n victim link set lo up
    restore_wan0=0
    trap - ERR
    echo "Created local victim namespace with $lab_victim_cidr and veth-pi."
elif ip link show dev veth-pi >/dev/null 2>&1 && ip -n victim link show dev veth-vic >/dev/null 2>&1; then
    old_host_cidr=$(ip -o -4 addr show dev veth-pi | awk '{ print $4 }')
    old_victim_cidr=$(ip -n victim -o -4 addr show dev veth-vic | awk '{ print $4 }')
    if [[ "$old_host_cidr" != "$lab_host_cidr" || "$old_victim_cidr" != "$lab_victim_cidr" ]]; then
        if ! python3 -c '
import ipaddress
import sys
try:
    host = ipaddress.ip_interface(sys.argv[1])
    victim = ipaddress.ip_interface(sys.argv[2])
    valid = host.version == 4 and victim.version == 4 and host.network == victim.network and host.network.prefixlen == 24
except ValueError:
    valid = False
sys.exit(0 if valid else 1)
' "$old_host_cidr" "$old_victim_cidr"; then
            echo "Existing veth addresses are not one matching IPv4 /24 pair; leaving them unchanged." >&2
            exit 1
        fi
        overlapping_routes=$(route_conflicts "veth-pi")
        if [[ -n "$overlapping_routes" ]]; then
            echo "Cannot switch victim to $lab_subnet; another Pi route overlaps it:" >&2
            echo "$overlapping_routes" >&2
            exit 1
        fi
        systemctl stop victim-monitor.service victim-http.service victim-syslog.service victim-coap.service victim-lan-dns.service victim-dns.service 2>/dev/null || true
        rollback_addresses() {
            ip -4 addr del "$lab_host_cidr" dev veth-pi 2>/dev/null || true
            ip -n victim -4 addr del "$lab_victim_cidr" dev veth-vic 2>/dev/null || true
            ip -4 addr add "$old_host_cidr" dev veth-pi 2>/dev/null || true
            ip -n victim -4 addr add "$old_victim_cidr" dev veth-vic 2>/dev/null || true
        }
        trap rollback_addresses ERR
        ip -4 addr del "$old_host_cidr" dev veth-pi
        ip -n victim -4 addr del "$old_victim_cidr" dev veth-vic
        ip -4 addr add "$lab_host_cidr" dev veth-pi
        ip -n victim -4 addr add "$lab_victim_cidr" dev veth-vic
        trap - ERR
        echo "Changed local victim network to $lab_subnet ($lab_victim_ip)."
    fi
fi

if ! ip -n victim -o -4 addr show | awk -v target="$lab_victim_ip" '
    { split($4, parts, "/"); if (parts[1] == target) found = 1 }
    END { exit !found }
'; then
    echo "Namespace 'victim' has no $lab_victim_ip address; configure the external WAN topology first." >&2
    exit 1
fi

ip -n victim link set lo up

if ip link show dev veth-pi >/dev/null 2>&1 && ip -n victim link show dev veth-vic >/dev/null 2>&1; then
    router_iface=$(ip -4 route show default | awk '
        NR == 1 {
            for (i = 1; i < NF; i++) {
                if ($i == "dev") { print $(i + 1); exit }
            }
        }
    ')
    if [[ -n "$router_iface" ]]; then
        router_lan_subnet=$(ip -o -4 addr show dev "$router_iface" | awk '{ print $4 }' | python3 -c '
import ipaddress
import sys
networks = {str(ipaddress.ip_interface(line.strip()).network) for line in sys.stdin if line.strip()}
if len(networks) == 1:
    print(networks.pop())
')
        if [[ -n "$router_lan_subnet" && "$router_lan_subnet" != "$lab_subnet" ]]; then
            sysctl -w net.ipv4.ip_forward=1 >/dev/null
            ip -n victim route replace "$router_lan_subnet" via "$lab_host_ip"
            echo "Router LAN $router_lan_subnet can reach victim through this Pi when the router has a static route."
        fi
    fi
fi

if (( network_only )); then
    exit 0
fi

if [[ "$source_dir" == "$install_dir" ]]; then
    echo "Run full setup from the project checkout, not from /opt/victim-lab." >&2
    exit 1
fi

if ! id -u victimlab >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "$install_dir" --shell /usr/sbin/nologin victimlab
fi

for legacy_unit in victim-lan-dns.service victim-dns.service; do
    systemctl disable --now "$legacy_unit" 2>/dev/null || true
done
systemctl disable --now victim-coap.service 2>/dev/null || true
systemctl stop victim-http.service victim-syslog.service victim-monitor.service 2>/dev/null || true
rm -f /etc/systemd/system/victim-lan-dns.service /etc/systemd/system/victim-dns.service
rm -f /etc/systemd/system/victim-coap.service
rm -f /etc/victim-lab/lan-dns.env
rm -f "$install_dir/bin/coredns" "$install_dir/scripts/lan_dns_config.py"
rm -rf -- "$install_dir/lan_dns" "$install_dir/dns_service" \
    "$install_dir/victim_http_app" "$install_dir/coap_service" "$install_dir/monitoring"

install -d -m 0755 "$install_dir" "$install_dir/src" "$install_dir/rsyslog"
rm -rf -- "$install_dir/src/victim_lab"
cp -a "$source_dir/src/victim_lab" "$install_dir/src/"
install -d -m 0755 "$install_dir/scripts" "$install_dir/config"
install -m 0755 "$source_dir/scripts/setup_pi.sh" "$install_dir/scripts/setup_pi.sh"
install -m 0755 "$source_dir/scripts/rotate_syslog.sh" "$install_dir/scripts/rotate_syslog.sh"
install -m 0644 "$source_dir/scripts/network_config.py" "$install_dir/scripts/network_config.py"
install -m 0644 "$source_dir/config/lab-network.env" "$install_dir/config/lab-network.env"
install -m 0644 "$source_dir/deploy/logrotate/victim-lab-stats" /etc/logrotate.d/victim-lab-stats
sed "s/10\.20\.0\.2/$lab_victim_ip/g" "$source_dir/deploy/rsyslog/victim.conf" > "$install_dir/rsyslog/victim.conf"
chmod 0644 "$install_dir/rsyslog/victim.conf"
chown -R root:root "$install_dir"
install -d -o victimlab -g victimlab -m 0750 /var/log/victim-lab /var/log/victim-lab/rsyslog-work
apparmor_profile=/etc/apparmor.d/usr.sbin.rsyslogd
if [[ -f "$apparmor_profile" && ! -e /etc/apparmor.d/disable/usr.sbin.rsyslogd ]] &&
   command -v aa-enabled >/dev/null 2>&1 && aa-enabled -q; then
    if ! command -v apparmor_parser >/dev/null 2>&1; then
        echo "AppArmor profile exists but apparmor_parser is missing; install the apparmor package." >&2
        exit 1
    fi
    install -d -m 0755 /etc/apparmor.d/rsyslog.d
    install -m 0644 "$source_dir/deploy/apparmor/victim-lab-rsyslog" /etc/apparmor.d/rsyslog.d/victim-lab-rsyslog
    apparmor_parser -r "$apparmor_profile"
fi
rsyslogd -N1 -f "$install_dir/rsyslog/victim.conf"
install -d -m 0700 /etc/victim-lab
secret=""
if [[ -f /etc/victim-lab/http.env ]]; then
    secret=$(awk -F= '$1 == "FLASK_SECRET_KEY" { print substr($0, index($0, "=") + 1); exit }' /etc/victim-lab/http.env)
fi
if [[ -z "$secret" ]]; then
    secret=$("$install_dir/.venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
fi
password_hash=$("$install_dir/.venv/bin/python" -c 'from werkzeug.security import generate_password_hash; print(generate_password_hash("admin"))')
temporary_env=$(mktemp /etc/victim-lab/http.env.XXXXXX)
printf 'FLASK_SECRET_KEY=%s\nVICTIM_USERNAME=admin\nVICTIM_PASSWORD_HASH=%s\n' "$secret" "$password_hash" > "$temporary_env"
chmod 0600 "$temporary_env"
mv -f "$temporary_env" /etc/victim-lab/http.env
rm -f /etc/victim-lab/credentials.txt
if [[ ! -f /etc/victim-lab/experiment.env ]]; then
    printf 'EXPERIMENT_ID=baseline\nCOLLECT_INTERVAL=5\n' > /etc/victim-lab/experiment.env
    chmod 0644 /etc/victim-lab/experiment.env
fi

install -m 0644 "$source_dir/deploy/systemd/victim-netns.service" /etc/systemd/system/victim-netns.service
install -m 0644 "$source_dir/deploy/systemd/victim-syslog.service" /etc/systemd/system/victim-syslog.service
sed "s/10\.20\.0\.2/$lab_victim_ip/g" "$source_dir/deploy/systemd/victim-http.service" > /etc/systemd/system/victim-http.service
chmod 0644 /etc/systemd/system/victim-http.service
sed "s/10\.20\.0\.2/$lab_victim_ip/g" "$source_dir/deploy/systemd/victim-monitor.service" > /etc/systemd/system/victim-monitor.service
chmod 0644 /etc/systemd/system/victim-monitor.service
if [[ -n "$requested_subnet" ]]; then
    temporary_network_file=$(mktemp /etc/victim-lab/network.env.XXXXXX)
    printf 'LAB_SUBNET=%s\n' "$lab_subnet" > "$temporary_network_file"
    chmod 0600 "$temporary_network_file"
    mv -f "$temporary_network_file" "$network_file"
fi
systemctl daemon-reload
systemctl enable victim-netns.service victim-syslog.service victim-http.service victim-monitor.service
systemctl restart victim-netns.service
systemctl restart victim-syslog.service victim-http.service victim-monitor.service

echo "Services started or restarted in namespace victim."
echo "Lab subnet: $lab_subnet; victim IP: $lab_victim_ip"
echo "Lab login: admin / admin"
echo "victim-netns, victim-syslog, victim-http and victim-monitor are enabled at boot."
