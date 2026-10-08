"""Tests for startup.py's parsing: program paths, which scheduled tasks are listed, and the
"missing program" flag. Nothing here changes the PC's startup settings.

Run: python tools/test_startup.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import startup   # noqa: E402


def test_exe_of_reads_quoted_unquoted_and_spaced_paths():
    assert startup.exe_of('"C:\\Program Files\\App\\app.exe" --min') == 'C:\\Program Files\\App\\app.exe'
    # Unquoted with spaces: up to the program's extension, as Windows reads it.
    assert startup.exe_of('C:\\Program Files (x86)\\MSI Afterburner\\MSIAfterburner.exe /s') == \
        'C:\\Program Files (x86)\\MSI Afterburner\\MSIAfterburner.exe'
    assert startup.exe_of('rundll32.exe C:\\x.dll,Run') == 'rundll32.exe'
    assert startup.exe_of('%windir%\\system32\\DFDWiz.exe') == '%windir%\\system32\\DFDWiz.exe'
    assert startup.exe_of('') == ''


def task(path, trigger, user='S-1-5-18', command='C:\\App\\app.exe'):
    """One task as `schtasks /query /xml` prints it."""
    return (f'<!-- {path} -->\n<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            f'<Triggers><{trigger}><Enabled>true</Enabled></{trigger}></Triggers>'
            f'<Principals><Principal><UserId>{user}</UserId></Principal></Principals>'
            f'<Actions><Exec><Command>{command}</Command></Exec></Actions></Task>\n')


def test_tasks_hide_windows_own_but_keep_third_party_whatever_the_account():
    xml = '<Tasks>' + ''.join([
        task('\\Microsoft\\Windows\\DiskDiagnostic\\Resolver', 'LogonTrigger', user='S-1-5-32-545'),
        task('\\GoogleUpdaterSystem', 'LogonTrigger', user='S-1-5-18'),       # SYSTEM, but not Windows'
        task('\\VendorBootHelper', 'BootTrigger'),
        task('\\NightlyBackup', 'CalendarTrigger'),                           # not at start-up
    ]) + '</Tasks>'
    names = [t['name'] for t in startup._parse_tasks_xml(xml)]
    assert names == ['GoogleUpdaterSystem', 'VendorBootHelper']


def test_missing_program_flag():
    here = sys.executable
    entries = [
        {'name': 'ok', 'source': 'HKCU', 'command': f'"{here}" -x'},
        {'name': 'gone', 'source': 'HKCU', 'command': '"C:\\Nope\\gone.exe"'},
        {'name': 'empty', 'source': 'HKCU', 'command': ''},
        {'name': 'bare', 'source': 'HKCU', 'command': 'rundll32.exe x.dll'},
        {'name': 'com', 'source': 'Task', 'command': 'COM handler'},
    ]
    startup._mark_missing(entries)
    assert [e['missing'] for e in entries] == [False, True, True, False, False]


def test_store_display_names_pass_through_unless_a_resource():
    assert startup._store_name('X_1.0.0.0_x64__abc', 'Microsoft Teams') == 'Microsoft Teams'


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception as e:                       # noqa: BLE001 (report and carry on)
            failed += 1
            print("FAIL", name, repr(e))
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
