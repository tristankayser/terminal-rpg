"""game_castles.py — the Duskthorn Citadel (demon castle, Ironspire) and the
Sunspire Kasbah (desert palace, Ash Sands).

  Duskthorn Citadel — a black-and-crimson fortress ringed by lava.  Demon Lord
  Kharzul is honourable: swear the Ember Pact (flags demon_pact) for a dark
  shop, a demon companion and an ally in the kingdom finale, or defy him
  (flags demon_war) and storm the citadel.  The choice is permanent.

  Sunspire Kasbah — a laid-back sandstone palace with an oasis, bazaar,
  hammocks and musicians.  Sultan Rahzim offers tea and a quest; but rude
  guests and vault thieves are hunted by the guard (flags sunspire_hostile)
  until a fine is paid, assassins prowl the colonnades at night, and a
  scorpion pit and a djinn's vault lie beneath the palace.

Placement is driven from game_capital.place_capital() → place_castles().
All persistent state lives in player.flags ("demon_*", "sunspire_*").
"""

from __future__ import annotations

import random

from game_term import C, clr
from game_scene import Entity, Tile, fg, parse_map, R_, B_, C_GOLD, C_DIM, C_WHITE, C_RED, C_GREEN, C_CYAN

import game_capital as cap
from game_capital import (CastleScene, pflags, set_flag, check_flags, show_completions, make_boss,
                          make_elite, give_item, try_recruit, has_companion, kingdom_step, kingdom_past,
                          kingdom_at_least, story_lines, show_banner, pick, mini_shop, _log)

DEMON_NAME = "Duskthorn Citadel"
DESERT_NAME = "Sunspire Kasbah"
DEMON_GLYPH = "Z"
DESERT_GLYPH = "Y"

C_EMBER = fg(255, 110, 40)
C_BLOOD = fg(200, 40, 50)
C_BONE = fg(225, 215, 190)
C_SAND = fg(235, 200, 130)
C_OASIS = fg(90, 190, 230)
C_ROSE = fg(240, 120, 150)


def _T(rgb, glyph, walk=True, name="", dark=False):
    return Tile(fg(*rgb), glyph, walk, name, dark)


def _mirror(lines):
    """Hand-drawn left halves → symmetric art."""
    swap = str.maketrans("/\\()[]<>{}", "\\/)(][><}{")
    return [ln + ln[::-1].translate(swap) for ln in lines]


# ═════════════════════════════════════════════════════════════════
#  REGISTRATION + PLACEMENT
# ═════════════════════════════════════════════════════════════════

def _arrive_demon(loc):
    return (f"{fg(230, 60, 40)}{B_}Ψ {loc['name']}{R_} {fg(170, 70, 70)}— black spires over a moat of fire.{R_} "
            f"{C_DIM}[E] to approach.{R_}")


def _arrive_desert(loc):
    return (f"{fg(240, 200, 110)}{B_}☼ {loc['name']}{R_} {fg(200, 170, 110)}— music drifts over sandstone walls.{R_} "
            f"{C_DIM}[E] to enter.{R_}")


def _enter_demon(world, player, loc, autosave=None):
    enter_duskthorn(world, player, loc, autosave)


def _enter_desert(world, player, loc, autosave=None):
    enter_sunspire(world, player, loc, autosave)


try:
    from game_world import register_place_type as _reg
    _reg("demon_castle", DEMON_GLYPH, fg(220, 40, 40) + B_, "Demon Citadel",
         enter=_enter_demon, arrive=_arrive_demon, symbol="Ψ")
    _reg("desert_castle", DESERT_GLYPH, fg(245, 205, 110) + B_, "Desert Palace",
         enter=_enter_desert, arrive=_arrive_desert, symbol="☼")
except Exception:
    pass


def place_castles(world, rng):
    """Duskthorn deep in Ironspire's peaks, Sunspire inland on the Ash Sands."""
    from game_world import MOUNTAIN, SNOW, SAND, HILL, PLAINS
    if not any(l.get("type") == "demon_castle" for l in world.locations):
        nest = lambda x, y: cap.surround_score(world, x, y, (MOUNTAIN, SNOW), 2)
        site = (cap.find_site(world, rng, "B", (MOUNTAIN, SNOW), gap=5, spread=12, score_fn=nest)
                or cap.find_site(world, rng, "B", (MOUNTAIN, SNOW, HILL), gap=3, spread=12)
                or cap.find_site(world, rng, "B", (MOUNTAIN, SNOW, HILL, PLAINS, "T"), gap=2, spread=12))
        if site:
            cap.add_location(world, "demon_castle", DEMON_GLYPH, DEMON_NAME, site[0], site[1], "B")
    if not any(l.get("type") == "desert_castle" for l in world.locations):
        dunes = lambda x, y: cap.surround_score(world, x, y, (SAND,), 3)
        site = (cap.find_site(world, rng, "D", (SAND,), gap=5, spread=12, inland=3, score_fn=dunes)
                or cap.find_site(world, rng, "D", (SAND,), gap=3, spread=12)
                or cap.find_site(world, rng, "D", (SAND, PLAINS, HILL), gap=2, spread=12))
        if site:
            cap.add_location(world, "desert_castle", DESERT_GLYPH, DESERT_NAME, site[0], site[1], "D")


