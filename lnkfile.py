"""lnkfile.py: read a Windows shortcut (.lnk) file's target and arguments, in plain Python.

The Startup tab used to launch PowerShell (a COM object) to read Startup-folder shortcuts:
slow (~0.4 s), and antivirus heuristics dislike apps that quietly spawn PowerShell. This
reads the Shell Link binary format directly ([MS-SHLLINK], Microsoft Open Specifications).

Public API: read_lnk(path) -> (target, arguments); target is "" when it can't be worked out.
"""
import os
import struct

_HAS_ID_LIST, _HAS_LINK_INFO, _HAS_NAME, _HAS_RELATIVE_PATH = 0x1, 0x2, 0x4, 0x8
_HAS_WORKING_DIR, _HAS_ARGUMENTS, _HAS_ICON, _IS_UNICODE = 0x10, 0x20, 0x40, 0x80
_VOLUME_ID_AND_LOCAL_BASE_PATH = 0x1
_ENV_BLOCK_SIGNATURE = 0xA0000001          # EnvironmentVariableDataBlock (e.g. %windir%\...)


def _cstring(data, at, wide):
    """A NUL-terminated string at `at` (UTF-16 if wide, else the ANSI code page)."""
    if wide:
        end = at
        while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
            end += 2
        return data[at:end].decode("utf-16-le", "replace")
    end = data.find(b"\0", at)
    return data[at:end if end >= 0 else len(data)].decode("mbcs", "replace")


def read_lnk(path):
    """(target, arguments) of a .lnk file; ("", "") if it isn't a readable shortcut."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return "", ""
    if len(data) < 76 or struct.unpack_from("<I", data, 0)[0] != 0x4C:
        return "", ""
    flags = struct.unpack_from("<I", data, 20)[0]
    pos = 76
    if flags & _HAS_ID_LIST:
        pos += 2 + struct.unpack_from("<H", data, pos)[0]

    target = ""
    if flags & _HAS_LINK_INFO:
        size, header, info_flags, _vol, base_off, _net, suffix_off = struct.unpack_from("<7I", data, pos)
        if info_flags & _VOLUME_ID_AND_LOCAL_BASE_PATH:
            if header >= 0x24:                                   # Unicode copies are present
                base_u, suffix_u = struct.unpack_from("<II", data, pos + 28)
                target = _cstring(data, pos + base_u, True) + _cstring(data, pos + suffix_u, True)
            else:
                target = _cstring(data, pos + base_off, False) + _cstring(data, pos + suffix_off, False)
        pos += size

    wide = bool(flags & _IS_UNICODE)
    strings = {}
    for flag, name in ((_HAS_NAME, "name"), (_HAS_RELATIVE_PATH, "relative"), (_HAS_WORKING_DIR, "workdir"),
                       (_HAS_ARGUMENTS, "args"), (_HAS_ICON, "icon")):
        if flags & flag:
            count = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            width = 2 if wide else 1
            raw = data[pos:pos + count * width]
            strings[name] = raw.decode("utf-16-le" if wide else "mbcs", "replace")
            pos += count * width

    if not target:
        # Targets written with environment variables (%ProgramFiles%\...) live in an extra block.
        while pos + 8 <= len(data):
            block_size, signature = struct.unpack_from("<II", data, pos)
            if block_size < 8:
                break
            if signature == _ENV_BLOCK_SIGNATURE:
                target = os.path.expandvars(_cstring(data, pos + 268, True) or _cstring(data, pos + 8, False))
                break
            pos += block_size
    if not target and strings.get("relative"):
        target = os.path.normpath(os.path.join(os.path.dirname(path), strings["relative"]))
    return target, strings.get("args", "")
