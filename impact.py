"""
impact.py — startup impact (High / Medium / Low), the way Task Manager works it out.

At each sign-in Windows measures every process for its first 90 seconds and writes the
results to %WINDIR%\\System32\\WDI\\LogFiles\\StartupInfo\\<SID>_StartupInfo<N>.xml: CPU time
(microseconds) and disk I/O (bytes) per process. Task Manager's ratings come from those files:
  High:   over 1 s of CPU or over 3 MB of disk
  Medium: over 300 ms of CPU or over 300 KB of disk
  Low:    less than both

The folder is readable by administrators only, so the figures are read when RamWarden runs
as ADMIN and kept in %LOCALAPPDATA%\\RamWarden\\startup_impact.json for normal runs (they only
change at the next sign-in anyway). No tkinter dependency.
"""
import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET

STARTUP_INFO_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'),
                                'System32', 'WDI', 'LogFiles', 'StartupInfo')

# Programs that start many unrelated things; a match on one of these by name alone says
# nothing about which startup entry it belongs to, so they're only matched by full path.
_GENERIC_HOSTS = {'rundll32.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe', 'wscript.exe',
                  'cscript.exe', 'mshta.exe', 'msiexec.exe', 'explorer.exe', 'conhost.exe',
                  'svchost.exe', 'dllhost.exe', 'regsvr32.exe', 'javaw.exe', 'java.exe',
                  'python.exe', 'pythonw.exe', 'node.exe'}

# Figures older than this are ignored: Windows 11 24H2 and later stopped recording them, and a
# rating from years ago says little about the apps installed now.
STALE_DAYS = 60

# Display order for sorting: worst first.
RANK = {'High': 0, 'Medium': 1, 'Low': 2, 'Not measured': 3, 'None': 4, '': 5}


def level(cpu_us: int, disk_bytes: int) -> str:
    """Task Manager's rating for one app's CPU time (µs) and disk I/O (bytes) at sign-in."""
    if cpu_us > 1_000_000 or disk_bytes > 3 * 1024 * 1024:
        return 'High'
    if cpu_us > 300_000 or disk_bytes > 300 * 1024:
        return 'Medium'
    return 'Low'


def _current_sid() -> str:
    """This user's SID (e.g. S-1-5-21-…), which prefixes their StartupInfo file names."""
    try:
        out = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=10).stdout
        m = re.search(rb'(S-1-[0-9-]+)', out)
        return m.group(1).decode() if m else ''
    except Exception:
        return ''


def _xml_text(raw: bytes) -> str:
    """The files are UTF-16 (with a byte-order mark); fall back to UTF-8 just in case."""
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('utf-16-le', errors='replace')


def parse_startup_info(raw: bytes) -> dict:
    """{process path: (cpu_us, disk_bytes)} from one StartupInfo file; copies of the same
    program are added together."""
    text = _xml_text(raw)
    # ElementTree refuses a str that still declares encoding="UTF-16".
    text = re.sub(r'^\s*<\?xml[^>]*\?>', '', text)
    # Windows writes program names unescaped, so "Spybot - Search & Destroy" makes the whole
    # file invalid XML. Escape any & that doesn't start a real entity.
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)
    root = ET.fromstring(text)
    result = {}
    for p in root.iter('Process'):
        name = (p.get('Name') or '').strip()
        if not name:
            continue
        cpu = _int(p.findtext('CpuUsage'))
        disk = _int(p.findtext('DiskUsage'))
        old = result.get(name, (0, 0))
        result[name] = (old[0] + cpu, old[1] + disk)
    return result


def _int(text) -> int:
    """An integer from element text, 0 when missing or malformed."""
    try:
        return int((text or '0').strip())
    except ValueError:
        return 0


