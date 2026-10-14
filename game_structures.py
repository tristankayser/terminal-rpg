"""game_structures.py — explorable world structures.

~50 hand-placed-by-seed points of interest across the five continents:
watchtowers, shrines (one per god), bandit camps and Rourke's Hideout,
abandoned villages, wizard towers, obelisks/portals, desert caravans, fishing
huts, graveyards, hunting lodges, dragon bones, frozen shipwrecks, lighthouses,
hermit huts and hidden caves (two-floor mini dungeons).

Every structure is a SMALL walkable scene (game_scene) with real content:
NPCs with story ids, chests, encounters, lore, story/side-story hooks and a
one-time discovery reward.  Persistent state lives in player.flags:
    disc:<name>            discovered (journal "Discoveries x/y")
    lore:<key>             lore entry read (journal lore reader)
    chest:<name>:<n>       chest opened
    cleared:<name>:<n>     encounter defeated
    blessed:<god>          first blessing taken at a shrine
    attuned:<name>         obelisk attuned (obelisk travel network)
    found_bandit_camp, rourke_defeated, ...

World placement: place_structures(world, rng) is called by game_world after
base generation.  It uses its own random.Random derived from world.seed (never
the global RNG and never the shared rng's sequence), so the layout of an old
save stays identical even if other feature modules change what they consume.
"""

from __future__ import annotations

import random
from game_term import C, clr, H
from game_scene import (Scene, Entity, Tile, fg, parse_map, R_, B_,
                        C_GOLD, C_WHITE, C_DIM, C_RED, C_GREEN, C_CYAN, C_PURP)

C_ORAN = fg(230, 150, 60)
C_YELL = fg(240, 210, 90)
C_IVORY = fg(235, 225, 200)

# ── terrain constants (mirrors game_world; kept local to avoid imports) ──
OCEAN = "~"; SHALLOWS = ";"; PLAINS = "."; FOREST = "T"; MOUNTAIN = "^"
SNOW = "*"; HILL = ","; ROAD = "="; RIVER = "/"; SAND = ":"
LAND = (PLAINS, FOREST, HILL, SNOW, SAND, MOUNTAIN)

DANGER = {"A": 1, "E": 2, "B": 3, "D": 3, "C": 4}

# ═════════════════════════════════════════════════════════════════
# Place types — storage glyph (unique ASCII in world.terrain), drawn symbol
# ═════════════════════════════════════════════════════════════════

TYPES = {
    #  type               glyph  sym  colour              HUD name
    "watchtower":        ("1", "I", (235, 205, 120), "Watchtower"),
    "shrine":            ("2", "†", (250, 245, 200), "Shrine"),
    "bandit_camp":       ("3", "&", (225, 90, 60),   "Bandit Camp"),
    "bandit_hideout":    ("4", "%", (200, 50, 50),   "Bandit Hideout"),
    "abandoned_village": ("5", "v", (160, 155, 150), "Abandoned Village"),
    "wizard_tower":      ("6", "Ψ", (170, 120, 255), "Wizard Tower"),
    "obelisk":           ("7", "!", (200, 130, 255), "Ancient Obelisk"),
    "caravan":           ("8", "¤", (240, 180, 90),  "Caravan Camp"),
    "fishing_hut":       ("9", "f", (110, 190, 230), "Fishing Hut"),
    "graveyard":         ("0", "+", (190, 200, 190), "Graveyard"),
    "hunting_lodge":     ("&", "n", (180, 130, 80),  "Hunting Lodge"),
    "dragon_bones":      ("$", "}", (240, 235, 215), "Dragon Bones"),
    "frozen_wreck":      ("!", "w", (170, 220, 250), "Frozen Shipwreck"),
    "lighthouse":        ("?", "i", (255, 240, 150), "Lighthouse"),
    "hermit_hut":        ("(", "h", (170, 200, 140), "Hermit's Hut"),
    "hidden_cave":       (")", "o", (150, 140, 130), "Hidden Cave"),
}
# Free fallback glyphs in case another module registered one of ours first.
_SPARE_GLYPHS = list("[]{}<>|'`\"jlqu")

GLYPH = {}       # type -> glyph actually used

# ═════════════════════════════════════════════════════════════════
# The placement plan — (type, continent, name, extra)
# Landmarks come first: stories target them by name.
# ═════════════════════════════════════════════════════════════════

GODS = {
    "Solara": ("sun",   "the Dawnmother, goddess of the sun and of healing", (255, 210, 90)),
    "Morrin": ("moon",  "the Silver Watcher, god of the moon, dreams and magic", (170, 190, 255)),
    "Kaelos": ("war",   "the Iron Hand, god of war and courage", (230, 90, 70)),
    "Vessa":  ("wind",  "the Unseen, goddess of wind, roads and thieves", (160, 230, 200)),
    "Nerys":  ("sea",   "the Deep Mother, goddess of the sea and of tides", (80, 170, 240)),
    "Thalor": ("stone", "the Old Mountain, god of stone, oaths and endurance", (190, 170, 130)),
}

PLAN = [
    # landmarks
    ("wizard_tower", "A", "Tower of Mirelle", {"npc": "magus_mirelle"}),
    ("abandoned_village", "A", "Hollowmere", {"special": "hollowmere"}),
    ("bandit_hideout", "A", "Rourke's Hideout", {"alt_cont": "B"}),
    ("dragon_bones", "B", "The Wyrm's Graveyard", {"special": "wyrm"}),
    ("graveyard", "B", "Ashen Barrow", {"npc": "gravekeeper_ashen"}),
    ("hidden_cave", "B", "Emberdeep Hollow", {"boss": "Brood Mother", "floors": 2}),
    ("hermit_hut", "C", "White Pass Hermitage", {"npc": "hermit_osric"}),
    ("frozen_wreck", "C", "Wreck of the Morrow", {"special": "morrow"}),
    ("wizard_tower", "C", "Spire of Quellan", {"npc": "magus_quellan"}),
    ("obelisk", "D", "Starfall Obelisk", {"special": "starfall"}),
    ("lighthouse", "E", "Saltglass Lighthouse", {"npc": "keeper_maris", "special": "saltglass"}),
    # shrines — one per god
    ("shrine", "A", "Shrine of Solara", {"god": "Solara"}),
    ("shrine", "B", "Shrine of Kaelos", {"god": "Kaelos"}),
    ("shrine", "C", "Shrine of Morrin", {"god": "Morrin"}),
    ("shrine", "D", "Shrine of Vessa", {"god": "Vessa"}),
    ("shrine", "E", "Shrine of Nerys", {"god": "Nerys"}),
    ("shrine", "B", "Shrine of Thalor", {"god": "Thalor"}),
    # watchtowers
    ("watchtower", "A", "Highwatch", {}),
    ("watchtower", "A", "Briar Watch", {}),
    ("watchtower", "B", "Ironcrag Watch", {}),
    ("watchtower", "B", "Emberwatch", {}),
    ("watchtower", "C", "Whitecap Tower", {"npc": "warden_halvard"}),
    ("watchtower", "C", "Frostfang Watch", {}),
    ("watchtower", "D", "Sunstone Watch", {}),
    ("watchtower", "D", "Mirage Tower", {}),
    ("watchtower", "E", "Palmcrest Watch", {}),
    ("watchtower", "E", "Reefwatch", {}),
    # bandits
    ("bandit_camp", "A", "Grimwater Camp", {}),
    ("bandit_camp", "B", "Redcliff Camp", {}),
    ("bandit_camp", "E", "Smugglers' Camp", {}),
    ("bandit_camp", "D", "Vulture Camp", {}),
    # the rest
    ("abandoned_village", "C", "Rimefall", {}),
    ("abandoned_village", "E", "Saltmarsh", {}),
    ("obelisk", "B", "Runestone of Aeld", {}),
    ("obelisk", "E", "Moonwell Portal", {}),
    ("caravan", "D", "Caravan of Qasim", {}),
    ("caravan", "D", "Saffron Caravan", {}),
    ("fishing_hut", "A", "Old Tam's Hut", {}),
    ("fishing_hut", "C", "Icefisher's Hut", {}),
    ("fishing_hut", "E", "Coral Hut", {}),
    ("graveyard", "A", "Gravesend Barrow", {"npc": "gravekeeper_gravesend"}),
    ("graveyard", "C", "Frostgrave", {"npc": "gravekeeper_frost"}),
    ("hunting_lodge", "A", "Antler Lodge", {}),
    ("hunting_lodge", "C", "Snowmane Lodge", {}),
    ("dragon_bones", "D", "Bones of the Sand Wyrm", {}),
    ("frozen_wreck", "C", "Wreck of the Halcyon", {}),
    ("lighthouse", "B", "Cliffwatch Light", {"npc": "keeper_bram"}),
    ("hermit_hut", "D", "Zahra's Shelter", {"npc": "hermit_zahra"}),
    ("hermit_hut", "E", "Pell's Driftwood Hut", {"npc": "hermit_pell"}),
    ("hidden_cave", "A", "Whispering Grotto", {"boss": "Grotto Troll", "floors": 2}),
    ("hidden_cave", "C", "Rimeheart Cave", {"boss": "Frost Dragon", "floors": 2}),
    ("hidden_cave", "D", "Sandglass Hollow", {"boss": "Shadow Lich", "floors": 2}),
    ("hidden_cave", "E", "Tidepool Grotto", {"boss": "Dungeon Warden", "floors": 1}),
]

LANDMARKS = {name for t, c, name, ex in PLAN[:11]}

# Preferred world terrain per type
PREF = {
    "watchtower":        (HILL, PLAINS, FOREST, SNOW, SAND),
    "shrine":            (PLAINS, HILL, FOREST, SNOW, SAND),
    "bandit_camp":       (FOREST, HILL, PLAINS, SAND),
    "bandit_hideout":    (FOREST, HILL, MOUNTAIN),
    "abandoned_village": (PLAINS, FOREST, SNOW, HILL),
    "wizard_tower":      (FOREST, HILL, PLAINS, SNOW),
    "obelisk":           (SAND, PLAINS, HILL),
    "caravan":           (SAND, PLAINS),
    "fishing_hut":       (SAND, PLAINS, SNOW),
    "graveyard":         (PLAINS, HILL, SNOW),
    "hunting_lodge":     (FOREST, SNOW, HILL),
    "dragon_bones":      (MOUNTAIN, HILL, SAND, SNOW),
    "frozen_wreck":      (SNOW, SAND, PLAINS),
    "lighthouse":        (SAND, HILL, PLAINS, SNOW),
    "hermit_hut":        (SNOW, HILL, SAND, FOREST, PLAINS),
    "hidden_cave":       (HILL, MOUNTAIN, FOREST),
}
COASTAL = {"fishing_hut", "frozen_wreck", "lighthouse"}

_TOTAL = [0]          # number of structures in the current world (journal)
_PLACED = []          # names placed in the current world


# ═════════════════════════════════════════════════════════════════
# Registration
# ═════════════════════════════════════════════════════════════════

