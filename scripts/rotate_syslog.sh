#!/bin/bash
set -euo pipefail

log_file=/var/log/victim-lab/syslog.jsonl
exec 9>>/var/log/victim-lab/.syslog-clear.lock
flock -x 9
[[ -f "$log_file" ]] || exit 0
rotated_at=$(date -u +%Y%m%dT%H%M%SZ)
archive="$log_file.$rotated_at.$$.$RANDOM"
while [[ -e "$archive" ]]; do
    archive="$log_file.$rotated_at.$$.$RANDOM"
done
mv -- "$log_file" "$archive"
