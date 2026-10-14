"""game_scene.py — reusable walkable-map engine for towns, ports, the capital,
castle interiors and world structures.

A Scene is a grid of tile characters plus entities (NPCs, guards, bandits,
merchants) and triggers (doors, gates, docks).  The player walks around with
the same keys as on the world map; bumping into an NPC or pressing E next to
it interacts, walking into a door runs that building's callback (shop, inn,
quest board ...), and dark tiles hide lurking bandits.

Usage:

    sc = Scene("GREENVEIL", rows, palette=TOWN_TILES, start=(10, 20),
               subtitle="Aeloria · market town")
    sc.add_door(12, 5, "Shop", lambda sc, pl: town.shop())
    sc.add_entity(Entity(14, 9, "@", fg(240,200,120), "Mira", kind="npc",
                         lines=["Lovely day!"], ai="wander"))
    result = sc.run(player)          # 'left', 'defeat', or anything set via sc.leave()

All drawing goes through game_term.draw_frame (flicker free).  Everything is
Python standard library only.
"""

from __future__ import annotations

import os, random
from game_term import C, W, H, clr, draw_frame, _vis

R_ = "\033[0m"
B_ = "\033[1m"


def fg(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"


def bg(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"


C_GOLD = fg(255, 215, 0)
C_WHITE = fg(230, 230, 230)
C_DIM = fg(120, 120, 130)
C_RED = fg(230, 70, 70)
C_GREEN = fg(90, 210, 110)
C_CYAN = fg(80, 220, 220)
C_BLUE = fg(80, 130, 220)
C_PURP = fg(180, 110, 230)


# ── Tiles ────────────────────────────────────────────────────────

class Tile:
    """How one map character looks and behaves."""
    __slots__ = ("colour", "glyph", "walkable", "name", "dark")

    def __init__(self, colour, glyph, walkable=True, name="", dark=False):
        self.colour = colour
        self.glyph = glyph
        self.walkable = walkable
        self.name = name
        self.dark = dark          # dark tiles: drawn dim, lurkers hide here


def _t(rgb, glyph, walk=True, name="", dark=False):
    return Tile(fg(*rgb), glyph, walk, name, dark)


# Default palette. Map rows use these KEY characters; the glyph is what is
# drawn (may differ from the key). All glyphs are single-width.
TOWN_TILES = {
    " ": _t((0, 0, 0), " ", False, "void"),
    ".": _t((95, 90, 80), "·", True, "cobbles"),
    ",": _t((70, 140, 60), '"', True, "grass"),
    ":": _t((180, 160, 110), ".", True, "dirt path"),
    "_": _t((150, 120, 80), "▪", True, "wooden floor"),
    "=": _t((150, 110, 60), "═", True, "pier"),
    "~": _t((40, 90, 200), "≈", False, "water"),
    "w": _t((60, 130, 220), "~", False, "shallow water"),
    "#": _t((150, 145, 135), "█", False, "stone wall"),
    "%": _t((120, 85, 50), "▓", False, "timber wall"),
    "-": _t((160, 150, 140), "─", False, "wall"),
    "|": _t((160, 150, 140), "│", False, "wall"),
    "1": _t((160, 150, 140), "┌", False, "wall"),
    "2": _t((160, 150, 140), "┐", False, "wall"),
    "3": _t((160, 150, 140), "└", False, "wall"),
    "4": _t((160, 150, 140), "┘", False, "wall"),
    "H": _t((200, 190, 170), "═", False, "stone wall"),
    "V": _t((200, 190, 170), "║", False, "stone wall"),
    "5": _t((200, 190, 170), "╔", False, "stone wall"),
    "6": _t((200, 190, 170), "╗", False, "stone wall"),
    "7": _t((200, 190, 170), "╚", False, "stone wall"),
    "8": _t((200, 190, 170), "╝", False, "stone wall"),
    "+": _t((200, 150, 70), "+", True, "door"),
    "D": _t((230, 190, 90), "▒", True, "gate"),
    "T": _t((40, 140, 50), "♣", False, "tree"),
    "f": _t((200, 80, 200), "*", False, "flowers"),
    "o": _t((120, 170, 230), "o", False, "well"),
    "s": _t((210, 160, 80), "¤", False, "market stall"),
    "c": _t((170, 120, 70), "▫", False, "crate"),
    "b": _t((140, 100, 60), "o", False, "barrel"),
    "t": _t((150, 110, 70), "π", False, "table"),
    "p": _t((210, 200, 180), "‡", False, "pillar"),
    "r": _t((170, 40, 50), "░", True, "royal carpet"),
    "Q": _t((255, 215, 0), "Ω", False, "throne"),
    "F": _t((255, 140, 40), "♨", False, "fire"),
    "L": _t((255, 220, 120), "¡", False, "lamp post"),
    "a": _t((45, 40, 50), "░", True, "dark alley", dark=True),
    "x": _t((55, 50, 45), "·", True, "back street", dark=True),
    "^": _t((130, 125, 115), "^", False, "rock"),
    "n": _t((200, 200, 220), "♦", False, "banner"),
    "u": _t((190, 170, 120), "∩", False, "fountain"),
    "S": _t((140, 140, 150), "▲", False, "statue"),
    "B": _t((120, 85, 50), "▬", False, "boat"),
    "*": _t((230, 240, 255), "*", True, "snow"),
    "z": _t((210, 190, 120), ".", True, "sand"),
    "y": _t((150, 120, 200), "≡", False, "bookshelf"),
    "k": _t((150, 150, 160), "Π", False, "anvil"),
    "e": _t((110, 75, 45), "=", True, "bridge"),
    "g": _t((90, 90, 95), "▒", False, "portcullis"),
    "v": _t((200, 200, 210), "▼", True, "stairs down"),
    "<": _t((200, 200, 210), "▲", True, "stairs up"),
}


# ── Entities ─────────────────────────────────────────────────────

class Entity:
    """Anything standing on the map that isn't terrain.

    kind   : 'npc', 'guard', 'merchant', 'bandit', 'recruit', 'object' ...
    lines  : default dialogue lines (one picked at random per talk)
    ai     : 'static' | 'wander' | 'patrol' | 'lurk' | 'chase'
    interact(scene, player, ent) -> optional str message.  Called on E / bump
             for friendly entities.  If None and lines exist, a talk box opens.
    hostile: walking into it (or it reaching you) calls on_contact.
    on_contact(scene, player, ent) -> optional str.  Default: nothing.
    lurk   : invisible until the player is within reveal_radius (dark corners)
    npc_id : stable id used by stories: talking emits on_talk("npc:<npc_id>")
    """

    def __init__(self, x, y, glyph, colour, name, kind="npc", lines=None,
                 ai="static", interact=None, hostile=False, on_contact=None,
                 radius=4, lurk=False, reveal_radius=2, npc_id=None,
                 patrol=None, solid=True, data=None, title=""):
        self.x, self.y = x, y
        self.home = (x, y)
        self.glyph = glyph
        self.colour = colour
        self.name = name
        self.title = title
        self.kind = kind
        self.lines = list(lines or [])
        self.ai = ai
        self.interact = interact
        self.hostile = hostile
        self.on_contact = on_contact
        self.radius = radius
        self.lurk = lurk
        self.reveal_radius = reveal_radius
        self.npc_id = npc_id
        self.patrol = list(patrol or [])
        self._pi = 0
        self.solid = solid
        self.data = dict(data or {})
        self.alive = True
        self.revealed = not lurk
        self.cooldown = 0

    def visible_to(self, px, py):
        if not self.lurk:
            return True
        if self.revealed:
            return True
        return max(abs(self.x - px), abs(self.y - py)) <= self.reveal_radius


# ── Scene ────────────────────────────────────────────────────────

class Scene:
    HUD_TOP = 4       # title, subtitle, status, divider
    HUD_BOTTOM = 6    # divider, 3 message lines, hint, keys

    def __init__(self, title, rows, palette=None, start=(1, 1), subtitle="",
                 colour=C_GOLD, fog=False, sight=7, night=False, exit_on_edge=True,
                 allow_leave_anywhere=True):
        self.title = title
        self.subtitle = subtitle
        self.colour = colour
        self.palette = dict(TOWN_TILES)
        if palette:
            self.palette.update(palette)
        w = max((len(r) for r in rows), default=1)
        self.grid = [list(r.ljust(w)) for r in rows]
        self.w, self.h = w, len(rows)
        self.px, self.py = start
        self.entities = []
        self.triggers = {}        # (x,y) -> (label, fn, step_back)
        self.labels = []          # (x, y, text, colour)
        self.on_turn = []         # callables(scene, player)
        self.log = []
        self.result = None
        self.fog = fog
        self.sight = sight
        self.night = night
        self.seen = set()
        self.turns = 0
        self.exit_on_edge = exit_on_edge
        self.allow_leave_anywhere = allow_leave_anywhere
        self.player = None
        self.extra_keys = {}      # key -> (label, fn(scene, player))
        self.hud_extra = None     # callable(scene, player) -> str
        self._reveal()

    # ── building the map ──────────────────────────────────────────
    def set_tile(self, x, y, ch):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.grid[y][x] = ch

    def tile_at(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return None
        return self.palette.get(self.grid[y][x])

    def add_entity(self, ent):
        self.entities.append(ent)
        return ent

    def add_door(self, x, y, label, fn, step_back=True, tile="+"):
        """Walking onto (x,y) runs fn(scene, player). With step_back the
        player is put back where they came from afterwards (shop doors)."""
        if tile:
            self.set_tile(x, y, tile)
        self.triggers[(x, y)] = (label, fn, step_back)

    add_trigger = add_door

    def add_label(self, x, y, text, colour=None):
        """Painted sign text over the map (e.g. 'SMITH' on a roof)."""
        self.labels.append((x, y, text, colour or fg(230, 200, 120)))

    def add_key(self, key, label, fn):
        """Extra command key for this scene, e.g. ('r', 'Rest', fn)."""
        self.extra_keys[key.lower()] = (label, fn)

    def leave(self, result="left"):
        self.result = result

    def message(self, text):
        self.log.append(text)
        self.log = self.log[-3:]

    say = message

    # ── queries ───────────────────────────────────────────────────
    def walkable(self, x, y, ignore=None):
        t = self.tile_at(x, y)
        if t is None or not t.walkable:
            return False
        for e in self.entities:
            if e is not ignore and e.alive and e.solid and e.x == x and e.y == y:
                return False
        return True

    def entity_at(self, x, y):
        for e in self.entities:
            if e.alive and e.x == x and e.y == y:
                return e
        return None

    def adjacent_entities(self):
        out = []
        for e in self.entities:
            if not e.alive or not e.visible_to(self.px, self.py):
                continue
            if max(abs(e.x - self.px), abs(e.y - self.py)) <= 1 and (e.x, e.y) != (self.px, self.py):
                out.append(e)
        return out

    def nearby_trigger(self):
        for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)):
            k = (self.px + dx, self.py + dy)
            if k in self.triggers:
                return k
        return None

    def find(self, ch):
        """All (x,y) positions holding tile key ch."""
        return [(x, y) for y, row in enumerate(self.grid) for x, c in enumerate(row) if c == ch]

    def random_floor(self, rng=None, keys=(".", ",", ":", "_")):
        rng = rng or random
        spots = [(x, y) for y, row in enumerate(self.grid) for x, c in enumerate(row)
                 if c in keys and self.walkable(x, y)]
        return rng.choice(spots) if spots else (self.px, self.py)

    # ── modal helpers ─────────────────────────────────────────────
    def modal(self, fn, *a, **kw):
        """Run a blocking full-screen menu, then restore the map."""
        clr()
        try:
            return fn(*a, **kw)
        finally:
            clr()

    def talk_box(self, ent, text=None, player=None):
        """Show a dialogue box with one line from ent and wait for a key."""
        text = text or (random.choice(ent.lines) if ent.lines else "...")
        lines = self._frame_lines(player or self.player)
        name = f"{ent.colour}{B_}{ent.name}{R_}" + (f" {C_DIM}· {ent.title}{R_}" if ent.title else "")
        lines.append(C(f"{C_GOLD}╭{'─' * 70}╮{R_}"))
        lines.append(C(f"{C_GOLD}│{R_} {name}"))
        for chunk in _wrap(text, 68):
            lines.append(C(f"{C_GOLD}│{R_} {C_WHITE}{chunk}{R_}"))
        lines.append(C(f"{C_GOLD}╰{'─' * 70}╯{R_}"))
        lines.append(C(f"{C_DIM}(any key){R_}"))
        draw_frame(lines)
        self._wait_key()

    def choice_box(self, title, options, ent=None):
        """Small inline menu. options: list of (key, label). Returns key or None."""
        lines = self._frame_lines(self.player)
        head = f"{ent.colour}{B_}{ent.name}{R_}  " if ent else ""
        lines.append(C(f"{C_GOLD}╭{'─' * 70}╮{R_}"))
        for chunk in _wrap(title, 68):
            lines.append(C(f"{C_GOLD}│{R_} {head}{C_WHITE}{chunk}{R_}"))
            head = ""
        for k, lbl in options:
            lines.append(C(f"{C_GOLD}│{R_}  {C_GOLD}[{k}]{R_} {C_WHITE}{lbl}{R_}"))
        lines.append(C(f"{C_GOLD}╰{'─' * 70}╯{R_}"))
        draw_frame(lines)
        valid = {str(k).lower() for k, _ in options}
        while True:
            k = self._wait_key().lower()
            if k in valid:
                return k
            if k in ("\x1b", "q", "0"):
                return None

    def fight(self, player, enemy, first_strike=False, allow_escape=True):
        """Run a combat from inside the scene. Sets result='defeat' on loss."""
        from game_systems import run_combat
        res = self.modal(run_combat, player, enemy, allow_escape, first_strike)
        if res == "defeat" or not player.is_alive():
            self.result = "defeat"
        return res

    # ── input ─────────────────────────────────────────────────────
    def _wait_key(self):
        try:
            from game_input import _getch
            return _getch() or ""
        except Exception:
            try:
                return (input(C("> ")).strip() or "\n")[0]
            except (EOFError, KeyboardInterrupt):
                return "\x1b"

    def _read(self, inp):
        """Returns ('move',dx,dy) or ('key', ch)."""
        from game_input import ARROW_MAP, DIAG_MAP, WASD_MAP, NUMPAD_MAP
        if inp._raw_ok:
            try:
                from game_input import _getch
                k = _getch()
            except Exception:
                inp._raw_ok = False
                k = None
        else:
            k = None
        if k is None:
            try:
                line = input(C("> ")).strip()
            except (EOFError, KeyboardInterrupt):
                return ("key", "\x1b")
            k = line[0] if line else ""
        if k in ARROW_MAP:
            return ("move",) + ARROW_MAP[k]
        if k in DIAG_MAP and inp.mode != "wasd":
            return ("move",) + DIAG_MAP[k]
        mm = WASD_MAP if inp.mode == "wasd" else NUMPAD_MAP
        if k in mm:
            return ("move",) + mm[k]
        return ("key", k)

    # ── main loop ─────────────────────────────────────────────────
    def run(self, player):
        from game_input import InputHandler
        self.player = player
        inp = InputHandler(mode=getattr(player, "movement_mode", "wasd"))
        clr()
        self.result = None
        while self.result is None:
            self.render(player)
            act = self._read(inp)
            if act[0] == "move":
                self._move(act[1], act[2], player)
            else:
                self._command(act[1], player)
            if self.result is None and not player.is_alive():
                self.result = "defeat"
        clr()
        return self.result

    def _command(self, k, player):
        kl = k.lower() if k else ""
        if kl in self.extra_keys:
            _, fn = self.extra_keys[kl]
            msg = fn(self, player)
            if msg:
                self.message(msg)
            return
        if kl in ("e", " ", "\r", "\n"):
            self.interact(player)
        elif kl == "i":
            from game_player import quick_inventory
            self.modal(quick_inventory, player)
        elif kl == "j":
            self.modal(player.stories.show_journal, player)
        elif kl == "t":
            def _st():
                player.show_status()
                input(C(f"\n{C_DIM}(Press Enter){R_}"))
            self.modal(_st)
        elif k == "?":
            self.modal(self._help)
        elif kl in ("q", "\x1b", "\x03", "\x04"):
            if self.allow_leave_anywhere:
                if self.choice_box(f"Leave {self.title.title()}?", [("y", "Yes, leave"), ("n", "Stay")]) == "y":
                    self.result = "left"
            else:
                self.message(f"{C_DIM}Find the exit to leave.{R_}")

    def interact(self, player):
        adj = self.adjacent_entities()
        # prefer the entity the player is facing / nearest friendly
        friendly = [e for e in adj if not e.hostile]
        if friendly:
            self._talk(friendly[0], player)
            return
        if adj:
            self._contact(adj[0], player)
            return
        k = self.nearby_trigger()
        if k:
            self._fire_trigger(k, player, (self.px, self.py))
            return
        self.message(f"{C_DIM}Nothing here to interact with.{R_}")

    def _talk(self, ent, player):
        try:
            st = getattr(player, "stories", None)
            extra = None
            if st is not None and ent.npc_id:
                if hasattr(st, "on_talk"):
                    done = st.on_talk(f"npc:{ent.npc_id}", player) if _accepts_player(st.on_talk) else st.on_talk(f"npc:{ent.npc_id}")
                    if done:
                        self.message(f"{C_GOLD}★ Story updated!{R_}")
                # Story contract: npc_event(npc_id, player) -> None or
                # {"lines": [...], "fight": "Boss Name", "flag": "key"}
                if hasattr(st, "npc_event"):
                    ev = st.npc_event(ent.npc_id, player)
                    if isinstance(ev, dict) and (ev.get("lines") or ev.get("fight")):
                        for line in ev.get("lines") or []:
                            self.talk_box(ent, line, player)
                        if ev.get("flag"):
                            player.flags[ev["flag"]] = True
                            if hasattr(st, "check_flags"):
                                if st.check_flags(player):
                                    self.message(f"{C_GOLD}★ Story updated!{R_}")
                        if ev.get("fight"):
                            from game_enemies import create_boss
                            boss = create_boss(ev["fight"], player.level)
                            if self.fight(player, boss, allow_escape=False) == "victory":
                                self.message(f"{C_GOLD}★ {boss.name} is defeated!{R_}")
                        return
                if hasattr(st, "npc_dialogue"):
                    extra = st.npc_dialogue(ent.npc_id, player)
        except Exception as _e:
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as _f:
                    _f.write(f"scene talk {ent.npc_id}: {_e!r}\n")
            except Exception:
                pass
            extra = None
        if self.result is not None:
            return
        if ent.interact:
            msg = ent.interact(self, player, ent)
            if msg:
                self.message(msg)
            return
        if extra:
            for line in (extra if isinstance(extra, (list, tuple)) else [extra]):
                self.talk_box(ent, line, player)
            return
        self.talk_box(ent, None, player)

    def _contact(self, ent, player):
        if ent.on_contact:
            msg = ent.on_contact(self, player, ent)
            if msg:
                self.message(msg)

    def _fire_trigger(self, k, player, back):
        label, fn, step_back = self.triggers[k]
        msg = fn(self, player)
        if msg:
            self.message(msg)
        if step_back and self.result is None and (self.px, self.py) == k:
            self.px, self.py = back

    def _move(self, dx, dy, player):
        nx, ny = self.px + dx, self.py + dy
        if not (0 <= nx < self.w and 0 <= ny < self.h):
            if self.exit_on_edge:
                self.result = "left"
            return
        ent = self.entity_at(nx, ny)
        if ent and ent.visible_to(self.px, self.py) or (ent and ent.hostile):
            if ent.hostile:
                ent.revealed = True
                self._contact(ent, player)
            else:
                self._talk(ent, player)
            self._tick(player)
            return
        t = self.tile_at(nx, ny)
        if t is None or not t.walkable:
            if t is not None and t.name:
                self.message(f"{C_DIM}A {t.name} blocks the way.{R_}")
            return
        back = (self.px, self.py)
        self.px, self.py = nx, ny
        self._reveal()
        if (nx, ny) in self.triggers:
            self._fire_trigger((nx, ny), player, back)
        self._tick(player)

    def _tick(self, player):
        self.turns += 1
        for fn in list(self.on_turn):
            try:
                msg = fn(self, player)
            except Exception:
                msg = None
            if msg:
                self.message(msg)
            if self.result is not None:
                return
        for e in list(self.entities):
            if not e.alive:
                continue
            self._step_entity(e, player)
            if self.result is not None:
                return

    def _step_entity(self, e, player):
        if e.cooldown > 0:
            e.cooldown -= 1
            return
        dist = max(abs(e.x - self.px), abs(e.y - self.py))
        if e.lurk and not e.revealed and dist <= e.reveal_radius:
            e.revealed = True
            if e.hostile:
                self.message(f"{C_RED}{e.name} steps out of the shadows!{R_}")
        if e.ai == "static":
            return
        if e.ai == "wander":
            if random.random() < 0.45:
                dx, dy = random.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
                nx, ny = e.x + dx, e.y + dy
                hx, hy = e.home
                if (abs(nx - hx) <= e.radius and abs(ny - hy) <= e.radius
                        and self.walkable(nx, ny, ignore=e) and (nx, ny) != (self.px, self.py)
                        and (nx, ny) not in self.triggers):
                    e.x, e.y = nx, ny
            return
        if e.ai == "patrol" and e.patrol:
            tx, ty = e.patrol[e._pi]
            if (e.x, e.y) == (tx, ty):
                e._pi = (e._pi + 1) % len(e.patrol)
                return
            self._step_toward(e, tx, ty)
            return
        if e.ai in ("lurk", "chase"):
            sight = 6 if e.ai == "chase" else (e.reveal_radius + 2)
            if e.revealed and dist <= sight:
                if dist <= 1:
                    if e.hostile:
                        self._contact(e, player)
                    return
                self._step_toward(e, self.px, self.py)
                if max(abs(e.x - self.px), abs(e.y - self.py)) <= 1 and e.hostile:
                    self._contact(e, player)

    def _step_toward(self, e, tx, ty):
        best = None
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = e.x + dx, e.y + dy
            if (nx, ny) == (self.px, self.py) or not self.walkable(nx, ny, ignore=e):
                continue
            d = abs(nx - tx) + abs(ny - ty)
            if best is None or d < best[0]:
                best = (d, nx, ny)
        if best:
            e.x, e.y = best[1], best[2]

    def _reveal(self):
        if not self.fog:
            return
        r = self.sight
        for dy in range(-r, r + 1):
            for dx in range(-r * 2, r * 2 + 1):
                if (dx / 2) ** 2 + dy ** 2 <= r * r:
                    self.seen.add((self.px + dx, self.py + dy))

    # ── rendering ─────────────────────────────────────────────────
    def _view(self):
        cols, rows = W(), H()
        vw = max(20, min(self.w, cols - 2))
        vh = max(8, min(self.h, rows - self.HUD_TOP - self.HUD_BOTTOM))
        cx = min(max(0, self.px - vw // 2), max(0, self.w - vw))
        cy = min(max(0, self.py - vh // 2), max(0, self.h - vh))
        return vw, vh, cx, cy, cols

    def _status_line(self, player):
        if player is None:
            return ""
        try:
            from game_term import hpbar, mpbar
            hp = hpbar(player.hp, player.max_hp, 14)
            mp = mpbar(player.mp, player.max_mp, 8)
        except Exception:
            hp = mp = ""
        cls = getattr(getattr(player, "job", None), "name", "")
        extra = ""
        if self.hud_extra:
            try:
                extra = "  " + self.hud_extra(self, player)
            except Exception:
                extra = ""
        return (f"{C_WHITE}{B_}{player.name}{R_} {C_DIM}Lv{R_}{C_GOLD}{player.level}{R_} "
                f"{C_DIM}[{cls}]{R_}  HP {hp}  MP {mp}  {C_GOLD}Gold {player.gold}{R_}{extra}")

    def _frame_lines(self, player):
        vw, vh, cx, cy, cols = self._view()
        pad = " " * max(0, (cols - vw) // 2)
        out = []
        sub = f"  {C_DIM}{self.subtitle}{R_}" if self.subtitle else ""
        out.append(pad + f"{self.colour}{B_}══ {self.title} ══{R_}{sub}")
        out.append(pad + self._status_line(player))
        out.append(pad + f"{C_DIM}{'─' * vw}{R_}")

        # entity + label overlays
        ents = {}
        for e in self.entities:
            if e.alive and e.visible_to(self.px, self.py):
                ents[(e.x, e.y)] = e
        lab = {}
        for (lx, ly, text, col) in self.labels:
            for i, ch in enumerate(text):
                lab[(lx + i, ly)] = (ch, col)

        dark_r = 3
        for vy in range(vh):
            y = cy + vy
            row = []
            last = None
            for vx in range(vw):
                x = cx + vx
                if (x, y) == (self.px, self.py):
                    seg = f"{fg(255, 70, 70)}{B_}@"
                    row.append(seg)
                    last = None
                    continue
                if self.fog and (x, y) not in self.seen:
                    if last != "fog":
                        row.append(R_)
                        last = "fog"
                    row.append(" ")
                    continue
                if (x, y) in ents:
                    e = ents[(x, y)]
                    row.append(f"{R_}{e.colour}{B_}{e.glyph}{R_}")
                    last = None
                    continue
                if (x, y) in lab:
                    ch, col = lab[(x, y)]
                    row.append(f"{R_}{col}{B_}{ch}{R_}")
                    last = None
                    continue
                if y >= self.h or x >= self.w:
                    row.append(" ")
                    continue
                t = self.palette.get(self.grid[y][x])
                if t is None:
                    row.append(self.grid[y][x])
                    continue
                col = t.colour
                if t.dark or self.night:
                    near = max(abs(x - self.px), abs(y - self.py)) <= dark_r
                    if not near:
                        col = C_DIM if t.dark else _dim(col)
                if col != last:
                    row.append(R_ + col)
                    last = col
                row.append(t.glyph)
            out.append(pad + "".join(row) + R_)
        return out

    def render(self, player):
        lines = self._frame_lines(player)
        vw, vh, cx, cy, cols = self._view()
        pad = " " * max(0, (cols - vw) // 2)
        lines.append(pad + f"{C_DIM}{'─' * vw}{R_}")
        msgs = self.log[-3:]
        for i in range(3):
            lines.append(pad + (msgs[i] if i < len(msgs) else ""))
        lines.append(pad + self._hint())
        extra = "".join(f"{C_GOLD}[{k.upper()}]{R_}{C_DIM}{lbl}  {R_}" for k, (lbl, _) in self.extra_keys.items())
        lines.append(pad + f"{C_DIM}move  {R_}{C_GOLD}[E]{R_}{C_DIM}Talk/Use  {R_}"
                     f"{C_GOLD}[I]{R_}{C_DIM}Bag  {R_}{C_GOLD}[J]{R_}{C_DIM}Journal  {R_}"
                     f"{C_GOLD}[T]{R_}{C_DIM}Status  {R_}{extra}"
                     f"{C_GOLD}[?]{R_}{C_DIM}Help  {R_}{C_GOLD}[Q]{R_}{C_DIM}Leave{R_}")
        draw_frame(lines)

    def _hint(self):
        adj = [e for e in self.adjacent_entities()]
        if adj:
            e = adj[0]
            verb = "Fight" if e.hostile else "Talk to"
            return f"{C_GOLD}[E]{R_} {C_WHITE}{verb} {e.colour}{e.name}{R_}" + (f" {C_DIM}({e.title}){R_}" if e.title else "")
        k = self.nearby_trigger()
        if k:
            return f"{C_GOLD}[E]{R_} {C_WHITE}{self.triggers[k][0]}{R_}"
        t = self.tile_at(self.px, self.py)
        if t and t.dark:
            return f"{C_PURP}It's dark here. Watch your purse.{R_}"
        return ""

    def _help(self):
        print(C(f"\n{C_GOLD}{B_}══ HOW TO GET AROUND ══{R_}\n"))
        print(C(f"{C_WHITE}Walk with WASD / arrows (or the numpad in 8-direction mode).{R_}"))
        print(C(f"{C_WHITE}Walk into a door {C_GOLD}+{R_}{C_WHITE} to enter a building.{R_}"))
        print(C(f"{C_WHITE}Walk into someone, or stand next to them and press {C_GOLD}E{R_}{C_WHITE}, to talk.{R_}"))
        print(C(f"{C_PURP}Dark alleys ░ hide thieves and bandits. Guards keep them away.{R_}"))
        print(C(f"{C_WHITE}Leave through a gate {C_GOLD}▒{R_}{C_WHITE}, the map edge, or press {C_GOLD}Q{R_}{C_WHITE}.{R_}\n"))
        print(C(f"{C_DIM}Legend:{R_}"))
        shown = set()
        for key, t in self.palette.items():
            if t.name in shown or not t.name or key == " ":
                continue
            shown.add(t.name)
        # print the legend compactly for tiles actually on this map
        present = {c for row in self.grid for c in row}
        items = [f"{t.colour}{t.glyph}{R_} {C_DIM}{t.name}{R_}" for k, t in self.palette.items()
                 if k in present and t.name and k != " "]
        seen_names = set()
        uniq = []
        for it in items:
            if it not in seen_names:
                seen_names.add(it)
                uniq.append(it)
        for i in range(0, len(uniq), 5):
            print(C("   ".join(uniq[i:i + 5])))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))


# ── helpers ──────────────────────────────────────────────────────

def _dim(col):
    """Darken an fg() colour code for night/dark rendering."""
    try:
        parts = col.split("[38;2;")[1].split("m")[0].split(";")
        r, g, b = (int(p) for p in parts[:3])
        return fg(r // 2, g // 2, b // 2)
    except Exception:
        return C_DIM


def _wrap(text, width):
    words = str(text).split()
    out, cur = [], ""
    for w in words:
        if _vis(cur) + len(w) + (1 if cur else 0) > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        out.append(cur)
    return out or [""]


def _accepts_player(fn):
    try:
        import inspect
        return len(inspect.signature(fn).parameters) >= 2
    except Exception:
        return False


def parse_map(text):
    """Turn a triple-quoted map into rows, dropping the first/last blank lines
    and any common left indentation."""
    rows = text.split("\n")
    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()
    ind = min((len(r) - len(r.lstrip(" ")) for r in rows if r.strip()), default=0)
    return [r[ind:] for r in rows]