def _register():
    try:
        import game_world as gw
    except Exception:
        return
    used = set(gw.TILE.keys())
    spare = [g for g in _SPARE_GLYPHS if g not in used]
    for t, (glyph, sym, rgb, name) in TYPES.items():
        g = glyph
        if g in used and GLYPH.get(t) != g:
            if not spare:
                continue
            g = spare.pop(0)
        GLYPH[t] = g
        used.add(g)
        gw.register_place_type(t, g, fg(*rgb) + B_, name,
                               enter=_enter, arrive=_arrive, symbol=sym)


def _arrive(loc):
    t = loc.get("type")
    rgb = TYPES.get(t, (None, None, (230, 230, 230)))[2]
    return (f"{fg(*rgb)}{B_}{TYPES.get(t, ('', '', '', 'Place'))[3]}: {loc['name']}.{R_} "
            f"{C_DIM}[E] to explore.{R_}")


# ═════════════════════════════════════════════════════════════════
# Placement
# ═════════════════════════════════════════════════════════════════

def place_structures(world, rng=None):
    """Called by game_world after base generation. Deterministic per seed."""
    if not GLYPH:
        _register()
    r = random.Random((int(getattr(world, "seed", 1)) * 104729 + 7) & 0xFFFFFFFF)
    W_, H_ = len(world.terrain[0]), len(world.terrain)
    by_cont = {}
    for y in range(1, H_ - 1):
        row = world.terrain[y]
        crow = world.cont_map[y]
        for x in range(1, W_ - 1):
            ch = row[x]
            if ch in LAND:
                by_cont.setdefault(crow[x], []).append((x, y))
    taken = [(l["x"], l["y"]) for l in world.locations]
    ships = {(s["x"], s["y"]) for s in getattr(world, "ships", [])}
    del _PLACED[:]

    def coastal(x, y):
        return any(world.terrain[y + dy][x + dx] in (OCEAN, SHALLOWS)
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    def free(x, y, dist):
        if (x, y) in ships:
            return False
        for (lx, ly) in taken:
            if abs(lx - x) < dist and abs(ly - y) < dist:
                return False
        # don't cut roads/rivers: the tile itself and its 4 neighbours stay clear
        if world.terrain[y][x] in (ROAD, RIVER):
            return False
        return True

    def has_land_neighbour(x, y):
        return any(world.terrain[y + dy][x + dx] not in (OCEAN, SHALLOWS)
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    placed = 0
    for t, cont, name, extra in PLAN:
        if any(l.get("name") == name for l in world.locations):
            continue
        glyph = GLYPH.get(t)
        if not glyph:
            continue
        conts = [cont] + ([extra["alt_cont"]] if extra.get("alt_cont") else [])
        spot = None
        attempts = [(5, True), (4, True), (3, False), (2, False)]
        for c in conts:
            tiles = by_cont.get(c, [])
            if not tiles:
                continue
            for dist, strict in attempts:
                pref = PREF.get(t, LAND)
                cand = [p for p in tiles
                        if (not strict or world.terrain[p[1]][p[0]] in pref)
                        and (t not in COASTAL or coastal(*p) or not strict)
                        and has_land_neighbour(*p)]
                if t in COASTAL and strict:
                    cand = [p for p in cand if coastal(*p)]
                r.shuffle(cand)
                for p in cand[:400]:
                    if free(p[0], p[1], dist):
                        spot = p
                        break
                if spot:
                    break
            if spot:
                cont = c
                break
        if not spot:
            continue
        x, y = spot
        world.terrain[y][x] = glyph
        loc = {"type": t, "icon": glyph, "name": name, "x": x, "y": y,
               "continent": cont, "region": cont, "structure": True}
        for k, v in extra.items():
            if k != "alt_cont":
                loc[k] = v
        world.locations.append(loc)
        taken.append((x, y))
        _PLACED.append(name)
        placed += 1
    _TOTAL[0] = placed
    return placed


# ═════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════

def _flags(player):
    if not isinstance(getattr(player, "flags", None), dict):
        player.flags = {}
    return player.flags


def _loc_rng(world, loc, salt=""):
    return random.Random(f"{getattr(world, 'seed', 0)}:{loc['name']}:{salt}")


def _make(name):
    try:
        from game_items import make_item
        it = make_item(name)
        if it is not None:
            return it
    except Exception:
        pass
    try:
        from game_items import ITEM_POOL
        if name in ITEM_POOL:
            return ITEM_POOL[name]()
    except Exception:
        pass
    return None


LOOT_TIERS = [
    ["Potion", "Ether", "Antidote", "Wolf Pelt", "Iron Ore", "Feather", "Leather Armor", "Iron Helm", "Travel Cloak"],
    ["Hi-Potion", "Hi-Ether", "Smoke Bomb", "Fire Bomb", "Mana Stone", "Runic Stone", "Iron Ring", "Power Ring", "Steel Shield"],
    ["Full Potion", "Elixir", "Strength Draught", "Holy Water", "Dark Shard", "Mana Amulet", "Shadow Cloak", "Frost Cloak", "Titan Ring"],
    ["Mega Potion", "Mega Ether", "Hero's Brew", "Phoenix Feather", "Dragon Scale", "Obsidian Armor", "Mirror Shield", "Hero Amulet", "Amulet of Life"],
]


def _loot(player, rng, bonus=0):
    """One random item suited to the player's level."""
    lv = getattr(player, "level", 1)
    try:
        from game_items import random_loot
        it = random_loot(lv + bonus * 3, rng=rng)
        if it is not None:
            return it
    except Exception:
        pass
    tier = max(0, min(len(LOOT_TIERS) - 1, (lv + bonus * 4) // 6))
    if rng.random() < 0.25 and tier < len(LOOT_TIERS) - 1:
        tier += 1
    return _make(rng.choice(LOOT_TIERS[tier]))


def _give(player, item):
    if item is None:
        return ""
    try:
        if player.add_item(item):
            return f"{C_WHITE}{item.name}{R_}"
    except Exception:
        pass
    return f"{C_DIM}(bag full — {item.name} left behind){R_}"


def _story(player, fn, *a):
    """Call a story hook safely; completions are queued for popups."""
    st = getattr(player, "stories", None)
    if st is None or not hasattr(st, fn):
        return []
    try:
        return getattr(st, fn)(*a) or []
    except Exception:
        return []


def _flush(player):
    try:
        from game_stories import flush_story_popups
        flush_story_popups(player)
    except Exception:
        pass


def _enemy(player, loc, name=None, zone="plains", bonus=0):
    from game_enemies import generate_enemy
    d = DANGER.get(loc.get("continent", "A"), 2) + bonus
    return generate_enemy(zone, d, player.level, name=name)


def _boss(name, player):
    from game_enemies import create_boss
    try:
        return create_boss(name, player.level)
    except Exception:
        from game_enemies import generate_enemy
        e = generate_enemy("dungeon_deep", 4, player.level + 2)
        e.name = name
        return e


def read_lore(scene, player, ent, key):
    """Show a lore entry in a talk box and remember it."""
    title, text = LORE.get(key, ("Old writing", "The words have faded."))
    first = not _flags(player).get(f"lore:{key}")
    _flags(player)[f"lore:{key}"] = True
    for chunk in _paragraphs(f"《 {title} 》  {text}", 330):
        scene.talk_box(ent, chunk, player)
    if first:
        try:
            player.gain_exp(15 + player.level * 2)
        except Exception:
            pass
        return f"{C_CYAN}Lore added to your journal: {title}.{R_}"
    return None


def _paragraphs(text, n):
    words = text.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        out.append(cur)
    return out


def _lore_ent(x, y, key, name="Old journal", glyph="?"):
    return Entity(x, y, glyph, C_CYAN, name, kind="object",
                  interact=lambda sc, pl, e: read_lore(sc, pl, e, key))


def _chest_ent(x, y, loc, idx, world, bonus=0, gold=(30, 90), extra=None, name="Chest"):
    key = f"chest:{loc['name']}:{idx}"

    def opened(sc, pl, e):
        f = _flags(pl)
        if f.get(key):
            return f"{C_DIM}Empty.{R_}"
        f[key] = True
        rng = _loc_rng(world, loc, f"chest{idx}:{pl.level}")
        g = rng.randint(*gold) + pl.level * 6 * (1 + bonus)
        pl.gold += g
        parts = [f"{C_GOLD}+{g} gold{R_}"]
        parts.append(_give(pl, _loot(pl, rng, bonus)))
        for nm in extra or []:
            parts.append(_give(pl, _make(nm)))
        e.glyph = "□"
        e.colour = C_DIM
        return f"{C_GOLD}★ {name}:{R_} " + "  ".join(p for p in parts if p)
    e = Entity(x, y, "■", C_GOLD, name, kind="object", interact=opened)
    return e


def _foe(x, y, loc, idx, label, glyph, factory, ai="wander", lurk=False, persistent=True, boss=False,
         on_win=None, colour=C_RED):
    """A hostile entity. factory(player) -> Enemy."""
    key = f"cleared:{loc['name']}:{idx}"

    def contact(sc, pl, e):
        if e.cooldown > 0:
            return f"{C_DIM}The {e.name} keeps its distance.{R_}"
        enemy = factory(pl)
        res = sc.fight(pl, enemy, allow_escape=not boss)
        if res == "victory":
            e.alive = False
            if persistent:
                _flags(pl)[key] = True
            if on_win:
                return on_win(sc, pl, e)
            return f"{C_GREEN}The {enemy.name} is defeated.{R_}"
        if res == "escaped":
            e.cooldown = 4
            return f"{C_DIM}You break away from the {e.name}.{R_}"
        return None
    ent = Entity(x, y, glyph, colour, label, kind="enemy", ai=ai, hostile=True, on_contact=contact,
                 lurk=lurk, reveal_radius=2, radius=3)
    ent.data["key"] = key
    return ent


def _alive(player, key):
    return not _flags(player).get(key)


def _sprinkle(rows, rng, floor, deco, n):
    """Place up to n decoration tiles on floor tiles away from the path."""
    rows = [list(r) for r in rows]
    spots = [(x, y) for y, r in enumerate(rows) for x, c in enumerate(r)
             if c == floor and 0 < y < len(rows) - 2]
    rng.shuffle(spots)
    for (x, y) in spots[:n]:
        rows[y][x] = rng.choice(deco)
    return ["".join(r) for r in rows]


_WALK_FLOORS = ".,:_Jidzq*="


class _Tpl:
    """A parsed template: rows + marker positions.

    Markers (replaced by floor): @ start, & npc, K second npc / boss,
    $ chest, ! enemy, ? lore, > main feature trigger.  With floor=None each
    marker becomes the most common walkable floor around it."""
    MARKS = "@&$!?>K"

    def __init__(self, text, floor=None, subst=None):
        rows = [list(r) for r in parse_map(text)]
        w = max(len(r) for r in rows)
        rows = [r + [" "] * (w - len(r)) for r in rows]
        self.marks = {}
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch in self.MARKS:
                    self.marks.setdefault(ch, []).append((x, y))
        for ch, lst in self.marks.items():
            for (x, y) in lst:
                rep = (subst or {}).get(ch) or floor or self._auto(rows, x, y)
                rows[y][x] = rep
        self.rows = ["".join(r) for r in rows]

    def _auto(self, rows, x, y):
        cnt = {}
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if (dx or dy) and 0 <= yy < len(rows) and 0 <= xx < len(rows[yy]):
                    c = rows[yy][xx]
                    if c in _WALK_FLOORS:
                        cnt[c] = cnt.get(c, 0) + 1
        if not cnt:
            return "."
        return max(sorted(cnt), key=lambda c: cnt[c])

    def at(self, ch, i=0, default=(1, 1)):
        lst = self.marks.get(ch, [])
        return lst[i] if i < len(lst) else default

    def all(self, ch):
        return list(self.marks.get(ch, []))


EXTRA_TILES = {
    "A": Tile(fg(240, 215, 120), "╤", False, "altar"),
    "G": Tile(fg(170, 175, 170), "†", False, "gravestone"),
    "O": Tile(fg(190, 120, 255), "█", False, "rune obelisk"),
    "I": Tile(fg(150, 110, 220), "○", True, "rune circle"),
    "M": Tile(fg(180, 90, 70), "▲", False, "tent"),
    "W": Tile(fg(235, 225, 200), ")", False, "great bone"),
    "X": Tile(fg(235, 225, 200), "(", False, "great bone"),
    "Y": Tile(fg(235, 225, 200), "═", False, "rib bone"),
    "Z": Tile(fg(250, 245, 230), "Ö", False, "dragon skull"),
    "i": Tile(fg(190, 225, 245), "·", True, "ice"),
    "j": Tile(fg(150, 200, 235), "▓", False, "ice block"),
    "h": Tile(fg(110, 75, 50), "▓", False, "ship's hull"),
    "l": Tile(fg(255, 245, 160), "☼", False, "great lamp"),
    "E": Tile(fg(85, 80, 75), "▓", False, "cave wall"),
    "J": Tile(fg(80, 75, 70), "·", True, "cave floor", dark=True),
    "P": Tile(fg(140, 100, 60), "¦", False, "palisade"),
    "N": Tile(fg(160, 140, 100), "#", False, "drying net"),
    "U": Tile(fg(120, 100, 140), "▬", False, "bedroll"),
    "q": Tile(fg(200, 190, 90), '"', True, "dry field"),
    "R": Tile(fg(120, 115, 110), "%", False, "rubble"),
    "d": Tile(fg(120, 95, 60), "_", True, "deck"),
    "m": Tile(fg(80, 60, 50), "▒", False, "burnt wall"),
}


def _new_scene(loc, tpl, sub, colour, world, night=False, fog=False, sight=7):
    sc = Scene(loc["name"].upper(), tpl.rows, palette=EXTRA_TILES, start=tpl.at("@"),
               subtitle=sub, colour=colour, night=night, fog=fog, sight=sight)
    sc.data_world = world
    sc.data_loc = loc
    return sc


def _npc(x, y, name, title, lines, npc_id=None, colour=None, ai="static", interact=None, radius=2):
    if npc_id and interact is None:
        interact = _with_story(None)
    return Entity(x, y, "@", colour or fg(240, 210, 140), name, kind="npc", lines=lines,
                  ai=ai, npc_id=npc_id, title=title, interact=interact, radius=radius)


def _with_story(fn):
    """NPC interact wrapper: story-aware lines first (npc_dialogue), then any
    story popups the talk just triggered, then the NPC's own behaviour
    (fn(scene, player, ent)); plain NPCs (fn=None) only chat when the story
    had nothing to say."""
    def interact(sc, pl, e):
        extra = None
        try:
            if e.npc_id and hasattr(pl.stories, "npc_dialogue"):
                extra = pl.stories.npc_dialogue(e.npc_id, pl)
        except Exception:
            extra = None
        for line in extra or []:
            sc.talk_box(e, line, pl)
        try:
            from game_stories import pending_popups, flush_story_popups
            if pending_popups():
                sc.modal(flush_story_popups, pl)
        except Exception:
            pass
        if fn is not None:
            return fn(sc, pl, e)
        if not extra:
            sc.talk_box(e, None, pl)
        return None
    return interact


# ═════════════════════════════════════════════════════════════════
# Enter handler
# ═════════════════════════════════════════════════════════════════

def _enter(world, player, loc, autosave=None):
    t = loc.get("type")
    builder = BUILDERS.get(t)
    if builder is None:
        return
    first = _discover(world, player, loc)
    # story hooks: visit by name and by type
    _story(player, "on_visit", loc["name"], player, t)
    _flush(player)
    try:
        sc = builder(world, player, loc)
    except Exception as e:
        _log(f"build {loc['name']}: {e!r}")
        world.last_msg = f"{C_DIM}{loc['name']} — nothing more to see.{R_}"
        return
    if sc is None:
        return
    if first:
        sc.message(first)
    res = sc.run(player)
    _story(player, "check_flags", player)
    if res == "defeat" or not player.is_alive():
        world._handle_defeat(player)
        return
    if res == "dungeon":
        _run_cave(world, player, loc)
        return
    if isinstance(res, str) and res.startswith("travel:"):
        world.last_msg = f"{C_PURP}The rune-light fades. You stand beside {res[7:]}.{R_}"
        return
    world.last_msg = f"{C_DIM}You leave {loc['name']}.{R_}"


def _discover(world, player, loc):
    f = _flags(player)
    key = f"disc:{loc['name']}"
    if f.get(key):
        return None
    f[key] = True
    xp = 25 + player.level * 8
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):      # level-up text would tear the scene
            lv = player.level
            player.gain_exp(xp)
        lvl = f"  {C_GOLD}{B_}LEVEL UP! Lv {player.level}{R_}" if player.level > lv else ""
    except Exception:
        lvl = ""
    n = sum(1 for k, v in f.items() if k.startswith("disc:") and v)
    tot = max(_TOTAL[0], n)
    return f"{C_GOLD}★ Discovery! {loc['name']}{R_} {C_CYAN}+{xp} EXP{R_} {C_DIM}({n}/{tot} found){R_}{lvl}"


def _log(msg):
    try:
        import os
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
            f.write(f"structures: {msg}\n")
    except Exception:
        pass


def _reveal_area(world, loc, radius):
    W_, H_ = len(world.terrain[0]), len(world.terrain)
    cx, cy = loc["x"], loc["y"]
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius * 2, radius * 2 + 1):
            if (dx / 2.0) ** 2 + dy ** 2 <= radius * radius:
                x, y = cx + dx, cy + dy
                if 0 <= x < W_ and 0 <= y < H_ and not world.discovered[y][x]:
                    world.discovered[y][x] = True
                    n += 1
    return n


# ═════════════════════════════════════════════════════════════════
# Builders — one per type
# ═════════════════════════════════════════════════════════════════

WATCHTOWER_TPL = [r"""
  ,,,,,,,,,,,,,,,,,,,,,,,
  ,,T,,,,1-----2,,,,,T,,,
  ,,,,,,,|__>__|,,,,,,,,,
  ,,,,^,,|_____|,,,,^,,,,
  ,T,,,,,|_?___|,,,,,,,T,
  ,,,,,,,3--+--4,,,,,,,,,
  ,,,,,,,,,,:,,,,,&,,,,,,
  ,,,F,,,,,,:,,,,,,,,,,,,
  ,,,,,,$,,,:,,,,,,,!,,,,
  ,,T,,,,,,,:,,,,,,,,,T,,
  ,,,,,,,,,,@,,,,,,,,,,,,
""", r"""
  ...........,,,,,..........
  ..T....5HHHHHHH6.......T..
  .......V_______V..........
  .......V___>___V....^.....
  ..^....V_?_____V..........
  .......V_______V......T...
  .......7HHH+HHH8..........
  ...........:........&.....
  ...F.......:..............
  .....$.....:.........!....
  ..T........:..........T...
  ...........@..............
"""]


def build_watchtower(world, player, loc):
    rng = _loc_rng(world, loc)
    tpl = _Tpl(rng.choice(WATCHTOWER_TPL))
    sc = _new_scene(loc, tpl, "an old watch-wardens' tower", fg(235, 205, 120), world)
    name = loc["name"]
    f = _flags(player)
    # warden / keeper
    x, y = tpl.at("&")
    if loc.get("npc") == "warden_halvard":
        sc.add_entity(_npc(x, y, "Warden Halvard", "last of the watch-wardens", [
            "Forty years on these stairs. My knees hate me. The view never does.",
            "Light the beacons, keep the circuit. That's all a warden is.",
            "The wardens saw the dragon's first flight from this very roof. Nobody listened."],
            npc_id="warden_halvard", colour=fg(220, 220, 170)))
    else:
        lines = [f"Welcome to {name}. Mind the stairs — the third one bites.",
                 "From the top you can see half the continent on a clear day.",
                 "Bandits used to camp below. We stopped lighting the beacon. Now nobody comes."]
        sc.add_entity(_npc(x, y, rng.choice(["Old Sentry Bas", "Lookout Wenna", "Sergeant Pike", "Lookout Ilse"]),
                           "tower lookout", lines, colour=fg(210, 200, 160), ai="wander"))
    # lore note inside
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "watch_log", "Warden's logbook"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(20, 60), name="Supply crate"))
    # sometimes a prowler waits outside
    if rng.random() < 0.6 and _alive(player, f"cleared:{name}:1"):
        ex, ey = tpl.at("!")
        zone = {"C": "snow", "D": "desert", "B": "mountain"}.get(loc.get("continent"), "forest")
        sc.add_entity(_foe(ex, ey, loc, 1, "Prowler", "w", lambda pl: _enemy(pl, loc, zone=zone)))
    sx, sy = tpl.at(">")

    def climb(s, pl):
        radius = 26 if _flags(pl).get("watch_warden") else 18
        n = _reveal_area(world, loc, radius)
        key = f"climbed:{name}"
        first = not _flags(pl).get(key)
        _flags(pl)[key] = True
        s.talk_box(Entity(0, 0, "@", C_GOLD, "Tower roof"),
                   f"You climb the winding stair to the beacon platform. The land spreads out below you"
                   f" — roads, rivers, smoke from distant chimneys. {n} new tiles of the world map are revealed."
                   + (" You relight the old beacon; somewhere far away, another fire answers." if first else ""), pl)
        return f"{C_GOLD}★ The view from {name} reveals the surrounding land.{R_}"
    sc.add_door(sx, sy, "Climb to the beacon", climb, tile="<")
    return sc


