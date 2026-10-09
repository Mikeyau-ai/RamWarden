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


def test_old_windows_figures_are_ignored():
    import os, time, unittest.mock as mock
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / f"{SID}_StartupInfo1.xml"
        f.write_bytes(sample_file(process(r"C:\a.exe", 1, 1)))
        old = time.time() - 700 * 86400
        os.utime(f, (old, old))
        cache = pathlib.Path(d) / "cache.json"
        with mock.patch.object(impact, "STARTUP_INFO_DIR", d), mock.patch.object(impact, "_current_sid", lambda: SID):
            assert impact.load(True, cache) == ({}, 0)
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
    assert entries[0]['impact_detail'] == "1.5 s CPU, 0.0 MB read or written in the first 90 s"


def test_no_figures_leaves_the_column_blank():
    entries = [{'name': 'Chat', 'command': r'C:\chat.exe', 'enabled': True}]
    impact.rate_entries(entries, {}, exe_of)
    assert entries[0]['impact'] == ''


def test_load_returns_the_kept_figures():
    with tempfile.TemporaryDirectory() as d:
        cache = pathlib.Path(d) / "startup_impact.json"
        assert impact.load(False, cache) == ({}, 0)
        impact.save({"a.exe": (5, 6)}, 1760000000, cache)
        assert impact.load(False, cache) == ({"a.exe": (5, 6)}, 1760000000)


class P:
    """A fake procsnap.Proc."""
    def __init__(self, pid, name, created, cpu, io, session=1, ppid=0):
        self.pid, self.name, self.created, self.ppid = pid, name, created, ppid
        self.cpu_time, self.io_bytes, self.session = cpu, io, session
        self.key = (pid, created)


def test_measure_signin_keeps_programs_that_quit_and_ignores_the_rest():
    t0 = 1_000_000.0
    clock = {'now': t0 + 20}                     # RamWarden starts 20 s after sign-in
    snaps = [
        # At 20 s: the desktop, a launcher about to quit, a chat app, a service, an old process.
        [P(1, 'explorer.exe', t0, 0.5, 0), P(2, 'Update.exe', t0 + 8, 0.2, 100_000),
         P(3, 'Discord.exe', t0 + 9, 0.4, 1_000_000, ppid=2), P(4, 'svc.exe', t0 + 5, 9.0, 0, session=0),
         P(5, 'old.exe', t0 - 600, 50.0, 0)],
        # Later: the launcher has quit; Discord kept working; a second Discord copy started.
        [P(1, 'explorer.exe', t0, 0.6, 0), P(3, 'Discord.exe', t0 + 9, 1.1, 4_000_000, ppid=2),
         P(6, 'Discord.exe', t0 + 30, 0.3, 0, ppid=3)],
    ]
    calls = []

    def snapshot():
        calls.append(1)
        return snaps[min(len(calls), len(snaps)) - 1]

    def sleep(seconds):
        clock['now'] += seconds

    figs, when = impact.measure_signin(snapshot, now=lambda: clock['now'], sleep=sleep, session=1)
    assert when == int(t0)
    assert figs['discord.exe'] == (1_400_000, 4_000_000)       # both copies, latest figures
    # The launcher quit, so it's kept, with the Discord it started credited to it.
    assert figs['update.exe'] == (200_000 + 1_100_000, 100_000 + 4_000_000)
    assert figs['explorer.exe'] == (600_000, 0)                # still running: nothing credited
    assert 'svc.exe' not in figs and 'old.exe' not in figs     # another session; started long before
    assert clock['now'] >= t0 + impact.WINDOW_S                # watched until 90 s after sign-in


def test_measure_signin_skips_a_late_start():
    t0 = 1_000_000.0
    snap = lambda: [P(1, 'explorer.exe', t0, 1, 0)]
    assert impact.measure_signin(snap, now=lambda: t0 + 3600, sleep=lambda s: None, session=1) == ({}, 0)


def test_unseen_launcher_falls_back_to_the_app_it_names():
    figs = {'discord.exe': (1_400_000, 0), 'avgui.exe': (500_000, 0)}      # launchers quit unseen
    e = [{'name': 'Discord', 'enabled': True,
          'command': r'"C:\Users\x\AppData\Local\Discord\Update.exe" --processStart Discord.exe'},
         {'name': 'AVGUI.exe', 'enabled': True, 'command': r'"C:\Program Files\AVG\Antivirus\AvLaunch.exe" /gui'}]
    impact.rate_entries(e, figs, exe_of)
    assert [x['impact'] for x in e] == ['High', 'Medium']


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
