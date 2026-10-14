"""
game_party.py — companions, party, roster and clan for Terminal-RPG.

  • 42 companions in 5 rarities (data + spawn rules: game_recruits.py)
  • Real XP / levels, gear (weapon / armour / trinket), traits, passives
    that actually do something, loyalty (affinity -100..100) with a
    signature skill and an outfit at Loyal, and departures when unhappy
  • Customisation: rename, title, marker, RGB colour styles shown on the
    companion's own sprite, outfit unlocks
  • Roster = active party (max 3) + bench (waiting at your hall / base)
  • Clan: income once per in-game day, upgrades with real effects

Public API (cross-team contract #6):
  COMPANION_DEFS                     id -> definition (dict)
  recruit_menu(player, town_name="") party / tavern / clan hub
  offer_recruit(player, companion_id, scene=None, cost=None) -> bool
  tavern_recruits(town_name, day, player=None) -> [ids]
  current_day(player, world=None)    in-game day number
Events other modules may call (all safe to call any time, return bool):
  wandering_recruit_event(player, continent_id)
  dungeon_prisoner_event(player, dungeon_name)
  ruins_stranger_event(player, place_name="")
  post_battle_recruit_chance(player, enemy)
Combat API for enemy AI (Companion): name, role, hp, max_hp, is_alive(),
  take_damage(n)->int, try_dodge()->bool, heal(n)->int, add_status(e);
  Party.pick_target(player) -> player or a companion (aggro-weighted).
"""

import random
import unicodedata

from game_term import C, clr, W, _vis
from game_recruits import (
    COMPANION_DEFS, COMPANION_BY_ID, PASSIVES, TRAITS, RARITIES, RARITY_ORDER,
    ROLE_STATS, ROLE_SKILL, ROLE_COLOUR, ROLE_CLASSES, GEAR_SLOTS,
    SIGNATURE_EFFECTS, COMPANION_STYLES, LEGACY_COLOURS, BONUS_TRAIT_POOL,
    STARBORN_ACCENT, DEF_VERSION, DAY_TURNS, CONTRACT_IDS,
    tavern_recruits, hire_cost, is_starborn, where_found, town_continent,
)

_R = "\033[0m"; _B = "\033[1m"
def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"
_GOLD = _fg(255, 215, 0);   _WHITE = _fg(240, 240, 240); _DIM = _fg(120, 120, 130)
_GREEN = _fg(90, 210, 110); _RED = _fg(225, 70, 70);     _CYAN = _fg(80, 220, 220)
_YELL = _fg(240, 200, 60);  _ORAN = _fg(230, 140, 40);   _PURP = _fg(185, 100, 235)
_PINK = _fg(255, 150, 200); _BLUE = _fg(90, 140, 255)

MAX_PARTY = 3
MAX_ROSTER = 30
AFF_MIN, AFF_MAX = -100, 100
LOYAL_AT = 60
LEAVE_AT = -60

__all__ = [
    "COMPANION_DEFS", "COMPANION_BY_ID", "MAX_PARTY", "Companion", "Party", "Clan",
    "recruit_menu", "party_menu", "offer_recruit", "tavern_recruits", "current_day",
    "wandering_recruit_event", "dungeon_prisoner_event", "ruins_stranger_event",
    "post_battle_recruit_chance", "try_world_companion_event", "customise_menu",
    "clan_daily_tick", "row_of_sprites", "sanitize_name", "sanitize_marker",
]


# ═══════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════

def _rgb(t, default=(240, 240, 240)):
    try:
        r, g, b = (max(0, min(255, int(v))) for v in t)
        return (r, g, b)
    except Exception:
        return default


def _col_rgb(rgb):
    return _fg(*_rgb(rgb))


def rarity_col(rarity):
    return _col_rgb(RARITIES.get(rarity, RARITIES["common"])["colour"])


def rarity_tag(rarity):
    info = RARITIES.get(rarity, RARITIES["common"])
    return f"{_col_rgb(info['colour'])}{'★' * info['stars']} {info['label']}{_R}"


def role_col(role):
    return _col_rgb(ROLE_COLOUR.get(role, (240, 240, 240)))