SHRINE_TPL = r"""
  ...............................
  ...T.....5HHHHHHHHHHH6.....T...
  .........Vp....A....pV.........
  ..T......V.....>.....V......T..
  .........V..f.....f..V.........
  .........Vp.........pV.........
  .........7HHHH...HHHH8.........
  ..............:................
  ....T.........:..&.......T.....
  ..............:................
  ..............@................
"""


def build_shrine(world, player, loc):
    rng = _loc_rng(world, loc)
    god = loc.get("god", "Solara")
    domain, desc, rgb = GODS.get(god, GODS["Solara"])
    ground = {"C": "*", "D": "z"}.get(loc.get("continent"), ",")
    text = SHRINE_TPL.replace(".", ground)
    tpl = _Tpl(text)
    tpl.rows = _sprinkle(tpl.rows, rng, ground, ["T", "^", "f"] if ground != "z" else ["^"], 6)
    sc = _new_scene(loc, tpl, f"shrine of {god}, {desc.split(',')[0]}", fg(*rgb), world)
    x, y = tpl.at("&")
    sc.add_entity(_npc(x, y, f"Sister of {god}" if rng.random() < .5 else f"Brother of {god}", "shrine keeper", [
        f"{god} is {desc}. Kneel at the altar and be heard.",
        "Pilgrims who pray at all six shrines are said to be watched over for life.",
        "The gods ask little. A moment of quiet. A little courage. Sometimes a lot of courage."],
        colour=fg(*rgb), ai="wander"))
    ax, ay = tpl.at(">")

    def pray(s, pl):
        f = _flags(pl)
        first = not f.get(f"blessed:{god}")
        pl.hp = pl.max_hp
        pl.mp = pl.max_mp
        try:
            pl.status_effects.clear()
        except Exception:
            pass
        msg = f"{fg(*rgb)}★ {god} hears your prayer. HP and MP restored.{R_}"
        if first:
            f[f"blessed:{god}"] = True
            bonus = {"Solara": "max_hp", "Morrin": "max_mp", "Kaelos": "atk",
                     "Vessa": "stealth", "Nerys": "both", "Thalor": "defense"}[god]
            if bonus == "max_hp":
                pl.max_hp += 12; pl.hp = pl.max_hp; txt = "Max HP +12"
            elif bonus == "max_mp":
                pl.max_mp += 10; pl.mp = pl.max_mp; txt = "Max MP +10"
            elif bonus == "atk":
                pl.atk += 3; txt = "ATK +3"
            elif bonus == "stealth":
                pl.stealth = getattr(pl, "stealth", 0) + 2; txt = "Stealth +2"
            elif bonus == "defense":
                pl.defense += 3; txt = "DEF +3"
            else:
                pl.max_hp += 6; pl.max_mp += 5; pl.hp = pl.max_hp; pl.mp = pl.max_mp; txt = "Max HP +6, Max MP +5"
            s.talk_box(Entity(0, 0, "†", fg(*rgb), f"The altar of {god}"),
                       f"Light pools around the altar and something vast and kind regards you. "
                       f"The blessing of {god} settles into your bones: {txt}, permanently.", pl)
            msg = f"{fg(*rgb)}★ Blessing of {god}: {txt}!{R_}"
        return msg
    sc.add_door(ax, ay, f"Pray to {god}", pray, tile="I")
    return sc


