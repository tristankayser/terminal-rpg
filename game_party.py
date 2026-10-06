"""
game_party.py — Party system for Terminal-RPG.
  • 20 recruitable companions spread across all continents
  • Companion customization: rename, reassign nickname, colour marker
  • Healer companions auto-heal party members in combat
  • Clan system: found a clan, collect passive income, upgrade clan hall
"""

import random, os
from game_term import C, div, clr, W
from game_lang import T, LANG

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60);     _CYAN=_fg(80,220,220)
_YELL=_fg(240,200,60); _ORAN=_fg(220,140,40);   _PURP=_fg(180,80,220)
_PINK=_fg(255,150,200);_BLUE=_fg(80,140,255)

MAX_PARTY = 3

# ── Companion definitions — 20 across 5 continents ──────────────

COMPANION_DEFS = [
    # AELORIA
    dict(id="aldric",     name="Aldric",     title="Knight of Greenveil", town="Greenveil",
         continent="AELORIA",   role="warrior",
         hp_bonus=40, atk_bonus=8, def_bonus=5, mp_bonus=0,
         passive="Bulwark: +5 DEF to party while alive",
         hire_cost=80,
         dialogue=[
             "I swore to protect the innocent. You count, I suppose.",
             "My sword arm is yours. Let's move.",
             "Greenveil needs heroes. Glad I found one.",
             "Watch your flanks. I'll take the front.",
             "Victory or death. I prefer victory.",
         ]),
    dict(id="lyra",       name="Lyra",       title="Forest Scout", town="Ironmoor",
         continent="AELORIA",   role="rogue",
         hp_bonus=15, atk_bonus=12, def_bonus=2, mp_bonus=10,
         passive="Keen Eye: +10% crit for whole party",
         hire_cost=90,
         dialogue=[
             "I know every path in this forest. Follow me quietly.",
             "Stealth is the only armour you truly need.",
             "Did you hear that? Something's following us.",
             "I'll scout ahead. Don't move until I whistle.",
             "My arrows find their mark even in the dark.",
         ]),
    dict(id="mira",       name="Mira",       title="Herbalist Healer", town="Greenveil",
         continent="AELORIA",   role="healer",
         hp_bonus=10, atk_bonus=2, def_bonus=2, mp_bonus=50,
         passive="Field Medicine: heals lowest HP ally each round",
         hire_cost=100,
         heal_power=30,
         dialogue=[
             "I've patched up worse. Hold still.",
             "My herbs can cure most things. Almost.",
             "You look terrible. Drink this.",
             "Healing is an art. And I am very good at my craft.",
             "Stay close. I can't heal what I can't see.",
         ]),

    # IRONSPIRE
    dict(id="kael",       name="Kael",       title="Desert Drifter", town="Sandreach",
         continent="IRONSPIRE", role="rogue",
         hp_bonus=20, atk_bonus=14, def_bonus=1, mp_bonus=15,
         passive="Sand Step: enemy accuracy -8%",
         hire_cost=110,
         dialogue=[
             "Gold first. Loyalty second. That's the desert way.",
             "The sand hides many things. Including me.",
             "I've survived worse than this. Probably.",
             "Don't get between me and the exit.",
             "I know people in Sandreach who can help. For a price.",
         ]),
    dict(id="gorath",     name="Gorath",     title="Iron Miner", town="Stonehelm",
         continent="IRONSPIRE", role="warrior",
         hp_bonus=60, atk_bonus=6, def_bonus=8, mp_bonus=0,
         passive="Iron Grip: +15 max HP to party",
         hire_cost=95,
         dialogue=[
             "Aye, I can swing a pickaxe AND a sword.",
             "Give me a minute. These legs aren't what they used to be.",
             "Stone doesn't lie. Neither do I.",
             "I've seen deeper darkness in the mines. This is fine.",
             "Stay behind me. I've got the thickest skull here.",
         ]),
    dict(id="zephyr",     name="Zephyr",     title="Wind Mage", town="Ironmoor",
         continent="IRONSPIRE", role="mage",
         hp_bonus=5, atk_bonus=10, def_bonus=0, mp_bonus=60,
         passive="Tailwind: party moves faster, +1 escape chance",
         hire_cost=130,
         dialogue=[
             "The wind whispers secrets to those who listen.",
             "I've mastered three winds. The fourth still eludes me.",
             "My magic isn't flashy. It simply works.",
             "Don't blink. Wind moves faster than you.",
             "The storms of Ironspire forged my resolve.",
         ]),

    # FROSTHEIM
    dict(id="seraphine",  name="Seraphine",  title="Ice Witch", town="Frostheim",
         continent="FROSTHEIM", role="mage",
         hp_bonus=10, atk_bonus=15, def_bonus=0, mp_bonus=70,
         passive="Frost Aura: enemies lose 5 ATK (frozen aura)",
         hire_cost=150,
         dialogue=[
             "The cold doesn't bother me. You might though.",
             "I froze a troll solid once. He's still there.",
             "Every snowflake has a story. This blizzard tells mine.",
             "Don't touch the staff. Please.",
             "Frostheim's warmth is within, apparently.",
         ]),
    dict(id="bramwyn",    name="Bramwyn",    title="Frost Knight", town="Glacierhold",
         continent="FROSTHEIM", role="warrior",
         hp_bonus=55, atk_bonus=9, def_bonus=10, mp_bonus=5,
         passive="Permafrost: +10% chance to block incoming hits",
         hire_cost=140,
         dialogue=[
             "The cold is my shield. Do not question it.",
             "I trained for fifteen winters on this glacier.",
             "Glacierhold produces the finest knights. I am the finest.",
             "We push forward. The cold will follow.",
             "In Frostheim, we do not retreat. We advance differently.",
         ]),
    dict(id="solenne",    name="Solenne",    title="Blizzard Healer", town="Frostheim",
         continent="FROSTHEIM", role="healer",
         hp_bonus=15, atk_bonus=3, def_bonus=3, mp_bonus=55,
         passive="Icebloom Mend: heals 15 HP to party after every battle",
         hire_cost=160,
         heal_power=35,
         dialogue=[
             "Ice and healing go together. Trust me.",
             "A cool head and a warm heart. That's the Frostheim way.",
             "I've mended wounds in blizzards. This is calm.",
             "Your HP is concerning. Drink the vial.",
             "Even the hardest frost yields to care.",
         ]),

    # ASH SANDS
    dict(id="thalia",     name="Thalia",     title="Dune Dancer", town="Oasis Keep",
         continent="ASH SANDS", role="rogue",
         hp_bonus=25, atk_bonus=16, def_bonus=2, mp_bonus=20,
         passive="Mirage: 15% dodge bonus",
         hire_cost=120,
         dialogue=[
             "The desert kills the slow. I am not slow.",
             "Watch my feet. The dance decides who dies.",
             "I've crossed the Ash Sands alone. Three times.",
             "Pretty weapons matter less than fast ones.",
             "Sand gets everywhere. So do my blades.",
         ]),
    dict(id="rashid",     name="Rashid",     title="Sand Mage", town="Sandreach",
         continent="ASH SANDS", role="mage",
         hp_bonus=8, atk_bonus=11, def_bonus=0, mp_bonus=65,
         passive="Sandstorm: enemies have -10% hit accuracy",
         hire_cost=135,
         dialogue=[
             "Sand is everywhere. Sand is everything.",
             "They call it a wasteland. I call it home.",
             "My spells carry the sting of a thousand grains.",
             "The desert has its own magic. Ancient and merciless.",
             "Never underestimate what hides beneath the dunes.",
         ]),
    dict(id="nur",        name="Nur",        title="Desert Cleric", town="Oasis Keep",
         continent="ASH SANDS", role="healer",
         hp_bonus=20, atk_bonus=4, def_bonus=4, mp_bonus=45,
         passive="Oasis Blessing: restore 10 MP to party after combat",
         hire_cost=115,
         heal_power=25,
         dialogue=[
             "The oasis gives life. So shall I.",
             "Faith is armour. Mine is well-fitted.",
             "I've healed warriors, merchants, and one very large camel.",
             "The desert heat is no obstacle to divine mercy.",
             "Follow the star. I'll keep you alive until we get there.",
         ]),

    # SOUTH ISLES
    dict(id="brennan",    name="Brennan",    title="Sea Brawler", town="Hammerfast",
         continent="SOUTH ISLES", role="warrior",
         hp_bonus=50, atk_bonus=11, def_bonus=6, mp_bonus=0,
         passive="Sea Legs: immune to terrain movement penalties",
         hire_cost=105,
         dialogue=[
             "I've brawled in every port from here to the north isles.",
             "My fists are my weapons. Don't let the size fool you.",
             "The sea hardens you. Look at me. Very hard.",
             "Pay me fair and I'll die for you. Simple as that.",
             "First rule of a sea fight: hit first, hit hard.",
         ]),
    dict(id="coral",      name="Coral",      title="Siren Scholar", town="Seaview",
         continent="SOUTH ISLES", role="mage",
         hp_bonus=10, atk_bonus=13, def_bonus=0, mp_bonus=60,
         passive="Siren Song: enemies are distracted, -5 ATK",
         hire_cost=140,
         dialogue=[
             "Knowledge is power. I have a great deal of both.",
             "The seas hold secrets older than any kingdom.",
             "Don't be distracted by my voice. Others have been.",
             "Magic flows like water. I am very good at water.",
             "The Siren Library in Seaview is magnificent. Miss it already.",
         ]),
    dict(id="petra",      name="Petra",      title="Tide Healer", town="Seaview",
         continent="SOUTH ISLES", role="healer",
         hp_bonus=18, atk_bonus=3, def_bonus=5, mp_bonus=50,
         passive="Tidal Mend: heal scales with party damage taken each round",
         hire_cost=155,
         heal_power=28,
         dialogue=[
             "The tide heals all things. Given enough time.",
             "I've stitched sailors back together mid-storm.",
             "You're lucky I'm here. Very lucky.",
             "The sea provides. I simply channel it.",
             "My healing isn't magic — it's dedication. Mostly.",
         ]),

    # WANDERERS (no fixed town)
    dict(id="rex",        name="Rex",        title="Wandering Swordmaster", town="Random",
         continent="ANY",  role="warrior",
         hp_bonus=45, atk_bonus=18, def_bonus=4, mp_bonus=10,
         passive="Wanderer's Edge: +15% crit chance",
         hire_cost=200,
         dialogue=[
             "I go where the wind takes me. Today it brought me to you.",
             "Don't ask where I've been. It's classified.",
             "I've faced dragons before. Twice.",
             "No guild. No master. Just the road.",
             "I fight for coin and the occasional interesting adventure.",
         ]),
    dict(id="vex",        name="Vex",        title="Void Rogue", town="Random",
         continent="ANY",  role="rogue",
         hp_bonus=20, atk_bonus=20, def_bonus=2, mp_bonus=25,
         passive="Void Step: teleport behind enemy, 25% bonus first-strike damage",
         hire_cost=220,
         dialogue=[
             "You can't see me unless I want you to.",
             "The void calls. I answer. Then bill someone.",
             "Don't follow me. Seriously. Stop.",
             "I've stolen from kings. You seem nicer.",
             "Death? Pfft. I've been there. Got bored.",
         ]),
    dict(id="elara",      name="Elara",      title="Arcane Wanderer", town="Random",
         continent="ANY",  role="mage",
         hp_bonus=5, atk_bonus=18, def_bonus=0, mp_bonus=80,
         passive="Arcane Overflow: spells deal +10% damage when MP > 50%",
         hire_cost=210,
         dialogue=[
             "I've studied in seven academies. Left them all.",
             "Theory is overrated. Results matter.",
             "This staff has seen three continents. Wants a fourth.",
             "Do not ask me to explain the math. Just trust the explosion.",
             "Magic is limitless. My patience isn't.",
         ]),
    dict(id="magnus",     name="Magnus",     title="Grand Paladin", town="Random",
         continent="ANY",  role="healer",
         hp_bonus=50, atk_bonus=8, def_bonus=8, mp_bonus=40,
         passive="Holy Aura: all party members regen 5 HP per round",
         hire_cost=250,
         heal_power=40,
         dialogue=[
             "The light does not abandon us. Neither shall I.",
             "I've led armies. A small party is refreshing.",
             "Heal first. Then smite. In that order.",
             "My order disbanded. Their loss. Your gain.",
             "The divine favours the prepared. Let us be prepared.",
         ]),
    dict(id="yuki",       name="Yuki",       title="Storm Monk", town="Random",
         continent="ANY",  role="warrior",
         hp_bonus=35, atk_bonus=16, def_bonus=6, mp_bonus=20,
         passive="Storm Fists: unarmed bonus, all attacks hit twice on crits",
         hire_cost=180,
         dialogue=[
             "The mountain does not fear the storm. Neither do I.",
             "My monastery taught peace. I taught myself the rest.",
             "Speed is strength. I have both.",
             "Breathe. Fight. Win. Simple.",
             "I don't need a weapon. Everything is a weapon.",
         ]),
]

