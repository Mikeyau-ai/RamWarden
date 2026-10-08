"""Offline tests for impact.py (startup impact ratings), using a made-up StartupInfo file in a
temp folder written the way Windows writes them (UTF-16 with a byte-order mark).

Run: python tools/test_impact.py
"""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import impact           # noqa: E402
from startup import exe_of   # noqa: E402

SID = "S-1-5-21-1-2-3-1001"


def process(name, cpu_us, disk_bytes, pid=100):
    """One <Process> element as Windows writes it."""
    return (f'<Process Name="{name}" PID="{pid}" StartedInTraceSec="1.2">'
            f'<StartTime>2026/10/08:09:14:01.000000</StartTime>'
            f'<CommandLine><![CDATA["{name}"]]></CommandLine>'
            f'<DiskUsage Units="bytes">{disk_bytes}</DiskUsage>'
            f'<CpuUsage Units="us">{cpu_us}</CpuUsage>'
            f'<ParentPID>4</ParentPID></Process>')


def sample_file(*procs) -> bytes:
    """A whole StartupInfo file, UTF-16 with BOM and an encoding declaration."""
    xml = '<?xml version="1.0" encoding="UTF-16"?><StartupData>' + ''.join(procs) + '</StartupData>'
    return xml.encode('utf-16')


def test_levels_match_task_manager():
    assert impact.level(1_200_000, 0) == 'High'
    assert impact.level(0, 4 * 1024 * 1024) == 'High'
    assert impact.level(500_000, 0) == 'Medium'
    assert impact.level(0, 400 * 1024) == 'Medium'
    assert impact.level(100_000, 100 * 1024) == 'Low'


def test_parse_adds_copies_of_the_same_program():
    raw = sample_file(process(r"C:\Apps\Chat\chat.exe", 400_000, 0, 1),
                      process(r"C:\Apps\Chat\chat.exe", 700_000, 0, 2),
                      process(r"C:\Apps\Tiny\tiny.exe", 1_000, 2_000, 3))
    figs = impact.parse_startup_info(raw)
    assert figs[r"C:\Apps\Chat\chat.exe"] == (1_100_000, 0)
    assert figs[r"C:\Apps\Tiny\tiny.exe"] == (1_000, 2_000)


def test_parse_survives_windows_unescaped_ampersands():
    # Windows really writes this (seen on a live PC): a bare & that makes the file invalid XML.
    raw = sample_file(process(r"C:\Program Files (x86)\Spybot - Search & Destroy 2\SDTray.exe", 5, 6),
                      process(r"C:\a&amp;b.exe", 1, 2))
    figs = impact.parse_startup_info(raw)
    assert figs[r"C:\Program Files (x86)\Spybot - Search & Destroy 2\SDTray.exe"] == (5, 6)
    assert figs[r"C:\a&b.exe"] == (1, 2)


def test_old_figures_are_ignored_but_their_date_kept():
    import os, time, unittest.mock as mock
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / f"{SID}_StartupInfo1.xml"
        f.write_bytes(sample_file(process(r"C:\a.exe", 1, 1)))
        old = time.time() - 700 * 86400
        os.utime(f, (old, old))
        cache = pathlib.Path(d) / "cache.json"
        with mock.patch.object(impact, "STARTUP_INFO_DIR", d), mock.patch.object(impact, "_current_sid", lambda: SID):
            assert impact.load(True, cache) == ({}, int(old), True)
        assert not cache.exists()                                  # stale figures aren't kept
        assert str(time.localtime(old).tm_year) in impact.when_text(int(old))


def test_read_latest_picks_this_users_newest_file():
    with tempfile.TemporaryDirectory() as d:
        folder = pathlib.Path(d)
        (folder / f"{SID}_StartupInfo1.xml").write_bytes(sample_file(process(r"C:\a.exe", 1, 1)))
        newest = folder / f"{SID}_StartupInfo2.xml"
        newest.write_bytes(sample_file(process(r"C:\b.exe", 2, 2)))
        other = folder / "S-1-5-21-9-9-9-500_StartupInfo1.xml"   # another user's sign-in
        other.write_bytes(sample_file(process(r"C:\c.exe", 3, 3)))
        import os, time
        now = time.time()
        os.utime(folder / f"{SID}_StartupInfo1.xml", (now - 100, now - 100))
        os.utime(newest, (now - 10, now - 10))
        os.utime(other, (now, now))
        figs, when = impact.read_latest(str(folder), sid=SID)
        assert list(figs) == [r"C:\b.exe"]
        assert when == int(now - 10)


def test_rate_entries_matches_by_path_then_unique_name():
    figs = {r"C:\Program Files\Chat\Chat.exe": (1_500_000, 0),
            r"C:\PROGRA~1\Sync\sync.exe": (50_000, 10_000),
            r"C:\Windows\System32\rundll32.exe": (2_000_000, 0)}
    entries = [
        {'name': 'Chat', 'command': r'"C:\Program Files\Chat\chat.exe" --minimised', 'enabled': True},
        {'name': 'Sync', 'command': r'"C:\Program Files\Sync\sync.exe"', 'enabled': True},     # 8.3 path in the file
        {'name': 'Helper', 'command': r'rundll32.exe C:\x.dll,Run', 'enabled': True},           # generic host
        {'name': 'Off', 'command': r'"C:\Program Files\Chat\chat.exe"', 'enabled': False},
        {'name': 'Gone', 'command': r'C:\nothere.exe', 'enabled': True},
    ]
    impact.rate_entries(entries, figs, exe_of)
    assert [e['impact'] for e in entries] == ['High', 'Low', 'Not measured', 'None', 'Not measured']
    assert entries[0]['impact_detail'] == "1.5 s CPU, 0.0 MB disk at sign-in"


def test_no_figures_leaves_the_column_blank():
    entries = [{'name': 'Chat', 'command': r'C:\chat.exe', 'enabled': True}]
    impact.rate_entries(entries, {}, exe_of)
    assert entries[0]['impact'] == ''


def test_load_uses_the_kept_figures_when_not_admin():
    with tempfile.TemporaryDirectory() as d:
        cache = pathlib.Path(d) / "startup_impact.json"
        assert impact.load(False, cache) == ({}, 0, False)
        cache.write_text('{"measured_at": 1760000000, "figures": {"C:\\\\a.exe": [5, 6]}}', encoding='utf-8')
        assert impact.load(False, cache) == ({r"C:\a.exe": (5, 6)}, 1760000000, False)


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