BANDIT_CAMP_TPL = r"""
  TT,,,,,TT,,,,,,,,,TT,,,,,,TT
  T,,,M,,,,,,,,M,,,,,,,,,M,,,T
  ,,,,,,,,PPPPPPPPPPPP,,,,,,,,
  ,,,!,,,,P,,,,U,,,U,P,,,!,,,,
  ,,,,,,,,P,,,,,F,,,,P,,,,,,,,
  ,M,,,,,,P,!,,,,,,$,P,,,,,M,,
  ,,,,,,,,P,,,,?,,,,,P,,,,,,,,
  ,,,,,,,,PPPPP,,PPPPP,,,,,,,,
  ,,T,,,,,,,,,,:,,,,,,,,,,T,,,
  ,,,,,,,,,,,,,:,,,,,,,!,,,,,,
  TT,,,,,,,,,,,@,,,,,,,,,,,,TT
"""


def build_bandit_camp(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"D": "z", "C": "*"}.get(loc.get("continent"), ",")
    text = BANDIT_CAMP_TPL.replace(",", ground) if ground != "," else BANDIT_CAMP_TPL
    tpl = _Tpl(text)
    sc = _new_scene(loc, tpl, "a bandit encampment — Rourke's colours fly here", fg(225, 90, 60), world)
    _flags(player)["found_bandit_camp"] = True
    zone = {"D": "desert", "B": "mountain", "C": "snow"}.get(loc.get("continent"), "plains")
    names = ["Bandit", "Bandit", "Cutthroat", "Bandit"]
    for i, (x, y) in enumerate(tpl.all("!")):
        if _alive(player, f"cleared:{loc['name']}:{i}"):
            nm = names[i % len(names)]
            sc.add_entity(_foe(x, y, loc, i, nm, "B" if nm == "Bandit" else "C",
                               (lambda n: (lambda pl: _enemy(pl, loc, name=n, zone=zone)))(nm),
                               ai="lurk" if i % 2 else "wander", lurk=bool(i % 2)))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=0, gold=(60, 140), name="Stolen strongbox"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "rourke_orders", "Bandit orders", "?"))
    return sc


HIDEOUT_TPL = r"""
  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  ^^^EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE^^^^
  ^^EEJJJJJJJJEEEEEJJJJKJJJJEEEEEJJJJ$JE^^
  ^^EJJJ!JJJJJJJJJJJJJJJJJJJJJJJJJJ!JJJE^^
  ^^EJJJJJJJJEEEEEJJJJJJJJJJEEEEEJJJJJJE^^
  ^^EEEEEJJJEE^^^EEEEEJJEEEEE^^^EEJJJEEE^^
  ^^^^^^EJJJE^^^^^^^^EJJE^^^^^^^^EJJJE^^^^
  ^^^^^^EJ!JEEEEEEEEEEJJEEEEEEEEEEJJJE^^^^
  ^^^^^^EJJJJJJJJJ!JJJJJJJJJ?JJJJJJJJE^^^^
  ^^^^^^EEEEEEEEEEEEEJJEEEEEEEEEEEEEEE^^^^
  ,,,,,,,,,,,,,PPPPPPJJPPPPPP,,,,,,,,,,,,,
  ,,T,,,,,,,,,,P,!,,,::,,,,,P,,,,,,,T,,,,,
  ,,,,,,,,,,,,,P,,,,,::,,,F,P,,,,,,,,,,,,,
  ,,,,T,,,,,,,,PPPPPP::PPPPPP,,,,,,T,,,,,,
  ,,,,,,,,,,,,,,,,,,,::,,,,,,,,,,,,,,,,,,,
  ,,,,,,,,,,,,,,,,,,,@:,,,,,,,,,,,,,,,,,,,
"""


def build_bandit_hideout(world, player, loc):
    tpl = _Tpl(HIDEOUT_TPL)
    sc = _new_scene(loc, tpl, "the Bandit King's mountain hideout", fg(200, 50, 50), world, sight=8)
    _flags(player)["found_bandit_camp"] = True
    name = loc["name"]
    for i, (x, y) in enumerate(tpl.all("!")):
        if _alive(player, f"cleared:{name}:{i}"):
            nm = ["Bandit", "Cutthroat", "Bandit", "Cutthroat", "Bandit"][i % 5]
            lurk = y < 10 and i % 2 == 1
            sc.add_entity(_foe(x, y, loc, i, nm, "B" if nm == "Bandit" else "C",
                               (lambda n: (lambda pl: _enemy(pl, loc, name=n, zone="plains", bonus=1)))(nm),
                               ai="lurk" if lurk else "wander", lurk=lurk))
    bx, by = tpl.at("K")

    def rourke_down(sc_, pl, e):
        f = _flags(pl)
        f["rourke_defeated"] = True
        sc_.talk_box(e, "Rourke staggers against his throne of stolen chests. 'Take it, then. Take it all. "
                        "There's always another king...' He does not get up again.", pl)
        return f"{C_GOLD}★ Bandit King Rourke is defeated! His strongbox is yours.{R_}"
    if _alive(player, f"cleared:{name}:boss"):
        boss = _foe(bx, by, loc, "boss", "Bandit King Rourke", "R", lambda pl: _boss("Bandit King Rourke", pl),
                    ai="static", boss=True, on_win=rourke_down, colour=fg(255, 80, 60))
        boss.title = "the Bandit King"
        sc.add_entity(boss)
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=2, gold=(300, 600), extra=["Hi-Potion"],
                             name="Rourke's strongbox"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "rourke_ledger", "Rourke's ledger"))
    return sc


VILLAGE_TPL = r"""
  ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
  ,,T,,%%%%%,,,,,,,,,,,,,,,,%%%%%,,,T,,
  ,,,,,%___%,,,,qqqqqqqq,,,,%___%,,,,,,
  ,,,,,%%+%%,,,,qqqqqqqq,,,,%%+%%,,,,,,
  ,,,,,,,:,,,,,,,,,,,,,,,,,,,,:,,,,,,,,
  ,,,,,,,:::::::::::o::::::::::,,,!,,,,
  ,,,,,,,,,,,,,,,,,,:,,,,,,,,,,,,,,,,,,
  ,,T,,%%%%%%,,,,,,,:,,,,,,%%%%%,,,,,,,
  ,,,,,%____%,,,,!,,:,,,,,,%___%,,,T,,,
  ,,,,,%%%+%%,,,,,,,:,,,,,,%%+%%,,,,,,,
  ,,,,,,,,:,,,,,,,,,:,,,,,,,,:,,,,,,,,,
  ,,,,,,,,::::::::::::::::::::,,,,,,,,,
  ,,T,,,,,,,,,,,,,,,:,,,,,,,,,,,,,,T,,,
  ,,,,,,,,,,,,,,,,,,@,,,,,,,,,,,,,,,,,,
"""

VILLAGE_FINDS = [
    ("lore", None), ("loot", None), ("ambush", "Skeleton"), ("gold", None), ("lore", None),
]


def build_abandoned_village(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"C": "*", "E": ","}.get(loc.get("continent"), ",")
    text = VILLAGE_TPL.replace(",", ground) if ground != "," else VILLAGE_TPL
    tpl = _Tpl(text)
    tpl.rows = _sprinkle(tpl.rows, rng, ground, ["T", "R", "^"], 8)
    hollow = loc.get("special") == "hollowmere"
    sub = "doors marked with a sewn-shut eye" if hollow else "an empty village, tables still set"
    sc = _new_scene(loc, tpl, sub, fg(160, 155, 150), world, night=hollow)
    doors = sc.find("+")
    finds = list(VILLAGE_FINDS)
    rng.shuffle(finds)
    lore_keys = (["hollowmere_marks", "hollowmere_diary"] if hollow else
                 ["empty_village", "village_letter"])
    li = 0
    for i, (dx, dy) in enumerate(doors):
        kind, foe = finds[i % len(finds)]
        if kind == "lore":
            key = lore_keys[li % len(lore_keys)]
            li += 1
        else:
            key = None
        fkey = f"chest:{loc['name']}:house{i}"

        def search(s, pl, kind=kind, foe=foe, key=key, fkey=fkey, i=i):
            f = _flags(pl)
            if f.get(fkey) and kind != "lore":
                return f"{C_DIM}You already searched this house. Dust and silence.{R_}"
            f[fkey] = True
            if kind == "lore":
                return read_lore(s, pl, Entity(0, 0, "?", C_CYAN, "Abandoned house"), key)
            if kind == "ambush":
                s.talk_box(Entity(0, 0, "!", C_RED, "Abandoned house"),
                           "Something was waiting in the dark under the stairs.", pl)
                res = s.fight(pl, _enemy(pl, loc, name=foe, zone="dungeon"))
                if res == "victory":
                    r2 = _loc_rng(world, loc, f"amb{i}")
                    return f"{C_GREEN}Behind it, a hidden stash:{R_} " + _give(pl, _loot(pl, r2, 1))
                if res == "escaped":
                    f.pop(fkey, None)
                return None
            r2 = _loc_rng(world, loc, f"house{i}")
            if kind == "gold":
                g = r2.randint(30, 80) + pl.level * 5
                pl.gold += g
                return f"{C_GOLD}A purse under a loose floorboard: +{g} gold.{R_}"
            return f"{C_GOLD}In a cupboard:{R_} " + _give(pl, _loot(pl, r2))
        sc.add_door(dx, dy, "Search the house", search)
    for i, (x, y) in enumerate(tpl.all("!")):
        if _alive(player, f"cleared:{loc['name']}:{i}"):
            foe = "Shadow Beast" if hollow else ("Frost Wraith" if ground == "*" else "Skeleton")
            sc.add_entity(_foe(x, y, loc, i, foe, foe[0], (lambda n: lambda pl: _enemy(pl, loc, name=n, zone="dungeon"))(foe),
                               ai="lurk", lurk=True))
    wx, wy = sc.find("o")[0] if sc.find("o") else (1, 1)
    sc.add_entity(_lore_ent(wx + 1, wy, "village_well" if not hollow else "hollowmere_well", "Village well sign"))
    return sc


