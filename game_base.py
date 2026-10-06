"""
base.py — Player Base / House system for Terminal-RPG.

One base per continent. Acquire by:
  A) Buying a plot in any city (costs gold)
  B) Building anywhere on land with materials

Rooms / upgrades:
  Bedroom       — rest restores full HP/MP (free at start, upgrades speed)
  Storage Chest — 30 extra item slots permanently available
  Crafting Workshop — unlocks advanced crafting recipes
  Garden        — grows 1–3 potions per real game-session resting
  Trophy Wall   — displays boss kills and achievements

Passive regen:
  Sleeping in your base restores HP/MP over several "rest ticks",
  with party members healing too. Higher bedroom tier = faster recovery.
"""

from __future__ import annotations

import random, os, json
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_lang import T, set_language, LANG, LANGUAGE_NAMES

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD  =_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM  =_fg(100,100,100)
_GREEN =_fg(80,200,80);  _RED  =_fg(220,60,60);   _CYAN =_fg(80,220,220)
_YELL  =_fg(240,200,60); _PURP =_fg(180,80,220);  _ORAN =_fg(220,140,40)
_TEAL  =_fg(60,200,180); _PINK =_fg(220,80,160)

def _clear(): clr()
def _div(w=0): return C(f"{_DIM}{'─'*(w or max(40,W()-4))}{_R}")
def _opt(key,lbl,hint=""):
    return (f"  {_GOLD}{_B}[{key}]{_R} {_WHITE}{lbl}{_R}"
            + (f"  {_DIM}{hint}{_R}" if hint else ""))

# ── Room definitions ─────────────────────────────────────────────

ROOMS = {
    "bedroom": {
        "name":  "Bedroom",
        "icon":  "🛏",
        "desc":  "Rest and recover HP/MP. Higher tiers recover faster.",
        "tiers": [
            {"name":"Straw Bedroll", "cost_gold":0,   "cost_mats":{},
             "regen_pct":50,  "desc":"A basic mat on the floor. Better than nothing."},
            {"name":"Wooden Bed",   "cost_gold":300,  "cost_mats":{"Iron Ore":2},
             "regen_pct":80,  "desc":"A proper bed. Decent sleep."},
            {"name":"Stone Chamber","cost_gold":800,  "cost_mats":{"Iron Ore":5,"Wolf Pelt":2},
             "regen_pct":100, "desc":"Thick stone walls. Deep, healing sleep. Full restore."},
            {"name":"Royal Suite",  "cost_gold":2000, "cost_mats":{"Dark Shard":3,"Dragon Scale":1},
             "regen_pct":100, "desc":"Luxury beyond measure. Also regenerates party HP/MP fully."},
        ],
    },
    "storage": {
        "name":  "Storage Chest",
        "icon":  "📦",
        "desc":  "Store items at your base. Accessible any time you visit.",
        "tiers": [
            {"name":"Wooden Crate",  "cost_gold":200, "cost_mats":{"Wolf Pelt":1},
             "slots":20, "desc":"A sturdy crate. 20 extra item slots."},
            {"name":"Iron Chest",    "cost_gold":600, "cost_mats":{"Iron Ore":4},
             "slots":50, "desc":"Lockable iron chest. 50 extra item slots."},
            {"name":"Vault Room",    "cost_gold":1500,"cost_mats":{"Iron Ore":8,"Dark Shard":2},
             "slots":100,"desc":"A whole vault. 100 item slots. Basically a warehouse."},
        ],
    },
    "workshop": {
        "name":  "Crafting Workshop",
        "icon":  "⚒",
        "desc":  "Unlocks advanced crafting recipes unavailable at town benches.",
        "tiers": [
            {"name":"Workbench",    "cost_gold":400, "cost_mats":{"Iron Ore":3},
             "recipes":5,  "desc":"Basic tools. 5 advanced recipes unlocked."},
            {"name":"Forge",        "cost_gold":1000,"cost_mats":{"Iron Ore":6,"Frost Crystal":2},
             "recipes":12, "desc":"A real forge. 12 advanced recipes unlocked."},
            {"name":"Master Forge", "cost_gold":2500,"cost_mats":{"Dragon Scale":2,"Dark Shard":3},
             "recipes":20, "desc":"Legendary smith's forge. All advanced recipes unlocked."},
        ],
    },
    "garden": {
        "name":  "Garden",
        "icon":  "🌿",
        "desc":  "Grows potions and herbs while you rest at base.",
        "tiers": [
            {"name":"Herb Patch",   "cost_gold":250, "cost_mats":{"Feather":2},
             "yield":1, "item":"Potion",    "desc":"Grows 1 Potion per rest."},
            {"name":"Herb Garden",  "cost_gold":700, "cost_mats":{"Feather":4,"Wolf Pelt":2},
             "yield":2, "item":"Hi-Potion", "desc":"Grows 2 Hi-Potions per rest."},
            {"name":"Alchemist Grove","cost_gold":1800,"cost_mats":{"Frost Crystal":3,"Scale Fragment":2},
             "yield":3, "item":"Hi-Ether",  "desc":"Grows 3 Hi-Ethers per rest. Rare herbs too."},
        ],
    },
    "trophy": {
        "name":  "Trophy Wall",
        "icon":  "🏆",
        "desc":  "Display your greatest victories. Grants small stat bonuses per trophy.",
        "tiers": [
            {"name":"Wooden Board", "cost_gold":150, "cost_mats":{"Bone Shard":2},
             "bonus_atk":1,"bonus_def":0,"desc":"A board to hang trophies. +1 ATK per 3 trophies."},
            {"name":"Stone Mantle", "cost_gold":500, "cost_mats":{"Iron Ore":3,"Bone Shard":3},
             "bonus_atk":2,"bonus_def":1,"desc":"Impressive stone display. +2 ATK +1 DEF per 3 trophies."},
            {"name":"Hall of Glory", "cost_gold":1200,"cost_mats":{"Dark Shard":2,"Dragon Scale":1},
             "bonus_atk":3,"bonus_def":2,"desc":"A whole hall. +3 ATK +2 DEF per 3 trophies."},
        ],
    },
}

