#!/bin/bash
set -euo pipefail

log_file=/var/log/victim-lab/syslog.jsonl
[[ -f "$log_file" ]] || exit 0
[[ -f "$log_file.2" ]] && mv -f -- "$log_file.2" "$log_file.3"
[[ -f "$log_file.1" ]] && mv -f -- "$log_file.1" "$log_file.2"
mv -f -- "$log_file" "$log_file.1"