WIZARD_TPL = r"""
  ,,,,,,,,,,,,,,,,,,,,,,,,,,
  ,,T,,,,5HHHHHHHHH6,,,,,T,,
  ,,,,,,,Vyyyy_yyyyV,,,,,,,,
  ,,,,,,,V____&____V,,,,,,,,
  ,,,,^,,V_t_____?_V,,,^,,,,
  ,,,,,,,V____O____V,,,,,,,,
  ,,,,,,,V$_______pV,,,,,,,,
  ,,,,,,,7HHHH+HHHH8,,,,,,,,
  ,,T,,,,,,,,,:,,,,,,,,,T,,,
  ,,,,,,,,,,,,:,,,,,,,,,,,,,
  ,,,,,,,,,,,,@,,,,,,,,,,,,,
"""


def build_wizard_tower(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"C": "*"}.get(loc.get("continent"), ",")
    text = WIZARD_TPL.replace(",", ground) if ground != "," else WIZARD_TPL
    tpl = _Tpl(text)
    sc = _new_scene(loc, tpl, "a tower humming with old magic", fg(170, 120, 255), world)
    npc = loc.get("npc", "magus_mirelle")
    x, y = tpl.at("&")
    if npc == "magus_quellan":
        name, title = "Magus Quellan", "frost-wizard, gambler, genius (self-described)"
        lines = ["A portal to the moon! Why not? Somebody has to be first.",
                 "Mirelle says my theories are 'brave'. She means stupid. She is wrong.",
                 "Cold is just magic standing still. Bring me Frost Crystals sometime."]
        lore = "quellan_notes"
    else:
        name, title = "Magus Mirelle", "scholar of curses and dragon-lore"
        lines = ["Books first, swords later. You would be amazed how often that order saves lives.",
                 "Dragons, curses, lost kingdoms — everything in this world is written down somewhere.",
                 "Mind the bookshelves. Some of them bite. That one especially."]
        lore = "mirelle_notes"

    def gift(sc_, pl, e):
        f = _flags(pl)
        if not f.get(f"gift:{npc}"):
            f[f"gift:{npc}"] = True
            sc_.talk_box(e, "A traveller with sense enough to visit a library. Take these — I brew them by the barrel.", pl)
            return f"{C_PURP}Received:{R_} " + _give(pl, _make("Hi-Ether")) + " " + _give(pl, _make("Hi-Ether"))
        sc_.talk_box(e, rng.choice(lines), pl)
        return None
    sc.add_entity(_npc(x, y, name, title, lines, npc_id=npc, colour=fg(200, 150, 255), interact=_with_story(gift)))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, lore, "Open spellbook"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=1, gold=(40, 90), extra=["Mana Stone"], name="Reagent chest"))
    ox, oy = sc.find("O")[0]

    def orb(s, pl, e):
        n = _reveal_area(world, loc, 12)
        return f"{C_PURP}The scrying orb clouds, then clears: the land around the tower ({n} tiles) is revealed.{R_}"
    sc.set_tile(ox, oy, "_")
    sc.add_entity(Entity(ox, oy, "●", fg(200, 150, 255), "Scrying orb", kind="object", interact=orb))
    return sc


OBELISK_TPL = r"""
  zzzzzzzzzzzzzzzzzzzzzzzzz
  zzz^zzzzzzzzzzzzzzzzz^zzz
  zzzzzzzzpzzzzzzzpzzzzzzzz
  zzzzzzzzzIIIIIIIzzzzzzzzz
  zzzzzpzzzIIIOIIIzzzpzzzzz
  zzzzzzzzzIII>IIIzzzzzzzzz
  zzzzzzzzzIIIIIIIzzzzzzzzz
  zzzzzzzzpzzz?zzzpzzzzzzzz
  zzzzzzzzzzzzzzzzzzzzzzzzz
  zzz^zzzzzzzzzzzzzzzz!zzzz
  zzzzzzzzzzzz@zzzzzzzzzzzz
"""


def build_obelisk(world, player, loc):
    ground = {"D": "z", "C": "*", "E": ","}.get(loc.get("continent"), ",")
    text = OBELISK_TPL.replace("z", ground)
    tpl = _Tpl(text)
    sc = _new_scene(loc, tpl, "a rune-stone older than any kingdom", fg(200, 130, 255), world, night=True)
    name = loc["name"]
    lore = "starfall" if loc.get("special") == "starfall" else "obelisks"
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, lore, "Weathered inscription"))
    ex, ey = tpl.at("!")
    if _alive(player, f"cleared:{name}:0"):
        zone = {"D": "desert", "C": "snow"}.get(loc.get("continent"), "plains")
        sc.add_entity(_foe(ex, ey, loc, 0, "Rune-drawn beast", "x", lambda pl: _enemy(pl, loc, zone=zone, bonus=1),
                           ai="chase"))
    ax, ay = tpl.at(">")

    def touch(s, pl):
        f = _flags(pl)
        if not f.get(f"attuned:{name}"):
            f[f"attuned:{name}"] = True
            pl.mp = pl.max_mp
            s.talk_box(Entity(0, 0, "!", C_PURP, name),
                       "You lay a hand on the rune. It flares violet and something clicks into place behind your eyes: "
                       "you are ATTUNED. From any attuned obelisk you can step to any other.", pl)
        others = [l for l in world.locations if l.get("type") == "obelisk" and l["name"] != name
                  and f.get(f"attuned:{l['name']}")]
        if not others:
            return f"{C_PURP}The stone hums, waiting for a second attuned obelisk somewhere in the world.{R_}"
        opts = [(str(i + 1), f"Step to {l['name']}") for i, l in enumerate(others[:8])]
        opts.append(("0", "Stay here"))
        k = s.choice_box("The rune-light opens a path. Where will you go?", opts)
        if not k or k == "0":
            return None
        dest = others[int(k) - 1]
        world.player_x, world.player_y = dest["x"], dest["y"]
        try:
            world._reveal(radius=8)
        except Exception:
            pass
        _story(pl, "on_visit", dest["name"], pl, dest.get("type"))
        s.leave(f"travel:{dest['name']}")
        return None
    sc.add_door(ax, ay, "Touch the rune-stone", touch, tile="I")
    return sc


CARAVAN_TPL = r"""
  zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
  zzzMzzzzzzzMzzzzzzzzMzzzzzzMzz
  zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
  zzzzcbczzzzzzzzFzzzzzzzzsszzzz
  zzzzzzzzzz&zzzzzzzzz?zzzzzzzzz
  zzzzzzzzzzzzzzUzUzzzzzzzzKzzzz
  zzzzBBBzzzzzzzzzzzzzzzzzzzzzzz
  zzzzzzzzzzzzzzzzzzzzzzzzzzzTzz
  zzTzzzzzzzzzz$zzzzzzzzzzzzzzzz
  zzzzzzzzzzzzzz@zzzzzzzzzzzzzzz
"""

CARAVAN_WARES = [("Antidote", 20), ("Hi-Potion", 45), ("Hi-Ether", 55), ("Fire Bomb", 40),
                 ("Smoke Bomb", 45), ("Strength Draught", 80), ("Venom Fang", 60), ("Scale Fragment", 70)]


def build_caravan(world, player, loc):
    rng = _loc_rng(world, loc)
    tpl = _Tpl(CARAVAN_TPL)
    sc = _new_scene(loc, tpl, "spice, silk and gossip under the desert stars", fg(240, 180, 90), world)
    x, y = tpl.at("&")
    master = rng.choice(["Qasim", "Yusra", "Old Fahd", "Nadira"])
    sc.add_entity(_npc(x, y, f"{master} the Caravan Master", "keeps the camels and the peace", [
        "Sit, sit. Water first, business after. That is the law of the sands.",
        "Scorpions took our rear wagon two nights ago. My daughter was on it.",
        "The Sunspire Sultan buys our dates. Everyone buys our dates. They are very good dates."],
        npc_id="caravan_master", colour=fg(240, 190, 110)))
    mx, my = tpl.at("K")

    def shop(sc_, pl, e):
        wares = rng.sample(CARAVAN_WARES, 5)
        opts = [(str(i + 1), f"{n:<16} {C_GOLD}{p}g{R_}") for i, (n, p) in enumerate(wares)]
        opts.append(("0", "Nothing today"))
        k = sc_.choice_box(f"'Finest goods this side of the dunes.' (You have {pl.gold}g)", opts, e)
        if not k or k == "0":
            return None
        n, p = wares[int(k) - 1]
        if pl.gold < p:
            return f"{C_RED}'Come back with more coin, friend.'{R_}"
        it = _make(n)
        if it is None:
            return None
        if pl.add_item(it):
            pl.gold -= p
            return f"{C_GOLD}Bought {n} for {p}g.{R_}"
        return f"{C_RED}Your bag is full.{R_}"
    sc.add_entity(_npc(mx, my, rng.choice(["Rashid", "Lailah", "Tarek"]), "spice merchant",
                       ["Spices, potions, scorpion venom — all fresh!"], colour=fg(250, 210, 120), interact=shop))
    lx, ly = tpl.at("?")
    sc.add_entity(_npc(lx, ly, "A musician", "plays an oud by the fire", [
        "♪ The sands remember every footstep... ♪",
        "Sing with me! No? Your loss.",
        "I once played for the Sultan himself. He fell asleep. Highest compliment."], colour=fg(200, 230, 160), ai="static"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(20, 50), extra=["Antidote"], name="Gift basket"))
    return sc


