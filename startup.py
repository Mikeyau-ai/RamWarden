"""
startup.py — Windows startup entry scanner and toggler for RamWarden.
No tkinter dependency. Public API: scan_startup(), set_enabled(), StartupAccessError.
"""
import os
import winreg

from lnkfile import read_lnk

class StartupAccessError(Exception):
    """Raised when enable/disable requires elevation."""


# Registry Run key locations: (hive, run_subkey, source_label, approved_subkey, access)
_RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER,
     r'Software\Microsoft\Windows\CurrentVersion\Run',
     'HKCU',
     r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
     winreg.KEY_READ),
    (winreg.HKEY_LOCAL_MACHINE,
     r'Software\Microsoft\Windows\CurrentVersion\Run',
     'HKLM',
     r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
     winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE,
     r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run',
     'HKLM',
     r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32',
     winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
]


def _read_run_key(hive: int, subkey: str, source: str, access: int = winreg.KEY_READ) -> list:
    """Return list of partial entry dicts from one Run registry key. enabled=True placeholder."""
    entries = []
    try:
        key = winreg.OpenKey(hive, subkey, access=access)
    except OSError:
        return []
    with key:
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                entries.append({
                    'name':    name,
                    'command': value,
                    'source':  source,
                    'enabled': True,   # overwritten by _read_approved below
                    'key':     name,   # value name in the Run key
                    'hive':    hive,
                    'approved_subkey': '',
                })
                i += 1
            except OSError:
                break
    return entries


def _read_approved(hive: int, subkey: str) -> dict:
    """Return {value_name: bool} from a StartupApproved subkey. Missing name → True (enabled)."""
    result = {}
    try:
        key = winreg.OpenKey(hive, subkey, access=winreg.KEY_READ)
    except OSError:
        return result
    with key:
        i = 0
        while True:
            try:
                name, data, _ = winreg.EnumValue(key, i)
                # First byte: 0x02 = enabled, 0x03 = disabled
                result[name] = (len(data) > 0 and data[0] == 0x02)
                i += 1
            except OSError:
                break
    return result


_STARTUP_FOLDERS = [
    (
        os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup'),
        winreg.HKEY_CURRENT_USER,
        r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder',
        'Folder',
    ),
    (
        os.path.expandvars(r'%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Startup'),
        winreg.HKEY_LOCAL_MACHINE,
        r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder',
        'Common',
    ),
]


def _scan_startup_folders() -> list:
    """Return startup entries from user and all-users Startup folders."""
    entries = []
    for folder_path, hive, approved_subkey, source in _STARTUP_FOLDERS:
        try:
            lnk_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.lnk')]
        except OSError:
            continue
        if not lnk_files:
            continue
        approved = _read_approved(hive, approved_subkey)
        for lnk_filename in lnk_files:
            name = os.path.splitext(lnk_filename)[0]
            # Read the shortcut directly (lnkfile); this used to start PowerShell for every folder.
            target, args = read_lnk(os.path.join(folder_path, lnk_filename))
            command = (f'{target} {args}'.strip() if target else '') or os.path.join(folder_path, lnk_filename)
            enabled = approved.get(lnk_filename, True)
            entries.append({
                'name':           name,
                'command':        command,
                'source':         source,
                'enabled':        enabled,
                'key':            lnk_filename,
                'hive':           hive,
                'approved_subkey': approved_subkey,
            })
    return entries


# Accounts whose logon tasks belong to Windows itself (SIDs, and names for older task files).
_SYSTEM_ACCOUNTS = {'S-1-5-18', 'S-1-5-19', 'S-1-5-20', 'SYSTEM', 'NT AUTHORITY\\SYSTEM',
                    'LOCAL SERVICE', 'NETWORK SERVICE', 'NT AUTHORITY\\LOCAL SERVICE',
                    'NT AUTHORITY\\NETWORK SERVICE'}
_TASK_NS = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}


