#!/usr/bin/env python3
"""
tools/screenshots.py — regenerate the README screenshots of Terminal-RPG.

Usage (from the repo root):

    python3 tools/screenshots.py              # capture every scene
    python3 tools/screenshots.py combat dungeon   # only some scenes
    python3 tools/screenshots.py --html-only  # skip the PNG step
    python3 tools/screenshots.py --list       # list scene names

How it works
------------
1. The repository is copied to a temporary directory (saves are anchored to
   the game folder, so this keeps ``saves/`` and ``crash.log`` out of the repo).
2. Each scene spawns the game in a pseudo-terminal of fixed size (120x42),
   with ``random`` seeded so the shots are reproducible.  Some scenes go
   through ``main.py`` exactly as a player would; others jump straight to a
   game screen (combat, dungeon, character sheet) through a tiny bootstrap.
3. Scripted keystrokes are sent with delays, and the output is fed into a
   ``pyte`` virtual screen.  At chosen moments the screen (characters,
   24-bit colours, bold) is dumped to an HTML file.
4. ``tools/render_screens.js`` (Node + Playwright/Chromium) renders each HTML
   file to a PNG with a dark terminal theme and a macOS-style window frame.

Output: ``docs/screenshots/*.png`` (the intermediate HTML files are written
to the temp directory and discarded).

Requirements: Python 3.8+, ``pip install pyte``, Node with the ``playwright``
package and a Chromium build (fonts: DejaVu Sans Mono + Noto Color Emoji
render best).
"""

from __future__ import annotations

import html
import os
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")
COLS, ROWS = 120, 42
SEED = 20240611

# ── Scenes ─────────────────────────────────────────────────────────
# Each scene: (bootstrap, steps).  bootstrap is Python code run in the child
# (inside the temp copy of the game), steps are driver instructions:
#   ("keys", "abc")   send characters one at a time (raw-key menus)
#   ("line", "text")  send text + Enter (input() prompts)
#   ("wait", secs)    idle, still reading output
#   ("expect", "txt") wait until "txt" is on screen (max 10 s)
#   ("shot", "name")  dump the screen to name.html

_HERO = """
from game_player import Player
p = Player("Aria", {job!r})
p.movement_mode = "wasd"
"""

