"""game_towns.py — walkable ASCII towns and ports.

Every city and port on the world map is a walkable town built with the
game_scene engine instead of a numbered menu:

* a deterministic layout per town (seeded by crc32 of "<world seed>:<name>",
  never saved — regenerated on every visit) with a town wall and gates,
  two main streets, a central plaza (fountain / oasis / fire pit / statue),
  market stalls, lamp posts, gardens, and buildings whose doors open the
  existing Town menus (inn, shop, smithy, alchemist, guild, workshop, tavern,
  trader, tailor, bank, land office, library, temple, harbour office);
* a different look for every continent (Aeloria timber & green, South Isles
  sand, palms & huts, Ironspire slate & forges, Ash Sands sandstone &
  awnings, Frostheim snow & log cabins);
* townsfolk that wander and talk (story hooks via npc_id), patrolling guards,
  stall merchants, beggars who sell hints, a town crier, children;
* dark alleys and back streets where thieves and cutthroats lurk — more at
  night, fewer near guards — and, in big towns, a hidden door to a
  Thieves' Guild (fence + Guildmaster boss);
* walkable interiors for the Inn, the Tavern and the Thieves' Guild;
* ports with a harbour district, piers, a docked ship you board by walking
  up the gangplank or talking to the captain, fishermen and smugglers.

The old numbered town menu stays reachable with [M].

Entry point used by game_world.WorldMap.enter_location:

    result = run_town(world, player, loc, autosave, town)
    # 'left' | 'defeat' | 'sailed'
"""

from __future__ import annotations

import os
import random
import zlib
from collections import deque

from game_term import C
from game_scene import (Scene, Entity, Tile, TOWN_TILES, fg, R_, B_, C_GOLD, C_DIM,
                        C_WHITE, C_RED, C_GREEN, C_CYAN, C_BLUE, C_PURP)

C_ORANGE = fg(230, 150, 60)
C_YELLOW = fg(240, 210, 90)

# ── Time of day ──────────────────────────────────────────────────
# The world has no clock of its own: one in-game day is DAY_LEN world-map
# turns, and the last stretch of every day is night.

DAY_LEN = 200
NIGHT_START = 140


def day_index(world):
    """Number of the current in-game day (0-based)."""
    try:
        return int(getattr(world, "turn_count", 0)) // DAY_LEN
    except Exception:
        return 0


def is_night(world):
    try:
        return int(getattr(world, "turn_count", 0)) % DAY_LEN >= NIGHT_START
    except Exception:
        return False


def time_label(world):
    phase = int(getattr(world, "turn_count", 0) or 0) % DAY_LEN
    if phase >= NIGHT_START:
        return "Night"
    if phase < 25:
        return "Morning"
    if phase < 110:
        return "Day"
    return "Evening"


def advance_to_morning(world):
    """Resting at an inn sleeps until the next morning."""
    try:
        t = int(world.turn_count)
        world.turn_count = (t // DAY_LEN + 1) * DAY_LEN + 5
    except Exception:
        pass


def _slug(name):
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name))
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_") or "town"


def _log_error(where, exc):
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        with open(path, "a") as f:
            f.write(f"game_towns {where}: {exc!r}\n")
    except Exception:
        pass


def _t(rgb, glyph, walk=True, name="", dark=False):
    return Tile(fg(*rgb), glyph, walk, name, dark)


# ── Continental styles ───────────────────────────────────────────
# Each style: tile keys for ground/street, building wall keys ('light' box
# drawing 1234-| or 'double' 5678HV), and palette overrides.

LIGHT = ("1", "2", "3", "4", "-", "|")
DOUBLE = ("5", "6", "7", "8", "H", "V")


def _box_palette(keys, rgb, name):
    tl, tr, bl, br, h, v = keys
    glyphs = ("┌", "┐", "└", "┘", "─", "│") if keys == LIGHT else ("╔", "╗", "╚", "╝", "═", "║")
    return {k: _t(rgb, g, False, name) for k, g in zip(keys, glyphs)}


def _style(cid):
    """Palette + layout parameters for a continent."""
    if cid == "E":      # South Isles — sand, palms, thatched huts
        pal = {
            "z": _t((222, 202, 140), ".", True, "sand"),
            ":": _t((176, 146, 96), "·", True, "dirt path"),
            "W": _t((150, 110, 60), "#", False, "bamboo fence"),
            "R": _t((205, 175, 85), "░", False, "thatched roof"),
            "T": _t((60, 175, 85), "¥", False, "palm tree"),
            "P": _t((60, 175, 85), "¥", False, "palm tree"),
        }
        pal.update(_box_palette(LIGHT, (190, 150, 80), "hut wall"))
        return dict(cid=cid, name="South Isles", ground="z", street=":", plaza=":",
                    box=LIGHT, palette=pal, centre="firepit", tree="P", flower="f",
                    colour=fg(80, 200, 160), flavour="island")
    if cid == "B":      # Ironspire — slate, stone, forges
        pal = {
            ":": _t((115, 108, 100), ".", True, "gravel"),
            ".": _t((140, 140, 150), "·", True, "flagstones"),
            "W": _t((105, 105, 118), "█", False, "fortress wall"),
            "R": _t((85, 92, 110), "▓", False, "slate roof"),
            "T": _t((130, 125, 115), "^", False, "boulder"),
        }
        pal.update(_box_palette(DOUBLE, (160, 160, 172), "stone wall"))
        return dict(cid=cid, name="Ironspire", ground=":", street=".", plaza=".",
                    box=DOUBLE, palette=pal, centre="statue", tree="T", flower="c",
                    colour=fg(175, 160, 130), flavour="mountain")
    if cid == "D":      # Ash Sands — sandstone, awnings, oasis
        pal = {
            "z": _t((215, 185, 110), ".", True, "sand"),
            ":": _t((198, 160, 96), "·", True, "sandstone paving"),
            "W": _t((200, 160, 100), "▓", False, "sandstone wall"),
            "R": _t((188, 142, 82), "░", False, "flat roof"),
            "T": _t((95, 170, 70), "¥", False, "date palm"),
            "P": _t((95, 170, 70), "¥", False, "date palm"),
            "A": _t((215, 75, 60), "▀", False, "awning"),
        }
        pal.update(_box_palette(DOUBLE, (214, 176, 116), "sandstone wall"))
        return dict(cid=cid, name="Ash Sands", ground="z", street=":", plaza=":",
                    box=DOUBLE, palette=pal, centre="oasis", tree="P", flower="P",
                    colour=fg(230, 190, 60), flavour="desert")
    if cid == "C":      # Frostheim — snow, log cabins, pines
        pal = {
            "*": _t((222, 232, 246), ".", True, "snow"),
            ".": _t((150, 150, 162), "·", True, "cobbles"),
            "W": _t((200, 215, 235), "█", False, "ice-crusted wall"),
            "R": _t((226, 236, 250), "▓", False, "snowy roof"),
            "T": _t((40, 110, 70), "♠", False, "pine"),
            "I": _t((170, 210, 240), "≈", False, "frozen pond"),
        }
        pal.update(_box_palette(LIGHT, (140, 95, 58), "log wall"))
        return dict(cid=cid, name="Frostheim", ground="*", street=".", plaza=".",
                    box=LIGHT, palette=pal, centre="frozen", tree="T", flower="T",
                    colour=fg(180, 220, 255), flavour="snow")
    # Aeloria (default) — green, timber, red roofs
    pal = {
        ",": _t((70, 140, 60), '"', True, "grass"),
        ".": _t((150, 140, 120), "·", True, "cobbles"),
        "W": _t((150, 145, 130), "█", False, "town wall"),
        "R": _t((172, 72, 52), "▒", False, "tiled roof"),
        "T": _t((40, 140, 50), "♣", False, "tree"),
    }
    pal.update(_box_palette(LIGHT, (160, 112, 64), "timber wall"))
    return dict(cid=cid or "A", name="Aeloria", ground=",", street=".", plaza=".",
                box=LIGHT, palette=pal, centre="fountain", tree="T", flower="f",
                colour=fg(80, 210, 100), flavour="forest")


# Extra tile keys used by every town (added on top of game_scene.TOWN_TILES)
COMMON_TILES = {
    "h": _t((70, 64, 60), "▒", True, "loose boards", dark=True),     # hidden door
    "d": _t((90, 75, 55), "═", True, "dark pier", dark=True),
    "M": _t((150, 110, 70), "╫", False, "mast"),
    "N": _t((235, 232, 220), "▓", False, "sail"),
    "C": _t((140, 95, 55), "▀", False, "counter"),
    "Z": _t((175, 65, 65), "■", False, "bed"),
    "_": _t((150, 115, 75), "▪", True, "wooden floor"),
}


# ── Buildings ────────────────────────────────────────────────────
# type -> (sign label, door hint, short description)
BUILDINGS = {
    "inn":       ("INN",     "Inn",                "rest & recover"),
    "tavern":    ("TAVERN",  "Tavern",             "drinks, rumours, recruits"),
    "shop":      ("SHOP",    "General Store",      "buy & sell"),
    "guild":     ("GUILD",   "Adventurers Guild",  "rank, clan, quests"),
    "smith":     ("SMITHY",  "Blacksmith",         "weapons & armour"),
    "alchemist": ("ALCHEMY", "Alchemist",          "potions & bombs"),
    "crafts":    ("CRAFTS",  "Crafting Workshop",  "craft gear"),
    "temple":    ("TEMPLE",  "Temple",             "healing & cures"),
    "bank":      ("BANK",    "Bank & Storage",     "bag & guild storage"),
    "land":      ("LAND",    "Land Office",        "your base"),
    "trader":    ("TRADER",  "Trading Post",       "barter goods"),
    "tailor":    ("TAILOR",  "Tailor",             "look & style"),
    "library":   ("LIBRARY", "Library",            "encyclopedia"),
    "harbour":   ("HARBOUR", "Harbour Office",     "ships & passage"),
}
SHORT_LABELS = {"ALCHEMY": "ALCH", "LIBRARY": "BOOKS", "HARBOUR": "DOCKS",
                "TAVERN": "ALE", "TEMPLE": "SHRINE", "SMITHY": "SMITH",
                "CRAFTS": "CRAFT", "TRADER": "TRADE", "TAILOR": "TAILR"}

# Placement priority (closest to the plaza first)
PRIORITY = ["tavern", "inn", "shop", "guild", "temple", "smith", "alchemist",
            "crafts", "bank", "land", "trader", "tailor", "library"]
REQUIRED = ["inn", "shop", "guild", "tavern"]


def town_kind(world, loc):
    """'major' (first city of its continent), 'city' or 'port'."""
    if loc.get("type") == "port":
        return "port"
    try:
        from game_world import CONTINENTS
        cont = next((c for c in CONTINENTS if c["id"] == loc.get("continent")), None)
        if cont and cont["cities"] and cont["cities"][0] == loc.get("name"):
            return "major"
    except Exception:
        pass
    return "city"


def _wanted_buildings(kind, rng):
    if kind == "major":
        return list(PRIORITY)
    optional = [b for b in PRIORITY if b not in REQUIRED]
    if kind == "port":
        rest = [b for b in optional if b != "trader"]
        rng.shuffle(rest)
        return REQUIRED + ["trader"] + rest[:rng.randint(4, 6)]
    rest = list(optional)
    rng.shuffle(rest)
    # every city keeps a smith and a temple; the rest is the town's character
    keep = ["smith", "temple"]
    rest = [b for b in rest if b not in keep]
    return REQUIRED + keep + rest[:rng.randint(4, 6)]


