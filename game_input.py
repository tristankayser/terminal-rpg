"""
input_handler.py — Cross-platform raw terminal input for Terminal-RPG.

Strategy (in order of preference):
  1. Windows: msvcrt.getch()  — always works in a real Windows terminal
  2. Unix/Mac: open /dev/tty directly — works even if stdin is piped
  3. Unix/Mac: termios on stdin — works when stdin is a real tty
  4. Fallback: regular input() taking first character — always works,
     just requires Enter.  A warning is printed once.

This means the game ALWAYS works, even in unusual setups.
On a normal terminal (which is the expected use case) options 1–3 apply
and keypresses are instant with no Enter needed.
"""

import os, sys

# ── Movement maps ────────────────────────────────────────────────

WASD_MAP = {
    'w': (0,-1), 's': (0,1), 'a': (-1,0), 'd': (1,0),
    'W': (0,-1), 'S': (0,1), 'A': (-1,0), 'D': (1,0),
}

# 8-dir numpad layout (7=NW 8=N 9=NE / 4=W 6=E / 1=SW 2=S 3=SE)
# Digits only — vi-keys (hjklyubn) used to shadow the J/B/N commands
# (journal, base, party) so those menus were unreachable in this mode.
NUMPAD_MAP = {
    '8':(0,-1),  '2':(0,1),   '4':(-1,0),  '6':(1,0),
    '7':(-1,-1), '9':(1,-1),  '1':(-1,1),  '3':(1,1),
}

ARROW_MAP = {
    'arrow_up':(0,-1), 'arrow_down':(0,1),
    'arrow_left':(-1,0), 'arrow_right':(1,0),
}

DIAG_MAP = {
    'diag_nw':(-1,-1), 'diag_ne':(1,-1),
    'diag_sw':(-1,1),  'diag_se':(1,1),
}

CMD_MAP = {
    'e':'enter', 'E':'enter',
    'f':'fast',  'F':'fast',
    'o':'overview','O':'overview',
    'm':'map',   'M':'map',
    '?':'help',
    'q':'quit',  'Q':'quit',
    'p':'save',  'P':'save',
    'j':'journal','J':'journal',
    'b':'base',   'B':'base',
    'i':'inventory','I':'inventory',
    'c':'codex',   'C':'codex',
    'n':'party',  'N':'party',
    '\x1b':'quit',   # Escape key
    '\x03':'quit',   # Ctrl-C
    '\x04':'quit',   # Ctrl-D
    '\x13':'save',   # Ctrl-S
}

# ── Low-level single-char readers ────────────────────────────────

def _read_raw_unix(stream):
    """Read one raw keypress from a Unix stream. Returns char or arrow string."""
    import tty, termios
    fd = stream.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = stream.read(1)
        if ch == '\x1b':
            # Try to read escape sequence (arrow keys etc.)
            # setraw + non-blocking peek
            import select
            r, _, _ = select.select([stream], [], [], 0.05)
            if r:
                ch2 = stream.read(1)
                if ch2 == '[':
                    r2, _, _ = select.select([stream], [], [], 0.05)
                    if r2:
                        ch3 = stream.read(1)
                        return {'A':'arrow_up','B':'arrow_down',
                                'C':'arrow_right','D':'arrow_left'}.get(ch3, '\x1b')
            return '\x1b'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        # Flush any pending input so it doesn't echo to next render
        try:
            import termios as _t
            _t.tcflush(fd, _t.TCIFLUSH)
        except Exception:
            pass


def _getch():
    """
    Read a single keypress without needing Enter.
    Returns a character string or one of the arrow_* strings.
    Raises RuntimeError if raw input is completely unavailable.
    """
    # ── Windows ──────────────────────────────────────────────────
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):     # special key prefix
            ch2 = msvcrt.getwch()
            # Numpad with NumLock off: Home/PgUp/End/PgDn act as diagonals
            return {'H':'arrow_up','P':'arrow_down',
                    'M':'arrow_right','K':'arrow_left',
                    'G':'diag_nw','I':'diag_ne',
                    'O':'diag_sw','Q':'diag_se'}.get(ch2, '')
        return ch

    # ── Unix / Mac — try /dev/tty first ──────────────────────────
    try:
        tty_stream = open('/dev/tty', 'r')
        try:
            return _read_raw_unix(tty_stream)
        finally:
            tty_stream.close()
    except Exception:
        pass

    # ── Unix — fall back to stdin if it's a real tty ──────────────
    try:
        if sys.stdin.isatty():
            return _read_raw_unix(sys.stdin)
    except Exception:
        pass

    # ── Last resort: regular line input ──────────────────────────
    raise RuntimeError('no_raw_tty')


# ── Public InputHandler class ────────────────────────────────────

class InputHandler:
    """
    mode: 'wasd'   — WASD 4-dir  (W/A/S/D + arrows)
          'numpad' — 8-dir (numpad 1-9, vi-keys YUHJKLBN, + arrows)

    Returns from get_action():
        ('move', dx, dy)
        ('cmd',  key_str)    e.g. 'enter','fast','overview','quit','save'
        ('none',)
    """

    _warned = False   # print the fallback warning only once

    def __init__(self, mode='wasd'):
        self.mode = mode
        self._raw_ok = self._probe_raw()

    def _probe_raw(self):
        """Quick check: can we do raw input at all?"""
        if os.name == 'nt':
            try:
                import msvcrt; return True
            except ImportError:
                return False
        # Try opening /dev/tty
        try:
            t = open('/dev/tty','r'); t.close(); return True
        except Exception:
            pass
        # Try stdin isatty
        try:
            return sys.stdin.isatty()
        except Exception:
            return False

    def get_action(self):
        if self._raw_ok:
            try:
                key = _getch()
                return self._decode(key)
            except Exception:
                # Raw read failed at runtime — switch to fallback
                self._raw_ok = False

        # ── Fallback: line input ──────────────────────────────────
        if not InputHandler._warned:
            InputHandler._warned = True
            from game_term import C as _C
            print(_C("\n[Note: raw terminal input unavailable — type a command + Enter]"))
            print(_C("Commands: w/a/s/d=move  e=enter  f=fast  o=overview  p=save  q=quit\n"))
        from game_term import C as _C
        try:
            line = input(_C("> ")).strip().lower()
            if not line:
                return ('none',)
            return self._decode(line[0])
        except (EOFError, KeyboardInterrupt):
            return ('cmd', 'quit')

    def _decode(self, key):
        """Turn a raw key into an action tuple."""
        if not key:
            return ('none',)

        # Arrow keys (returned as strings by _getch)
        if key in ARROW_MAP:
            dx, dy = ARROW_MAP[key]
            return ('move', dx, dy)
        if key in DIAG_MAP:
            if self.mode == 'wasd':
                return ('none',)
            dx, dy = DIAG_MAP[key]
            return ('move', dx, dy)

        # Movement keys
        move_map = WASD_MAP if self.mode == 'wasd' else NUMPAD_MAP
        if key in move_map:
            dx, dy = move_map[key]
            return ('move', dx, dy)

        # Special commands
        if key in CMD_MAP:
            return ('cmd', CMD_MAP[key])

        return ('none',)
