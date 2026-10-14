"""game_castles.py — the Duskthorn Citadel (demon castle, Ironspire) and the
Sunspire Kasbah (desert palace, Ash Sands).

Placement is driven from game_capital.place_capital() → place_castles().
Persistent state lives in player.flags under "demon_*" / "sunspire_*".
"""

from __future__ import annotations

import random

from game_term import C, clr
from game_scene import Entity, Tile, fg, parse_map, R_, B_, C_GOLD, C_DIM, C_WHITE, C_RED, C_GREEN, C_CYAN

import game_capital as cap
from game_capital import (CastleScene, pflags, set_flag, make_boss, make_elite, give_item,
                          try_recruit, has_companion, kingdom_step, kingdom_past, story_lines,
                          show_banner, pick, mini_shop, _log)

DEMON_NAME = "Duskthorn Citadel"
DESERT_NAME = "Sunspire Kasbah"
DEMON_GLYPH = "Z"
DESERT_GLYPH = "Y"


def _T(rgb, glyph, walk=True, name="", dark=False):
    return Tile(fg(*rgb), glyph, walk, name, dark)


# ═════════════════════════════════════════════════════════════════
#  REGISTRATION + PLACEMENT
# ═════════════════════════════════════════════════════════════════

def _arrive_demon(loc):
    return (f"{fg(230, 60, 40)}{B_}☠ {loc['name']}{R_} {fg(170, 60, 60)}— black spires over a moat of fire.{R_} "
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


def enter_duskthorn(world, player, loc=None, autosave=None):
    world.last_msg = f"{C_DIM}The citadel gates are shut.{R_}"


def enter_sunspire(world, player, loc=None, autosave=None):
    world.last_msg = f"{C_DIM}The Kasbah gates are shut.{R_}"
