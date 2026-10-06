"""
trading.py — Trading / barter system for Terminal-RPG.
Traders appear in towns. Each has a rotating stock of offers.
You give one item, you get another. No gold involved — pure barter.
Some traders offer rare items in exchange for specific materials.
"""

import random, os
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_lang import T, set_language, LANG, LANGUAGE_NAMES

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD =_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM  =_fg(100,100,100)
_GREEN=_fg(80,200,80);  _RED  =_fg(220,60,60);   _CYAN =_fg(80,220,220)
_YELL =_fg(240,200,60); _PURP =_fg(180,80,220);  _ORAN =_fg(220,140,40)

def _clear(): clr()
def _opt(k,l,h=""): return f"    {_GOLD}{_B}[{k}]{_R} {_WHITE}{l}{_R}" + (f"  {_DIM}{h}{_R}" if h else "")

# ── Trade offer templates ─────────────────────────────────────────
# (give_name, give_qty, receive_name, receive_qty, rarity)
# rarity: "common"|"uncommon"|"rare"

ALL_TRADES = [
    # Common material swaps
    ("Wolf Pelt",      2, "Potion",        3, "common"),
    ("Wolf Pelt",      3, "Hi-Potion",     2, "common"),
    ("Bone Shard",     3, "Ether",         2, "common"),
    ("Iron Ore",       2, "Potion",        4, "common"),
    ("Iron Ore",       4, "Hi-Ether",      1, "common"),
    ("Feather",        4, "Ether",         3, "common"),
    ("Feather",        2, "Potion",        5, "common"),
    # Uncommon — materials for gear
    ("Iron Ore",       5, "Iron Sword",    1, "uncommon"),   # Equipment("Iron Sword","weapon",atk_bonus=5)
    ("Frost Crystal",  3, "Hi-Ether",      2, "uncommon"),
    ("Scale Fragment", 2, "Hi-Potion",     3, "uncommon"),
    ("Dark Shard",     2, "Hi-Ether",      2, "uncommon"),
    ("Wolf Pelt",      5, "Leather Armor", 1, "uncommon"),
    ("Bone Shard",     6, "Iron Ore",      4, "uncommon"),
    ("Scale Fragment", 4, "Frost Crystal", 3, "uncommon"),
    ("Frost Crystal",  4, "Dark Shard",    2, "uncommon"),
    # Rare — valuable items for precious materials
    ("Dragon Scale",   1, "God Potion",    1, "rare"),
    ("Dragon Scale",   2, "Hi-Potion",     8, "rare"),
    ("Dark Shard",     5, "Hi-Ether",      5, "rare"),
    ("Frost Crystal",  6, "Hi-Potion",     6, "rare"),
    ("Dragon Scale",   1, "Hi-Ether",      5, "rare"),
]

# Builds an actual Item/Equipment from a name
def _make_item(name, qty=1):
    from game_items import Item, Equipment, ITEM_POOL
    if name in ITEM_POOL:
        return [ITEM_POOL[name]() for _ in range(qty)]
    # Fallback for equipment names not in ITEM_POOL
    if name == "Iron Sword":
        return [Equipment("Iron Sword","weapon",atk_bonus=5,sell_value=25) for _ in range(qty)]
    if name == "Leather Armor":
        return [Equipment("Leather Armor","armor",hp_bonus=20,def_bonus=4,sell_value=20) for _ in range(qty)]
    return [Item(name,"material",0,10) for _ in range(qty)]