# Advanced crafting recipes unlocked by workshop
ADVANCED_RECIPES = [
    # tier 1 (5 recipes)
    {"name":"Reinforced Blade",  "tier":1,
     "needs":{"Iron Ore":3,"Wolf Pelt":1},
     "result":lambda: __import__('game_items').Equipment("Reinforced Blade","weapon",atk_bonus=12,sell_value=80)},
    {"name":"Scale Mail",        "tier":1,
     "needs":{"Scale Fragment":3,"Iron Ore":2},
     "result":lambda: __import__('game_items').Equipment("Scale Mail","armor",hp_bonus=35,def_bonus=8,sell_value=90)},
    {"name":"Frost Amulet",      "tier":1,
     "needs":{"Frost Crystal":2},
     "result":lambda: __import__('game_items').Equipment("Frost Amulet","amulet",mp_bonus=20,sell_value=70)},
    {"name":"Bone Shield",       "tier":1,
     "needs":{"Bone Shard":4,"Iron Ore":2},
     "result":lambda: __import__('game_items').Equipment("Bone Shield","shield",hp_bonus=20,def_bonus=10,sell_value=85)},
    {"name":"Shadow Dagger",     "tier":1,
     "needs":{"Dark Shard":2,"Feather":1},
     "result":lambda: __import__('game_items').Equipment("Shadow Dagger","weapon",atk_bonus=9,stealth_bonus=4,sell_value=75)},
    # tier 2 (additional 7 = 12 total)
    {"name":"Dragonbone Spear",  "tier":2,
     "needs":{"Dragon Scale":1,"Iron Ore":4},
     "result":lambda: __import__('game_items').Equipment("Dragonbone Spear","weapon",atk_bonus=18,sell_value=150)},
    {"name":"Frost Plate",       "tier":2,
     "needs":{"Frost Crystal":4,"Iron Ore":4},
     "result":lambda: __import__('game_items').Equipment("Frost Plate","armor",hp_bonus=50,def_bonus=14,sell_value=160)},
    {"name":"Shadow Crown",      "tier":2,
     "needs":{"Dark Shard":4,"Feather":2},
     "result":lambda: __import__('game_items').Equipment("Shadow Crown","helmet",mp_bonus=25,stealth_bonus=8,sell_value=140)},
    {"name":"Berserker Bracer",  "tier":2,
     "needs":{"Iron Ore":5,"Wolf Pelt":3},
     "result":lambda: __import__('game_items').Equipment("Berserker Bracer","ring",atk_bonus=8,def_bonus=2,sell_value=130)},
    {"name":"Phoenix Elixir",    "tier":2,
     "needs":{"Frost Crystal":2,"Scale Fragment":2,"Feather":2},
     "result":lambda: __import__('game_items').Item("Phoenix Elixir","heal",150,80)},
    {"name":"Mana Crystal",      "tier":2,
     "needs":{"Dark Shard":3,"Frost Crystal":2},
     "result":lambda: __import__('game_items').Item("Mana Crystal","mana",100,70)},
    {"name":"Ancient Rune Armor","tier":2,
     "needs":{"Dragon Scale":2,"Iron Ore":6,"Dark Shard":2},
     "result":lambda: __import__('game_items').Equipment("Ancient Rune Armor","armor",hp_bonus=70,def_bonus=18,mp_bonus=15,sell_value=250)},
    # tier 3 (additional 8 = 20 total)
    {"name":"Dragon Emperor Sword","tier":3,
     "needs":{"Dragon Scale":3,"Dark Shard":3,"Iron Ore":5},
     "result":lambda: __import__('game_items').Equipment("Dragon Emperor Sword","weapon",atk_bonus=28,sell_value=400)},
    {"name":"Void Cloak",        "tier":3,
     "needs":{"Dark Shard":5,"Feather":3,"Frost Crystal":2},
     "result":lambda: __import__('game_items').Equipment("Void Cloak","cloak",hp_bonus=30,mp_bonus=30,stealth_bonus=12,sell_value=380)},
    {"name":"Titan Gauntlets",   "tier":3,
     "needs":{"Dragon Scale":2,"Iron Ore":8},
     "result":lambda: __import__('game_items').Equipment("Titan Gauntlets","ring",atk_bonus=10,def_bonus=8,sell_value=320)},
    {"name":"God's Tear",        "tier":3,
     "needs":{"Dragon Scale":1,"Dark Shard":4,"Frost Crystal":3},
     "result":lambda: __import__('game_items').Item("God's Tear","heal",200,200)},
    {"name":"Eternal Compass",   "tier":3,
     "needs":{"Dragon Scale":1,"Feather":4,"Iron Ore":4},
     "result":lambda: __import__('game_items').Equipment("Eternal Compass","amulet",mp_bonus=40,stealth_bonus=6,sell_value=350)},
    {"name":"War Titan Plate",   "tier":3,
     "needs":{"Dragon Scale":4,"Iron Ore":10,"Dark Shard":3},
     "result":lambda: __import__('game_items').Equipment("War Titan Plate","armor",hp_bonus=100,def_bonus=25,sell_value=500)},
    {"name":"Arcane Orb",        "tier":3,
     "needs":{"Dark Shard":5,"Frost Crystal":4},
     "result":lambda: __import__('game_items').Equipment("Arcane Orb","amulet",mp_bonus=50,sell_value=420)},
    {"name":"Legendary God Potion","tier":3,
     "needs":{"Dragon Scale":1,"Dark Shard":5},
     "result":lambda: __import__('game_items').Item("God Potion","god",5,500)},
]