def _strip_ansi(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\x1b":
            # skip CSI / OSC sequences
            i += 1
            if i < len(s) and s[i] == "[":
                i += 1
                while i < len(s) and not ("@" <= s[i] <= "~"):
                    i += 1
                i += 1
            elif i < len(s) and s[i] == "]":
                while i < len(s) and s[i] not in ("\x07",):
                    if s[i] == "\x1b" and i + 1 < len(s) and s[i + 1] == "\\":
                        i += 1
                        break
                    i += 1
                i += 1
            else:
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def sanitize_name(s, maxlen=20):
    """Printable text only: no ANSI escapes, control or format characters,
    no wide/combining characters that would break the layout."""
    s = _strip_ansi(str(s or ""))
    keep = []
    for ch in s.replace("\t", " ").replace("\n", " ").replace("\r", " "):
        cat = unicodedata.category(ch)
        if cat[0] in ("C", "M") or cat in ("Zl", "Zp"):
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            continue
        keep.append(" " if cat == "Zs" else ch)
    out = " ".join("".join(keep).split())
    return out[:maxlen].strip()


def sanitize_marker(s):
    """A single, single-width printable character or None."""
    s = sanitize_name(s, 8).replace(" ", "")
    for ch in s:
        if ch in "[]":
            continue
        return ch
    return None


def _ask(prompt=">"):
    try:
        return input(C(f"{_GOLD}{prompt}{_R} ")).strip()
    except (EOFError, KeyboardInterrupt):
        return "0"


def _pause(msg="(Press Enter)"):
    try:
        input(C(f"{_DIM}{msg}{_R}"))
    except (EOFError, KeyboardInterrupt):
        pass


def _yes(prompt):
    return _ask(prompt + f" {_DIM}[Y/N]{_R}").lower() in ("y", "yes")


def _bar(cur, mx, w=12, col=None):
    mx = max(1, int(mx or 0))
    cur = max(0, min(int(cur or 0), mx))
    f = int(w * cur / mx)
    frac = cur / mx
    col = col or (_GREEN if frac > .5 else _YELL if frac > .25 else _RED)
    return f"{col}{'█' * f}{_DIM}{'░' * (w - f)}{_R}"


def _wrap(text, width):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def current_day(player=None, world=None):
    """In-game day: world turns // DAY_TURNS (party clock mirrors the world)."""
    try:
        if world is not None and hasattr(world, "turn_count"):
            return int(world.turn_count) // DAY_TURNS
    except Exception:
        pass
    try:
        return int(player.party.clock) // DAY_TURNS
    except Exception:
        return 0


def _count_item(player, name):
    n = 0
    for e in getattr(player, "inventory", []) or []:
        if getattr(e, "name", None) == name:
            n += getattr(e, "qty", 1)
    return n


def _remove_item(player, name, qty):
    try:
        from game_items import remove_items
        return remove_items(player.inventory, name, qty)
    except Exception:
        return 0


def _flags(player):
    f = getattr(player, "flags", None)
    if not isinstance(f, dict):
        f = {}
        try:
            player.flags = f
        except Exception:
            pass
    return f


def _clan_has(player, upgrade):
    clan = getattr(player, "owned_clan", None) if player is not None else None
    return bool(clan) and upgrade in (getattr(clan, "upgrades", []) or [])


# ═══════════════════════════════════════════════════════════════
# Passive effects
# ═══════════════════════════════════════════════════════════════
# aura: bonus to the PLAYER while the companion stands (replaces the old
# flat per-role bonuses that were counted twice).  team: bonus to every
# companion.  self: bonus to the companion itself.

PASSIVE_FX = {
    "bulwark":         dict(aura=dict(df=3), taunt=2),
    "keen_eye":        dict(aura=dict(stealth=3), team=dict(crit=10)),
    "field_medicine":  dict(heal_threshold=0.7, heal_cost=-2),
    "sand_step":       dict(aura=dict(stealth=2), team=dict(dodge=8)),
    "iron_grip":       dict(team=dict(hp=15)),
    "tailwind":        dict(aura=dict(stealth=4), team=dict(dodge=5)),
    "frost_aura":      dict(start_debuff=dict(atk_pct=8)),
    "permafrost":      dict(aura=dict(df=2), block=10),
    "icebloom_mend":   dict(after_heal=15),
    "mirage":          dict(self=dict(dodge=15)),
    "sandstorm":       dict(start_debuff=dict(atk_pct=5, crit=10)),
    "oasis_blessing":  dict(after_mp=10),
    "sea_legs":        dict(aura=dict(df=2), immune=["Poison", "Burn"]),
    "siren_song":      dict(start_debuff=dict(atk_flat=5)),
    "tidal_mend":      dict(heal_missing=0.2),
    "wanderers_edge":  dict(self=dict(crit=15)),
    "void_step":       dict(first_mult=1.5),
    "arcane_overflow": dict(aura=dict(skill=3), mp_mult=1.1),
    "holy_aura":       dict(regen=3),
    "storm_fists":     dict(double_crit=True),
    "prayer":          dict(start_heal=8),
    "trapper":         dict(after_item=20),
    "shield_wall":     dict(aura=dict(df=4)),
    "frostbite":       dict(proc=("stun", 12)),
    "lance_charge":    dict(first_mult=2.0),
    "pearl_diver":     dict(gold_pct=10),
    "tide_ward":       dict(cleanse=True),
    "brawler":         dict(low_hp_mult=1.25),
    "scavenger":       dict(after_gold=25),
    "gelatinous":      dict(dmg_taken=0.85),
    "cheap_shot":      dict(proc=("stun", 15)),
    "forbidden_lore":  dict(proc=("burn", 25)),
    "riposte":         dict(riposte=True),
    "starlight":       dict(aura=dict(skill=4), team=dict(crit=5)),
    "pathfinder":      dict(aura=dict(stealth=6)),
    "hex_ward":        dict(start_debuff=dict(atk_pct=6)),
    "royal_guard":     dict(aura=dict(df=5), taunt=3),
    "royal_ward":      dict(aura=dict(df=3, skill=6), regen=2),
    "hellfire_blade":  dict(proc=("burn", 30)),
    "desert_eyes":     dict(aura=dict(stealth=5), gold_pct=10),
    "old_guard":       dict(aura=dict(df=2), first_block=True),
    "dragonheart":     dict(boss_mult=1.2, immune=["Burn"]),
}


def _fx(passive_id):
    return PASSIVE_FX.get(passive_id or "", {})


# ═══════════════════════════════════════════════════════════════
# Companion
# ═══════════════════════════════════════════════════════════════

def _xp_to_next(level):
    n = 50
    for _ in range(max(0, int(level) - 1)):
        n = int(n * 1.25) + 10
    return n


def _status_from_dict(d):
    try:
        from game_items import status_from_dict
        return status_from_dict(d)
    except Exception:
        return None


def _fallback_def(cid, name="Stranger", role="warrior"):
    role = role if role in ROLE_STATS else "warrior"
    return dict(id=cid, name=name or "Stranger", title="Companion", role=role, rarity="common",
                sprite={"warrior": "Swordsman", "rogue": "Rogue", "mage": "Mage", "healer": "Healer"}[role],
                accent=(200, 200, 200), continent="ANY", spawn={"type": "none"}, bio="",
                passive_id="", passive="", traits=[], likes=[], dislikes=[], gifts=[],
                recruit={}, cost=0, mod={}, signature={"name": "Heroic Strike", "effect": "smite"},
                skill_name=None, alt={"label": "Veteran's Garb", "accent": (200, 200, 200)},
                dialogue=dict(hire=[], idle=[], loyal=[], leave=[]), town="Random", hire_cost=0)


class Companion:
    """A recruited companion. Stats are computed from its definition, level,
    rarity, traits, gear and party passives (see recalc)."""

    def __init__(self, data, player_level=1, starborn=False, rng=None):
        if isinstance(data, str):
            data = COMPANION_DEFS.get(data) or _fallback_def(data)
        d = COMPANION_DEFS.get(data.get("id")) or data
        if "spawn" not in d:                    # a legacy / partial dict
            d = _fallback_def(data.get("id", "unknown"), data.get("name"), data.get("role", "warrior"))
        self.d = d
        self.id = d["id"]
        self.base_name = d["name"]
        self.name = d["name"]
        self.custom_title = ""
        self.role = d["role"] if d["role"] in ROLE_STATS else "warrior"
        self.rarity = d.get("rarity", "common")
        self.level = max(1, int(player_level or 1))
        self.xp = 0
        self.affinity = 10
        self.starborn = bool(starborn)
        self.traits = list(d.get("traits", []))
        if self.starborn:
            rng = rng or random
            extra = [t for t in BONUS_TRAIT_POOL if t not in self.traits]
            if extra:
                self.traits.append(rng.choice(extra))
            self.traits.append("starborn")
        self.gear = {"weapon": None, "armor": None, "trinket": None}
        self.style = {"id": "signature", "label": "Signature", "accent": list(d.get("accent", (220, 220, 220))),
                      "crown": self.rarity == "legendary"}
        if self.starborn:
            self.style = {"id": "starborn", "label": "Starborn", "accent": list(STARBORN_ACCENT), "crown": True}
        self.marker = self._default_marker()
        self.colour_key = "custom"             # v1 field, kept for old readers
        self.floor = {}                        # v1 migration: stats never drop below this
        self.status_effects = []
        self.battles = 0
        self.kos = 0
        self.joined_day = 0
        self.flags = {}                        # per-companion misc (talk day, gift day, tiers seen)
        self.max_hp = self.max_mp = self.atk = self.defense = 1
        self._team = {}
        self._clan_forge = False
        self.recalc()
        self.hp = self.max_hp
        self.mp = self.max_mp
        self._reset_battle()

    # ── identity / text ───────────────────────────────────────────
    def _default_marker(self):
        return sanitize_marker(self.name) or "@"

    @property
    def title(self):
        return self.custom_title or self.d.get("title", "")

    @title.setter
    def title(self, value):
        self.custom_title = sanitize_name(value, 28)

    @property
    def passive_id(self):
        return self.d.get("passive_id", "")

    @property
    def passive(self):
        return self.d.get("passive", "")

    @property
    def continent(self):
        return self.d.get("continent", "ANY")

    @property
    def hire_cost(self):
        return hire_cost(self.id, self.level)

    @property
    def dialogue(self):
        dl = self.d.get("dialogue", {})
        return list(dl.get("idle", [])) + list(dl.get("hire", []))

    def line(self, trigger="idle"):
        dl = self.d.get("dialogue", {})
        pool = list(dl.get(trigger) or [])
        if trigger == "idle" and self.loyal:
            pool += list(dl.get("loyal") or [])
        if not pool:
            pool = list(dl.get("idle") or []) or ["..."]
        return random.choice(pool)

    @property
    def accent(self):
        return _rgb(self.style.get("accent") or self.d.get("accent"))

    @property
    def sprite(self):
        return self.d.get("sprite") or "Swordsman"

    @property
    def crown(self):
        return bool(self.style.get("crown"))

    def _col(self):
        return _col_rgb(self.accent)

    def tag(self):
        """Coloured 'marker name' used in combat logs and lists."""
        star = f"{_GOLD}✦{_R}" if self.starborn else ""
        return f"{self._col()}{self.marker} {_B}{self.name}{_R}{star}"

    # ── loyalty ────────────────────────────────────────────────────
    @property
    def loyal(self):
        return self.affinity >= LOYAL_AT

    def loyalty_tier(self):
        a = self.affinity
        if a >= LOYAL_AT:
            return "Loyal", _GOLD
        if a >= 25:
            return "Friendly", _GREEN
        if a > -25:
            return "Neutral", _WHITE
        if a > LEAVE_AT:
            return "Unhappy", _ORAN
        return "Leaving", _RED

    def change_affinity(self, delta, reason=""):
        """Adjust affinity. Positive gains scale with traits. Returns change."""
        delta = int(delta)
        if delta > 0:
            mult = 100 + sum(TRAITS.get(t, {}).get("mods", {}).get("aff_mult", 0) for t in self.traits)
            delta = max(1, delta * mult // 100)
        old_loyal = self.loyal
        old = self.affinity
        self.affinity = max(AFF_MIN, min(AFF_MAX, self.affinity + delta))
        if self.loyal and not old_loyal and not self.flags.get("loyal_seen"):
            self.flags["loyal_seen"] = True
            sig = self.d.get("signature", {})
            print(C(f"{_GOLD}{_B}★ {self.name} is now LOYAL!{_R} {_DIM}Signature skill:{_R} "
                    f"{_YELL}{sig.get('name', '?')}{_R}  {_DIM}· outfit unlocked:{_R} "
                    f"{_YELL}{self.d.get('alt', {}).get('label', '?')}{_R}"))
        return self.affinity - old

    def reaction(self, topic):
        """+1 like, -1 dislike, 0 neutral for an affinity topic."""
        if topic in self.d.get("likes", []):
            return 1
        if topic in self.d.get("dislikes", []):
            return -1
        return 0

    # ── stats ───────────────────────────────────────────────────────
    def _trait_mod(self, key):
        total = 0
        for t in self.traits:
            v = TRAITS.get(t, {}).get("mods", {}).get(key, 0)
            if isinstance(v, (int, float)):
                total += v
        return total

    def immune_to(self, status_name):
        for t in self.traits:
            if status_name in TRAITS.get(t, {}).get("mods", {}).get("immune", []):
                return True
        return status_name in _fx(self.passive_id).get("immune", [])

    def recalc(self, party=None, player=None):
        """Recompute derived stats. HP/MP are clamped, never refilled."""
        if party is not None:
            self._team = party.team_bonus()
        if player is not None:
            self._clan_forge = _clan_has(player, "Forge")
        rs = ROLE_STATS[self.role]
        g = RARITIES.get(self.rarity, RARITIES["common"])["growth"]
        mod = self.d.get("mod", {})
        L = self.level - 1
        hp = rs["base"]["hp"] + mod.get("hp", 0) + rs["grow"]["hp"] * g * L
        atk = rs["base"]["atk"] + mod.get("atk", 0) + rs["grow"]["atk"] * g * L
        df = rs["base"]["df"] + mod.get("df", 0) + rs["grow"]["df"] * g * L
        mp = rs["base"]["mp"] + mod.get("mp", 0) + rs["grow"]["mp"] * g * L
        hp *= 1 + self._trait_mod("hp_pct") / 100.0
        atk *= 1 + self._trait_mod("atk_pct") / 100.0
        df = df * (1 + self._trait_mod("def_pct") / 100.0) + self._trait_mod("df")
        mp *= 1 + self._trait_mod("mp_pct") / 100.0
        fl = self.floor or {}
        hp = max(int(hp), int(fl.get("max_hp", 0)))
        atk = max(int(atk), int(fl.get("atk", 0)))
        df = max(int(df), int(fl.get("defense", 0)))
        mp = max(int(mp), int(fl.get("max_mp", 0)))
        hp += self._team.get("hp", 0)
        if self._clan_forge:
            atk += 2; df += 2
        for it in self.gear.values():
            if it is not None:
                hp += getattr(it, "hp_bonus", 0) or 0
                atk += getattr(it, "atk_bonus", 0) or 0
                df += getattr(it, "def_bonus", 0) or 0
                mp += getattr(it, "mp_bonus", 0) or 0
        self.max_hp = max(1, int(hp))
        self.atk = max(1, int(atk))
        self.defense = max(0, int(df))
        self.max_mp = max(0, int(mp))
        self.hp = max(0, min(int(getattr(self, "hp", self.max_hp)), self.max_hp))
        self.mp = max(0, min(int(getattr(self, "mp", self.max_mp)), self.max_mp))

    @property
    def heal_power(self):
        g = RARITIES.get(self.rarity, RARITIES["common"])["growth"]
        base = 14 + 2.2 * g * (self.level - 1) + self.d.get("mod", {}).get("heal", 0)
        if self.role != "healer":
            base *= 0.6
        return int(base * (1 + self._trait_mod("heal_pct") / 100.0))

    def crit_chance(self):
        c = (15 if self.role == "rogue" else 8) + self._trait_mod("crit")
        c += _fx(self.passive_id).get("self", {}).get("crit", 0)
        c += self._team.get("crit", 0)
        return max(0, min(75, c))

    def dodge_chance(self):
        d = (12 if self.role == "rogue" else 5) + self._trait_mod("dodge")
        d += _fx(self.passive_id).get("self", {}).get("dodge", 0)
        d += self._team.get("dodge", 0)
        return max(0, min(60, d))

    # ── levels ─────────────────────────────────────────────────────
    @property
    def xp_to_next(self):
        return _xp_to_next(self.level)

    def xp_mult(self):
        return 1 + self._trait_mod("xp_pct") / 100.0

    def gain_exp(self, amount, cap_level=None, quiet=False):
        """Add XP (traits applied by the caller via xp_mult). Levels up to
        cap_level (the player's level); surplus XP is banked. Returns levels."""
        amount = max(0, int(amount))
        self.xp += amount
        gained = 0
        while self.xp >= self.xp_to_next and (cap_level is None or self.level < cap_level):
            self.xp -= self.xp_to_next
            old_hp, old_mp, old_atk = self.max_hp, self.max_mp, self.atk
            self.level += 1
            gained += 1
            self.recalc()
            self.hp = min(self.max_hp, self.hp + (self.max_hp - old_hp))
            self.mp = min(self.max_mp, self.mp + (self.max_mp - old_mp))
            if not quiet:
                print(C(f"{_GOLD}▲ {self.tag()} {_GOLD}reached Lv {self.level}!{_R} "
                        f"{_DIM}HP+{self.max_hp - old_hp} ATK+{self.atk - old_atk}{_R}"))
        if cap_level is not None and self.level >= cap_level:
            self.xp = min(self.xp, self.xp_to_next - 1)
        return gained

    def scale_to_level(self, new_level):
        """Raise level directly (debug / story rewards). Raises HP, MP, DEF."""
        new_level = int(new_level)
        if new_level <= self.level:
            return
        old_hp, old_mp = self.max_hp, self.max_mp
        self.level = new_level
        self.recalc()
        self.hp = min(self.max_hp, self.hp + (self.max_hp - old_hp))
        self.mp = min(self.max_mp, self.mp + (self.max_mp - old_mp))

    # ── gear ────────────────────────────────────────────────────────
    def gear_slot_for(self, item):
        slot = getattr(item, "slot", None)
        for gs, allowed in GEAR_SLOTS.items():
            if slot in allowed:
                return gs
        return None

    def can_wear(self, item):
        try:
            from game_items import Equipment
        except Exception:
            return False, "No gear system."
        if not isinstance(item, Equipment):
            return False, "Not equipment."
        gs = self.gear_slot_for(item)
        if gs is None:
            return False, f"{self.name} has no slot for {item.slot} items."
        allowed = getattr(item, "allowed_classes", None)
        if allowed and not set(allowed) & set(ROLE_CLASSES.get(self.role, [])):
            return False, f"A {self.role} can't use {item.name}."
        return True, gs

    def equip(self, item):
        """Wear item. Returns (ok, msg, removed_item_or_None)."""
        ok, gs = self.can_wear(item)
        if not ok:
            return False, gs, None
        old = self.gear.get(gs)
        self.gear[gs] = item
        self.recalc()
        return True, f"{self.name} equips {item.name}.", old

    def unequip(self, gs):
        it = self.gear.get(gs)
        self.gear[gs] = None
        self.recalc()
        return it

    # ── combat API ──────────────────────────────────────────────────
    def is_alive(self):
        return self.hp > 0

    def _reset_battle(self):
        self._battle_ref = None
        self._first_attack = True
        self._guard_used = False
        self._riposte = False
        self._acted_rounds = 0

    def take_damage(self, dmg):
        """Damage from an enemy. Returns damage actually taken (0 = blocked)."""
        fx = _fx(self.passive_id)
        try:
            dmg = int(dmg)
        except Exception:
            dmg = 1
        if fx.get("first_block") and not self._guard_used:
            self._guard_used = True
            print(C(f"{self.tag()} {_DIM}catches the blow on an old, dented shield!{_R}"))
            return 0
        if fx.get("block") and random.randint(1, 100) <= fx["block"]:
            print(C(f"{self.tag()} {_CYAN}blocks the hit completely!{_R}"))
            return 0
        if fx.get("dmg_taken"):
            dmg = int(dmg * fx["dmg_taken"])
        actual = max(1, dmg - self.defense // 3)
        was_alive = self.hp > 0
        self.hp = max(0, self.hp - actual)
        if was_alive and self.hp == 0:
            self.kos += 1
            print(C(f"{_RED}✖ {self.name} is knocked out!{_R}"))
        return actual

    def try_dodge(self):
        ok = random.randint(1, 100) <= self.dodge_chance()
        if ok and _fx(self.passive_id).get("riposte"):
            self._riposte = True
        return ok

    def heal(self, amount, revive=False):
        """Restore HP. Knocked-out companions need revive=True."""
        if self.hp <= 0 and not revive:
            return 0
        old = self.hp
        self.hp = max(0, min(self.max_hp, self.hp + max(0, int(amount))))
        return self.hp - old

    def add_status(self, effect):
        name = getattr(effect, "name", "")
        if self.immune_to(name):
            print(C(f"{self.tag()} {_DIM}shrugs off {name}.{_R}"))
            return
        for e in self.status_effects:
            if e.name == name:
                e.duration = max(e.duration, effect.duration)
                return
        self.status_effects.append(effect)

    def process_status(self):
        for e in self.status_effects[:]:
            try:
                e.on_turn_start(self)
            except Exception:
                pass
            e.duration -= 1
            if not e.is_active():
                self.status_effects.remove(e)

    def _damage_mult(self, enemy):
        fx = _fx(self.passive_id)
        m = 1.0
        if self._first_attack and fx.get("first_mult"):
            m *= fx["first_mult"]
        if fx.get("mp_mult") and self.mp > self.max_mp / 2:
            m *= fx["mp_mult"]
        if fx.get("low_hp_mult") and self.hp < self.max_hp / 2:
            m *= fx["low_hp_mult"]
        if fx.get("boss_mult") and getattr(enemy, "enemy_class", "") == "BOSS":
            m *= fx["boss_mult"]
        if self._team.get("war_room"):
            m *= 1.1
        return m

    def attack(self, enemy, mult=1.0, label=None, quiet=False):
        """Attack the enemy (respects enemy dodge). Returns damage dealt."""
        if not enemy.is_alive():
            return 0
        verb = f"{_YELL}{label}{_R}" if label else "attacks"
        if hasattr(enemy, "try_dodge") and enemy.try_dodge():
            self._first_attack = False
            if not quiet:
                print(C(f"{self.tag()} {verb} — {_DIM}{enemy.name} dodges!{_R}"))
            return 0
        mult *= self._damage_mult(enemy)
        self._first_attack = False
        base = max(1, self.atk + random.randint(-2, 3))
        crit = random.randint(1, 100) <= self.crit_chance()
        dmg = int(base * mult * (1.5 if crit else 1.0))
        actual = enemy.take_damage(max(1, dmg))
        tag = f" {_ORAN}{_B}CRIT!{_R}" if crit else ""
        if not quiet:
            print(C(f"{self.tag()} {verb}{tag} → {_RED}{actual}{_R} dmg"))
        fx = _fx(self.passive_id)
        if crit and fx.get("double_crit") and enemy.is_alive():
            extra = enemy.take_damage(max(1, int(base * mult)))
            actual += extra
            print(C(f"  {_CYAN}Storm Fists strike again → {_RED}{extra}{_R} dmg"))
        proc = fx.get("proc")
        if proc and enemy.is_alive() and random.randint(1, 100) <= proc[1]:
            self._apply_proc(enemy, proc[0])
        return actual

    def _apply_proc(self, enemy, kind):
        try:
            from game_items import Stun, Burn, Poison
        except Exception:
            return
        lv = self.level
        if kind == "stun":
            enemy.add_status(Stun(1))
            print(C(f"  {_CYAN}{enemy.name} is stunned!{_R}"))
        elif kind == "burn":
            enemy.add_status(Burn(3, 3 + lv // 3))
            print(C(f"  {_ORAN}{enemy.name} catches fire!{_R}"))
        elif kind == "poison":
            enemy.add_status(Poison(3, 3 + lv // 3))
            print(C(f"  {_GREEN}{enemy.name} is poisoned!{_R}"))

    def heal_target(self, target, mult=1.0, quiet=False):
        """Heal one ally (player or companion). Returns HP restored."""
        fx = _fx(self.passive_id)
        amount = int((self.heal_power + random.randint(0, 6)) * mult)
        if fx.get("heal_missing"):
            amount += int((target.max_hp - target.hp) * fx["heal_missing"])
        old = target.hp
        if target is self or isinstance(target, Companion):
            target.heal(amount)
        else:
            target.hp = min(target.max_hp, target.hp + amount)
        healed = target.hp - old
        if fx.get("cleanse"):
            for e in list(getattr(target, "status_effects", []) or []):
                if getattr(e, "name", "") in ("Poison", "Burn"):
                    target.status_effects.remove(e)
                    print(C(f"  {_CYAN}{getattr(target, 'name', 'Ally')} is cleansed of {e.name}.{_R}"))
        if not quiet:
            print(C(f"{self.tag()} heals {_GREEN}{getattr(target, 'name', 'ally')}{_R} "
                    f"for {_GREEN}+{healed} HP{_R}"))
        return healed

    def _heal_cost(self):
        return max(4, 8 + _fx(self.passive_id).get("heal_cost", 0))

    def combat_action(self, player, enemy, party=None):
        """One round of this companion's turn (called by run_combat)."""
        pobj = getattr(player, "party", None)
        if not isinstance(pobj, Party):
            pobj = None
        if self._battle_ref is not enemy:
            self._reset_battle()
            self._battle_ref = enemy
        if pobj is not None:
            pobj._tick_round(player, enemy, self)
        if not self.is_alive():
            return
        stunned = any(getattr(e, "name", "") == "Stun" for e in self.status_effects)
        self.process_status()
        if not self.is_alive():
            print(C(f"{_RED}✖ {self.name} collapses!{_R}"))
            return
        self._acted_rounds += 1
        # MP regeneration for casters (healers used to run dry for good)
        if self.role in ("mage", "healer"):
            self.mp = min(self.max_mp, self.mp + 2 + self.level // 10)
        if stunned:
            print(C(f"{self.tag()} {_DIM}is stunned and can't act.{_R}"))
            return
        if self.affinity <= -25 and random.randint(1, 100) <= 20:
            print(C(f"{self.tag()} {_ORAN}ignores your call and sulks.{_R}"))
            return
        if not enemy.is_alive():
            return
        if self._riposte:
            self._riposte = False
            self.attack(enemy, 0.7, "ripostes")
            if not enemy.is_alive():
                return
        allies = [player] + [c for c in (pobj.members if pobj else (party or []))
                             if isinstance(c, Companion) and c.is_alive()]
        # Healers: heal the most wounded first
        if self.role == "healer":
            thr = _fx(self.passive_id).get("heal_threshold", 0.6)
            wounded = [a for a in allies if a.hp / max(1, a.max_hp) < thr and a.hp > 0]
            if len(wounded) >= 2 and self.mp >= ROLE_SKILL["healer"]["mp"]:
                self._use_skill(player, enemy, allies)
                return
            if wounded and self.mp >= self._heal_cost():
                needy = min(wounded, key=lambda t: t.hp / max(1, t.max_hp))
                self.mp -= self._heal_cost()
                self.heal_target(needy)
                return
        # Signature (loyal) every 4th round, skill every 3rd round
        if self.loyal and self._acted_rounds % 4 == 0 and self.mp >= 15:
            self._use_signature(player, enemy, allies)
            return
        sk = ROLE_SKILL[self.role]
        if self._acted_rounds % 3 == 0 and self.mp >= sk["mp"] and sk["effect"] == "strike":
            self.mp -= sk["mp"]
            self.attack(enemy, sk["mult"], self.d.get("skill_name") or sk["name"])
            return
        self.attack(enemy)

    def _use_skill(self, player, enemy, allies):
        sk = ROLE_SKILL["healer"]
        self.mp -= sk["mp"]
        name = self.d.get("skill_name") or sk["name"]
        print(C(f"{self.tag()} casts {_YELL}{name}{_R}!"))
        for a in allies:
            if a.hp > 0:
                self.heal_target(a, sk["mult"], quiet=True)
        print(C(f"  {_GREEN}The whole party is mended.{_R}"))

    def _use_signature(self, player, enemy, allies):
        sig = self.d.get("signature", {})
        eff = sig.get("effect", "smite")
        name = sig.get("name", "Signature")
        self.mp -= 15
        label = f"★{name}"
        if eff == "smite":
            self.attack(enemy, 2.2, label)
        elif eff == "volley":
            print(C(f"{self.tag()} unleashes {_YELL}{label}{_R}!"))
            total = 0
            for _ in range(3):
                if enemy.is_alive():
                    total += self.attack(enemy, 0.8, quiet=True)
            print(C(f"  {_RED}{total}{_R} total damage"))
        elif eff == "stun":
            if self.attack(enemy, 1.5, label) and enemy.is_alive():
                self._apply_proc(enemy, "stun")
        elif eff == "inferno":
            if self.attack(enemy, 1.8, label) and enemy.is_alive():
                self._apply_proc(enemy, "burn")
        elif eff == "venom":
            if self.attack(enemy, 1.4, label) and enemy.is_alive():
                self._apply_proc(enemy, "poison")
        elif eff == "drain":
            dealt = self.attack(enemy, 1.6, label)
            got = self.heal(dealt // 2)
            if got:
                print(C(f"  {_GREEN}{self.name} drains {got} HP{_R}"))
        elif eff == "sanctuary":
            print(C(f"{self.tag()} invokes {_YELL}{label}{_R}!"))
            for a in allies:
                if a.hp > 0:
                    self.heal_target(a, 1.3, quiet=True)
            print(C(f"  {_GREEN}Light washes over the party.{_R}"))
        elif eff == "rally":
            try:
                from game_items import Regen
                print(C(f"{self.tag()} sounds {_YELL}{label}{_R}! {_GREEN}Everyone regenerates.{_R}"))
                for a in allies:
                    if a.hp > 0 and hasattr(a, "add_status"):
                        a.add_status(Regen(3, 4 + self.level // 4))
            except Exception:
                self.attack(enemy, 1.5, label)
        else:
            self.attack(enemy, 2.0, label)

    def rest(self):
        """Full heal (inn / Royal Suite) — also revives."""
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.status_effects = []

    def hp_bar(self, w=16):
        mx = max(1, self.max_hp)
        return f"{_bar(self.hp, mx, w)} {_DIM}{self.hp}/{mx}{_R}"

    # ── save / load ────────────────────────────────────────────────
    def to_dict(self):
        gear = {}
        for k, it in self.gear.items():
            if it is not None:
                try:
                    gear[k] = it.to_dict()
                except Exception:
                    pass
        return {
            "id": self.id, "def_ver": DEF_VERSION, "name": self.name,
            "title": self.custom_title, "level": self.level, "xp": self.xp,
            "hp": self.hp, "mp": self.mp,
            # derived stats are saved too so older builds can still read them
            "max_hp": self.max_hp, "atk": self.atk, "defense": self.defense, "max_mp": self.max_mp,
            "affinity": self.affinity, "starborn": self.starborn, "traits": list(self.traits),
            "gear": gear, "style": dict(self.style, accent=list(self.accent)),
            "marker": self.marker, "colour_key": self.colour_key, "floor": dict(self.floor),
            "status_effects": [e.to_dict() for e in self.status_effects if hasattr(e, "to_dict")],
            "battles": self.battles, "kos": self.kos, "joined_day": self.joined_day,
            "flags": dict(self.flags),
        }

    @classmethod
    def from_dict(cls, d):
        """Load v2 or migrate a v1 save entry. Raises KeyError for unknown ids
        (Party.from_dict keeps those raw)."""
        cid = d["id"]
        base = COMPANION_DEFS.get(cid)
        if base is None:
            raise KeyError(cid)
        try:
            level = max(1, min(999, int(d.get("level", 1))))
        except Exception:
            level = 1
        c = cls(base, level, starborn=False)
        c.starborn = bool(d.get("starborn", False))
        if isinstance(d.get("traits"), list):
            c.traits = [t for t in d["traits"] if t in TRAITS] or list(base.get("traits", []))
        nm = sanitize_name(d.get("name", c.name), 20)
        c.name = nm or c.base_name
        c.custom_title = sanitize_name(d.get("title", "") or "", 28)
        if d.get("def_ver", 1) < 2:
            # v1: stats were stored; keep max(saved, computed) so nobody loses power
            fl = {}
            for k in ("max_hp", "atk", "defense", "max_mp"):
                try:
                    fl[k] = int(d.get(k, 0) or 0)
                except Exception:
                    pass
            c.floor = fl
            ck = d.get("colour_key", "white")
            if ck in LEGACY_COLOURS and ck != "white":
                c.style = {"id": "custom", "label": "Classic " + ck.title(),
                           "accent": list(LEGACY_COLOURS[ck]), "crown": False}
            c.colour_key = ck if isinstance(ck, str) else "white"
        else:
            fl = d.get("floor") or {}
            c.floor = {k: int(v) for k, v in fl.items() if isinstance(v, (int, float))}
            st = d.get("style")
            if isinstance(st, dict):
                c.style = {"id": str(st.get("id", "custom"))[:24],
                           "label": sanitize_name(st.get("label", "Custom"), 24) or "Custom",
                           "accent": list(_rgb(st.get("accent", c.accent))),
                           "crown": bool(st.get("crown", False))}
            try:
                c.xp = max(0, int(d.get("xp", 0)))
            except Exception:
                c.xp = 0
            try:
                c.affinity = max(AFF_MIN, min(AFF_MAX, int(d.get("affinity", 10))))
            except Exception:
                c.affinity = 10
            c.battles = int(d.get("battles", 0) or 0)
            c.kos = int(d.get("kos", 0) or 0)
            c.joined_day = int(d.get("joined_day", 0) or 0)
            if isinstance(d.get("flags"), dict):
                c.flags = dict(d["flags"])
            gear = d.get("gear") or {}
            if isinstance(gear, dict):
                try:
                    from game_items import item_from_dict
                    for k, raw in gear.items():
                        if k in c.gear and raw:
                            try:
                                c.gear[k] = item_from_dict(raw)
                            except Exception:
                                pass
                except Exception:
                    pass
        c.marker = sanitize_marker(d.get("marker", "")) or c._default_marker()
        c.status_effects = []
        for e in d.get("status_effects", []) or []:
            try:
                st = _status_from_dict(e)
                if st is not None:
                    c.status_effects.append(st)
            except Exception:
                pass
        c.recalc()
        try:
            c.hp = max(0, min(int(d.get("hp", c.max_hp)), c.max_hp))
        except Exception:
            c.hp = c.max_hp
        try:
            c.mp = max(0, min(int(d.get("mp", c.max_mp)), c.max_mp))
        except Exception:
            c.mp = c.max_mp
        return c


# ═══════════════════════════════════════════════════════════════
# Party (active members + bench = roster)
# ═══════════════════════════════════════════════════════════════

class Party:
    """Active party (max MAX_PARTY) plus a bench of recruited companions."""

    def __init__(self):
        self.members = []          # active, fight with you
        self.bench = []            # recruited, waiting at your hall / base
        self.unresolved = []       # raw save entries for unknown ids (kept, not dropped)
        self.departed = {}         # id -> day they left in anger
        self.clock = 0             # mirrors the world turn counter
        self.wander_cd = 0
        self._battle_ref = None
        self._round = 0
        self._acted = set()

    # ── roster ─────────────────────────────────────────────────────
    @property
    def roster(self):
        return list(self.members) + list(self.bench)

    def find(self, cid):
        for c in self.roster:
            if c.id == cid:
                return c
        return None

    def has(self, cid):
        return self.find(cid) is not None

    def add(self, companion):
        """Recruit: joins the active party, or the bench when it is full."""
        if self.has(companion.id):
            return False, f"{companion.name} is already with you."
        if len(self.roster) >= MAX_ROSTER:
            return False, "Your roster is full."
        self.departed.pop(companion.id, None)
        if len(self.members) < MAX_PARTY:
            self.members.append(companion)
            self.refresh()
            return True, f"{companion.name} joined the party!"
        self.bench.append(companion)
        self.refresh()
        return True, f"{companion.name} joined your roster and waits at your hall (party full)."

    def bench_member(self, idx):
        if not (0 <= idx < len(self.members)):
            return False, "Invalid slot."
        c = self.members.pop(idx)
        self.bench.append(c)
        c.change_affinity(-2)
        self.refresh()
        return True, f"{c.name} heads back to wait on the bench."

    def remove(self, idx):
        """Legacy 'dismiss': benches instead of deleting the companion."""
        return self.bench_member(idx)

    def activate(self, cid):
        for i, c in enumerate(self.bench):
            if c.id == cid:
                if len(self.members) >= MAX_PARTY:
                    return False, "Your party is full — bench someone first."
                self.members.append(self.bench.pop(i))
                self.refresh()
                return True, f"{c.name} rejoins the party!"
        return False, "Not on the bench."

    def release(self, cid):
        """Part ways for good (they go home; may be re-recruited)."""
        for lst in (self.members, self.bench):
            for i, c in enumerate(lst):
                if c.id == cid:
                    lst.pop(i)
                    self.refresh()
                    return c
        return None

    def alive_members(self):
        return [c for c in self.members if c.is_alive()]

    # ── passives ───────────────────────────────────────────────────
    def team_bonus(self):
        out = {}
        for c in self.members:
            for k, v in _fx(c.passive_id).get("team", {}).items():
                out[k] = out.get(k, 0) + v
        if getattr(self, "_war_room", False):
            out["war_room"] = 1
        return out

    def refresh(self, player=None):
        """Recompute stats after roster / gear / passive changes."""
        if player is not None:
            self._war_room = _clan_has(player, "War Room")
        for c in self.members:
            c.recalc(self, player)
        for c in self.bench:
            c._team = {}
            c.recalc(None, player)

    def _aura(self, key):
        return sum(_fx(c.passive_id).get("aura", {}).get(key, 0) for c in self.alive_members())

    def total_stealth_bonus(self):
        return self._aura("stealth")

    def total_atk_bonus(self):
        return self._aura("atk")

    def total_def_bonus(self):
        return self._aura("df")

    def total_heal_bonus(self):
        return self._aura("heal")

    def total_skill_power(self):
        return self._aura("skill")

    def gold_bonus_pct(self):
        return sum(_fx(c.passive_id).get("gold_pct", 0) for c in self.alive_members())

    def pick_target(self, player, rng=None):
        """Aggro-weighted target for enemy attacks: the player or an alive
        companion. Warriors and 'taunt' passives draw more attention."""
        rng = rng or random
        opts = [(player, 4)]
        for c in self.alive_members():
            w = {"warrior": 3, "rogue": 1, "mage": 1, "healer": 1}.get(c.role, 1)
            w += _fx(c.passive_id).get("taunt", 0)
            opts.append((c, w))
        total = sum(w for _, w in opts)
        r = rng.uniform(0, total)
        for t, w in opts:
            r -= w
            if r <= 0:
                return t
        return player

    def _tick_round(self, player, enemy, comp):
        """Called by each companion's combat_action: detects battle start and
        new rounds, applies party-wide round effects once per round."""
        if self._battle_ref is not enemy:
            self._battle_ref = enemy
            self._round = 1
            self._acted = {comp.id}
            self.refresh(player)
            self._battle_start(player, enemy)
            self._round_effects(player)
            return
        if comp.id in self._acted:
            self._round += 1
            self._acted = set()
            self._round_effects(player)
        self._acted.add(comp.id)

    def _battle_start(self, player, enemy):
        for c in self.alive_members():
            fx = _fx(c.passive_id)
            deb = fx.get("start_debuff")
            if deb:
                old = enemy.atk
                cut = int(old * deb.get("atk_pct", 0) / 100.0) + deb.get("atk_flat", 0)
                if deb.get("atk_flat"):
                    cut = min(cut, max(1, old // 10))
                if cut > 0:
                    enemy.atk = max(1, old - cut)
                if deb.get("crit") and hasattr(enemy, "crit_chance"):
                    enemy.crit_chance = max(0, enemy.crit_chance - deb["crit"])
                print(C(f"{c.tag()}'s {_CYAN}{PASSIVES.get(c.passive_id, {}).get('name', '')}{_R} "
                        f"weakens {enemy.name} {_DIM}(ATK -{cut}){_R}"))
            if fx.get("start_heal") and player.hp < player.max_hp:
                amt = fx["start_heal"] + c.level // 2
                old = player.hp
                player.hp = min(player.max_hp, player.hp + amt)
                print(C(f"{c.tag()} prays for you: {_GREEN}+{player.hp - old} HP{_R}"))

    def _round_effects(self, player):
        regen = sum(_fx(c.passive_id).get("regen", 0) + (c.level // 10 if _fx(c.passive_id).get("regen") else 0)
                    for c in self.alive_members())
        if regen > 0:
            if player.hp > 0:
                player.hp = min(player.max_hp, player.hp + regen)
            for c in self.alive_members():
                c.heal(regen)
            print(C(f"{_GREEN}✚ A soothing aura heals the party (+{regen} HP){_R}"))

    def end_battle(self):
        self._battle_ref = None
        self._round = 0
        self._acted = set()
        for c in self.roster:
            c._reset_battle()

    # ── XP & victory ───────────────────────────────────────────────
    def gain_exp(self, amount, player=None):
        """Share of victory XP for the active party (60% each, +catch-up for
        companions far below the player; benched companions train for 25%
        with the Training Grounds clan upgrade). Returns {id: levels}."""
        out = {}
        try:
            amount = max(0, int(amount))
        except Exception:
            return out
        if amount <= 0:
            return out
        cap = getattr(player, "level", None)
        tg = _clan_has(player, "Training Grounds")
        for c in self.members:
            if not c.is_alive():
                continue
            share = amount * 0.6 * c.xp_mult()
            if tg:
                share *= 1.10
            if cap is not None and c.level < cap - 2:
                share *= 1.5
            out[c.id] = c.gain_exp(int(share), cap)
        if tg:
            for c in self.bench:
                out[c.id] = c.gain_exp(int(amount * 0.25 * c.xp_mult()), cap, quiet=True)
        if any(out.values()):
            self.refresh(player)
        return out

    def after_victory(self, player, enemy):
        """Everything companions do after a won battle. Safe: never raises."""
        try:
            self._after_victory(player, enemy)
        except Exception as e:      # never break award_victory
            try:
                import os
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
                    f.write(f"party.after_victory: {e!r}\n")
            except Exception:
                pass
        finally:
            self.end_battle()

    def _after_victory(self, player, enemy):
        is_boss = getattr(enemy, "enemy_class", "") == "BOSS"
        if self.members:
            self.gain_exp(getattr(enemy, "exp_reward", 0), player)
        for c in self.members:
            c.battles += 1
            if c.hp <= 0:
                c.hp = max(1, c.max_hp // 10)
                print(C(f"{_DIM}{c.name} staggers back to their feet ({c.hp} HP).{_R}"))
            c.mp = min(c.max_mp, c.mp + max(1, c.max_mp * 15 // 100))
        alive = self.alive_members()
        for c in alive:
            fx = _fx(c.passive_id)
            if fx.get("after_heal"):
                amt = fx["after_heal"] + c.level
                player.hp = min(player.max_hp, player.hp + amt)
                for o in alive:
                    o.heal(amt)
                print(C(f"{c.tag()}'s {_CYAN}Icebloom Mend{_R} heals everyone {_GREEN}+{amt} HP{_R}"))
            if fx.get("after_mp"):
                amt = fx["after_mp"]
                player.mp = min(player.max_mp, player.mp + amt)
                for o in alive:
                    o.mp = min(o.max_mp, o.mp + amt)
                print(C(f"{c.tag()}'s {_CYAN}Oasis Blessing{_R} restores {_BLUE}+{amt} MP{_R}"))
            if fx.get("after_item") and random.randint(1, 100) <= fx["after_item"]:
                try:
                    from game_items import ITEM_POOL
                    nm = random.choice(["Wolf Pelt", "Feather"])
                    if nm in ITEM_POOL and player.add_item(ITEM_POOL[nm]()):
                        print(C(f"{c.tag()} skins a {_WHITE}{nm}{_R} from the remains."))
                except Exception:
                    pass
            if fx.get("after_gold") and random.randint(1, 100) <= fx["after_gold"]:
                g = random.randint(3, 8) + c.level
                player.gold += g
                print(C(f"{c.tag()} pockets something shiny: {_GOLD}+{g}g{_R}"))
        pct = self.gold_bonus_pct()
        if pct and getattr(enemy, "gold_reward", 0):
            g = max(1, enemy.gold_reward * pct // 100)
            player.gold += g
            print(C(f"{_GOLD}+{g}g{_R} {_DIM}(companions' sharp eyes){_R}"))
        # loyalty
        for c in self.members:
            delta = 1 if c.reaction("battle") > 0 else 0
            if c.reaction("battle") < 0 and random.randint(1, 3) == 1:
                delta -= 1
            if is_boss:
                delta += 3 if c.reaction("boss") > 0 else 1
            if delta:
                c.change_affinity(delta)
        if alive and random.randint(1, 4) == 1:
            c = random.choice(alive)
            print(C(f"{c.tag()}: {_DIM}\"{c.line('idle')}\"{_R}"))
        _tick_companion_quests(player, enemy)
        self.react_to_world(player)
        self._check_departures(player)
        try:
            post_battle_recruit_chance(player, enemy)
        except Exception:
            pass

    def react_to_world(self, player):
        """One-off loyalty reactions to big choices stored in player.flags
        (e.g. the demon pact): companions who dislike demons are appalled."""
        f = _flags(player)
        n = 0
        for flag, topic, label in (("demon_pact", "demons", "your pact with the demon lord"),):
            if not f.get(flag):
                continue
            for c in self.roster:
                key = f"reacted_{flag}"
                if c.flags.get(key):
                    continue
                c.flags[key] = True
                r = c.reaction(topic)
                n += 1 if r else 0
                if r < 0:
                    c.change_affinity(-20)
                    print(C(f"{c.tag()} {_RED}is appalled by {label}.{_R}"))
                elif r > 0:
                    c.change_affinity(10)
                    print(C(f"{c.tag()} {_GREEN}approves of {label}.{_R}"))
        return n

    def _check_departures(self, player=None):
        gone = []
        for c in list(self.roster):
            if c.affinity <= LEAVE_AT:
                self.release(c.id)
                self.departed[c.id] = current_day(player) if player is not None else 0
                print(C(f"{_RED}{_B}{c.name} leaves you.{_R} {_DIM}\"{c.line('leave')}\"{_R}"))
                gone.append(c.id)
        return gone

    def rest_all(self, full=True, pct=100):
        for c in self.roster:
            if full:
                c.rest()
            else:
                c.hp = max(c.hp, min(c.max_hp, c.max_hp * pct // 100))
                c.mp = max(c.mp, min(c.max_mp, c.max_mp * pct // 100))
                c.status_effects = []

    # ── world clock & map hook ─────────────────────────────────────
    def scale_all(self, player_level=None, turn=None, world=None, player=None):
        """Called on every world-map step. Companions no longer copy the
        player's level (they earn XP); this keeps the in-game clock in sync
        with the world and occasionally triggers a wandering recruit."""
        try:
            if turn is not None:
                self.clock = max(int(self.clock), int(turn))
            else:
                self.clock = int(self.clock) + 1
        except Exception:
            self.clock = 0
        if world is not None and player is not None:
            try:
                self._maybe_wander(player, world)
            except Exception:
                pass

    def _maybe_wander(self, player, world):
        if self.clock - self.wander_cd < 300:
            return
        if random.randint(1, 260) != 1:
            return
        x, y = getattr(world, "player_x", 0), getattr(world, "player_y", 0)
        try:
            if world._loc_at(x, y):
                return
            cont = world.cont_map[y][x]
        except Exception:
            return
        if not cont or cont == " ":
            return
        if wandering_recruit_event(player, cont):
            self.wander_cd = self.clock
        else:
            self.wander_cd = self.clock - 150

    # ── save / load ─────────────────────────────────────────────────
    def to_dict(self):
        return {
            "def_ver": DEF_VERSION,
            "members": [c.to_dict() for c in self.members],
            "bench": [c.to_dict() for c in self.bench],
            "unresolved": list(self.unresolved),
            "departed": dict(self.departed),
            "clock": int(self.clock),
            "wander_cd": int(self.wander_cd),
        }

    @classmethod
    def from_dict(cls, d):
        p = cls()
        if not isinstance(d, dict):
            return p
        seen = set()

        def _load(entries, active):
            for cd in entries or []:
                if not isinstance(cd, dict) or not cd.get("id"):
                    if isinstance(cd, dict):
                        p.unresolved.append(cd)
                    continue
                if cd["id"] in seen:
                    continue
                try:
                    c = Companion.from_dict(cd)
                except Exception:
                    p.unresolved.append(cd)
                    continue
                seen.add(c.id)
                if active and len(p.members) < MAX_PARTY:
                    p.members.append(c)
                else:
                    p.bench.append(c)

        _load(d.get("members"), True)
        _load(d.get("bench"), False)
        for raw in d.get("unresolved", []) or []:
            if isinstance(raw, dict) and raw not in p.unresolved:
                if raw.get("id") in COMPANION_DEFS and raw["id"] not in seen:
                    _load([raw], False)          # a def that exists again
                else:
                    p.unresolved.append(raw)
        dep = d.get("departed") or {}
        if isinstance(dep, dict):
            p.departed = {k: v for k, v in dep.items() if isinstance(k, str)}
        try:
            p.clock = max(0, int(d.get("clock", 0)))
            p.wander_cd = int(d.get("wander_cd", 0))
        except Exception:
            pass
        p.refresh()
        return p


# ═══════════════════════════════════════════════════════════════
# Companion mini-quests (recruit conditions)
# ═══════════════════════════════════════════════════════════════

def _quests(player):
    f = _flags(player)
    q = f.get("comp_quests")
    if not isinstance(q, dict):
        q = {}
        f["comp_quests"] = q
    return q


def _quest_done(player, qid):
    return bool(_flags(player).get(f"comp_quest_done_{qid}"))


def _start_quest(player, cid, quest):
    q = _quests(player)
    if quest["id"] not in q:
        q[quest["id"]] = {"cid": cid, "progress": 0, "count": int(quest.get("count", 1)),
                          "kill": list(quest.get("kill", ["*"])), "desc": quest.get("desc", "")}


def _tick_companion_quests(player, enemy):
    q = _quests(player)
    name = str(getattr(enemy, "name", "")).lower()
    for qid, st in list(q.items()):
        if _quest_done(player, qid):
            continue
        if any(k == "*" or k.lower() in name for k in st.get("kill", [])):
            st["progress"] = st.get("progress", 0) + 1
            if st["progress"] >= st.get("count", 1):
                _flags(player)[f"comp_quest_done_{qid}"] = True
                who = COMPANION_DEFS.get(st.get("cid"), {}).get("name", "your recruit")
                print(C(f"{_GOLD}✔ Recruit quest complete!{_R} {_DIM}Go back and see {who}.{_R}"))
            else:
                print(C(f"{_DIM}Recruit quest: {st['progress']}/{st['count']}{_R}"))


# ═══════════════════════════════════════════════════════════════
# Sprites
# ═══════════════════════════════════════════════════════════════

def row_of_sprites(specs, gap=4, width=None, raw=False):
    """Render several sprites side by side, feet aligned, labels underneath.
    specs: list of dicts {sprite, accent, legendary, label, sub}. Wraps onto
    more rows when the terminal is too narrow. Returns centred lines."""
    try:
        from game_art import render_sprite
    except Exception:
        return []
    width = width or W()
    blocks = []
    for s in specs:
        try:
            art = render_sprite(s.get("sprite", "Swordsman"), s.get("accent"), s.get("legendary", False))
        except Exception:
            art = []
        aw = max([_vis(a) for a in art] or [0])
        labels = [s.get("label", ""), s.get("sub", "")]
        w = max([aw] + [_vis(x) for x in labels])
        blocks.append((art, aw, w, labels))
    rows, cur, curw = [], [], 0
    for b in blocks:
        need = b[2] + (gap if cur else 0)
        if cur and curw + need > width - 2:
            rows.append(cur); cur, curw = [], 0
            need = b[2]
        cur.append(b); curw += need
    if cur:
        rows.append(cur)
    out = []
    for row in rows:
        h = max(len(b[0]) for b in row)
        for i in range(h):
            parts = []
            for art, aw, w, _ in row:
                off = i - (h - len(art))
                cell = art[off] if 0 <= off < len(art) else ""
                left = (w - aw) // 2
                parts.append(" " * left + cell + " " * max(0, w - left - _vis(cell)))
            out.append((" " * gap).join(parts))
        for li in range(2):
            parts = []
            for art, aw, w, labels in row:
                t = labels[li]
                left = (w - _vis(t)) // 2
                parts.append(" " * left + t + " " * max(0, w - left - _vis(t)))
            if any(b[3][li] for b in row):
                out.append((" " * gap).join(parts))
    return out if raw else [C(ln) for ln in out]


def _two_col(left, right, gap=3):
    """Print two blocks side by side (left lines padded to equal width)."""
    lw = max([_vis(x) for x in left] or [0])
    for i in range(max(len(left), len(right))):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        print(C(l + " " * (lw - _vis(l) + gap) + r))


def _opts(opts, width=None):
    """Print [K] option chips, wrapping to the content width."""
    width = (width or min(W(), 120)) - 4
    line, out = "", []
    for k, lbl in opts:
        chip = f"{_GOLD}[{k}]{_R} {lbl}"
        if line and _vis(line) + 3 + _vis(chip) > width:
            out.append(line); line = chip
        else:
            line = (line + "   " + chip) if line else chip
    if line:
        out.append(line)
    for ln in out:
        print(C(ln))


def _spec_for(c, sub=None):
    return dict(sprite=c.sprite, accent=c.accent, legendary=c.crown,
                label=f"{c._col()}{c.marker}{_R} {_B}{c.name}{_R}" + (f"{_GOLD}✦{_R}" if c.starborn else ""),
                sub=sub if sub is not None else f"{role_col(c.role)}{c.role.title()}{_R} {_DIM}Lv{c.level}{_R}")


def _def_spec(d, starborn=False, sub=""):
    acc = STARBORN_ACCENT if starborn else d.get("accent")
    return dict(sprite=d.get("sprite", "Swordsman"), accent=acc,
                legendary=starborn or d.get("rarity") == "legendary",
                label=f"{_B}{d['name']}{_R}" + (f"{_GOLD}✦{_R}" if starborn else ""), sub=sub)


# ═══════════════════════════════════════════════════════════════
# Recruiting
# ═══════════════════════════════════════════════════════════════

def _party(player):
    p = getattr(player, "party", None)
    if not isinstance(p, Party):
        p = Party()
        try:
            player.party = p
        except Exception:
            pass
    return p


def _conditions(player, d, cost, waive=False):
    """[(label, ok, kind)] for a companion's recruit conditions."""
    rec = d.get("recruit", {})
    out = []
    if waive:
        return out
    lvl = rec.get("min_level")
    if lvl:
        out.append((f"Reach level {lvl}", getattr(player, "level", 1) >= lvl, "level"))
    if rec.get("flag"):
        out.append((rec.get("flag_text") or f"Requires: {rec['flag'].replace('_', ' ')}",
                    bool(_flags(player).get(rec["flag"])), "flag"))
    if rec.get("companion"):
        other = COMPANION_DEFS.get(rec["companion"], {}).get("name", rec["companion"])
        out.append((f"{other} travels with you", _party(player).has(rec["companion"]), "companion"))
    if rec.get("item"):
        nm, qty = rec["item"][0], int(rec["item"][1])
        have = _count_item(player, nm)
        out.append((f"Bring {qty}x {nm} (have {have})", have >= qty, "item"))
    if rec.get("quest"):
        q = rec["quest"]
        st = _quests(player).get(q["id"])
        done = _quest_done(player, q["id"])
        prog = f" ({st['progress']}/{st['count']})" if st and not done else ""
        out.append((q.get("desc", "Finish their task") + prog, done, "quest"))
    if rec.get("duel"):
        out.append(("Win a duel against them", bool(_flags(player).get(f"duel_won_{d['id']}")), "duel"))
    if cost:
        out.append((f"Pay {cost}g (have {getattr(player, 'gold', 0)}g)", getattr(player, "gold", 0) >= cost, "gold"))
    return out


def _offer_cost(player, d, cost):
    if cost is not None:
        try:
            return max(0, int(cost))
        except Exception:
            return 0
    c = hire_cost(d["id"], getattr(player, "level", 1), player)
    if d["id"] in _party(player).departed:
        c = max(c, 50) * 2
    return c


def offer_recruit(player, companion_id, scene=None, cost=None, reason=None, starborn=None):
    """Offer companion `companion_id` to the player: dialogue, conditions,
    duel / quest / payment, then recruit (to the party, or the bench when
    full). Works from a walkable Scene (pass scene=) or a plain menu.
    cost overrides the gold price (0 = free). Returns True if recruited."""
    if companion_id not in COMPANION_DEFS:
        return False
    try:
        if scene is not None and hasattr(scene, "modal"):
            return bool(scene.modal(_offer_screen, player, companion_id, cost, reason, starborn))
        return bool(_offer_screen(player, companion_id, cost, reason, starborn))
    except Exception as e:
        try:
            import os
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
                f.write(f"offer_recruit {companion_id}: {e!r}\n")
        except Exception:
            pass
        return False


def _offer_screen(player, cid, cost=None, reason=None, starborn=None):
    d = COMPANION_DEFS[cid]
    party = _party(player)
    day = current_day(player)
    if d["spawn"].get("type") == "story":
        reason = reason or "story"
    waive = reason in ("prisoner", "story")
    if starborn is None:
        starborn = is_starborn(getattr(player, "name", "hero"), cid, day)
    msg = ""
    while True:
        existing = party.find(cid)
        price = _offer_cost(player, d, cost)
        conds = _conditions(player, d, price, waive=waive)
        clr()
        rc = rarity_col(d["rarity"])
        print(C(f"\n{rc}{_B}══════  {d['name'].upper()}  ══════{_R}"))
        print(C(f"{_DIM}{d['title']}{_R}   {rarity_tag(d['rarity'])}   "
                f"{role_col(d['role'])}{d['role'].title()}{_R}"
                + (f"   {_GOLD}{_B}✦ STARBORN ✦{_R}" if starborn else "")))
        print()
        dl = d.get("dialogue", {})
        greet = (dl.get("hire") or dl.get("idle") or ["..."])
        greet = greet[-1] if (_quest_done(player, d["recruit"].get("quest", {}).get("id", "-"))
                              or _flags(player).get(f"duel_won_{cid}")) else greet[0]
        info = [f"{_DIM}{ln}{_R}" for ln in _wrap(d.get("bio", ""), 52)] + [""]
        info += [f"{_WHITE}{ln}{_R}" for ln in _wrap(f'"{greet}"', 52)] + [""]
        pas = PASSIVES.get(d.get("passive_id"), {})
        info.append(f"{_CYAN}Passive{_R} {_YELL}{pas.get('name', '—')}{_R}")
        info += [f"{_DIM}{ln}{_R}" for ln in _wrap(pas.get("desc", ""), 52)]
        tr = ", ".join(TRAITS[t]["name"] for t in d.get("traits", []) if t in TRAITS)
        info.append(f"{_CYAN}Traits{_R} {_DIM}{tr or '—'}{_R}" + (f" {_GOLD}+1 Starborn trait{_R}" if starborn else ""))
        _two_col(row_of_sprites([_def_spec(d, starborn)], width=40, raw=True), info)
        if existing is not None:
            where = "in your party" if existing in party.members else "on your bench"
            print(C(f"\n{_GREEN}{d['name']} already travels with you ({where}).{_R}"))
            if existing in party.bench and len(party.members) < MAX_PARTY:
                if _yes("Bring them into the active party?"):
                    ok, m = party.activate(cid)
                    print(C(f"{_GREEN if ok else _RED}{m}{_R}"))
            _pause()
            return False
        if cid in party.departed:
            print(C(f"{_ORAN}They remember how you parted. The price is doubled.{_R}"))
        print(C(f"\n{_GOLD}{_B}To recruit:{_R}"))
        if not conds:
            print(C(f"  {_GREEN}✓ Free — they are ready to join.{_R}"))
        for label, ok, kind in conds:
            print(C(f"  {_GREEN + '✓' if ok else _RED + '✗'}{_R} {label}"))
        if len(party.members) >= MAX_PARTY:
            print(C(f"  {_DIM}(Party full — they will wait on your bench){_R}"))
        all_ok = all(ok for _, ok, _ in conds)
        opts = []
        if all_ok:
            opts.append(("Y", f"Recruit {d['name']}" + (f" for {price}g" if price else "")))
        kinds = {k: ok for _, ok, k in conds}
        if "duel" in kinds and not kinds["duel"]:
            opts.append(("D", "Challenge to a duel"))
        q = d["recruit"].get("quest")
        if q and not _quest_done(player, q["id"]) and q["id"] not in _quests(player):
            opts.append(("Q", "Accept their task"))
        opts.append(("T", "Chat"))
        opts.append(("0", "Leave"))
        print()
        _opts(opts)
        if msg:
            print(C(msg)); msg = ""
        ch = _ask(">").lower()
        if ch in ("0", "", "x", "n") or (ch == "q" and not q):
            return False
        if ch == "t":
            msg = f"{_WHITE}{d['name']}: \"{random.choice(dl.get('idle') or ['...'])}\"{_R}"
        elif ch == "q" and q:
            _start_quest(player, cid, q)
            msg = f"{_GOLD}Task accepted:{_R} {q.get('desc', '')}"
        elif ch == "d" and "duel" in kinds:
            if _flags(player).get(f"duel_lost_day_{cid}") == day:
                msg = f"{_DIM}\"Rest first. Come back tomorrow.\"{_R}"
                continue
            won = _duel(player, d)
            if won:
                _flags(player)[f"duel_won_{cid}"] = True
                msg = f"{_GOLD}{_B}You win the duel!{_R} {_DIM}\"Well fought.\"{_R}"
            else:
                _flags(player)[f"duel_lost_day_{cid}"] = day
                msg = f"{_RED}You lose the duel.{_R} {_DIM}Try again another day.{_R}"
        elif ch == "y" and all_ok:
            if price and player.gold < price:
                msg = f"{_RED}Not enough gold.{_R}"
                continue
            rec = d.get("recruit", {})
            if rec.get("item") and not waive:
                nm, qty = rec["item"][0], int(rec["item"][1])
                if _remove_item(player, nm, qty) < qty:
                    msg = f"{_RED}You don't have the {nm}.{_R}"
                    continue
            if price:
                player.gold -= price
            c = Companion(d, getattr(player, "level", 1), starborn=starborn)
            c.joined_day = day
            if cid in party.departed:
                c.affinity = -10
            if reason == "story":
                c.affinity = 40
            ok, m = party.add(c)
            party.refresh(player)
            print(C(f"\n{_GREEN}{_B}{m}{_R}"))
            if starborn:
                print(C(f"{_GOLD}✦ A Starborn! Touched by a falling star — rarer than 1 in 500. ✦{_R}"))
            print(C(f"{c.tag()}: {_WHITE}\"{c.line('hire')}\"{_R}"))
            _pause()
            return ok


def _duel(player, d):
    """Practice-blade duel: first to lose half their HP yields. No real HP or
    items are lost. Returns True if the player wins."""
    opp = Companion(d, max(getattr(player, "level", 1), d.get("recruit", {}).get("min_level", 1)))
    mult = 1.0 + 0.15 * RARITY_ORDER.index(d.get("rarity", "common"))
    o_pool = int(opp.max_hp * 0.5 * mult) + 10
    p_pool = max(10, int(player.max_hp * 0.5))
    o_atk = int(opp.atk * (1.1 + 0.1 * RARITY_ORDER.index(d.get("rarity", "common"))))
    o_max, p_max = o_pool, p_pool
    log = [f"{_DIM}Practice blades. First to yield loses.{_R}"]
    guard = False
    rnd = 0
    try:
        p_atk = player.combat_atk()
    except Exception:
        p_atk = getattr(player, "atk", 10)
    try:
        p_def = player.combat_def()
    except Exception:
        p_def = getattr(player, "defense", 5)
    while o_pool > 0 and p_pool > 0:
        rnd += 1
        clr()
        print(C(f"\n{_GOLD}{_B}⚔  DUEL — {getattr(player, 'name', 'You')} vs {d['name']}  ⚔{_R}\n"))
        for ln in row_of_sprites([dict(sprite=getattr(getattr(player, "job", None), "name", "Swordsman"),
                                       label=f"{_B}{getattr(player, 'name', 'You')}{_R}",
                                       sub=_bar(p_pool, p_max, 14)),
                                  dict(_def_spec(d), sub=_bar(o_pool, o_max, 14))], gap=10):
            print(ln)
        print()
        for ln in log[-5:]:
            print(C(ln))
        print(C(f"\n{_GOLD}[1]{_R} Strike   {_GOLD}[2]{_R} Feint (risky, big crit)   "
                f"{_GOLD}[3]{_R} Guard   {_GOLD}[4]{_R} Yield"))
        ch = _ask(f"Round {rnd} >")
        if ch == "4" or ch == "0":
            log.append(f"{_DIM}You yield.{_R}")
            p_pool = 0
            break
        guard = ch == "3"
        if ch in ("1", "2"):
            if ch == "2" and random.randint(1, 100) <= 40:
                log.append(f"{_DIM}Your feint is read — you hit nothing.{_R}")
            else:
                base = max(1, p_atk + random.randint(-2, 3) - opp.defense // 3)
                crit = random.randint(1, 100) <= (45 if ch == "2" else 12)
                dmg = int(base * (2.0 if crit and ch == "2" else 1.5 if crit else 1.0))
                if random.randint(1, 100) <= opp.dodge_chance():
                    log.append(f"{_DIM}{d['name']} sidesteps your blow.{_R}")
                else:
                    o_pool -= dmg
                    log.append(f"{_WHITE}You strike{(' ' + _ORAN + 'CRIT' + _R) if crit else ''} → {dmg}{_R}")
        elif guard:
            log.append(f"{_CYAN}You raise your guard.{_R}")
        if o_pool <= 0:
            break
        dmg = max(1, o_atk + random.randint(-2, 3) - p_def // 3)
        if random.randint(1, 100) <= 15:
            dmg = int(dmg * 1.5)
        if guard:
            dmg = max(1, dmg // 3)
        p_pool -= dmg
        log.append(f"{_RED}{d['name']} strikes → {dmg}{_R}")
    won = o_pool <= 0 and p_pool > 0
    clr()
    print(C(f"\n{_GOLD if won else _RED}{_B}{'VICTORY' if won else 'DEFEAT'} — the duel is over.{_R}"))
    _pause()
    return won


def recruit_board(player, town_name):
    """The tavern board: who is drinking here today."""
    while True:
        day = current_day(player)
        ids = tavern_recruits(town_name, day, player)
        clr()
        print(C(f"\n{_GOLD}{_B}🍺  TAVERN — {town_name}  {_R}{_DIM}(day {day + 1}){_R}"))
        party = _party(player)
        print(C(f"{_DIM}Party {len(party.members)}/{MAX_PARTY} · Roster {len(party.roster)} · "
                f"Gold {_GOLD}{player.gold}g{_R}\n"))
        if not ids:
            print(C(f"{_DIM}Nobody here is looking for work today. Travellers come and go — try another day.{_R}"))
            _pause()
            return
        specs = []
        for cid in ids:
            d = COMPANION_DEFS[cid]
            specs.append(_def_spec(d, is_starborn(player.name, cid, day),
                                   sub=f"{rarity_col(d['rarity'])}{RARITIES[d['rarity']]['label']}{_R}"))
        for ln in row_of_sprites(specs):
            print(ln)
        print()
        for i, cid in enumerate(ids, 1):
            d = COMPANION_DEFS[cid]
            price = _offer_cost(player, d, None)
            cond = _conditions(player, d, price)
            ready = all(ok for _, ok, _ in cond)
            extra = "" if d["spawn"].get("type") == "tavern" else f" {_CYAN}(travelling — gone tomorrow?){_R}"
            print(C(f"{_GOLD}[{i}]{_R} {rarity_col(d['rarity'])}{_B}{d['name']}{_R} {_DIM}— {d['title']}{_R}  "
                    f"{role_col(d['role'])}{d['role'].title()}{_R}  "
                    f"{(_GOLD + str(price) + 'g' + _R) if price else _DIM + 'no fee' + _R}  "
                    f"{_GREEN + 'ready' if ready else _ORAN + 'conditions'}{_R}{extra}"))
        print(C(f"\n{_GOLD}[#]{_R} Talk to someone   {_GOLD}[0]{_R} Back"))
        ch = _ask(">")
        if ch in ("0", "", "q"):
            return
        if ch.isdigit() and 1 <= int(ch) <= len(ids):
            offer_recruit(player, ids[int(ch) - 1])


# ═══════════════════════════════════════════════════════════════
# Recruit events (world map, dungeons, ruins, after battles)
# ═══════════════════════════════════════════════════════════════

def _available(player, cid):
    party = _party(player)
    return cid in COMPANION_DEFS and not party.has(cid)


def _event_card(title, d, text, starborn=False):
    clr()
    print(C(f"\n{_GOLD}{_B}{title}{_R}\n"))
    for ln in row_of_sprites([_def_spec(d, starborn, sub=rarity_tag(d["rarity"]))]):
        print(ln)
    print()
    for ln in _wrap(text, 66):
        print(C(f"{_WHITE}{ln}{_R}"))


def wandering_recruit_event(player, continent_id):
    """A rare companion met on the road. Returns True if one was met."""
    lvl = getattr(player, "level", 1)
    pool = []
    for cid, d in COMPANION_DEFS.items():
        sp = d["spawn"]
        conts = sp.get("continents") or sp.get("wander") or []
        if sp.get("type") == "wander" or (sp.get("type") == "special" and sp.get("wander")):
            if continent_id in conts and lvl >= sp.get("min_level", 1) and _available(player, cid):
                pool.append(cid)
    if not pool:
        return False
    cid = random.choice(pool)
    d = COMPANION_DEFS[cid]
    star = random.randint(1, 512) == 1
    _event_card("A TRAVELLER ON THE ROAD", d,
                f"A lone figure blocks the road ahead — {d['name']}, {d['title']}. "
                f"\"{(d['dialogue'].get('hire') or ['Well met.'])[0]}\"", star)
    if _yes("\nTalk to them?"):
        offer_recruit(player, cid, reason="wander", starborn=star)
    return True


def dungeon_prisoner_event(player, dungeon_name, danger=None):
    """After a boss clear: a prisoner may be found in a cell. Returns True if
    a prisoner was found (whether or not they joined)."""
    f = _flags(player)
    key = f"prisoner_checked_{dungeon_name}"
    if f.get(key):
        return False
    f[key] = True
    if danger is None:
        danger = 2
        try:
            from game_world import CONTINENTS, CONTINENT_DANGER
            for cont in CONTINENTS:
                if dungeon_name in cont.get("dungeons", []):
                    danger = CONTINENT_DANGER.get(cont["id"], 2)
            if "Vaeltharion" in str(dungeon_name):
                danger = 5
        except Exception:
            pass
    pool = []
    for cid, d in COMPANION_DEFS.items():
        sp = d["spawn"]
        if sp.get("type") == "prisoner" and _available(player, cid):
            if (danger or 2) >= sp.get("min_danger", 0) or getattr(player, "level", 1) >= 15:
                pool.append(cid)
    if not pool or random.randint(1, 100) > 65:
        return False
    cid = random.choice(pool)
    d = COMPANION_DEFS[cid]
    star = random.randint(1, 512) == 1
    _event_card("A PRISONER IN THE DEPTHS", d,
                f"Behind the fallen guardian you find a locked cell. Inside, chained and starving: "
                f"{d['name']}, {d['title']}. You break the lock.", star)
    offer_recruit(player, cid, cost=0, reason="prisoner", starborn=star)
    return True


def ruins_stranger_event(player, place_name=""):
    """A mysterious stranger among the ruins. Returns True if met."""
    pool = [cid for cid, d in COMPANION_DEFS.items()
            if d["spawn"].get("type") == "ruins" and _available(player, cid)]
    if not pool:
        return False
    cid = random.choice(pool)
    d = COMPANION_DEFS[cid]
    star = random.randint(1, 512) == 1
    _event_card("A STRANGER IN THE RUINS", d,
                f"Among the broken stones{(' of ' + place_name) if place_name else ''} someone is watching you: "
                f"{d['name']}, {d['title']}.", star)
    if _yes("\nApproach?"):
        offer_recruit(player, cid, reason="ruins", starborn=star)
    return True


def post_battle_recruit_chance(player, enemy):
    """Low chance that a beaten (non-boss) enemy asks to join. Returns True if
    the offer was made."""
    if getattr(enemy, "enemy_class", "") == "BOSS":
        return False
    name = str(getattr(enemy, "name", ""))
    pool = []
    for cid, d in COMPANION_DEFS.items():
        sp = d["spawn"]
        if sp.get("type") == "defeated" and _available(player, cid):
            if any(e.lower() == name.lower() for e in sp.get("enemies", [])):
                pool.append(cid)
    if not pool:
        return False
    chance = 4 + (2 if _clan_has(player, "Clan Banner") else 0)
    if random.randint(1, 100) > chance:
        return False
    cid = random.choice(pool)
    d = COMPANION_DEFS[cid]
    print(C(f"\n{_GOLD}{_B}The defeated {name} raises a hand — it wants to join you!{_R}"))
    print(C(f"{_WHITE}{d['name']}: \"{(d['dialogue'].get('hire') or ['...'])[0]}\"{_R}"))
    if _yes("Hear them out?"):
        offer_recruit(player, cid, reason="defeated", starborn=random.randint(1, 512) == 1)
    return True


def try_world_companion_event(player, event_type="ruins_event"):
    """Ruins exploration: a companion finds something — or, now and then, a
    stranger is waiting among the stones."""
    party = _party(player)
    if event_type == "ruins_event" and (not party.alive_members() or random.randint(1, 100) <= 25):
        if ruins_stranger_event(player):
            return
    if not party.alive_members():
        return
    companion = random.choice(party.alive_members())
    roll = random.random()
    if roll < 0.35:
        try:
            from game_items import ITEM_POOL
            item = random.choice(list(ITEM_POOL.values()))()
            if player.add_item(item):
                print(C(f"{companion.tag()} {_WHITE}searches the ruins and finds {item.name}!{_R}"))
        except Exception:
            pass
    elif roll < 0.65:
        gold = random.randint(15, 60)
        player.gold += gold
        print(C(f"{companion.tag()} {_WHITE}spots a hidden cache — {gold} gold!{_R}"))
    elif roll < 0.85:
        heal = random.randint(10, 30)
        player.hp = min(player.max_hp, player.hp + heal)
        print(C(f"{companion.tag()} {_GREEN}tends your wounds — +{heal} HP.{_R}"))
    else:
        print(C(f"{companion.tag()}: {_DIM}\"{companion.line('idle')}\"{_R}"))
        companion.change_affinity(1)


# ═══════════════════════════════════════════════════════════════
# Party UI
# ═══════════════════════════════════════════════════════════════

def _comp_row(i, c, prefix=""):
    tier, tcol = c.loyalty_tier()
    return (f"{_GOLD}[{prefix}{i}]{_R} {c.tag()} {_DIM}{c.title}{_R}  {role_col(c.role)}{c.role.title()}{_R} "
            f"{_DIM}Lv{c.level}{_R}  HP {c.hp_bar(10)}  {tcol}{tier}{_R}")


def recruit_menu(player, town_name=""):
    """Party & clan hub. With a town name it has the tavern board and lets you
    swap companions with the bench; from the world map ([N]) it is a party
    screen only (recruiting happens in taverns and out in the world)."""
    party = _party(player)
    in_town = bool(town_name)
    try:
        if party.react_to_world(player) or party._check_departures(player):
            _pause()
    except Exception:
        pass
    while True:
        party.refresh(player)
        clr()
        print(C(f"\n{_GOLD}{_B}══════════  PARTY · ROSTER · CLAN  ══════════{_R}"))
        if party.members:
            print()
            for ln in row_of_sprites([_spec_for(c) for c in party.members]):
                print(ln)
            print()
            for i, c in enumerate(party.members, 1):
                print(C(_comp_row(i, c)))
        else:
            print(C(f"\n{_DIM}No companions travel with you.{_R}"))
        if party.bench:
            names = ", ".join(f"{c._col()}{c.name}{_R}" for c in party.bench)
            print(C(f"\n{_DIM}Bench ({len(party.bench)}):{_R} {names}"))
        clan = getattr(player, "owned_clan", None)
        if clan:
            print(C(f"\n{_GOLD}Clan {clan.name}{_R}  {_DIM}Rank{_R} {_CYAN}{clan.rank}{_R}  "
                    f"{_DIM}Income{_R} {_GOLD}+{clan.passive_income}g/day{_R}"))
        print(C(f"\n{_DIM}{'─' * 44}{_R}"))
        opts = []
        if in_town:
            opts.append(("R", "Tavern board"))
        opts += [("P", "Manage party & bench"), ("C", "Customise companions"), ("K", "Clan"), ("0", "Back")]
        _opts(opts)
        if not in_town:
            for ln in _wrap("Recruit in town taverns. Rarer companions wander the roads, sit in the cells "
                            "of conquered dungeons, lurk in ruins - and beaten foes sometimes ask to join.", 90):
                print(C(f"{_DIM}{ln}{_R}"))
        ch = _ask(">").lower()
        if ch in ("0", "", "q"):
            return
        if ch == "r" and in_town:
            recruit_board(player, town_name)
        elif ch == "p":
            party_menu(player, can_swap=in_town)
        elif ch == "c":
            customise_menu(player)
        elif ch == "k":
            _clan_menu(player, can_swap=in_town)


def party_menu(player, can_swap=False):
    """Inspect, talk, gift, equip, bench / recall, release."""
    party = _party(player)
    msg = ""
    while True:
        party.refresh(player)
        clr()
        print(C(f"\n{_CYAN}{_B}════  PARTY & BENCH  ════{_R}\n"))
        allc = party.roster
        if not allc:
            print(C(f"{_DIM}You have no companions yet.{_R}"))
            _pause()
            return
        for i, c in enumerate(allc, 1):
            if i == 1 and party.members:
                print(C(f"{_GREEN}Active{_R}"))
            if i == len(party.members) + 1:
                print(C(f"\n{_DIM}Bench{_R}"))
            print(C(_comp_row(i, c)))
        print(C(f"\n{_GOLD}[#]{_R} Open companion   {_GOLD}[0]{_R} Back"
                + ("" if can_swap else f"   {_DIM}(recall benched companions in a town, base or clan hall){_R}")))
        if msg:
            print(C(msg)); msg = ""
        ch = _ask(">").lower()
        if ch in ("0", "", "q"):
            return
        if ch.isdigit() and 1 <= int(ch) <= len(allc):
            msg = _companion_screen(player, allc[int(ch) - 1], can_swap) or ""


def _detail_lines(c):
    tier, tcol = c.loyalty_tier()
    out = [
        f"{c.tag()} {_DIM}— {c.title}{_R}",
        f"{rarity_tag(c.rarity)}  {role_col(c.role)}{c.role.title()}{_R}  {_DIM}Lv{_R} {c.level}  "
        f"{_DIM}XP{_R} {c.xp}/{c.xp_to_next}",
        f"HP {c.hp_bar(12)}   MP {_bar(c.mp, c.max_mp, 8, _BLUE)} {_DIM}{c.mp}/{c.max_mp}{_R}",
        f"{_DIM}ATK{_R} {c.atk}  {_DIM}DEF{_R} {c.defense}  {_DIM}Crit{_R} {c.crit_chance()}%  "
        f"{_DIM}Dodge{_R} {c.dodge_chance()}%" + (f"  {_DIM}Heal{_R} {c.heal_power}" if c.role == "healer" else ""),
        f"{_DIM}Loyalty{_R} {tcol}{tier} ({c.affinity:+d}){_R}  {_DIM}Battles{_R} {c.battles}",
        "",
        f"{_CYAN}Passive{_R} {_DIM}{c.passive}{_R}",
    ]
    sk = ROLE_SKILL[c.role]
    out.append(f"{_CYAN}Skill{_R} {_DIM}{c.d.get('skill_name') or sk['name']} (every 3rd round){_R}")
    sig = c.d.get("signature", {})
    out.append(f"{_CYAN}Signature{_R} " + (f"{_YELL}{sig.get('name')}{_R} {_DIM}— {SIGNATURE_EFFECTS.get(sig.get('effect'), '')}{_R}"
                                          if c.loyal else f"{_DIM}locked until Loyal ({LOYAL_AT}){_R}"))
    out.append(f"{_CYAN}Traits{_R} " + ", ".join(f"{_GOLD if t == 'starborn' else _WHITE}{TRAITS[t]['name']}{_R}"
                                                  for t in c.traits if t in TRAITS))
    likes = ", ".join(c.d.get("likes", [])) or "—"
    dislikes = ", ".join(c.d.get("dislikes", [])) or "—"
    out.append(f"{_GREEN}Likes{_R} {_DIM}{likes}{_R}   {_RED}Dislikes{_R} {_DIM}{dislikes}{_R}")
    for gs in ("weapon", "armor", "trinket"):
        it = c.gear.get(gs)
        out.append(f"{_DIM}{gs.title():<8}{_R}" + (f"{_WHITE}{it.name}{_R} {_DIM}{it.stat_line()}{_R}" if it else f"{_DIM}—{_R}"))
    return out


def _companion_screen(player, c, can_swap):
    party = _party(player)
    msg = ""
    while True:
        party.refresh(player)
        if not party.has(c.id):
            return ""
        clr()
        active = c in party.members
        print(C(f"\n{_CYAN}{_B}════  {c.name.upper()}  ════{_R}  {_DIM}({'active' if active else 'bench'}){_R}\n"))
        _two_col(row_of_sprites([_spec_for(c)], width=40, raw=True), _detail_lines(c))
        print()
        for ln in _wrap(c.d.get("bio", ""), 90):
            print(C(f"{_DIM}{ln}{_R}"))
        opts = [("T", "Talk"), ("G", "Give a gift"), ("E", "Equipment"), ("C", "Customise")]
        if active:
            opts.append(("B", "Send to bench"))
        elif can_swap:
            opts.append(("A", "Bring into party"))
        opts += [("X", "Part ways"), ("0", "Back")]
        print()
        _opts(opts)
        if msg:
            print(C(msg)); msg = ""
        ch = _ask(">").lower()
        if ch in ("0", "", "q"):
            return ""
        if ch == "t":
            msg = _talk(player, c)
        elif ch == "g":
            msg = _gift(player, c)
        elif ch == "e":
            _gear_menu(player, c)
        elif ch == "c":
            _customise_one(player, c)
        elif ch == "b" and active:
            if _yes(f"Send {c.name} to wait on the bench? (They'll be a little hurt.)"):
                ok, m = party.bench_member(party.members.index(c))
                msg = f"{_GREEN if ok else _RED}{m}{_R}"
        elif ch == "a" and not active and can_swap:
            ok, m = party.activate(c.id)
            msg = f"{_GREEN if ok else _RED}{m}{_R}"
        elif ch == "x":
            print(C(f"{_RED}{c.name} will go home. Their gear returns to your bag.{_R}"))
            if _yes("Really part ways?") and _ask(f"Type {_B}{c.name[:12]}{_R}{_GOLD} to confirm >") .lower() == c.name[:12].lower():
                for gs in list(c.gear):
                    it = c.unequip(gs)
                    if it is not None and not player.add_item(it):
                        try:
                            player.guild_storage.items.append(it)
                        except Exception:
                            pass
                party.release(c.id)
                return f"{_DIM}{c.name} says goodbye: \"{c.line('leave')}\"{_R}"
            msg = f"{_DIM}Never mind.{_R}"


TALK_CHOICES = [
    ("1", "Offer sympathy", "kindness"),
    ("2", "Crack a joke", "humour"),
    ("3", "Give honest advice", "honesty"),
]


def _talk(player, c):
    day = current_day(player)
    clr()
    print(C(f"\n{c.tag()}: {_WHITE}\"{c.line('idle')}\"{_R}\n"))
    if c.flags.get("talk_day") == day:
        _pause()
        return f"{_DIM}You've already had a heart-to-heart today.{_R}"
    for ln in _wrap(c.d.get("bio", ""), 64):
        print(C(f"{_DIM}{ln}{_R}"))
    print()
    for k, lbl, _ in TALK_CHOICES:
        print(C(f"{_GOLD}[{k}]{_R} {lbl}"))
    print(C(f"{_GOLD}[0]{_R} Just nod"))
    ch = _ask(">")
    for k, lbl, topic in TALK_CHOICES:
        if ch == k:
            c.flags["talk_day"] = day
            r = c.reaction(topic)
            delta = 4 if r > 0 else -3 if r < 0 else 1
            got = c.change_affinity(delta)
            mood = (f"{_GREEN}{c.name} appreciates that ({got:+d}).{_R}" if r > 0 else
                    f"{_ORAN}{c.name} doesn't like that ({got:+d}).{_R}" if r < 0 else
                    f"{_DIM}{c.name} nods ({got:+d}).{_R}")
            return mood
    return ""


def _gift_score(c, item):
    gifts = c.d.get("gifts", [])
    name = getattr(item, "name", "")
    itype = getattr(item, "item_type", "")
    if name in gifts:
        return 8
    if f"type:{itype}" in gifts:
        return 5
    return 2


def _gift(player, c):
    day = current_day(player)
    if c.flags.get("gift_day") == day:
        return f"{_DIM}{c.name} has already accepted a gift today.{_R}"
    inv = list(getattr(player, "inventory", []) or [])
    clr()
    print(C(f"\n{_CYAN}{_B}Give {c.name} a gift{_R}  {_DIM}(one per day){_R}\n"))
    print(C(f"{_GOLD}[$]{_R} Gold (25g × level)" + ("  " + _GREEN + "loves gold" + _R if c.reaction("gold") > 0 else "")))
    for i, e in enumerate(inv, 1):
        qty = getattr(e, "qty", 1)
        star = f" {_GREEN}♥{_R}" if _gift_score(c, getattr(e, "item", e)) >= 5 else ""
        print(C(f"{_GOLD}[{i}]{_R} {e.name}{(' x' + str(qty)) if qty > 1 else ''}{star}"))
    print(C(f"{_GOLD}[0]{_R} Back"))
    ch = _ask(">")
    if ch == "$":
        cost = 25 * c.level
        if player.gold < cost:
            return f"{_RED}You need {cost}g.{_R}"
        player.gold -= cost
        r = c.reaction("gold")
        got = c.change_affinity(8 if r > 0 else -2 if r < 0 else 3)
        c.flags["gift_day"] = day
        return f"{_GOLD}You give {c.name} {cost}g ({got:+d} affinity).{_R}"
    if ch.isdigit() and 1 <= int(ch) <= len(inv):
        e = inv[int(ch) - 1]
        item = getattr(e, "item", e)
        sc = _gift_score(c, item)
        if _remove_item(player, e.name, 1) < 1:
            try:
                player.inventory.remove(e)
            except Exception:
                return f"{_RED}Couldn't hand that over.{_R}"
        got = c.change_affinity(sc)
        c.flags["gift_day"] = day
        return (f"{_GREEN}{c.name} loves the {item.name}! ({got:+d}){_R}" if sc >= 5
                else f"{_DIM}{c.name} accepts the {item.name} politely ({got:+d}).{_R}")
    return ""


def _gear_menu(player, c):
    msg = ""
    while True:
        clr()
        print(C(f"\n{_CYAN}{_B}════  {c.name.upper()}'S GEAR  ════{_R}\n"))
        for gs in ("weapon", "armor", "trinket"):
            it = c.gear.get(gs)
            fits = ", ".join(GEAR_SLOTS[gs])
            print(C(f"{_DIM}{gs.title():<8}{_R} " + (f"{_WHITE}{it.name}{_R} {_DIM}{it.stat_line()}{_R}" if it
                                                     else f"{_DIM}— ({fits}){_R}")))
        print(C(f"\n{_DIM}ATK {c.atk}  DEF {c.defense}  HP {c.max_hp}  MP {c.max_mp}{_R}\n"))
        inv = list(getattr(player, "inventory", []) or [])
        wearable = [(i, e) for i, e in enumerate(inv) if c.can_wear(getattr(e, "item", e))[0]]
        for n, (i, e) in enumerate(wearable, 1):
            it = getattr(e, "item", e)
            print(C(f"{_GOLD}[{n}]{_R} {_WHITE}{it.name}{_R} {_DIM}({c.gear_slot_for(it)}) {it.stat_line()}{_R}"))
        if not wearable:
            print(C(f"{_DIM}Nothing in your bag that {c.name} can use ({c.role} gear).{_R}"))
        print(C(f"\n{_GOLD}[#]{_R} Equip   {_GOLD}[U]{_R} Unequip a slot   {_GOLD}[0]{_R} Back"))
        if msg:
            print(C(msg)); msg = ""
        ch = _ask(">").lower()
        if ch in ("0", "", "q"):
            return
        if ch == "u":
            s = _ask("Slot (weapon/armor/trinket) >").lower()
            if s in c.gear and c.gear[s] is not None:
                it = c.unequip(s)
                if not player.add_item(it):
                    c.gear[s] = it
                    c.recalc()
                    msg = f"{_RED}Your bag is full.{_R}"
                else:
                    msg = f"{_GREEN}Took back {it.name}.{_R}"
            continue
        if ch.isdigit() and 1 <= int(ch) <= len(wearable):
            i, e = wearable[int(ch) - 1]
            it = getattr(e, "item", e)
            ok, m, old = c.equip(it)
            if ok:
                try:
                    player.inventory.remove(e)
                except ValueError:
                    pass
                if old is not None and not player.add_item(old):
                    c.gear[c.gear_slot_for(it)] = old
                    player.add_item(it)
                    c.recalc()
                    m = f"Bag full — couldn't swap out {old.name}."
                    ok = False
                if ok and c.reaction("battle") >= 0 and _gift_score(c, it) >= 5:
                    c.change_affinity(2)
            msg = f"{_GREEN if ok else _RED}{m}{_R}"
            _party(player).refresh(player)


# ── customisation ────────────────────────────────────────────────

def _styles_for(c):
    """List of (style_dict, locked_reason_or_None)."""
    d = c.d
    out = [({"id": "signature", "label": "Signature", "desc": "Their own colours.",
             "colour": tuple(d.get("accent", (220, 220, 220))), "crown": c.rarity == "legendary"}, None)]
    for s in COMPANION_STYLES.get(c.role, []):
        out.append((dict(s, crown=False), None))
    alt = d.get("alt", {})
    out.append(({"id": "loyal", "label": alt.get("label", "Loyal Outfit"), "desc": "Unlocked by loyalty.",
                 "colour": tuple(alt.get("accent", d.get("accent", (220, 220, 220)))), "crown": False},
                None if c.loyal else f"Reach Loyal ({LOYAL_AT}) affinity"))
    regal_ok = c.rarity == "legendary" or c.starborn
    out.append(({"id": "starborn" if c.starborn else "regal", "label": "Starborn Radiance" if c.starborn else "Regal Crown",
                 "desc": "A golden crown and radiant trim.", "colour": STARBORN_ACCENT, "crown": True},
                None if regal_ok else "Legendary or Starborn companions only"))
    return out


def customise_menu(player):
    """Pick a companion to customise (also reachable from the tailor)."""
    party = _party(player)
    while True:
        allc = party.roster
        clr()
        print(C(f"\n{_CYAN}{_B}════  🎨 COMPANION CUSTOMISATION  ════{_R}\n"))
        if not allc:
            print(C(f"{_DIM}No companions to customise.{_R}"))
            _pause()
            return
        for ln in row_of_sprites([_spec_for(c) for c in allc[:6]]):
            print(ln)
        print()
        for i, c in enumerate(allc, 1):
            print(C(f"{_GOLD}[{i}]{_R} {c.tag()} {_DIM}{c.title} · {c.style.get('label', '')}{_R}"))
        print(C(f"{_GOLD}[0]{_R} Back"))
        ch = _ask(">")
        if ch in ("0", "", "q"):
            return
        if ch.isdigit() and 1 <= int(ch) <= len(allc):
            _customise_one(player, allc[int(ch) - 1])


def _customise_one(player, c):
    styles = _styles_for(c)
    sel = next((i for i, (s, _) in enumerate(styles) if s["id"] == c.style.get("id")), 0)
    msg = ""
    while True:
        s, locked = styles[sel]
        clr()
        print(C(f"\n{_GOLD}{_B}══════  🎨 {c.name.upper()}  ══════{_R}"))
        print(C(f"{_DIM}{c.title} · marker{_R} {c._col()}{c.marker}{_R} {_DIM}· wearing{_R} {_GOLD}{c.style.get('label')}{_R}\n"))
        prev_acc = s["colour"]
        art = row_of_sprites([dict(sprite=c.sprite, accent=prev_acc, legendary=s.get("crown"),
                                   label=f"{_col_rgb(prev_acc)}{c.marker}{_R} {_B}{c.name}{_R}",
                                   sub=f"{_DIM}{c.title}{_R}")], width=40, raw=True)
        info = [f"{_DIM}{sel + 1}/{len(styles)}{_R}  {_col_rgb(prev_acc)}██{_R}  {_B}{s['label']}{_R}"
                + (f"  {_RED}[LOCKED]{_R}" if locked else f"  {_GREEN}✓ wearing{_R}" if s["id"] == c.style.get("id") else ""),
                ""] + [f"{_DIM}{ln}{_R}" for ln in _wrap(s.get("desc", ""), 36)]
        if locked:
            info += ["", f"{_ORAN}Unlock: {locked}{_R}"]
        _two_col(art, info, gap=4)
        print()
        _opts([("A/D", "browse"), ("Enter", "wear"), ("K", "custom RGB"), ("N", "rename"),
               ("T", "title"), ("M", "marker"), ("E", "gear"), ("0", "back")])
        if msg:
            print(C(msg)); msg = ""
        ch = _ask(">").lower()
        if ch in ("0", "q", "x", "b"):
            return
        if ch == "a":
            sel = (sel - 1) % len(styles)
        elif ch == "d":
            sel = (sel + 1) % len(styles)
        elif ch in ("", "w", "y"):
            if locked:
                msg = f"{_RED}Locked — {locked}.{_R}"
            else:
                c.style = {"id": s["id"], "label": s["label"], "accent": list(s["colour"]), "crown": bool(s.get("crown"))}
                msg = f"{_GREEN}{c.name} now wears {s['label']}.{_R}"
        elif ch == "k":
            raw = _ask("Colour as R G B (0-255) or #RRGGBB >")
            rgb = _parse_rgb(raw)
            if rgb is None:
                msg = f"{_RED}Couldn't read that colour.{_R}"
            else:
                c.style = {"id": "custom", "label": "Custom Colour", "accent": list(rgb), "crown": c.crown and (c.rarity == "legendary" or c.starborn)}
                msg = f"{_col_rgb(rgb)}██{_R} {_GREEN}Custom colour applied.{_R}"
        elif ch == "n":
            nm = sanitize_name(_ask("New name (max 20) >"), 20)
            if nm and nm != "0":
                c.name = nm
                msg = f"{_GREEN}Renamed to {c.name}.{_R}"
        elif ch == "t":
            t = sanitize_name(_ask("New title (max 28, empty = default) >"), 28)
            c.custom_title = "" if t == "0" else t
            msg = f"{_GREEN}Title: {c.title}{_R}"
        elif ch == "m":
            m = sanitize_marker(_ask("Marker (one character) >"))
            if m:
                c.marker = m
                msg = f"{_GREEN}Marker set to {c._col()}{m}{_R}"
            else:
                msg = f"{_RED}Pick one printable character.{_R}"
        elif ch == "e":
            _gear_menu(player, c)


def _parse_rgb(raw):
    raw = (raw or "").strip()
    try:
        if raw.startswith("#") and len(raw) == 7:
            return tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))
        parts = raw.replace(",", " ").split()
        if len(parts) == 3:
            vals = [int(p) for p in parts]
            if all(0 <= v <= 255 for v in vals):
                return tuple(vals)
    except Exception:
        return None
    return None


# ═══════════════════════════════════════════════════════════════
# CLAN SYSTEM
# ═══════════════════════════════════════════════════════════════

CLAN_RANKS = ["Unranked", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Legend"]
CLAN_HALL_UPGRADES = [
    {"name": "Clan Banner",      "cost": 500,   "income": 5,
     "desc": "Your colours draw recruits: hire costs -10%, beaten foes ask to join more often."},
    {"name": "Training Grounds", "cost": 1200,  "income": 15,
     "desc": "Companions gain +10% XP; benched companions train (25% XP share)."},
    {"name": "Guild Storage",    "cost": 2000,  "income": 20,
     "desc": "Quartermaster stocks one Potion per day for you to collect (max 5)."},
    {"name": "Tavern",           "cost": 3500,  "income": 40,
     "desc": "Hire costs -10% more; today's travelling guests can be met at your hall."},
    {"name": "Forge",            "cost": 5000,  "income": 50,
     "desc": "Clan-forged gear: every companion +2 ATK and +2 DEF."},
    {"name": "War Room",         "cost": 8000,  "income": 80,
     "desc": "Drilled tactics: companions deal +10% damage."},
    {"name": "Dragon Vault",     "cost": 15000, "income": 150,
     "desc": "Legendary income from dragon contracts."},
]
FOUND_COST = 1000
MAX_BACKLOG_DAYS = 7
MAX_SUPPLIES = 5


class Clan:
    def __init__(self, name, leader_name):
        self.name = sanitize_name(name, 24) or "Nameless"
        self.leader = sanitize_name(leader_name, 24) or "Leader"
        self.rank_idx = 0
        self.members = 1
        self.upgrades = []
        self.gold_earned = 0
        self.days_active = 0
        self.pending_gold = 0
        self.last_tick_day = None     # in-game day of the last income settlement
        self.supplies = 0             # Guild Storage potions waiting

    @property
    def rank(self):
        return CLAN_RANKS[min(self.rank_idx, len(CLAN_RANKS) - 1)]

    @property
    def passive_income(self):
        base = 10
        for u in self.upgrades:
            for uh in CLAN_HALL_UPGRADES:
                if uh["name"] == u:
                    base += uh["income"]
        return base

    def _update_rank(self):
        new_rank = min(len(CLAN_RANKS) - 1, self.days_active // 15 + len(self.upgrades) // 2)
        if new_rank > self.rank_idx:
            self.rank_idx = new_rank
            return True
        return False

    def tick(self, days=1):
        """Accrue `days` of income directly (no day check). Prefer settle()."""
        days = max(0, int(days))
        self.days_active += days
        earned = self.passive_income * days
        self.pending_gold += earned
        if "Guild Storage" in self.upgrades:
            self.supplies = min(MAX_SUPPLIES, self.supplies + days)
        self._update_rank()
        return earned

    def settle(self, day):
        """Accrue income for whole in-game days elapsed since the last
        settlement (max MAX_BACKLOG_DAYS). Resting twice in one day pays
        nothing extra. Returns (days, gold)."""
        day = int(day)
        if self.last_tick_day is None:
            self.last_tick_day = day - 1
        days = min(MAX_BACKLOG_DAYS, max(0, day - int(self.last_tick_day)))
        if day > self.last_tick_day:
            self.last_tick_day = day
        if days <= 0:
            return 0, 0
        return days, self.tick(days)

    def collect(self):
        g = self.pending_gold
        self.pending_gold = 0
        self.gold_earned += g
        return g

    def buy_upgrade(self, player, upgrade_name):
        for uh in CLAN_HALL_UPGRADES:
            if uh["name"] == upgrade_name:
                if upgrade_name in self.upgrades:
                    return False, "Already purchased."
                if player.gold < uh["cost"]:
                    return False, f"Need {uh['cost']}g."
                player.gold -= uh["cost"]
                self.upgrades.append(upgrade_name)
                self.members += 2
                self._update_rank()
                try:
                    _party(player).refresh(player)
                except Exception:
                    pass
                return True, f"Upgrade '{upgrade_name}' built! Income +{uh['income']}g/day."
        return False, "Unknown upgrade."

    def to_dict(self):
        return {
            "name": self.name, "leader": self.leader,
            "rank_idx": self.rank_idx, "members": self.members,
            "upgrades": list(self.upgrades), "gold_earned": self.gold_earned,
            "days_active": self.days_active, "pending_gold": self.pending_gold,
            "last_tick_day": self.last_tick_day, "supplies": self.supplies,
        }

    @classmethod
    def from_dict(cls, d):
        c = cls(d.get("name", "Clan"), d.get("leader", "Leader"))
        c.rank_idx = int(d.get("rank_idx", 0) or 0)
        c.members = int(d.get("members", 1) or 1)
        c.upgrades = [u for u in (d.get("upgrades") or []) if isinstance(u, str)]
        c.gold_earned = int(d.get("gold_earned", 0) or 0)
        c.days_active = int(d.get("days_active", 0) or 0)
        c.pending_gold = int(d.get("pending_gold", 0) or 0)
        ltd = d.get("last_tick_day")
        c.last_tick_day = int(ltd) if isinstance(ltd, (int, float)) else None
        c.supplies = int(d.get("supplies", 0) or 0)
        return c


def clan_daily_tick(player, quiet=False):
    """Called on a rest (inn / base): settles clan income once per in-game
    day. Returns gold accrued."""
    clan = getattr(player, "owned_clan", None)
    if not clan:
        return 0
    day = current_day(player)
    days, gold = clan.settle(day)
    if quiet:
        return gold
    if gold:
        print(C(f"{_GOLD}Your clan '{clan.name}' earned {gold}g over {days} day{'s' if days != 1 else ''} "
                f"(collect it from the Clan menu).{_R}"))
    else:
        left = DAY_TURNS - (_party(player).clock % DAY_TURNS)
        print(C(f"{_DIM}Your clan has already reported today's income — next report in ~{left} steps of travel.{_R}"))
    return gold


def _clan_menu(player, can_swap=False):
    while True:
        clan = getattr(player, "owned_clan", None)
        clr()
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════╗"))
        print(C(f"║        ⚑  CLAN MENU          ║"))
        print(C(f"╚══════════════════════════════╝{_R}\n"))
        if not clan:
            print(C(f"{_DIM}You have no clan yet.{_R}"))
            print(C(f"Found a clan for {_GOLD}{FOUND_COST}g{_R}: daily income, a hall for your bench, upgrades."))
            print(C(f"\n{_GOLD}[F]{_R} Found clan  {_GOLD}[0]{_R} Back"))
            ch = _ask(">").lower()
            if ch in ("0", "", "q"):
                return
            if ch == "f":
                if player.gold < FOUND_COST:
                    print(C(f"{_RED}Need {FOUND_COST}g to found a clan.{_R}")); _pause(); continue
                name = sanitize_name(_ask("Clan name >"), 24)
                if not name or name == "0":
                    continue
                player.gold -= FOUND_COST
                player.owned_clan = Clan(name, player.name)
                player.owned_clan.last_tick_day = current_day(player)
                print(C(f"{_GREEN}Clan '{name}' founded!{_R}")); _pause()
            continue
        day = current_day(player)
        clan.settle(day)
        print(C(f"{_CYAN}{_B}{clan.name}{_R}  Rank: {_GOLD}{clan.rank}{_R}  {_DIM}Leader{_R} {clan.leader}"))
        print(C(f"Members: {clan.members}  Active: {clan.days_active} days  {_DIM}(day {day + 1}){_R}"))
        print(C(f"Income: {_GOLD}+{clan.passive_income}g/day{_R}  {_DIM}(accrues once per in-game day of travel){_R}"))
        print(C(f"Waiting: {_GOLD}{clan.pending_gold}g{_R}" + (f" + {clan.supplies} Potion(s)" if clan.supplies else "")
                + f"   Total collected: {_GOLD}{clan.gold_earned}g{_R}"))
        if clan.upgrades:
            print(C(f"{_DIM}Hall: {', '.join(clan.upgrades)}{_R}"))
        bench = _party(player).bench
        print(C(f"{_DIM}Hall bench: {len(bench)} companion(s){_R}\n"))
        opts = [("C", "Collect"), ("U", "Upgrade hall"), ("H", "Hall bench")]
        if "Tavern" in clan.upgrades and can_swap:
            opts.append(("V", "Guests at the hall tavern"))
        opts.append(("0", "Back"))
        _opts(opts)
        ch = _ask(">").lower()
        if ch in ("0", "", "q"):
            return
        if ch == "c":
            earned = clan.collect()
            player.gold += earned
            pots = 0
            if clan.supplies:
                try:
                    from game_items import ITEM_POOL
                    while clan.supplies > 0 and player.add_item(ITEM_POOL["Potion"]()):
                        clan.supplies -= 1; pots += 1
                except Exception:
                    pass
            if earned or pots:
                print(C(f"{_GREEN}Collected {earned}g" + (f" and {pots} Potion(s)" if pots else "") + f".{_R}"))
            else:
                print(C(f"{_DIM}Nothing to collect yet — income arrives with each new day.{_R}"))
            _pause()
        elif ch == "u":
            _clan_upgrade_menu(player, clan)
        elif ch == "h":
            party_menu(player, can_swap=can_swap)
        elif ch == "v" and "Tavern" in clan.upgrades and can_swap:
            _hall_guests(player)


def _hall_guests(player):
    day = current_day(player)
    from game_recruits import rotation_town
    ids = [cid for cid, d in COMPANION_DEFS.items()
           if d["spawn"].get("type") == "rotation" and rotation_town(cid, day) and not _party(player).has(cid)]
    clr()
    print(C(f"\n{_GOLD}{_B}🍺 Guests at your hall tavern today{_R}\n"))
    if not ids:
        print(C(f"{_DIM}No travellers today.{_R}")); _pause(); return
    for i, cid in enumerate(ids, 1):
        d = COMPANION_DEFS[cid]
        print(C(f"{_GOLD}[{i}]{_R} {rarity_col(d['rarity'])}{d['name']}{_R} {_DIM}— {d['title']}{_R}"))
    ch = _ask(">")
    if ch.isdigit() and 1 <= int(ch) <= len(ids):
        offer_recruit(player, ids[int(ch) - 1])


def _clan_upgrade_menu(player, clan):
    clr()
    print(C(f"\n{_CYAN}{_B}════  CLAN UPGRADES  ════{_R}\n"))
    for i, uh in enumerate(CLAN_HALL_UPGRADES):
        owned = uh["name"] in clan.upgrades
        tag = f"{_GREEN}[BUILT]{_R}" if owned else f"{_GOLD}{uh['cost']}g{_R}"
        print(C(f"{_GOLD}[{i + 1}]{_R} {_WHITE}{uh['name']}{_R}  {tag}  {_DIM}+{uh['income']}g/day{_R}"))
        print(C(f"     {_DIM}{uh['desc']}{_R}"))
    print(C(f"\n{_GOLD}[0]{_R} Back"))
    ch = _ask(">")
    if ch.isdigit() and 1 <= int(ch) <= len(CLAN_HALL_UPGRADES):
        uh = CLAN_HALL_UPGRADES[int(ch) - 1]
        ok, msg = clan.buy_upgrade(player, uh["name"])
        print(C(f"{_GREEN if ok else _RED}{msg}{_R}"))
        _pause()
