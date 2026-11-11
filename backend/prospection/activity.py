import os
from contextlib import contextmanager
from django.conf import settings


@contextmanager
def worker_activity(filename=".activity.lock"):
    handle = open(settings.BASE_DIR / filename, "a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            if not handle.seek(0, 2):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
    except OSError:
        pass
    try:
        yield acquired
    finally:
        handle.close()