# Build dict for fast lookup
COMPANION_BY_ID = {c["id"]: c for c in COMPANION_DEFS}


class Companion:
    """A party companion with leveling, customization, and role behaviour."""

    def __init__(self, data, player_level=1):
        self.id          = data["id"]
        self.name        = data["name"]          # can be renamed
        self.base_name   = data["name"]
        self.title       = data["title"]
        self.role        = data["role"]          # warrior/rogue/mage/healer
        self.passive     = data["passive"]
        self.continent   = data.get("continent","ANY")
        self.hire_cost   = data["hire_cost"]
        self.dialogue    = data.get("dialogue", [])
        self.heal_power  = data.get("heal_power", 20)
        self.colour_key  = "white"               # customisable
        self.marker      = data["name"][0].upper()  # customisable

        lvl = max(1, player_level)
        self.level   = lvl
        self.max_hp  = 80 + data["hp_bonus"]  + lvl * 8
        self.hp      = self.max_hp
        self.atk     = 8  + data["atk_bonus"] + lvl * 2
        self.defense = 2  + data["def_bonus"]
        self.mp      = 20 + data.get("mp_bonus",0) + lvl * 3
        self.max_mp  = self.mp

        self.status_effects = []
        self.is_alive_flag  = True

    # ── Combat helpers ───────────────────────────────────────────

    def is_alive(self): return self.hp > 0

    def take_damage(self, dmg):
        actual = max(1, dmg - self.defense // 3)
        self.hp = max(0, self.hp - actual)
        return actual

    def try_dodge(self):
        dodge_pct = 12 if self.role == "rogue" else 5
        return random.randint(1,100) <= dodge_pct

    def add_status(self, effect):
        for e in self.status_effects:
            if e.name == effect.name:
                e.duration = max(e.duration, effect.duration)
                return
        self.status_effects.append(effect)

    def process_status(self):
        for e in self.status_effects[:]:
            e.on_turn_start(self)
            e.duration -= 1
            if not e.is_active():
                self.status_effects.remove(e)

    def attack(self, enemy):
        """Standard companion attack."""
        base = self.atk + random.randint(-2, 4)
        crit = random.randint(1,100) <= (20 if self.role=="rogue" else 10)
        dmg  = int(base * 1.5) if crit else base
        actual = enemy.take_damage(dmg)
        tag = " [CRIT!]" if crit else ""
        print(C(f"  {self._col()}{self.name}{_R} attacks{tag} → {_RED}{actual}{_R} dmg!"))
        return actual

    def heal_target(self, target):
        """Healer role: restore HP to target."""
        if self.mp < 8:
            return 0
        self.mp -= 8
        amount = self.heal_power + random.randint(0, 10)
        old = target.hp
        target.hp = min(target.max_hp, target.hp + amount)
        healed = target.hp - old
        print(C(f"  {self._col()}{self.name}{_R} heals {_GREEN}{target.name}{_R} for {_GREEN}+{healed} HP{_R}!"))
        return healed

    def combat_action(self, player, enemy, party):
        """
        Called each combat round.
        Healers heal the most wounded party member;
        others attack.
        """
        if not self.is_alive():
            return
        self.process_status()
        if not self.is_alive():
            return

        if self.role == "healer":
            # Find most wounded target (player or companions)
            targets = [player] + [c for c in party if c.is_alive() and c is not self]
            needy   = min(targets, key=lambda t: t.hp / max(1, t.max_hp))
            hp_frac = needy.hp / max(1, needy.max_hp)
            # Heal if someone is below 60% HP
            if hp_frac < 0.6 and self.mp >= 8:
                self.heal_target(needy)
                return
        # Otherwise attack
        if enemy.is_alive():
            self.attack(enemy)

    def _col(self):
        return {
            "gold":   _GOLD, "green": _GREEN, "cyan": _CYAN,
            "purple": _PURP,  "pink":  _PINK,  "blue": _BLUE,
            "red":    _RED,   "white": _WHITE,
        }.get(self.colour_key, _WHITE)

    def rest(self):
        """Full heal (inn / Royal Suite)."""
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.status_effects = []

    def scale_to_level(self, new_level):
        gain = max(0, new_level - self.level)
        self.level  = new_level
        self.max_hp += gain * 8
        self.hp      = min(self.hp + gain * 8, self.max_hp)
        self.atk    += gain * 2
        self.max_mp += gain * 3

    def hp_bar(self, w=16):
        filled = int(w * self.hp / max(1, self.max_hp))
        col = _GREEN if self.hp/self.max_hp > .5 else _YELL if self.hp/self.max_hp > .25 else _RED
        return f"{col}{'█'*filled}{_DIM}{'░'*(w-filled)}{_R} {col}{self.hp}/{self.max_hp}{_R}"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "level": self.level,
            "hp": self.hp, "max_hp": self.max_hp,
            "atk": self.atk, "defense": self.defense,
            "mp": self.mp, "max_mp": self.max_mp,
            "colour_key": self.colour_key, "marker": self.marker,
        }

    @classmethod
    def from_dict(cls, d):
        base_data = COMPANION_BY_ID.get(d["id"])
        if not base_data:
            base_data = {"id":d["id"],"name":d["name"],"title":"","role":"warrior",
                         "passive":"","continent":"ANY","hire_cost":0,
                         "hp_bonus":0,"atk_bonus":0,"def_bonus":0,"mp_bonus":0,
                         "dialogue":[]}
        c = cls(base_data, d.get("level",1))
        c.name       = d.get("name", c.name)
        c.hp         = d.get("hp", c.max_hp)
        c.max_hp     = d.get("max_hp", c.max_hp)
        c.atk        = d.get("atk", c.atk)
        c.defense    = d.get("defense", c.defense)
        c.mp         = d.get("mp", c.max_mp)
        c.max_mp     = d.get("max_mp", c.max_mp)
        c.colour_key = d.get("colour_key","white")
        c.marker     = d.get("marker", c.name[0].upper())
        return c


