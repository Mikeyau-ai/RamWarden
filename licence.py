"""RamWarden's licence: a 14-day trial, then a licence from sixthdaystudios.com.

Stdlib only, like updater.py. The site signs small tokens with its private key; RamWarden
checks them with PUBLIC_KEY below (ed25519.py), so a token can't be forged or edited.
Tokens are tied to this PC (a hash of Windows' MachineGuid, never the raw id).

  - Trial: started by the site on first launch (one per PC, so reinstalling doesn't
    reset it). If the site can't be reached at all, RamWarden allows OFFLINE_GRACE_DAYS from
    the first launch instead.
  - Licence: from a product code, or "Sign in" (the site's /link page approves this PC).
    A licence token lasts 60 days and is refreshed in the background whenever RamWarden is
    online, so it works offline and a refunded/removed licence stops at the next refresh.

Locked (trial over, no licence): RamWarden still scans and shows everything; only the actions
that change the system (kill, trim, startup on/off) ask for a licence. See main.pyw.
"""
import base64
import hashlib
import json
import math
import os
import platform
import time
import urllib.error
import urllib.request

import ed25519
from updater import USER_ROOT

SITE = "https://sixthdaystudios.com"
PRODUCT = "ramwarden"
# The sixthdaystudios.com licence signing key (public half; the private half is a server secret).
PUBLIC_KEY = base64.urlsafe_b64decode("dvVn29Gb2x5o8_00kW65ueD0vC7NU1SYZD_nm14Tu08=")
OFFLINE_GRACE_DAYS = 14          # only used if the site has never been reachable
REFRESH_AFTER_DAYS = 1           # refresh a licence token at most once a day
_FILE = USER_ROOT / "licence.json"
_TIMEOUT = 10


# ── This PC ────────────────────────────────────────────────────────────────────
def device_id():
    """A stable, anonymous id for this PC: a hash of Windows' MachineGuid."""
    guid = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            guid = winreg.QueryValueEx(k, "MachineGuid")[0]
    except OSError:
        guid = platform.node()          # not Windows, or no access: still stable per PC
    return hashlib.sha256(f"sixthdaystudios:{guid}".encode()).hexdigest()[:32]


def device_name():
    """The PC's name, shown on the person's "Your apps" page so they can tell PCs apart."""
    return (os.environ.get("COMPUTERNAME") or platform.node() or "PC")[:60]


