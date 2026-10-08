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


# Windows' own scheduled tasks live in this folder. They're maintenance, not apps, and turning
# them off can break Windows features, so they aren't listed (whatever account they run as).
_WINDOWS_TASK_FOLDER = '\\microsoft\\windows\\'
_TASK_NS = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}


def _parse_tasks_xml(text: str) -> list:
    """Tasks that run at sign-in or start-up, from `schtasks /query /xml` output, skipping
    Windows' own (_WINDOWS_TASK_FOLDER). Third-party tasks are listed whatever account runs them.

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
        triggers = (task.findall('t:Triggers/t:LogonTrigger', _TASK_NS)
                    + task.findall('t:Triggers/t:BootTrigger', _TASK_NS))
        if not any((tr.findtext('t:Enabled', 'true', _TASK_NS) or 'true').strip().lower() != 'false' for tr in triggers):
            continue
        if path.lower().startswith(_WINDOWS_TASK_FOLDER) or path in seen:
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


# Store (packaged) apps' startup tasks: one subkey per package family, holding one subkey per
# task with a State value. The same switches Task Manager and Settings > Apps > Startup use.
_STORE_TASKS = r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData'
_STORE_PACKAGES = r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'
# State: 0 off (never turned on), 1 turned off by the user, 2 on, 3 off by policy, 4 on by policy.
_STORE_ON = {2, 4}
_STORE_POLICY = {3, 4}


def _subkeys(key) -> list:
    """Names of a registry key's subkeys."""
    names, i = [], 0
    while True:
        try:
            names.append(winreg.EnumKey(key, i))
        except OSError:
            return names
        i += 1


def _store_name(full_name: str, display: str) -> str:
    """A Store package's display name; 'ms-resource:…' names are looked up in the package."""
    if not display.startswith('ms-resource:'):
        return display
    import ctypes
    res = display[len('ms-resource:'):]
    if not res.startswith('/') and '/' not in res:
        res = 'Resources/' + res
    package = full_name.split('_')[0]
    buf = ctypes.create_unicode_buffer(512)
    ok = ctypes.windll.shlwapi.SHLoadIndirectString(
        f'@{{{full_name}?ms-resource://{package}/{res.lstrip("/")}}}', buf, 512, None) == 0
    return buf.value if ok and buf.value else ''


def _store_package(packages, family: str):
    """(display name, startup program path) for an installed package family; blanks if unknown."""
    name, _, publisher = family.rpartition('_')
    for full in _subkeys(packages):
        if not (full.startswith(name + '_') and full.endswith('__' + publisher)):
            continue
        try:
            with winreg.OpenKey(packages, full) as pk:
                display = winreg.QueryValueEx(pk, 'DisplayName')[0]
                root = winreg.QueryValueEx(pk, 'PackageRootFolder')[0]
        except OSError:
            continue
        return _store_name(full, display), _store_program(root)
    return '', ''


def _store_program(root: str) -> str:
    """The program a package's startup task runs: the task's own Executable, else its app's."""
    import re
    try:
        with open(os.path.join(root, 'AppxManifest.xml'), encoding='utf-8') as fh:
            manifest = fh.read()
    except OSError:
        return ''
    for app in re.findall(r'<Application\b.*?</Application>', manifest, re.S):
        task = re.search(r'<[\w:]*Extension\b[^>]*Category="windows\.startupTask"[^>]*>', app)
        if task:
            exe = re.search(r'Executable="([^"]+)"', task.group(0)) or re.search(r'Executable="([^"]+)"', app)
            return os.path.join(root, exe.group(1)) if exe else ''
    return ''


