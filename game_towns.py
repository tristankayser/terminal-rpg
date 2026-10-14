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
                    box=DOUBLE, palette=pal, centre="statue", tree="T", flower="k",
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
        for y in range(1, wall_end + 1):
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