def _parse_tasks_xml(text: str) -> list:
    """Logon-triggered tasks from `schtasks /query /xml` output, skipping Windows' own accounts.

    That output is each task's own XML document (declaration and all) inside a <Tasks> wrapper,
    each preceded by a <!-- \\Path\\Name --> comment, so the tasks are parsed one at a time.
    The XML element names are the same in every Windows language, unlike schtasks' CSV text
    columns ("Schedule Type", "At logon time"), which are translated, so the old parser found
    no tasks at all on non-English Windows."""
    import re
    import xml.etree.ElementTree as ET
    tasks, seen = [], set()
    for path, body in re.findall(r'<!--\s*(.+?)\s*-->\s*(?:<\?xml[^>]*\?>)?\s*(<Task\b.*?</Task>)', text, re.S):
        try:
            task = ET.fromstring(body)
        except ET.ParseError:
            continue
        triggers = task.findall('t:Triggers/t:LogonTrigger', _TASK_NS)
        if not any((tr.findtext('t:Enabled', 'true', _TASK_NS) or 'true').strip().lower() != 'false' for tr in triggers):
            continue
        user = (task.findtext('t:Principals/t:Principal/t:UserId', '', _TASK_NS) or '').strip().upper()
        if user in _SYSTEM_ACCOUNTS or path in seen:
            continue
        seen.add(path)
        exe = task.find('t:Actions/t:Exec', _TASK_NS)
        if exe is not None:
            command = ' '.join(x for x in (exe.findtext('t:Command', '', _TASK_NS).strip(),
                                           exe.findtext('t:Arguments', '', _TASK_NS).strip()) if x)
        else:
            command = 'COM handler'
        enabled = (task.findtext('t:Settings/t:Enabled', 'true', _TASK_NS) or 'true').strip().lower() != 'false'
        tasks.append({
            'name':           os.path.basename(path.strip('\\')) or path,
            'command':        command,
            'source':         'Task',
            'enabled':        enabled,
            'key':            path,
            'hive':           None,
            'approved_subkey': '',
        })
    return tasks


def _scan_tasks() -> list:
    """Return logon-triggered Task Scheduler entries, excluding Windows' own (SYSTEM etc.)."""
    import subprocess
    try:
        result = subprocess.run(
            ['schtasks', '/query', '/xml'],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=15,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    # schtasks writes in the console's code page; UTF-8 first, then Windows' ANSI page.
    try:
        text = result.stdout.decode('utf-8')
    except UnicodeDecodeError:
        text = result.stdout.decode('mbcs', errors='replace')
    return _parse_tasks_xml(text)


def _dedup(entries: list) -> list:
    """Deduplicate by normalised executable path. Priority: Task > HKCU > HKLM."""
    priority = {'Task': 0, 'HKCU': 1, 'Folder': 1, 'HKLM': 2, 'Common': 2}
    seen = {}
    for e in entries:
        try:
            raw = e['command'].strip()
            if raw.startswith('"'):
                raw = raw[1:raw.index('"', 1)]
            else:
                raw = raw.split()[0]
            exe_key = os.path.normcase(os.path.expandvars(raw))
        except (IndexError, ValueError, AttributeError):
            exe_key = e['name'].lower()
        current = seen.get(exe_key)
        if current is None or priority.get(e['source'], 9) < priority.get(current['source'], 9):
            seen[exe_key] = e
    return list(seen.values())


def scan_startup() -> list:
    """Scan Registry Run keys and Task Scheduler; return deduplicated sorted list of entry dicts."""
    entries = []
    for hive, subkey, source, approved_subkey, access in _RUN_KEYS:
        approved = _read_approved(hive, approved_subkey)
        for e in _read_run_key(hive, subkey, source, access):
            e['enabled'] = approved.get(e['name'], True)
            e['approved_subkey'] = approved_subkey
            entries.append(e)
    entries.extend(_scan_tasks())
    entries.extend(_scan_startup_folders())
    entries = _dedup(entries)
    return sorted(entries, key=lambda x: x['name'].lower())


def _set_registry_enabled(hive: int, approved_subkey: str, name: str, enabled: bool) -> None:
    """Write to StartupApproved subkey to enable/disable without touching the Run key."""
    # 12-byte binary: first byte 0x02=enabled, 0x03=disabled, rest zeros
    data = bytes([0x02 if enabled else 0x03]) + b'\x00' * 11
    try:
        key = winreg.OpenKey(hive, approved_subkey, access=winreg.KEY_SET_VALUE)
    except FileNotFoundError:
        # StartupApproved key doesn't exist yet — create it
        try:
            key = winreg.CreateKeyEx(hive, approved_subkey, access=winreg.KEY_SET_VALUE)
        except PermissionError as exc:
            raise StartupAccessError(str(exc)) from exc
    except PermissionError as exc:
        raise StartupAccessError(str(exc)) from exc
    try:
        with key:
            winreg.SetValueEx(key, name, 0, winreg.REG_BINARY, data)
    except PermissionError as exc:
        raise StartupAccessError(str(exc)) from exc


def _set_task_enabled(task_name: str, enabled: bool) -> None:
    """Enable or disable a scheduled task via schtasks /change."""
    import subprocess
    flag = '/enable' if enabled else '/disable'
    result = subprocess.run(
        ['schtasks', '/change', '/tn', task_name, flag],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=10,
    )
    if result.returncode != 0:
        msg = result.stderr.decode(errors='replace').strip() or f'schtasks exited {result.returncode}'
        raise StartupAccessError(msg)


def set_enabled(entry: dict, enabled: bool) -> None:
    """Enable or disable a startup entry. Raises StartupAccessError on permission failure."""
    if entry['source'] == 'Task':
        _set_task_enabled(entry['key'], enabled)
    else:
        _set_registry_enabled(entry['hive'], entry['approved_subkey'], entry['key'], enabled)
