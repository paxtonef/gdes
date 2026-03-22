"""Prevents concurrent pipeline runs corrupting JSON staging"""
import fcntl
import os
from pathlib import Path
from contextlib import contextmanager

class StagingConcurrencyError(Exception):
    pass

@contextmanager
def staging_lock(staging_dir: Path, timeout: int = 5):
    lock_file = staging_dir / ".pipeline.lock"
    lock_fd = None
    
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = open(lock_file, "w")
        try:
            fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            raise StagingConcurrencyError(
                f"Another pipeline process holds the staging lock. "
                f"Wait for completion or remove {lock_file} if stale."
            )
        
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        yield
        
    finally:
        if lock_fd:
            fcntl.lockf(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            try:
                lock_file.unlink()
            except FileNotFoundError:
                pass
