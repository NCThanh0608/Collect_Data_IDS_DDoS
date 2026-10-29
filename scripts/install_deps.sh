#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script with sudo." >&2
    exit 1
fi

source_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
install_dir=/opt/victim-lab
if [[ "$#" -ne 0 ]]; then
    echo "Usage: sudo bash scripts/install_deps.sh" >&2
    exit 2
fi

apt-get update
apt-get install -y iproute2 python3 python3-venv python3-pip ca-certificates rsyslog logrotate

install -d -m 0755 "$install_dir"
python3 -m venv "$install_dir/.venv"
"$install_dir/.venv/bin/python" -m pip install --requirement "$source_dir/requirements.txt"

echo "Dependencies installed for HTTP, UDP Syslog and monitoring."
echo "Next: sudo bash scripts/setup_pi.sh"
