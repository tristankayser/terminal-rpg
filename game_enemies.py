"""
game_enemies.py — Enemy definitions, generation, and the boss mechanics framework.

Regular enemies stay simple and snappy: one basic attack per round, plus an
optional on-hit trait (poison, bleed, burn, gold theft) for elites.

Bosses (BossEnemy) are data-driven.  Every boss has a *kit* in BOSS_KITS:
  • intents     — the boss decides its move at the start of each round and the
                  combat screen shows it (Slay the Spire style), with a damage
                  estimate, so the right answer is always readable.
  • shields     — pips removed by every hit (2 for a weakness hit).  At zero
                  the boss is BROKEN: it loses its turn, any charge fizzles and
                  it takes heavy extra damage until it recovers (Octopath).
  • charges     — "⚠ CHARGING: Meteor Fall [2]" countdowns; Defend blunts the
                  release, breaking the boss cancels it.
  • stances     — counter stances (riposte, mirror, evasion, flight) active
                  for the round they are announced.
  • phases      — HP thresholds with a line of dialogue, stat changes, new
                  moves, new sprite, extra shields or summons.
  • adds        — minions that act each round and can be targeted.
  • enrage      — after N rounds every attack escalates.
  • immunities  — per-boss status immunities plus a general status resist.
Damage types: physical / fire / ice / shadow / holy / arcane / poison.
Difficulty ('story' | 'normal' | 'hard') lives in player.flags["difficulty"].
"""

import random, copy
from game_items import StatusEffect, Poison, Burn, Regen, Stun, roll_drops

def _C(text=""):
    from game_term import C
    return C(text)

def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"
_R = "\033[0m"
_B = "\033[1m"

# =============================================================
# DAMAGE TYPES
# =============================================================

DAMAGE_TYPES = ("physical", "fire", "ice", "shadow", "holy", "arcane", "poison")

TYPE_COLOUR = {
    "physical": _fg(200, 200, 210), "fire": _fg(240, 120, 40), "ice": _fg(120, 210, 255),
    "shadow": _fg(150, 90, 200),    "holy": _fg(255, 225, 120), "arcane": _fg(200, 110, 255),
    "poison": _fg(110, 210, 90),
}

# Class skills → damage type.  Unknown skills fall back to keywords, then to
# the caster's class (Mage → arcane, Healer → holy, everyone else physical).
SKILL_TYPES = {
    "Power Slash": "physical", "Guard Break": "physical",
    "Fireball": "fire", "Ice Spike": "ice", "Arcane Blast": "arcane",
    "Backstab": "physical", "Quick Strike": "physical", "Venom Blade": "poison",
    "Shield Bash": "physical", "Iron Slam": "physical",
    "Smite": "holy",
    "Cyclone Slash": "physical", "Sword Aura": "arcane", "Dragon Slash": "fire",
    "Meteor Burst": "fire", "Mana Storm": "arcane", "Time Freeze": "ice",
    "Phantom Strike": "shadow", "Nightfall": "shadow", "Shadow Realm": "shadow",
    "Titan Crush": "physical", "Rage Quake": "physical",
    "Holy Nova": "holy",
}
_TYPE_WORDS = (
    ("fire", ("fire", "flame", "meteor", "burn", "inferno", "blaze", "ember")),
    ("ice", ("ice", "frost", "freeze", "frozen", "blizzard", "glacial", "chill")),
    ("shadow", ("shadow", "night", "void", "dark", "umbra", "phantom")),
    ("holy", ("holy", "smite", "divine", "light", "radiant", "sacred", "judg")),
    ("arcane", ("arcane", "mana", "magic", "aura", "rune", "astral")),
    ("poison", ("venom", "poison", "toxic", "blight")),
)
_CLASS_TYPE = {"Mage": "arcane", "Archmage": "arcane", "Healer": "holy", "Arch Priest": "holy"}
COMPANION_ROLE_TYPE = {"mage": "arcane", "healer": "holy", "rogue": "physical",
                       "warrior": "physical"}


def skill_damage_type(skill, user=None):
    """Damage type of a player skill (Skill object or name)."""
    name = getattr(skill, "name", skill) or ""
    t = getattr(skill, "damage_type", None) or SKILL_TYPES.get(name)
    if t:
        return t
    low = name.lower()
    for typ, words in _TYPE_WORDS:
        if any(w in low for w in words):
            return typ
    job = getattr(getattr(user, "job", None), "name", "")
    return _CLASS_TYPE.get(job, "physical")


def companion_damage_type(companion):
    return COMPANION_ROLE_TYPE.get(getattr(companion, "role", ""), "physical")


# =============================================================
# EXTRA STATUS EFFECTS (combat-only; stripped when a battle ends)
# =============================================================

class Bleed(StatusEffect):
    def __init__(self, duration=3, damage=5):
        super().__init__("Bleed", duration); self.damage = damage
    def on_turn_start(self, target):
        target.hp = max(0, target.hp - self.damage)
        print(_C(f"[/] {target.name} bleeds for {self.damage} damage!"))
    def to_dict(self): return {"type": "Bleed", "duration": self.duration, "damage": self.damage}


class Blind(StatusEffect):
    """Sandstorms and smoke: the hero's attacks often miss."""
    MISS = 35
    def __init__(self, duration=2):
        super().__init__("Blind", duration)


COMBAT_ONLY_STATUSES = ("Blind", "Bleed")


# =============================================================
# DIFFICULTY
# =============================================================

DIFFICULTY = {
    "story":  dict(hp=0.75, atk=0.80, enrage=6,  shield=-1, reward=0.90, label="Story"),
    "normal": dict(hp=1.00, atk=1.00, enrage=0,  shield=0,  reward=1.00, label="Normal"),
    "hard":   dict(hp=1.30, atk=1.15, enrage=-3, shield=1,  reward=1.35, label="Hard"),
}


def get_difficulty(player):
    flags = getattr(player, "flags", None) or {}
    d = flags.get("difficulty", "normal")
    return d if d in DIFFICULTY else "normal"


def set_difficulty(player, level):
    """Set 'story' | 'normal' | 'hard'.  Returns the level actually stored."""
    level = (level or "normal").lower()
    if level not in DIFFICULTY:
        level = "normal"
    if not isinstance(getattr(player, "flags", None), dict):
        player.flags = {}
    player.flags["difficulty"] = level
    return level


# =============================================================
# ENEMY BASE
# =============================================================