def read_latest(folder: str = None, sid: str = None) -> tuple:
    """(figures, measured_at) from this user's newest StartupInfo file.
    Raises PermissionError when not running as administrator; ({}, 0) when there are none."""
    folder = folder or STARTUP_INFO_DIR
    sid = _current_sid() if sid is None else sid
    names = [n for n in os.listdir(folder)            # PermissionError without admin rights
             if re.search(r'StartupInfo\d*\.xml$', n, re.I) and (not sid or n.upper().startswith(sid.upper() + '_'))]
    if not names:
        import logging
        logging.getLogger("ramwarden").info("Startup impact: no StartupInfo file for %s among %s",
                                            sid or 'any user', os.listdir(folder)[:10])
        return {}, 0
    newest = max(names, key=lambda n: os.path.getmtime(os.path.join(folder, n)))
    path = os.path.join(folder, newest)
    with open(path, 'rb') as fh:
        return parse_startup_info(fh.read()), int(os.path.getmtime(path))


def _cache_path():
    """Where the last figures read as admin are kept."""
    import updater
    return updater.USER_ROOT / 'startup_impact.json'


def load(admin: bool, cache_path=None) -> tuple:
    """(figures, measured_at, fresh): read Windows' figures when admin (and keep them), else
    the ones kept from the last admin run. fresh is False when they came from the cache."""
    cache_path = cache_path or _cache_path()
    if admin:
        import logging
        log = logging.getLogger("ramwarden")
        try:
            figures, when = read_latest()
            log.info("Startup impact: %d programs in Windows' sign-in figures", len(figures))
            if figures and time.time() - when > STALE_DAYS * 86400:
                # Windows 11 24H2 and later stopped writing these, leaving the last ones behind.
                log.info("Startup impact: Windows' figures are from %s, too old to use", time.ctime(when))
                return {}, when, True
            if figures:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps({'measured_at': when, 'figures': figures}),
                                          encoding='utf-8')
                except OSError:
                    pass
                return figures, when, True
        except (OSError, ET.ParseError):
            log.warning("Startup impact: couldn't read %s", STARTUP_INFO_DIR, exc_info=True)
    try:
        data = json.loads(cache_path.read_text(encoding='utf-8'))
        return {k: tuple(v) for k, v in data['figures'].items()}, int(data['measured_at']), False
    except (OSError, ValueError, KeyError, TypeError):
        return {}, 0, False


def rate_entries(entries: list, figures: dict, exe_of) -> None:
    """Set entry['impact'] on each startup entry: High / Medium / Low, 'None' when it's
    turned off, 'Not measured' when it didn't run at the last sign-in (or there are no
    figures), plus entry['impact_detail'] with the raw numbers. exe_of(command) gives an
    entry's program path."""
    by_path, by_name = {}, {}
    for path, fig in figures.items():
        full = os.path.normcase(path)
        by_path[full] = fig
        by_name.setdefault(os.path.basename(full), []).append(fig)

    for e in entries:
        e['impact_detail'] = ''
        if not e.get('enabled', True):
            e['impact'] = 'None'
            continue
        if not figures:
            e['impact'] = ''
            continue
        exe = os.path.normcase(os.path.expandvars(exe_of(e.get('command', '')) or ''))
        fig = by_path.get(exe)
        base = os.path.basename(exe)
        # The file may record a path in another form (e.g. 8.3 names); a unique program
        # name is good enough, except for hosts like rundll32 that run many things.
        if fig is None and base and base not in _GENERIC_HOSTS and len(by_name.get(base, [])) == 1:
            fig = by_name[base][0]
        if fig is None:
            e['impact'] = 'Not measured'
            continue
        cpu, disk = fig
        e['impact'] = level(cpu, disk)
        e['impact_detail'] = f"{cpu / 1_000_000:.1f} s CPU, {disk / 1024 / 1024:.1f} MB disk at sign-in"


def when_text(measured_at: int) -> str:
    """'at sign-in on 8 Oct, 9:14 am' for the status line."""
    if not measured_at:
        return ''
    t = time.localtime(measured_at)
    hour = t.tm_hour % 12 or 12
    ampm = 'am' if t.tm_hour < 12 else 'pm'
    year = f" {t.tm_year}" if t.tm_year != time.localtime().tm_year else ""
    return f"at sign-in on {t.tm_mday} {time.strftime('%b', t)}{year}, {hour}:{t.tm_min:02d} {ampm}"
