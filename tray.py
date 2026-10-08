"""
tray.py — RamWarden's notification-area (tray) icon: live RAM % with a right-click menu.

Built on the Windows API through ctypes (no extra packages). The icon lives on its own thread
with a hidden window and message loop; the Tk side never touches it directly. Instead:
  - Tk -> tray: update(), notify(), stop() post a message to the tray thread.
  - tray -> Tk: clicks and menu choices go into `events` (a queue) that Tk polls.

Events put on the queue: 'open', 'exit', 'autostart'. A second copy of RamWarden calls
show_running_copy() to bring this one forward (open_message).
"""
import ctypes
import queue
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

CLASS_NAME = 'RamWardenTray'
WM_APP = 0x8000
WM_TRAY = WM_APP + 1        # the icon's mouse events
WM_REFRESH = WM_APP + 2     # Tk changed the figure or tooltip
WM_OPEN = WM_APP + 3        # another copy of RamWarden asks this one to show itself
WM_BALLOON = WM_APP + 4     # Tk wants a one-off notification shown
WM_CLOSE, WM_DESTROY, WM_NULL = 0x0010, 0x0002, 0x0000
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
MENU_OPEN, MENU_AUTOSTART, MENU_EXIT = 1, 2, 3


class WNDCLASSW(ctypes.Structure):
    _fields_ = [('style', wintypes.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE), ('hIcon', wintypes.HICON),
                ('hCursor', wintypes.HANDLE), ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR), ('lpszClassName', wintypes.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('hWnd', wintypes.HWND), ('uID', wintypes.UINT),
                ('uFlags', wintypes.UINT), ('uCallbackMessage', wintypes.UINT), ('hIcon', wintypes.HICON),
                ('szTip', wintypes.WCHAR * 128), ('dwState', wintypes.DWORD), ('dwStateMask', wintypes.DWORD),
                ('szInfo', wintypes.WCHAR * 256), ('uVersion', wintypes.UINT), ('szInfoTitle', wintypes.WCHAR * 64),
                ('dwInfoFlags', wintypes.DWORD), ('guidItem', ctypes.c_byte * 16), ('hBalloonIcon', wintypes.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD), ('yHotspot', wintypes.DWORD),
                ('hbmMask', wintypes.HBITMAP), ('hbmColor', wintypes.HBITMAP)]


# Pointer-sized arguments and results must be declared, or 64-bit handles get cut to 32 bits.
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.LPVOID]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.ChangeWindowMessageFilterEx.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.DWORD, wintypes.LPVOID]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, wintypes.LPVOID]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

# ── Drawing the figure ───────────────────────────────────────────────────────────────────────
# A 3×5 pixel font for the digits, scaled up to the icon size, so the number is crisp at any
# size without needing a font (each string is one row, '#' = lit).
DIGITS = {
    '0': ('###', '#.#', '#.#', '#.#', '###'), '1': ('.#.', '##.', '.#.', '.#.', '###'),
    '2': ('###', '..#', '###', '#..', '###'), '3': ('###', '..#', '###', '..#', '###'),
    '4': ('#.#', '#.#', '###', '..#', '..#'), '5': ('###', '#..', '###', '..#', '###'),
    '6': ('###', '#..', '###', '#.#', '###'), '7': ('###', '..#', '..#', '..#', '..#'),
    '8': ('###', '#.#', '###', '#.#', '###'), '9': ('###', '#.#', '###', '..#', '###'),
}


def colours(percent):
    """(tile, digits) as (r, g, b) for a RAM %: teal, then amber from 60 %, red from 85 %
    (the same steps as the RAM bar in the window)."""
    if percent >= 85:
        return (0xe0, 0x52, 0x52), (0xff, 0xff, 0xff)
    if percent >= 60:
        return (0xe0, 0xa0, 0x40), (0x10, 0x14, 0x18)
    return (0x2c, 0xc4, 0xa8), (0x0b, 0x1a, 0x1a)


