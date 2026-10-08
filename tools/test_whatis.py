"""Tests for whatis.py ("What is this?" explanations).

Run: python tools/test_whatis.py
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import whatis   # noqa: E402


def test_every_known_entry_is_lower_case_and_complete():
    for name, (what, advice) in whatis.KNOWN.items():
        assert name == name.lower(), name
        assert what.strip() and advice.strip(), name


def test_known_process_uses_the_written_explanation_whatever_the_case():
    info = whatis.explain('MsMpEng.exe')
    assert 'Defender' in info['what']
    assert info['advice'] == whatis.SECURITY


def test_unknown_program_in_windows_folder_is_left_alone():
    path = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'System32', 'notepad.exe')
    info = whatis.explain('somethingodd.exe', path)
    assert 'part of Windows' in info['advice']


def test_unknown_program_elsewhere_reads_its_own_details():
    info = whatis.explain('python-like.exe', sys.executable)    # not in KNOWN under this name
    assert info['publisher'] == 'Python Software Foundation'
    assert info['what'].endswith('.')
    assert 'search its name' in info['advice']


def test_missing_file_still_explains_something():
    info = whatis.explain('nothing.exe', r'C:\nope\nothing.exe')
    assert "doesn't know" in info['what']
    assert whatis.file_details('') == ('', '')


def test_as_text_includes_publisher_and_location():
    text = whatis.as_text('x.exe', {'what': 'A.', 'advice': 'B.', 'publisher': 'P', 'path': r'C:\x.exe'})
    assert text == "A.\n\nB.\n\nPublisher: P\n\nLocation: C:\\x.exe"


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