# Build cost to acquire a plot in a city
PLOT_COST_GOLD = 1500
PLOT_BUILD_MATS = {"Iron Ore": 5, "Wolf Pelt": 3}

# Continent-specific plot names
PLOT_NAMES = {
    "A": "Aeloria Homestead",
    "B": "Ironspire Stronghold",
    "C": "Frostheim Refuge",
    "D": "Desert Outpost",
    "E": "Island Retreat",
}


# ── PlayerBase class ─────────────────────────────────────────────

class PlayerBase:
    """
    A single base on one continent.
    """
    def __init__(self, continent_id, name, location_name, x, y):
        self.continent_id  = continent_id
        self.name          = name
        self.location_name = location_name   # city it's in / "Wilderness"
        self.x             = x
        self.y             = y

        # Room tiers: 0 = not built, 1+ = tier level
        self.rooms = {
            "bedroom":  1,   # everyone starts with a basic bedroll
            "storage":  0,
            "workshop": 0,
            "garden":   0,
            "trophy":   0,
        }

        # Storage inventory (separate from game_player bag)
        self.storage: list = []

        # Trophy wall: list of {"name": str, "type": str, "continent": str}
        self.trophies: list = []

        # Garden: how many rests since last harvest
        self.garden_rests = 0

        # Rest counter: how many times player has slept here
        self.total_rests = 0

    # ── Properties ───────────────────────────────────────────────

    def storage_capacity(self):
        t = self.rooms["storage"]
        if t == 0: return 0
        return ROOMS["storage"]["tiers"][t-1]["slots"]

    def workshop_tier(self):
        return self.rooms["workshop"]

    def bedroom_tier(self):
        return self.rooms["bedroom"]

    def regen_pct(self):
        t = self.bedroom_tier()
        if t == 0: return 30
        return ROOMS["bedroom"]["tiers"][t-1]["regen_pct"]

    def trophy_bonus(self):
        """Returns (atk_bonus, def_bonus) from trophy wall."""
        t = self.rooms["trophy"]
        if t == 0: return (0, 0)
        n = len(self.trophies)
        tier_data = ROOMS["trophy"]["tiers"][t-1]
        multiplier = n // 3
        return (tier_data["bonus_atk"] * multiplier,
                tier_data["bonus_def"] * multiplier)

    def available_recipes(self):
        t = self.workshop_tier()
        if t == 0: return []
        max_tier = t  # workshop tier 1 = recipes up to tier 1, etc.
        return [r for r in ADVANCED_RECIPES if r["tier"] <= max_tier]

    # ── Rest ─────────────────────────────────────────────────────

    def rest(self, player):
        """Rest at base. Restores HP/MP, garden grows, party heals."""
        _clear()
        t = self.bedroom_tier()
        tier_name = ROOMS["bedroom"]["tiers"][t-1]["name"]
        regen = self.regen_pct()

        print(C(f"\n{_CYAN}{_B}╔══════════════════════════════════════════╗"))
        print(C(f"║  🛏  Resting at {self.name:<26}║"))
        print(C(f"║     {tier_name:<40}║"))
        print(C(f"╚══════════════════════════════════════════╝{_R}\n"))

        # Restore player
        old_hp = player.hp; old_mp = player.mp
        # Restore UP TO regen% — never lower HP/MP that is already higher
        player.hp = max(player.hp, min(player.max_hp, int(player.max_hp * regen / 100)))
        player.mp = max(player.mp, min(player.max_mp, int(player.max_mp * regen / 100)))
        player.status_effects.clear()
        print(C(f"{_GREEN}HP restored: {old_hp} → {player.hp}{_R}"))
        print(C(f"{_CYAN}MP restored: {old_mp} → {player.mp}{_R}"))
        print(C(f"{_DIM}Status effects cleared.{_R}"))

        # Royal suite: full restore for party too
        if t >= 4:
            player.hp = player.max_hp
            player.mp = player.max_mp
            print(C(f"{_GOLD}Royal Suite: fully restored!{_R}"))

        # Party healing
        if player.party.members:
            print(C(f"\n{_CYAN}Party rests:{_R}"))
            for m in player.party.members:
                old = m.hp
                if t >= 4:
                    m.rest()
                else:
                    m.hp = max(m.hp, min(m.max_hp, int(m.max_hp * regen / 100)))
                    m.mp = max(m.mp, min(m.max_mp, int(m.max_mp * regen / 100)))
                print(C(f"  {m.name}: {old} → {m.hp} HP"))

        # Garden harvest
        if self.rooms["garden"] > 0:
            self.garden_rests += 1
            if self.garden_rests >= 2:   # harvest every 2 rests
                self.garden_rests = 0
                gt = self.rooms["garden"]
                tier_data = ROOMS["garden"]["tiers"][gt-1]
                yield_n   = tier_data["yield"]
                item_name = tier_data["item"]
                from game_items import ITEM_POOL
                harvested = []
                for _ in range(yield_n):
                    if item_name in ITEM_POOL:
                        item = ITEM_POOL[item_name]()
                        player.add_item(item)
                        harvested.append(item.name)
                    else:
                        from game_items import Item
                        item = Item(item_name, "heal", 80, 30)
                        player.add_item(item)
                        harvested.append(item_name)
                print(C(f"\n{_GREEN}🌿 Garden harvest: {', '.join(harvested)}!{_R}"))

        # Trophy bonus reminder
        atk_b, def_b = self.trophy_bonus()
        if atk_b or def_b:
            print(C(f"\n{_GOLD}🏆 Trophy bonus active: +{atk_b} ATK, +{def_b} DEF{_R}"))

        self.total_rests += 1
        from game_systems import pass_day
        pass_day(player)
        input(C(f"\n{_DIM}(Press Enter){_R}"))

    # ── Add trophy ────────────────────────────────────────────────

    def add_trophy(self, enemy_name, continent_id):
        if self.rooms["trophy"] == 0:
            return False
        # Don't duplicate same enemy
        if any(t["name"] == enemy_name for t in self.trophies):
            return False
        self.trophies.append({"name": enemy_name, "continent": continent_id})
        return True

    # ── Serialise ─────────────────────────────────────────────────

    def to_dict(self):
        from game_items import item_from_dict
        return {
            "continent_id":   self.continent_id,
            "name":           self.name,
            "location_name":  self.location_name,
            "x":              self.x,
            "y":              self.y,
            "rooms":          self.rooms,
            "storage":        [i.to_dict() for i in self.storage],
            "trophies":       self.trophies,
            "garden_rests":   self.garden_rests,
            "total_rests":    self.total_rests,
        }

    @classmethod
    def from_dict(cls, d):
        b = cls(d["continent_id"], d["name"], d["location_name"], d["x"], d["y"])
        b.rooms        = d.get("rooms", b.rooms)
        b.trophies     = d.get("trophies", [])
        b.garden_rests = d.get("garden_rests", 0)
        b.total_rests  = d.get("total_rests", 0)
        from game_items import item_from_dict
        b.storage = [item_from_dict(i) for i in d.get("storage", [])]
        return b