def render(percent, size):
    """The icon's pixels: size×size, top row first, 4 bytes (B, G, R, A) each. The RAM % (shown
    up to 99) in big digits on a tile coloured by how full RAM is."""
    text = str(max(0, min(99, int(round(percent)))))
    tile, ink = colours(percent)
    scale = max(1, size // 8)
    width = (len(text) * 4 - 1) * scale          # 3 px per digit plus a 1 px gap, scaled
    left, top = (size - width) // 2, (size - 5 * scale) // 2
    lit = set()
    for i, ch in enumerate(text):
        for row, bits in enumerate(DIGITS[ch]):
            for col, bit in enumerate(bits):
                if bit == '#':
                    x0, y0 = left + (i * 4 + col) * scale, top + row * scale
                    lit.update((x0 + dx, y0 + dy) for dx in range(scale) for dy in range(scale))
    out = bytearray()
    radius = max(1, size // 8)                   # rounded corners: leave the corner pixels clear
    for y in range(size):
        for x in range(size):
            cx = min(x, size - 1 - x)
            cy = min(y, size - 1 - y)
            corner = cx < radius and cy < radius and (radius - cx) ** 2 + (radius - cy) ** 2 > radius ** 2
            if corner:
                out += b'\x00\x00\x00\x00'
            else:
                r, g, b = ink if (x, y) in lit else tile
                out += bytes((b, g, r, 255))
    return bytes(out)


def _make_icon(percent, size):
    """An HICON of render(percent, size). The caller destroys it."""
    bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=size, biHeight=-size,
                           biPlanes=1, biBitCount=32, biCompression=0)
    bits = ctypes.c_void_p()
    colour = gdi32.CreateDIBSection(None, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    pixels = render(percent, size)
    ctypes.memmove(bits, pixels, len(pixels))
    # The 1-bit mask is unused for a 32-bit icon with alpha, but must exist; rows are WORD-aligned.
    mask = gdi32.CreateBitmap(size, size, 1, 1, ctypes.create_string_buffer((size + 15) // 16 * 2 * size))
    info = ICONINFO(fIcon=True, hbmMask=mask, hbmColor=colour)
    icon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(colour)
    gdi32.DeleteObject(mask)
    return icon


# ── The icon itself ──────────────────────────────────────────────────────────────────────────
class Tray:
    """The tray icon, running on its own thread. Tk reads `events`; everything else is a call."""

    def __init__(self, tip="RamWarden"):
        self.events = queue.Queue()
        self.autostart_checked = False   # shown as the menu's tick; Tk keeps it current
        self._percent, self._tip = 0.0, tip
        self._balloon = ('', '')
        self._hwnd = None
        self._icon = None
        self._ready = threading.Event()
        self._proc = WNDPROC(self._wndproc)   # kept referenced: Windows calls it for the window's life
        self._thread = threading.Thread(target=self._run, name='tray', daemon=True)
        self._thread.start()
        self._ready.wait(5)
        if not self._hwnd:
            raise OSError("The tray icon couldn't be created.")

    # Called from the Tk thread.
    def update(self, percent, tip):
        """Show a new RAM % and hover text."""
        self._percent, self._tip = percent, tip[:127]
        user32.PostMessageW(self._hwnd, WM_REFRESH, 0, 0)

    def notify(self, title, text):
        """A one-off Windows notification from the icon."""
        self._balloon = (title[:63], text[:255])
        user32.PostMessageW(self._hwnd, WM_BALLOON, 0, 0)

    def stop(self):
        """Remove the icon and end its thread."""
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            self._thread.join(2)

    # The tray thread.
    def _run(self):
        """Create the hidden window and icon, then pump its messages until stop()."""
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName=CLASS_NAME)
        user32.RegisterClassW(ctypes.byref(wc))        # fails harmlessly if already registered
        self._hwnd = user32.CreateWindowExW(0, CLASS_NAME, 'RamWarden tray', 0, 0, 0, 0, 0,
                                            None, None, hinst, None)
        if not self._hwnd:
            self._ready.set()
            return
        self._taskbar_created = user32.RegisterWindowMessageW('TaskbarCreated')
        # Let a normal copy reach an elevated one, and Explorer's restart notice through too.
        for msg in (WM_OPEN, self._taskbar_created):
            user32.ChangeWindowMessageFilterEx(self._hwnd, msg, 1, None)   # 1 = MSGFLT_ALLOW
        self._notify(NIM_ADD)
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _notify(self, action, balloon=False):
        """Add or refresh the icon (with a fresh picture of the current %)."""
        size = user32.GetSystemMetrics(49) or 16      # SM_CXSMICON: the tray's icon size at this DPI
        old, self._icon = self._icon, _make_icon(self._percent, size)
        nid = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self._hwnd, uID=1,
                              uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP, uCallbackMessage=WM_TRAY,
                              hIcon=self._icon, szTip=self._tip)
        if balloon:
            nid.uFlags |= NIF_INFO
            nid.szInfoTitle, nid.szInfo = self._balloon
            nid.dwInfoFlags = 0x1                       # NIIF_INFO
        shell32.Shell_NotifyIconW(action, ctypes.byref(nid))
        if old:
            user32.DestroyIcon(old)

    def _menu(self):
        """The right-click menu; its choice goes on the events queue."""
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, 0, MENU_OPEN, 'Open RamWarden')
        user32.AppendMenuW(menu, 0x8 if self.autostart_checked else 0, MENU_AUTOSTART, 'Start with Windows')
        user32.AppendMenuW(menu, 0x800, 0, None)                      # separator
        user32.AppendMenuW(menu, 0, MENU_EXIT, 'Exit')
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self._hwnd)          # else the menu won't close on a click elsewhere
        choice = user32.TrackPopupMenu(menu, 0x100 | 0x80 | 0x2, pt.x, pt.y, 0, self._hwnd, None)
        user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        event = {MENU_OPEN: 'open', MENU_AUTOSTART: 'autostart', MENU_EXIT: 'exit'}.get(choice)
        if event:
            self.events.put(event)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """The hidden window's messages: icon clicks, refreshes, and shutting down."""
        if msg == WM_TRAY:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.events.put('open')
            elif lparam == WM_RBUTTONUP:
                self._menu()
            return 0
        if msg == WM_REFRESH:
            self._notify(NIM_MODIFY)
            return 0
        if msg == WM_BALLOON:
            self._notify(NIM_MODIFY, balloon=True)
            return 0
        if msg == WM_OPEN:
            self.events.put('open')
            return 0
        if msg == getattr(self, '_taskbar_created', -1):   # Explorer restarted: the icon was lost
            self._notify(NIM_ADD)
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            nid = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=hwnd, uID=1)
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            if self._icon:
                user32.DestroyIcon(self._icon)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def show_running_copy():
    """Ask an already-running RamWarden (perhaps hidden in the tray) to show its window.
    True when there was one to ask."""
    hwnd = user32.FindWindowW(CLASS_NAME, None)
    if not hwnd:
        return False
    return bool(user32.PostMessageW(hwnd, WM_OPEN, 0, 0))
