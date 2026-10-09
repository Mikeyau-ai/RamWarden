"""
impact.py — startup impact (High / Medium / Low), the way Task Manager worked it out.

Task Manager rated each startup app by its CPU time and disk I/O in the first 90 seconds
after sign-in:
  High:   over 1 s of CPU or over 3 MB of disk
  Medium: over 300 ms of CPU or over 300 KB of disk
  Low:    less than both

Its figures came from %WINDIR%\\System32\\WDI\\LogFiles\\StartupInfo (admin-only), which
Windows 11 24H2 and later no longer write. So when RamWarden starts with Windows it measures
the same window itself (measure_signin) and keeps the result in
%LOCALAPPDATA%\\RamWarden\\startup_impact.json. On older Windows run as admin, Windows' own
figures are used when they're newer. No tkinter dependency.
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
    """Where the latest figures are kept between runs."""
    import updater
    return updater.USER_ROOT / 'startup_impact.json'


def save(figures: dict, measured_at: int, cache_path=None) -> None:
    """Keep a sign-in's figures for later runs (the Startup tab reads them from here)."""
    cache_path = cache_path or _cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({'measured_at': measured_at, 'figures': figures}), encoding='utf-8')
    except OSError:
        pass


def _read_cache(cache_path) -> tuple:
    """(figures, measured_at) kept from an earlier sign-in, ({}, 0) when there are none."""
    try:
        data = json.loads(cache_path.read_text(encoding='utf-8'))
        return {k: tuple(v) for k, v in data['figures'].items()}, int(data['measured_at'])
    except (OSError, ValueError, KeyError, TypeError):
        return {}, 0


def load(admin: bool, cache_path=None) -> tuple:
    """(figures, measured_at): the newest figures there are. Usually RamWarden's own sign-in
    measurement; on older Windows run as admin, Windows' own figures when they're newer."""
    import logging
    log = logging.getLogger("ramwarden")
    cache_path = cache_path or _cache_path()
    figures, when = _read_cache(cache_path)
    if admin:
        try:
            wdi, wdi_when = read_latest()
            if wdi and time.time() - wdi_when > STALE_DAYS * 86400:
                # Windows 11 24H2 and later stopped writing these, leaving the last ones behind.
                log.info("Startup impact: Windows' own figures are from %s, too old to use", time.ctime(wdi_when))
            elif wdi and wdi_when > when:
                save(wdi, wdi_when, cache_path)
                return wdi, wdi_when
        except (OSError, ET.ParseError):
            log.warning("Startup impact: couldn't read %s", STARTUP_INFO_DIR, exc_info=True)
    return figures, when


# ── RamWarden's own measurement ─────────────────────────────────────────────────────────────
# Windows' figures are gone on current Windows 11, so when RamWarden starts with Windows it
# measures the same thing itself: CPU time and bytes read/written by every program started in
# the first WINDOW_S seconds after sign-in. Each process carries its own running totals, so
# RamWarden needn't be first; it checks every POLL_S seconds to also catch programs that start
# and finish early (launchers, updaters), keeping the last figures seen for each.
WINDOW_S = 90
POLL_S = 2
LATE_LIMIT_S = 300      # started this long after sign-in (e.g. reopened later): don't measure


def _own_session() -> int:
    """This process's sign-in session number."""
    import ctypes
    sid = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
    return sid.value


def signed_in_at(procs, session: int) -> float:
    """When this user signed in: the start of their session's first Explorer (the desktop)."""
    times = [p.created for p in procs
             if p.session == session and p.name.lower() == 'explorer.exe' and p.created]
    return min(times) if times else 0.0


def measure_signin(snapshot=None, now=time.time, sleep=time.sleep, session=None) -> tuple:
    """Watch the sign-in window, then return (figures, signed_in_at); ({}, 0) when RamWarden
    started too long after sign-in. figures: {program name: (cpu_us, io_bytes)}, copies of a
    program added together, the same shape as Windows' figures."""
    if snapshot is None:
        import procsnap
        snapshot = procsnap.snapshot
    session = _own_session() if session is None else session
    procs = snapshot()
    start = signed_in_at(procs, session)
    if not start or now() - start > LATE_LIMIT_S:
        return {}, 0
    end = start + WINDOW_S
    seen = {}                                   # (pid, start time) -> [name, cpu s, io bytes, parent pid]
    while True:
        for p in procs:
            if p.session == session and start - 2 <= p.created <= end:
                seen[p.key] = [p.name.lower(), p.cpu_time, p.io_bytes, getattr(p, 'ppid', 0)]
        if now() >= end:
            break
        sleep(min(POLL_S, max(0.1, end - now())))
        procs = snapshot()

    figures = {}
    for name, cpu, io, _ in seen.values():
        old = figures.get(name, (0, 0))
        figures[name] = (old[0] + int(cpu * 1_000_000), old[1] + int(io))

    # Launchers: a startup entry often runs a small program that starts the real app and quits
    # (AVG's AvLaunch, Teams' autostarter, OneDriveLauncher, Discord's Update.exe). Credit what
    # such a launcher started to the launcher, so its entry gets the real app's figures.
    alive = {p.key for p in procs}
    for (pid, born), (name, *_rest) in seen.items():
        if (pid, born) in alive:
            continue                            # still running: not a launcher
        children = [v for (cpid, cborn), v in seen.items() if v[3] == pid and cborn >= born and cpid != pid]
        if children:
            cpu, io = figures[name]
            figures[name] = (cpu + sum(int(c[1] * 1_000_000) for c in children), io + sum(int(c[2]) for c in children))
    return figures, int(start)


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
        # A launcher like Discord's ("Update.exe --processStart Discord.exe") quits at once;
        # the app it starts is what costs, so its figures count too.
        # (Measured launchers already include it; this covers one that quit unseen.)
        launched = re.search(r'--processStart\s+"?([^"\s]+)', e.get('command', ''), re.I)
        extra = by_name.get(os.path.normcase(launched.group(1)), []) if launched else []
        if fig is None and len(extra) == 1:
            fig = extra[0]
        # Entries named after their real program ("AVGUI.exe" runs AvLaunch.exe) match by name too.
        named = os.path.normcase(e.get('name', ''))
        if fig is None and named.endswith('.exe') and len(by_name.get(named, [])) == 1:
            fig = by_name[named][0]
        if fig is None:
            e['impact'] = 'Not measured'
            continue
        cpu, disk = fig
        e['impact'] = level(cpu, disk)
        e['impact_detail'] = f"{cpu / 1_000_000:.1f} s CPU, {disk / 1024 / 1024:.1f} MB read or written in the first 90 s"


def when_text(measured_at: int) -> str:
    """'at sign-in on 8 Oct, 9:14 am' for the status line."""
    if not measured_at:
        return ''
    t = time.localtime(measured_at)
    hour = t.tm_hour % 12 or 12
    ampm = 'am' if t.tm_hour < 12 else 'pm'
    year = f" {t.tm_year}" if t.tm_year != time.localtime().tm_year else ""
    return f"at sign-in on {t.tm_mday} {time.strftime('%b', t)}{year}, {hour}:{t.tm_min:02d} {ampm}"