FISHING_TPL = r"""
  ~~~~~~~~~~~~~~~~~~~~~~~~~~
  ~~~~~~~~~~~~~~~~~~~~~~~~~~
  ~~~~~~~ww~~~~~~~ww~~~~~~~~
  ~~~~~~www==>=wwwww~~~~~~~~
  ~~wwwwwwww=wwwwwwwwwww~~~~
  zzzzzzzzzz=zzzzzzzzzzzzzzz
  zzzN%%%%%zzzzzzzBzzzzzzzzz
  zzzz%_&_%zzzzzzzzzzzN?zzzz
  zzzz%%+%%zzzzzzbzzzzzzzzzz
  zzzzzz:zzzzz$zzzzzzzzzzzzz
  zzzzzz@zzzzzzzzzzzzzzzzzzz
"""


def build_fishing_hut(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"C": "*"}.get(loc.get("continent"), "z")
    tpl = _Tpl(FISHING_TPL.replace("z", ground))
    sc = _new_scene(loc, tpl, "salt, nets and a crackling stove", fg(110, 190, 230), world)
    x, y = tpl.at("&")
    fisher = rng.choice(["Old Tam", "Grandmother Ysolde", "Fenn", "Marta Netwright"])
    sc.add_entity(_npc(x, y, fisher, "fisher", [
        "The fish bite best when you stop wanting them to. Like most things.",
        "Saw a sea serpent once. Or a very long log. Fifty years and I still can't decide.",
        "Take the pier. Mind the loose plank. All the planks are loose."], colour=fg(140, 200, 230)))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "fisher_tales", "Carved oar"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(15, 40), name="Tackle box"))
    fx, fy = tpl.at(">")

    def fish(s, pl):
        f = _flags(pl)
        key = f"fished:{loc['name']}"
        now = getattr(world, "turn_count", 0)
        last = f.get(key)
        if isinstance(last, int) and now - last < 40:
            return f"{C_DIM}The fish have gone quiet. Come back after a good walk.{R_}"
        f[key] = now
        r = random.random()
        if r < 0.15:
            return f"{C_DIM}Nothing bites. You enjoy the sea air anyway.{R_}"
        if r < 0.75:
            g = random.randint(10, 25) + pl.level * 2
            pl.gold += g
            return f"{fg(140, 200, 230)}You land a fine catch and sell it to {fisher}: +{g} gold.{R_}"
        if r < 0.95:
            return f"{fg(140, 200, 230)}Something glints on your hook:{R_} " + _give(pl, _make(random.choice(["Hi-Potion", "Regen Tonic", "Ether", "Antidote"])))
        return f"{C_GOLD}★ A pearl-studded box on the line!{R_} " + _give(pl, _loot(pl, random.Random(), 2))
    sc.add_door(fx, fy, "Cast a line", fish, tile="=")
    return sc


GRAVEYARD_TPL = r"""
  ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
  ,,T,,%%%%%%%%%%%%%%%%%%%%%,,T,,
  ,,,,,%,G,G,G,,,,,,G,G,G,,%,,,,,
  ,,,,,%,,,,,,,#####,,,,,,,%,,,,,
  ,,,,,%,G,G,!,#_$_#,!,G,G,%,,,,,
  ,,,,,%,,,,,,,##+##,,,,,,,%,,,,,
  ,,,,,%,G,G,G,,,:,,,G,?,G,%,,,,,
  ,,,,,%,,,,,,,,,:,,,,,,,,,%,,,,,
  ,,,,,%,G,!,G,,,:,,,G,G,G,%,,,,,
  ,,,,,%%%%%%%,,,:,,,%%%%%%%,,,,,
  ,,T,,,,,,,,,,&,:,,,,,,,,,,,,T,,
  ,,,,,,,,,,,,,,,@,,,,,,,,,,,,,,,
"""

EPITAPHS = [
    "HERE LIES GARRET WICK. HE DID NOT BELIEVE IN GHOSTS. — Not the most reassuring epitaph.",
    "BELOVED MOTHER, TERRIBLE COOK. — Someone has left a single burnt biscuit on the stone.",
    "SHE CLIMBED EVERY MOUNTAIN BUT THE LAST. — Fresh flowers. Somebody still remembers.",
    "THE SEA TOOK HIM. THE SEA CAN KEEP HIM. — Scratched in angry letters.",
    "REST, SOLDIER. THE WAR IS OVER. — The stone is newer than the war it mentions.",
    "WE BURIED HIM TWICE. — There is no explanation. You decide not to ask.",
]


def build_graveyard(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"C": "*"}.get(loc.get("continent"), ",")
    text = GRAVEYARD_TPL.replace(",", ground) if ground != "," else GRAVEYARD_TPL
    tpl = _Tpl(text)
    sc = _new_scene(loc, tpl, "crooked headstones under a cold moon", fg(190, 200, 190), world, night=True)
    x, y = tpl.at("&")
    npc = loc.get("npc", "gravekeeper")
    sc.add_entity(_npc(x, y, rng.choice(["Gravekeeper Osk", "Gravekeeper Hild", "Old Mortimer"]), "gravekeeper", [
        "They don't stay down like they used to. Not since the crypts were opened.",
        "Bring a light. And a shovel. And a better sword than that.",
        "Every stone here has a story. Most of them end the same way."],
        npc_id=npc, colour=fg(170, 190, 170)))
    stones = sc.find("G")
    rng.shuffle(stones)
    for i, (gx, gy) in enumerate(stones[:6]):
        text_ = EPITAPHS[i % len(EPITAPHS)]
        sc.add_entity(Entity(gx, gy, "†", fg(200, 205, 200), "Headstone", kind="object",
                             interact=(lambda t: lambda s, pl, e: s.talk_box(e, t, pl))(text_)))
    # restless dead rise every night you visit (not persistent)
    for i, (ex, ey) in enumerate(tpl.all("!")):
        sc.add_entity(_foe(ex, ey, loc, i, "Risen dead", "S", lambda pl: _enemy(pl, loc, name="Skeleton", zone="dungeon"),
                           ai="lurk", lurk=True, persistent=False, colour=fg(200, 220, 200)))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=1, gold=(50, 120), extra=["Holy Water"], name="Mausoleum offering"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "ashen_barrow" if loc["name"] == "Ashen Barrow" else "graveyards", "Cracked tablet"))
    return sc


LODGE_TPL = r"""
  TTTTTTTTTTTTTTTTTTTTTTTTTTTT
  TT,,,,,,,,,,,,,,,,,,,,,,,,TT
  T,,,%%%%%%%%%%%%%,,,,,,,,,,T
  T,,,%___t__?___F%,,,,N,,,,,T
  T,,,%_&_________%,,,,,,,,,,T
  T,,,%________$U_%,,,,,,>,,,T
  T,,,%%%%%%+%%%%%%,,,,,,,,,,T
  T,,,,,,,,,:,,,,,,,,,,,,,,,,T
  TT,,,,,,,,:,,,,,,,,,,,,,,,TT
  TTTTTTTTTT@TTTTTTTTTTTTTTTTT
"""


def build_hunting_lodge(world, player, loc):
    rng = _loc_rng(world, loc)
    ground = {"C": "*"}.get(loc.get("continent"), ",")
    text = LODGE_TPL.replace(",", ground) if ground != "," else LODGE_TPL
    tpl = _Tpl(text)
    sc = _new_scene(loc, tpl, "antlers over the door, a fire in the hearth", fg(180, 130, 80), world)
    x, y = tpl.at("&")
    hunter = rng.choice(["Huntmaster Brann", "Old Greta", "Vilmar Longshot"])

    def rest(sc_, pl, e):
        k = sc_.choice_box(f"'Stew and a bunk for 15 gold. Or a hunt, if you've the nerve.' (Gold {pl.gold})",
                           [("1", "Stew and a bunk (15g) — restore HP/MP"), ("2", "Ask about the trophy board"), ("0", "Leave")], e)
        if k == "1":
            if pl.gold < 15:
                return f"{C_RED}'No coin, no stew.'{R_}"
            pl.gold -= 15
            pl.hp, pl.mp = pl.max_hp, pl.max_mp
            return f"{C_GREEN}You eat, sleep, and wake restored.{R_}"
        if k == "2":
            return read_lore(sc_, pl, e, "great_hunt")
        return None
    sc.add_entity(_npc(x, y, hunter, "master of the lodge", [], colour=fg(200, 160, 100), interact=rest))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "great_hunt", "Trophy board"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(30, 70), extra=["Wolf Pelt"], name="Pelt chest"))
    hx, hy = tpl.at(">")

    def hunt(s, pl):
        f = _flags(pl)
        key = f"hunted:{loc['name']}"
        now = getattr(world, "turn_count", 0)
        last = f.get(key)
        if isinstance(last, int) and now - last < 60:
            return f"{C_DIM}The game has fled these woods for now.{R_}"
        k = s.choice_box("Fresh tracks lead into the trees. Follow them?", [("y", "Hunt"), ("n", "Not now")])
        if k != "y":
            return None
        f[key] = now
        prey = "Snow Beast" if loc.get("continent") == "C" else random.choice(["Wolf", "Rock Wolf", "Wolf"])
        zone = "snow" if loc.get("continent") == "C" else "forest"
        res = s.fight(pl, _enemy(pl, loc, name=prey, zone=zone))
        if res == "victory":
            return f"{C_GREEN}A clean hunt.{R_} " + _give(pl, _make("Wolf Pelt" if prey != "Snow Beast" else "Frost Crystal"))
        return None
    sc.add_door(hx, hy, "Follow the tracks", hunt, tile=":")
    return sc


BONES_TPL = r"""
  ^^^^^,,,,,,,,,,,,,,,,,,,,,,,^^^^^
  ^^^,,,,,,,,,,,,,,,,,,,,,,,,,,,^^^
  ^,,,,,,,W,,W,,W,,W,,W,,,,,,,,,,^^
  ^,,,Z,YYYYYYYYYYYYYYYYYY,,,,,,,,^
  ^,,,,,,,X,,X,,X,,X,,X,,,!,,,,,,,^
  ^,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,^
  ^,,,,,,,,,,IIIII,,,,,,,,,,$,,,,,^
  ^,,,!,,,,,,II>II,,,,,,,,,,,,,,,,^
  ^^,,,,,,,,,IIIII,,,?,,,,,,,,,,,^^
  ^^^,,,,,,,,,,,,,,,,,,,,,,,,,,^^^^
  ^^^^^,,,,,,,,,,,,@,,,,,,,,,,^^^^^
"""


def build_dragon_bones(world, player, loc):
    ground = {"D": "z", "C": "*"}.get(loc.get("continent"), ",")
    tpl = _Tpl(BONES_TPL.replace(",", ground))
    wyrm = loc.get("special") == "wyrm"
    sc = _new_scene(loc, tpl, "the bones of something that once ruled the sky", fg(240, 235, 215), world)
    name = loc["name"]
    foe = "Cultist" if wyrm else "Sand Wyrm"
    for i, (x, y) in enumerate(tpl.all("!")):
        if _alive(player, f"cleared:{name}:{i}"):
            sc.add_entity(_foe(x, y, loc, i, "Ashen Choir cultist" if wyrm else "Sand Wyrm", "C" if wyrm else "W",
                               (lambda pl: _enemy(pl, loc, name=foe, zone="dungeon" if wyrm else "desert", bonus=1)),
                               ai="lurk" if i else "wander", lurk=bool(i)))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=1, gold=(60, 150), extra=["Scale Fragment"], name="Bone hoard"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "wyrm_graveyard" if wyrm else "sand_wyrm_bones", "Scorched tablet"))
    ax, ay = tpl.at(">")

    def circle(s, pl):
        if wyrm:
            return read_lore(s, pl, Entity(0, 0, "○", C_PURP, "Ritual circle"), "brand_of_ash")
        return f"{C_DIM}Wind hisses through the ribs like a breath that never ends.{R_}"
    sc.add_door(ax, ay, "Examine the circle", circle, tile="I")
    return sc