class Trader:
    """A travelling trader with a handful of barter offers."""

    TRADER_NAMES = [
        "Mira the Wanderer", "Old Gregor", "Sable the Merchant",
        "Duskwind", "Fenris the Peddler", "Lady Rova",
        "Thane the Collector", "Whisper Market", "Ironhand Trader",
    ]

    def __init__(self, town_name, seed=None):
        # Stable seed (str hash() is randomised per run, so the trader's
        # stock used to change every time you restarted the game)
        import zlib
        rng = random.Random(seed or zlib.crc32(town_name.encode("utf-8")))
        self.name   = rng.choice(self.TRADER_NAMES)
        self.town   = town_name
        # Pick 3–5 offers: at least 2 common, 1–2 uncommon, 0–1 rare
        pool_c = [t for t in ALL_TRADES if t[4]=="common"]
        pool_u = [t for t in ALL_TRADES if t[4]=="uncommon"]
        pool_r = [t for t in ALL_TRADES if t[4]=="rare"]

        offers = (rng.sample(pool_c, min(2, len(pool_c))) +
                  rng.sample(pool_u, min(2, len(pool_u))) +
                  rng.sample(pool_r, min(1, len(pool_r))))
        rng.shuffle(offers)
        self.offers = offers[:5]

    def open(self, player):
        from game_items import entry_qty, remove_items
        # Trades already completed in this town stay completed
        done = player.flags.setdefault("trades_done", {}).setdefault(self.town, [])
        self.offers = [o for o in self.offers if f"{o[0]}>{o[2]}" not in done]
        if not self.offers:
            _clear()
            print(C(f"\n{_DIM}{self.name} has nothing left to trade with you.{_R}"))
            input(C(f"{_DIM}(Enter){_R}")); return
        while True:
            _clear()
            # Count player items (stack-aware)
            have = {}
            for it in player.inventory:
                have[it.name] = have.get(it.name, 0) + entry_qty(it)

            print(C(f"\n{_YELL}{_B}╔══════════════════════════════════════════════╗"))
            print(C(f"║  🧳  TRADER: {self.name:<32}║"))
            print(C(f"╚══════════════════════════════════════════════╝{_R}\n"))
            print(C(f"{_DIM}Pure barter — no gold needed. Give what they want, get what you need.{_R}\n"))

            tradeable = []
            for i, (give_n, give_q, recv_n, recv_q, rarity) in enumerate(self.offers, 1):
                can   = have.get(give_n, 0) >= give_q
                mark  = f"{_GREEN}[✓]{_R}" if can else f"{_DIM}[✗]{_R}"
                r_col = _DIM if rarity=="common" else _ORAN if rarity=="uncommon" else _PURP
                have_str = f"{_DIM}(have {have.get(give_n,0)}){_R}"
                print(C(f"{_GOLD}{_B}[{i}]{_R} {mark}  "
                        f"{_RED}Give:{_R} {_WHITE}{give_n} ×{give_q}{_R} {have_str}  "
                        f"{_GREEN}Get:{_R} {_WHITE}{recv_n} ×{recv_q}{_R}  "
                        f"{r_col}[{rarity}]{_R}"))
                if can:
                    tradeable.append((i-1, give_n, give_q, recv_n, recv_q))

            print(C(f"\n{_opt('0','Leave trader')}"))
            if not tradeable:
                print(C(f"\n{_DIM}You don't have enough of the required items for any trade.{_R}"))

            ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
            if ch in ("0", ""): return
            if not ch.isdigit(): continue
            idx = int(ch)-1
            if not (0 <= idx < len(self.offers)): continue

            give_n, give_q, recv_n, recv_q, rarity = self.offers[idx]
            if have.get(give_n, 0) < give_q:
                print(C(f"\n{_RED}You need {give_q}x {give_n} for this trade.{_R}"))
                input(C(f"{_DIM}(Enter){_R}")); continue

            # Execute trade — remove given items (stack-aware)
            remove_items(player.inventory, give_n, give_q)

            # Add received items
            received = _make_item(recv_n, recv_q)
            for item in received:
                player.add_item(item)

            print(C(f"\n{_GREEN}Trade complete!{_R}"))
            print(C(f"Gave: {_RED}{give_n} ×{give_q}{_R}  →  Got: {_GREEN}{recv_n} ×{recv_q}{_R}"))
            input(C(f"{_DIM}(Press Enter){_R}"))

            # Remove this offer (one-time trade, remembered in the save)
            done.append(f"{give_n}>{recv_n}")
            self.offers.pop(idx)
            if not self.offers:
                print(C(f"\n{_DIM}{self.name} has nothing left to trade.{_R}"))
                input(C(f"{_DIM}(Enter){_R}")); return


def open_trader_in_town(player, town_name):
    """Open a trader in the given town. Seed from town name so it's consistent per session."""
    t = Trader(town_name)
    t.open(player)
