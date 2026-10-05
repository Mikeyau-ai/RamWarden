"""Offline tests for licence.py: a throwaway signing key, a fake site and a temp licence file,
so nothing touches the real sixthdaystudios.com or this PC's real licence.

Run: python tools/test_licence.py
"""
import base64
import json
import os
import pathlib
import secrets
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ed25519   # noqa: E402
import licence   # noqa: E402

SEED = secrets.token_bytes(32)
licence.PUBLIC_KEY = ed25519.public_key(SEED)
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
NOW = time.time()


def token(kind, exp, device=None, product="ramwarden", iat=None, seed=SEED):
    """A token signed the way the site signs them."""
    body = b64(json.dumps({"v": 1, "k": kind, "p": product, "l": 7, "d": device or licence.device_id(),
                           "iat": iat or NOW, "exp": exp}).encode())
    return body + "." + b64(ed25519.sign(seed, body.encode()))


class FakeSite:
    """Answers licence._post with scripted replies and records the calls."""
    def __init__(self, replies):
        self.replies, self.calls = dict(replies), []

    def __call__(self, path, body):
        self.calls.append(path)
        return self.replies.get(path, (None, {}))


def fresh(state=None, site=None):
    """Point licence.py at a new temp file (optionally pre-filled) and a fake site."""
    d = tempfile.mkdtemp()
    licence._FILE = pathlib.Path(d) / "licence.json"
    if state is not None:
        licence._FILE.write_text(json.dumps(state))
    licence._post = site or FakeSite({})
    return licence._post


def test_first_launch_offline_gets_grace_then_needs_a_check():
    fresh()
    licence.status()                                                    # first launch records first_seen
    assert abs(json.loads(licence._FILE.read_text())["first_seen"] - time.time()) < 5
    fresh({"first_seen": NOW})
    assert licence.status(NOW) == {"state": "trial", "days_left": 14}
    assert licence.allowed(NOW)
    assert licence.status(NOW + 15 * 86400)["state"] == "check_needed"
    assert not licence.allowed(NOW + 15 * 86400)


def test_trial_from_site_then_over():
    site = fresh(site=FakeSite({"licence/trial": (200, {"token": token("trial", NOW + 5 * 86400)})}))
    licence.sync(NOW)
    assert site.calls == ["licence/trial"]
    assert licence.status(NOW) == {"state": "trial", "days_left": 5}
    assert licence.status(NOW + 6 * 86400)["state"] == "trial_over"
    fresh(site=FakeSite({"licence/trial": (200, {"expired": True})}))
    licence.sync(NOW)
    assert licence.status(NOW)["state"] == "trial_over" and not licence.allowed(NOW)


def test_forged_wrong_pc_and_wrong_product_tokens_are_ignored():
    other_key = secrets.token_bytes(32)
    for bad in [token("licence", NOW + 86400, seed=other_key), token("licence", NOW + 86400, device="0" * 32),
                token("licence", NOW + 86400, product="ashenfall"), "not.a-token", None]:
        fresh({"token": bad, "first_seen": NOW - 30 * 86400})
        assert not licence.allowed(NOW), bad


def test_code_activation_and_licensed_state():
    good = token("licence", NOW + 60 * 86400)
    fresh(site=FakeSite({"licence/activate": (200, {"token": good})}))
    ok, _ = licence.activate_code("RAMWARDEN-AAAA")
    assert ok and licence.status(NOW) == {"state": "licensed", "days_left": 60}
    fresh(site=FakeSite({"licence/activate": (404, {"error": "That code isn't right."})}))
    assert licence.activate_code("nope") == (False, "That code isn't right.")
    fresh(site=FakeSite({}))
    assert licence.activate_code("x")[0] is False                       # offline


def test_licence_refresh_and_removal():
    old = token("licence", NOW + 10 * 86400, iat=NOW - 50 * 86400)
    new = token("licence", NOW + 60 * 86400)
    site = fresh({"token": old, "first_seen": NOW - 99 * 86400}, FakeSite({"licence/refresh": (200, {"token": new})}))
    licence.sync(NOW)
    assert site.calls == ["licence/refresh"] and licence.status(NOW)["days_left"] == 60
    # Removed on the website / refunded: back to trial rules (over here)
    site = fresh({"token": old, "first_seen": NOW - 99 * 86400},
                 FakeSite({"licence/refresh": (403, {"code": "removed"}), "licence/trial": (200, {"expired": True})}))
    licence.sync(NOW)
    assert site.calls == ["licence/refresh", "licence/trial"] and licence.status(NOW)["state"] == "trial_over"
    # Offline: keeps the licence until the token itself runs out, then needs a check
    fresh({"token": old, "first_seen": NOW - 99 * 86400})
    licence.sync(NOW)
    assert licence.status(NOW)["state"] == "licensed"
    assert licence.status(NOW + 11 * 86400)["state"] == "check_needed"


def test_recent_licence_is_not_refreshed_every_launch():
    site = fresh({"token": token("licence", NOW + 60 * 86400), "first_seen": NOW})
    licence.sync(NOW)
    assert site.calls == []


def test_sign_in_flow_and_deactivate():
    good = token("licence", NOW + 60 * 86400)
    fresh(site=FakeSite({"link/start": (200, {"user_code": "K7QD-4MX2", "poll": "p", "url": "u"}),
                         "link/poll": (200, {"token": good}), "licence/deactivate": (200, {"ok": True})}))
    assert licence.link_start()["user_code"] == "K7QD-4MX2"
    assert licence.link_poll("p")[0] == "ok" and licence.status(NOW)["state"] == "licensed"
    assert licence.deactivate()[0] is True
    assert licence.read_token(json.loads(licence._FILE.read_text()).get("token")) is None
    fresh(site=FakeSite({"link/poll": (200, {"pending": True})}))
    assert licence.link_poll("p") == ("pending", "")


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