WRECK_TPL = r"""
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  ~~~~jjjjjjjjjjjjjjjjjjjjj~~~~~~
  ~~~jiiiiiiiiiiiiiiiiiiiiij~~~~~
  ~~jiiihhhhhhhhhhhhhhhhiiiij~~~~
  ~jiiihdd$ddhddd!dddddhhiiiij~~~
  ~jiiihddddd+ddddddd?ddhiiiiij~~
  ~jiiihhhhhhh+hhhhhhhhhhiiiij~~~
  ~~jiiiiiiiii:iiiiiii!iiiiij~~~~
  ~~~jjiiiiiii:iiiiiiiiiijjj~~~~~
  ********iiii:iiii**************
  ************@******************
"""


def build_frozen_wreck(world, player, loc):
    tpl = _Tpl(WRECK_TPL)
    morrow = loc.get("special") == "morrow"
    sc = _new_scene(loc, tpl, "a ship locked in the ice for centuries", fg(170, 220, 250), world, night=True)
    name = loc["name"]
    for i, (x, y) in enumerate(tpl.all("!")):
        if _alive(player, f"cleared:{name}:{i}"):
            sc.add_entity(_foe(x, y, loc, i, "Frozen sailor", "W",
                               lambda pl: _enemy(pl, loc, name="Frost Wraith", zone="snow"),
                               ai="lurk", lurk=True, colour=fg(170, 220, 255)))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, bonus=1, gold=(80, 200), extra=["Frost Crystal"], name="Captain's chest"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "morrow_log" if morrow else "wreck_log", "Captain's log"))
    return sc


LIGHTHOUSE_TPL = r"""
  ~~~~~~~~~~~~~~~~~~~~~~~~~~
  ~~~~~~~~~~5HHH6~~~~~~~~~~~
  ~~~~~ww~~~V_l_V~~~ww~~~~~~
  ~~~wwzzzzzV_>_Vzzzzzww~~~~
  ~~wzzzzzzzV___Vzzzzzzzw~~~
  ~wzzzN?zzzV&__Vzzz$zzzzw~~
  ~zzzzzzzzz7H+H8zzzzzzzzzw~
  zzzzzzBzzzzz:zzzzzzzzzzzzz
  zzzzzzzzzzzz:zzzzzzzzzzzzz
  zzzzzzzzzzzz@zzzzzzzzzzzzz
"""


def build_lighthouse(world, player, loc):
    ground = {"C": "*", "B": ","}.get(loc.get("continent"), "z")
    tpl = _Tpl(LIGHTHOUSE_TPL.replace("z", ground))
    sc = _new_scene(loc, tpl, "a lamp that has never once gone out", fg(255, 240, 150), world)
    npc = loc.get("npc", "keeper")
    x, y = tpl.at("&")
    sc.add_entity(_npc(x, y, "Keeper Maris" if npc == "keeper_maris" else "Keeper Bram", "lighthouse keeper", [
        "Two hundred and twelve steps. I count them every night. Some nights there are two hundred and thirteen.",
        "Ships owe their lives to this lamp. They never write.",
        "The drowned walk out of the Tide Tomb when the lamp gutters. So I keep it lit."],
        npc_id=npc, colour=fg(255, 230, 150)))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "saltglass" if loc.get("special") == "saltglass" else "lighthouses", "Keeper's journal"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(30, 80), extra=["Ether"], name="Salvage crate"))
    sx, sy = tpl.at(">")

    def climb(s, pl):
        n = _reveal_area(world, loc, 22)
        return f"{fg(255, 240, 150)}From the lamp room the coast unrolls like a map: {n} tiles revealed.{R_}"
    sc.add_door(sx, sy, "Climb to the lamp", climb, tile="<")
    return sc


HERMIT_TPL = r"""
  ^^^,,,,,,,,,,,,,,,,,,,,^^^
  ^,,,,,,,T,,,,,,,,T,,,,,,,^
  ,,,,,,%%%%%%%,,,,,,,,,,,,,
  ,,,,,,%_&_t_%,,,,F,,,,,,,,
  ,,T,,,%___$_%,,,,,,,,T,,,,
  ,,,,,,%%%+%%%,,,,,,,?,,,,,
  ,,,,,,,,,:,,,,,,,,,,,,,,,,
  ,,,,,,,,,:,,,,,,,,,,,,,,,,
  ,,,,,,,,,@,,,,,,,,,,,,,,,,
"""

RIDDLES = [
    ("I have cities but no houses, forests but no trees, water but no fish. What am I?",
     [("1", "A map"), ("2", "A dream"), ("3", "A painting")], "1"),
    ("The more you take, the more you leave behind. What are they?",
     [("1", "Coins"), ("2", "Footsteps"), ("3", "Years")], "2"),
    ("What can run but never walks, has a mouth but never talks?",
     [("1", "A river"), ("2", "A bard"), ("3", "The wind")], "1"),
]

HERMITS = {
    "hermit_osric": ("Osric of the White Pass", "a hermit who was once something else",
                     ["I left the Veil thirty years ago. It has not left me.",
                      "Snow is honest. It shows every footprint. That is why I live here.",
                      "Sit. The kettle is almost singing."], "osric"),
    "hermit_zahra": ("Zahra Dune-Reader", "reads the future in shifting sand",
                     ["The sand says you will travel far. The sand says that to everyone. The sand is not very creative.",
                      "The Ashen Choir sang here once. The dunes still hum their hymn at night.",
                      "Water, child. Always water first."], "zahra"),
    "hermit_pell": ("Pell the Beachcomber", "collects what the sea forgets",
                    ["Every bottle on this beach has a message. Most of them say 'help'. Some say 'never mind'.",
                     "The Drowned King's ships still wash up, plank by plank.",
                     "Shells for your trouble? No? More for me."], "pell"),
}


def build_hermit_hut(world, player, loc):
    ground = {"C": "*", "D": "z"}.get(loc.get("continent"), ",")
    text = HERMIT_TPL.replace(",", ground) if ground != "," else HERMIT_TPL
    tpl = _Tpl(text)
    npc = loc.get("npc", "hermit_osric")
    name, title, lines, lore = HERMITS.get(npc, HERMITS["hermit_osric"])
    sc = _new_scene(loc, tpl, "a solitary hut far from any road", fg(170, 200, 140), world)
    x, y = tpl.at("&")

    def talk(sc_, pl, e):
        f = _flags(pl)
        rk = f"riddle:{npc}"
        if not f.get(rk):
            q, opts, ans = RIDDLES[sum(map(ord, npc)) % len(RIDDLES)]
            k = sc_.choice_box(f"'Answer my riddle and earn my gift.' {q}", opts + [("0", "Maybe later")], e)
            if k == ans:
                f[rk] = True
                sc_.talk_box(e, "Ha! Clever. Clever is rarer than gold out here. Take this.", pl)
                return f"{C_GREEN}The hermit's gift:{R_} " + _give(pl, _make("Elixir")) + " " + _give(pl, _make("Hero's Brew"))
            if k and k != "0":
                return f"{C_DIM}'No. Think on it. I'll be here. I'm always here.'{R_}"
            return None
        sc_.talk_box(e, random.choice(lines), pl)
        return None
    sc.add_entity(_npc(x, y, name, title, lines, npc_id=npc, colour=fg(190, 210, 160), interact=_with_story(talk)))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(10, 40), extra=["Potion"], name="Hermit's larder"))
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, f"hermit_{lore}", "Notes nailed to a post"))
    return sc


CAVE_TPL = r"""
  ^^^^^^^^^^^^^^^^^^^^^^^^
  ^^^^EEEEEEEEEEEEEEE^^^^^
  ^^^EEJJJJJJJJJJJJJEE^^^^
  ^^EEJJJJ?JJJJJJ$JJJEE^^^
  ^^EJJJJJJJJ>JJJJJJJJE^^^
  ^^EEJJJ!JJJJJJJJJJJEE^^^
  ^^^EEEEEJJJJJJEEEEEE^^^^
  ^^^^^^^EEJJJJEE^^^^^^^^^
  ,,,,,,,,,,JJ,,,,,,,,,,,,
  ,,T,,,,,,,::,,,,,,T,,,,,
  ,,,,,,,,,,@,,,,,,,,,,,,,
"""


def build_hidden_cave(world, player, loc):
    ground = {"C": "*", "D": "z"}.get(loc.get("continent"), ",")
    tpl = _Tpl(CAVE_TPL.replace(",", ground))
    sc = _new_scene(loc, tpl, "a cave mouth hidden by rock and root", fg(150, 140, 130), world, fog=True, sight=5)
    name = loc["name"]
    lx, ly = tpl.at("?")
    sc.add_entity(_lore_ent(lx, ly, "emberdeep" if name == "Emberdeep Hollow" else "hidden_caves", "Scratched warning"))
    cx, cy = tpl.at("$")
    sc.add_entity(_chest_ent(cx, cy, loc, 0, world, gold=(25, 70), name="Forgotten pack"))
    ex, ey = tpl.at("!")
    if _alive(player, f"cleared:{name}:0"):
        sc.add_entity(_foe(ex, ey, loc, 0, "Cave lurker", "x", lambda pl: _enemy(pl, loc, zone="dungeon"),
                           ai="lurk", lurk=True))
    dx, dy = tpl.at(">")
    cleared = _flags(player).get(f"dungeon_cleared_{name}")

    def descend(s, pl):
        k = s.choice_box(f"A narrow passage leads down into {name}"
                         + (" (cleared — treasure may remain)." if cleared else f". {loc.get('floors', 2)} floors deep. Something big lives at the bottom."),
                         [("y", "Descend"), ("n", "Not yet")])
        if k == "y":
            s.leave("dungeon")
        return None
    sc.add_door(dx, dy, "Descend into the depths", descend, tile="v")
    return sc


def _run_cave(world, player, loc):
    from game_dungeon import DungeonManager
    name = loc["name"]
    cleared = _flags(player).get(f"dungeon_cleared_{name}")
    boss = None if cleared else loc.get("boss", "Dungeon Warden")
    danger = DANGER.get(loc.get("continent", "A"), 2)
    d = DungeonManager(name, danger=danger, boss_name=boss, floors=loc.get("floors", 2))
    result = d.enter(player)
    if result == "cleared":
        _flags(player)[f"dungeon_cleared_{name}"] = True
        done = _story(player, "on_dungeon_clear", name, player)
        world._handle_story_completions(done)
        world.last_msg = f"{C_GOLD}★ {name} conquered!{R_}"
    elif not world._after_adventure(player):
        world.last_msg = f"{C_DIM}You climb out of {name}.{R_}"