SCENES = {
    "title": ("import main; main.run()", [
        ("expect", "New Game"), ("wait", 0.5), ("shot", "title"),
    ]),
    "character_creation": ("import main; main.run()", [
        ("expect", "New Game"), ("line", "1"),
        ("expect", "NAME"), ("line", "Aria"),
        ("expect", "CLASS"), ("wait", 0.5), ("shot", "character_creation"),
    ]),
    "world_map": ("""
import main
from game_world import WorldMap
""" + _HERO.format(job="Swordsman") + """
p.stories.start_main(next(iter(main.MAIN_STORIES)))
w = WorldMap(seed=1337)
import random as _r
_g = _r.Random(7)
H_, W_ = len(w.terrain), len(w.terrain[0])
vh, vw = ROWS - 8, COLS - 1          # map viewport (see WorldMap.render)
cy = min(max(w.player_y, vh // 2), H_ - vh // 2)
cx = min(max(w.player_x, vw // 2), W_ - vw // 2)
for dy in range(-vh // 2, vh // 2 + 1):   # pretend this region was explored
    span = int(54 * max(0, 1 - (dy / (vh / 2 + 1)) ** 2) ** 0.5) + _g.randint(-3, 3)
    for dx in range(-span, span + 1):
        x, y = cx + dx, cy + dy
        if 0 <= x < W_ and 0 <= y < H_:
            w.discovered[y][x] = True
w._random_encounter = lambda *a, **k: None   # no fights while we walk
main.world_loop(p, w)
""", [
        ("expect", "HP"), ("wait", 0.5),
        ("keys", "dddddsssddd"), ("wait", 0.8), ("shot", "world_map"),
    ]),
    "combat": ("""
from game_enemies import generate_enemy
from game_systems import run_combat
""" + _HERO.format(job="Mage") + """
p.level = 4; p.max_hp += 30; p.hp = p.max_hp - 22
e = generate_enemy("forest", 2, 3)
run_combat(p, e)
""", [
        ("expect", "battle log"), ("line", "1"),
        ("expect", "Round 2"), ("line", "2"),
        ("expect", "SKILLS"), ("line", "1"),
        ("expect", "Round 3"), ("wait", 0.5), ("shot", "combat"),
    ]),
    "dungeon": ("""
from game_dungeon import DungeonManager
""" + _HERO.format(job="Rogue") + """
p.god_immunity_turns = 999
d = DungeonManager("Blackroot Crypt", danger=2, boss_name="Shadow Lich")
# Walk most of the way to the stairs first, so the fog of war shows an
# explored trail (direct moves: no fights/chests are triggered).
from collections import deque
f = d.current()
goal = next((x, y) for y, row in enumerate(f.grid) for x, c in enumerate(row) if c == "\u25bc")
prev = {(f.px, f.py): None}; q = deque([(f.px, f.py)])
while q:
    cx, cy = q.popleft()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        n = (cx+dx, cy+dy)
        if 0 <= n[0] < f.W_MAP and 0 <= n[1] < f.H_MAP and n not in prev and f.grid[n[1]][n[0]] != "#":
            prev[n] = (cx, cy); q.append(n)
path = []; n = goal
while n: path.append(n); n = prev[n]
path.reverse()
for (x0, y0), (x1, y1) in list(zip(path, path[1:]))[:-4]:
    f.move(x1 - x0, y1 - y0)
d.enter(p)
""", [
        ("expect", "Floor 1"), ("wait", 0.4),
        ("wait", 0.8), ("shot", "dungeon"),
    ]),
    "character_sheet": ("""
from game_items import town_shop_stock, Equipment
""" + _HERO.format(job="Swordsman") + """
p.gain_exp(900)
gear = {it.name: it for it, _ in town_shop_stock("IRONSPIRE") + town_shop_stock("FROSTHEIM")
        + town_shop_stock("SOUTH ISLES") if isinstance(it, Equipment)}
for name in ("Steel Sword", "Chain Mail", "Iron Helm", "Steel Shield",
             "Frost Cloak", "Iron Ring", "Amulet of Life"):
    if name in gear:
        p.inventory.append(gear[name])
        p.equip(gear[name])
p.gold = 1250
p.hp = p.max_hp
from game_term import clr
clr()
p.show_status()
input()
""", [
        ("expect", "CHARACTER STATUS"), ("wait", 0.5), ("shot", "character_sheet"),
    ]),
    "customise": ("""
""" + _HERO.format(job="Mage") + """
from game_customise import open_customise
open_customise(p)
""", [
        ("expect", "CUSTOMISATION"), ("wait", 0.3), ("line", "5"), ("wait", 0.6),
        ("shot", "customise"),
    ]),
}


# ── Child side: runs inside the pty ───────────────────────────────

def _child(game_dir: str, scene: str) -> None:
    os.chdir(game_dir)
    sys.argv = [os.path.join(game_dir, "main.py")]
    sys.path.insert(0, game_dir)
    import random
    _orig_seed = random.seed

    def _fixed_seed(a=None, *args, **kw):
        # The game re-seeds from the clock after world generation; keep
        # everything deterministic for the screenshots instead.
        _orig_seed(SEED if a is None else a, *args, **kw)

    random.seed = _fixed_seed
    random.seed(SEED)
    code = SCENES[scene][0]
    exec(compile(code, f"<scene {scene}>", "exec"),
         {"__name__": "__scene__", "ROWS": ROWS, "COLS": COLS})


# ── Parent side: pty driver ───────────────────────────────────────

