"""Clear only the lab's stored Syslog messages and rsyslog statistics."""

import os
import re
import stat
from pathlib import Path


LOG_DIR = Path("/var/log/victim-lab")
ACTIVE_FILES = ("syslog.jsonl", "rsyslog-stats.log")
BACKUP_NAME = re.compile(
    r"(?:syslog\.jsonl\.(?:[1-9]\d*|\d{8}T\d{6}Z\.\d+\.\d+)"
    r"|rsyslog-stats\.log\.[1-9]\d*(?:\.gz)?)\Z"
)
LOCK_NAME = ".syslog-clear.lock"


def _truncate_regular_file(path):
    try:
        descriptor = os.open(path, os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return 0
    try:
        size = os.fstat(descriptor)
        if not stat.S_ISREG(size.st_mode):
            raise OSError(f"Refusing to truncate a non-regular file: {path}")
        os.ftruncate(descriptor, 0)
        return size.st_size
    finally:
        os.close(descriptor)


def clear_syslog_data(log_dir=LOG_DIR):
    """Truncate live files in place and unlink only known rotated Syslog files.

    Keep the live inodes so rsyslog can continue writing without a restart.
    The lock coordinates with rotate_syslog.sh on Linux.
    """
    log_dir = Path(log_dir)
    bytes_cleared = 0
    backups_removed = 0
    with (log_dir / LOCK_NAME).open("a+b") as lock:
        if os.name == "posix":
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for name in ACTIVE_FILES:
            bytes_cleared += _truncate_regular_file(log_dir / name)
        for path in log_dir.iterdir():
            if not BACKUP_NAME.fullmatch(path.name):
                continue
            try:
                bytes_cleared += path.lstat().st_size
                path.unlink()
                backups_removed += 1
            except FileNotFoundError:
                # logrotate may finish a stats rotation while cleanup runs.
                continue
    return {"bytes_cleared": bytes_cleared, "backups_removed": backups_removed}