BUILDERS = {
    "watchtower": build_watchtower,
    "shrine": build_shrine,
    "bandit_camp": build_bandit_camp,
    "bandit_hideout": build_bandit_hideout,
    "abandoned_village": build_abandoned_village,
    "wizard_tower": build_wizard_tower,
    "obelisk": build_obelisk,
    "caravan": build_caravan,
    "fishing_hut": build_fishing_hut,
    "graveyard": build_graveyard,
    "hunting_lodge": build_hunting_lodge,
    "dragon_bones": build_dragon_bones,
    "frozen_wreck": build_frozen_wreck,
    "lighthouse": build_lighthouse,
    "hermit_hut": build_hermit_hut,
    "hidden_cave": build_hidden_cave,
}


# ═════════════════════════════════════════════════════════════════
# Lore
# ═════════════════════════════════════════════════════════════════

LORE = {
    "watch_log": ("The Warden's Logbook",
                  "Day 1,204. Beacon lit at dusk. Answered by Briar Watch and Ironcrag. All quiet. Day 1,205. Beacon lit. "
                  "No answer. Day 1,206. No answer. Day 1,240. They say the circuit is 'no longer funded'. I lit it anyway."),
    "rourke_orders": ("Orders from the Hideout",
                      "By order of the King of the Road: every camp sends a third of its take to the Hideout by the new moon. "
                      "Merchants who pay the toll live. Caravans with guards — burn the wagons, keep the guards' boots. — R."),
    "rourke_ledger": ("Rourke's Ledger",
                      "Bought: one star-chart rubbing from the Gilded Hand, 800 gold. Offered to the Veil, 3,000. Offered to "
                      "the Sultan of Sunspire, 5,000. Nobody is buying fast enough. Note to self: raise the price."),
    "hollowmere_marks": ("The Sewn Eye",
                         "Every door in Hollowmere is marked with an eye stitched shut in black thread. In the Veil's tongue "
                         "it means: 'Here we see nothing. Here we are seen by nothing.' It is a blessing. It is a threat."),
    "hollowmere_diary": ("A Child's Diary, Hollowmere",
                         "The singing lady came again. Mam says not to listen. Da listens. Everyone's da listens now. "
                         "Tonight we're all going for a walk in the woods. Mam's crying but she's coming too."),
    "hollowmere_well": ("Notice by the Well",
                        "VILLAGE MEETING TONIGHT. ATTENDANCE REQUIRED. THE MASK WILL SPEAK."),
    "empty_village": ("A Letter Never Sent",
                      "Dear Hennick — the harvest failed again and the dead won't stay in the churchyard. We're going "
                      "south to my sister's. Don't come looking. Burn this letter. Love always, Aud."),
    "village_letter": ("Tax Notice",
                       "Owed to the crown: 40 silver, 2 sheep, 1 barrel of beer. Someone has written underneath: "
                       "'COME AND TAKE THEM. WE'RE NOT HERE.'"),
    "village_well": ("Scratched into the Well",
                     "'The water went bad first. Then the cows. Then the dreams.' Below, newer scratches: a tally of "
                     "days, stopping at thirty-one."),
    "mirelle_notes": ("Mirelle's Treatise on Curses",
                      "A curse is a promise that refuses to be broken. To lift one, you need not be stronger than the "
                      "one who made it — only more stubborn. Annotation in the margin: 'Dragons are VERY stubborn.'"),
    "quellan_notes": ("Quellan's Lunar Equations",
                      "Moon = big. Portal = small. Therefore: make portal bigger. (Mirelle says this is 'not an equation'. "
                      "Mirelle is jealous.) Also: buy more Frost Crystals. Also: feed the cat."),
    "obelisks": ("The Rune-Stones",
                 "Before kingdoms, before gods with names, someone set these stones across the world. Touch one and "
                 "it remembers you. Touch two, and they remember each other."),
    "starfall": ("The Starfall Inscription",
                 "When the Crown sleeps beneath the sea, let the four winds point the way. Raise the fragments to the "
                 "Wanderer's Star and the road will open. Bring light from the salt-glass, or walk in darkness forever."),
    "fisher_tales": ("Carved Oar",
                     "Notches for every great catch: 'Tuna, big as a dog. Eel, longer than the boat. Something with "
                     "too many eyes — threw it back, it threw me back.'"),
    "graveyards": ("Cracked Tablet",
                   "Here rest those who held the line at the Fording, the year the dead first walked from the Blackroot "
                   "Crypt. Their watch is ended. Let no one wake them."),
    "ashen_barrow": ("The Ashen Barrow",
                     "Veil cultists were buried here in unmarked graves after the last purge. Every grave has a small "
                     "porcelain shard set in the soil above the heart — the mark of those who wore the Mask."),
    "great_hunt": ("The Trophy Board",
                   "BIGGEST WOLF: Brann (again). MOST STUBBORN SNOW BEAST: Old Greta (took 3 days). MOST EMBARRASSING: "
                   "Vilmar, chased up a tree by a rabbit. There is a space at the top marked 'YOUR NAME HERE?'"),
    "wyrm_graveyard": ("Bones of the Mate",
                       "Vaeltharion's mate, Seryx the Pale, died here three hundred years ago. The dragon came every "
                       "century to lie beside her bones. That is why the Choir chose this place: grief makes a heart "
                       "easy to brand."),
    "brand_of_ash": ("The Ritual Circle",
                     "Black salt in a perfect ring, a branding iron cooling at its centre, and the stamp of a desert "
                     "smith: a sun with seven rays. The Brand of Ash was forged here, from dragon-bone fire."),
    "sand_wyrm_bones": ("The Sand Wyrm",
                        "Not a true dragon — a wyrm of the deep sands that grew too big to burrow and starved under the "
                        "open sky. Its scales are still prized by smiths. Its ghost is said to swim through the dunes."),
    "morrow_log": ("Log of the Morrow",
                   "We carry the Saltglass Lens south to the lighthouse, as the King commanded, so that Valdremoor's "
                   "vault may only open to one who walks the old road. Ice closing in. Crew singing to keep warm. "
                   "If found, tell the King we did not fail him."),
    "wreck_log": ("Frozen Logbook",
                  "Day 9 in the ice. Food for six more. The cook swears he sees lights under the floe. The captain "
                  "says we wait for the thaw. There has not been a thaw in this bay for forty years."),
    "saltglass": ("The Saltglass Lamp",
                  "The lens in this lamp came from the sea-kings of Valdremoor. Light through saltglass shows what "
                  "was hidden. Keepers have passed it down for five hundred years, waiting for someone to ask."),
    "lighthouses": ("Keeper's Journal",
                    "Lit the lamp. Counted the steps. Fed the gulls. Saw a ship, waved, it did not wave back. "
                    "A good day."),
    "hermit_osric": ("Osric's Confession",
                     "I wore the Mask for a single night, thirty years ago. In that night I did things I still dream "
                     "about. When I took it off, I walked until the roads ran out. They ran out here."),
    "hermit_zahra": ("Zahra's Sand-Readings",
                     "The dunes sing at night: the old hymn of the Ashen Choir. They believed the world must be "
                     "burned clean to be sung anew. The sand remembers every verse. The sand would rather not."),
    "hermit_pell": ("Pell's Bottle Collection",
                    "Bottle 1: 'Help.' Bottle 2: 'Never mind.' Bottle 3: a map of the South Isles with an X in the "
                    "middle of the sea, labelled 'the King's door'."),
    "emberdeep": ("Scratched Warning",
                  "TURN BACK. THE BROOD NESTS BELOW. THE MOTHER IS AWAKE. — and beneath, in another hand: "
                  "'we did not turn back.'"),
    "hidden_caves": ("Scratched Warning",
                     "Something has been sharpening its claws on these walls. Recently."),
}


# ═════════════════════════════════════════════════════════════════
# Journal integration
# ═════════════════════════════════════════════════════════════════

def journal_lines(player):
    """Lines for the journal's Discoveries tab."""
    f = getattr(player, "flags", {}) or {}
    found = [k[5:] for k, v in f.items() if k.startswith("disc:") and v]
    total = max(_TOTAL[0], len(found))
    out = [f"{C_GOLD}{B_}Discoveries {len(found)}/{total}{R_}  "
           f"{C_DIM}(watchtowers, shrines, camps, wrecks, caves ... — press [E] on them){R_}"]
    filled = int(30 * len(found) / total) if total else 0
    out.append(f"[{C_GOLD}{'█' * filled}{C_DIM}{'░' * (30 - filled)}{R_}]")
    out.append("")
    if found:
        out.append(f"{C_WHITE}Recently found:{R_}")
        for n in found[-8:][::-1]:
            out.append(f"  {C_GOLD}★{R_} {C_WHITE}{n}{R_}")
        out.append("")
    blessed = [g for g in GODS if f.get(f"blessed:{g}")]
    out.append(f"{C_WHITE}Blessings:{R_} " + (", ".join(blessed) if blessed else f"{C_DIM}none yet — pray at a shrine{R_}")
               + f"  {C_DIM}({len(blessed)}/{len(GODS)}){R_}")
    att = [k[8:] for k, v in f.items() if k.startswith("attuned:") and v]
    if att:
        out.append(f"{C_WHITE}Attuned obelisks:{R_} {C_PURP}{', '.join(att)}{R_}")
    lore = [k[5:] for k, v in f.items() if k.startswith("lore:") and v and k[5:] in LORE]
    out.append("")
    out.append(f"{C_WHITE}Lore collected:{R_} {C_CYAN}{len(lore)}/{len(LORE)}{R_}  {C_DIM}press [L] to read{R_}")
    for k in lore[-6:][::-1]:
        out.append(f"  {C_CYAN}¶{R_} {LORE[k][0]}")
    return out


def lore_reader(player):
    """Simple list + reader for collected lore."""
    from game_stories import _wrap
    f = getattr(player, "flags", {}) or {}
    keys = [k[5:] for k, v in f.items() if k.startswith("lore:") and v and k[5:] in LORE]
    while True:
        clr()
        print(C(f"\n{C_CYAN}{B_}════  LORE  ════{R_}\n"))
        if not keys:
            print(C(f"{C_DIM}No lore yet. Read journals, tablets and inscriptions at the places you explore.{R_}"))
            input(C(f"\n{C_DIM}(Press Enter){R_}"))
            return
        per = max(8, H() - 8)
        for i, k in enumerate(keys[:per], 1):
            print(C(f"{C_GOLD}[{i}]{R_} {C_WHITE}{LORE[k][0]}{R_}"))
        ch = input(C(f"\n{C_DIM}Number to read, Enter to go back{R_} {C_GOLD}>{R_} ")).strip()
        if not ch.isdigit() or not (1 <= int(ch) <= min(len(keys), per)):
            return
        title, text = LORE[keys[int(ch) - 1]]
        clr()
        print(C(f"\n{C_CYAN}{B_}{title}{R_}\n"))
        for line in _wrap(text, 72):
            print(C(f"{C_WHITE}{line}{R_}"))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))


_register()