# ── Base Manager (holds all bases) ───────────────────────────────

class BaseManager:
    MAX_BASES = 5   # one per continent

    def __init__(self):
        self.bases: dict[str, PlayerBase] = {}   # continent_id → PlayerBase

    def has_base(self, continent_id):
        return continent_id in self.bases

    def get_base(self, continent_id):
        return self.bases.get(continent_id)

    def add_base(self, base: PlayerBase):
        self.bases[base.continent_id] = base

    def to_dict(self):
        return {cid: b.to_dict() for cid, b in self.bases.items()}

    @classmethod
    def from_dict(cls, d):
        bm = cls()
        for cid, bd in d.items():
            bm.bases[cid] = PlayerBase.from_dict(bd)
        return bm


# ── Base Menu (entered from town or world map) ────────────────────

class BaseMenu:
    def __init__(self, player, base: PlayerBase):
        self.player = player
        self.base   = base

    def _header(self, subtitle=""):
        _clear()
        tier_name = ROOMS["bedroom"]["tiers"][self.base.bedroom_tier()-1]["name"]
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════════╗"))
        print(C(f"║  🏠  {self.base.name:<42}║"))
        if subtitle:
            print(C(f"║  {_DIM}{subtitle:<44}{_GOLD}║"))
        print(C(f"╚══════════════════════════════════════════════╝{_R}"))
        info_line = (f"{_DIM}Continent:{_R} {_CYAN}{self._cont_name()}{_R}  "
                     f"{_DIM}Bedroom:{_R} {_WHITE}{tier_name}{_R}  "
                     f"{_DIM}Rests:{_R} {_YELL}{self.base.total_rests}{_R}")
        print(C(f"\n{info_line}"))
        atk_b, def_b = self.base.trophy_bonus()
        if atk_b or def_b:
            print(C(f"{_GOLD}🏆 Trophy bonus: +{atk_b} ATK  +{def_b} DEF{_R}"))
        print(_div())

    def _cont_name(self):
        from game_world import CONTINENTS
        cont = next((c for c in CONTINENTS if c["id"]==self.base.continent_id), None)
        return cont["name"] if cont else "?"

    def enter(self):
        while True:
            self._header()
            print(C(f"\n{_opt('1', 'Rest',              f'Restore HP/MP ({self.base.regen_pct()}% restore)')}"))
            print(C(f"{_opt('2', 'Storage Chest',     f'Slots: {len(self.base.storage)}/{self.base.storage_capacity() or chr(8212)}')}"))
            print(C(f"{_opt('3', 'Upgrade Rooms',     'Build and improve your base')}"))
            print(C(f"{_opt('4', 'Workshop',          'Advanced crafting' if self.base.workshop_tier() else 'Build workshop first')}"))
            print(C(f"{_opt('5', 'Garden',            'Harvest produce' if self.base.rooms['garden'] else 'Plant a garden first')}"))
            print(C(f"{_opt('6', 'Trophy Wall',       f'{len(self.base.trophies)} trophies' if self.base.rooms['trophy'] else 'Build trophy wall first')}"))
            print(C(f"{_opt('7', 'Rename Base',       '')}"))
            print(C(f"{_opt('0', 'Leave',             '')}"))

            ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
            if   ch == "1": self.base.rest(self.player)
            elif ch == "2": self._storage_menu()
            elif ch == "3": self._upgrade_menu()
            elif ch == "4": self._workshop_menu()
            elif ch == "5": self._garden_menu()
            elif ch == "6": self._trophy_menu()
            elif ch == "7": self._rename()
            elif ch == "0": break
            else:
                print(f"  {_R}Invalid.{_R}"); input(C(f"{_DIM}(Enter){_R}"))

    # ── Storage ──────────────────────────────────────────────────

    def _storage_menu(self):
        if self.base.storage_capacity() == 0:
            _clear()
            print(C(f"\n{_DIM}You need to build a Storage Chest first (Upgrade Rooms → Storage Chest).{_R}"))
            input(C(f"{_DIM}(Press Enter){_R}")); return

        while True:
            _clear()
            cap = self.base.storage_capacity()
            print(C(f"\n{_CYAN}{_B}════  STORAGE: {self.base.name}  ════{_R}"))
            print(C(f"{_DIM}Capacity: {_GOLD}{len(self.base.storage)}/{cap}{_R}\n"))

            print(C(f"{_CYAN}Stored items:{_R}"))
            if not self.base.storage:
                print(C(f"{_DIM}Empty.{_R}"))
            for i, it in enumerate(self.base.storage, 1):
                print(C(f"{_GOLD}[{i:>2}]{_R} {_WHITE}{it.name:<28}{_R} {_DIM}{it.item_type}{_R}"))

            print(f"\n{_div()}")
            print(C(f"{_CYAN}Bag items:{_R}"))
            if not self.player.inventory:
                print(C(f"{_DIM}Your bag is empty.{_R}"))
            for i, it in enumerate(self.player.inventory, 1):
                print(C(f"{_GOLD}[{i:>2}]{_R} {_WHITE}{it.name:<28}{_R} {_DIM}{it.item_type}{_R}"))

            print(C(f"\n{_opt('D','Deposit  (bag → storage)')}"))
            print(C(f"{_opt('W','Withdraw (storage → bag)')}"))
            print(C(f"{_opt('0','Back')}"))
            ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()

            if ch == "0": break
            elif ch == "d": self._deposit()
            elif ch == "w": self._withdraw()

    def _deposit(self):
        if not self.player.inventory:
            print(f"  {_DIM}Nothing in bag.{_R}"); input(C(f"{_DIM}(Enter){_R}")); return
        cap = self.base.storage_capacity()
        if len(self.base.storage) >= cap:
            print(f"  {_RED}Storage full!{_R}"); input(C(f"{_DIM}(Enter){_R}")); return
        print(C(f"\nDeposit which item # (or 0 to cancel):"), end=" ")
        ch = input().strip()
        if ch == "0" or not ch.isdigit(): return
        idx = int(ch)-1
        if not (0 <= idx < len(self.player.inventory)): return
        item = self.player.inventory.pop(idx)
        self.base.storage.append(item)
        print(C(f"{_GREEN}Deposited {item}.{_R}")); input(C(f"{_DIM}(Enter){_R}"))

    def _withdraw(self):
        if not self.base.storage:
            print(f"  {_DIM}Storage empty.{_R}"); input(C(f"{_DIM}(Enter){_R}")); return
        print(C(f"\nWithdraw which stored item # (or 0 to cancel):"), end=" ")
        ch = input().strip()
        if ch == "0" or not ch.isdigit(): return
        idx = int(ch)-1
        if not (0 <= idx < len(self.base.storage)): return
        item = self.base.storage[idx]
        if not self.player.add_item(item):
            input(C(f"{_DIM}(Enter){_R}")); return
        self.base.storage.pop(idx)
        print(C(f"{_GREEN}Withdrew {item}.{_R}")); input(C(f"{_DIM}(Enter){_R}"))

    # ── Upgrade menu ─────────────────────────────────────────────

    def _upgrade_menu(self):
        while True:
            _clear()
            print(C(f"\n{_CYAN}{_B}════  UPGRADE ROOMS  ════{_R}"))
            print(C(f"{_DIM}Gold: {_GOLD}{self.player.gold}{_R}\n"))

            # Mat inventory
            from game_items import material_counts
            mat_count = material_counts(self.player.inventory)

            room_ids = list(ROOMS.keys())
            for i, rid in enumerate(room_ids, 1):
                rdef   = ROOMS[rid]
                cur_t  = self.base.rooms[rid]
                tiers  = rdef["tiers"]
                if cur_t >= len(tiers):
                    status = f"{_GREEN}MAX{_R}"
                    next_info = ""
                else:
                    next_t    = tiers[cur_t]  # next tier to build (0-indexed)
                    g_cost    = next_t["cost_gold"]
                    m_cost    = next_t["cost_mats"]
                    can_gold  = self.player.gold >= g_cost
                    can_mats  = all(mat_count.get(k,0)>=v for k,v in m_cost.items())
                    can       = can_gold and can_mats
                    g_col     = _GREEN if can_gold else _RED
                    m_col     = _GREEN if can_mats else _RED
                    m_str     = ", ".join(f"{k}×{v}" for k,v in m_cost.items()) or "—"
                    status    = f"{_GREEN}[BUILD]{_R}" if can else f"{_DIM}[need more]{_R}"
                    next_info = (f"  → {_WHITE}{next_t['name']}{_R}  "
                                 f"{g_col}{g_cost}g{_R}  {m_col}{m_str}{_R}")

                cur_name = tiers[cur_t-1]["name"] if cur_t>0 else "Not built"
                print(f"  {_GOLD}{_B}[{i}]{_R} {_CYAN}{rdef['name']:<20}{_R} "
                      f"{_DIM}Current: {_WHITE}{cur_name}{_R}  {status}")
                if next_info: print(f"       {next_info}")
                print()

            print(C(f"{_opt('0','Back')}"))
            ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
            if ch == "0": break
            if not ch.isdigit(): continue
            idx = int(ch)-1
            if not (0 <= idx < len(room_ids)): continue
            self._try_upgrade(room_ids[idx], mat_count)

    def _try_upgrade(self, room_id, mat_count):
        rdef  = ROOMS[room_id]
        cur_t = self.base.rooms[room_id]
        tiers = rdef["tiers"]
        if cur_t >= len(tiers):
            print(f"  {_DIM}Already at max tier.{_R}"); input(C(f"{_DIM}(Enter){_R}")); return
        next_t  = tiers[cur_t]
        g_cost  = next_t["cost_gold"]
        m_cost  = next_t["cost_mats"]
        if self.player.gold < g_cost:
            print(C(f"{_RED}Need {g_cost}g (have {self.player.gold}g).{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return
        for k, v in m_cost.items():
            if mat_count.get(k, 0) < v:
                print(f"  {_RED}Need {v}x {k}.{_R}"); input(C(f"{_DIM}(Enter){_R}")); return
        # Pay
        self.player.gold -= g_cost
        from game_items import remove_items
        for mat_name, qty in m_cost.items():
            remove_items(self.player.inventory, mat_name, qty)
        self.base.rooms[room_id] += 1
        print(C(f"\n{_GREEN}★ Built: {next_t['name']}!{_R}"))
        print(C(f"{_DIM}{next_t['desc']}{_R}"))
        input(C(f"{_DIM}(Press Enter){_R}"))

    # ── Workshop ─────────────────────────────────────────────────

    def _workshop_menu(self):
        if self.base.workshop_tier() == 0:
            _clear()
            print(C(f"\n{_DIM}No workshop yet. Upgrade Rooms → Crafting Workshop.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return

        _clear()
        print(C(f"\n{_CYAN}{_B}════  WORKSHOP: {self.base.name}  ════{_R}\n"))
        from game_items import material_counts
        mat_count = material_counts(self.player.inventory)

        print(C(f"{_DIM}Materials in bag:{_R}"))
        for m, q in mat_count.items():
            print(C(f"  {_WHITE}{m:<22}{_R} x{q}"))
        if not mat_count: print(f"  {_DIM}None.{_R}")

        recipes = self.base.available_recipes()
        print(C(f"\n{_CYAN}Advanced recipes (Workshop Tier {self.base.workshop_tier()}):{_R}\n"))
        available = []
        for rec in recipes:
            can   = all(mat_count.get(k,0) >= v for k,v in rec["needs"].items())
            mark  = f"{_GREEN}[OK]{_R}" if can else f"{_DIM}[--]{_R}"
            needs = ", ".join(f"{k}×{v}" for k,v in rec["needs"].items())
            print(C(f"{mark} {_WHITE}{rec['name']:<28}{_R} {_DIM}{needs}{_R}"))
            if can: available.append(rec)

        if not available:
            print(C(f"\n{_DIM}Nothing craftable. Gather more materials.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return

        print(C(f"\n{_CYAN}Craftable now:{_R}"))
        for i, rec in enumerate(available, 1):
            print(C(f"{_GOLD}[{i}]{_R} {_WHITE}{rec['name']}{_R}"))
        print(C(f"\n{_opt('0','Cancel')}"))
        ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
        if ch == "0" or not ch.isdigit(): return
        idx = int(ch)-1
        if not (0 <= idx < len(available)): return
        rec = available[idx]
        from game_items import remove_items
        for mat_name, qty in rec["needs"].items():
            remove_items(self.player.inventory, mat_name, qty)
        result = rec["result"]()
        self.player.add_item(result)
        print(C(f"\n{_GREEN}Crafted: {result}!{_R}"))
        input(C(f"{_DIM}(Press Enter){_R}"))

    # ── Garden ───────────────────────────────────────────────────

    def _garden_menu(self):
        if self.base.rooms["garden"] == 0:
            _clear()
            print(C(f"\n{_DIM}No garden yet. Upgrade Rooms → Garden.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return
        _clear()
        gt = self.base.rooms["garden"]
        tier = ROOMS["garden"]["tiers"][gt-1]
        print(C(f"\n{_CYAN}{_B}════  GARDEN  ════{_R}\n"))
        print(C(f"{_WHITE}{tier['name']}{_R}"))
        print(C(f"{_DIM}Yields {tier['yield']}x {tier['item']} every 2 rests at base.{_R}"))
        print(C(f"{_DIM}Rests since last harvest: {_GOLD}{self.base.garden_rests}/2{_R}"))
        if self.base.garden_rests >= 2:
            print(C(f"\n{_GREEN}★ Ready to harvest! Rest at your base to collect.{_R}"))
        else:
            print(C(f"\n{_DIM}Rest at base {2-self.base.garden_rests} more time(s) to harvest.{_R}"))
        input(C(f"\n{_DIM}(Press Enter){_R}"))

    # ── Trophy wall ───────────────────────────────────────────────

    def _trophy_menu(self):
        if self.base.rooms["trophy"] == 0:
            _clear()
            print(C(f"\n{_DIM}No trophy wall yet. Upgrade Rooms → Trophy Wall.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return
        _clear()
        tt = self.base.rooms["trophy"]
        tier = ROOMS["trophy"]["tiers"][tt-1]
        atk_b, def_b = self.base.trophy_bonus()
        print(C(f"\n{_GOLD}{_B}════  🏆 TROPHY WALL  ════{_R}\n"))
        print(C(f"{_WHITE}{tier['name']}{_R}  {_DIM}({tier['desc']}){_R}"))
        print(f"  {_YELL}Current bonus: +{atk_b} ATK  +{def_b} DEF  "
              f"({len(self.base.trophies)} trophies, +1 bonus per 3){_R}\n")
        if not self.base.trophies:
            print(C(f"{_DIM}No trophies yet. Defeat bosses to earn them!{_R}"))
        else:
            for i, t in enumerate(self.base.trophies, 1):
                print(f"  {_GOLD}[{i}]{_R} {_WHITE}{t['name']:<22}{_R} "
                      f"  {_DIM}({t.get('continent','?')}){_R}")
        input(C(f"\n{_DIM}(Press Enter){_R}"))

    # ── Rename ───────────────────────────────────────────────────

    def _rename(self):
        _clear()
        print(C(f"\nCurrent name: {_CYAN}{self.base.name}{_R}"))
        new_name = input(C(f"New name (Enter to cancel): ")).strip()
        if new_name:
            self.base.name = new_name
            print(C(f"{_GREEN}Renamed to {new_name}!{_R}"))
            input(C(f"{_DIM}(Enter){_R}"))


# ── Acquisition screens ───────────────────────────────────────────

def buy_plot_in_city(player, town_name, continent_id, x, y):
    """Called from Town menu. Returns True if base was purchased."""
    if player.bases.has_base(continent_id):
        _clear()
        print(C(f"\n{_DIM}You already have a base on this continent.{_R}"))
        base = player.bases.get_base(continent_id)
        print(C(f"{_CYAN}Your base: {base.name} in {base.location_name}{_R}"))
        ch = input(C(f"\n{_GOLD}[E]{_R} Enter your base  {_GOLD}[0]{_R} Back\n  > ")).strip()
        if ch.lower() == "e":
            BaseMenu(player, base).enter()
        return False

    _clear()
    plot_name = PLOT_NAMES.get(continent_id, f"{town_name} Homestead")
    mat_str = "  ".join(f"{k}×{v}" for k,v in PLOT_BUILD_MATS.items())

    print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════╗"))
    print(C(f"║  🏠  BUY A BASE PLOT                     ║"))
    print(C(f"╚══════════════════════════════════════════╝{_R}\n"))
    print(C(f"{_WHITE}Location:{_R} {town_name}"))
    print(C(f"{_WHITE}Name:{_R}     {plot_name}\n"))
    print(C(f"{_opt('1', f'Buy pre-built plot', f'{PLOT_COST_GOLD} gold')}"))

    # Check if can build from materials
    from game_items import material_counts
    mat_count = material_counts(player.inventory)
    can_build = all(mat_count.get(k, 0) >= v for k,v in PLOT_BUILD_MATS.items())
    build_col = _GREEN if can_build else _DIM
    print(C(f"{_opt('2', 'Build from materials', mat_str)}"))
    if not can_build:
        print(C(f"  {_RED}(Need: {mat_str}){_R}"))

    print(C(f"{_opt('0', 'Cancel')}"))
    print(C(f"\n{_DIM}Gold: {_GOLD}{player.gold}{_R}"))
    ch = input(C(f"\n{_GOLD}>{_R} ")).strip()

    if ch == "1":
        if player.gold < PLOT_COST_GOLD:
            print(C(f"\n{_RED}Need {PLOT_COST_GOLD}g (have {player.gold}g).{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return False
        player.gold -= PLOT_COST_GOLD
        _create_base(player, plot_name, town_name, continent_id, x, y)
        return True

    elif ch == "2":
        if not can_build:
            print(C(f"\n{_RED}Not enough materials.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return False
        from game_items import remove_items
        for mat_name, qty in PLOT_BUILD_MATS.items():
            remove_items(player.inventory, mat_name, qty)
        _create_base(player, plot_name, town_name, continent_id, x, y)
        return True

    return False


def build_base_on_map(player, x, y, continent_id):
    """Called when player presses B on the world map on a non-water land tile."""
    if player.bases.has_base(continent_id):
        print(C(f"\n{_DIM}You already have a base on this continent.{_R}"))
        input(C(f"{_DIM}(Enter){_R}")); return False

    from game_items import material_counts
    mat_count = material_counts(player.inventory)
    can_build = all(mat_count.get(k, 0) >= v for k,v in PLOT_BUILD_MATS.items())

    _clear()
    mat_str = "  ".join(f"{k}×{v}" for k,v in PLOT_BUILD_MATS.items())
    print(C(f"\n{_GOLD}{_B}Build a base here?{_R}\n"))
    print(C(f"{_DIM}Cost: {mat_str}{_R}"))
    if not can_build:
        print(C(f"\n{_RED}You don't have the required materials:{_R}"))
        for k, v in PLOT_BUILD_MATS.items():
            have = mat_count.get(k, 0)
            col  = _GREEN if have >= v else _RED
            print(C(f"  {col}{k}: {have}/{v}{_R}"))
        input(C(f"\n{_DIM}(Enter){_R}")); return False

    ch = input(C(f"\n{_opt('Y','Build here')}  {_opt('N','Cancel')}\n  {_GOLD}>{_R} ")).strip().lower()
    if ch != "y": return False

    from game_items import remove_items
    for mat_name, qty in PLOT_BUILD_MATS.items():
        remove_items(player.inventory, mat_name, qty)

    plot_name = PLOT_NAMES.get(continent_id, "Wilderness Outpost")
    _create_base(player, plot_name, "Wilderness", continent_id, x, y)
    return True


def _create_base(player, name, location, continent_id, x, y):
    base = PlayerBase(continent_id, name, location, x, y)
    player.bases.add_base(base)
    _clear()
    print(C(f"\n{_GREEN}{_B}★ {name} established!{_R}\n"))
    print(C(f"{_DIM}You now have a base on this continent.{_R}"))
    print(C(f"{_DIM}Access it from any city on this continent,{_R}"))
    print(C(f"{_DIM}or press [B] on the map when standing here.{_R}"))
    print(C(f"\n{_DIM}Your base starts with a basic Bedroll bedroom.{_R}"))
    print(C(f"{_DIM}Upgrade rooms with gold and materials to unlock more features.{_R}"))
    input(C(f"\n{_DIM}(Press Enter){_R}"))