# ── Reachability ─────────────────────────────────────────────────

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def reachable(grid, palette, start, blocked=(), endpoints=(), passable=()):
    """Tiles the player can reach from start by walking (4-directional).

    endpoints : trigger tiles (doors/gates) — reachable but not walked through
    passable  : endpoint tiles that CAN be walked through (gangplank)
    blocked   : tiles occupied by static entities
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    blocked = set(blocked)
    endpoints = set(endpoints) - set(passable)
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        if (x, y) in endpoints and (x, y) != start:
            continue
        for dx, dy in N4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen or (nx, ny) in blocked:
                continue
            t = palette.get(grid[ny][nx])
            if t is None or not t.walkable:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


# ── Layout generator ─────────────────────────────────────────────

class TownPlan:
    """Deterministic town layout. Pure data — no Scene, no player."""

    def __init__(self, name, cid="A", kind="city", seed=0, has_ship=True):
        self.name = name
        self.slug = _slug(name)
        self.cid = cid or "A"
        self.kind = kind
        self.port = kind == "port"
        self.has_ship = has_ship and self.port
        self.rng = random.Random(zlib.crc32(f"{seed}:{name}".encode("utf-8")))
        self.style = _style(self.cid)
        self.palette = dict(TOWN_TILES)
        self.palette.update(COMMON_TILES)
        self.palette.update(self.style["palette"])
        self.buildings = []        # dicts: type,x0,y0,x1,y1,door,label,band
        self.gates = []            # (x, y)
        self.triggers = set()      # door / gate / gangplank tiles
        self.passable = set()      # triggers you may walk across
        self.statics = set()       # tiles reserved for static entities
        self.labels = []           # (x, y, text, colour)
        self.stalls = []           # (stall_x, stall_y, merchant_x, merchant_y)
        self.lamps = []
        self.guard_routes = []     # [ [(x,y),(x,y)], ... ]
        self.gate_posts = []       # tiles beside gates for gate guards
        self.hidden_door = None
        self.ship = None           # dict with gangplank, deck tiles, captain spot, name
        self.piers = []            # list of (x, y0, y1, dark)
        self.harbour_spot = None
        self.notice_spot = None
        self.crier_spot = None
        self.beggar_spots = []
        self.anvil = None
        self._generate()

    # ── grid helpers ──────────────────────────────────────────────
    def _set(self, x, y, ch):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.grid[y][x] = ch

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.grid[y][x]
        return None

    def walkable(self, x, y):
        t = self.palette.get(self.get(x, y))
        return bool(t and t.walkable)

    def reach(self, extra_block=()):
        blocked = set(self.statics) | set(extra_block)
        return reachable(self.grid, self.palette, self.start, blocked,
                         self.triggers, self.passable)

    def _ok(self, extra_block=()):
        r = self.reach(extra_block)
        if any(t not in r for t in self.triggers):
            return False
        blocked = set(self.statics) | set(extra_block)
        for (sx, sy) in blocked:
            if not any((sx + dx, sy + dy) in r for dx, dy in N8):
                return False
        return True

    def try_block(self, x, y, ch):
        """Place a non-walkable decoration only if nothing becomes unreachable."""
        if (x, y) in self.triggers or (x, y) == self.start or (x, y) in self.statics:
            return False
        old = self.get(x, y)
        if old is None:
            return False
        self._set(x, y, ch)
        if self._ok():
            return True
        self._set(x, y, old)
        return False

    def reserve_static(self, x, y):
        """Reserve a tile for an entity that never moves (merchant, guard post)."""
        if not self.walkable(x, y) or (x, y) in self.triggers or (x, y) in self.statics \
                or (x, y) == self.start:
            return False
        if self._ok(extra_block=[(x, y)]):
            self.statics.add((x, y))
            return True
        return False

    def near_door(self, x, y, r=1):
        for (tx, ty) in self.triggers:
            if abs(tx - x) <= r and abs(ty - y) <= r:
                return True
        return False

    # ── generation ────────────────────────────────────────────────
    def _generate(self):
        r = self.rng
        st = self.style
        G, S = st["ground"], st["street"]
        if self.kind == "major":
            w = r.randint(98, 108)
        elif self.kind == "city":
            w = r.randint(86, 96)
        else:
            w = r.randint(84, 94)
        hA, hB, hC, hD = (r.choice((5, 5, 6)) for _ in range(4))
        yA = 3
        s1 = yA + hA
        yB = s1 + 2
        yAl = yB + hB
        yC = yAl + 1
        s2 = yC + hC
        yD = s2 + 2
        yD2 = yD + hD - 1
        if self.port:
            board = yD2 + 1
            water0 = board + 2
            h = water0 + 9
        else:
            board = water0 = None
            h = yD2 + 4
        self.w, self.h = w, h
        self.grid = [[G] * w for _ in range(h)]
        self.rows = dict(yA=yA, hA=hA, s1=s1, yB=yB, hB=hB, yAl=yAl, yC=yC, hC=hC,
                         s2=s2, yD=yD, hD=hD, board=board, water0=water0)
        bottom_wall = None if self.port else h - 1
        wall_end = (board - 1) if self.port else h - 1

        # town wall
        for x in range(w):
            self._set(x, 0, "W")
            if bottom_wall is not None:
                self._set(x, bottom_wall, "W")
        for y in range(0, wall_end + 1):
            self._set(0, y, "W")
            self._set(w - 1, y, "W")

        # garden strips (just inside the wall) — trees & flowers, sparse
        strips = [1] + ([h - 2] if not self.port else [])
        for y in strips:
            for x in range(1, w - 1):
                if r.random() < 0.18:
                    self._set(x, y, st["tree"] if r.random() < 0.6 else st["flower"])
        # dark back streets behind the outer building rows
        backs = [2] + ([h - 3] if not self.port else [])
        for y in backs:
            for x in range(1, w - 1):
                self._set(x, y, "x")
        # ring road just inside the side walls
        for y in range(1, wall_end + (1 if self.port else 0)):
            self._set(1, y, S)
            self._set(w - 2, y, S)
        # main streets & the dark alley between the two middle rows
        for x in range(1, w - 1):
            for y in (s1, s1 + 1, s2, s2 + 1):
                self._set(x, y, S)
            self._set(x, yAl, "x")

        # main avenue (2 wide) and the plaza
        mx = w // 2 - 1
        self.mx = mx
        av_end = (board - 1) if self.port else h - 2
        for y in range(1, av_end + 1):
            self._set(mx, y, S)
            self._set(mx + 1, y, S)
        pw = r.randint(10, 13) * 2
        px0 = mx + 1 - pw // 2
        px1 = px0 + pw - 1
        self.plaza = (px0, yB, px1, s2 - 1)
        for y in range(yB, s2):
            for x in range(px0, px1 + 1):
                self._set(x, y, st["plaza"])

        # side streets through the middle rows (and sometimes the outer ones)
        carved = set(range(mx, mx + 2)) | set(range(px0, px1 + 1))
        side = [2 + (px0 - 2) // 2, px1 + 1 + (w - 3 - px1) // 2]
        self.side_streets = side
        for sx in side:
            for y in range(yB, s2):
                self._set(sx, y, S)
            if r.random() < 0.5:
                for y in range(yA, s1):
                    self._set(sx, y, S)
            if r.random() < 0.5 or self.port:
                for y in range(yD, yD2 + 1):
                    self._set(sx, y, S)

        # gates: north always; south for inland towns; east & west on the main streets
        self._gate(mx, 0)
        self._gate(mx + 1, 0)
        if bottom_wall is not None:
            self._gate(mx, bottom_wall)
            self._gate(mx + 1, bottom_wall)
        west_row = s2 if r.random() < 0.5 else s1
        east_row = s1 if west_row == s2 else s2
        for yy in (west_row, west_row + 1):
            self._gate(0, yy)
        for yy in (east_row, east_row + 1):
            self._gate(w - 1, yy)

        # where the player arrives
        if self.port:
            self.start = (1, west_row)
        else:
            self.start = (mx, h - 2)

        # harbour before buildings so the ship knows where the main pier is
        if self.port:
            self._harbour(board, water0)

        # building lots
        bands = [
            ("A", yA, yA + hA - 1, "bottom"),
            ("B", yB, yB + hB - 1, "top"),
            ("C", yC, yC + hC - 1, "bottom"),
            ("D", yD, yD2, "bottom" if self.port else "top"),
        ]
        lots = []
        for band, y0, y1, face in bands:
            for a, b in self._free_spans(y0, y1):
                lots.extend(self._lots(a, b, y0, y1, face, band))
        self._assign(lots)

        # decorations, plaza, lamps
        self._plaza_decor()
        self._lamps()
        self._clutter()
        self._routes()
        self._spots()

    def _gate(self, x, y):
        self._set(x, y, "D")
        self.gates.append((x, y))
        self.triggers.add((x, y))

    def _free_spans(self, y0, y1):
        """x-intervals in a building band not cut by streets or the plaza."""
        spans = []
        cur = None
        for x in range(2, self.w - 2):
            free = all(self.grid[y][x] == self.style["ground"] for y in range(y0, y1 + 1))
            if free:
                if cur is None:
                    cur = [x, x]
                else:
                    cur[1] = x
            elif cur is not None:
                spans.append(tuple(cur))
                cur = None
        if cur is not None:
            spans.append(tuple(cur))
        return spans

    def _lots(self, a, b, y0, y1, face, band):
        r = self.rng
        out = []
        pos = a
        while True:
            room = b - pos + 1
            if room < 7:
                break
            wdt = r.randint(7, min(15, room))
            rest = room - wdt
            if 0 < rest < 8:
                wdt = room if room <= 16 else room - 8
            out.append(dict(x0=pos, x1=pos + wdt - 1, y0=y0, y1=y1, face=face, band=band))
            pos += wdt
            if pos <= b:
                for y in range(y0, y1 + 1):
                    self._set(pos, y, "a")      # dark alley between buildings
                pos += 1
        # leftover strip: a little garden
        for x in range(pos, b + 1):
            for y in range(y0, y1 + 1):
                if self.grid[y][x] == self.style["ground"] and r.random() < 0.35:
                    self._set(x, y, self.style["tree"] if r.random() < 0.5 else self.style["flower"])
        return out

    def _assign(self, lots):
        r = self.rng
        px0, py0, px1, py1 = self.plaza
        cx, cy = (px0 + px1) // 2, (py0 + py1) // 2
        for lot in lots:
            lot["door"] = (lot["x0"] + (lot["x1"] - lot["x0"]) // 2,
                           lot["y0"] if lot["face"] == "top" else lot["y1"])
            dx, dy = lot["door"]
            lot["dist"] = abs(dx - cx) + abs(dy - cy) * 2
        wanted = _wanted_buildings(self.kind, r)
        free = sorted(lots, key=lambda l: l["dist"])
        if self.port and self.has_ship:
            # harbour office on the waterfront row, closest to the main pier
            water = [l for l in free if l["band"] == "D"]
            if water:
                best = min(water, key=lambda l: abs(l["door"][0] - self.mx))
                best["type"] = "harbour"
                free.remove(best)
        for btype in wanted:
            if not free:
                break
            lot = free.pop(0)
            lot["type"] = btype
        for lot in free:
            lot["type"] = "garden" if r.random() < 0.18 else "house"
        # hidden Thieves' Guild door on the back wall of a house next to the dark alley
        want_guild = self.kind == "major" or r.random() < 0.35
        if want_guild:
            cands = [l for l in lots if l.get("type") == "house" and l["band"] in ("B", "C")]
            if cands:
                lot = r.choice(cands)
                lot["type"] = "den"
        for lot in lots:
            self._draw_building(lot)

    def _draw_building(self, lot):
        st = self.style
        x0, x1, y0, y1 = lot["x0"], lot["x1"], lot["y0"], lot["y1"]
        btype = lot.get("type", "house")
        if btype == "garden":
            # a small open park: grass, a few trees and flower beds
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    roll = self.rng.random()
                    if roll < 0.16:
                        self._set(x, y, st["tree"])
                    elif roll < 0.26:
                        self._set(x, y, st["flower"])
            return
        tl, tr, bl, br, hz, vt = st["box"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y == y0:
                    ch = tl if x == x0 else tr if x == x1 else hz
                elif y == y1:
                    ch = bl if x == x0 else br if x == x1 else hz
                elif x in (x0, x1):
                    ch = vt
                else:
                    ch = "R"
                self._set(x, y, ch)
        dx, dy = lot["door"]
        self._set(dx, dy, "+")
        self.triggers.add((dx, dy))
        lot["label"] = ""
        if btype in BUILDINGS:
            label = BUILDINGS[btype][0]
            if len(label) > (x1 - x0 - 1):
                label = SHORT_LABELS.get(label, label[:x1 - x0 - 1])
            lot["label"] = label
            ly = (y0 + y1) // 2
            lx = x0 + 1 + ((x1 - x0 - 1) - len(label)) // 2
            self.labels.append((lx, ly, label, fg(250, 225, 150)))
        if btype == "den":
            # back wall faces the dark alley between rows B and C
            by = y1 if lot["band"] == "B" else y0
            hx = x0 + 2 + self.rng.randint(0, max(0, x1 - x0 - 4))
            if hx == dx:
                hx = min(x1 - 1, hx + 1)
            self._set(hx, by, "h")
            self.triggers.add((hx, by))
            self.hidden_door = (hx, by)
        self.buildings.append(dict(lot))

    def _harbour(self, board, water0):
        r = self.rng
        w, h = self.w, self.h
        for y in (board, board + 1):
            for x in range(0, w):
                self._set(x, y, "=")
        for y in range(water0, h):
            for x in range(0, w):
                self._set(x, y, "~")
        mx = self.mx
        # main pier (2 wide) under the avenue
        main_len = 7
        for y in range(water0, water0 + main_len):
            self._set(mx, y, "=")
            self._set(mx + 1, y, "=")
        self.piers.append((mx, water0, water0 + main_len - 1, False))
        # side piers; the far one is the dark smugglers' dock
        left = max(4, w // 6)
        right = min(w - 5, (w * 5) // 6)
        dark_left = r.random() < 0.5
        for px, dark in ((left, dark_left), (right, not dark_left)):
            ln = r.randint(4, 6)
            ch = "d" if dark else "="
            for y in range(water0, water0 + ln):
                self._set(px, y, ch)
                self._set(px + 1, y, ch)
            self.piers.append((px, water0, water0 + ln - 1, dark))
            if dark:
                # a crate stack at the end of the dark pier (one lane stays open)
                self._set(px, water0 + ln - 1, "c")
        # boats moored here and there
        for _ in range(3):
            bx = r.randint(3, w - 6)
            by = r.randint(water0 + 1, h - 2)
            if all(self.get(bx + i, by) == "~" for i in range(-1, 4)):
                for i in range(3):
                    self._set(bx + i, by, "B")
        if not self.has_ship:
            return
        # the docked ship, east of the main pier
        d = water0 + 4
        gx = mx + 2
        tpl = [
            "      N      N     ",
            "     NNN    NNN    ",
            "    NNNNN  NNNNN   ",
            " BBBBBMBBBBBBMBBBB ",
            "e________________B ",
            " BBBBBBBBBBBBBBBBB ",
            "  BBBBBBBBBBBBBBB  ",
        ]
        top = d - 4
        if gx + len(tpl[0]) >= right - 1:
            # not enough room east — dock to the west instead (mirror)
            tpl = [row[::-1] for row in tpl]
            gx = mx - len(tpl[0])
            mirrored = True
        else:
            mirrored = False
        deck = []
        gang = None
        for j, row in enumerate(tpl):
            for i, ch in enumerate(row):
                x, y = gx + i, top + j
                if ch == " " or not (0 <= x < w and 0 <= y < h):
                    continue
                self._set(x, y, ch)
                if ch == "_":
                    deck.append((x, y))
                if ch == "e":
                    gang = (x, y)
        if gang is None or not deck:
            self.has_ship = False
            return
        self.triggers.add(gang)
        self.passable.add(gang)
        deck.sort()
        cap = deck[len(deck) // 2]
        names = ["SEA WREN", "GULL'S LUCK", "TIDECALLER", "SALT QUEEN", "MORNING STAR",
                 "WAVEDANCER", "IRON GULL", "SILVER KELP"]
        sname = r.choice(names)
        hull_y = top + 5
        hx = gx + (len(tpl[0]) - len(sname)) // 2
        self.labels.append((hx, hull_y, sname, fg(240, 240, 230)))
        self.ship = dict(gangplank=gang, deck=deck, captain=cap, name=sname.title(),
                         mirrored=mirrored)

    def _plaza_decor(self):
        r = self.rng
        st = self.style
        px0, py0, px1, py1 = self.plaza
        cx, cy = (px0 + px1) // 2, (py0 + py1) // 2
        centre = st["centre"]
        if centre == "fountain":
            pat = [" uuu ", "uwwwu", " uuu "]
        elif centre == "oasis":
            pat = [" P   P ", "wwwwwww", "wwwwwww", " P   P "]
        elif centre == "firepit":
            pat = ["S   S", "  F  ", "S   S"]
        elif centre == "statue":
            pat = ["F   F", "  S  ", "F   F"]
        else:  # frozen
            pat = ["F     F", " IIIII ", " IIIII ", "F     F"]
        ph, pw = len(pat), len(pat[0])
        ox, oy = cx - pw // 2 + 1, cy - ph // 2
        for j, row in enumerate(pat):
            for i, ch in enumerate(row):
                if ch != " ":
                    self.try_block(ox + i, oy + j, ch)
        self.centre_box = (ox, oy, ox + pw - 1, oy + ph - 1)
        # market stalls along the top and bottom of the plaza
        n = r.randint(3, 5)
        xs = list(range(px0 + 2, px1 - 2, 5))
        r.shuffle(xs)
        for x in xs[:n]:
            top = r.random() < 0.5
            sy = py0 + 1 if top else py1 - 1
            my = sy + 1 if top else sy - 1
            if self.near_door(x, sy, 1) or self.near_door(x + 1, sy, 1):
                continue
            if self.try_block(x, sy, "s"):
                if not self.try_block(x + 1, sy, "s"):
                    pass
                if st["cid"] == "D":
                    ay = sy - 1 if top else sy + 1
                    if py0 <= ay <= py1:
                        self.try_block(x, ay, "A")
                        self.try_block(x + 1, ay, "A")
                if self.reserve_static(x, my):
                    self.stalls.append((x, sy, x, my))
        # lamp posts at the plaza corners
        for (lx, ly) in ((px0 + 1, py0 + 1), (px1 - 1, py0 + 1), (px0 + 1, py1 - 1), (px1 - 1, py1 - 1)):
            if self.get(lx, ly) == st["plaza"] and self.try_block(lx, ly, "L"):
                self.lamps.append((lx, ly))
        # notice board and crier near the centrepiece
        ox0, oy0, ox1, oy1 = self.centre_box
        for spot in ((ox1 + 2, cy), (ox0 - 2, cy), (cx, oy1 + 2), (cx, oy0 - 2)):
            if self.reserve_static(*spot):
                self.notice_spot = spot
                break
        for spot in ((ox0 - 2, cy + 1), (ox1 + 2, cy - 1), (cx + 2, oy1 + 1), (cx - 2, oy0 - 1)):
            if self.walkable(*spot) and spot not in self.statics:
                self.crier_spot = spot
                break

    def _lamps(self):
        """Lamp posts along the main streets, never in front of a door or alley."""
        s = self.rows
        st = self.style["street"]
        for y, side in ((s["s1"], -1), (s["s2"] + 1, 1)):
            x = 4 + self.rng.randint(0, 4)
            while x < self.w - 4:
                band = self.get(x, y + side)
                if (band not in ("a", "x", st, "+", "h") and not self.near_door(x, y, 1)
                        and self.get(x, y) == st and self.get(x, y - side) == st
                        and not (self.mx - 1 <= x <= self.mx + 2)):
                    if self.try_block(x, y, "L"):
                        self.lamps.append((x, y))
                x += self.rng.randint(9, 14)

    def _clutter(self):
        """Crates and barrels in the back streets — hiding spots for thieves."""
        r = self.rng
        dark = [(x, y) for y in range(self.h) for x in range(self.w) if self.grid[y][x] in ("x", "a")]
        r.shuffle(dark)
        placed = 0
        for (x, y) in dark:
            if placed >= 6 + self.w // 20:
                break
            if self.near_door(x, y, 1):
                continue
            if self.try_block(x, y, r.choice(("c", "b"))):
                placed += 1

    def _routes(self):
        """Guard patrol routes along straight streets (the engine walks greedily)."""
        s = self.rows
        mx = self.mx
        px0, py0, px1, py1 = self.plaza
        top = 3
        self.guard_routes.append([(mx, top), (mx, py0 - 1)])
        if self.port:
            self.guard_routes.append([(mx + 1, s["board"]), (mx + 1, py1 + 1)])
        else:
            self.guard_routes.append([(mx + 1, self.h - 3), (mx + 1, py1 + 1)])
        row = s["s1"] + 1 if self.rng.random() < 0.5 else s["s2"]
        self.guard_routes.append([(3, row), (self.w - 4, row)])
        # gate posts
        for (gx, gy) in self.gates:
            for dx, dy in N8:
                p = (gx + dx, gy + dy)
                if (0 < p[0] < self.w - 1 and 0 < p[1] < self.h and p not in self.triggers
                        and self.walkable(*p) and p != self.start
                        and not any(abs(p[0] - q[0]) + abs(p[1] - q[1]) < 3 for q in self.gate_posts)):
                    # posts must not stand in the gate's own corridor
                    if gy == 0 and p[1] == 1 and p[0] in (mx, mx + 1):
                        continue
                    if gy == self.h - 1 and p[1] == self.h - 2 and p[0] in (mx, mx + 1):
                        continue
                    if gx in (0, self.w - 1) and p[0] in (1, self.w - 2) and p[1] == gy:
                        continue
                    if self.reserve_static(*p):
                        self.gate_posts.append(p)
                        break

    def _spots(self):
        """Beggars at alley mouths, a smith's anvil outside the smithy."""
        r = self.rng
        s = self.rows
        mouths = []
        for x in range(2, self.w - 2):
            for y in (s["s1"], s["s1"] + 1, s["s2"], s["s2"] + 1):
                if self.get(x, y) != self.style["street"]:
                    continue
                if any(self.get(x, y + dy) == "a" for dy in (-1, 1)):
                    mouths.append((x, y))
        r.shuffle(mouths)
        for m in mouths:
            if len(self.beggar_spots) >= (2 if self.kind == "major" else 1):
                break
            # stand beside the mouth, not in it
            for dx in (1, -1):
                p = (m[0] + dx, m[1])
                if self.get(*p) == self.style["street"] and not self.near_door(*p, 1) \
                        and self.reserve_static(*p):
                    self.beggar_spots.append(p)
                    break
        smith = next((b for b in self.buildings if b.get("type") == "smith"), None)
        if smith:
            dx, dy = smith["door"]
            fy = dy + 1 if smith["face"] == "bottom" else dy - 1
            for ax in (dx + 2, dx - 2, dx + 3, dx - 3):
                if self.get(ax, fy) == self.style["street"] and not self.near_door(ax, fy, 1):
                    if self.try_block(ax, fy, "k"):
                        self.anvil = (ax, fy)
                        break

    # ── queries ───────────────────────────────────────────────────
    def rows_text(self):
        return ["".join(r) for r in self.grid]

    def dark_tiles(self):
        return [(x, y) for y in range(self.h) for x in range(self.w)
                if self.palette.get(self.grid[y][x]) is not None
                and self.palette[self.grid[y][x]].dark and self.walkable(x, y)
                and (x, y) not in self.triggers]

    def street_tiles(self):
        keys = (self.style["street"], self.style["plaza"])
        return [(x, y) for y in range(self.h) for x in range(self.w)
                if self.grid[y][x] in keys and (x, y) not in self.triggers
                and (x, y) not in self.statics]

    def building(self, btype):
        return next((b for b in self.buildings if b.get("type") == btype), None)