class Enemy:
    def __init__(self, name, hp, atk, defense=0, exp_reward=10,
                 gold_reward=5, crit_chance=5, dodge_chance=3,
                 skills=None, enemy_class="Normal"):
        self.name         = name
        self.max_hp       = hp
        self.hp           = hp
        self.atk          = atk
        self.defense      = defense
        self.exp_reward   = exp_reward
        self.gold_reward  = gold_reward
        self.crit_chance  = crit_chance
        self.dodge_chance = dodge_chance
        self.skills       = skills or []
        self.enemy_class  = enemy_class
        self.status_effects = []
        # Mechanics shared by all enemies
        self.sprite        = name          # sprite key used by the combat screen
        self.dtype         = "physical"    # type of its own attacks
        self.weak          = set()         # damage types that hit for x1.5
        self.resist        = {}            # damage type -> multiplier (<1)
        self.immune        = set()         # status names it ignores
        self.status_resist = 0             # % chance to shrug off a status
        self.traits        = {}            # on-hit extras (see _on_hit_traits)
        self.stolen_gold   = 0
        self.is_add        = False
        self.notes         = []            # messages produced while taking hits
        self._incoming     = None          # (damage_type, source) for the next hit
        self._dodge_next   = False         # roll dodge inside take_damage (companions)

    # ── basics ────────────────────────────────────────────────
    def is_alive(self):
        return self.hp > 0

    def pop_notes(self):
        out, self.notes = self.notes, []
        return out

    def damage_mult(self, dtype, source):
        """Multiplier for an incoming hit (weakness / resistance)."""
        if not dtype:
            return 1.0
        if dtype in self.weak:
            return 1.5
        return self.resist.get(dtype, 1.0)

    def take_damage(self, dmg):
        dtype, source = self._incoming or (None, None)
        self._incoming = None
        if self._dodge_next:
            self._dodge_next = False
            if self.try_dodge():
                self.notes.append(f"{self.name} sidesteps the blow!")
                return 0
        mult = self.damage_mult(dtype, source)
        if dtype and dtype in self.weak:
            self.notes.append(f"{TYPE_COLOUR.get(dtype, '')}{_B}WEAK!{_R} {self.name} "
                              f"reels from {dtype} damage.")
        elif dtype and self.resist.get(dtype, 1.0) < 0.95:
            self.notes.append(f"{self.name} resists {dtype}.")
        dmg = int(dmg * mult)
        actual = max(1, dmg - self.defense // 4)
        self.hp = max(0, self.hp - actual)
        self._after_hit(actual, dtype, source)
        return actual

    def _after_hit(self, actual, dtype, source):
        pass

    def try_dodge(self):
        return random.randint(1, 100) <= self.dodge_chance

    def calc_crit(self, base):
        if random.randint(1, 100) <= self.crit_chance:
            return True, int(base * 1.5)
        return False, base

    def add_status(self, effect):
        if effect.name in self.immune:
            self.notes.append(f"{self.name} is immune to {effect.name}!")
            print(_C(f"{self.name} is immune to {effect.name}!"))
            return
        if self.status_resist and random.randint(1, 100) <= self.status_resist:
            print(_C(f"{self.name} shrugs off {effect.name}!"))
            return
        for e in self.status_effects:
            if e.name == effect.name:
                e.duration = max(e.duration, effect.duration)
                return
        self.status_effects.append(effect)

    def is_stunned(self):
        return any(e.name == "Stun" for e in self.status_effects)

    def process_status_start(self):
        for e in self.status_effects[:]:
            e.on_turn_start(self)

    def process_status_end(self):
        for e in self.status_effects[:]:
            e.on_turn_end(self)
            if not e.is_active():
                self.status_effects.remove(e)

    def basic_attack(self, target):
        if hasattr(target, "try_dodge") and target.try_dodge():
            print(_C(f"{target.name} dodges {self.name}'s attack!"))
            return 0
        base = max(1, self.atk + random.randint(-2, 3))
        crit, dmg = self.calc_crit(base)
        actual = target.take_damage(dmg)
        tag = " [CRIT!]" if crit else ""
        who = "" if getattr(target, "job", None) is not None else f" on {target.name}"
        print(_C(f"{self.name} attacks{who}{tag} -> {actual} damage!"))
        self._on_hit_traits(target, actual)
        return actual

    def _on_hit_traits(self, target, actual):
        """Elite extras: {'poison': (chance, turns), 'bleed': ..., 'burn': ...,
        'steal': (chance, fraction)}."""
        t = self.traits
        if not t or actual <= 0 or not target.is_alive():
            return
        power = max(2, self.atk // 6)
        for key, cls in (("poison", Poison), ("bleed", Bleed), ("burn", Burn)):
            if key in t and random.randint(1, 100) <= t[key][0]:
                if hasattr(target, "add_status"):
                    target.add_status(cls(duration=t[key][1], damage=power))
        if "steal" in t and hasattr(target, "gold") and target.gold > 0:
            chance, frac = t["steal"]
            if random.randint(1, 100) <= chance:
                amount = min(target.gold, max(3, int(target.gold * frac)))
                target.gold -= amount
                self.stolen_gold += amount
                print(_C(f"{self.name} snatches {amount} gold! (win to get it back)"))

    def hp_bar(self, width=20):
        filled = int(width * self.hp / self.max_hp)
        bar = "[" + "#" * filled + "-" * (width - filled) + "]"
        return f"{bar} {self.hp}/{self.max_hp}"

    def status_line(self):
        if not self.status_effects:
            return ""
        return "  (" + ", ".join(str(e) for e in self.status_effects) + ")"


# =============================================================
# BOSS MOVES
#   kind: attack | charge | heal | buff | summon | stance | shield | debuff
#         | drain_mp | steal
#   mult: damage multiplier of ATK     hits: number of strikes
#   type: damage type                  aoe: also hits companions
#   status: (name, turns)  with name in poison/burn/bleed/stun/blind
#   pierce: guard-break (punishes Defend)   lifesteal: fraction healed
#   turns (charge): countdown          stance: dict(counter=..., evade=..., halve=...)
#   cd: cooldown in rounds after use   finisher: favoured when the hero is low
# =============================================================

def _mv(name, kind="attack", **kw):
    d = dict(name=name, kind=kind, mult=1.0, hits=1, type="physical")
    d.update(kw)
    return d


MOVES = {
    # ── shared basics ──
    "strike":       _mv("Strike"),
    "heavy":        _mv("Heavy Blow", mult=1.55, cd=1),
    "roar":         _mv("Roar", "debuff", mult=0.4, status=("stun", 1), cd=4,
                        hint="Defend to resist the stun"),
    "rally":        _mv("Rally", "buff", buff=1.2, turns=3, cd=5),

    # ── Goblin King ──
    "gk_cudgel":    _mv("Royal Cudgel", mult=1.5, cd=1),
    "gk_horde":     _mv("Call the Horde", "summon", add="Goblin", count=1, cd=5),
    "gk_grog":      _mv("Swig of Grog", "heal", heal=0.18),
    "gk_roar":      _mv("Bellowing Roar", "debuff", mult=0.4, status=("stun", 1), cd=4,
                        hint="Defend to resist the stun"),
    "gk_slam":      _mv("Throne Slam", mult=1.35, pierce=True, cd=2),
    "gk_toss":      _mv("Crown Toss", "charge", turns=1, mult=2.3, cd=4),

    # ── Dungeon Warden ──
    "dw_flail":     _mv("Iron Flail", mult=1.5, cd=1),
    "dw_riposte":   _mv("Riposte Stance", "stance", stance=dict(counter="attack"), cd=3,
                        hint="basic attacks are countered — use a skill or Defend"),
    "dw_shackle":   _mv("Shackle Breaker", mult=1.3, pierce=True, cd=2),
    "dw_lockdown":  _mv("Lockdown", "charge", turns=2, mult=2.4, status=("stun", 1), cd=5),
    "dw_cells":     _mv("Open the Cells", "summon", add="Skeleton", count=1, cd=5),

    # ── Shadow Lich ──
    "sl_bolt":      _mv("Soul Bolt", mult=1.15, type="shadow"),
    "sl_drain":     _mv("Life Drain", mult=1.0, type="shadow", lifesteal=0.6, cd=2),
    "sl_raise":     _mv("Raise Dead", "summon", add="Skeleton", count=1, cd=4),
    "sl_ward":      _mv("Bone Ward", "shield", cd=5),
    "sl_harvest":   _mv("Soul Harvest", "charge", turns=2, mult=2.5, type="shadow",
                        lifesteal=0.5, cd=5),
    "sl_decay":     _mv("Curse of Decay", "debuff", mult=0.6, type="shadow",
                        status=("poison", 4), cd=3),

    # ── Frost Dragon ──
    "fd_claw":      _mv("Frost Claw", mult=1.1, type="ice"),
    "fd_sweep":     _mv("Tail Sweep", mult=0.85, aoe=True, cd=2),
    "fd_breath":    _mv("Glacial Breath", "charge", turns=2, mult=2.5, type="ice",
                        status=("stun", 1), cd=5),
    "fd_armor":     _mv("Ice Armor", "shield", cd=5),
    "fd_sky":       _mv("Take to the Sky", "stance", stance=dict(halve="attack"), cd=3,
                        hint="airborne — basic attacks deal half damage, skills fly true"),
    "fd_blizzard":  _mv("Blizzard", mult=0.7, type="ice", aoe=True, status=("bleed", 2), cd=3),

    # ── Shadow Lord ──
    "sh_lash":      _mv("Umbral Lash", mult=1.15, type="shadow"),
    "sh_eclipse":   _mv("Eclipse", "debuff", mult=0.5, type="shadow", status=("blind", 2), cd=4),
    "sh_drain":     _mv("Shadow Drain", mult=1.0, type="shadow", lifesteal=0.5, cd=2),
    "sh_mirror":    _mv("Umbral Mirror", "stance", stance=dict(counter="skill"), cd=3,
                        hint="skills are reflected — use basic attacks or Defend"),
    "sh_night":     _mv("Night Eternal", "charge", turns=2, mult=2.6, type="shadow", cd=5),
    "sh_beasts":    _mv("Call of the Abyss", "summon", add="Shadow Beast", count=1, cd=5),

    # ── Vaeltharion / Dragon ──
    "dr_claw":      _mv("Rending Claw", mult=1.15),
    "dr_breath":    _mv("Fire Breath", mult=1.2, type="fire", status=("burn", 3), cd=2),
    "dr_wing":      _mv("Wing Buffet", mult=0.8, aoe=True, cd=2),
    "dr_tail":      _mv("Tail Crush", mult=1.35, pierce=True, cd=2),
    "dr_flight":    _mv("Take Flight", "stance", stance=dict(halve="attack"), cd=3,
                        hint="airborne — basic attacks deal half damage, skills fly true"),
    "dr_dive":      _mv("Inferno Dive", "charge", turns=2, mult=2.7, type="fire", cd=5),
    "dr_cataclysm": _mv("Cataclysm", "charge", turns=2, mult=3.0, type="fire", aoe=True,
                        status=("burn", 3), cd=5),

    # ── Demon Lord Kharzul ──
    "dk_lash":      _mv("Hellfire Lash", mult=1.15, type="fire", status=("burn", 2)),
    "dk_imps":      _mv("Summon Imps", "summon", add="Imp", count=1, cd=5),
    "dk_brand":     _mv("Soul Brand", mult=1.0, type="shadow", status=("bleed", 3), cd=2),
    "dk_cleave":    _mv("Abyssal Cleave", mult=1.4, type="shadow", pierce=True, cd=2),
    "dk_meteor":    _mv("Hellfire Meteor", "charge", turns=2, mult=2.7, type="fire", aoe=True,
                        cd=5),
    "dk_aura":      _mv("Flame Aura", "stance", stance=dict(counter="attack"), cd=3,
                        hint="touching him burns — basic attacks are countered"),
    "dk_doom":      _mv("Doomfire", "charge", turns=1, mult=2.4, type="fire", cd=4),

    # ── Hellhound Warden ──
    "hh_twin":      _mv("Twin Bite", mult=0.7, hits=2, status=("bleed", 2), needs_heads=True),
    "hh_bite":      _mv("Savage Bite", mult=1.2, status=("bleed", 3), cd=1),
    "hh_howl":      _mv("Hellfire Howl", "debuff", mult=0.5, type="fire", status=("stun", 1),
                        cd=4, hint="Defend to resist the stun"),
    "hh_breath":    _mv("Brimstone Breath", "charge", turns=1, mult=2.0, type="fire",
                        status=("burn", 3), cd=4),
    "hh_pounce":    _mv("Pounce", mult=1.3, pierce=True, cd=2),

    # ── Sand Djinn Azhar ──
    "dj_wind":      _mv("Scouring Wind", mult=1.1, type="arcane"),
    "dj_storm":     _mv("Sandstorm", "debuff", mult=0.5, status=("blind", 3), cd=4),
    "dj_ward":      _mv("Wind Ward", "stance", stance=dict(counter="attack"), cd=3,
                        hint="the wind turns blades — basic attacks are countered"),
    "dj_wish":      _mv("Wish Granted", "heal", heal=0.15),
    "dj_tempest":   _mv("Desert Tempest", "charge", turns=2, mult=2.4, type="arcane", aoe=True,
                        cd=5),
    "dj_mirage":    _mv("Mirage", "stance", stance=dict(evade=60), cd=4,
                        hint="shimmering mirage — most attacks will miss"),

    # ── Scorpion Matriarch ──
    "sm_pincer":    _mv("Pincer Crush", mult=1.45, cd=1),
    "sm_sting":     _mv("Venom Sting", mult=0.9, type="poison", status=("poison", 4)),
    "sm_brood":     _mv("Brood Call", "summon", add="Sand Scorpion", count=1, cd=3),
    "sm_burrow":    _mv("Burrow", "stance", stance=dict(evade=70), cd=4,
                        hint="she burrows — most attacks will miss"),
    "sm_deluge":    _mv("Toxic Deluge", "charge", turns=2, mult=2.2, type="poison", aoe=True,
                        status=("poison", 3), cd=5),

    # ── The Hollow Regent ──
    "hr_sceptre":   _mv("Sceptre Strike", mult=1.15, type="arcane"),
    "hr_toll":      _mv("Crown's Toll", "drain_mp", mult=0.6, type="arcane", drain=0.35, cd=2),
    "hr_decree":    _mv("Royal Decree", mult=1.35, type="arcane", pierce=True, cd=2),
    "hr_court":     _mv("Hollow Court", "shield", cd=5),
    "hr_lance":     _mv("Void Lance", mult=1.0, type="shadow", aoe=True, cd=2),
    "hr_collapse":  _mv("Ward Collapse", "charge", turns=2, mult=3.0, type="arcane", aoe=True,
                        cd=5),

    # ── Archmage Veyl the Unbound ──
    "av_missiles":  _mv("Arcane Missiles", mult=0.5, hits=3, type="arcane"),
    "av_images":    _mv("Mirror Images", "summon", add="Mirror Image", count=2, cd=5),
    "av_blink":     _mv("Blink Counter", "stance", stance=dict(counter="all"), cd=4,
                        hint="he will teleport and counter ANY hit — Defend or heal"),
    "av_barrier":   _mv("Rebuild Barrier", "shield", cd=4),
    "av_nova":      _mv("Unbound Nova", "charge", turns=2, mult=2.6, type="arcane", aoe=True,
                        cd=5),
    "av_hex":       _mv("Hex of Frailty", "debuff", mult=0.6, type="arcane",
                        status=("blind", 2), cd=4),

    # ── Bandit King Rourke ──
    "br_chop":      _mv("Axe Chop", mult=1.15),
    "br_smoke":     _mv("Smoke Bomb", "stance", stance=dict(evade=65), cd=4,
                        hint="smoke everywhere — most attacks will miss"),
    "br_boys":      _mv("Call the Boys", "summon", add="Bandit Thug", count=1, cd=4),
    "br_fingers":   _mv("Sticky Fingers", "steal", mult=0.7, steal=0.08, cd=3),
    "br_kick":      _mv("Dirty Kick", mult=1.25, pierce=True, cd=2),
    "br_execute":   _mv("Headsman's Swing", "charge", turns=1, mult=2.2, finisher=True, cd=4),

    # ── Thieves' Guildmaster ──
    "tg_daggers":   _mv("Poisoned Daggers", mult=0.6, hits=2, type="poison",
                        status=("poison", 3)),
    "tg_riposte":   _mv("Riposte", "stance", stance=dict(counter="attack"), cd=3,
                        hint="blade raised — basic attacks are countered"),
    "tg_step":      _mv("Shadowstep", "stance", stance=dict(evade=60), cd=4,
                        hint="he melts into shadow — most attacks will miss"),
    "tg_pocket":    _mv("Pickpocket", "steal", mult=0.6, steal=0.06, cd=3),
    "tg_guild":     _mv("Whistle for the Guild", "summon", add="Alley Thief", count=1, cd=4),
    "tg_garrote":   _mv("Garrote", mult=1.35, pierce=True, status=("bleed", 2), cd=2),
}

# Intent icons per move kind (all single-width glyphs)
_KIND_ICON = {"attack": "⚔", "charge": "⚠", "heal": "✚", "buff": "▲", "summon": "✦",
              "stance": "↺", "shield": "◆", "debuff": "✖", "drain_mp": "✖", "steal": "$"}


# =============================================================
# BOSS KITS  (moves are (move_id, weight) lists per phase)
# =============================================================

BOSS_KITS = {
    "Goblin King": dict(
        hp=1.15, atk=1.22,
        title="Tyrant of the Warrens", element="physical", colour=(95, 205, 95),
        weak=["fire", "holy"], shield=3, enrage=14, heals=1, max_adds=2,
        intro="\"Kneel before the Goblin King, or be crushed beneath his throne!\"",
        last_words="\"My... crown... my precious...\"",
        moves=[("strike", 4), ("gk_cudgel", 3), ("gk_horde", 2), ("gk_roar", 1),
               ("gk_grog", 1)],
        phases=[dict(at=0.5, title="THRONE RAGE",
                     line="\"You'll pay for every scratch on my royal hide!\"",
                     atk=1.15, add=[("gk_slam", 2), ("gk_toss", 2)])],
    ),
    "Dungeon Warden": dict(
        hp=1.05, atk=1.05,
        title="Keeper of the Deep Cells", element="physical", colour=(195, 200, 215),
        weak=["arcane", "ice"], resist={"physical": 0.8}, immune=["Stun"],
        shield=5, enrage=15, max_adds=1,
        intro="\"No prisoner leaves my halls. Not alive.\"",
        last_words="\"The keys... are... yours...\"",
        moves=[("strike", 4), ("dw_flail", 3), ("dw_riposte", 2), ("dw_shackle", 2),
               ("dw_lockdown", 2)],
        phases=[dict(at=0.5, title="RIOT IN THE CELLS",
                     line="\"Guards! Inmates! Anyone! Tear this intruder apart!\"",
                     atk=1.1, summon=("Skeleton", 1), add=[("dw_cells", 2)])],
    ),
    "Shadow Lich": dict(
        hp=1.05, atk=1.08,
        title="Hoarder of Souls", element="shadow", colour=(235, 95, 175),
        weak=["holy", "fire"], resist={"shadow": 0.4, "poison": 0.5},
        immune=["Poison", "Stun"], shield=4, enrage=15, max_adds=2,
        intro="\"Your soul will glow so prettily in my phylactery.\"",
        last_words="\"I... will... return...\"",
        moves=[("sl_bolt", 4), ("sl_drain", 2), ("sl_raise", 2), ("sl_harvest", 2),
               ("sl_ward", 1)],
        phases=[dict(at=0.5, title="PHYLACTERY PULSE",
                     line="\"Death is a door — and I hold the key!\"",
                     atk=1.15, add=[("sl_decay", 2)], shield=5)],
    ),
    "Frost Dragon": dict(
        hp=1.15, atk=1.15,
        title="Wyrm of the White Silence", element="ice", colour=(185, 225, 255),
        weak=["fire"], resist={"ice": 0.3}, immune=["Stun"], shield=5, enrage=16,
        intro="The air freezes in your lungs as the great wyrm uncoils.",
        last_words="The Frost Dragon's breath fades into silent snow.",
        moves=[("fd_claw", 4), ("fd_sweep", 2), ("fd_breath", 2), ("fd_armor", 1)],
        phases=[dict(at=0.6, title="WINGS OF WINTER",
                     line="The dragon beats its wings and rises into the blizzard!",
                     atk=1.1, add=[("fd_sky", 2)]),
                dict(at=0.3, title="ENDLESS BLIZZARD",
                     line="Ice storms howl — the dragon fights with frozen fury!",
                     atk=1.1, add=[("fd_blizzard", 2)], enrage=True)],
    ),
    "Shadow Lord": dict(
        hp=0.88, atk=1.0,
        title="Prince of the Lightless Court", element="shadow", colour=(185, 95, 235),
        weak=["holy"], resist={"shadow": 0.5}, immune=["Stun"], shield=5, enrage=16,
        max_adds=1,
        intro="\"Light is a brief accident. Darkness is forever.\"",
        last_words="\"The dark... remembers... you...\"",
        moves=[("sh_lash", 4), ("sh_eclipse", 2), ("sh_drain", 2), ("sh_mirror", 2)],
        phases=[dict(at=0.66, title="THE LONG NIGHT",
                     line="\"Let the stars go out one by one.\"",
                     atk=1.1, add=[("sh_night", 2)]),
                dict(at=0.33, title="ABYSSAL CROWN",
                     line="\"Rise, my beasts! Devour the light!\"",
                     atk=1.1, summon=("Shadow Beast", 1), add=[("sh_beasts", 1)])],
    ),
    "Dragon": dict(
        hp=1.0, atk=1.0,
        title="Vaeltharion the Ashen", element="fire", colour=(225, 60, 60),
        weak=["ice"], resist={"fire": 0.4}, immune=["Burn", "Stun"], shield=6, enrage=18,
        intro="\"Little ember. I have burned kingdoms older than your bloodline.\"",
        last_words="\"The ash... settles... at last...\"",
        moves=[("dr_claw", 4), ("dr_breath", 3), ("dr_wing", 2), ("dr_tail", 2)],
        phases=[dict(at=0.66, title="WINGS OF ASH",
                     line="Vaeltharion takes to the burning sky!",
                     atk=1.1, add=[("dr_flight", 2), ("dr_dive", 2)]),
                dict(at=0.33, title="ASHEN FURY",
                     line="\"ENOUGH! Burn with this world!\"",
                     atk=1.15, add=[("dr_cataclysm", 2)], enrage=True, shield=7)],
    ),
    "Demon Lord Kharzul": dict(
        hp=0.75, atk=0.9,
        title="Tyrant of Duskthorn", element="fire", colour=(225, 60, 60),
        weak=["holy", "ice"], resist={"fire": 0.3, "shadow": 0.6},
        immune=["Burn", "Stun"], shield=6, enrage=16, max_adds=2,
        intro="\"Another hero? My imps were getting hungry.\"",
        last_words="\"This... is not... the end of the Dusk...\"",
        moves=[("dk_lash", 4), ("dk_imps", 2), ("dk_brand", 2), ("dk_cleave", 2)],
        phases=[dict(at=0.66, title="DUSKTHORN BURNS",
                     line="\"Let the whole citadel become your pyre!\"",
                     atk=1.1, add=[("dk_meteor", 2), ("dk_aura", 2)]),
                dict(at=0.33, title="INFERNAL ASCENSION",
                     line="Kharzul's armour cracks — hellfire pours from within!",
                     atk=1.15, enrage=True, shield=7, summon=("Imp", 1),
                     add=[("dk_doom", 2)])],
    ),
    "Hellhound Warden": dict(
        hp=0.92, atk=1.0,
        title="Gatekeeper of Duskthorn", element="fire", colour=(235, 140, 45),
        weak=["ice", "holy"], resist={"fire": 0.5}, immune=["Burn"],
        shield=6, shield_label="HEADS", enrage=14,
        intro="Two heads snarl in unison. Chains as thick as your arm rattle.",
        last_words="Both heads fall silent. The gate stands unguarded.",
        moves=[("hh_twin", 4), ("hh_bite", 3), ("hh_howl", 1), ("hh_breath", 2)],
        phases=[dict(at=0.4, title="CHAINS SNAP",
                     line="The chains break — the Warden lunges with savage fury!",
                     atk=1.2, add=[("hh_pounce", 2)])],
    ),
    "Sand Djinn Azhar": dict(
        hp=1.2, atk=1.18,
        title="Breath of the Burning Dunes", element="arcane", colour=(100, 225, 235),
        weak=["ice", "holy"], resist={"physical": 0.85, "arcane": 0.6},
        immune=["Poison", "Stun"], shield=5, enrage=15, heals=1,
        intro="\"Three wishes? Hah! You get none, little thief.\"",
        last_words="\"Back... into the lamp... again...\"",
        moves=[("dj_wind", 4), ("dj_storm", 2), ("dj_ward", 2), ("dj_tempest", 2),
               ("dj_wish", 1)],
        phases=[dict(at=0.5, title="THE LAMP CRACKS",
                     line="\"You dare? Then let the desert swallow you!\"",
                     atk=1.15, add=[("dj_mirage", 2)])],
    ),
    "Scorpion Matriarch": dict(
        hp=0.85, atk=0.9,
        title="Mother of the Sunspire Pit", element="poison", colour=(235, 140, 45),
        weak=["arcane", "fire"], resist={"physical": 0.8, "poison": 0.2},
        immune=["Poison"], shield=4, enrage=14, max_adds=2,
        intro="The pit floor heaves. Something huge clicks in the dark.",
        last_words="The Matriarch's tail curls, trembles, and is still.",
        moves=[("sm_pincer", 3), ("sm_sting", 3), ("sm_brood", 2), ("sm_burrow", 1),
               ("sm_deluge", 2)],
        phases=[dict(at=0.5, title="THE BROOD SWARMS",
                     line="Dozens of tiny scorpions boil out of the sand!",
                     atk=1.15, summon=("Sand Scorpion", 1))],
    ),
    "The Hollow Regent": dict(
        hp=0.92, atk=1.0,
        title="Usurper of the Cursed Crown", element="arcane", colour=(185, 95, 235),
        weak=["holy"], resist={"arcane": 0.5, "shadow": 0.7}, immune=["Stun", "Poison"],
        shield=6, enrage=18,
        intro="\"The crown chose me. It will choose your silence, too.\"",
        last_words="The cursed crown rolls across the floor, its whispers finally silent.",
        moves=[("hr_sceptre", 4), ("hr_toll", 2), ("hr_decree", 2), ("hr_court", 1)],
        phases=[dict(at=0.6, title="THE TRUE FORM",
                     line="The regent's face splits — nothing but violet void beneath the crown!",
                     atk=1.15, sprite="Hollow Regent Unmasked",
                     resist={"shadow": 0.7}, weak=["holy", "arcane"],
                     passive=dict(mp_drain=0.08), add=[("hr_lance", 2)]),
                dict(at=0.3, title="WARD COLLAPSE",
                     line="\"If I cannot keep this kingdom, NO ONE WILL!\"",
                     atk=1.1, add=[("hr_collapse", 3)], enrage=True, shield=7)],
    ),
    "Archmage Veyl the Unbound": dict(
        hp=0.95, atk=1.0,
        title="Renegade of the Royal Tower", element="arcane", colour=(85, 135, 235),
        weak=["shadow", "physical"], resist={"arcane": 0.5, "fire": 0.8, "ice": 0.8},
        immune=["Stun"], shield=6, shield_label="BARRIER", enrage=15, max_adds=2,
        intro="\"The King chained my art. I am Unbound now — and you are in my way.\"",
        last_words="\"Bound... once more...\"",
        moves=[("av_missiles", 4), ("av_images", 2), ("av_blink", 2), ("av_barrier", 1),
               ("av_nova", 2)],
        phases=[dict(at=0.5, title="UNBOUND",
                     line="\"Watch closely. This is what they feared.\"",
                     atk=1.15, add=[("av_hex", 2)], summon=("Mirror Image", 2))],
    ),
    "Bandit King Rourke": dict(
        hp=1.2, atk=1.25,
        title="Lord of the Hideout", element="physical", colour=(160, 105, 60),
        weak=["fire", "arcane"], shield=3, enrage=14, max_adds=2, heals=1,
        intro="\"Nice boots. Nice purse. I'll take both.\"",
        last_words="\"Should've... stayed a farmer...\"",
        moves=[("br_chop", 4), ("br_smoke", 2), ("br_boys", 2), ("br_fingers", 2),
               ("br_kick", 2)],
        phases=[dict(at=0.5, title="NO MORE GAMES",
                     line="\"Right. Now I'm angry. Boys — the big axe!\"",
                     atk=1.15, add=[("br_execute", 2), ("rally", 1)])],
    ),
    "Thieves' Guildmaster": dict(
        hp=1.25, atk=1.25,
        title="Master of the Undercity", element="poison", colour=(110, 60, 150),
        weak=["holy", "fire"], resist={"poison": 0.3}, immune=["Poison"],
        shield=3, enrage=14, max_adds=1,
        intro="\"You've been a nuisance to the Guild. Nuisances disappear.\"",
        last_words="\"The Guild... never... forgets...\"",
        moves=[("tg_daggers", 4), ("tg_riposte", 2), ("tg_step", 1), ("tg_pocket", 2),
               ("tg_guild", 1)],
        phases=[dict(at=0.5, title="THE GUILD NEVER FORGETS",
                     line="\"Cutthroats! To me!\"",
                     atk=1.15, summon=("Cutthroat", 1), add=[("tg_garrote", 2)])],
    ),
}
BOSS_KITS["Vaeltharion"] = BOSS_KITS["Dragon"]

# Sensible default kit for any boss name without its own
_DEFAULT_KIT = dict(
    title="", element="physical", colour=(225, 60, 60), shield=3, enrage=14,
    moves=[("strike", 4), ("heavy", 2), ("roar", 1)],
    phases=[dict(at=0.5, title="PHASE 2", line="", atk=1.2)],
)


# =============================================================
# BOSS ENEMY
# =============================================================

BREAK_MULT = 1.6      # extra damage taken while broken / exposed
CHARGE_MULT = 1.15    # charged attacks hit this much harder than their listed mult
PARTY_HP_PER_POWER = 0.95  # boss HP bonus per "one hero's worth" of companion ATK
PARTY_HP_PER_SOAK = 0.40   # ... and per "one hero's worth" of companion HP (they soak hits)
PARTY_ATK_PER_MATE = 0.04  # boss ATK bonus per companion
COMPANION_HIT = 0.7        # single-target boss blows on companions land softer


class BossEnemy(Enemy):
    SKILL_CHANCE = 40   # kept for compatibility

    def __init__(self, name, hp, atk, defense=10, exp_reward=500,
                 gold_reward=300, boss_skills=None, kit=None, level=None):
        super().__init__(name, hp, atk, defense, exp_reward, gold_reward,
                         crit_chance=8, dodge_chance=4, enemy_class="BOSS")
        self.boss_skills = boss_skills or []
        self.kit = kit or BOSS_KITS.get(name) or _DEFAULT_KIT
        k = self.kit
        self.level       = level or max(1, int((atk - 9) / 2.9))
        self.title       = k.get("title", "")
        self.colour      = tuple(k.get("colour", (225, 60, 60)))
        self.dtype       = k.get("element", "physical")
        self.weak        = set(k.get("weak", []))
        self.resist      = dict(k.get("resist", {}))
        self.immune      = set(k.get("immune", []))
        self.status_resist = 30
        self.phase       = 1
        self.phases      = [dict(p) for p in k.get("phases", [])]
        self.moves       = list(k.get("moves", _DEFAULT_KIT["moves"]))
        self.shield_max  = k.get("shield", 0)
        self.shield      = self.shield_max
        self.shield_label = k.get("shield_label", "SHIELD")
        self.broken      = False
        self.exposed     = False
        self.intent      = None
        self.charge      = None        # {"id": move_id, "left": n}
        self.stance      = None        # move id of the active stance
        self.adds        = []
        self.max_adds    = k.get("max_adds", 2)
        self.enrage_at   = k.get("enrage", 14)
        self.enraged     = 0
        self.atk_mult    = 1.0
        self.buff_turns  = 0
        self.buff_mult   = 1.0
        self.cooldowns   = {}
        self.heals_left  = k.get("heals", 0)
        self.passive     = {}
        self.round       = 0
        self.last_move   = None
        self.player_defended_last = False
        self.just_summoned = False
        self._pending_counter = 0
        self._prepared   = False
        self.difficulty  = "normal"

    # ── setup ─────────────────────────────────────────────────
    def prepare(self, player):
        """Apply the player's difficulty once, right before the fight."""
        if self._prepared:
            return
        self._prepared = True
        self.difficulty = get_difficulty(player)
        d = DIFFICULTY[self.difficulty]
        # Every companion adds damage and soaks hits: bosses grow to match
        # (scaled by their attack relative to the hero's, so it adapts to
        # however strong companions are at this point of the game).
        try:
            alive = [m for m in player.party.members if m.is_alive()]
            power = sum(max(0, getattr(m, "atk", 0)) for m in alive)
            # skills and crits make the hero hit ~1.3x their listed ATK
            ratio = min(3.0, power / max(1.0, player.combat_atk() * 1.3))
            bulk = sum(max(0, getattr(m, "max_hp", 0)) for m in alive)
            soak = min(3.0, bulk / max(1, player.max_hp))
        except Exception:
            alive, ratio, soak = [], 0.0, 0.0
        self.party_size = len(alive)
        party_hp = 1.0 + PARTY_HP_PER_POWER * ratio + PARTY_HP_PER_SOAK * soak
        party_atk = 1.0 + PARTY_ATK_PER_MATE * len(alive)
        self.enrage_at += len(alive)            # bigger fights last a little longer
        self.max_hp = max(1, int(self.max_hp * d["hp"] * party_hp))
        self.atk = max(1, int(self.atk * party_atk))
        self.hp = self.max_hp
        self.atk = max(1, int(self.atk * d["atk"]))
        self.enrage_at = max(6, self.enrage_at + d["enrage"])
        if self.shield_max:
            self.shield_max = max(1, self.shield_max + d["shield"])
            self.shield = self.shield_max
        self.exp_reward = int(self.exp_reward * d["reward"])
        self.gold_reward = int(self.gold_reward * d["reward"])

    # ── damage intake ─────────────────────────────────────────
    def damage_mult(self, dtype, source):
        m = super().damage_mult(dtype, source)
        if self.broken or self.exposed:
            m *= BREAK_MULT
        st = MOVES.get(self.stance, {}).get("stance") if self.stance else None
        if st:
            kind = "attack" if source == "attack" else "skill" if source == "skill" else None
            if st.get("halve") and kind == st["halve"]:
                m *= 0.5
            ctr = st.get("counter")
            if ctr and source in ("attack", "skill") and ctr in (kind, "all"):
                m *= 0.3
                self._pending_counter += 1
        return m

    def try_dodge(self):
        st = MOVES.get(self.stance, {}).get("stance") if self.stance else None
        chance = st.get("evade", self.dodge_chance) if st else self.dodge_chance
        if self.broken:
            chance = 0
        return random.randint(1, 100) <= chance

    def _after_hit(self, actual, dtype, source):
        if not self.shield_max or self.broken or self.hp <= 0:
            return
        weak_hit = bool(dtype and dtype in self.weak)
        if source == "companion":
            # Companions only chip the guard by exploiting a weakness, so
            # breaking stays the hero's job even with a full party.
            pips = 1 if weak_hit else 0
        else:
            pips = 2 if weak_hit else 1
        if not pips:
            return
        before = self.shield
        self.shield = max(0, self.shield - pips)
        half = self.shield_max // 2
        if self.shield_label == "HEADS" and before > half >= self.shield:
            self.notes.append(f"{_fg(235,140,45)}One of the Warden's heads reels, dazed!{_R}")
        if self.shield == 0:
            self.broken = True
            self.exposed = False
            msg = f"{_fg(255,215,0)}{_B}✦ BREAK! ✦{_R} {self.name}'s guard shatters"
            if self.charge:
                msg += f" — {MOVES[self.charge['id']]['name']} fizzles"
                self.charge = None
            self.stance = None
            self.notes.append(msg + "!")

    def add_status(self, effect):
        if effect.name == "Stun" and "Stun" not in self.immune:
            # A stun on a boss staggers it: knocks pips off instead
            if self.shield_max and not self.broken:
                self.shield = max(1, self.shield - 1)
                print(_C(f"{self.name} is staggered! (-1 {self.shield_label.lower()})"))
                return
        super().add_status(effect)

    # ── phases ────────────────────────────────────────────────
    def check_phase(self):
        """Enter every phase whose threshold has been crossed. Returns log lines."""
        out = []
        while self.phases and self.hp > 0 and self.hp <= self.max_hp * self.phases[0]["at"]:
            ph = self.phases.pop(0)
            self.phase += 1
            out.append(f"{_fg(*self.colour)}{_B}══ PHASE {self.phase}: {ph.get('title', '')} ══{_R}")
            if ph.get("line"):
                out.append(f"{_fg(240,200,60)}{ph['line']}{_R}")
            self.atk_mult *= ph.get("atk", 1.0)
            if ph.get("moves"):
                self.moves = list(ph["moves"])
            for mv in ph.get("add", []):
                self.moves.append(tuple(mv))
            if ph.get("sprite"):
                self.sprite = ph["sprite"]
            if "weak" in ph:
                self.weak = set(ph["weak"])
            if "resist" in ph:
                self.resist = dict(ph["resist"])
            if ph.get("passive"):
                self.passive.update(ph["passive"])
            if ph.get("shield"):
                d = DIFFICULTY.get(self.difficulty, DIFFICULTY["normal"])
                self.shield_max = max(1, ph["shield"] + d["shield"])
                if not self.broken:
                    self.shield = self.shield_max
            if ph.get("enrage"):
                self.enraged = max(self.enraged, 1)
                out.append(f"{_fg(220,60,60)}{_B}{self.name} is ENRAGED!{_R}")
            if ph.get("summon"):
                name, count = ph["summon"]
                out += self._summon(name, count)
        return out

    # ── adds ──────────────────────────────────────────────────
    def alive_adds(self):
        return [a for a in self.adds if a.is_alive()]

    def _summon(self, name, count):
        lines = []
        self.adds = self.alive_adds()
        for _ in range(count):
            if len(self.adds) >= max(self.max_adds, count):
                break
            a = make_add(name, self.level)
            self.adds.append(a)
            self.just_summoned = True
            lines.append(f"{_fg(235,140,45)}✦ {a.name} joins the fight!{_R}")
        return lines

    # ── AI ────────────────────────────────────────────────────
    def total_atk(self):
        enr = 1.0 + 0.10 * self.enraged
        buff = self.buff_mult if self.buff_turns > 0 else 1.0
        return self.atk * self.atk_mult * enr * buff

    def estimate(self, mv, player, per_hit=False):
        """Rough damage estimate of a move against the hero (for the intent line).
        Total over all hits unless per_hit."""
        if mv.get("kind") not in ("attack", "charge", "debuff", "drain_mp", "steal"):
            return 0
        per = int(self.total_atk() * mv.get("mult", 1.0)
                  * (CHARGE_MULT if mv.get("kind") == "charge" else 1.0))
        try:
            red = player.combat_def() // 3
        except Exception:
            red = 0
        one = max(1, per - red)
        return one if per_hit else one * mv.get("hits", 1)

    def _choose(self, player):
        hp_frac = self.hp / max(1, self.max_hp)
        p_frac = player.hp / max(1, player.max_hp)
        p_stunned = any(e.name == "Stun" for e in getattr(player, "status_effects", []))
        heads_up = self.shield > self.shield_max // 2
        pool = []
        for mid, w in self.moves:
            mv = MOVES.get(mid)
            if not mv or self.cooldowns.get(mid, 0) > 0:
                continue
            kind = mv["kind"]
            w = float(w)
            if kind == "heal":
                if hp_frac > 0.4 or self.heals_left <= 0:
                    continue
                w *= 6
            elif kind == "summon":
                alive = len(self.alive_adds())
                if alive >= self.max_adds:
                    continue
                w *= 1.5 if alive == 0 else 0.7
            elif kind == "shield":
                if not self.shield_max or self.shield > self.shield_max // 2:
                    continue
                w *= 2
            elif kind in ("charge", "stance") and self.last_move and \
                    MOVES.get(self.last_move, {}).get("kind") == kind:
                continue
            elif kind == "drain_mp" and getattr(player, "mp", 0) < 8:
                w *= 0.3
            elif kind == "steal" and getattr(player, "gold", 0) <= 0:
                continue
            if mv.get("status", (None,))[0] == "stun" and p_stunned:
                continue
            if mv.get("needs_heads") and not heads_up:
                continue
            if mv.get("pierce"):
                w *= 4 if self.player_defended_last else 0.6
            if mv.get("finisher") and p_frac < 0.35:
                w *= 3
            if mid == self.last_move and kind == "attack" and mv.get("mult", 1) > 1.2:
                w *= 0.4
            pool.append((mid, w))
        if not pool:
            return "strike"
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        for mid, w in pool:
            r -= w
            if r <= 0:
                return mid
        return pool[-1][0]

    def plan(self, player):
        """Start of round: decide (and reveal) what the boss will do."""
        self.round += 1
        if self.broken:
            self.intent = {"kind": "broken"}
            return
        if self.charge:
            mv = MOVES[self.charge["id"]]
            self.intent = {"id": self.charge["id"], "kind": "charge", "left": self.charge["left"]}
            return
        mid = self._choose(player)
        mv = MOVES.get(mid, MOVES["strike"])
        self.intent = {"id": mid, "kind": mv["kind"]}
        if mv["kind"] == "charge":
            self.charge = {"id": mid, "left": mv.get("turns", 2)}
            self.intent["left"] = self.charge["left"]
        elif mv["kind"] == "stance":
            self.stance = mid

    def intent_text(self, player):
        """One coloured line describing the boss's next move."""
        it = self.intent or {}
        kind = it.get("kind")
        if kind == "broken":
            return (f"{_fg(255,215,0)}{_B}✦ BROKEN{_R} {_fg(255,215,0)}— it can't act and "
                    f"takes heavy damage. Hit it hard!{_R}")
        mv = MOVES.get(it.get("id"), {})
        if not mv:
            return ""
        name = mv["name"]
        icon = _KIND_ICON.get(kind, "⚔")
        est = self.estimate(mv, player, per_hit=True)
        tcol = TYPE_COLOUR.get(mv.get("type", "physical"), "")
        hits = f" x{mv['hits']}" if mv.get("hits", 1) > 1 else ""
        if kind == "charge":
            left = it.get("left", 1)
            aoe = " all" if mv.get("aoe") else ""
            when = "THIS TURN — DEFEND!" if left <= 1 else "Break it or Defend when it lands"
            return (f"{_fg(255,90,60)}{_B}⚠ CHARGING: {name} [{left}]{_R} "
                    f"{tcol}~{est}{aoe}{_R} {_fg(255,200,80)}{when}{_R}")
        if kind == "stance":
            return f"{_fg(240,200,60)}{_B}{icon} {name}{_R} {_fg(240,200,60)}— {mv.get('hint', '')}{_R}"
        if kind == "heal":
            return f"{_fg(80,200,80)}{_B}{icon} {name}{_R} {_fg(80,200,80)}— will heal itself{_R}"
        if kind == "summon":
            return f"{_fg(235,140,45)}{_B}{icon} {name}{_R} {_fg(235,140,45)}— calls reinforcements{_R}"
        if kind == "shield":
            return f"{_fg(120,210,255)}{_B}{icon} {name}{_R} {_fg(120,210,255)}— restores its {self.shield_label.lower()}{_R}"
        if kind == "buff":
            return f"{_fg(220,140,40)}{_B}▲ {name}{_R} {_fg(220,140,40)}— powers up{_R}"
        extra = ""
        st = mv.get("status")
        if st:
            extra = f" +{st[0].upper()}"
        if mv.get("hint"):
            extra += f" {_fg(240,200,60)}({mv['hint']}){_R}"
        if mv.get("pierce"):
            extra += f" {_fg(240,200,60)}(GUARD BREAK — don't Defend){_R}"
        if kind == "drain_mp":
            extra += " (drains MP)"
        if kind == "steal":
            extra += " (steals gold)"
        if mv.get("aoe"):
            extra += " (hits everyone)"
        return f"{_fg(220,60,60)}{_B}{icon} {name}{_R} {tcol}~{est}{hits}{_R}{extra}"

    def enrage_text(self):
        if self.enraged:
            return f"{_fg(220,60,60)}{_B}ENRAGED +{self.enraged * 10}%{_R}"
        left = self.enrage_at - self.round
        if 0 < left <= 4:
            return f"{_fg(220,140,40)}Enrage in {left}{_R}"
        return ""

    def shield_text(self):
        if not self.shield_max:
            return ""
        if self.broken:
            return f"{_fg(255,215,0)}{_B}{self.shield_label} BROKEN{_R}"
        on, off = "◆" * self.shield, "◇" * (self.shield_max - self.shield)
        if self.shield_label == "HEADS":
            half = self.shield_max // 2
            pips = on + off
            pips = pips[:half] + " " + pips[half:]
        else:
            pips = on + off
        return f"{_fg(120,210,255)}{self.shield_label} {pips}{_R}"

    def weak_text(self):
        if not self.weak:
            return ""
        return "weak: " + " ".join(f"{TYPE_COLOUR.get(t, '')}{t}{_R}" for t in sorted(self.weak))

    # ── counters (resolved right after the hero acts) ─────────
    def resolve_counters(self, player):
        n, self._pending_counter = self._pending_counter, 0
        if not n or not self.is_alive() or not player.is_alive():
            return
        mv = MOVES.get(self.stance, {})
        dmg = int(self.total_atk() * 1.2) + random.randint(0, 4)
        actual = player.take_damage(dmg)
        print(_C(f"↺ {self.name} COUNTERS ({mv.get('name', 'counter')}) -> {actual} damage!"))
        if self.stance == "dk_aura":
            player.add_status(Burn(duration=2, damage=max(3, self.atk // 6)))

    # ── the boss turn ─────────────────────────────────────────
    def act(self, player, party=None, defending=False, base_def=None):
        """Execute this round's intent. `party` = alive companions."""
        party = [m for m in (party or []) if m.is_alive()]
        ctx = dict(player=player, party=party, defending=defending,
                   base_def=player.defense if base_def is None else base_def)
        for k in list(self.cooldowns):
            self.cooldowns[k] = max(0, self.cooldowns[k] - 1)
        if self.buff_turns > 0:
            self.buff_turns -= 1

        if self.broken:
            self.broken = False
            self.exposed = True
            self.shield = self.shield_max
            self.intent = None
            print(_C(f"{self.name} staggers back to its feet — {self.shield_label.lower()} restored."))
            return
        self.exposed = False

        if self.is_stunned():
            print(_C(f"{self.name} is stunned and loses its turn!"))
            self.stance = None
            return

        it = self.intent or {"id": "strike", "kind": "attack"}
        mid = it.get("id", "strike")
        mv = MOVES.get(mid, MOVES["strike"])

        if self.charge:
            self.charge["left"] -= 1
            if self.charge["left"] > 0:
                print(_C(f"⚠ {self.name} gathers power for {mv['name']}... "
                         f"[{self.charge['left']}]"))
                self._tick_enrage()
                return
            self.charge = None
            self._release(mid, mv, ctx)
        elif mv["kind"] == "stance":
            self.stance = None
            print(_C(f"{self.name} drops out of {mv['name']}."))
            self._attack(MOVES["strike"], ctx, scale=0.7)
        else:
            self._execute(mid, mv, ctx)

        if mv.get("cd"):
            self.cooldowns[mid] = mv["cd"]
        self.last_move = mid
        self.stance = None
        if self.passive.get("mp_drain") and player.is_alive() and player.mp > 0:
            amt = max(1, int(player.max_mp * self.passive["mp_drain"]))
            amt = min(amt, player.mp)
            player.mp -= amt
            print(_C(f"The cursed crown siphons {amt} MP from you."))
        self._tick_enrage()

    def _tick_enrage(self):
        if self.round >= self.enrage_at:
            self.enraged += 1
            if self.enraged == 1:
                print(_C(f"{self.name} grows ENRAGED — its attacks keep escalating!"))

    def _pick_target(self, ctx):
        return pick_target(ctx["player"], ctx["party"])

    def _attack(self, mv, ctx, scale=1.0, target=None, charged=False):
        """Hit one target with a move; returns total damage dealt."""
        player = ctx["player"]
        target = target or self._pick_target(ctx)
        total = 0
        for _ in range(max(1, mv.get("hits", 1))):
            if not target.is_alive():
                break
            if not charged and target.try_dodge():
                print(_C(f"{target.name} dodges {mv['name']}!"))
                continue
            mult = mv.get("mult", 1.0) * (CHARGE_MULT if charged else 1.0)
            base = int(self.total_atk() * mult * scale) + random.randint(-2, 3)
            crit, dmg = self.calc_crit(max(1, base)) if not charged else (False, max(1, base))
            tag = " [CRIT!]" if crit else ""
            is_hero = target is player
            if not is_hero and scale == 1.0:
                base = int(base * COMPANION_HIT)   # bosses focus their worst on the hero
            if is_hero and ctx["defending"] and mv.get("pierce"):
                player.defense = ctx["base_def"]
                dmg = int(dmg * 1.3)
                ctx["defending"] = False
                tag += " GUARD BREAK!"
            if is_hero and ctx["defending"]:
                # Defending halves boss blows; a braced charge is blunted hard
                dmg = int(dmg * (0.3 if charged else 0.5))
                tag += " (braced!)" if charged else " (guarded)"
            actual = target.take_damage(dmg)
            total += actual
            who = "" if is_hero else f" {target.name}"
            print(_C(f"{self.name} uses {mv['name']}{tag} ->{who} {actual} damage!"))
            self._apply_status(mv, target, ctx)
        if total and mv.get("lifesteal"):
            heal = int(total * mv["lifesteal"])
            self.hp = min(self.max_hp, self.hp + heal)
            print(_C(f"{self.name} drains {heal} HP!"))
        return total

    def _apply_status(self, mv, target, ctx):
        st = mv.get("status")
        if not st or not target.is_alive() or not hasattr(target, "add_status"):
            return
        name, turns = st
        power = max(3, int(self.atk * 0.12))
        if name == "stun":
            if target is ctx["player"] and ctx["defending"]:
                print(_C(f"You brace and resist being stunned!"))
                return
            if target is not ctx["player"]:
                return
            eff = Stun(duration=turns)
        elif name == "poison":
            eff = Poison(duration=turns, damage=power)
        elif name == "burn":
            eff = Burn(duration=turns, damage=power)
        elif name == "bleed":
            eff = Bleed(duration=turns, damage=power)
        elif name == "blind":
            if target is not ctx["player"]:
                return
            eff = Blind(duration=turns)
        else:
            return
        target.add_status(eff)

    def _release(self, mid, mv, ctx):
        print(_C(f"⚠ {self.name} unleashes {mv['name'].upper()}!"))
        self._strike_all(mv, ctx, charged=True) if mv.get("aoe") else \
            self._attack(mv, ctx, target=ctx["player"], charged=True)

    def _strike_all(self, mv, ctx, charged=False):
        self._attack(mv, ctx, target=ctx["player"], charged=charged)
        for m in ctx["party"]:
            if m.is_alive():
                self._attack(mv, ctx, scale=0.6, target=m, charged=charged)

    def _execute(self, mid, mv, ctx):
        kind = mv["kind"]
        player = ctx["player"]
        if kind == "attack":
            if mv.get("aoe"):
                self._strike_all(mv, ctx)
            else:
                tgt = player if (mv.get("pierce") or mv.get("status")) else None
                self._attack(mv, ctx, target=tgt)
        elif kind == "debuff":
            print(_C(f"{self.name} uses {mv['name']}!"))
            self._attack(mv, ctx, target=player)
        elif kind == "heal":
            if self.heals_left > 0:
                self.heals_left -= 1
                amt = int(self.max_hp * mv.get("heal", 0.15))
                self.hp = min(self.max_hp, self.hp + amt)
                print(_C(f"{self.name} uses {mv['name']} and recovers {amt} HP!"))
            else:
                self._attack(MOVES["strike"], ctx)
        elif kind == "buff":
            self.buff_mult = mv.get("buff", 1.2)
            self.buff_turns = mv.get("turns", 3)
            print(_C(f"{self.name} uses {mv['name']} — its attacks grow stronger!"))
        elif kind == "summon":
            lines = self._summon(mv.get("add", "Goblin"), mv.get("count", 1))
            print(_C(f"{self.name} uses {mv['name']}!"))
            for ln in lines:
                print(_C(ln))
            if not lines:
                self._attack(MOVES["strike"], ctx)
        elif kind == "shield":
            if self.shield_max:
                self.shield = self.shield_max
                print(_C(f"{self.name} uses {mv['name']} — {self.shield_label.lower()} fully restored!"))
        elif kind == "drain_mp":
            dealt = self._attack(mv, ctx, target=player)
            amt = min(player.mp, int(player.mp * mv.get("drain", 0.3)) + 4)
            if amt > 0:
                player.mp -= amt
                self.hp = min(self.max_hp, self.hp + amt * 2)
                print(_C(f"{mv['name']}: {amt} MP torn from you — {self.name} heals {amt * 2}!"))
        elif kind == "steal":
            dealt = self._attack(mv, ctx, target=player)
            gold = getattr(player, "gold", 0)
            if dealt and gold > 0:
                amt = min(gold, max(5, int(gold * mv.get("steal", 0.05))), 40 + self.level * 25)
                player.gold -= amt
                self.stolen_gold += amt
                print(_C(f"{self.name} lifts {amt} gold from your purse! (win to get it back)"))
        else:
            self._attack(MOVES["strike"], ctx)

    # ── compatibility: one complete legacy boss action ────────
    def use_boss_skill(self, target):
        if not self._prepared:
            self._prepared = True
        if self.intent is None:
            self.plan(target)
        self.act(target, [], False, target.defense)
        self.intent = None


# =============================================================
# TARGETING  (enemies also hit companions; warriors draw aggro)
# =============================================================

ROLE_AGGRO = {"warrior": 75, "tank": 75, "rogue": 30, "mage": 40, "healer": 45}


def pick_target(player, party=None):
    """Weighted random target: the hero or an alive companion.
    Prefers the companions module's own Party.pick_target(player) when present."""
    try:
        pt = getattr(getattr(player, "party", None), "pick_target", None)
        if callable(pt):
            t = pt(player)
            if t is not None and (t is player or (hasattr(t, "take_damage") and t.is_alive())):
                return t
    except Exception:
        pass
    cands = [(player, 100)]
    for m in party or []:
        try:
            if m.is_alive():
                cands.append((m, ROLE_AGGRO.get(getattr(m, "role", ""), 40)))
        except Exception:
            continue
    if len(cands) == 1:
        return player
    total = sum(w for _, w in cands)
    r = random.uniform(0, total)
    for t, w in cands:
        r -= w
        if r <= 0:
            return t
    return player


# =============================================================
# ZONE ENEMY POOLS
# NOTE: Dragon/Vaeltharion/Frost Dragon are REMOVED from all
#       random encounter pools. They are story-boss-only.
# =============================================================

ZONE_ENEMIES = {
    "plains":   ["Slime", "Goblin", "Wolf", "Bandit"],
    "forest":   ["Wolf", "Bandit", "Harpy", "Goblin"],
    "mountain": ["Stone Golem", "Harpy", "Rock Wolf", "Bandit"],
    "desert":   ["Sand Wyrm", "Scorpion", "Desert Raider", "Dust Imp"],
    "snow":     ["Ice Wolf", "Frost Wraith", "Snow Beast", "Ice Golem"],
    # Dungeon pools by floor — deeper = harder, NO dragons
    "dungeon":        ["Skeleton", "Cultist", "Shadow Beast", "Armored Knight"],
    "dungeon_deep":   ["Shadow Beast", "Armored Knight", "Cultist", "Dark Golem"],
    "dungeon_bottom": ["Death Knight", "Lich", "Void Stalker", "Armored Knight"],
    # Dragon scouts — unlocked only via story flag
    "dragon_territory": ["Dragon Scout", "Wyvern", "Dragon Cultist"],
    # Overhaul locations (towns' underworld, castles, demon citadel, desert kasbah)
    "town":     ["Alley Thief", "Cutthroat", "Bandit"],
    "castle":   ["Royal Guard"],
    "citadel":  ["Imp", "Demon Knight"],
    "kasbah":   ["Desert Assassin", "Sand Scorpion"],
}

# ── Stat multipliers per enemy ─────────────────────────────────
ENEMY_STATS = {
    "Slime":         dict(hp_m=0.5, atk_m=0.6, def_m=0.3, exp_m=0.6, gold_m=0.4),
    "Goblin":        dict(hp_m=0.7, atk_m=0.8, def_m=0.4, exp_m=0.8, gold_m=0.7),
    "Wolf":          dict(hp_m=0.9, atk_m=1.0, def_m=0.5, exp_m=1.0, gold_m=0.8, dodge=10),
    "Bandit":        dict(hp_m=1.0, atk_m=1.0, def_m=0.6, exp_m=1.1, gold_m=1.2, crit=12),
    "Harpy":         dict(hp_m=0.8, atk_m=1.2, def_m=0.3, exp_m=1.2, gold_m=0.9, dodge=14),
    "Stone Golem":   dict(hp_m=2.0, atk_m=0.9, def_m=2.0, exp_m=1.5, gold_m=1.2),
    "Rock Wolf":     dict(hp_m=1.1, atk_m=1.1, def_m=0.8, exp_m=1.1, gold_m=0.9),
    "Sand Wyrm":     dict(hp_m=1.4, atk_m=1.3, def_m=0.7, exp_m=1.4, gold_m=1.3),
    "Scorpion":      dict(hp_m=0.9, atk_m=1.1, def_m=0.6, exp_m=1.0, gold_m=0.8),
    "Desert Raider": dict(hp_m=1.0, atk_m=1.2, def_m=0.5, exp_m=1.2, gold_m=1.4),
    "Dust Imp":      dict(hp_m=0.7, atk_m=0.9, def_m=0.3, exp_m=0.9, gold_m=0.6),
    "Ice Wolf":      dict(hp_m=1.1, atk_m=1.2, def_m=0.6, exp_m=1.3, gold_m=1.0, dodge=8),
    "Frost Wraith":  dict(hp_m=0.9, atk_m=1.4, def_m=0.3, exp_m=1.5, gold_m=1.2, dodge=15),
    "Snow Beast":    dict(hp_m=1.5, atk_m=1.1, def_m=0.8, exp_m=1.4, gold_m=1.0),
    "Ice Golem":     dict(hp_m=2.2, atk_m=0.9, def_m=2.2, exp_m=1.7, gold_m=1.3),
    "Skeleton":      dict(hp_m=0.9, atk_m=0.9, def_m=0.7, exp_m=1.0, gold_m=0.8),
    "Cultist":       dict(hp_m=1.0, atk_m=1.1, def_m=0.5, exp_m=1.2, gold_m=1.0),
    "Shadow Beast":  dict(hp_m=1.3, atk_m=1.4, def_m=0.6, exp_m=1.6, gold_m=1.3, dodge=12, crit=15),
    "Armored Knight":dict(hp_m=1.5, atk_m=1.2, def_m=1.8, exp_m=1.8, gold_m=1.5),
    # Deep dungeon enemies
    "Dark Golem":    dict(hp_m=2.4, atk_m=1.1, def_m=2.4, exp_m=2.2, gold_m=1.8),
    "Death Knight":  dict(hp_m=1.8, atk_m=1.6, def_m=1.4, exp_m=2.5, gold_m=2.0, crit=18),
    "Lich":          dict(hp_m=1.2, atk_m=1.8, def_m=0.8, exp_m=2.8, gold_m=2.2, dodge=8),
    "Void Stalker":  dict(hp_m=1.4, atk_m=1.7, def_m=0.7, exp_m=2.6, gold_m=2.0, dodge=18, crit=14),
    # Dragon territory (story-gated)
    "Dragon Scout":  dict(hp_m=1.8, atk_m=1.6, def_m=1.0, exp_m=3.0, gold_m=2.5, crit=10),
    "Wyvern":        dict(hp_m=2.0, atk_m=1.5, def_m=1.2, exp_m=3.2, gold_m=2.8, dodge=8),
    "Dragon Cultist":dict(hp_m=1.1, atk_m=1.4, def_m=0.6, exp_m=2.8, gold_m=2.2),
    # Overhaul elites (towns, castles, citadel, kasbah)
    "Alley Thief":   dict(hp_m=0.8, atk_m=0.9, def_m=0.4, exp_m=0.9, gold_m=1.3, dodge=15),
    "Cutthroat":     dict(hp_m=1.0, atk_m=1.3, def_m=0.5, exp_m=1.3, gold_m=1.3, crit=18),
    "Royal Guard":   dict(hp_m=1.5, atk_m=1.2, def_m=1.8, exp_m=1.6, gold_m=1.4),
    "Imp":           dict(hp_m=0.6, atk_m=1.0, def_m=0.3, exp_m=0.8, gold_m=0.5, dodge=14),
    "Desert Assassin":dict(hp_m=1.0, atk_m=1.5, def_m=0.5, exp_m=1.6, gold_m=1.5, crit=20, dodge=15),
    "Sand Scorpion": dict(hp_m=1.0, atk_m=1.1, def_m=0.9, exp_m=1.0, gold_m=0.7),
    "Demon Knight":  dict(hp_m=1.9, atk_m=1.6, def_m=1.6, exp_m=2.4, gold_m=1.8, crit=12),
    # Boss adds (summoned only)
    "Bandit Thug":   dict(hp_m=0.9, atk_m=0.9, def_m=0.6, exp_m=0.8, gold_m=0.8),
    "Mirror Image":  dict(hp_m=0.35, atk_m=0.6, def_m=0.1, exp_m=0.2, gold_m=0.0),
}

# Elemental identity and on-hit traits.  These only matter when the incoming
# hit carries a type (skills, companions, bombs) — basic fights stay snappy.
ENEMY_TRAITS = {
    "Slime":        dict(weak=["fire"]),
    "Skeleton":     dict(weak=["holy"], resist={"poison": 0.5}),
    "Lich":         dict(weak=["holy"], resist={"shadow": 0.5}, dtype="shadow"),
    "Death Knight": dict(weak=["holy"], dtype="shadow"),
    "Shadow Beast": dict(weak=["holy"], dtype="shadow"),
    "Void Stalker": dict(weak=["holy"], resist={"shadow": 0.5}, dtype="shadow"),
    "Ice Wolf":     dict(weak=["fire"], resist={"ice": 0.5}),
    "Frost Wraith": dict(weak=["fire"], resist={"ice": 0.5}, dtype="ice"),
    "Ice Golem":    dict(weak=["fire"], resist={"ice": 0.3, "physical": 0.85}),
    "Stone Golem":  dict(weak=["arcane"], resist={"physical": 0.85}),
    "Dark Golem":   dict(weak=["holy"], resist={"physical": 0.85}),
    # Elites
    "Alley Thief":  dict(traits={"steal": (30, 0.04)}),
    "Cutthroat":    dict(traits={"bleed": (30, 2)}),
    "Bandit":       dict(traits={"steal": (15, 0.03)}),
    "Royal Guard":  dict(resist={"physical": 0.85}, weak=["shadow"]),
    "Imp":          dict(weak=["ice", "holy"], resist={"fire": 0.5}, dtype="fire",
                         traits={"burn": (25, 2)}),
    "Desert Assassin": dict(traits={"poison": (35, 3)}),
    "Sand Scorpion":   dict(weak=["arcane"], resist={"poison": 0.3}, traits={"poison": (30, 3)}),
    "Demon Knight": dict(weak=["holy", "ice"], resist={"fire": 0.5}, dtype="fire",
                         traits={"burn": (25, 2)}),
    "Bandit Thug":  dict(traits={"steal": (15, 0.02)}),
    "Mirror Image": dict(weak=["physical", "shadow"], dtype="arcane"),
}

# ── PROGRESSIVE difficulty multiplier per dungeon floor ────────
def _floor_scale(floor: int) -> float:
    """Returns a bonus multiplier. Floor 1=0, Floor 3=+0.2, Floor 5=+0.5 etc."""
    return 1.0 + max(0, floor - 1) * 0.15


def _apply_traits(enemy):
    tr = ENEMY_TRAITS.get(enemy.name)
    if tr:
        enemy.weak = set(tr.get("weak", []))
        enemy.resist = dict(tr.get("resist", {}))
        enemy.traits = dict(tr.get("traits", {}))
        enemy.dtype = tr.get("dtype", "physical")
    return enemy


def generate_enemy(zone="plains", danger=1, player_level=1, floor=1, name=None):
    """
    Generate a scaled enemy.
    zone: see ZONE_ENEMIES keys.
    danger: 1–5 base danger rating of the location.
    player_level: scales stats.
    floor: dungeon floor depth (1=surface, increases as deeper).
    name: force a specific enemy type (e.g. the overworld sprite you bumped into).
    """
    names = ZONE_ENEMIES.get(zone, ["Goblin"])
    name  = name or random.choice(names)
    stats = ENEMY_STATS.get(name, {})

    floor_mult = _floor_scale(floor)
    # Level now matters much more than before (0.3/level made enemies trivial
    # after the first few levels while the player gained +15 HP / +2 ATK each).
    scale = (danger * 0.8 + player_level * 0.9) * floor_mult

    base_hp  = int((25 + scale * 16) * stats.get("hp_m",  1.0)) + random.randint(0, 6)
    base_atk = int((5  + scale * 2.8) * stats.get("atk_m", 1.0)) + random.randint(0, 2)
    base_def = int((1  + scale * 1.0)* stats.get("def_m", 1.0))
    base_exp = int((10 + scale * 8)  * stats.get("exp_m", 1.0))
    base_gld = int((5  + scale * 5)  * stats.get("gold_m",1.0))

    e = Enemy(
        name, base_hp, base_atk, base_def,
        base_exp, base_gld,
        crit_chance  = stats.get("crit",  5),
        dodge_chance = stats.get("dodge", 3),
    )
    return _apply_traits(e)


def make_add(name, level=1):
    """A boss minion: weaker than a normal enemy, gives no rewards."""
    e = generate_enemy("plains", 2, max(1, level), name=name)
    e.max_hp = e.hp = max(8, int(e.max_hp * 0.35))
    e.atk = max(2, int(e.atk * 0.5))
    e.exp_reward = e.gold_reward = 0
    e.is_add = True
    return e


def generate_dungeon_enemy(danger=1, player_level=1, floor=1):
    """
    Select the correct dungeon zone based on floor depth.
    Floor 1–2: normal dungeon. Floor 3–4: deep. Floor 5+: bottom.
    """
    if floor >= 5:
        zone = "dungeon_bottom"
    elif floor >= 3:
        zone = "dungeon_deep"
    else:
        zone = "dungeon"
    return generate_enemy(zone, danger, player_level, floor)


# =============================================================
# DRAGON SCOUT GENERATION (story-gated)
# =============================================================

def generate_dragon_scout(player_level=1):
    """
    Used only when player has story flag 'dragon_scouts_active'.
    These are enemies in the dragon's territory before the final boss.
    """
    return generate_enemy("dragon_territory", danger=4, player_level=player_level, floor=1)


# =============================================================
# BOSS DEFINITIONS
#   Fixed stats are used only when create_boss() gets no player level.
#   "boss_skills" lists move names (shown in the codex bestiary).
# =============================================================

def _skill_names(name):
    kit = BOSS_KITS.get(name, _DEFAULT_KIT)
    ids = [m for m, _ in kit.get("moves", [])]
    for ph in kit.get("phases", []):
        ids += [m for m, _ in ph.get("add", [])]
    out = []
    for i in ids:
        n = MOVES.get(i, {}).get("name")
        if n and n not in out:
            out.append(n)
    return out


BOSS_DEFS = {
    "Goblin King":        dict(hp=280,  atk=28, defense=8,  exp_reward=600,  gold_reward=400),
    "Frost Dragon":       dict(hp=500,  atk=40, defense=15, exp_reward=1200, gold_reward=800),
    "Shadow Lord":        dict(hp=650,  atk=50, defense=18, exp_reward=2000, gold_reward=1200),
    "Dragon":             dict(hp=1200, atk=70, defense=25, exp_reward=8000, gold_reward=3000),
    "Vaeltharion":        dict(hp=1200, atk=70, defense=25, exp_reward=8000, gold_reward=3000),
    "Dungeon Warden":     dict(hp=400,  atk=35, defense=12, exp_reward=900,  gold_reward=550),
    "Shadow Lich":        dict(hp=450,  atk=42, defense=10, exp_reward=1000, gold_reward=650),
    "Demon Lord Kharzul": dict(hp=1100, atk=66, defense=24, exp_reward=6000, gold_reward=2500),
    "Hellhound Warden":   dict(hp=600,  atk=48, defense=16, exp_reward=1600, gold_reward=900),
    "Sand Djinn Azhar":   dict(hp=650,  atk=50, defense=14, exp_reward=1800, gold_reward=1100),
    "Scorpion Matriarch": dict(hp=600,  atk=46, defense=18, exp_reward=1600, gold_reward=900),
    "The Hollow Regent":  dict(hp=1000, atk=62, defense=22, exp_reward=5000, gold_reward=2500),
    "Archmage Veyl the Unbound": dict(hp=700, atk=54, defense=14, exp_reward=2200, gold_reward=1300),
    "Bandit King Rourke": dict(hp=380,  atk=32, defense=10, exp_reward=800,  gold_reward=700),
    "Thieves' Guildmaster": dict(hp=420, atk=34, defense=10, exp_reward=900, gold_reward=800),
}
for _n, _d in BOSS_DEFS.items():
    _d["boss_skills"] = _skill_names(_n)

# These bosses CANNOT appear as random encounters — ever.
STORY_ONLY_BOSSES = {"Dragon", "Vaeltharion"}
# Bosses tied to specific places (citadel, kasbah, capital, hideout, guild)
PLACE_BOSSES = {"Demon Lord Kharzul", "Hellhound Warden", "Sand Djinn Azhar",
                "Scorpion Matriarch", "The Hollow Regent", "Archmage Veyl the Unbound",
                "Bandit King Rourke", "Thieves' Guildmaster"}

# Relative toughness of each boss. Stats are derived from the player's level
# so a boss is always a real fight but never an unwinnable wall.
BOSS_POWER = {
    "Bandit King Rourke":   0.95,
    "Goblin King":          1.00,
    "Thieves' Guildmaster": 1.00,
    "Dungeon Warden":       1.10,
    "Shadow Lich":          1.15,
    "Scorpion Matriarch":   1.15,
    "Hellhound Warden":     1.20,
    "Frost Dragon":         1.25,
    "Sand Djinn Azhar":     1.25,
    "Archmage Veyl the Unbound": 1.25,
    "Shadow Lord":          1.30,
    "Dragon":               1.40,
    "Vaeltharion":          1.40,
    "The Hollow Regent":    1.45,
    "Demon Lord Kharzul":   1.50,
}

# Regular dungeons never roll these
RANDOM_BOSS_POOL = [n for n in BOSS_DEFS
                    if n not in STORY_ONLY_BOSSES and n not in PLACE_BOSSES]


def boss_stats(name, player_level):
    """Level-scaled stats.  HP and ATK grow quadratically so late bosses keep
    pace with awakened, well-geared heroes; the first few levels are softened
    so an early dungeon boss is beatable by a fresh character."""
    lv = max(1, player_level)
    p  = BOSS_POWER.get(name, 1.0)
    soft = min(1.0, 0.6 + 0.08 * lv)
    # Mid-game relief: heroes are weakest relative to bosses just before they
    # awaken (~Lv 20), so the curve dips around Lv 16.
    soft *= 1.0 - 0.12 * max(0.0, 1.0 - abs(lv - 16) / 9.0)
    return dict(
        hp          = int((269 + 0.1 * lv + 1.30 * lv * lv) * soft * p ** 0.85),
        atk         = int((18.2 + 1.35 * lv + 0.090 * lv * lv) * soft * p ** 0.5),
        defense     = int((4 + 1.1 * lv) * p ** 0.5),
        exp_reward  = int((150 + 55 * lv) * p),
        gold_reward = int((110 + 36 * lv) * p),
    )


def create_boss(name, player_level=None):
    d = dict(BOSS_DEFS.get(name, BOSS_DEFS["Goblin King"]))
    level = None
    if player_level is not None:
        level = max(1, player_level)
        d.update(boss_stats(name, level))
        kit = BOSS_KITS.get(name) or {}
        d["hp"] = int(d["hp"] * kit.get("hp", 1.0))
        d["atk"] = int(d["atk"] * kit.get("atk", 1.0))
    d["boss_skills"] = list(d.get("boss_skills", []))
    return BossEnemy(name, kit=BOSS_KITS.get(name), level=level, **d)


def get_floor_miniboss(floor: int):
    """
    Returns the name of the mini-boss that guards a dungeon floor end.
    Floor 3: Dungeon Warden. Floor 5+: Shadow Lich.
    """
    if floor >= 5:
        return "Shadow Lich"
    return "Dungeon Warden"
