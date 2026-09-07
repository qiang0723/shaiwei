"""Temporary test-only write barrier; never imported by production."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PROTECTED = tuple(ROOT / name for name in ('ledger', 'data', 'logs', '.release', '.runtime-locks'))

def checked_path(value):
    if isinstance(value, (str, bytes, os.PathLike)):
        return Path(os.fsdecode(value)).resolve()
    return None

def deny_write(value):
    path = checked_path(value)
    if path is not None and any(path == base or path.is_relative_to(base) for base in PROTECTED):
        raise PermissionError('test barrier: production write forbidden')

def audit(event, args):
    if event == 'open':
        path = checked_path(args[0])
        if path == ROOT / '.env':
            raise PermissionError('test barrier: real dotenv read forbidden')
        flags = args[2]
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            deny_write(args[0])
    elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.truncate'):
        deny_write(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        deny_write(args[0])
        deny_write(args[1])
    elif event in ('socket.connect', 'socket.connect_ex'):
        raise PermissionError('test barrier: network connection forbidden')

sys.addaudithook(audit)