# ═══════════════════════════════════════════════════════════════
# PEOPLE — names, roles, rumours (all original text)
# ═══════════════════════════════════════════════════════════════

FIRST_NAMES = {
    "A": ["Alden", "Bryn", "Cora", "Edda", "Finn", "Gwen", "Hollis", "Ivy", "Jory", "Kestrel",
          "Lark", "Maren", "Nell", "Orrin", "Pippa", "Rowan", "Sela", "Tamsin", "Wren", "Yorick"],
    "E": ["Kai", "Leilani", "Makoa", "Nalu", "Ona", "Pika", "Rua", "Tavi", "Uli", "Wai",
          "Koa", "Mele", "Hina", "Lono", "Sina", "Tama", "Ari", "Moana"],
    "B": ["Brannoc", "Dagna", "Flint", "Garnet", "Hesk", "Korra", "Marl", "Odo", "Pell", "Rusk",
          "Slate", "Tova", "Ulric", "Vena", "Bodda", "Cobb", "Ferra", "Grist"],
    "D": ["Amir", "Bashir", "Dalia", "Farah", "Hakim", "Jamila", "Kasim", "Layla", "Nadir",
          "Omar", "Rashid", "Samira", "Tariq", "Yasmin", "Zafir", "Idris", "Nura", "Selim"],
    "C": ["Astrid", "Bjorn", "Eira", "Frode", "Gudrun", "Halla", "Ivar", "Jorunn", "Leif",
          "Sigrun", "Solveig", "Torvald", "Ulf", "Vigdis", "Yrsa", "Ragna", "Hakon", "Ingrid"],
}

# role -> (title, colour rgb, lines). Shared roles first, then per continent.
ROLES_COMMON = {
    "baker":     ("baker", (235, 200, 140), [
        "Fresh loaves at dawn, stale ones at dusk. Adventurers buy both.",
        "Flour in my hair, coin in my pocket. A good morning.",
        "You look like someone who forgets to eat before a dungeon."]),
    "washer":    ("washerwoman", (180, 200, 230), [
        "You would not believe the stains adventurers bring home. Is that... ichor?",
        "The river knows every secret in this town. So do I.",
        "Guards' tunics, merchants' silks — dirt treats everyone the same."]),
    "farmer":    ("farmer", (150, 190, 90), [
        "Wolves took two sheep last week. If you're hunting, start at the tree line.",
        "Rain's late this year. Mind you don't track mud into the inn.",
        "Came to sell turnips. Leaving with a story about a dragon. Typical."]),
    "scholar":   ("scholar", (170, 150, 230), [
        "Every dungeon floor is older than the one above it. Think about that.",
        "I catalogue monsters. From a safe distance. Mostly.",
        "The old maps show roads where the sea is now. Something broke the world."]),
    "minstrel":  ("minstrel", (230, 150, 200), [
        "Give me a heroic deed and I'll give you a verse. Maybe two.",
        "I'm composing a ballad about you. Currently it ends badly. Prove me wrong.",
        "Every tavern from here to the frozen north knows my songs. Some even like them."]),
    "old_man":   ("old-timer", (190, 180, 160), [
        "In my day we fought slimes with sticks and were grateful for the sticks.",
        "Watch the alleys after dark, youngster. The shadows have hands.",
        "I've seen four kings and three wars. The kings were worse."]),
}
NIGHT_ROLES = {
    "watchman":  ("night watchman", (120, 150, 200), [
        "Lamps are lit, gates are shut. Mostly. Keep to the main streets.",
        "Heard footsteps in the back streets. Nobody there when I looked. Nobody ever is.",
        "Third night running something's been prowling the alleys. I don't get paid enough."]),
    "drunk":     ("tipsy reveller", (210, 170, 110), [
        "*hic* I once punched a goblin. Or a very short man. Either way he deserved it.",
        "The cobbles keep moving. Have you noticed? Very rude of them.",
        "To adventure! To glory! To... where's my boot?"]),
}