class Session:
    def __init__(self, game_dir: str, scene: str):
        import pty, fcntl, termios
        import pyte
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        env = dict(os.environ, COLUMNS=str(COLS), LINES=str(ROWS),
                   TERM="xterm-256color", COLORTERM="truecolor",
                   HOME=game_dir, PYTHONIOENCODING="utf-8",
                   PYTHONDONTWRITEBYTECODE="1", LANG="C.UTF-8")
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe(sys.executable,
                       [sys.executable, os.path.abspath(__file__),
                        "--child", game_dir, scene], env)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    def pump(self, secs: float) -> None:
        end = time.time() + secs
        while True:
            left = end - time.time()
            if left <= 0:
                return
            r, _, _ = select.select([self.fd], [], [], left)
            if r:
                try:
                    data = os.read(self.fd, 65536)
                except OSError:
                    return
                if not data:
                    return
                self.stream.feed(data)

    def text(self) -> str:
        return "\n".join(self.screen.display)

    def expect(self, needle: str, timeout: float = 10.0) -> None:
        end = time.time() + timeout
        while needle not in self.text():
            if time.time() > end:
                raise RuntimeError(f"timed out waiting for {needle!r}; screen:\n{self.text()}")
            self.pump(0.1)

    def send(self, data: str) -> None:
        os.write(self.fd, data.encode())

    def close(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass


# ── HTML dump ─────────────────────────────────────────────────────

_NAMED = {
    "black": "1e1e2e", "red": "f38ba8", "green": "a6e3a1", "brown": "f9e2af",
    "yellow": "f9e2af", "blue": "89b4fa", "magenta": "f5c2e7", "cyan": "94e2d5",
    "white": "cdd6f4", "brightblack": "585b70", "brightred": "f38ba8",
    "brightgreen": "a6e3a1", "brightbrown": "f9e2af", "brightyellow": "f9e2af",
    "brightblue": "89b4fa", "brightmagenta": "f5c2e7", "brightcyan": "94e2d5",
    "brightwhite": "ffffff",
}
DEFAULT_FG = "d4d4dc"
DEFAULT_BG = "15161e"


def _col(c: str, default: str) -> str:
    if c == "default":
        return default
    if c in _NAMED:
        return _NAMED[c]
    if len(c) == 6:
        return c
    return default


def _wide(ch: str) -> bool:
    import unicodedata
    return bool(ch) and unicodedata.east_asian_width(ch[0]) in ("W", "F")


def screen_to_html(screen, title: str) -> str:
    rows = []
    # Trim trailing blank rows so the window hugs the content.
    last = 0
    for y in range(screen.lines):
        if "".join(screen.buffer[y][x].data for x in range(screen.columns)).strip():
            last = y
    for y in range(min(screen.lines, last + 2)):
        line = screen.buffer[y]
        out, run, run_style, x = [], [], None, 0
        while x < screen.columns:
            ch = line[x]
            data = ch.data or " "
            fg = _col(ch.fg, DEFAULT_FG)
            bg = _col(ch.bg, DEFAULT_BG)
            if ch.reverse:
                fg, bg = bg, fg
            style = (fg, bg, ch.bold)
            wide = _wide(data)
            if wide or style != run_style:
                if run:
                    out.append(_span(run, run_style))
                run, run_style = [], style
            if wide:
                out.append(_span([data], style, cells=2))
                run_style = None
                x += 2
                continue
            run.append(data)
            x += 1
        if run:
            out.append(_span(run, run_style))
        rows.append(f'<div class="row">{"".join(out)}</div>')
    return TEMPLATE.replace("{{TITLE}}", html.escape(title)).replace(
        "{{ROWS}}", "\n".join(rows)).replace("{{COLS}}", str(COLS))


def _span(chars, style, cells=None) -> str:
    fg, bg, bold = style
    css = [f"color:#{fg}"]
    if bg != DEFAULT_BG:
        css.append(f"background:#{bg}")
    if bold:
        css.append("font-weight:bold")
    n = cells or len(chars)
    cls = "w" if cells else "r"
    return (f'<span class="{cls}" style="{";".join(css)};width:calc(var(--cw)*{n})">'
            f'{html.escape("".join(chars))}</span>')


TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{{TITLE}}</title>
<style>
  :root { --cw: 8.43px; --lh: 16.3px; }
  html, body { margin: 0; background: transparent; }
  body { padding: 28px; display: inline-block; }
  .window {
    background: #15161e; border-radius: 12px; overflow: hidden;
    box-shadow: 0 18px 48px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.08);
  }
  .bar { height: 34px; background: #23242f; display: flex; align-items: center;
         padding: 0 14px; position: relative; border-bottom: 1px solid #0d0e14; }
  .dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
  .title { position: absolute; left: 0; right: 0; text-align: center;
           font: 13px -apple-system, "DejaVu Sans", sans-serif; color: #9a9cad; }
  .term { padding: 14px 18px 18px; font-family: "DejaVu Sans Mono", monospace;
          font-size: 14px; line-height: var(--lh); color: #d4d4dc;
          width: calc(var(--cw) * {{COLS}}); }
  .row { height: var(--lh); white-space: pre; display: flex; }
  .r, .w { display: inline-block; flex: none; overflow: visible; height: var(--lh); }
  .w { font-family: "Noto Color Emoji", "DejaVu Sans Mono", monospace;
       text-align: center; font-size: 13px; }
</style></head>
<body><div class="window">
  <div class="bar"><span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span><span class="dot" style="background:#28c840"></span><div class="title">{{TITLE}}</div></div>
  <div class="term">
{{ROWS}}
  </div>
</div></body></html>
"""


# ── Orchestration ─────────────────────────────────────────────────

def capture(scene: str, game_dir: str, html_dir: str) -> list:
    _, steps = SCENES[scene]
    sess = Session(game_dir, scene)
    made = []
    try:
        sess.pump(0.3)
        for kind, arg in steps:
            if kind == "keys":
                for ch in arg:
                    sess.send(ch)
                    sess.pump(0.12)
            elif kind == "line":
                sess.send(arg + "\r")
                sess.pump(0.3)
            elif kind == "wait":
                sess.pump(arg)
            elif kind == "expect":
                sess.expect(arg)
            elif kind == "shot":
                path = os.path.join(html_dir, f"{arg}.html")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(screen_to_html(sess.screen, "Terminal-RPG — python3 main.py"))
                made.append(path)
    finally:
        sess.close()
    return made


def main(argv) -> int:
    if argv[:1] == ["--child"]:
        _child(argv[1], argv[2])
        return 0
    if "--list" in argv:
        print("\n".join(SCENES))
        return 0
    html_only = "--html-only" in argv
    wanted = [a for a in argv if not a.startswith("--")] or list(SCENES)
    for w in wanted:
        if w not in SCENES:
            print(f"unknown scene {w!r}; try --list", file=sys.stderr)
            return 2

    tmp = tempfile.mkdtemp(prefix="trpg-shots-")
    game_dir = os.path.join(tmp, "game")
    html_dir = os.path.join(tmp, "html")
    os.makedirs(html_dir)
    shutil.copytree(ROOT, game_dir, ignore=shutil.ignore_patterns(
        ".git", "saves", "docs", "__pycache__", "tools", "*.log"))
    try:
        files = []
        for scene in wanted:
            print(f"capturing {scene} ...", flush=True)
            # Fresh copy of mutable state for every scene
            shutil.rmtree(os.path.join(game_dir, "saves"), ignore_errors=True)
            files += capture(scene, game_dir, html_dir)
        if html_only:
            keep = os.path.join(ROOT, "docs", "screenshots", "html")
            os.makedirs(keep, exist_ok=True)
            for f in files:
                shutil.copy(f, keep)
            print(f"HTML written to {keep}")
            return 0
        os.makedirs(OUT_DIR, exist_ok=True)
        js = os.path.join(ROOT, "tools", "render_screens.js")
        subprocess.run(["node", js, OUT_DIR, *files], check=True)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
