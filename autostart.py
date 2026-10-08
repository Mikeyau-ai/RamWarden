"""
autostart.py — the "Start with Windows" switch: a per-user Run entry that starts RamWarden
hidden in the tray (--tray). Off unless the user turns it on; no administrator rights needed.

The Store copy is started through its app execution alias (RamWarden.exe in
%LOCALAPPDATA%\\Microsoft\\WindowsApps, declared in the package manifest), because its real
program path changes with every update. No tkinter dependency.
"""
import os
import sys
import winreg

TRAY_FLAG = '--tray'
VALUE = 'RamWarden'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APPROVED_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'


def command(store=None):
    """The command Windows should run at sign-in to start this copy of RamWarden in the tray."""
    if store is None:
        import updater
        store = updater.is_store_install()
    if store:
        alias = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps', 'RamWarden.exe')
        return f'"{alias}" {TRAY_FLAG}'
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}" {TRAY_FLAG}'
    # From source: the windowless Python, so no console flashes up at sign-in.
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    main = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.pyw')
    return f'"{pythonw}" "{main}" {TRAY_FLAG}'


def is_enabled():
    """True when the Run entry exists and hasn't been turned off (e.g. in Task Manager)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE)
    except OSError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            data, _ = winreg.QueryValueEx(key, VALUE)
            return not data or data[0] != 0x03          # 0x03 = turned off in Startup settings
    except OSError:
        return True


def set_enabled(on):
    """Add or remove the Run entry. Turning it on also clears an 'off' left by Task Manager."""
    if on:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, command())
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE)
        except OSError:
            pass
    else:
        for subkey in (RUN_KEY, APPROVED_KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, VALUE)
            except OSError:
                pass