ROLES_BY_CONT = {
    "A": {
        "woodcutter": ("woodcutter", (150, 110, 60), [
            "The old forest is getting darker. Even the birds keep their voices down.",
            "Split oak for winter, split goblins for coin. Only one of those pays well."]),
        "herbalist":  ("herbalist", (110, 200, 120), [
            "Moonpetal for fever, silverleaf for wounds, and never the purple ones.",
            "If you find mushrooms that glow, bring them to me. Do not eat them."]),
        "shepherd":   ("shepherd", (220, 220, 200), [
            "Something big moves through the hills at night. The flock won't graze there.",
            "I count my sheep twice a day. Lately the second count comes up short."]),
    },
    "E": {
        "fisher":     ("fisher", (90, 170, 220), [
            "Coral reef's hungry this season. Lost a net and nearly a toe.",
            "The tide brings bottles with messages. Last one just said 'RUN'."]),
        "pearl_diver": ("pearl diver", (200, 230, 240), [
            "Down past the reef there's a temple. The fish there don't blink.",
            "Hold your breath, count to ninety, grab the pearl, swim. That's the whole job."]),
        "fruit_seller": ("fruit seller", (240, 170, 80), [
            "Starfruit, sea-mango, fire-plum! Smell them — your mana thanks you already.",
            "Island fruit heals better than any city potion. Don't tell the alchemist."]),
    },
    "B": {
        "miner":      ("miner", (170, 150, 120), [
            "Deep shafts are hot this year. Hot means the mountain is awake.",
            "Found a vein of silver and a tunnel that breathes. Kept the silver."]),
        "forgehand":  ("forgehand", (240, 130, 60), [
            "Iron from Ironspire, fire from the mountain. Best steel in five lands.",
            "Hammer, quench, temper, repeat. Then the customer complains. Repeat."]),
        "mountaineer": ("mountaineer", (200, 200, 220), [
            "Saw a shadow cross the peaks — wings wider than the market square.",
            "Above the snow line, the dragon's scorch marks are still warm."]),
    },
    "D": {
        "caravaneer": ("caravaneer", (220, 180, 100), [
            "Twelve camels left Oasis Keep. Nine arrived. The desert takes its tax.",
            "Travel at dawn or dusk. Midday sun cooks the brave and the foolish alike."]),
        "water_seller": ("water seller", (110, 190, 230), [
            "Water! Cool, clean, blessed by the oasis spirit! Two coppers a cup!",
            "In the sands, a full waterskin is worth more than a full purse."]),
        "spice_trader": ("spice trader", (230, 120, 70), [
            "Saffron, ember-pepper, dune salt. One pinch and your stew sings.",
            "My spices travel further than most heroes. And return more often."]),
    },
    "C": {
        "hunter":     ("hunter", (180, 150, 110), [
            "Frost wolves hunt in packs of six. If you see one, you've already met five.",
            "Wrap your boots in fur and your sword hilt in leather. Steel bites in this cold."]),
        "ice_fisher": ("ice fisher", (170, 210, 240), [
            "Cut the hole, drop the line, wait. Sometimes something looks back up.",
            "The lake froze with a light still glowing beneath it. Nobody goes near."]),
        "skald":      ("skald", (220, 200, 140), [
            "I sing of heroes who walked into the ice caves. The songs are short.",
            "Frostheim remembers every oath. Swear carefully, stranger."]),
    },
}

GUARD_LINES = [
    "Keep your weapon sheathed inside the walls, traveller.",
    "Thieves work the back streets after dark. Stay where the lamps are.",
    "If anyone cuts your purse, shout. We come running. Eventually.",
    "Quiet shift. I like quiet shifts.",
    "Report anything strange to the guild. Strange is their business.",
    "We walk the gate to the plaza and back. The alleys are on your own head.",
]
GUARD_NIGHT_LINES = [
    "No curfew here, but it's good advice. Mind the dark corners.",
    "Lamps help. They don't help enough.",
    "Saw a knife glint near the alley mouth. Gone before I got there.",
]
CHILD_LINES = [
    "Are you a real adventurer? Show me your sword! ...Wow.",
    "My brother says there's a monster in the inn's cellar. I'm not scared. Much.",
    "Tag! You're it! ...You're not playing? Boring!",
    "When I grow up I'm going to slay a dragon. Or run a bakery. Maybe both.",
    "The man in the alley gave me a coin to say nothing. So I'm saying nothing!",
]

GLOBAL_RUMOURS = [
    "They say Castle Lumeris in Valdmere glows purple at night — the royal wards are failing.",
    "Valdmere's king is hiring sellswords. Whatever troubles the crown, it pays in gold.",
    "Up in Ironspire's black peaks stands Duskthorn Citadel. Demons — honourable ones, some say.",
    "Duskthorn's gate is held by a hound with two heads. Bring two plans.",
    "Out in the Ash Sands, the Sunspire Kasbah shimmers like a mirage. The Sultan is generous... to friends.",
    "A djinn sleeps in Sunspire's vault. Treasure hunters go in. Fewer come out.",
    "Bandit King Rourke runs the roads from a hidden hideout. His men wear red scarves.",
    "Every big town has a Thieves' Guild. Every one of them swears it doesn't.",
    "Vaeltharion the dragon nests on the highest peak in Ironspire. Its scales are worth a kingdom.",
    "The God Potions weren't brewed. Ask the scholars — they argue about it every night.",
]

DIRS = {(0, -1): "north", (0, 1): "south", (1, 0): "east", (-1, 0): "west",
        (1, -1): "north-east", (-1, -1): "north-west", (1, 1): "south-east", (-1, 1): "south-west"}