# ── Local file ─────────────────────────────────────────────────────────────────
def _load():
    """The saved licence state: {"token", "first_seen", "trial_over"}."""
    try:
        with open(_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if "first_seen" not in data:
        data["first_seen"] = time.time()
        _save(data)
    return data


def _save(data):
    """Write the licence state (failures are ignored: worst case we ask the site again)."""
    try:
        USER_ROOT.mkdir(parents=True, exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass


# ── Tokens ─────────────────────────────────────────────────────────────────────
def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def read_token(token):
    """The payload of a genuine token for this product and this PC (expired or not), else None."""
    try:
        body, sig = token.split(".")
        if not ed25519.verify(PUBLIC_KEY, body.encode(), _unb64(sig)):
            return None
        p = json.loads(_unb64(body))
    except (AttributeError, ValueError, TypeError):
        return None
    return p if p.get("p") == PRODUCT and p.get("d") == device_id() else None


def status(now=None):
    """Where this PC stands: {"state", "days_left"}.

    state: licensed | trial | trial_over | check_needed (licence older than 60 days offline,
    or the site never reached and the offline grace is over). Actions are allowed only for
    licensed and trial."""
    now = now or time.time()
    data = _load()
    p = read_token(data.get("token"))
    # Whole days left, rounded up; the small allowance absorbs clock differences with the server.
    days = lambda until: max(0, math.ceil((until - now) / 86400 - 0.01))
    if p and p.get("k") == "licence":
        return {"state": "licensed", "days_left": days(p["exp"])} if p["exp"] > now else {"state": "check_needed", "days_left": 0}
    if p and p.get("k") == "trial" and p["exp"] > now:
        return {"state": "trial", "days_left": days(p["exp"])}
    if data.get("trial_over") or (p and p.get("k") == "trial"):
        return {"state": "trial_over", "days_left": 0}
    grace_end = data["first_seen"] + OFFLINE_GRACE_DAYS * 86400
    if grace_end > now:
        return {"state": "trial", "days_left": days(grace_end)}
    return {"state": "check_needed", "days_left": 0}


def allowed(now=None):
    """True when the licence/trial lets RamWarden change the system (end processes, trim, startup)."""
    return status(now)["state"] in ("licensed", "trial")


# ── Talking to the site ────────────────────────────────────────────────────────
def _post(path, body):
    """POST JSON to the site; (http status, reply dict), or (None, {}) when offline."""
    req = urllib.request.Request(f"{SITE}/api/{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "RamWarden-Licence"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return None, {}


def _app_body(**extra):
    """The fields every app request carries."""
    return {"product": PRODUCT, "device": device_id(), "name": device_name(), **extra}


def _keep(token):
    """Save a fresh token from the site (only if it's genuine and for this PC)."""
    if not read_token(token):
        return False
    data = _load()
    data["token"] = token
    _save(data)
    return True


def sync(now=None):
    """Background check at launch: refresh a licence, or start/read the trial. Never raises;
    does nothing when offline (the saved token keeps working until it expires)."""
    now = now or time.time()
    data = _load()
    p = read_token(data.get("token"))
    if p and p.get("k") == "licence":
        if now - p.get("iat", 0) < REFRESH_AFTER_DAYS * 86400:
            return
        code, r = _post("licence/refresh", {"token": data["token"]})
        if code is None:
            return
        if r.get("token") and _keep(r["token"]):
            return
        if code == 403:                      # removed from this PC, revoked or refunded
            data["token"] = None
            _save(data)
        else:
            return
    code, r = _post("licence/trial", _app_body())
    if r.get("token"):
        _keep(r["token"])
    elif r.get("expired"):
        data = _load()
        data["trial_over"], data["token"] = True, None
        _save(data)


def activate_code(code):
    """Redeem a product code on this PC: (True, message) or (False, why not)."""
    status_code, r = _post("licence/activate", _app_body(code=code))
    if status_code is None:
        return False, "Couldn't reach sixthdaystudios.com. Check your internet connection and try again."
    if r.get("token") and _keep(r["token"]):
        return True, "Activated. Thanks for supporting RamWarden!"
    return False, r.get("error") or "That didn't work. Please try again."


def link_start():
    """Begin "Sign in": {"user_code", "poll", "url"} or {"error"}."""
    status_code, r = _post("link/start", _app_body())
    if status_code is None:
        return {"error": "Couldn't reach sixthdaystudios.com. Check your internet connection and try again."}
    return r if r.get("user_code") else {"error": r.get("error") or "That didn't work. Please try again."}


def link_poll(poll):
    """Check a "Sign in" request: ("pending", ""), ("ok", message) or ("error", message)."""
    status_code, r = _post("link/poll", {"poll": poll})
    if status_code is None or r.get("pending"):
        return "pending", ""                 # offline blips just mean "keep waiting"
    if r.get("token") and _keep(r["token"]):
        return "ok", "Signed in and activated. Thanks for supporting RamWarden!"
    return "error", r.get("error") or "That didn't work. Please try again."


def deactivate():
    """Free this PC's licence slot (to move RamWarden to another PC): (True, msg) or (False, why)."""
    data = _load()
    if not read_token(data.get("token")):
        return False, "This PC isn't activated."
    status_code, r = _post("licence/deactivate", {"token": data["token"]})
    if status_code is None:
        return False, "Couldn't reach sixthdaystudios.com, so this PC is still activated. Try again when online."
    if not r.get("ok"):
        return False, r.get("error") or "That didn't work. Please try again."
    data["token"] = None
    _save(data)
    return True, "This PC is deactivated, and its slot is free for another PC."