def _scan_store_tasks() -> list:
    """Startup tasks of Store apps (Teams, Phone Link, Windows Terminal…) for this user."""
    entries = []
    try:
        tasks = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STORE_TASKS)
        packages = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STORE_PACKAGES)
    except OSError:
        return []
    with tasks, packages:
        for family in _subkeys(tasks):
            with winreg.OpenKey(tasks, family) as fk:
                found = []
                for task_id in _subkeys(fk):
                    try:
                        with winreg.OpenKey(fk, task_id) as tk_:
                            found.append((task_id, winreg.QueryValueEx(tk_, 'State')[0]))
                    except OSError:
                        pass           # a subkey that isn't a startup task
            if not found:
                continue
            display, program = _store_package(packages, family)
            display = display or family.rpartition('_')[0].split('.')[-1]
            for task_id, state in found:
                entries.append({
                    # Packages with several tasks (Phone Link has two) show which is which.
                    'name':           display if len(found) == 1 else f'{display} ({task_id})',
                    'command':        f'"{program}"' if program else f'Store app {family}',
                    'source':         'Store',
                    'enabled':        state in _STORE_ON,
                    'key':            f'{_STORE_TASKS}\\{family}\\{task_id}',
                    'hive':           winreg.HKEY_CURRENT_USER,
                    'approved_subkey': '',
                    'policy':         state in _STORE_POLICY,
                })
    return entries


def _mark_missing(entries: list) -> None:
    """Set entry['missing'] when an entry's program isn't there (usually an app uninstalled
    without cleaning up): it does nothing at sign-in and is safe to turn off."""
    for e in entries:
        exe = os.path.expandvars(exe_of(e['command']))
        if e['source'] == 'Task' and e['command'] == 'COM handler':
            e['missing'] = False
        elif not e['command'].strip():
            e['missing'] = True
        else:
            # Only a full path can be checked; a bare name ("rundll32.exe") is found via PATH.
            e['missing'] = os.path.isabs(exe) and not os.path.exists(exe)


def exe_of(command: str) -> str:
    """The program part of a startup command (quoted or not), '' when there isn't one.

    An unquoted path may contain spaces ("C:\\Program Files (x86)\\App\\app.exe /x"), so it runs
    up to the first program extension, as Windows reads it; only otherwise to the first space."""
    import re
    try:
        raw = command.strip()
        if raw.startswith('"'):
            return raw[1:raw.index('"', 1)]
        m = re.match(r'(.+?\.(?:exe|com|bat|cmd|pyw?))(?=\s|$)', raw, re.I)
        return m.group(1) if m else raw.split()[0]
    except (IndexError, ValueError, AttributeError):
        return ''


def _dedup(entries: list) -> list:
    """Deduplicate by normalised executable path. Priority: Task > HKCU > HKLM."""
    priority = {'Task': 0, 'HKCU': 1, 'Folder': 1, 'HKLM': 2, 'Common': 2}
    seen = {}
    for e in entries:
        exe = exe_of(e['command'])
        exe_key = os.path.normcase(os.path.expandvars(exe)) if exe else e['name'].lower()
        current = seen.get(exe_key)
        if current is None or priority.get(e['source'], 9) < priority.get(current['source'], 9):
            seen[exe_key] = e
    return list(seen.values())


def scan_startup() -> list:
    """Scan Run keys, scheduled tasks, Startup folders and Store apps; return a sorted list of entry dicts."""
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
    entries.extend(_scan_store_tasks())    # after _dedup: each Store task is its own switch
    _mark_missing(entries)
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


def _set_store_enabled(entry: dict, enabled: bool) -> None:
    """Turn a Store app's startup task on (2) or off by the user (1), as Task Manager does.
    One set by the organisation's policy can't be changed."""
    if entry.get('policy'):
        raise StartupAccessError("It's set by your organisation's policy.")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, entry['key'], 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, 'State', 0, winreg.REG_DWORD, 2 if enabled else 1)
    except OSError as exc:
        raise StartupAccessError(str(exc)) from exc


def set_enabled(entry: dict, enabled: bool) -> None:
    """Enable or disable a startup entry. Raises StartupAccessError on permission failure."""
    if entry['source'] == 'Task':
        _set_task_enabled(entry['key'], enabled)
    elif entry['source'] == 'Store':
        _set_store_enabled(entry, enabled)
    else:
        _set_registry_enabled(entry['hive'], entry['approved_subkey'], entry['key'], enabled)
