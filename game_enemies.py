"""
game_enemies.py — Enemy definitions, generation, and boss management.

FIXES:
  • Dragon (Vaeltharion) and Frost Dragon NO LONGER appear in random dungeon
    encounters — they are story-only bosses triggered by main.py / game_stories.py.
  • Dragon Scouts added — weaker dragon-type enemies for the main story pregame.
  • Progressive difficulty: enemy stats scale harder in deep/high-danger areas.
"""

import random, copy
from game_items import StatusEffect, Poison, Burn, Regen, Stun, roll_drops

def _C(text=""):
    from game_term import C
    return C(text)

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

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, dmg):
        actual = max(1, dmg - self.defense // 4)
        self.hp = max(0, self.hp - actual)
        return actual

    def try_dodge(self):
        return random.randint(1, 100) <= self.dodge_chance

    def calc_crit(self, base):
        if random.randint(1, 100) <= self.crit_chance:
            return True, int(base * 1.5)
        return False, base

    def add_status(self, effect):
        for e in self.status_effects:
            if e.name == effect.name:
                e.duration = max(e.duration, effect.duration)
                return
        self.status_effects.append(effect)

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
        print(_C(f"{self.name} attacks{tag} -> {actual} damage!"))
        return actual

    def hp_bar(self, width=20):
        filled = int(width * self.hp / self.max_hp)
        bar = "[" + "#" * filled + "-" * (width - filled) + "]"
        return f"{bar} {self.hp}/{self.max_hp}"

    def status_line(self):
        if not self.status_effects:
            return ""
        return "  (" + ", ".join(str(e) for e in self.status_effects) + ")"


# =============================================================
# BOSS ENEMY
# =============================================================

class BossEnemy(Enemy):
    def __init__(self, name, hp, atk, defense=10, exp_reward=500,
                 gold_reward=300, boss_skills=None):
        super().__init__(name, hp, atk, defense, exp_reward, gold_reward,
                         crit_chance=20, dodge_chance=10, enemy_class="BOSS")
        self.boss_skills = boss_skills or []
        self.phase = 1

    SKILL_CHANCE = 40   # % of turns a boss uses a special move (was 100%)

    def use_boss_skill(self, target):
        if self.hp < self.max_hp * 0.5 and self.phase == 1:
            self.phase = 2
            self.atk = int(self.atk * 1.25)
            print(_C(f"*** {self.name} ENTERS PHASE 2 — power surges! ***"))

        if not self.boss_skills or random.randint(1, 100) > self.SKILL_CHANCE:
            self.basic_attack(target)
            return

        skill = random.choice(self.boss_skills)
        # Roar cannot stun-lock: re-roll it if the target is already stunned
        if skill == "roar" and any(e.name == "Stun" for e in target.status_effects):
            skill = "power_strike"
        scale = max(1, self.atk // 10)   # status damage grows with the boss
        if skill == "power_strike":
            dmg = int(self.atk * 1.6) + random.randint(3, 8)
            actual = target.take_damage(dmg)
            print(_C(f"{self.name} uses POWER STRIKE -> {actual} damage!"))
        elif skill == "venom":
            target.add_status(Poison(duration=3, damage=3 + scale))
            print(_C(f"{self.name} spits venom! (Poison)"))
        elif skill == "roar":
            target.add_status(Stun(duration=1))
            print(_C(f"{self.name} ROARS — you are stunned!"))
        elif skill == "drain":
            dmg = max(1, self.atk)
            actual = target.take_damage(dmg)
            self.hp = min(self.max_hp, self.hp + actual // 2)
            print(_C(f"{self.name} DRAINS {actual} HP from you!"))
        elif skill == "fire_breath":
            dmg = self.atk + random.randint(5, 15)
            actual = target.take_damage(dmg)
            target.add_status(Burn(duration=3, damage=3 + scale))
            print(_C(f"{self.name} breathes FIRE — {actual} damage + BURN!"))
        elif skill == "wing_slam":
            dmg = int(self.atk * 1.4)
            actual = target.take_damage(dmg)
            print(_C(f"{self.name} WING SLAMS for {actual} damage!"))
        else:
            self.basic_attack(target)


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
}

# ── PROGRESSIVE difficulty multiplier per dungeon floor ────────
def _floor_scale(floor: int) -> float:
    """Returns a bonus multiplier. Floor 1=0, Floor 3=+0.2, Floor 5=+0.5 etc."""
    return 1.0 + max(0, floor - 1) * 0.15


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

    return Enemy(
        name, base_hp, base_atk, base_def,
        base_exp, base_gld,
        crit_chance  = stats.get("crit",  5),
        dodge_chance = stats.get("dodge", 3),
    )


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
# BOSS DEFINITIONS — story bosses only
# =============================================================

BOSS_DEFS = {
    "Goblin King": dict(
        hp=280, atk=28, defense=8, exp_reward=600, gold_reward=400,
        boss_skills=["power_strike", "roar", "power_strike"],
    ),
    "Frost Dragon": dict(
        # Frost Dragon is a mid-game STORY boss, not a random encounter
        hp=500, atk=40, defense=15, exp_reward=1200, gold_reward=800,
        boss_skills=["power_strike", "venom", "roar", "drain", "fire_breath"],
    ),
    "Shadow Lord": dict(
        hp=650, atk=50, defense=18, exp_reward=2000, gold_reward=1200,
        boss_skills=["power_strike", "drain", "roar", "venom"],
    ),
    "Dragon": dict(
        # Vaeltharion — FINAL BOSS ONLY. Never spawned in dungeons.
        hp=1200, atk=70, defense=25, exp_reward=8000, gold_reward=3000,
        boss_skills=["power_strike", "venom", "roar", "drain", "fire_breath", "wing_slam"],
    ),
    "Vaeltharion": dict(
        hp=1200, atk=70, defense=25, exp_reward=8000, gold_reward=3000,
        boss_skills=["power_strike", "venom", "roar", "drain", "fire_breath", "wing_slam"],
    ),
    # Mini-boss for dungeon floors 3+
    "Dungeon Warden": dict(
        hp=400, atk=35, defense=12, exp_reward=900, gold_reward=550,
        boss_skills=["power_strike", "roar", "drain"],
    ),
    "Shadow Lich": dict(
        hp=450, atk=42, defense=10, exp_reward=1000, gold_reward=650,
        boss_skills=["power_strike", "venom", "drain"],
    ),
}

# These bosses CANNOT appear as random encounters — ever.
STORY_ONLY_BOSSES = {"Dragon", "Vaeltharion"}

# Relative toughness of each boss. Stats are derived from the player's level
# so a boss is always a real fight but never an unwinnable wall (the old fixed
# stats meant a Lv 3 hero could meet a 1200 HP dragon in their first dungeon).
BOSS_POWER = {
    "Goblin King":    1.00,
    "Dungeon Warden": 1.10,
    "Shadow Lich":    1.15,
    "Frost Dragon":   1.25,
    "Shadow Lord":    1.30,
    "Dragon":         1.38,
    "Vaeltharion":    1.38,
}

# Regular dungeons never roll these
RANDOM_BOSS_POOL = [n for n in BOSS_DEFS if n not in STORY_ONLY_BOSSES]


def create_boss(name, player_level=None):
    d = dict(BOSS_DEFS.get(name, BOSS_DEFS["Goblin King"]))
    if player_level is not None:
        lv = max(1, player_level)
        p  = BOSS_POWER.get(name, 1.0)
        # Power scales HP fully but ATK only by its square root: tougher
        # bosses take longer to kill without one-shotting the player.
        d["hp"]          = int((110 + 24 * lv) * p)
        d["atk"]         = int((9 + 2.9 * lv) * p ** 0.5)
        d["defense"]     = int((4 + 1.0 * lv) * p ** 0.5)
        d["exp_reward"]  = int((120 + 45 * lv) * p)
        d["gold_reward"] = int((90 + 30 * lv) * p)
    return BossEnemy(name, **d)


def get_floor_miniboss(floor: int):
    """
    Returns the name of the mini-boss that guards a dungeon floor end.
    Floor 3: Dungeon Warden. Floor 5+: Shadow Lich.
    """
    if floor >= 5:
        return "Shadow Lich"
    return "Dungeon Warden"
