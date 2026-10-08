"""
whatis.py — "What is this?": a plain-English line about a process and whether it's safe to end.

Common Windows and app processes have a hand-written explanation (KNOWN). Anything else is
described from its program file's own details (description and publisher, the same ones
Explorer shows under Properties > Details) and where it lives. No tkinter dependency.
"""
import ctypes
import os
from ctypes import wintypes

# Advice wording, so the same situation always reads the same way.
LEAVE = "Leave it running: it's part of Windows."
CORE = "Windows won't let anything end it; the PC would crash."
SECURITY = "Leave it running: it's your antivirus, and it protects itself from being ended."
SAFE = "Safe to end; it starts again by itself when needed."

def _part_of(what):
    """Advice for a helper that belongs to a driver or Windows feature."""
    return f"Leave it running: it's part of {what}."

def _app(what):
    """Advice for an ordinary app: ending it just closes it."""
    return "Safe to end, but it closes " + what + " (unsaved work is lost)."

# name → (what it is, advice). Names are lower case.
KNOWN = {
    # Windows' core: can't be ended.
    'system': ("The Windows kernel: the core of Windows itself.", CORE),
    'registry': ("Holds Windows' settings database (the registry) in memory.", CORE),
    'memory compression': ("Windows squeezing idle memory so less goes to disk. Its size is a good sign, not a leak.", CORE),
    'secure system': ("Windows' protected security area (virtualisation-based security).", CORE),
    'smss.exe': ("Session Manager: starts your Windows session at sign-in.", CORE),
    'csrss.exe': ("Client/Server Runtime: runs the console and part of the desktop.", CORE),
    'wininit.exe': ("Windows Start-Up: launches Windows' background services.", CORE),
    'winlogon.exe': ("Handles signing in, signing out and the lock screen.", CORE),
    'services.exe': ("Starts and stops Windows' background services.", CORE),
    'lsass.exe': ("Local Security Authority: checks passwords and sign-ins.", CORE),
    'dwm.exe': ("Desktop Window Manager: draws everything you see on screen.", CORE),
    'fontdrvhost.exe': ("Font driver host: draws text safely for Windows.", CORE),
    # Windows, safe to leave and usually pointless to end.
    'svchost.exe': ("Service Host: runs Windows' background services, many copies at once. That's normal.", LEAVE),
    'explorer.exe': ("Windows Explorer: the taskbar, Start menu, desktop and folders.",
                     "Ending it makes the taskbar vanish for a moment; it usually restarts by itself. Sometimes fixes a stuck taskbar."),
    'runtimebroker.exe': ("Runtime Broker: checks permissions for Store apps (camera, location…).", SAFE),
    'conhost.exe': ("Console Window Host: one comes with every command-line window or tool.", SAFE),
    'dllhost.exe': ("COM Surrogate: runs bits of other programs, such as making thumbnails.", SAFE),
    'taskhostw.exe': ("Task Host: runs Windows' scheduled background tasks.", LEAVE),
    'sihost.exe': ("Shell Infrastructure Host: part of the Start menu, notifications and wallpaper.", LEAVE),
    'ctfmon.exe': ("Text input: the keyboard layout, touch keyboard and handwriting.",
                   "Leave it running: typing in some apps stops working without it."),
    'audiodg.exe': ("Windows Audio: mixes the sound from every app.", "Ending it cuts the sound briefly; it restarts by itself."),
    'searchindexer.exe': ("Windows Search indexer: keeps the file search fast.", LEAVE),
    'searchhost.exe': ("The Start menu's search box.", SAFE),
    'searchprotocolhost.exe': ("Part of Windows Search: reads files for the index.", SAFE),
    'searchfilterhost.exe': ("Part of Windows Search: reads files for the index.", SAFE),
    'startmenuexperiencehost.exe': ("The Start menu.", SAFE),
    'shellexperiencehost.exe': ("Taskbar pop-ups: the clock, calendar, volume and network flyouts.", SAFE),
    'textinputhost.exe': ("The touch keyboard, emoji panel and voice typing.", SAFE),
    'applicationframehost.exe': ("Draws the window frames of Store apps (Settings, Calculator…).", LEAVE),
    'systemsettings.exe': ("The Settings app.", _app("Settings")),
    'systemsettingsbroker.exe': ("Helps the Settings app make changes.", SAFE),
    'backgroundtaskhost.exe': ("Runs background jobs for Store apps.", SAFE),
    'wudfhost.exe': ("Windows driver host: runs drivers for devices like fingerprint readers and phones.", LEAVE),
    'spoolsv.exe': ("Print Spooler: sends documents to printers.", "Safe to end if you're not printing; it restarts with Windows."),
    'wlanext.exe': ("Wi-Fi helper for your wireless network card.", LEAVE),
    'usocoreworker.exe': ("Windows Update: checking for or installing updates.", "Best left to finish."),
    'msiexec.exe': ("Windows Installer: installing, repairing or removing a program.", "Leave it to finish, or a program may be left half installed."),
    'rundll32.exe': ("Runs part of another program (a DLL). What it's doing depends on that program.", "Look at its location or command before ending it."),
    'wermgr.exe': ("Windows Error Reporting: collecting details after something crashed.", SAFE),
    'smartscreen.exe': ("Microsoft Defender SmartScreen: checks downloads and apps for danger.", LEAVE),
    'securityhealthservice.exe': ("Windows Security's background service.", SECURITY),
    'securityhealthsystray.exe': ("Windows Security's taskbar icon.", SECURITY),
    'msmpeng.exe': ("Microsoft Defender Antivirus: scanning for viruses. High use during a scan is normal.", SECURITY),
    'nissrv.exe': ("Microsoft Defender's network protection.", SECURITY),
    'mpdefendercoreservice.exe': ("Microsoft Defender's core service.", SECURITY),
    'lsaiso.exe': ("Credential Guard: keeps sign-in secrets isolated.", CORE),
    'phoneexperiencehost.exe': ("Phone Link: connects your phone to the PC.", _app("Phone Link")),
    'widgets.exe': ("The Widgets board (news, weather) on the taskbar.", SAFE),
    'msedgewebview2.exe': ("Edge WebView2: a built-in browser other apps use to show their screens (Widgets, Teams, Outlook…).",
                           "Ending it can break the app that uses it; close that app instead."),
    'onedrive.exe': ("Microsoft OneDrive: syncs your files to the cloud.", "Safe to end; files stop syncing until it starts again."),
    'msedge.exe': ("Microsoft Edge, the web browser. Each tab and extension gets its own copy.", _app("Edge")),
    'chrome.exe': ("Google Chrome, the web browser. Each tab and extension gets its own copy.", _app("Chrome")),
    'firefox.exe': ("Mozilla Firefox, the web browser. Tabs share several copies.", _app("Firefox")),
    'brave.exe': ("Brave, the web browser. Each tab and extension gets its own copy.", _app("Brave")),
    'opera.exe': ("Opera, the web browser.", _app("Opera")),
    'discord.exe': ("Discord, the voice and chat app.", _app("Discord")),
    'steam.exe': ("Steam, the game store and launcher.", _app("Steam")),
    'steamwebhelper.exe': ("Steam's built-in browser that draws the Steam window.", "Ending it closes or breaks the Steam window."),
    'epicgameslauncher.exe': ("The Epic Games launcher.", _app("Epic Games")),
    'spotify.exe': ("Spotify, the music app.", _app("Spotify")),
    'ms-teams.exe': ("Microsoft Teams.", _app("Teams")),
    'teams.exe': ("Microsoft Teams (classic).", _app("Teams")),
    'outlook.exe': ("Microsoft Outlook, email and calendar.", _app("Outlook")),
    'olk.exe': ("The new Outlook, email and calendar.", _app("Outlook")),
    'winword.exe': ("Microsoft Word.", _app("Word")),
    'excel.exe': ("Microsoft Excel.", _app("Excel")),
    'powerpnt.exe': ("Microsoft PowerPoint.", _app("PowerPoint")),
    'zoom.exe': ("Zoom, video calls.", _app("Zoom")),
    'slack.exe': ("Slack, team chat.", _app("Slack")),
    'code.exe': ("Visual Studio Code, the code editor.", _app("VS Code")),
    'nvcontainer.exe': ("NVIDIA Container: runs NVIDIA's graphics-card helpers (the overlay, settings, updates).",
                        "Safe to end, but NVIDIA's overlay and settings stop working until it restarts."),
    'nvdisplay.container.exe': ("NVIDIA Display Container: runs the NVIDIA Control Panel and display settings.", _part_of("your NVIDIA graphics driver")),
    'nvidia overlay.exe': ("NVIDIA's in-game overlay (screenshots, recording, performance stats).", SAFE),
    'radeonsoftware.exe': ("AMD Software: Radeon graphics settings.", "Safe to end; graphics keep working, only the settings app closes."),
    'amdrsserv.exe': ("AMD Radeon Software's background service.", "Safe to end; graphics keep working."),
    'igfxem.exe': ("Intel graphics helper (screen hotkeys and display changes).", SAFE),
    'realtekaudioservice.exe': ("Realtek audio helper for your sound card.", _part_of("your sound driver")),
    'rtkauduservice64.exe': ("Realtek audio helper for your sound card.", _part_of("your sound driver")),
    'python.exe': ("Python: runs a Python program (with a window).", "Ending it stops that program."),
    'pythonw.exe': ("Python: runs a Python program (without a window). RamWarden itself runs this way from source.", "Ending it stops that program."),
    'node.exe': ("Node.js: runs a JavaScript program, often a developer tool.", "Ending it stops that program."),
    'java.exe': ("Java: runs a Java program (Minecraft and others).", "Ending it stops that program."),
    'javaw.exe': ("Java: runs a Java program without a window (Minecraft and others).", "Ending it stops that program."),
    'ramwarden.exe': ("RamWarden: this app.", "Ending it closes RamWarden."),
}


