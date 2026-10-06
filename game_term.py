"""
game_term.py — Terminal size detection and adaptive centred layout.

Every piece of UI uses C() to print centred text.
C(text) prepends the correct left-padding so the content sits in the
middle of whatever terminal the player is using — 60 wide, 220 wide, anything.

Usage:
    from game_term import C, W, H, div, clr

    C("Hello world")          # prints centred
    print(C(f"HP: {hp}"))     # use inside f-strings / print calls
    div()                     # full-width divider centred
    W()                       # current terminal width
    H()                       # current terminal height
"""

import os, sys, shutil

# ── Windows: enable ANSI / VT escape processing ─────────────────
# Every screen in the game uses 24-bit colour escape codes. Classic
# Windows consoles only interpret them once VT processing is switched
# on for the console handle.
def _enable_vt():
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        os.system("")   # well-known fallback that also enables VT mode

_enable_vt()

# Make sure box-drawing / emoji output never crashes on legacy code pages
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# ── Size detection ──────────────────────────────────────────────
def _sz():
    try:
        s = shutil.get_terminal_size(fallback=(120, 36))
        return max(60, s.columns), max(20, s.lines)
    except Exception:
        return 120, 36

def W() -> int:
    """Current terminal width in columns."""
    return _sz()[0]

def H() -> int:
    """Current terminal height in lines."""
    return _sz()[1]


# ── ANSI helpers ────────────────────────────────────────────────
import re as _re
_ANSI = _re.compile(r'\x1b\[[0-9;]*m')

def _vis(s: str) -> int:
    """Visible (non-ANSI) character length of a string."""
    return len(_ANSI.sub('', s))


# ── Content width ───────────────────────────────────────────────
# UI content is never wider than this many visible chars.
# Keeps things readable on ultra-wide terminals.
MAX_CONTENT = 120

def _content_w() -> int:
    return min(W(), MAX_CONTENT)

def _pad() -> int:
    """Left padding to centre MAX_CONTENT in the current terminal."""
    return max(0, (W() - _content_w()) // 2)


# ── Core centring function ──────────────────────────────────────
def C(text: str = "", extra_indent: int = 0) -> str:
    """
    Return text prefixed with enough spaces to centre it in the terminal.
    Handles embedded newlines — each line gets its own padding prefix.
    extra_indent: additional spaces on top of the base centring pad.
    Works with ANSI colour codes — measures visible width correctly.
    """
    prefix = " " * (_pad() + extra_indent)
    if "\n" not in text:
        return prefix + text
    # Pad each line individually; blank lines stay blank
    parts = text.split("\n")
    return "\n".join(prefix + p if p.strip() else p for p in parts)


def P(n: int = 0) -> str:
    """Return just the padding string (no text). n = extra indent."""
    return " " * (_pad() + n)


# ── Divider ─────────────────────────────────────────────────────
_DIM  = "\033[38;2;90;90;100m"
_R    = "\033[0m"
_B    = "\033[1m"
_GOLD = "\033[38;2;255;215;0m"
_CYAN = "\033[38;2;80;220;220m"

def div(char: str = "─", colour: str = _DIM, width: int = 0) -> str:
    """A divider line, centred. width=0 means fill content width."""
    w = width or _content_w()
    return C(f"{colour}{char*w}{_R}")


# ── Clear ───────────────────────────────────────────────────────
def clr():
    """Clear the screen with ANSI codes (much faster than spawning cls/clear)."""
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()

def home():
    """Move the cursor to the top-left without clearing (flicker-free redraws)."""
    sys.stdout.write("\033[H")

def draw_frame(lines, end_cursor=""):
    """
    Redraw a whole screen in one write: cursor home, each line followed by
    erase-to-end-of-line, then erase everything below. No flicker.
    """
    out = ["\033[H"]
    for ln in lines:
        out.append(ln + "\033[K\n")
    out.append("\033[J")
    out.append(end_cursor)
    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ── Box drawing ─────────────────────────────────────────────────
def box_top(title: str = "", width: int = 0, colour: str = _GOLD) -> str:
    w = width or min(_content_w(), 56)
    if title:
        pad_each = max(1, (w - len(title) - 2) // 2)
        inner = f"{'═'*pad_each}  {title}  {'═'*pad_each}"
        inner = inner[:w]
    else:
        inner = "═" * w
    return C(f"{colour}{_B}╔{inner}╗{_R}")

def box_mid(text: str, width: int = 0, colour: str = _GOLD) -> str:
    w = width or min(_content_w(), 56)
    vis = _vis(text)
    padded = text + " " * max(0, w - vis - 2)
    return C(f"{colour}{_B}║{_R} {padded}{colour}{_B}║{_R}")

def box_bot(width: int = 0, colour: str = _GOLD) -> str:
    w = width or min(_content_w(), 56)
    return C(f"{colour}{_B}╚{'═'*w}╝{_R}")


# ── Adaptive bar helpers ─────────────────────────────────────────
def hpbar(cur, mx, width: int = 0) -> str:
    w = width or max(10, min(20, _content_w() // 5))
    frac = cur / mx if mx else 0
    f = int(w * frac)
    col = ("\033[38;2;80;200;80m" if frac > .5 else
           "\033[38;2;240;200;60m" if frac > .25 else "\033[38;2;220;60;60m")
    dim = "\033[38;2;90;90;100m"
    return f"[{col}{'█'*f}{dim}{'░'*(w-f)}{_R}] {col}{cur}/{mx}{_R}"

def mpbar(cur, mx, width: int = 0) -> str:
    w = width or max(6, min(12, _content_w() // 8))
    frac = cur / mx if mx else 0
    f = int(w * frac)
    blue = "\033[38;2;80;130;220m"
    dim  = "\033[38;2;90;90;100m"
    return f"[{blue}{'█'*f}{dim}{'░'*(w-f)}{_R}] {blue}{cur}/{mx}{_R}"


# ── Map viewport size ───────────────────────────────────────────
def view_dims(hud_rows: int = 9):
    """(view_w, view_h) for the world map — fills available terminal space."""
    cols, rows = _sz()
    view_h = max(8,  min(rows - hud_rows, 120))
    view_w = max(20, min(cols - 2, 320))
    return view_w, view_h

def map_pad(view_w: int) -> str:
    """Left-padding prefix for map rows."""
    cols = W()
    return " " * max(0, (cols - view_w) // 2)

# Backwards-compatibility alias
get_size = _sz