class Party:
    """Manages up to MAX_PARTY companions."""

    def __init__(self):
        self.members = []

    def add(self, companion):
        if len(self.members) >= MAX_PARTY:
            return False, "Party is full (max 3)."
        if any(c.id == companion.id for c in self.members):
            return False, f"{companion.name} is already in your party."
        self.members.append(companion)
        return True, f"{companion.name} joined the party!"

    def remove(self, idx):
        if not (0 <= idx < len(self.members)):
            return False, "Invalid slot."
        c = self.members.pop(idx)
        return True, f"{c.name} left the party."

    def scale_all(self, player_level):
        for c in self.members:
            c.scale_to_level(max(c.level, player_level))

    def alive_members(self):
        return [c for c in self.members if c.is_alive()]

    def total_stealth_bonus(self):
        """Sum of stealth bonuses from all alive party members."""
        bonus = 0
        for c in self.alive_members():
            if c.role == "rogue":
                bonus += 4
            elif c.role == "mage":
                bonus += 2
            else:
                bonus += 1
        return bonus

    def total_atk_bonus(self):
        """ATK contribution from alive party members."""
        bonus = 0
        for c in self.alive_members():
            if c.role == "warrior":
                bonus += 3
            elif c.role == "rogue":
                bonus += 2
            elif c.role == "mage":
                bonus += 2
            else:
                bonus += 1
        return bonus

    def total_def_bonus(self):
        """DEF contribution from alive party members."""
        bonus = 0
        for c in self.alive_members():
            if c.role == "warrior":
                bonus += 3
            elif c.role == "healer":
                bonus += 1
            else:
                bonus += 1
        return bonus

    def total_heal_bonus(self):
        """Heal power contribution from alive party members."""
        bonus = 0
        for c in self.alive_members():
            if c.role == "healer":
                bonus += 5
            else:
                bonus += 1
        return bonus

    def total_skill_power(self):
        """Skill power contribution from alive party members."""
        bonus = 0
        for c in self.alive_members():
            if c.role == "mage":
                bonus += 4
            elif c.role == "rogue":
                bonus += 2
            else:
                bonus += 1
        return bonus

    def to_dict(self):
        return {"members": [c.to_dict() for c in self.members]}

    @classmethod
    def from_dict(cls, d):
        p = cls()
        for cd in d.get("members",[]):
            try:
                p.members.append(Companion.from_dict(cd))
            except Exception:
                pass
        return p