def _is_night(world):
    try:
        return (int(getattr(world, "turn_count", 0)) // 80) % 3 == 2
    except Exception:
        return False


def _open(scene, key):
    """Remove the triggers on every `key` tile: the gate is now open both ways."""
    for pos in scene.find(key):
        scene.triggers.pop(pos, None)


def _finish(world, player, res, msg):
    clr()
    if res == "defeat" or not player.is_alive():
        if world is not None:
            world._handle_defeat(player)
        return "defeat"
    if world is not None:
        world.last_msg = msg
    return "left"


# ═════════════════════════════════════════════════════════════════
#  DUSKTHORN CITADEL
# ═════════════════════════════════════════════════════════════════

DUSK_MAP = r"""
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
,,,,~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~,,,,
,,,,~~%%%%%~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~%%%%%~~,,,,
,,,,~~%%%%%#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^%%%%%~~,,,,
,,,,~~%%####################################################################################%%~~,,,,
,,,,~~%%#___________________________________dFdddQQdddFd___________________________________#%%~~,,,,
,,,,~~%%#___~~________________~_____________dddddddddddd_____________~________________~~___#%%~~,,,,
,,,,~~~##___~~___o_______o____~_____p_____p_____rrrr_____p_____p_____~____k___k___k___~~___##~~~,,,,
,,,,~~~^#___~~________________~_________________rrrr_________________~________________~~___#^~~~,,,,
,,,,~~~##___~~___o_______o____~_________________rrrr_________________~________________~~___##~~~,,,,
,,,,~~~##___~~________________~_____p_____p_____rrrr_____p_____p_____~____k___k___k___~~___##~~~,,,,
,,,,~~~^#___~~___o_______o____~_________________rrrr_________________~________________~~___#^~~~,,,,
,,,,~~~##___~~________________~_________________rrrr_________________~________________~~___##~~~,,,,
,,,,~~~##___~~___o_______o____~_____p_____p_____rrrr_____p_____p_____~____k___k___k___~~___##~~~,,,,
,,,,~~~^#___~~________________~_________________rrrr_________________~________________~~___#^~~~,,,,
,,,,~~~##___~~________________~_________________rrrr_________________~________________~~___##~~~,,,,
,,,,~~~##_______________________________________rrrr_______________________________________##~~~,,,,
,,,,~~~^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#gg^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^##^~~~,,,,
,,,,~~~#........................................eeee........................................#~~~,,,,
,,,,~~~#...####################.................eeee.................#########+##########...#~~~,,,,
,,T,~~~^...#..................#...............F.eeee.F...............#.^..^..^..^..^..^.#...^~~~,,,,
,,,,~~~#...#..kFF.............#.................eeee.................#ssssssssssssssssss#...#~~~,,,,
,,,,~~~#...#..................#.................eeee.................#ssssssssssssssssss#...#~~~,,,,
,,,,~~~^...#..............~~..+.................eeee.................#ssssssssssssssssss#...^~~~,,,,
,,,,~~~#...#..................#...............F.eeee.F...............#ssssssssssssssssss#...#~~~,,,,
,,,,~~~#...#..................#.................eeee.................#ssssssssssssssssss#...#~~~,T,,
,,,,~~~^...####################.................eeee.................#ssssssssssssssssss#...^~~~,,,,
,,,,~~~#...###I###I###I###I####.................eeee.................#.^..^..^..^..^..^.#...#~~~,,,,
,,,,~~~#...#xxxxxxxxxxxxxxxxxx#...............F.eeee.F...............####################...#~~~,,,,
,,,,~~%%...#xxxxxxxxxxxxxxxxxx+.......o.........eeee.........o..............................%%~~,,,,
,,,,~~%%...#xxxxxxxxxxxxxxxxxx#.................eeee............c..c........................%%~~,,,,
,,,,~~%%...####################.................eeee........................................%%~~,,,,
,,,,~~%%%%%#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^%%DD%%#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^#^%%%%%~~,,,,
,,,,~~%%%%%~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eeee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~%%%%%~~,,,,
,,,,~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eeee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~,,,,
,,,,~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eeee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,eeee,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,eeee,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,eeee,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
,,,,,,,,,,,,,,,,,,,,,,T,,,,,,,,,,,,,,,,,,,,,,,,,eeee,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,T,,,,,,,,,,,
,,,T,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,T,,,,,,,,,,,,,,,,,,,,,,
,,,,,,,,,,,,T,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,T,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
"""

DUSK_PAL = {
    ",": _T((95, 85, 85), "·", True, "ash"),
    ".": _T((88, 66, 76), "·", True, "obsidian flags"),
    "_": _T((105, 50, 60), "·", True, "scorched floor"),
    "#": _T((52, 38, 46), "█", False, "black stone"),
    "%": _T((150, 28, 38), "█", False, "crimson tower"),
    "^": _T((205, 45, 45), "▲", False, "iron spikes"),
    "~": _T((255, 95, 25), "≈", False, "lava"),
    "e": _T(  (225, 215, 190), "═", True, "bone bridge"),
    "T": _T((115, 90, 90), "♠", False, "dead tree"),
    "F": _T((255, 80, 40), "♨", False, "brazier"),
    "k": _T((150, 140, 150), "Π", False, "weapon rack"),
    "p": _T((225, 215, 190), "‡", False, "bone pillar"),
    "r": _T((150, 20, 35), "░", True, "blood carpet"),
    "d": _T((120, 32, 42), "▒", True, "dais"),
    "Q": _T((235, 55, 55), "Ψ", False, "obsidian throne"),
    "o": _T((225, 215, 190), "ø", False, "skull pile"),
    "c": _T((150, 100, 60), "▫", False, "imp's wares"),
    "s": _T((185, 120, 80), "·", True, "arena sand"),
    "I": _T((140, 120, 120), "║", False, "iron bars"),
    "x": _T((65, 45, 55), "·", True, "cell floor", dark=True),
    "g": _T((120, 45, 45), "▒", True, "portcullis"),
    "D": _T((190, 60, 40), "▒", True, "citadel gate"),
    "+": _T((180, 70, 50), "+", True, "door"),
}

DUSK_ART = _mirror([
    r"                 ^             ",
    r"         ^      /#\          /\ ",
    r"        /#\     |v|    ^    /##",
    r"        |^|   __|#|__ /#\  /###",
    r"     ___|#|__/  |#|  \|^| /####",
    r"     \  |#| |   |#|   |#|_|  /\ ",
    r"      \ |#| | o |#| o |#||  /  ",
    r"   ~~~~\|#|_|___|#|___|#||_/___",
    r"   ~~~~~~~~~~~~~~~~~~~~~~~~~ ||",
])


def _dusk_colour(ch, x, y):
    if ch == "~":
        return fg(255, 100 + (x * 7 + y * 13) % 60, 30)
    if ch == "^":
        return fg(230, 60, 50)
    if ch in "#":
        return fg(70, 50, 60)
    if ch in "ov":
        return fg(255, 160, 60)
    if ch in "|_":
        return fg(160, 40, 50)
    return fg(120, 90, 95)


DEMON_IMP_LINES = ["Kheh! A soft one. Lord Kharzul will want to see you. Or eat you. Probably see.",
                   "Don't touch the lava. Don't touch the bones. Don't touch ME.",
                   "The Lord keeps his word. That's the worst thing about him."]
DEMON_FRIEND_LINES = ["The pact-bearer! Welcome, welcome. Mind the drip — that's molten.",
                      "Skritch has new wares. Cursed! Very fashionable.",
                      "We bow to the mark on your hand. Ha! See? Bowing."]


class Duskthorn:
    def __init__(self, world, player, loc=None, autosave=None):
        self.world = world
        self.player = player
        self.loc = loc
        self.autosave = autosave

    def mode(self):
        f = pflags(self.player)
        if f.get("demon_pact"):
            return "pact"
        if f.get("demon_war"):
            return "war"
        return "neutral"

    def run(self):
        p = self.player
        f = pflags(p)
        note = {
            "pact": "The Hellhound Warden lowers its three heads as you pass. You are expected.",
            "war": "Horns blare from the black towers. Duskthorn remembers your defiance.",
        }.get(self.mode(), "Heat hammers your face from the moat. Somewhere above, something enormous is laughing.")
        if f.get("demon_kharzul_dead"):
            note = "The citadel is half-empty now. The throne of Duskthorn stands cold."
        show_banner(DUSK_ART, [f"{C_BLOOD}{B_}D U S K T H O R N   C I T A D E L{R_}",
                               f"{C_EMBER}~ seat of Demon Lord Kharzul ~{R_}"],
                    _dusk_colour, subtitle="Ironspire · demon fortress", note=note)
        # a decision made earlier still resolves the kingdom step
        if (f.get("demon_pact") or f.get("demon_kharzul_dead")) and kingdom_step(p) == "cp_demon":
            set_flag(p, "crowns_demon_resolved", True, world=self.world)
        start = (49, 41)
        while True:
            sc = self.build(start)
            res = sc.run(p)
            if res == "rebuild":
                start = (sc.px, sc.py)
                continue
            if res == "storm":
                start = (49, 38)
                continue
            return res

    # ── scene ────────────────────────────────────────────────────
    def build(self, start):
        p = self.player
        f = pflags(p)
        mode = self.mode()
        sc = CastleScene("DUSKTHORN CITADEL", parse_map(DUSK_MAP), palette=DUSK_PAL, start=start,
                         subtitle={"pact": "you bear the Ember Pact", "war": "at war with the demon host"}.get(
                             mode, "demon fortress of Ironspire"),
                         colour=C_BLOOD, world=self.world, night=(mode == "war"))
        if not f.get("demon_warden_beaten"):
            for x, y in sc.find("D"):
                sc.add_door(x, y, "Citadel gate", self._gate, step_back=False, tile="D")
        if mode == "war" and not f.get("demon_gate_broken") and not f.get("demon_kharzul_dead"):
            for x, y in sc.find("g"):
                sc.add_door(x, y, "Portcullis of the throne hall", self._inner_gate, step_back=False, tile="g")
        sc.add_door(30, 23, "Demon Forge", self._forge, step_back=False, tile="+")
        sc.add_door(78, 19, "Arena of Cinders", self._arena_door, step_back=False, tile="+")
        sc.add_door(30, 29, "Cells", lambda s, pl: None, step_back=False, tile="+")
        for (x, y, t, c) in ((13, 20, "DEMON FORGE", C_EMBER), (72, 21, "ARENA OF CINDERS", C_BLOOD),
                             (13, 28, "CELLS", C_DIM), (44, 9, "THRONE OF DUSKTHORN", C_EMBER)):
            sc.add_label(x, y, t, c)
        sc.hud_extra = lambda s, pl: {"pact": f"{C_EMBER}☠ Ember Pact{R_}",
                                      "war": f"{C_RED}⚔ at war{R_}"}.get(self.mode(), "")
        self._populate(sc, mode)
        return sc

    def _populate(self, sc, mode):
        p = self.player
        f = pflags(p)
        hostile = mode == "war"
        # Hellhound Warden at the gate
        if not f.get("demon_warden_beaten"):
            sc.add_entity(Entity(51, 33, "W", fg(255, 90, 40), "Hellhound Warden", kind="boss", npc_id="demon_warden",
                                 title="gate guardian", interact=self._warden_talk))
        # Kharzul
        if not f.get("demon_kharzul_dead"):
            if hostile:
                sc.add_entity(Entity(50, 6, "Ψ", fg(255, 60, 40), "Demon Lord Kharzul", kind="boss", hostile=True,
                                     npc_id="demon_kharzul", on_contact=self._kharzul_fight))
            else:
                sc.add_entity(Entity(50, 6, "Ψ", fg(255, 60, 40), "Demon Lord Kharzul", npc_id="demon_kharzul",
                                     title="Lord of Duskthorn", interact=self._kharzul_talk))
        imp_col = fg(240, 120, 60)
        knight_col = fg(170, 40, 60)
        if hostile:
            if not f.get("demon_kharzul_dead"):
                if not f.get("demon_gate_broken"):
                    for x in (47, 52):
                        sc.add_entity(Entity(x, 18, "K", knight_col, "Demon Knight", kind="demon", hostile=True,
                                             title="gatekeeper", on_contact=self._demon_fight,
                                             data={"gatekeeper": True}))
                for (x, y) in ((40, 12), (59, 12)):
                    sc.add_entity(Entity(x, y, "K", knight_col, "Demon Knight", kind="demon", hostile=True,
                                         ai="chase", on_contact=self._demon_fight))
                for (x, y) in ((40, 30), (36, 22), (62, 24), (75, 30), (90, 24)):
                    sc.add_entity(Entity(x, y, "i", imp_col, "Imp", kind="demon", hostile=True, ai="chase",
                                         on_contact=self._demon_fight))
            else:
                for (x, y) in ((36, 22), (75, 30)):
                    sc.add_entity(Entity(x, y, "i", imp_col, "Imp", kind="demon", hostile=True, ai="chase",
                                         on_contact=self._demon_fight))
        else:
            lines = DEMON_FRIEND_LINES if mode == "pact" else DEMON_IMP_LINES
            for (x, y) in ((36, 22), (62, 24), (90, 24), (55, 30)):
                sc.add_entity(Entity(x, y, "i", imp_col, "Imp", kind="demon", ai="wander", radius=4, lines=lines))
            for x in (47, 52):
                sc.add_entity(Entity(x, 18, "K", knight_col, "Demon Knight", kind="demon", title="gatekeeper",
                                     lines=(["The pact-bearer may pass."] if mode == "pact" else
                                            ["The Lord will receive you. Do not make him wait.",
                                             "Kneel when you reach the dais. Or don't. He likes the brave ones."])))
            sc.add_entity(Entity(65, 31, "i", fg(255, 170, 70), "Skritch", npc_id="demon_skritch",
                                 title="imp merchant", interact=self._skritch))
            sc.add_entity(Entity(20, 22, "B", fg(200, 90, 60), "Grommash", npc_id="demon_grommash",
                                 title="demon smith", interact=self._grommash))
            sc.add_entity(Entity(78, 18, "V", fg(230, 80, 120), "Vexa", npc_id="demon_vexa",
                                 title="arena mistress", interact=self._vexa))
            if mode == "pact" and not f.get("demon_zhaal_joined") and not has_companion(p, "zhaal"):
                sc.add_entity(Entity(53, 12, "Z", knight_col, "Zhaal", npc_id="zhaal",
                                  title="Kharzul's second blade", interact=self._zhaal))
        # captives (all modes) + jailer
        sc.add_entity(Entity(15, 29, "@", fg(220, 220, 180), "Brother Halvard", npc_id="demon_halvard",
                             title="captive paladin", interact=self._halvard))
        if not f.get("demon_jailer_dead") and not f.get("demon_captives_freed"):
            sc.add_entity(Entity(26, 29, "j", fg(255, 140, 60), "Imp Jailer Nix", kind="demon",
                                 hostile=hostile, on_contact=self._jailer_fight, interact=self._jailer_talk))

    # ── gate & warden ────────────────────────────────────────────
    def _gate(self, scene, player):
        w = next((e for e in scene.entities if e.name == "Hellhound Warden" and e.alive), None)
        scene.py = 33
        return self._warden_talk(scene, player, w or Entity(0, 0, "W", C_EMBER, "Hellhound Warden"))

    def _warden_talk(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(ent, ["Three heads lift from the bone bridge. Smoke curls from six nostrils.",
                              "'NONE PASS THE GATE OF DUSKTHORN UNBLOODIED.'"])
        ch = scene.choice_box("The Hellhound Warden bars the way.", [("1", "Fight the Warden"),
                                                                     ("2", "Back away")], ent)
        if ch != "1":
            scene.py = max(scene.py, 34)
            return f"{C_DIM}You back away down the bone bridge.{R_}"
        boss = make_boss("Hellhound Warden", player, power=1.15)
        res = scene.fight_enemy(player, boss, allow_escape=True)
        if res == "victory":
            f["demon_warden_beaten"] = True
            ent.alive = False
            _open(scene, "D")
            return f"{C_EMBER}The Warden whimpers and slinks aside. The gate of Duskthorn grinds open.{R_}"
        if res == "escaped":
            scene.py = 36
        return None

    def _inner_gate(self, scene, player):
        keepers = [e for e in scene.entities if e.alive and e.data.get("gatekeeper")]
        if keepers:
            scene.py = 18
            return f"{C_RED}The portcullis is chained shut. The gatekeeper knights hold the chain-key.{R_}"
        _open(scene, "g")
        return f"{C_EMBER}The portcullis grinds upward. Heat rolls out of the throne hall.{R_}"

    # ── Kharzul ──────────────────────────────────────────────────
    def _kharzul_talk(self, scene, player, ent):
        f = pflags(player)
        k = kingdom_step(player)
        if f.get("demon_pact"):
            lines = ["Pact-bearer. My forge and my legion are yours to call on, as sworn.",
                     "When the time comes, say my name over the false crown. I will hear."]
            if kingdom_past(player, "cp_regent") or f.get("valdmere_regent_dead"):
                lines = ["The Hollow Crown is ash, and my oath is fulfilled. Duskthorn will remember that you kept faith, mortal."]
            scene.say_lines(ent, lines)
            if not f.get("demon_pact_gift"):
                f["demon_pact_gift"] = True
                give_item(player, "Ember Pact Ring", scene=scene)
            return None
        intro = ["I am Kharzul, ninth of the Duskthorn line. My word is iron and fire, and I have never broken it.",
                 "Mortals come here to kill me, or to beg. You have not yet decided which. Interesting."]
        if k == "cp_demon":
            intro += ["You carry my forefathers' work on your mind — the Hollow Crown. Yes, Duskthorn forged it. "
                      "And yes: its maker's line can unmake it... or its anchor dies with me."]
        intro += ["Swear the Ember Pact, and my legion will not trouble your roads, my forge will arm you, and "
                  "when you face whatever wears that crown, I will stand beside you. The white city will hate you for it.",
                  "Or draw steel, and we will see whether you are worth a song."]
        scene.say_lines(ent, intro)
        ch = scene.choice_box("Kharzul waits. (This choice is permanent.)",
                              [("1", "Swear the Ember Pact"), ("2", "Defy him — storm the citadel"),
                               ("3", "Leave — decide another day")], ent)
        if ch == "1":
            if scene.choice_box("Swear the pact? Valdmere's guards will distrust you forever.",
                                [("y", "I swear it"), ("n", "Not yet")], ent) != "y":
                return None
            f["demon_pact"] = True
            f.pop("demon_war", None)
            scene.say_lines(ent, ["Then it is done. Hold out your hand.",
                                  "Fire writes the mark of Duskthorn across your palm. It does not hurt. That is what worries you."])
            give_item(player, "Ember Pact Ring", scene=scene)
            f["demon_pact_gift"] = True
            set_flag(player, "crowns_demon_resolved", True, scene)
            scene.leave("rebuild")
            return f"{C_EMBER}☠ You have sworn the Ember Pact.{R_}"
        if ch == "2":
            if scene.choice_box("Defy the Demon Lord? Duskthorn will be at war with you forever.",
                                [("y", "Draw steel"), ("n", "Not yet")], ent) != "y":
                return None
            f["demon_war"] = True
            scene.say_lines(ent, ["Ha! Then I grant you a courtesy: leave my hall alive.",
                                  "Come back through my legion, little champion. I will be waiting on my throne."])
            scene.leave("storm")
            return f"{C_RED}⚔ Duskthorn is at war with you. Fight your way to the throne!{R_}"
        return None

    def _kharzul_fight(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(Entity(0, 0, "Ψ", fg(255, 60, 40), "Demon Lord Kharzul"),
                        ["Kharzul rises from the obsidian throne, and the lava channels rise with him.",
                         "'You came back. Good. I would have been disappointed.'"])
        boss = make_boss("Demon Lord Kharzul", player, power=1.7)
        res = scene.fight_enemy(player, boss, allow_escape=False)
        if res != "victory":
            return None
        ent.alive = False
        f["demon_kharzul_dead"] = True
        scene.say_lines(Entity(0, 0, "Ψ", fg(255, 60, 40), "Demon Lord Kharzul"),
                        ["'Well... fought. The crown's anchor... dies with me. Use it well, mortal.'",
                         "The Demon Lord crumbles into embers. The citadel shudders; somewhere, imps begin to flee."])
        gold = 800 + 60 * player.level
        player.gold += gold
        give_item(player, "Crown of Cinders", scene=scene)
        give_item(player, "Duskthorn Greatsword", scene=scene)
        set_flag(player, "crowns_demon_resolved", True, scene)
        for e in scene.entities:
            if e.kind == "demon" and e.name == "Demon Knight":
                e.alive = False
        return f"{C_GOLD}★ Demon Lord Kharzul is slain! +{gold} gold{R_}"

    def _demon_fight(self, scene, player, ent):
        enemy = make_elite(ent.name, player, zone="dungeon_deep", danger=4,
                           mult=1.35 if ent.name == "Demon Knight" else 0.9)
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            ent.alive = False
            if ent.data.get("gatekeeper"):
                if not any(e.alive and e.data.get("gatekeeper") for e in scene.entities):
                    pflags(player)["demon_gate_broken"] = True
                    _open(scene, "g")
                    return f"{C_GOLD}You tear the chain-key from the last gatekeeper. The portcullis is yours.{R_}"
            return f"{C_GREEN}The {ent.name} bursts into cinders.{R_}"
        ent.cooldown = 3
        return None

    # ── pact services ────────────────────────────────────────────
    def _skritch(self, scene, player, ent):
        f = pflags(player)
        if not f.get("demon_pact"):
            scene.talk_box(ent, "Wares only for the pact-sworn, soft one. Kheh. Come back with a mark on your hand.", player)
            return None
        scene.talk_box(ent, "Cursed blades! Haunted mail! Rings that bite! All guaranteed to work, mostly on your enemies.", player)
        scene.modal(mini_shop, player, "SKRITCH'S CURSED WARES", [
            ("Kharzul's Oathbrand", 2600), ("Hellforged Mail", 1500), ("Fire Bomb", 30),
            ("Strength Draught", 60), ("Mega Potion", 140), ("Elixir", 120)], C_EMBER)
        return None

    def _grommash(self, scene, player, ent):
        f = pflags(player)
        if f.get("demon_trial_won") and not f.get("demon_trial_done"):
            scene.say_lines(ent, ["Vexa says you bled well in the arena. Hrm. Good.",
                                  "Here. Duskthorn steel, quenched in lava. Don't thank me. Thanks are for mortals."])
            give_item(player, "Duskthorn Greatsword", scene=scene)
            f["demon_trial_done"] = True
            try:
                player.gain_exp(300 + 30 * player.level)
            except Exception:
                pass
            return f"{C_GOLD}Side quest complete: Trial of Cinders{R_}"
        if f.get("demon_pact"):
            scene.talk_box(ent, "Your weapon is dull. Win in Vexa's arena and I'll forge you something worth carrying.", player)
        else:
            scene.talk_box(ent, "Hrm. A mortal in my forge. Touch nothing. The anvil bites.", player)
        return None

    def _forge(self, scene, player):
        return f"{C_EMBER}Heat and hammering. Grommash the smith works inside, beside a pool of lava.{R_}"

    def _arena_door(self, scene, player):
        return f"{C_BLOOD}The sand of the arena is black with old blood. Speak to Vexa to fight.{R_}"

    def _vexa(self, scene, player, ent):
        f = pflags(player)
        if f.get("demon_trial_won"):
            scene.talk_box(ent, "The sand still remembers you, champion. Grommash has a gift waiting." if not f.get("demon_trial_done")
                           else "Come back when you're bored of living safely.", player)
            return None
        scene.say_lines(ent, ["Vexa, mistress of the Arena of Cinders. Demons respect exactly one thing.",
                              "Beat my champion and Duskthorn will respect you. Lose, and we'll respect your corpse."])
        ch = scene.choice_box("Enter the Trial of Cinders?", [("1", "Step onto the sand"), ("2", "Not today")], ent)
        if ch != "1":
            return None
        f["demon_trial_started"] = True
        enemy = make_elite("Demon Knight", player, zone="dungeon_deep", danger=5, mult=1.8)
        enemy.name = "Cinder Champion"
        res = scene.fight_enemy(player, enemy, allow_escape=True)
        if res == "victory":
            f["demon_trial_won"] = True
            player.gold += 250
            return f"{C_GOLD}The arena roars! +250 gold. Grommash the smith wants a word.{R_}"
        return None

    def _zhaal(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(ent, ["Zhaal, second blade of Duskthorn. The pact binds my lord to your cause.",
                              "It binds me too, if you will have me. I have been bored for two hundred years."])
        if try_recruit(player, "zhaal", scene):
            f["demon_zhaal_joined"] = True
            ent.alive = False
            return f"{C_GOLD}Zhaal the demon knight joins your party!{R_}"
        return None

    # ── captives side quest ──────────────────────────────────────
    def _halvard(self, scene, player, ent):
        f = pflags(player)
        if f.get("demon_captives_freed"):
            scene.talk_box(ent, "Free air! Even here it tastes sweet. The Temple of the Moon will hear your name, friend.", player)
            return None
        if f.get("demon_jailer_dead") or (f.get("demon_pact") and f.get("demon_halvard_asked")):
            scene.say_lines(ent, ["The cell door swings open. Brother Halvard stumbles out, blinking at the lava-light.",
                                  "Take these — the demons never found them in my boot. And my blessing, for what it's worth."])
            f["demon_captives_freed"] = True
            player.gold += 300
            try:
                player.gain_exp(250 + 25 * player.level)
            except Exception:
                pass
            give_item(player, "Holy Water", 3, scene=scene)
            give_item(player, "Hi-Potion", 2, scene=scene)
            ent.alive = False
            return f"{C_GOLD}Side quest complete: Unchain the Captives (+300g){R_}"
        scene.say_lines(ent, ["A paladin of Valdmere, chained for a year. 'Friend! The imp jailer holds the keys.'",
                              ("'You bear the pact? Then ask the jailer — demons obey the mark.'" if f.get("demon_pact")
                               else "'Take them from him, by word or by blade. Please.'")])
        f["demon_halvard_asked"] = True
        return None

    def _jailer_talk(self, scene, player, ent):
        f = pflags(player)
        if f.get("demon_pact") and f.get("demon_halvard_asked"):
            scene.talk_box(ent, "The mark! Yes, yes, pact-bearer. Take the paladin. He sings hymns. Horrible.", player)
            f["demon_jailer_dead"] = True       # keys handed over
            ent.alive = False
            return f"{C_EMBER}Nix hands over the cell keys.{R_}"
        scene.talk_box(ent, "Keys? What keys? These are decorative. Go away. Kheh.", player)
        if f.get("demon_halvard_asked") and not f.get("demon_pact"):
            ch = scene.choice_box("Take the keys by force?", [("1", "Attack the jailer"), ("2", "Leave him")], ent)
            if ch == "1":
                return self._jailer_fight(scene, player, ent)
        return None

    def _jailer_fight(self, scene, player, ent):
        enemy = make_elite("Imp", player, zone="dungeon", danger=3, mult=1.2)
        enemy.name = "Imp Jailer Nix"
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            pflags(player)["demon_jailer_dead"] = True
            ent.alive = False
            return f"{C_GOLD}You take the cell keys from Nix's smouldering belt.{R_}"
        return None


def enter_duskthorn(world, player, loc=None, autosave=None):
    try:
        res = Duskthorn(world, player, loc, autosave).run()
    except Exception as e:
        import traceback
        _log(f"duskthorn crashed: {e!r}\n{traceback.format_exc()}")
        res = "left"
    return _finish(world, player, res, f"{C_BLOOD}You leave the black spires of Duskthorn behind.{R_}")


# ═════════════════════════════════════════════════════════════════
#  SUNSPIRE KASBAH
# ═════════════════════════════════════════════════════════════════

KASBAH_MAP = r"""
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:::XXXX::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::XXXX:::
:::XXXXq#q#q#q#q#q#q#q#q#q#q###########q#q#q#q#q#q#q#q#q#q#q#############q#q#q#q#q#q#q#q#q#q#XXXX:::
:::XXXX.....................#.........#.....crrrrQQrrrrc.....#.........#.....................XXXX:::
:::XXXX.....................#.vv......#......rrrrrrrrrr......#..$.$.$..#...#################.XXXX:::
:Y::#..,Y,,,,Y,,,,,Y,,,,Y,,.#.........#.p......rrrrrr......p.#.........#...#RRRRRRRRRRRRRRR#...#::::
::::#..,,,,,,,,,,,,,,,,,,,,.#.........+........rrrrrr........+.........#...#RRRRRRRRRRRRRRR#...#::::
::::#..f,,,f,,,f,,f,,f,,,f,.#.........#........rrrrrr........#.........#...#RRRRRRRRRRRRRRR#...#::::
::::#..,,,Y,,,,,uu,,,,Y,,,,.###########.p......rrrrrr......p.###########...#RRRRRRRRRRRRRRR#...#:Y::
::::#..f,,,f,,,f,,f,,f,,,f,.#..................rrrrrr..................#...#RRRRRRRRRRRRRRR#...#::::
::::#..,,,,,,,,,,,,,,,,,,,,.#..................rrrrrr..................#...#RRRRRRRRRRRRRRR#...#::::
::::#..,Y,,,,Y,,,,,Y,,,,Y,,.#......p....p......rrrrrr......p....p......#...########+########...#::::
::::#..,,,,,,,,,,,,,,,,,,,,.#..................rrrrrr..................#.......................#::::
::::#.......................#####################++#####################.......................#::::
::::#..........................................................................................#::::
::::#..........................................................................................#::::
::::#aaaaaaa.................,,,....................................,,,.................aaaaaaa#::::
::::#aaapaap..#############..,f,..........Y..............Y..........,f,.................paapaaa#::::
::::#aaaaaaa..#RRRRRRRRRRR#..,,,....Y......~~~~~~~~~~~~~~......Y....,,,.hh...s..s..s....aaaaaaa#::::
::::#aaaaaaa..#RRRRRRRRRRR#..,,,........~~~~~~~~~~~~~~~~~~~~........,,,.................aaaaaaa#::::
::Y:#aaapaap..#RRRRRRRRRRR#..,f,......~~~~~~~~~~~~~~~~~~~~~~~~......,f,.................paapaaa#::::
::::#aaaaaaa..#RRRRRRRRRRR#..,,,.....~~~~~~~~~~~~~~~~~~~~~~~~~~.....,,,.hh...s..s..s....aaaaaaa#::::
::::#aaaaaaa..#RRRRRRRRRRR#..,,,..Y..~~~~~~~~~~~~~~~~~~~~~~~~~~..Y..,,,.................aaaaaaa#::::
::::#aaapaap..######+######..,f,.....~~~~~~~~~~~~~~~~~~~~~~~~~~.....,f,.................paapaaa#::::
::::#aaaaaaa.................,,,.....~~~~~~~~~~~~~~~~~~~~~~~~~~.....,,,.hh...s..s..s....aaaaaaa#:Y::
::::#aaaaaaa.................,,,......~~~~~~~~~~~~~~~~~~~~~~~~......,,,.................aaaaaaa#::::
::::#aaapaap.................,f,........~~~~~~~~~~~~~~~~~~~~........,f,.................paapaaa#::::
::::#aaaaaaa..######+######..,,,....Y......~~~~~~~~~~~~~~......Y....,,,......s..s..s....aaaaaaa#::::
::::#aaaaaaa..#___________#..,,,..........Y..............Y..........,,,.................aaaaaaa#::::
::::#aaapaap..#___________#..,f,....................................,f,.......F.........paapaaa#::::
::::#aaaaaaa..#___________#..,,,....................................,,,..._________.....aaaaaaa#::::
::::#aaaaaaa..#___________#..............................................._________.....aaaaaaa#::::
::::#aaapaap..#___________#..............................................._________.....paapaaa#::::
:::XXaaaaaaa..#############..................XXX....XXX.................................aaaaaaaXX:::
:::XXXX......................................XXX....XXX......................................XXXX:::
:::XXXXq#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#XXXDDDDXXXq#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#XXXX:::
:::XXXX::::::::::::::::::::::::::::::::::::::XXX....XXX::::::::::::::::::::::::::::::::::::::XXXX:::
::::::::::::::::::::::::::::::::::::::::::::::::....::::::::::::::::::::::::::::::::::::::::::::Y:::
::Y:::::::::::::::::::::::::::::::::::::::::::::....::::::::::::::::::::::::::::::::::::::::::::::::
::::::::::::::::::::::::::::::::::::::::::::::::....::::::::::::::::::::::::::::::::::::::Y:::::::::
::::::::Y:::::::::::::::::::::::::::::::::::::::....::::::::::::::::::::::::::::::::::::::::::::::::
::::::::::::::::::::::::::::::::::::::::::::::::....::::::::::::::::::::::::::::::::::::::::::::::::
"""

DEPTHS_MAP = r"""
############################################################################
#################################....<<....#################################
#################################..........#################################
#################################F........F##########_____________________##
#################################..........##########__$__$_________$__$__##
###########zzzzzzzzzz############..........##########_____________________##
########zzzzzzozzzzzzzzz#########..........##########_____________________##
######zzzzzzzzzzzzzzozzzzz##########....#############_____________________##
#####zzzzzzzzzzzzzzzzzzzzzz#########....#############_C_________________C_##
####zzzzozzzzzzzzzzzzzzzzzzz########....#############_______mmmmmmmm______##
###zzzzzzzzzzzzzzzzzzzzzzzzzz#######....#############______mmmmmmmmmm_____##
###zzzzzzzzzzzzzzzzzzzzzzzzzzzz....................g_______mmmmmmmmmm_____##
###zzzzzzzzzzzzzzzzzzzzzzzzzzzz....................g_______mmmmmmmmmm_____##
##zzzzzzzzzzzzzzzzzzzzzzzzzzzz#######################______mmmmmmmmmm_____##
###zzzozzzzzzzzzzzzzzzzzzzzzz########################_______mmmmmmmm______##
###zzzzzzzzzzzzzzzzzzzzzzzzzz########################_C_________________C_##
###zzzzzzzzzzzzzzzzzzzzzozzzz########################_____________________##
####zzzzzzzozzzzzzzzzzzzzzzz#########################_____________________##
#####zzzzzzzzzzzzzzzzzzzzzz##########################_____________________##
######zzzzzzzzzzzozzzzzzzz###########################__$__$_________$__$__##
########zzzzzzzzzzzzzzzz#############################_____________________##
###########zzzzzzzzzz#######################################################
############################################################################
############################################################################
"""

KASBAH_PAL = {
    ":": _T((220, 190, 125), ".", True, "dunes"),
    ".": _T((205, 168, 118), "·", True, "sandstone paving"),
    "#": _T((215, 165, 100), "█", False, "sandstone wall"),
    "q": _T((240, 205, 140), "▀", False, "crenellation"),
    "X": _T((232, 182, 115), "█", False, "tower"),
    "Y": _T((70, 180, 90), "¥", False, "palm tree"),
    ",": _T((110, 175, 90), '"', True, "garden"),
    "f": _T((240, 110, 140), "*", False, "desert roses"),
    "~": _T((70, 175, 215), "≈", False, "oasis"),
    "a": _T((110, 85, 60), "░", True, "shaded colonnade", dark=True),
    "p": _T((240, 220, 180), "‡", False, "column"),
    "h": _T((215, 125, 80), "§", False, "hammock"),
    "s": _T((230, 150, 80), "¤", False, "bazaar stall"),
    "R": _T((185, 125, 85), "▒", False, "tiled roof"),
    "r": _T((190, 60, 60), "░", True, "carpet"),
    "Q": _T((255, 200, 80), "Ω", False, "divan"),
    "c": _T((205, 85, 140), "▫", False, "cushions"),
    "$": _T((255, 215, 0), "$", False, "gold"),
    "_": _T((165, 125, 85), "▪", True, "boards"),
    "D": _T((240, 200, 120), "▒", True, "gate"),
    "v": _T((230, 210, 170), "▼", True, "stairs down"),
    "u": _T((120, 200, 240), "∩", False, "fountain"),
}

DEPTHS_PAL = {
    "#": _T((115, 88, 62), "█", False, "rock"),
    ".": _T((155, 125, 88), "·", True, "tunnel floor"),
    "z": _T((200, 170, 110), "·", True, "pit sand", dark=True),
    "o": _T((230, 220, 200), "ø", False, "bones"),
    "_": _T((175, 145, 95), "·", True, "vault floor"),
    "$": _T((255, 215, 0), "$", False, "the Sultan's gold"),
    "C": _T((255, 200, 80), "▣", False, "treasure chest"),
    "m": _T((120, 200, 255), "∙", True, "binding circle"),
    "g": _T((200, 160, 80), "▒", True, "vault door"),
    "<": _T((230, 210, 170), "▲", True, "stairs up"),
}

SUN_ART = _mirror([
    r"                    \  |  /  ",
    r"          _          \ | /   ",
    r"         ( )       -- (O) ---",
    r"        _| |_         /|\    ",
    r"   _   |     |   _   / | \ __",
    r"  / \  |  o  |  / \     /    ",
    r" |   |_|_____|_|   |___/  o  ",
    r" | o   | ::: |   o |   |     ",
    r"~|_____|_____|_____|___|__/\_",
])


def _sun_colour(ch, x, y):
    if y <= 4 and ch in "\\|/-O":
        return fg(255, 210, 90)
    if ch == "~":
        return fg(90, 190, 230)
    if ch in "o:":
        return fg(120, 200, 240)
    if ch in "()":
        return fg(240, 200, 130)
    return fg(225, 175, 110)


class Sunspire:
    def __init__(self, world, player, loc=None, autosave=None):
        self.world = world
        self.player = player
        self.loc = loc
        self.autosave = autosave
        self.night = _is_night(world)
        self.scenes = {}

    def fine(self):
        return 150 + 25 * max(1, self.player.level)

    def run(self):
        p = self.player
        f = pflags(p)
        if f.get("sunspire_hostile"):
            note = f"The gate guards reach for their scimitars. There is the small matter of a fine ({self.fine()} gold)."
        elif self.night:
            note = "Night has fallen over the Kasbah. Lanterns sway in the palms; the colonnades are very dark."
        else:
            note = "Oud music, mint tea and the hush of palm leaves. Nobody here is in a hurry."
        show_banner(SUN_ART, [f"{C_SAND}{B_}S U N S P I R E   K A S B A H{R_}",
                              f"{C_OASIS}~ palace of Sultan Rahzim ~{R_}"],
                    _sun_colour, subtitle="Ash Sands · desert palace", note=note)
        nxt, entry = "kasbah", "gate"
        while True:
            sc = self.kasbah(entry) if nxt == "kasbah" else self.depths()
            res = sc.run(p)
            if res == "defeat" or not p.is_alive():
                return "defeat"
            if res == "to_depths":
                nxt = "depths"
            elif res == "to_kasbah":
                nxt, entry = "kasbah", "stairs"
            elif res == "rebuild":
                self.scenes.pop("kasbah", None)
                nxt, entry = "kasbah", (sc.px, sc.py)
            else:
                return res

    # ── the palace grounds ───────────────────────────────────────
    def kasbah(self, entry="gate"):
        sc = self.scenes.get("kasbah")
        if sc is None:
            sc = self._build_kasbah()
            self.scenes["kasbah"] = sc
        sc.result = None
        if entry == "stairs":
            sc.px, sc.py = 32, 5
        elif isinstance(entry, tuple):
            sc.px, sc.py = entry
        else:
            sc.px, sc.py = 49, 37
        self._apply_time(sc)
        self._apply_hostility(sc)
        return sc

    def _build_kasbah(self):
        p = self.player
        f = pflags(p)
        sc = CastleScene("SUNSPIRE KASBAH", parse_map(KASBAH_MAP), palette=KASBAH_PAL, start=(49, 37),
                         subtitle="palace of Sultan Rahzim", colour=C_SAND, world=self.world)
        sc.add_door(38, 6, "Stair room (the depths)", self._stair_door, step_back=False, tile="+")
        sc.add_door(61, 6, "Treasury antechamber", self._treasury_door, step_back=False, tile="+")
        for x, y in sc.find("v"):
            sc.add_door(x, y, "Stairs down beneath the palace", lambda s, pl: s.leave("to_depths"), tile="v")
        for x, y in sc.find("h"):
            sc.add_door(x, y, "Rest in a hammock", self._hammock, tile=None)
        for x, y in sc.find("$"):
            sc.add_door(x, y, "The Sultan's gold", self._steal_ante, tile=None)
        sc.add_door(20, 23, "The Mint Leaf tea house", self._teahouse, tile="+")
        sc.add_door(20, 27, "Caravan stables", self._stables, tile="+")
        sc.add_door(83, 11, "Guard barracks", self._barracks, tile="+")
        for (x, y, t, c) in ((16, 20, "MINT LEAF", C_GREEN), (17, 30, "STABLES", C_SAND),
                             (78, 7, "KASBAH GUARD", C_SAND), (77, 16, "BAZAAR", C_ROSE),
                             (44, 10, "AUDIENCE HALL", fg(255, 200, 80)), (29, 3, "STAIRS", C_DIM),
                             (63, 3, "TREASURY", C_GOLD), (12, 6, "PALM GARDEN", C_GREEN)):
            sc.add_label(x, y, t, c)
        sc.add_key("r", "Rest/Wait", self._wait)
        sc.hud_extra = lambda s, pl: ((f"{C_RED}⚔ WANTED (fine {self.fine()}g){R_}  " if pflags(pl).get("sunspire_hostile") else "")
                                      + (f"{fg(120, 140, 220)}☾ night{R_}" if self.night else f"{fg(255, 210, 90)}☼ day{R_}"))
        gcol = fg(230, 190, 120)
        # royals & court
        sc.add_entity(Entity(49, 4, "☼", fg(255, 210, 90), "Sultan Rahzim", npc_id="sultan_rahzim",
                             title="Sultan of Sunspire", interact=self._sultan))
        sc.add_entity(Entity(53, 5, "@", fg(200, 160, 230), "Vizier Qasim", npc_id="vizier_qasim", title="Grand Vizier",
                             lines=["The Sultan is in an excellent mood. Please do nothing to change that.",
                                    "Our vault is guarded by a djinn older than the dunes. He is... not pleasant.",
                                    "Beneath the palace is a pit. In the pit is a scorpion. The scorpion is the size of a barge."]))
        # guards (hostility toggled in _apply_hostility)
        for (x, y, n) in ((47, 14, "Palace Guard"), (52, 14, "Palace Guard"), (48, 32, "Gate Guard"),
                          (51, 32, "Gate Guard"), (39, 7, "Stair Guard")):
            sc.add_entity(Entity(x, y, "G", gcol, n, kind="guard", title="Kasbah Guard", data={"guard": True},
                                 lines=["Peace be upon you, traveller. Keep it that way.",
                                        "The Sultan's hospitality is famous. So is his patience. One of them has limits."],
                                 on_contact=self._guard_fight))
        sc.add_entity(Entity(43, 31, "G", fg(250, 210, 140), "Captain Farid", npc_id="captain_farid",
                             title="Captain of the Guard", interact=self._farid))
        # folk
        sc.add_entity(Entity(76, 31, "♪", fg(240, 180, 255), "Oud Player Selim", title="musician",
                             lines=["♪ The dunes are long, the wells are deep, the Sultan's tea will make you sleep ♪",
                                    "Request? I know eleven songs. Ten are about camels."]))
        sc.add_entity(Entity(80, 31, "♪", fg(240, 180, 255), "Drummer Lalla", title="musician",
                             lines=["Tak-tak-DUM. Tak-tak-DUM. You're stepping off the beat, friend.",
                                    "We play till the moon sets. Then we play quieter."]))
        for (x, y, n, ln) in ((78, 19, "Spice Seller", "Saffron, cumin, dragon pepper. Don't sniff the dragon pepper."),
                              (81, 22, "Silk Weaver", "Silk so light the wind steals it. That's why we tie it down."),
                              (84, 25, "Lamp Merchant", "Lamps! No djinn inside. Probably.")):
            sc.add_entity(Entity(x, y, "@", fg(240, 190, 120), n, title="bazaar", data={"merchant": True},
                                 interact=self._bazaar, lines=[ln]))
        sc.add_entity(Entity(70, 19, "@", fg(200, 200, 160), "Dozing Camel-driver", title="hammock enthusiast",
                             lines=["Zzz... five more minutes... zzz...", "The hammocks. Try the hammocks. Life is short."]))
        sc.add_entity(Entity(32, 21, "@", fg(150, 220, 200), "Gardener Yusra", title="oasis keeper", ai="wander", radius=2,
                             lines=["The oasis is fed by a spring under the palace. The scorpions like it too.",
                                    "Roses in the desert. You only need patience and a great deal of water."]))
        if not f.get("sunspire_nisa_joined") and not has_companion(p, "nisa_sandwalker"):
            sc.add_entity(Entity(27, 31, "N", fg(230, 170, 90), "Nisa Sandwalker", npc_id="nisa_sandwalker",
                                 title="desert scout", interact=self._nisa))
        # night assassins in the colonnades
        for (x, y) in ((7, 20), (92, 26), (9, 30)):
            sc.add_entity(Entity(x, y, "a", fg(160, 60, 160), "Desert Assassin", kind="assassin", hostile=True,
                                 ai="lurk", lurk=True, reveal_radius=2, on_contact=self._assassin,
                                 data={"assassin": True}))
        return sc

    def _apply_time(self, sc):
        sc.night = self.night
        for e in sc.entities:
            if e.data.get("assassin") and not e.data.get("slain"):
                e.alive = self.night
                e.revealed = False

    def _apply_hostility(self, sc):
        hostile = bool(pflags(self.player).get("sunspire_hostile"))
        for e in sc.entities:
            if e.data.get("guard"):
                e.hostile = hostile
                e.ai = "chase" if hostile else "static"
                if not hostile:
                    e.x, e.y = e.home

    # ── scenery & services ───────────────────────────────────────
    def _wait(self, scene, player):
        self.night = not self.night
        self._apply_time(scene)
        player.hp = min(player.max_hp, player.hp + player.max_hp // 10)
        return (f"{fg(120, 140, 220)}You sit and watch the sun sink. Night falls over the Kasbah.{R_}" if self.night
                else f"{fg(255, 210, 90)}You doze until dawn. The call of the tea-sellers wakes you.{R_}")

    def _hammock(self, scene, player):
        player.hp = min(player.max_hp, player.hp + player.max_hp // 3)
        player.mp = min(player.max_mp, player.mp + player.max_mp // 3)
        self.night = not self.night
        self._apply_time(scene)
        return (f"{C_OASIS}You sway in a hammock between two palms... and wake under the stars. (+HP/MP){R_}" if self.night
                else f"{C_OASIS}You sway in a hammock until the sun is high. Bliss. (+HP/MP){R_}")

    def _teahouse(self, scene, player):
        if pflags(player).get("sunspire_hostile"):
            return f"{C_RED}The tea-master shutters the window. 'No tea for outlaws.'{R_}"
        ent = Entity(0, 0, "@", C_GREEN, "Tea-master Habib", title="The Mint Leaf")
        scene.talk_box(ent, pick(["Mint tea, three sugars, poured from the height of a camel. That is the only correct way.",
                                  "Gossip with your tea? The Sultan's vault djinn hates everyone except the Sultan's cat.",
                                  "They say the assassins of the Black Sirocco walk the colonnades by night. Sit near a lamp."]),
                        player)
        if player.gold >= 5:
            player.gold -= 5
            player.hp = min(player.max_hp, player.hp + max(20, player.max_hp // 4))
            return f"{C_GREEN}You sip sweet mint tea (-5g). You feel restored.{R_}"
        return None

    def _stables(self, scene, player):
        return f"{C_SAND}Camels regard you with deep contempt. A stablehand sells you nothing.{R_}"

    def _barracks(self, scene, player):
        return f"{C_SAND}Off-duty guards play dice. 'Captain Farid handles fines, friend. Not us.'{R_}"

    def _bazaar(self, scene, player, ent):
        if pflags(player).get("sunspire_hostile"):
            scene.talk_box(ent, "Wanted by the guard? Then I don't know you. Shoo.", player)
            return None
        scene.talk_box(ent, ent.lines[0] if ent.lines else "Look, look! Buy, buy!", player)
        scene.modal(mini_shop, player, "BAZAAR OF SUNSPIRE", [
            ("Sunspire Scimitar", 650), ("Antidote", 12), ("Hi-Potion", 32), ("Smoke Bomb", 25),
            ("Regen Tonic", 30), ("Hero's Brew", 140)], C_SAND)
        return None

    def _stair_door(self, scene, player):
        f = pflags(player)
        if f.get("sunspire_hostile"):
            scene.px, scene.py = 39, 6
            return f"{C_RED}The stair guard levels his spear. 'Not while you're wanted.'{R_}"
        if (f.get("sunspire_pit_quest") or f.get("sunspire_vault_access")
                or kingdom_at_least(player, "cp_djinn")):
            return f"{C_SAND}The stair guard steps aside. 'Mind the scorpions.'{R_}"
        scene.px, scene.py = 39, 6
        return f"{C_SAND}'The depths are closed without the Sultan's leave,' says the stair guard.{R_}"

    def _treasury_door(self, scene, player):
        return f"{C_GOLD}The treasury antechamber glitters. Gold lies about in careless heaps.{R_}"

    def _steal_ante(self, scene, player):
        return self._steal(scene, player, 120 + 15 * player.level)

    def _steal(self, scene, player, amount):
        f = pflags(player)
        ch = scene.choice_box("Heaps of gold, unguarded. Nobody is looking...",
                              [("1", f"Fill your pockets (+{amount}g)"), ("2", "Leave it be")])
        if ch != "1":
            return None
        player.gold += amount
        f["sunspire_hostile"] = True
        f["sunspire_thefts"] = f.get("sunspire_thefts", 0) + 1
        k = self.scenes.get("kasbah")
        if k:
            self._apply_hostility(k)
        return f"{C_RED}A gong sounds. 'THIEF!' The Kasbah guard is after you!{R_}"

    def _guard_fight(self, scene, player, ent):
        enemy = make_elite("Royal Guard", player, zone="dungeon_deep", danger=3, mult=1.2)
        enemy.name = "Kasbah Guard"
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            ent.alive = False
            return f"{C_RED}The guard falls. More will come — pay your fine to Captain Farid to end this.{R_}"
        ent.cooldown = 4
        return None

    def _assassin(self, scene, player, ent):
        enemy = make_elite("Desert Assassin", player, zone="desert", danger=4, mult=1.25)
        scene.message(f"{fg(200, 90, 200)}A blade flashes in the dark of the colonnade!{R_}")
        res = scene.fight_enemy(player, enemy, first_strike=False)
        if res == "victory":
            ent.alive = False
            ent.data["slain"] = True
            pflags(player)["sunspire_assassins_slain"] = pflags(player).get("sunspire_assassins_slain", 0) + 1
            return f"{C_GREEN}The assassin's black veil falls to the sand.{R_}"
        ent.cooldown = 3
        return None

    def _farid(self, scene, player, ent):
        f = pflags(player)
        if f.get("sunspire_hostile"):
            fine = self.fine()
            scene.talk_box(ent, f"You have caused trouble in the Sultan's house. The fine is {fine} gold. Pay, and it is forgotten.", player)
            ch = scene.choice_box(f"Pay the fine of {fine} gold?", [("1", "Pay the fine"), ("2", "Refuse")], ent)
            if ch == "1":
                if player.gold < fine:
                    return f"{C_RED}You can't afford the fine. Farid sighs heavily.{R_}"
                player.gold -= fine
                f["sunspire_hostile"] = False
                f["sunspire_fines_paid"] = f.get("sunspire_fines_paid", 0) + 1
                for e in scene.entities:
                    if e.data.get("guard"):
                        e.alive = True
                self._apply_hostility(scene)
                return f"{C_GREEN}Fine paid. The guards sheathe their scimitars. Welcome back to Sunspire.{R_}"
            return None
        scene.talk_box(ent, pick(["Captain Farid. I keep the peace, so the Sultan can keep his naps.",
                                  "Watch the colonnades after dark. The Black Sirocco takes contracts even here.",
                                  "Steal from the Sultan and you'll meet me again. Less pleasantly."]), player)
        return None

    def _nisa(self, scene, player, ent):
        f = pflags(player)
        if f.get("sunspire_matriarch_dead"):
            scene.say_lines(ent, ["You killed the Matriarch? I've tracked her for two years. ...Fine. You're worth following.",
                                  "Nisa Sandwalker. I know every well between here and the sea. Want a guide?"])
            if try_recruit(player, "nisa_sandwalker", scene):
                f["sunspire_nisa_joined"] = True
                ent.alive = False
                return f"{C_GOLD}Nisa Sandwalker joins your party!{R_}"
            return None
        scene.talk_box(ent, pick(["Nisa. Scout. I don't do tea. The Matriarch under the palace killed my partner. Kill her and we'll talk.",
                                  "Sand tells you everything if you listen. Right now it says you're lost."]), player)
        return None

    # ── the Sultan ───────────────────────────────────────────────
    def _sultan(self, scene, player, ent):
        f = pflags(player)
        k = kingdom_step(player)
        if f.get("sunspire_hostile"):
            scene.talk_box(ent, "My guards tell me you are a troublemaker. Pay Captain Farid, and then we shall have tea again.", player)
            return None
        # kingdom story (cp_sultan was just completed by on_talk)
        if k == "cp_djinn" and not f.get("sunspire_vault_access"):
            scene.say_lines(ent, ["So Valdmere's own chancellor bought my crown. I knew that envoy smiled too much.",
                                  "Go below. Bind Azhar or break him, and take the Dawnglass Shard. Here — my seal opens the vault."])
            f["sunspire_vault_access"] = True
            return None
        lines = story_lines("sultan_rahzim", player)
        if not f.get("sunspire_tea"):
            scene.say_lines(ent, ["Ah! A guest! Sit, sit. Mind the cat; she is the true ruler here.",
                                  "I am Rahzim, Sultan of Sunspire, Keeper of the Oasis, and so on. Tea?"])
            ch = scene.choice_box("The Sultan pours you a glass of mint tea.",
                                  [("1", "Accept graciously: 'An honour, Your Majesty.'"),
                                   ("2", "'I didn't come for tea, old man.'"),
                                   ("3", "Sip politely and ask about the Kasbah")], ent)
            if ch == "2":
                f["sunspire_rude"] = f.get("sunspire_rude", 0) + 1
                f["sunspire_hostile"] = True
                self._apply_hostility(scene)
                scene.talk_box(ent, "...How sad. Guards — this guest is leaving. With some encouragement.", player)
                return f"{C_RED}The Kasbah guard turns on you! Pay a fine to Captain Farid to make amends.{R_}"
            if ch is None:
                return None
            f["sunspire_tea"] = True
            scene.talk_box(ent, "Wonderful! Nobody drinks tea properly any more. Everyone is in such a hurry to die heroically.", player)
            if ch == "3":
                scene.talk_box(ent, "My grandfather built the Kasbah around a spring. The scorpions found the spring first. We are negotiating.", player)
        if lines:
            scene.say_lines(ent, lines)
        # side quest: the Scorpion Matriarch
        if f.get("sunspire_matriarch_dead") and not f.get("sunspire_pit_rewarded"):
            scene.say_lines(ent, ["The Matriarch is dead? My goats will write songs about you.",
                                  "Take this cloak — woven for my own wedding — and my gold. And should you wish to test yourself "
                                  "against Azhar in the vault, my seal is yours."])
            f["sunspire_pit_rewarded"] = True
            f["sunspire_vault_access"] = True
            player.gold += 500
            try:
                player.gain_exp(400 + 30 * player.level)
            except Exception:
                pass
            give_item(player, "Sultan's Silk Cloak", scene=scene)
            return f"{C_GOLD}Side quest complete: The Matriarch Beneath (+500g){R_}"
        if f.get("sunspire_djinn_dead") and not f.get("sunspire_djinn_thanks"):
            f["sunspire_djinn_thanks"] = True
            scene.talk_box(ent, "Azhar is bound once more? The vault is quiet for the first time in sixty years. You are always welcome here.", player)
            return None
        if not f.get("sunspire_pit_quest") and not f.get("sunspire_matriarch_dead"):
            scene.say_lines(ent, ["Now. A small favour, between friends. Beneath this palace is a pit, and in the pit is a scorpion.",
                                  "She has eaten three goats, two guards and my least favourite cousin. I was fond of the goats."])
            ch = scene.choice_box("Will you deal with the Scorpion Matriarch?", [("1", "Consider it done."),
                                                                                ("2", "Perhaps later.")], ent)
            if ch == "1":
                f["sunspire_pit_quest"] = True
                return f"{C_GOLD}New side quest: The Matriarch Beneath — the stairs are in the palace's west room.{R_}"
            return None
        if f.get("sunspire_pit_quest") and not f.get("sunspire_matriarch_dead"):
            scene.talk_box(ent, "The pit is down the stairs in the west room. Take water. And perhaps a larger sword.", player)
            return None
        scene.talk_box(ent, pick(["More tea? There is always more tea.",
                                  "The cat approves of you. This is very rare. Do not let it go to your head.",
                                  "Sunspire is a simple place: water, shade, music. The rest is noise."]), player)
        return None

    # ── beneath the palace ───────────────────────────────────────
    def depths(self):
        sc = self.scenes.get("depths")
        if sc is None:
            sc = self._build_depths()
            self.scenes["depths"] = sc
        sc.result = None
        sc.px, sc.py = 37, 2
        return sc

    def _build_depths(self):
        f = pflags(self.player)
        sc = CastleScene("BENEATH SUNSPIRE", parse_map(DEPTHS_MAP), palette=DEPTHS_PAL, start=(37, 2),
                         subtitle="the scorpion pit and the djinn's vault", colour=C_SAND, world=self.world,
                         fog=True, sight=8)
        for x, y in sc.find("<"):
            sc.add_door(x, y, "Stairs up to the palace", lambda s, pl: s.leave("to_kasbah"), tile="<")
        if not (f.get("sunspire_vault_access") or kingdom_at_least(self.player, "cp_djinn")):
            for x, y in sc.find("g"):
                sc.add_door(x, y, "Sealed vault door", self._vault_door, step_back=False, tile="g")
        for x, y in sc.find("C") + sc.find("$"):
            sc.add_door(x, y, "The Sultan's treasure", self._vault_treasure, tile=None)
        if not f.get("sunspire_matriarch_dead"):
            sc.add_entity(Entity(15, 13, "M", fg(230, 90, 60), "Scorpion Matriarch", kind="boss", hostile=True,
                                 on_contact=self._matriarch, data={"pit": True}))
            for (x, y) in ((9, 7), (22, 18), (6, 12)):
                sc.add_entity(Entity(x, y, "s", fg(220, 140, 70), "Sand Scorpion", kind="beast", hostile=True,
                                     ai="lurk", lurk=True, reveal_radius=3, on_contact=self._scorpion,
                                     data={"pit": True}))
        if not f.get("sunspire_djinn_dead"):
            sc.add_entity(Entity(63, 11, "&", fg(120, 200, 255), "Sand Djinn Azhar", kind="boss", hostile=True,
                                 on_contact=self._djinn))
        return sc

    def _scorpion(self, scene, player, ent):
        enemy = make_elite("Sand Scorpion", player, zone="desert", danger=3)
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            ent.alive = False
            return f"{C_GREEN}The scorpion curls up and is still.{R_}"
        ent.cooldown = 3
        return None

    def _matriarch(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(Entity(0, 0, "M", fg(230, 90, 60), "Scorpion Matriarch"),
                        ["The sand heaves. A scorpion the size of a barge rises, clicking, her tail dripping green."])
        boss = make_boss("Scorpion Matriarch", player, power=1.3)
        res = scene.fight_enemy(player, boss, allow_escape=True)
        if res == "victory":
            ent.alive = False
            f["sunspire_matriarch_dead"] = True
            give_item(player, "Matriarch's Stinger", scene=scene)
            for e in scene.entities:
                if e.data.get("pit"):
                    e.alive = False
            return f"{C_GOLD}★ The Scorpion Matriarch is dead! Tell the Sultan.{R_}"
        if res == "escaped":
            ent.cooldown = 4
        return None

    def _vault_door(self, scene, player):
        f = pflags(player)
        if f.get("sunspire_vault_access") or kingdom_at_least(player, "cp_djinn"):
            _open(scene, "g")
            return f"{C_SAND}The Sultan's seal glows. The vault door grinds aside.{R_}"
        scene.px = 50
        return f"{C_SAND}The vault door bears the Sultan's seal. It will not open for you.{R_}"

    def _djinn(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(Entity(0, 0, "&", fg(120, 200, 255), "Sand Djinn Azhar"),
                        ["Sand lifts from the floor and spins into a towering shape with two burning blue eyes.",
                         "'ANOTHER THIEF? NO... A SEEKER. THE SHARD IS MINE UNTIL I AM UNMADE. TRY, LITTLE ONE.'"])
        boss = make_boss("Sand Djinn Azhar", player, power=1.45)
        res = scene.fight_enemy(player, boss, allow_escape=True)
        if res == "victory":
            ent.alive = False
            f["sunspire_djinn_dead"] = True
            give_item(player, "Djinn-Glass Talisman", scene=scene)
            if kingdom_step(player) is not None:
                f["crowns_dawnglass"] = True
                scene.message(f"{C_CYAN}You take the Dawnglass Shard from the swirling glass.{R_}")
            done = check_flags(player)
            if done:
                show_completions(done, scene, self.world)
            return f"{C_GOLD}★ Azhar is bound into glass once more.{R_}"
        if res == "escaped":
            ent.cooldown = 4
        return None

    def _vault_treasure(self, scene, player):
        return self._steal(scene, player, 300 + 30 * player.level)


def enter_sunspire(world, player, loc=None, autosave=None):
    try:
        res = Sunspire(world, player, loc, autosave).run()
    except Exception as e:
        import traceback
        _log(f"sunspire crashed: {e!r}\n{traceback.format_exc()}")
        res = "left"
    return _finish(world, player, res, f"{C_SAND}The music of Sunspire fades behind you into the dunes.{R_}")
