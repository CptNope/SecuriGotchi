"""Process-level collector exclusivity for Unix/Windows."""
from contextlib import contextmanager
import os
import stat
from gotchi_auth import data_dir


@contextmanager
def exclusive_watch_lock():
    path = data_dir() / "monitor-watch.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("Monitor lock must be a regular file")
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size < 1:
                os.write(fd, b"\0")
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another monitor watch process is already running") from exc
        else:
            import fcntl
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise RuntimeError("Monitor lock must be private and user-owned")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another monitor watch process is already running") from exc
        yield
    finally:
        os.close(fd)