# ═══════════════════════════════════════════════════════════════
# CLAN SYSTEM
# ═══════════════════════════════════════════════════════════════

CLAN_RANKS = ["Unranked","Bronze","Silver","Gold","Platinum","Diamond","Legend"]
CLAN_HALL_UPGRADES = [
    {"name":"Clan Banner",     "cost":500,   "income":5,   "desc":"A flag that attracts recruits."},
    {"name":"Training Grounds","cost":1200,  "income":15,  "desc":"Companions gain +10% XP."},
    {"name":"Guild Storage",   "cost":2000,  "income":20,  "desc":"Extra 20 storage slots."},
    {"name":"Tavern",          "cost":3500,  "income":40,  "desc":"Draws adventurers; passive 40g/day."},
    {"name":"Forge",           "cost":5000,  "income":50,  "desc":"Crafting tier unlocked for clan."},
    {"name":"War Room",        "cost":8000,  "income":80,  "desc":"Clan quests yield +25% gold."},
    {"name":"Dragon Vault",    "cost":15000, "income":150, "desc":"Legendary income from dragon contracts."},
]

FOUND_COST = 1000   # gold to found clan


class Clan:
    def __init__(self, name, leader_name):
        self.name         = name
        self.leader       = leader_name
        self.rank_idx     = 0
        self.members      = 1        # NPC members (increases with upgrades)
        self.upgrades     = []       # list of upgrade names purchased
        self.gold_earned  = 0
        self.days_active  = 0
        self.pending_gold = 0        # income waiting to be collected

    @property
    def rank(self): return CLAN_RANKS[min(self.rank_idx, len(CLAN_RANKS)-1)]

    @property
    def passive_income(self):
        base = 10
        for u in self.upgrades:
            for uh in CLAN_HALL_UPGRADES:
                if uh["name"] == u:
                    base += uh["income"]
        return base

    def tick(self, days=1):
        """Called when the player rests (one day passes). Income accrues
        into pending_gold. Returns gold earned."""
        self.days_active += days
        earned = self.passive_income * days
        self.pending_gold += earned
        # Auto-rank-up every 30 days
        new_rank = min(len(CLAN_RANKS)-1, self.days_active // 30)
        if new_rank > self.rank_idx:
            self.rank_idx = new_rank
        return earned

    def collect(self):
        """Pay out accrued income (used to be an infinite-gold button)."""
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
                return True, f"Upgrade '{upgrade_name}' purchased! Passive income +{uh['income']}g/day."
        return False, "Unknown upgrade."

    def to_dict(self):
        return {
            "name": self.name, "leader": self.leader,
            "rank_idx": self.rank_idx, "members": self.members,
            "upgrades": self.upgrades, "gold_earned": self.gold_earned,
            "days_active": self.days_active, "pending_gold": self.pending_gold,
        }

    @classmethod
    def from_dict(cls, d):
        c = cls(d["name"], d["leader"])
        c.rank_idx    = d.get("rank_idx",0)
        c.members     = d.get("members",1)
        c.upgrades    = d.get("upgrades",[])
        c.gold_earned = d.get("gold_earned",0)
        c.days_active = d.get("days_active",0)
        c.pending_gold= d.get("pending_gold",0)
        return c


# ═══════════════════════════════════════════════════════════════
# RECRUITMENT MENU
# ═══════════════════════════════════════════════════════════════

def recruit_menu(player, town_name=""):
    """Show available companions to recruit, customise, manage party & clan."""
    while True:
        clr()
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════╗"))
        print(C(f"║   ⚔  PARTY & CLAN MANAGEMENT   ║"))
        print(C(f"╚══════════════════════════════════╝{_R}"))

        party = getattr(player, "party", None)
        clan  = getattr(player, "owned_clan",  None)

        # ── Current party ───────────────────────────────────────
        print(C(f"\n{_CYAN}{_B}Current Party:{_R}"))
        if party and party.members:
            for i, c in enumerate(party.members):
                role_col = {"warrior":_RED,"rogue":_YELL,"mage":_PURP,"healer":_GREEN}.get(c.role,_WHITE)
                print(C(f"  {_GOLD}[{i}]{_R} {c._col()}{c.name}{_R} ({role_col}{c.role.title()}{_R} Lv{c.level}) — {_DIM}{c.passive}{_R}"))
                print(C(f"       HP: {c.hp_bar(12)}  ATK:{c.atk} DEF:{c.defense}"))
        else:
            print(C(f"  {_DIM}No companions yet.{_R}"))

        # ── Clan summary ─────────────────────────────────────────
        if clan:
            print(C(f"\n{_GOLD}{_B}Clan: {clan.name}{_R}  {_DIM}Rank:{_R} {_CYAN}{clan.rank}{_R}  "
                    f"{_DIM}Members:{_R} {clan.members}  {_DIM}Income:{_R} {_GOLD}+{clan.passive_income}g/day{_R}"))
        else:
            print(C(f"\n{_DIM}No clan founded yet.{_R}"))

        print(C(f"\n{_DIM}{'─'*44}{_R}"))
        print(C(f"  {_GOLD}[R]{_R} Recruit companion   {_GOLD}[P]{_R} Party manage"))
        print(C(f"  {_GOLD}[C]{_R} Customise companion {_GOLD}[K]{_R} Clan menu"))
        print(C(f"  {_GOLD}[0]{_R} Back"))

        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()

        if ch == "0":
            return
        elif ch == "r":
            _recruit_screen(player, town_name)
        elif ch == "p":
            _party_manage(player)
        elif ch == "c":
            _customise_companion(player)
        elif ch == "k":
            _clan_menu(player)


def _recruit_screen(player, town_name):
    party = getattr(player, "party", Party())
    if not hasattr(player, "party"):
        player.party = party

    # Filter companions available here (town or wanderers)
    available = [
        c for c in COMPANION_DEFS
        if c["id"] not in [m.id for m in party.members]
        and (c["continent"] == "ANY" or town_name.upper() in c.get("town","").upper()
             or True)  # show all if no town filter needed
    ]

    page, per = 0, 6
    while True:
        clr()
        print(C(f"\n{_CYAN}{_B}════  RECRUIT COMPANION  ════{_R}"))
        print(C(f"  {_DIM}Party {len(party.members)}/{MAX_PARTY}  —  Gold: {_GOLD}{player.gold}g{_R}\n"))

        start = page * per
        chunk = available[start:start+per]
        for i, cd in enumerate(chunk):
            role_col = {"warrior":_RED,"rogue":_YELL,"mage":_PURP,"healer":_GREEN}.get(cd["role"],_WHITE)
            in_party = any(m.id == cd["id"] for m in party.members)
            tag = f" {_GREEN}[IN PARTY]{_R}" if in_party else ""
            print(C(f"  {_GOLD}[{i+1}]{_R} {_WHITE}{_B}{cd['name']}{_R} — {role_col}{cd['role'].title()}{_R}{tag}"))
            print(C(f"       {_DIM}{cd['title']}  ·  {cd['town']}{_R}"))
            print(C(f"       Passive: {_CYAN}{cd['passive']}{_R}"))
            print(C(f"       Cost: {_GOLD}{cd['hire_cost']}g{_R}  "
                    f"HP+{cd['hp_bonus']} ATK+{cd['atk_bonus']} DEF+{cd['def_bonus']}"))
            print()

        total_pages = max(1, (len(available)-1)//per+1)
        print(C(f"  {_DIM}Page {page+1}/{total_pages}{_R}"))
        print(C(f"  {_GOLD}[N]{_R} Next  {_GOLD}[P]{_R} Prev  {_GOLD}[0]{_R} Back"))
        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()

        if ch == "0": return
        elif ch == "n" and start+per < len(available): page += 1
        elif ch == "p" and page > 0: page -= 1
        elif ch.isdigit():
            idx = int(ch) - 1
            if 0 <= idx < len(chunk):
                cd = chunk[idx]
                if any(m.id == cd["id"] for m in party.members):
                    print(C(f"{_DIM}Already in your party.{_R}")); input(C(f"{_DIM}Enter...{_R}")); continue
                if len(party.members) >= MAX_PARTY:
                    print(C(f"{_RED}Party is full!{_R}")); input(C(f"{_DIM}Enter...{_R}")); continue
                if player.gold < cd["hire_cost"]:
                    print(C(f"{_RED}Not enough gold. Need {cd['hire_cost']}g.{_R}")); input(C(f"{_DIM}Enter...{_R}")); continue
                player.gold -= cd["hire_cost"]
                comp = Companion(cd, player.level)
                ok, msg = party.add(comp)
                print(C(f"{_GREEN if ok else _RED}{msg}{_R}"))
                # Companion greeting
                if ok and cd["dialogue"]:
                    print(C(f'  {_DIM}"{random.choice(cd["dialogue"])}"{_R}'))
                input(C(f"\n{_DIM}(Press Enter){_R}"))


def _party_manage(player):
    party = getattr(player, "party", Party())
    while True:
        clr()
        print(C(f"\n{_CYAN}{_B}════  MANAGE PARTY  ════{_R}\n"))
        if not party.members:
            print(C(f"  {_DIM}No companions in party.{_R}"))
            input(C(f"\n{_DIM}Enter...{_R}")); return

        for i, c in enumerate(party.members):
            role_col = {"warrior":_RED,"rogue":_YELL,"mage":_PURP,"healer":_GREEN}.get(c.role,_WHITE)
            print(C(f"  {_GOLD}[{i}]{_R} {c._col()}{c.name}{_R} ({role_col}{c.title}{_R})  HP:{c.hp}/{c.max_hp}"))
        print(C(f"\n  {_GOLD}[D#]{_R} Dismiss (e.g. D0)  {_GOLD}[T#]{_R} Talk (e.g. T1)  {_GOLD}[0]{_R} Back"))
        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()
        if ch == "0": return
        elif ch.startswith("d") and ch[1:].isdigit():
            idx = int(ch[1:])
            ok, msg = party.remove(idx)
            print(C(f"{_GREEN if ok else _RED}{msg}{_R}"))
            input(C(f"{_DIM}Enter...{_R}"))
        elif ch.startswith("t") and ch[1:].isdigit():
            idx = int(ch[1:])
            if 0 <= idx < len(party.members):
                c = party.members[idx]
                line = random.choice(c.dialogue) if c.dialogue else "..."
                print(C(f"\n  {c._col()}{c.name}{_R}: {_DIM}\"{line}\"{_R}"))
                input(C(f"\n{_DIM}Enter...{_R}"))


def _customise_companion(player):
    party = getattr(player, "party", Party())
    if not party.members:
        print(C(f"\n  {_DIM}No companions to customise.{_R}")); input(C(f"{_DIM}Enter...{_R}")); return

    clr()
    print(C(f"\n{_CYAN}{_B}════  CUSTOMISE  ════{_R}\n"))
    for i, c in enumerate(party.members):
        print(C(f"  {_GOLD}[{i}]{_R} {c._col()}{c.name}{_R}"))
    ch = input(C(f"\n{_GOLD}Choose companion >{_R} ")).strip()
    if not ch.isdigit(): return
    idx = int(ch)
    if not (0 <= idx < len(party.members)): return
    c = party.members[idx]

    clr()
    print(C(f"\n{_CYAN}Customising: {_GOLD}{c.name}{_R}\n"))
    print(C(f"  {_GOLD}[1]{_R} Rename"))
    print(C(f"  {_GOLD}[2]{_R} Change colour marker"))
    print(C(f"  {_GOLD}[3]{_R} Change HP marker character"))
    print(C(f"  {_GOLD}[0]{_R} Back"))
    ch2 = input(C(f"\n{_GOLD}>{_R} ")).strip()
    if ch2 == "1":
        new_name = input(C(f"  New name for {c.name}: ")).strip()
        if new_name:
            c.name = new_name[:20]
            print(C(f"  {_GREEN}Renamed to {c.name}.{_R}"))
    elif ch2 == "2":
        colours = ["white","gold","green","cyan","purple","pink","blue","red"]
        print(C(f"  Colours: {', '.join(colours)}"))
        col = input(C(f"  Choose: ")).strip().lower()
        if col in colours:
            c.colour_key = col
            print(C(f"  {_GREEN}Colour set to {col}.{_R}"))
    elif ch2 == "3":
        m = input(C(f"  Marker char (1 char): ")).strip()
        if m:
            c.marker = m[0].upper()
            print(C(f"  {_GREEN}Marker set to '{c.marker}'.{_R}"))
    input(C(f"\n{_DIM}Enter...{_R}"))


def _clan_menu(player):
    clan = getattr(player, "owned_clan", None)
    while True:
        clr()
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════╗"))
        print(C(f"║        ⚑  CLAN MENU          ║"))
        print(C(f"╚══════════════════════════════╝{_R}\n"))

        if not clan:
            print(C(f"  {_DIM}You have no clan yet.{_R}"))
            print(C(f"  Found a clan for {_GOLD}{FOUND_COST}g{_R} and start earning passive gold!"))
            print(C(f"\n  {_GOLD}[F]{_R} Found clan  {_GOLD}[0]{_R} Back"))
            ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()
            if ch == "0": return
            elif ch == "f":
                if player.gold < FOUND_COST:
                    print(C(f"{_RED}Need {FOUND_COST}g to found a clan.{_R}")); input(C(f"{_DIM}Enter...{_R}")); continue
                name = input(C(f"  Clan name: ")).strip()
                if not name: continue
                player.gold -= FOUND_COST
                player.owned_clan = Clan(name[:24], player.name)
                clan = player.owned_clan
                print(C(f"{_GREEN}Clan '{name}' founded!{_R}")); input(C(f"{_DIM}Enter...{_R}"))
        else:
            print(C(f"  {_CYAN}{_B}{clan.name}{_R}  Rank: {_GOLD}{clan.rank}{_R}"))
            print(C(f"  Members: {clan.members}  Active: {clan.days_active} days"))
            print(C(f"  Passive income: {_GOLD}+{clan.passive_income}g/day{_R}  {_DIM}(a day passes each time you rest at an inn or base){_R}"))
            print(C(f"  Waiting to collect: {_GOLD}{clan.pending_gold}g{_R}   Total collected: {_GOLD}{clan.gold_earned}g{_R}\n"))
            print(C(f"  {_GOLD}[U]{_R} Upgrade clan hall"))
            print(C(f"  {_GOLD}[C]{_R} Collect income"))
            print(C(f"  {_GOLD}[0]{_R} Back"))
            ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()
            if ch == "0": return
            elif ch == "c":
                earned = clan.collect()
                player.gold += earned
                if earned:
                    print(C(f"{_GREEN}Collected {earned}g from your clan!{_R}"))
                else:
                    print(C(f"{_DIM}Nothing to collect yet — rest at an inn or your base to pass a day.{_R}"))
                input(C(f"{_DIM}Enter...{_R}"))
            elif ch == "u":
                _clan_upgrade_menu(player, clan)


def _clan_upgrade_menu(player, clan):
    clr()
    print(C(f"\n{_CYAN}{_B}════  CLAN UPGRADES  ════{_R}\n"))
    for i, uh in enumerate(CLAN_HALL_UPGRADES):
        owned = uh["name"] in clan.upgrades
        tag = f"{_GREEN}[OWNED]{_R}" if owned else f"{_GOLD}{uh['cost']}g{_R}"
        print(C(f"  {_GOLD}[{i+1}]{_R} {_WHITE}{uh['name']}{_R}  {tag}"))
        print(C(f"       {_DIM}{uh['desc']}  +{uh['income']}g/day{_R}"))
    print(C(f"\n  {_GOLD}[0]{_R} Back"))
    ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
    if ch.isdigit() and 1 <= int(ch) <= len(CLAN_HALL_UPGRADES):
        uh = CLAN_HALL_UPGRADES[int(ch)-1]
        ok, msg = clan.buy_upgrade(player, uh["name"])
        print(C(f"{_GREEN if ok else _RED}{msg}{_R}"))
        input(C(f"{_DIM}Enter...{_R}"))

def try_world_companion_event(player, event_type="ruins_event"):
    """
    Trigger a random companion interaction event on the world map.
    Called from ruins exploration and other overworld events.
    """
    from game_term import C
    import random

    if not hasattr(player, "party") or not player.party.members:
        return

    companion = random.choice(player.party.members)
    if not companion.is_alive():
        return

    _R = "\033[0m"; _B = "\033[1m"
    def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
    _GOLD = _fg(255,215,0); _WHITE = _fg(255,255,255)
    _DIM  = _fg(100,100,100); _GREEN = _fg(80,200,80)

    if event_type == "ruins_event":
        outcomes = [
            ("find_item",   0.35),
            ("find_gold",   0.30),
            ("heal",        0.20),
            ("dialogue",    0.15),
        ]
        roll = random.random()
        cumulative = 0.0
        outcome = "dialogue"
        for name, chance in outcomes:
            cumulative += chance
            if roll <= cumulative:
                outcome = name
                break

        if outcome == "find_item":
            from game_items import ITEM_POOL
            item = random.choice(list(ITEM_POOL.values()))()
            player.add_item(item)
            print(C(f"  {_GOLD}{_B}{companion.name}{_R}{_WHITE} searches the ruins and finds {item.name}!{_R}"))
        elif outcome == "find_gold":
            gold = random.randint(15, 60)
            player.gold += gold
            print(C(f"  {_GOLD}{_B}{companion.name}{_R}{_WHITE} spots a hidden cache — {gold} gold!{_R}"))
        elif outcome == "heal":
            heal = random.randint(10, 30)
            player.hp = min(player.max_hp, player.hp + heal)
            print(C(f"  {_GREEN}{_B}{companion.name}{_R}{_GREEN} tends your wounds — +{heal} HP.{_R}"))
        else:
            if companion.dialogue:
                line = random.choice(companion.dialogue)
                print(C(f"  {_GOLD}{_B}{companion.name}:{_R} {_DIM}\"{line}\"{_R}"))