def _version_strings(path):
    """{'FileDescription': …, 'CompanyName': …} from a program file's version details, {} if none."""
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return {}
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, buf):
        return {}
    ptr, length = ctypes.c_void_p(), wintypes.UINT()
    # The language/code-page pairs the strings are stored under; try each, then US English.
    pairs = []
    if ver.VerQueryValueW(buf, r'\VarFileInfo\Translation', ctypes.byref(ptr), ctypes.byref(length)) and length.value >= 4:
        words = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ushort * (length.value // 2))).contents
        pairs = [f'{words[i]:04x}{words[i + 1]:04x}' for i in range(0, len(words) - 1, 2)]
    pairs += ['040904b0', '040904e4']
    out = {}
    for field in ('FileDescription', 'CompanyName'):
        for pair in pairs:
            if ver.VerQueryValueW(buf, f'\\StringFileInfo\\{pair}\\{field}', ctypes.byref(ptr), ctypes.byref(length)) and length.value:
                text = ctypes.wstring_at(ptr, length.value).rstrip('\x00').strip()
                if text:
                    out[field] = text
                    break
    return out


def file_details(path):
    """(description, publisher) for a program file; empty strings when it has none or can't be read."""
    if not path:
        return '', ''
    try:
        info = _version_strings(path)
    except (OSError, AttributeError, ValueError):
        return '', ''
    return info.get('FileDescription', ''), info.get('CompanyName', '')


def explain(name, path=''):
    """{'what', 'advice', 'publisher', 'path'} about a process, in plain English."""
    key = (name or '').lower()
    description, publisher = file_details(path)
    if key in KNOWN:
        what, advice = KNOWN[key]
    else:
        what = (description + '.') if description and not description.endswith('.') else description
        windir = os.path.normcase(os.environ.get('WINDIR', r'C:\Windows'))
        if path and os.path.normcase(path).startswith(windir + os.sep):
            what = what or "Part of Windows."
            advice = "It's part of Windows. Usually best left alone unless it's misbehaving."
        else:
            what = what or "RamWarden doesn't know this one, and the program doesn't describe itself."
            advice = ("Ending it closes whatever it belongs to (unsaved work is lost). "
                      "If you don't recognise it, search its name and publisher first.")
    return {'what': what, 'advice': advice, 'publisher': publisher, 'path': path or ''}


def as_text(name, info):
    """The explanation as a few short paragraphs for a message box."""
    parts = [info['what'], info['advice']]
    if info['publisher']:
        parts.append(f"Publisher: {info['publisher']}")
    if info['path']:
        parts.append(f"Location: {info['path']}")
    return "\n\n".join(p for p in parts if p)