def _direction(fx, fy, tx, ty):
    dx, dy = tx - fx, ty - fy
    sx = 0 if abs(dx) < max(3, abs(dy) // 2) else (1 if dx > 0 else -1)
    sy = 0 if abs(dy) < max(3, abs(dx) // 2) else (1 if dy > 0 else -1)
    if sx == 0 and sy == 0:
        sx = 1 if dx >= 0 else -1
    return DIRS.get((sx, sy), "somewhere")


def _place_hints(world, loc, limit=3):
    """Real directions to nearby dungeons, ruins and other places."""
    out = []
    if world is None or not loc:
        return out
    lx, ly = loc.get("x", 0), loc.get("y", 0)
    try:
        places = [l for l in world.locations
                  if l is not loc and l.get("type") not in ("city", "port")
                  and l.get("continent") == loc.get("continent")]
    except Exception:
        return out
    places.sort(key=lambda l: abs(l["x"] - lx) + abs(l["y"] - ly))
    for l in places[:limit]:
        dist = int(((l["x"] - lx) ** 2 + (l["y"] - ly) ** 2) ** 0.5)
        kind = {"dungeon": "a dungeon", "mine": "a mine", "ruins": "old ruins",
                "dragon_cave": "the dragon's lair"}.get(l.get("type"), "a place worth seeing")
        out.append(f"{l['name']} — {kind} — lies about {dist} leagues "
                   f"{_direction(lx, ly, l['x'], l['y'])} of here.")
    return out


def _continent_rumours(cid):
    try:
        from game_world import CONTINENTS
        cont = next((c for c in CONTINENTS if c["id"] == cid), None)
    except Exception:
        cont = None
    if not cont:
        return []
    out = []
    for d in cont.get("dungeons", []):
        out.append(f"Folk who go down into {d} come back pale — the ones who come back.")
    if len(cont.get("cities", [])) > 1:
        out.append(f"Merchants say the road to {cont['cities'][-1]} is safe by day. By night, less so.")
    return out


# ═══════════════════════════════════════════════════════════════
# SCENE
# ═══════════════════════════════════════════════════════════════

class TownCtx:
    """Everything a town's callbacks need."""

    def __init__(self, world, player, loc, town, autosave=None, plan=None):
        self.world = world
        self.player = player
        self.loc = loc
        self.town = town
        self.autosave = autosave
        self.name = loc.get("name", "Town")
        self.slug = _slug(self.name)
        self.cid = loc.get("continent", "A") or "A"
        self.kind = town_kind(world, loc)
        self.ship_ref = None
        if world is not None and loc.get("type") == "port":
            self.ship_ref = next((s for s in getattr(world, "ships", [])
                                  if s.get("port_name") == self.name), None)
        seed = getattr(world, "seed", 0) if world is not None else 0
        self.seed = seed
        self.plan = plan or TownPlan(self.name, self.cid, self.kind, seed,
                                     has_ship=self.ship_ref is not None)
        self.style = self.plan.style
        self.night = is_night(world) if world is not None else False
        try:
            from game_world import CONTINENT_DANGER
            self.danger = CONTINENT_DANGER.get(self.cid, 2)
        except Exception:
            self.danger = 2
        self.people_rng = random.Random(zlib.crc32(f"{seed}:{self.name}:people".encode("utf-8")))
        self.ambushes = 0
        self.guild_flag = f"thieves_guild_{self.slug}"

    @property
    def guild_conquered(self):
        return bool(getattr(self.player, "flags", {}).get(self.guild_flag))


class TownScene(Scene):
    """Scene with town-specific interaction bookkeeping."""

    ctx = None
    _bump = None
    _last = None

    def _move(self, dx, dy, player):
        ent = self.entity_at(self.px + dx, self.py + dy)
        self._bump = ent if (ent is not None and ent.hostile) else None
        try:
            Scene._move(self, dx, dy, player)
        finally:
            self._bump = None

    def interact(self, player):
        adj = self.adjacent_entities()
        if adj and not any(not e.hostile for e in adj):
            self._bump = adj[0]
        try:
            Scene.interact(self, player)
        finally:
            self._bump = None

    def _talk(self, ent, player):
        Scene._talk(self, ent, player)
        if self.result is None and ent.data.get("rumour"):
            _dragon_rumour(self, player)


def _show_completions(sc, done):
    if not done:
        return
    sc.message(f"{C_GOLD}★ Story updated!{R_}")
    try:
        from game_stories import show_story_completion
        for stype, step in done:
            sc.modal(show_story_completion, stype, step)
    except Exception as e:
        _log_error("story completion", e)


def _dragon_rumour(sc, player):
    """The original 'speak to townsfolk in any city' story step."""
    st = getattr(player, "stories", None)
    if st is None:
        return
    try:
        done = st.on_talk("dragon_rumour", player)
    except Exception as e:
        _log_error("dragon_rumour", e)
        return
    _show_completions(sc, done)


def _story_check(sc, player):
    st = getattr(player, "stories", None)
    if st is not None and hasattr(st, "check_flags"):
        try:
            done = st.check_flags(player)
        except Exception:
            done = None
        _show_completions(sc, done)


def build_town_scene(ctx):
    plan = ctx.plan
    st = ctx.style
    kind_label = {"major": "capital city", "city": "town", "port": "harbour town"}.get(ctx.kind, "town")
    sub = f"{st['name']} · {kind_label} · [?] legend"
    sc = TownScene(ctx.name.upper(), plan.rows_text(), palette=plan.palette, start=plan.start,
                   subtitle=sub, colour=st["colour"], night=ctx.night, exit_on_edge=True)
    sc.ctx = ctx
    sc._last = plan.start
    for (x, y, text, col) in plan.labels:
        sc.add_label(x, y, text, col)

    for b in plan.buildings:
        btype = b.get("type", "house")
        dx, dy = b["door"]
        if btype in BUILDINGS:
            label, hint, desc = BUILDINGS[btype]
            if btype == "tavern":
                hint = _tavern_name(ctx)
            sc.add_door(dx, dy, f"Enter {hint} · {desc}", _door_fn(btype, b))
        else:
            sc.add_door(dx, dy, "Knock on the door", _house_fn(b))
    for (gx, gy) in plan.gates:
        sc.add_door(gx, gy, "Leave town", _gate_fn, step_back=False, tile="D")
    if plan.hidden_door:
        hx, hy = plan.hidden_door
        sc.add_door(hx, hy, "Loose boards in the wall... push them?", _hidden_door_fn, tile="h")
    if plan.ship:
        gx, gy = plan.ship["gangplank"]
        sc.add_door(gx, gy, f"Gangplank of the {plan.ship['name']}", _gangplank_fn,
                    step_back=False, tile="e")

    _populate(sc, ctx)

    sc.on_turn.append(_track_pos)
    sc.on_turn.append(_lurker_tick)
    sc.add_key("m", "Menu", _old_menu)
    sc.add_key("p", "Save", _save_key)
    sc.hud_extra = _hud
    return sc


def _hud(sc, player):
    ctx = sc.ctx
    if ctx.night:
        t = f"{C_BLUE}{B_}Night{R_}"
    else:
        lbl = time_label(ctx.world) if ctx.world is not None else "Day"
        t = f"{C_YELLOW}{lbl}{R_}"
    return f"{C_DIM}·{R_} {t}"


def _track_pos(sc, player):
    sc._last = (sc.px, sc.py)
    return None


def _tavern_name(ctx):
    r = random.Random(zlib.crc32(f"{ctx.seed}:{ctx.name}:tavern".encode("utf-8")))
    adj = ["Rusty", "Gilded", "Drunken", "Sleeping", "Laughing", "Salty", "Copper", "Wandering",
           "Crooked", "Merry", "Frozen", "Sunburnt", "Iron", "Lucky"]
    noun = ["Anchor", "Goose", "Dragon", "Barrel", "Mermaid", "Boar", "Lantern", "Kettle",
            "Stag", "Gull", "Camel", "Anvil", "Wolf", "Moon"]
    return f"The {r.choice(adj)} {r.choice(noun)}"


# ── door callbacks ───────────────────────────────────────────────

def _door_fn(btype, b):
    def fn(sc, pl):
        return _enter_building(sc, pl, btype, b)
    return fn


def _gate_fn(sc, pl):
    sc.leave("left")
    return None


def _house_fn(b):
    def fn(sc, pl):
        if b.get("type") == "den":
            return f"{C_DIM}The door is barred from inside. Odd, for a house that looks empty.{R_}"
        lines = [
            "Nobody answers. A cat watches you from the window.",
            "A voice calls: 'We gave at the temple already!'",
            "You hear a lullaby through the door. Best not to knock again.",
            "An old woman opens up, squints at you, and shuts the door. Firmly.",
            "'If you're selling something, the market's in the plaza!'",
            "The smell of stew drifts out. Someone inside laughs.",
        ]
        return f"{C_DIM}{random.choice(lines)}{R_}"
    return fn


def _modal(sc, fn, *a, **kw):
    try:
        return sc.modal(fn, *a, **kw)
    except Exception as e:
        _log_error(f"modal {getattr(fn, '__name__', fn)}", e)
        sc.message(f"{C_RED}Something went wrong in there — the door is stuck.{R_}")
        return None


def _enter_building(sc, pl, btype, b):
    ctx = sc.ctx
    town = ctx.town
    if btype == "inn":
        return _enter_interior(sc, pl, _inn_interior(ctx))
    if btype == "tavern":
        return _enter_interior(sc, pl, _tavern_interior(ctx))
    if btype == "shop":
        _modal(sc, town.shop)
    elif btype == "guild":
        ch = sc.choice_box("The Adventurers Guild. Maps, trophies and a very busy clerk.",
                           [("g", "Guild hall · rank up, clan, awakening"),
                            ("q", "Quest board · take & turn in quests"),
                            ("l", "Leave")])
        if ch == "g":
            _modal(sc, town.adventure_guild)
        elif ch == "q":
            _modal(sc, town.quest_board)
    elif btype == "smith":
        _modal(sc, _filtered_shop, town, lambda it: hasattr(it, "slot"), "Blacksmith")
    elif btype == "alchemist":
        _modal(sc, _filtered_shop, town, lambda it: not hasattr(it, "slot"), "Alchemist")
    elif btype == "crafts":
        _modal(sc, town.crafting_bench)
    elif btype == "temple":
        return _temple(sc, pl)
    elif btype == "bank":
        _modal(sc, town.inventory_screen)
    elif btype == "land":
        _modal(sc, town._base_menu)
    elif btype == "trader":
        from game_trading import open_trader_in_town
        _modal(sc, open_trader_in_town, pl, ctx.name)
    elif btype == "tailor":
        from game_customise import open_customise
        _modal(sc, open_customise, pl)
    elif btype == "library":
        from game_codex import open_encyclopedia
        _modal(sc, open_encyclopedia, pl)
    elif btype == "harbour":
        return _harbour_office(sc, pl)
    return None


def _swap_shop(town, stock, title):
    """Run Town.shop with a different stock list and title."""
    orig_stock = town.shop_stock
    town.shop_stock = stock
    orig = town._header
    town._header = lambda subtitle="": orig(str(subtitle).replace("Shop", title))
    try:
        town.shop()
    finally:
        town.shop_stock = orig_stock
        try:
            del town._header
        except AttributeError:
            pass


def _filtered_shop(town, pred, title):
    """Town.shop restricted to part of the stock (smithy, alchemist)."""
    sub = [(it, price) for (it, price) in town.shop_stock if pred(it)] or town.shop_stock
    _swap_shop(town, sub, title)


def _temple(sc, pl):
    heal_cost = 6 + pl.level * 2
    cure_cost = 8 + pl.level
    ailing = bool(getattr(pl, "status_effects", []))
    gods = {"A": "the Green Mother", "E": "the Tide Spirits", "B": "the Forge Father",
            "D": "the Sun Above", "C": "the Frost Mother"}
    god = gods.get(sc.ctx.cid, "the Light")
    opts = [("h", f"Healing prayer · restore HP & MP  ({heal_cost}g)"),
            ("c", f"Cleansing · cure all ailments  ({cure_cost}g)" + ("" if ailing else "  - you are well")),
            ("p", "Pray quietly"),
            ("l", "Leave")]
    ch = sc.choice_box(f"Candles flicker before the altar of {god}. A priest bows to you.", opts)
    if ch == "h":
        if pl.gold < heal_cost:
            return f"{C_RED}You need {heal_cost}g for the healing prayer.{R_}"
        pl.gold -= heal_cost
        pl.hp = pl.max_hp
        pl.mp = pl.max_mp
        return f"{C_GREEN}Warm light washes over you. HP and MP fully restored.{R_}"
    if ch == "c":
        if not ailing:
            return f"{C_DIM}'You carry no curse or poison, child. Keep your coin.'{R_}"
        if pl.gold < cure_cost:
            return f"{C_RED}You need {cure_cost}g for the cleansing.{R_}"
        pl.gold -= cure_cost
        pl.status_effects.clear()
        return f"{C_GREEN}The priest sprinkles holy water. Your ailments fade away.{R_}"
    if ch == "p":
        lines = [f"You kneel before {god}. For a moment the world is very quiet.",
                 "A whisper in your mind: 'Not every battle is won with a blade.'",
                 "The candle flames lean toward you, then settle. You feel watched — kindly."]
        return f"{C_CYAN}{random.choice(lines)}{R_}"
    return None


def _board(sc, pl):
    ctx = sc.ctx
    if ctx.world is None or ctx.ship_ref is None:
        return f"{C_DIM}No ship is moored here today.{R_}"
    ok = _modal(sc, ctx.world._board_ship, pl, ctx.ship_ref)
    if ok:
        sc.leave("sailed")
        return None
    return f"{C_DIM}You stay ashore.{R_}"


def _harbour_office(sc, pl):
    ch = sc.choice_box("The harbour office smells of tar and ink. Sea charts cover every wall.",
                       [("b", "Book passage on the ship"), ("a", "Ask about the sea"), ("l", "Leave")])
    if ch == "b":
        return _board(sc, pl)
    if ch == "a":
        lines = ["Storms are worst on the long crossings. Keep potions handy.",
                 "Every port has a ship. Fares depend on distance, not on how nicely you ask.",
                 "Sailors swear the South Isles have a reef that sings at night."]
        return f"{C_CYAN}'{random.choice(lines)}'{R_}"
    return None


def _gangplank_fn(sc, pl):
    ship = sc.ctx.plan.ship
    gx, gy = ship["gangplank"]
    last = sc._last or (gx, gy)
    from_deck = (last[0] > gx) if not ship.get("mirrored") else (last[0] < gx)
    if from_deck:
        return f"{C_DIM}You step down the gangplank.{R_}"
    ch = sc.choice_box(f"The {ship['name']} creaks at her moorings. Set sail?",
                       [("s", "Choose a destination and sail"), ("w", "Just walk aboard"),
                        ("l", "Stay on the pier")])
    if ch == "s":
        msg = _board(sc, pl)
        if sc.result is None:
            sc.px, sc.py = last
        return msg
    if ch == "w":
        return f"{C_DIM}You walk up the gangplank onto the deck.{R_}"
    sc.px, sc.py = last
    return None


def _old_menu(sc, pl):
    ctx = sc.ctx
    w = ctx.world
    before = (w.player_x, w.player_y) if w is not None else None
    _modal(sc, ctx.town.enter)
    if w is not None and (w.player_x, w.player_y) != before:
        sc.leave("sailed")
    return None


def _save_key(sc, pl):
    _modal(sc, sc.ctx.town._save_game)
    return None


def _enter_interior(sc, pl, inner):
    if inner is None:
        return None
    try:
        res = inner.run(pl)
    except Exception as e:
        _log_error("interior", e)
        res = "left"
    if res == "defeat" or not pl.is_alive():
        sc.leave("defeat")
    elif res == "sailed":
        sc.leave("sailed")
    sc.night = sc.ctx.night
    return None


# ═══════════════════════════════════════════════════════════════
# POPULATION
# ═══════════════════════════════════════════════════════════════

def _person(x, y, name, title, rgb, lines, npc_id, ai="wander", radius=6, glyph="@",
            kind="npc", interact=None, rumour=True, **data):
    d = {"rumour": rumour}
    d.update(data)
    return Entity(x, y, glyph, fg(*rgb), name, kind=kind, lines=lines, ai=ai,
                  radius=radius, npc_id=npc_id, title=title, interact=interact, data=d)


def _free_spot(sc, spots, rng, avoid=(), min_dist=0, far_from=None):
    """Pick a walkable, unoccupied, non-trigger spot from a candidate list."""
    cands = list(spots)
    rng.shuffle(cands)
    for (x, y) in cands:
        if (x, y) in sc.triggers or (x, y) == (sc.px, sc.py) or (x, y) in avoid:
            continue
        if not sc.walkable(x, y):
            continue
        if far_from is not None and max(abs(x - far_from[0]), abs(y - far_from[1])) < min_dist:
            continue
        return (x, y)
    return None


def _static_spot(sc, plan, cands, avoid=()):
    """First candidate where a never-moving NPC blocks no door or path."""
    for p in cands:
        if p in avoid or p in sc.triggers or not sc.walkable(*p):
            continue
        if plan.reserve_static(*p):
            return p
    return None


def _populate(sc, ctx):
    plan = ctx.plan
    pr = ctx.people_rng            # stable per town: the same folk every visit
    names = list(FIRST_NAMES.get(ctx.cid, FIRST_NAMES["A"]))
    pr.shuffle(names)
    name_iter = iter(names * 3)
    streets = plan.street_tiles()
    reserved = set(plan.statics)
    occupied = set()

    def spot(pool, **kw):
        p = _free_spot(sc, pool, pr, avoid=reserved | occupied, **kw)
        if p:
            occupied.add(p)
        return p

    rumours = (GLOBAL_RUMOURS + _continent_rumours(ctx.cid) + _place_hints(ctx.world, ctx.loc))

    # ── townsfolk ──
    roles = dict(ROLES_COMMON)
    roles.update(ROLES_BY_CONT.get(ctx.cid, {}))
    role_keys = sorted(roles)
    n = {"major": pr.randint(12, 15), "city": pr.randint(9, 12), "port": pr.randint(8, 11)}[ctx.kind]
    if ctx.night:
        n = max(4, n // 2)
    for i in range(n):
        role = role_keys[i % len(role_keys)] if i < len(role_keys) else pr.choice(role_keys)
        title, rgb, lines = roles[role]
        p = spot(streets)
        if not p:
            break
        lines = list(lines) + pr.sample(rumours, min(2, len(rumours)))
        sc.add_entity(_person(p[0], p[1], next(name_iter), title, rgb, lines,
                              f"{ctx.slug}_{role}", radius=7))
    if ctx.night:
        for role, (title, rgb, lines) in NIGHT_ROLES.items():
            p = spot(streets)
            if p:
                sc.add_entity(_person(p[0], p[1], next(name_iter), title, rgb,
                                      list(lines) + pr.sample(rumours, 1), f"{ctx.slug}_{role}"))

    # ── famous travellers from the old town menu (with their special offers) ──
    try:
        from game_systems import TOWNSFOLK
    except Exception:
        TOWNSFOLK = []
    if TOWNSFOLK:
        k = 3 if ctx.kind == "major" else 2
        for npc in pr.sample(TOWNSFOLK, min(k, len(TOWNSFOLK))):
            p = spot(streets)
            if p:
                sc.add_entity(_person(p[0], p[1], npc["name"], npc.get("personality", ""),
                                      (240, 220, 160), npc["lines"],
                                      f"{ctx.slug}_{_slug(npc['name'])}", radius=5,
                                      interact=_traveller_interact, offer=npc.get("offer")))

    # ── children (daytime) ──
    if not ctx.night:
        for _ in range(pr.randint(1, 2)):
            p = spot(streets)
            if p:
                sc.add_entity(_person(p[0], p[1], next(name_iter), "child", (250, 230, 200),
                                      CHILD_LINES, f"{ctx.slug}_child", radius=5, glyph="o"))

    # ── guards ──
    guard_rgb = (130, 170, 230)
    for route in plan.guard_routes:
        a, b = route
        if not sc.walkable(*a) or a in occupied:
            continue
        occupied.add(a)
        lines = GUARD_LINES + (GUARD_NIGHT_LINES if ctx.night else [])
        g = _person(a[0], a[1], f"Guard {next(name_iter)}", "town guard", guard_rgb, lines,
                    f"{ctx.slug}_guard", ai="patrol", glyph="G", kind="guard", rumour=False)
        g.patrol = [a, b]
        sc.add_entity(g)
    for p in plan.gate_posts:
        sc.add_entity(_person(p[0], p[1], f"Guard {next(name_iter)}", "gate guard", guard_rgb,
                              GUARD_LINES, f"{ctx.slug}_gate_guard", ai="static", glyph="G",
                              kind="guard", rumour=False))

    # ── stall merchants ──
    wares = ["fruit & potions", "trinkets & rings", "travel gear", "bombs & tonics",
             "fresh bread & ether", "odds & ends"]
    for i, (sx, sy, mx, my) in enumerate(plan.stalls):
        theme = wares[(i + pr.randint(0, 5)) % len(wares)]
        ent = _person(mx, my, f"{next(name_iter)}", f"stall · {theme}", (240, 200, 90),
                      ["Best prices in town!", "Take a look, take a look!"],
                      f"{ctx.slug}_merchant", ai="static", glyph="$", kind="merchant",
                      interact=_stall_interact, stall=i, theme=theme)
        sc.add_entity(ent)

    # ── notice board, crier, beggars ──
    if plan.notice_spot:
        x, y = plan.notice_spot
        sc.add_entity(Entity(x, y, "Ξ", fg(210, 180, 120), "Notice Board", kind="object",
                             interact=_notice_interact, title="quests & bounties"))
    if plan.crier_spot and plan.crier_spot not in occupied:
        x, y = plan.crier_spot
        occupied.add((x, y))
        if ctx.night:
            sc.add_entity(_person(x, y, next(name_iter), "lamplighter", (255, 220, 120),
                                  ["Every lamp I light is one less shadow for the cutpurses.",
                                   "Mind the alleys. I don't light those. Nobody pays for those."],
                                  f"{ctx.slug}_lamplighter", radius=3))
        else:
            sc.add_entity(_person(x, y, next(name_iter), "town crier", (255, 215, 0), [],
                                  f"{ctx.slug}_crier", radius=3, interact=_crier_interact))
    for (x, y) in plan.beggar_spots:
        sc.add_entity(_person(x, y, next(name_iter), "beggar", (150, 130, 110), [],
                              f"{ctx.slug}_beggar", ai="static", interact=_beggar_interact,
                              rumour=False))

    # ── smith at the anvil ──
    if plan.anvil:
        ax, ay = plan.anvil
        p = _static_spot(sc, plan, [(ax + dx, ay + dy) for dx, dy in N4], avoid=reserved | occupied)
        if p:
            occupied.add(p)
            sc.add_entity(_person(p[0], p[1], next(name_iter), "blacksmith", (240, 140, 70),
                                  ["Clang. Clang. Clang. ...Oh! A customer.",
                                   "Steel remembers every blow. So do I."],
                                  f"{ctx.slug}_blacksmith", ai="static", rumour=False,
                                  interact=_smith_interact))

    # ── harbour ──
    if ctx.kind == "port":
        _populate_harbour(sc, ctx, name_iter, occupied, reserved)

    # ── lurkers in the dark ──
    _spawn_lurkers(sc, ctx, occupied)


def _populate_harbour(sc, ctx, name_iter, occupied, reserved):
    plan = ctx.plan
    pr = ctx.people_rng
    board = plan.rows["board"]
    # dockmaster near the harbour office door (or the main pier)
    hb = plan.building("harbour")
    near = []
    if hb:
        dx, dy = hb["door"]
        near = [(dx + 2, dy + 1), (dx - 2, dy + 1), (dx + 3, dy + 1), (dx + 2, dy + 2)]
    near += [(plan.mx - 1, board + 1), (plan.mx + 2, board + 1)]
    p = _static_spot(sc, plan, near, avoid=reserved | occupied)
    if p:
        occupied.add(p)
        sc.add_entity(_person(p[0], p[1], next(name_iter), "dockmaster", (90, 200, 230), [],
                              f"{ctx.slug}_dockmaster", ai="static", interact=_dockmaster_interact,
                              rumour=False))
    # captain & sailors on deck
    if plan.ship:
        cx, cy = plan.ship["captain"]
        if _static_spot(sc, plan, [(cx, cy)], avoid=occupied):
            occupied.add((cx, cy))
            sc.add_entity(_person(cx, cy, f"Captain {next(name_iter)}", f"master of the {plan.ship['name']}",
                                  (240, 240, 240), [], f"{ctx.slug}_captain", ai="static",
                                  interact=_captain_interact, rumour=False))
        deck = [d for d in plan.ship["deck"] if d not in occupied]
        for _ in range(2):
            p = _free_spot(sc, deck, pr, avoid=occupied)
            if p:
                occupied.add(p)
                sc.add_entity(_person(p[0], p[1], next(name_iter), "sailor", (120, 180, 220),
                                      ["Haul! ...Oh, sorry, thought you were the bosun.",
                                       "Fair winds today. Captain's in a good mood. Ask now.",
                                       "Never whistle on deck. Calls the storm. Ask me how I know."],
                                      f"{ctx.slug}_sailor", radius=2))
    # fishermen at the ends of the lit piers
    for (px, y0, y1, dark) in plan.piers:
        if dark:
            continue
        p = _static_spot(sc, plan, [(px, y1), (px + 1, y1)], avoid=occupied)
        if p and pr.random() < 0.8:
            occupied.add(p)
            sc.add_entity(_person(p[0], p[1], next(name_iter), "fisher", (90, 170, 220),
                                  ["Shh. You'll scare the fish. And me.",
                                   "Caught a fish with a ring in its belly once. Didn't fit me.",
                                   "The dark pier over there? Nobody fishes there. Nobody honest."],
                                  f"{ctx.slug}_fisher", ai="static"))


# ── friendly interactions ────────────────────────────────────────

def _traveller_interact(sc, pl, ent):
    sc.talk_box(ent, random.choice(ent.lines) if ent.lines else "...", pl)
    offer = ent.data.get("offer")
    if not offer or ent.data.get("offered"):
        return None
    try:
        from game_systems import OFFER_RESPONSES
    except Exception:
        return None
    if offer not in OFFER_RESPONSES:
        return None
    ch = sc.choice_box("(They seem willing to share more...)",
                       [("y", "Interact further"), ("n", "Just listen")], ent)
    if ch != "y":
        return None
    ent.data["offered"] = True
    resp = random.choice(OFFER_RESPONSES[offer])
    if offer == "blessing":
        pl.hp = pl.max_hp
        resp += "  Your HP is fully restored!"
    elif offer == "secret":
        pl.gold += 1
        resp += "  (+1 gold)"
    sc.talk_box(ent, resp, pl)
    return None


def _crier_interact(sc, pl, ent):
    ctx = sc.ctx
    news = []
    st = getattr(pl, "stories", None)
    try:
        step = st.get_main_step() if st is not None else None
        if step:
            news.append(f"Hear ye! The realm needs heroes! Word is: {step['desc']}")
    except Exception:
        pass
    news.append("Hear ye! " + random.choice(GLOBAL_RUMOURS))
    hints = _place_hints(ctx.world, ctx.loc, 2)
    if hints:
        news.append("Travellers take note: " + random.choice(hints))
    for line in news[:2]:
        sc.talk_box(ent, line, pl)
    return None


def _beggar_interact(sc, pl, ent):
    ctx = sc.ctx
    ch = sc.choice_box("'Spare a coin, friend? I see things. I hear things.'",
                       [("1", "Give 1 gold"), ("5", "Give 5 gold"), ("n", "Walk on")], ent)
    if ch not in ("1", "5"):
        return None
    amt = int(ch)
    if pl.gold < amt:
        return f"{C_DIM}Your purse is lighter than you thought.{R_}"
    pl.gold -= amt
    hints = []
    if amt >= 5 and ctx.plan.hidden_door:
        hints.append("Bless you. Listen: there's a house by the dark alley with loose boards "
                     "on its back wall. Push them. Tell nobody I said so.")
    hints += _place_hints(ctx.world, ctx.loc, 3)
    hints.append("Stick to the lamps after dark. The cutpurses hate the light.")
    line = hints[0] if amt >= 5 else random.choice(hints)
    sc.talk_box(ent, line, pl)
    return None


def _notice_interact(sc, pl, ent):
    _modal(sc, sc.ctx.town.quest_board)
    return None


def _smith_interact(sc, pl, ent):
    ch = sc.choice_box("'Need something forged, mended or sharpened?'",
                       [("b", "Browse weapons & armour"), ("c", "Use the crafting bench"),
                        ("n", "Not now")], ent)
    if ch == "b":
        _modal(sc, _filtered_shop, sc.ctx.town, lambda it: hasattr(it, "slot"), "Blacksmith")
    elif ch == "c":
        _modal(sc, sc.ctx.town.crafting_bench)
    return None


def _stall_interact(sc, pl, ent):
    ctx = sc.ctx
    day = day_index(ctx.world)
    r = random.Random(zlib.crc32(f"{ctx.name}:stall{ent.data.get('stall')}:{day}".encode("utf-8")))
    stock = list(ctx.town.shop_stock)
    r.shuffle(stock)
    items = stock[:r.randint(3, 5)]
    sc.talk_box(ent, f"Today's {ent.data.get('theme', 'wares')}! Fresh this morning!", pl)
    _modal(sc, _swap_shop, ctx.town, items, f"{ent.name}'s Stall")
    return None


def _dockmaster_interact(sc, pl, ent):
    ch = sc.choice_box("'Passage, cargo or gossip? I deal in all three.'",
                       [("b", "Book passage on the ship"), ("g", "Gossip"), ("n", "Nothing")], ent)
    if ch == "b":
        return _board(sc, pl)
    if ch == "g":
        lines = ["Smugglers work the dark pier at night. The guards pretend not to see.",
                 "A ship came in with a hold full of sand and a captain who wouldn't speak.",
                 "Pearl Harbour pays the best for coral. Don't ask how I know."]
        sc.talk_box(ent, random.choice(lines), pl)
    return None


def _captain_interact(sc, pl, ent):
    ch = sc.choice_box(f"'Welcome aboard the {sc.ctx.plan.ship['name']}. Where are we bound?'",
                       [("s", "Show me the destinations"), ("n", "Not yet")], ent)
    if ch == "s":
        return _board(sc, pl)
    return None


# ═══════════════════════════════════════════════════════════════
# DARK CORNERS — thieves, cutthroats, bandits, smugglers
# ═══════════════════════════════════════════════════════════════

LURKERS = {
    # kind: (enemy name, entity name, colour)
    "thief":    ("Alley Thief", "Alley Thief", (175, 150, 215)),
    "cutthroat": ("Cutthroat", "Cutthroat", (225, 85, 85)),
    "bandit":   ("Bandit", "Bandit", (215, 140, 80)),
    "assassin": ("Desert Assassin", "Desert Assassin", (230, 120, 60)),
    "smuggler": ("Cutthroat", "Smuggler", (160, 160, 120)),
}


def _make_lurker(ctx, x, y, kind):
    enemy, name, rgb = LURKERS.get(kind, LURKERS["cutthroat"])
    perceptive = getattr(getattr(ctx.player, "job", None), "name", "") in ("Rogue", "Shadow Assassin")
    contact = {"thief": _thief_contact, "bandit": _bandit_contact}.get(kind, _cutthroat_contact)
    return Entity(x, y, "&", fg(*rgb), name, kind="bandit", ai="lurk", hostile=True,
                  lurk=True, reveal_radius=3 if perceptive else 2, on_contact=contact,
                  title={"thief": "cutpurse", "smuggler": "smuggler"}.get(kind, "lurking in the dark"),
                  data={"enemy": enemy, "lkind": kind})


def _guard_spots(sc):
    pts = []
    for e in sc.entities:
        if e.kind == "guard" and e.alive:
            pts.append((e.x, e.y))
            pts.extend(e.patrol)
    return pts


def _near_guard(sc, x, y, r):
    return any(max(abs(x - gx), abs(y - gy)) <= r for (gx, gy) in _guard_spots(sc))


def _lurker_kind(ctx, rng):
    roll = rng.random()
    if ctx.night:
        kind = "thief" if roll < 0.35 else ("cutthroat" if roll < 0.7 else "bandit")
        if kind == "cutthroat" and ctx.cid == "D" and rng.random() < 0.5:
            kind = "assassin"
        return kind
    return "thief" if roll < 0.6 else ("cutthroat" if roll < 0.85 else "bandit")


def _spawn_lurkers(sc, ctx, occupied):
    rng = random.Random()
    plan = ctx.plan
    if ctx.night:
        count = 3 + (2 if ctx.kind == "major" else 0) + rng.randint(0, 1)
    else:
        count = 1 + (1 if ctx.kind == "major" else 0)
    if ctx.guild_conquered:
        count = max(0, count - 2)
    dark = [p for p in plan.dark_tiles() if not (ctx.kind == "port" and sc.tile_at(*p).name == "dark pier")]
    for _ in range(count):
        p = _free_spot(sc, dark, rng, avoid=occupied, min_dist=10, far_from=plan.start)
        if not p or _near_guard(sc, p[0], p[1], 6):
            continue
        occupied.add(p)
        sc.add_entity(_make_lurker(ctx, p[0], p[1], _lurker_kind(ctx, rng)))
    # smugglers on the dark pier at night
    if ctx.kind == "port" and ctx.night:
        pier = [(x, y) for (x, y) in plan.dark_tiles() if sc.tile_at(x, y).name == "dark pier"]
        for _ in range(rng.randint(1, 2)):
            p = _free_spot(sc, pier, rng, avoid=occupied)
            if p:
                occupied.add(p)
                sc.add_entity(_make_lurker(ctx, p[0], p[1], "smuggler"))


def _lurker_tick(sc, player):
    """Per-step: fleeing thieves, guards chasing off lurkers, ambush rolls."""
    ctx = sc.ctx
    msgs = []
    guards = [e for e in sc.entities if e.alive and e.kind == "guard"]
    for e in list(sc.entities):
        if not e.alive or e.kind != "bandit":
            continue
        if e.revealed and "reveal_turn" not in e.data:
            e.data["reveal_turn"] = sc.turns
        if e.data.get("fleeing"):
            m = _flee_step(sc, player, e, guards)
            if m:
                msgs.append(m)
            continue
        if e.revealed:
            for g in guards:
                if max(abs(g.x - e.x), abs(g.y - e.y)) <= 3:
                    e.alive = False
                    msgs.append(f"{C_CYAN}{g.name} shouts — the {e.name} melts back into the shadows!{R_}")
                    break
    # ambush roll on dark tiles
    t = sc.tile_at(sc.px, sc.py)
    if t is not None and t.dark and ctx.ambushes < 3:
        near_lurker = any(e.alive and e.kind == "bandit" and
                          max(abs(e.x - sc.px), abs(e.y - sc.py)) <= 6 for e in sc.entities)
        if not near_lurker and not _near_guard(sc, sc.px, sc.py, 7):
            chance = 0.06 if ctx.night else 0.015
            if ctx.guild_conquered:
                chance /= 2
            if random.random() < chance:
                ring = [(sc.px + dx, sc.py + dy) for dx in range(-3, 4) for dy in range(-3, 4)
                        if 2 <= max(abs(dx), abs(dy)) <= 3]
                ring = [p for p in ring if sc.tile_at(*p) is not None and sc.tile_at(*p).dark]
                p = _free_spot(sc, ring, random)
                if p:
                    ctx.ambushes += 1
                    sc.add_entity(_make_lurker(ctx, p[0], p[1], _lurker_kind(ctx, random)))
    return "  ".join(msgs) if msgs else None


def _flee_step(sc, player, e, guards):
    e.data["flee_turns"] = e.data.get("flee_turns", 0) + 1
    stolen = e.data.get("stolen", 0)
    for g in guards:
        if max(abs(g.x - e.x), abs(g.y - e.y)) <= 2:
            e.alive = False
            player.gold += stolen
            return f"{C_GREEN}{g.name} tackles the thief! Your {stolen} gold is returned.{R_}"
    dist = max(abs(e.x - sc.px), abs(e.y - sc.py))
    if e.data["flee_turns"] > 28 or dist > 15:
        e.alive = False
        return f"{C_RED}The thief vanishes into the alleys with your {stolen} gold.{R_}"
    if e.data["flee_turns"] % 3 == 0:
        return None                  # stumbles — your chance to catch up
    best = None
    for dx, dy in N4:
        nx, ny = e.x + dx, e.y + dy
        if (nx, ny) == (sc.px, sc.py) or (nx, ny) in sc.triggers or not sc.walkable(nx, ny, ignore=e):
            continue
        d = abs(nx - sc.px) + abs(ny - sc.py)
        if best is None or d > best[0]:
            best = (d, nx, ny)
    if best:
        e.x, e.y = best[1], best[2]
    return None


def _make_enemy(ctx, name):
    from game_enemies import generate_enemy
    lvl = getattr(ctx.player, "level", 1)
    try:
        return generate_enemy("plains", ctx.danger, lvl, name=name)
    except Exception:
        return generate_enemy("plains", ctx.danger, lvl)


def _make_boss(name, level):
    try:
        from game_enemies import create_boss
        return create_boss(name, level)
    except Exception:
        from game_enemies import generate_enemy
        e = generate_enemy("plains", 4, level)
        try:
            e.name = name
            e.hp = e.max_hp = int(getattr(e, "max_hp", e.hp) * 3)
        except Exception:
            pass
        return e


def _loot_bonus(player):
    """Small extra reward for clearing a dark corner."""
    try:
        from game_items import make_item
        item = make_item(random.choice(["Potion", "Smoke Bomb", "Antidote", "Ether"]))
    except Exception:
        item = None
    if item is None:
        try:
            from game_items import ITEM_POOL
            item = ITEM_POOL["Potion"]()
        except Exception:
            item = None
    if item is not None and random.random() < 0.35 and player.add_item(item):
        return f" Found {item.name} on them."
    return ""


def _fight_lurker(sc, pl, ent, ambush=False):
    ctx = sc.ctx
    enemy = _make_enemy(ctx, ent.data.get("enemy", "Bandit"))
    if ambush:
        dmg = max(1, int(pl.max_hp * random.uniform(0.06, 0.12)))
        pl.hp = max(1, pl.hp - dmg)
        sc.talk_box(ent, f"The {ent.name} lunges from the shadows! A blade bites deep. (-{dmg} HP)", pl)
    res = sc.fight(pl, enemy, first_strike=not ambush)
    stolen = ent.data.get("stolen", 0)
    if res == "victory":
        ent.alive = False
        purse = random.randint(4, 12) + pl.level
        pl.gold += purse + stolen
        if enemy.name != "Bandit":
            # cutpurses and cutthroats count toward the bandit side story
            try:
                done = pl.stories.on_kill("Bandit", pl)
                _show_completions(sc, done)
            except Exception:
                pass
        back = f" Recovered your {stolen} gold!" if stolen else ""
        return f"{C_GOLD}The {ent.name} is beaten. +{purse}g from their purse.{back}{_loot_bonus(pl)}{R_}"
    if res == "escaped":
        if stolen:
            ent.alive = False
            return f"{C_RED}You break off — the thief escapes with your {stolen} gold.{R_}"
        ent.revealed = False
        ent.x, ent.y = ent.home
        ent.cooldown = 8
        return f"{C_DIM}You slip away. The {ent.name} fades back into the dark.{R_}"
    return None


def _thief_contact(sc, pl, ent):
    if ent.data.get("fleeing"):
        return _fight_lurker(sc, pl, ent)
    if sc._bump is ent:
        ch = sc.choice_box(f"You corner the {ent.name}. 'Easy, friend — no harm done!'",
                           [("f", "Fight"), ("l", "Let them run")], ent)
        if ch == "f":
            return _fight_lurker(sc, pl, ent)
        ent.alive = False
        return f"{C_DIM}The thief scurries off into the dark.{R_}"
    # the thief makes a grab for your purse
    try:
        stealth = pl.get_stealth()
    except Exception:
        stealth = 0
    caught = pl.try_dodge() or random.random() < 0.15 + stealth / 100.0
    if caught:
        ch = sc.choice_box(f"You catch a hand in your purse — the {ent.name}!",
                           [("f", "Fight"), ("l", "Shove them away")], ent)
        if ch == "f":
            return _fight_lurker(sc, pl, ent)
        ent.alive = False
        return f"{C_DIM}The thief stumbles off, empty-handed.{R_}"
    if pl.gold <= 0:
        ent.alive = False
        return f"{C_DIM}A hand slips into your empty purse. The thief curses and slinks away.{R_}"
    amt = min(pl.gold, max(5, int(pl.gold * random.uniform(0.05, 0.12))), 60 + pl.level * 20)
    pl.gold -= amt
    ent.data.update(fleeing=True, stolen=amt, flee_turns=0)
    ent.ai = "static"                # _flee_step moves it
    ent.lurk = False
    ent.revealed = True
    return f"{C_RED}The {ent.name} snatches {amt} gold and bolts! Catch them!{R_}"


def _cutthroat_contact(sc, pl, ent):
    if sc._bump is ent:
        return _fight_lurker(sc, pl, ent)
    seen = ent.data.get("reveal_turn")
    surprised = seen is None or seen >= sc.turns - 1
    try:
        alert = random.random() < 0.10 + pl.get_stealth() / 120.0
    except Exception:
        alert = False
    return _fight_lurker(sc, pl, ent, ambush=surprised and not alert)


def _bandit_contact(sc, pl, ent):
    if sc._bump is ent:
        return _fight_lurker(sc, pl, ent)
    toll = max(10, pl.gold // 10)
    ch = sc.choice_box(f"'Your purse or your life, friend. {toll} gold and you walk away.'",
                       [("f", "Fight"), ("p", f"Pay {toll} gold"), ("r", "Run for it")], ent)
    if ch == "p":
        if pl.gold >= toll:
            pl.gold -= toll
            ent.alive = False
            return f"{C_DIM}You pay {toll}g. The bandit grins and melts into the shadows.{R_}"
        sc.talk_box(ent, "'That's all? You insult me.'", pl)
        return _fight_lurker(sc, pl, ent, ambush=True)
    if ch == "r":
        if random.random() < 0.5 + getattr(getattr(pl, "job", None), "dodge_bonus", 0) / 100.0:
            ent.revealed = False
            ent.x, ent.y = ent.home
            ent.cooldown = 8
            return f"{C_DIM}You sprint for the light. The bandit doesn't follow.{R_}"
        sc.talk_box(ent, "You trip on a loose cobble — the bandit is on you!", pl)
        return _fight_lurker(sc, pl, ent, ambush=True)
    return _fight_lurker(sc, pl, ent)


# ═══════════════════════════════════════════════════════════════
# INTERIORS — Inn, Tavern, Thieves' Guild
# ═══════════════════════════════════════════════════════════════

def _room(w, h, floor="_", box=DOUBLE):
    tl, tr, bl, br, hz, vt = box
    g = [[floor] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = hz
        g[h - 1][x] = hz
    for y in range(h):
        g[y][0] = vt
        g[y][w - 1] = vt
    g[0][0], g[0][w - 1], g[h - 1][0], g[h - 1][w - 1] = tl, tr, bl, br
    return g


def _put(g, x, y, ch):
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = ch


def _interior_palette(rgb=(170, 125, 80)):
    pal = dict(COMMON_TILES)
    pal.update(_box_palette(DOUBLE, rgb, "wall"))
    return pal


def _leave_interior(sc, pl):
    sc.leave("left")
    return None


def _interior(title, grid, start, door, ctx, palette, subtitle, colour):
    rows = ["".join(r) for r in grid]
    sc = TownScene(title, rows, palette=palette, start=start, subtitle=subtitle,
                   colour=colour, night=False, exit_on_edge=False)
    sc.ctx = ctx
    sc.add_door(door[0], door[1], "Step outside", _leave_interior, step_back=False)
    sc.add_key("p", "Save", _save_key)
    sc.hud_extra = _hud
    return sc


def _inn_interior(ctx):
    w, h = 38, 11
    g = _room(w, h)
    for x in (2, 3, 6, 7, 10, 11, 14, 15):
        _put(g, x, 1, "Z")                        # guest beds
    for x in range(24, 28):
        _put(g, x, 1, "y")                        # bookshelf
    _put(g, 33, 1, "F"); _put(g, 34, 1, "F")      # fireplace
    for x in range(15, 23):
        _put(g, x, 4, "C")                        # counter
    for (x, y) in ((4, 5), (5, 5), (9, 7), (10, 7), (27, 5), (28, 5), (30, 7), (31, 7)):
        _put(g, x, y, "t")
    _put(g, 2, 8, "b"); _put(g, 35, 8, "b")
    _put(g, 35, 3, "<")                           # stairs to the rooms
    door = (w // 2, h - 1)
    _put(g, door[0], door[1], "+")
    sc = _interior(f"{ctx.name.upper()} INN", g, (door[0], door[1] - 1), door, ctx,
                   _interior_palette(), "warm hearth · soft beds", fg(240, 200, 120))
    pr = random.Random(zlib.crc32(f"{ctx.seed}:{ctx.name}:inn".encode("utf-8")))
    names = FIRST_NAMES.get(ctx.cid, FIRST_NAMES["A"])
    keeper = Entity(18, 3, "@", fg(240, 200, 120), f"{pr.choice(names)} the Innkeeper",
                    kind="npc", interact=_innkeeper_interact, npc_id=f"{ctx.slug}_innkeeper",
                    title="innkeeper", data={"rumour": True})
    sc.add_entity(keeper)
    sc.add_door(35, 3, "Stairs to the guest rooms · rest", _rest_door, step_back=True, tile="<")
    patrons = [("weary pilgrim", ["My feet have walked three continents. Tonight they rest."]),
               ("merchant", ["The roads are worse every season. Bandits, beasts, tax collectors."]),
               ("off-duty guard", ["Don't tell the captain you saw me here."])]
    for i, (x, y) in enumerate(((6, 5), (11, 7), (29, 5))):
        title, lines = patrons[i % len(patrons)]
        sc.add_entity(Entity(x, y, "@", fg(200, 180, 150), pr.choice(names), kind="npc",
                             lines=lines + [random.choice(GLOBAL_RUMOURS)], ai="static",
                             title=title, npc_id=f"{ctx.slug}_inn_patron", data={"rumour": True}))
    return sc


def _innkeeper_interact(sc, pl, ent):
    cost = max(5, 10 + pl.level * 2)
    ch = sc.choice_box(f"'Welcome, traveller! A warm bed is {cost} gold. Breakfast included.'",
                       [("r", f"Rest until morning ({cost}g)"), ("t", "Chat"), ("n", "No thanks")], ent)
    if ch == "r":
        return _rest(sc, pl)
    if ch == "t":
        sc.talk_box(ent, random.choice(GLOBAL_RUMOURS + [
            "The cellar keeps flooding with something. It's not water.",
            "Adventurers pay well and die young. Bad for repeat business."]), pl)
    return None


def _rest_door(sc, pl):
    return _rest(sc, pl)


def _rest(sc, pl):
    ctx = sc.ctx
    before = pl.gold
    _modal(sc, ctx.town.inn)
    if pl.gold < before:
        if ctx.world is not None:
            advance_to_morning(ctx.world)
        ctx.night = False
        sc.night = False
        return f"{C_GREEN}You wake at dawn, fully rested.{R_}"
    return None


def _companion_def(cid):
    try:
        from game_party import COMPANION_DEFS
    except Exception:
        return None
    try:
        if isinstance(COMPANION_DEFS, dict):
            return COMPANION_DEFS.get(cid)
        return next((d for d in COMPANION_DEFS if d.get("id") == cid), None)
    except Exception:
        return None


def _have_companion(pl, cid):
    party = getattr(pl, "party", None)
    if party is None:
        return False
    for lst in (getattr(party, "members", []), getattr(party, "roster", [])):
        try:
            if any(getattr(m, "id", None) == cid for m in lst):
                return True
        except Exception:
            pass
    return False


RARITY_RGB = {"common": (200, 200, 200), "uncommon": (90, 210, 110), "rare": (80, 150, 240),
              "epic": (190, 110, 240), "legendary": (255, 190, 40)}


def _tavern_interior(ctx):
    w, h = 42, 13
    g = _room(w, h, box=DOUBLE)
    for x in range(4, 17):
        _put(g, x, 3, "C")                        # the bar
    for x in (2, 3, 17, 18):
        _put(g, x, 1, "b")                        # kegs
    _put(g, 38, 1, "F"); _put(g, 39, 1, "F")      # fireplace
    tables = [(8, 6), (9, 6), (16, 8), (17, 8), (25, 5), (26, 5), (31, 8), (32, 8), (24, 10), (25, 10)]
    for (x, y) in tables:
        _put(g, x, y, "t")
    door = (w // 2, h - 1)
    _put(g, door[0], door[1], "+")
    sc = _interior(_tavern_name(ctx).upper(), g, (door[0], door[1] - 1), door, ctx,
                   _interior_palette((150, 105, 65)), "ale, songs & sellswords", fg(230, 170, 90))
    pr = random.Random(zlib.crc32(f"{ctx.seed}:{ctx.name}:tavern_people".encode("utf-8")))
    names = FIRST_NAMES.get(ctx.cid, FIRST_NAMES["A"])
    sc.add_entity(Entity(10, 2, "@", fg(230, 170, 90), f"{pr.choice(names)} the Barkeep", kind="npc",
                         interact=_barkeep_interact, npc_id=f"{ctx.slug}_barkeep", title="barkeep",
                         data={"rumour": True}))
    sc.add_entity(Entity(36, 4, "?", fg(240, 220, 150), "Party & Clan Board", kind="object",
                         interact=_party_board, title="manage companions"))
    # recruits sitting at the tables
    seats = [(10, 6), (7, 6), (18, 8), (15, 8), (27, 5), (24, 5), (33, 8), (30, 8), (26, 10), (23, 10)]
    ids = None
    try:
        from game_party import tavern_recruits
        ids = list(tavern_recruits(ctx.name, day_index(ctx.world)) or [])
    except Exception:
        ids = None
    placed = 0
    if ids is not None:
        for cid in ids:
            if _have_companion(ctx.player, cid):
                continue
            d = _companion_def(cid) or {}
            if placed >= len(seats):
                break
            x, y = seats[placed]
            placed += 1
            rarity = str(d.get("rarity", "common")).lower()
            role = d.get("role", d.get("class", "adventurer"))
            sc.add_entity(Entity(x, y, "@", fg(*RARITY_RGB.get(rarity, (200, 200, 200))),
                                 d.get("name", cid.replace("_", " ").title()), kind="recruit",
                                 interact=_recruit_interact, npc_id=f"{ctx.slug}_tavern_{cid}",
                                 title=f"{rarity} {role}", data={"cid": cid}))
    else:
        # older game_party without tavern_recruits: a recruiter opens the old menu
        sc.add_entity(Entity(10, 6, "@", fg(120, 200, 230), "Recruiter", kind="npc",
                             interact=_party_board, npc_id=f"{ctx.slug}_recruiter",
                             title="sellswords for hire"))
        placed = 1
    if placed == 0:
        sc.add_entity(Entity(10, 6, "@", fg(170, 170, 170), "Empty-handed Sellsword", kind="npc",
                             lines=["Slow day. Everyone worth hiring left with the morning caravan.",
                                    "Come back tomorrow — new faces arrive every day."],
                             npc_id=f"{ctx.slug}_tavern_regular", title="regular"))
    # atmosphere
    sc.add_entity(Entity(20, 9, "@", fg(230, 150, 200), f"{pr.choice(names)} the Bard", kind="npc",
                         lines=["~ Oh the dragon sleeps on the mountain high... ~",
                                "Requests cost a coin. Silence costs two.",
                                "I'm writing a song about the Hollow Crown. Nobody wants to hear it."],
                         ai="wander", radius=4, npc_id=f"{ctx.slug}_bard", title="bard",
                         data={"rumour": True}))
    sc.add_entity(Entity(5, 9, "@", fg(210, 170, 110), pr.choice(names), kind="npc",
                         lines=NIGHT_ROLES["drunk"][2], ai="static", title="tipsy regular",
                         npc_id=f"{ctx.slug}_drunk", data={"rumour": True}))
    return sc


def _barkeep_interact(sc, pl, ent):
    ch = sc.choice_box("'What'll it be?'",
                       [("r", "Any rumours?"), ("d", "A drink (3g · restores some HP)"), ("n", "Nothing")], ent)
    if ch == "r":
        pool = GLOBAL_RUMOURS + _place_hints(sc.ctx.world, sc.ctx.loc, 3)
        sc.talk_box(ent, random.choice(pool), pl)
        _dragon_rumour(sc, pl)
    elif ch == "d":
        if pl.gold < 3:
            return f"{C_DIM}'No coin, no ale.'{R_}"
        pl.gold -= 3
        heal = max(1, pl.max_hp // 7)
        pl.hp = min(pl.max_hp, pl.hp + heal)
        return f"{C_GREEN}Warm ale. +{heal} HP.{R_}"
    return None


def _party_board(sc, pl, ent):
    try:
        from game_party import recruit_menu
    except Exception:
        return None
    _modal(sc, recruit_menu, pl, sc.ctx.name)
    return None


def _recruit_interact(sc, pl, ent):
    cid = ent.data.get("cid")
    try:
        from game_party import offer_recruit
    except Exception:
        return _party_board(sc, pl, ent)
    ok = _modal(sc, offer_recruit, pl, cid, scene=sc)
    if ok:
        ent.alive = False
        return f"{C_GOLD}{ent.name} joins you!{R_}"
    return None


# ── Thieves' Guild ───────────────────────────────────────────────

def _hidden_door_fn(sc, pl):
    ctx = sc.ctx
    ch = sc.choice_box("Two boards in the wall are loose. Behind them: a narrow stair going down, "
                       "and the smell of candle smoke.",
                       [("d", "Go down"), ("l", "Leave it be")])
    if ch != "d":
        return None
    try:
        pl.flags[f"found_guild_{ctx.slug}"] = True
        pl.flags["found_thieves_guild"] = True
    except Exception:
        pass
    _story_check(sc, pl)
    return _enter_interior(sc, pl, _guild_interior(ctx))


def _guild_interior(ctx):
    w, h = 36, 12
    g = _room(w, h, floor="x", box=DOUBLE)
    for x in range(3, 11):
        _put(g, x, 3, "C")                        # fence's counter
    for x in (2, 12, 13):
        _put(g, x, 1, "c")
    _put(g, 26, 1, "Q")                           # the Guildmaster's chair
    _put(g, 24, 1, "n"); _put(g, 28, 1, "n")      # banners
    for (x, y) in ((17, 6), (18, 6), (8, 8), (9, 8), (27, 7), (28, 7)):
        _put(g, x, y, "t")
    _put(g, 33, 9, "b"); _put(g, 32, 9, "b")
    door = (2, h - 1)
    _put(g, door[0], door[1], "<")
    pal = _interior_palette((90, 80, 95))
    pal["<"] = _t((200, 200, 210), "▲", True, "stairs up")
    sc = _interior("THIEVES' GUILD", g, (2, h - 2), door, ctx, pal,
                   "secrets, stolen goods & sharp knives", fg(180, 110, 230))
    sc.triggers[door] = ("Climb back up to the street", _leave_interior, False)
    sc.set_tile(door[0], door[1], "<")
    sc.add_entity(Entity(6, 2, "@", fg(200, 180, 120), "Vesk the Fence", kind="npc",
                         interact=_fence_interact, npc_id=f"{ctx.slug}_fence", title="fence"))
    conquered = ctx.guild_conquered
    gm_title = "Guildmaster" if not conquered else "former Guildmaster (yields to you)"
    sc.add_entity(Entity(26, 2, "@", fg(200, 90, 220), "The Guildmaster", kind="npc",
                         interact=_guildmaster_interact, npc_id=f"{ctx.slug}_guildmaster",
                         title=gm_title))
    thug_lines = ["Lost, are we? The exit's behind you. Use it.",
                  "Friends of the Guild drink free. You're not a friend. Yet.",
                  "Buy something or get out. Your choice. Choose fast."]
    if conquered:
        thug_lines = ["Boss.", "Whatever you need, boss.", "The streets are quiet, just like you wanted."]
    for (x, y) in ((16, 5), (29, 8), (12, 9)):
        sc.add_entity(Entity(x, y, "&", fg(150, 130, 170), "Guild Thug", kind="npc",
                             lines=thug_lines, ai="wander", radius=2, title="enforcer",
                             npc_id=f"{ctx.slug}_guild_thug"))
    return sc


def _black_market(ctx):
    r = random.Random(zlib.crc32(f"{ctx.name}:blackmarket:{day_index(ctx.world)}".encode("utf-8")))
    items = []
    try:
        from game_items import random_loot
        for _ in range(4):
            it = random_loot(ctx.player.level, rarity=r.choice(["rare", "rare", "epic"]), rng=r)
            if it is not None:
                items.append(it)
    except Exception:
        pass
    if not items:
        try:
            from game_items import ITEM_POOL
            pool = [n for n in ("Smoke Bomb", "Fire Bomb", "Elixir", "Mega Potion", "Elixir of Life",
                                "Mana Crystal", "Strength Draught") if n in ITEM_POOL]
            for n in r.sample(pool, min(4, len(pool))):
                items.append(ITEM_POOL[n]())
        except Exception:
            pass
    disc = 0.8 if ctx.guild_conquered else 1.0
    out = []
    for it in items:
        base = int(getattr(it, "sell_value", 0) or getattr(it, "value", 0) or 20)
        out.append((it, max(15, int(base * 2.6 * disc))))
    return out


def _fence_interact(sc, pl, ent):
    ch = sc.choice_box("'No names, no questions. You sell, I buy. You buy, I forget your face.'",
                       [("s", "Sell loot"), ("b", "Browse the black market"), ("n", "Nothing")], ent)
    if ch == "s":
        try:
            from game_sell import open_sell_screen
            _modal(sc, open_sell_screen, pl, shop_sell_multiplier=1.0)
        except Exception as e:
            _log_error("fence sell", e)
    elif ch == "b":
        stock = _black_market(sc.ctx)
        if not stock:
            return f"{C_DIM}'Shelves are bare tonight. Come back tomorrow.'{R_}"
        _modal(sc, _swap_shop, sc.ctx.town, stock, "Black Market")
    return None


def _guildmaster_interact(sc, pl, ent):
    ctx = sc.ctx
    if ctx.guild_conquered:
        sc.talk_box(ent, "'The Guild answers to you now. The alleys of this town are quieter for it. "
                         "And the fence gives you a fair price.'", pl)
        return None
    ch = sc.choice_box("'Bold, walking in here. Most who find our door pay for the privilege. "
                       "Or you could try to take my chair.'",
                       [("c", "Challenge the Guildmaster"), ("t", "Talk"), ("n", "Back away")], ent)
    if ch == "t":
        sc.talk_box(ent, "'Every coin that changes hands in the dark passes through my fingers. "
                         "Even the king's men buy from us. Especially the king's men.'", pl)
        return None
    if ch != "c":
        return None
    boss = _make_boss("Thieves' Guildmaster", pl.level)
    res = sc.fight(pl, boss, allow_escape=True)
    if res != "victory":
        return None if res == "defeat" else f"{C_DIM}You retreat. The Guildmaster laughs.{R_}"
    pl.flags[ctx.guild_flag] = True
    pl.flags["thieves_guildmaster_defeated"] = True
    reward = 120 + pl.level * 25
    pl.gold += reward
    extra = ""
    try:
        from game_items import random_loot
        it = random_loot(pl.level, rarity="epic")
        if it is not None and pl.add_item(it):
            extra = f" and {it.name}"
    except Exception:
        pass
    ent.title = "former Guildmaster (yields to you)"
    for e in sc.entities:
        if e.name == "Guild Thug":
            e.lines = ["Boss.", "Whatever you need, boss."]
    _story_check(sc, pl)
    return f"{C_GOLD}The Guildmaster yields! The Guild is yours. +{reward}g{extra}.{R_}"


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def make_town(world, player, loc, autosave=None):
    """The classic Town object (menus) with all callbacks wired up."""
    from game_systems import Town
    from game_party import recruit_menu
    try:
        from game_world import CONTINENTS
        cont = next((c for c in CONTINENTS if c["id"] == loc.get("continent", "")), None)
    except Exception:
        cont = None
    rname = cont["name"] if cont else ""
    town = Town(player, loc["name"], rname)
    town.set_companion_callback(lambda: recruit_menu(player, loc["name"]))
    town.set_base_info(loc.get("continent", ""), loc["x"], loc["y"])
    town.set_world(world, autosave)
    if loc.get("type") == "port" and world is not None:
        ship = next((s for s in world.ships if s["port_name"] == loc["name"]), None)
        if ship:
            town.set_ship(world, ship, player)
    return town


def run_town(world, player, loc, autosave=None, town=None):
    """Walk around a city or port. Returns 'left', 'defeat' or 'sailed'.
    Defeat is handled here (world._handle_defeat). Falls back to the old menu
    if the walkable town cannot be built."""
    if town is None:
        town = make_town(world, player, loc, autosave)
    player.location_name = loc.get("name", "")
    try:
        ctx = TownCtx(world, player, loc, town, autosave)
        sc = build_town_scene(ctx)
    except Exception as e:
        _log_error(f"build {loc.get('name')}", e)
        before = (world.player_x, world.player_y) if world is not None else None
        town.enter()
        if world is not None and (world.player_x, world.player_y) != before:
            return "sailed"
        return "left"
    res = sc.run(player)
    if res == "defeat" or not player.is_alive():
        if world is not None:
            world._handle_defeat(player)
        return "defeat"
    return res or "left"
