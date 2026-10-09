"""procsnap.py: every process on the PC from ONE Windows call.

NtQuerySystemInformation(SystemProcessInformation) returns the whole process table in a
single buffer: name, parent, start time, Task Manager's memory figure, CPU time and the
state of every thread. RamWarden used to build the same picture with several psutil calls
per process (about 1,600 calls for ~400 processes, 2.4 s); this takes a few tens of ms.

It also fixes stale identities: each process arrives with its own start time, so a PID
that Windows has recycled is never confused with the process that used it before.

Stdlib only (ctypes + struct). x64 layout of SYSTEM_PROCESS_INFORMATION and
SYSTEM_THREAD_INFORMATION, as documented in winternl.h / the NT headers.
"""
import ctypes
import struct
import time
from ctypes import wintypes

_ntdll = ctypes.WinDLL("ntdll")
_ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                            ctypes.POINTER(ctypes.c_ulong)]
_ntdll.NtQuerySystemInformation.restype = ctypes.c_long   # NTSTATUS

_SYSTEM_PROCESS_INFORMATION = 5
_STATUS_INFO_LENGTH_MISMATCH = -1073741820                 # 0xC0000004
_EPOCH_AS_FILETIME = 116444736000000000                   # 1970-01-01 in 100 ns ticks since 1601
_PROC_SIZE = 256                                           # sizeof(SYSTEM_PROCESS_INFORMATION), x64
_THREAD_SIZE = 80                                          # sizeof(SYSTEM_THREAD_INFORMATION), x64
_THREAD_WAITING, _WAIT_SUSPENDED = 5, 5                    # KTHREAD_STATE.Waiting, KWAIT_REASON.Suspended

# Same strings psutil uses, so callers can keep comparing with psutil.STATUS_*.
RUNNING, STOPPED, ZOMBIE = "running", "stopped", "zombie"

_buf_size = 1 << 20      # grows to fit and is remembered, so later calls need one try


class Proc:
    """One process from a snapshot."""
    __slots__ = ("pid", "ppid", "name", "created", "memory", "cpu_time", "threads", "status",
                 "session", "io_bytes")

    def __init__(self, pid, ppid, name, created, memory, cpu_time, threads, status,
                 session=0, io_bytes=0):
        self.pid, self.ppid, self.name = pid, ppid, name
        self.created = created        # unix seconds
        self.memory = memory          # private working set: Task Manager's "Memory" column
        self.cpu_time = cpu_time      # user + kernel, seconds
        self.threads = threads
        self.status = status          # RUNNING | STOPPED (every thread suspended) | ZOMBIE (no threads left)
        self.session = session        # sign-in session (0 = Windows services)
        self.io_bytes = io_bytes      # bytes read + written since it started

    @property
    def key(self):
        """Identity that survives PID reuse: (pid, start time)."""
        return self.pid, self.created


def _query():
    """The raw SystemProcessInformation buffer (and its length)."""
    global _buf_size
    while True:
        buf = ctypes.create_string_buffer(_buf_size)
        needed = ctypes.c_ulong(0)
        status = _ntdll.NtQuerySystemInformation(_SYSTEM_PROCESS_INFORMATION, buf, _buf_size,
                                                 ctypes.byref(needed))
        if status == _STATUS_INFO_LENGTH_MISMATCH:
            _buf_size = max(_buf_size * 2, needed.value + (1 << 16))   # processes can appear meanwhile
            continue
        if status < 0:
            raise OSError(f"NtQuerySystemInformation failed: 0x{status & 0xFFFFFFFF:08X}")
        return buf


def snapshot():
    """Every process except the Idle pseudo-process (PID 0), as a list of Proc."""
    buf = _query()
    raw = buf.raw
    base = ctypes.addressof(buf)
    out, offset = [], 0
    while True:
        (next_off, n_threads, private_ws) = struct.unpack_from("<IIq", raw, offset)
        (created, user, kernel) = struct.unpack_from("<qqq", raw, offset + 32)
        (name_len, _name_max, name_ptr) = struct.unpack_from("<HH4xQ", raw, offset + 56)
        (pid, ppid) = struct.unpack_from("<QQ", raw, offset + 80)
        (session,) = struct.unpack_from("<I", raw, offset + 100)
        (read_bytes, write_bytes) = struct.unpack_from("<qq", raw, offset + 232)   # Read/WriteTransferCount
        if pid:
            if name_ptr:
                # The name lives inside our own buffer; read it there rather than via the pointer.
                start = name_ptr - base
                name = raw[start:start + name_len].decode("utf-16-le", "replace")
            else:
                name = "System" if pid == 4 else ""
            suspended = 0
            t = offset + _PROC_SIZE
            for _ in range(n_threads):
                state, reason = struct.unpack_from("<II", raw, t + 68)
                if state == _THREAD_WAITING and reason == _WAIT_SUSPENDED:
                    suspended += 1
                t += _THREAD_SIZE
            status = ZOMBIE if n_threads == 0 else (STOPPED if suspended == n_threads else RUNNING)
            born = (created - _EPOCH_AS_FILETIME) / 1e7 if created else 0.0
            out.append(Proc(pid, ppid, name, born, private_ws, (user + kernel) / 1e7, n_threads, status,
                            session, read_bytes + write_bytes))
        if not next_off:
            return out
        offset += next_off


class CpuMeter:
    """CPU % per process between two snapshots, like Task Manager (100% = every core busy)."""

    def __init__(self):
        self._last = {}            # Proc.key -> cpu seconds at the last reading
        self._last_at = None
        self._cores = max(1, __import__("os").cpu_count() or 1)

    def update(self, procs):
        """{Proc.key: percent} for processes seen last time too; others aren't measurable yet."""
        now = time.monotonic()
        result = {}
        if self._last_at is not None:
            span = (now - self._last_at) * self._cores
            if span > 0:
                for p in procs:
                    before = self._last.get(p.key)
                    if before is not None:
                        result[p.key] = max(0.0, min(100.0, (p.cpu_time - before) / span * 100))
        self._last = {p.key: p.cpu_time for p in procs}
        self._last_at = now
        return result
