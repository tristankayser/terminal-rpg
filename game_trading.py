"""
trading.py — Trading / barter system for Terminal-RPG.
Traders appear in towns. Each has a rotating stock of offers.
You give one item, you get another. No gold involved — pure barter.
Some traders offer rare items in exchange for specific materials, and
every continent's traders want (and pay in) their own regional goods.
Type ?3 / x3 to inspect what offer 3 would give you.
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
# rarity: "common"|"uncommon"|"rare"|"epic"

ALL_TRADES = [
    # Common material swaps
    ("Wolf Pelt",      2, "Potion",        3, "common"),
    ("Wolf Pelt",      3, "Hi-Potion",     2, "common"),
    ("Bone Shard",     3, "Ether",         2, "common"),
    ("Iron Ore",       2, "Potion",        4, "common"),
    ("Iron Ore",       4, "Hi-Ether",      1, "common"),
    ("Feather",        4, "Ether",         3, "common"),
    ("Feather",        2, "Potion",        5, "common"),
    ("Bone Shard",     2, "Bandage",       4, "common"),
    ("Leather Strip",  3, "Traveller's Bread", 3, "common"),
    ("Linen Cloth",    3, "Bandage",       5, "common"),
    ("Ancient Coin",   1, "Spiced Jerky",  2, "common"),
    ("Venom Fang",     2, "Antidote",      3, "common"),
    # Uncommon — materials for gear
    ("Iron Ore",       5, "Iron Sword",    1, "uncommon"),
    ("Frost Crystal",  3, "Hi-Ether",      2, "uncommon"),
    ("Scale Fragment", 2, "Hi-Potion",     3, "uncommon"),
    ("Dark Shard",     2, "Hi-Ether",      2, "uncommon"),
    ("Wolf Pelt",      5, "Leather Armor", 1, "uncommon"),
    ("Bone Shard",     6, "Iron Ore",      4, "uncommon"),
    ("Scale Fragment", 4, "Frost Crystal", 3, "uncommon"),
    ("Frost Crystal",  4, "Dark Shard",    2, "uncommon"),
    ("Ancient Coin",   3, "Escape Scroll", 1, "uncommon"),
    ("Gold Nugget",    1, "Silver Ring",   1, "uncommon"),
    ("Mana Stone",     2, "Spark Wand",    1, "uncommon"),
    ("Iron Ore",       6, "Steel Ingot",   2, "uncommon"),
    ("Shadow Cloth",   2, "Smoke Bomb",    3, "uncommon"),
    ("Obsidian Shard", 1, "Frost Bomb",    2, "uncommon"),
    # Rare — valuable items for precious materials
    ("Dragon Scale",   1, "God Potion",    1, "rare"),
    ("Dragon Scale",   2, "Hi-Potion",     8, "rare"),
    ("Dark Shard",     5, "Hi-Ether",      5, "rare"),
    ("Frost Crystal",  6, "Hi-Potion",     6, "rare"),
    ("Dragon Scale",   1, "Hi-Ether",      5, "rare"),
    ("Runic Stone",    2, "Talisman of Warding", 1, "rare"),
    ("Holy Relic",     2, "Panacea",       3, "rare"),
    ("Ruby",           2, "Lucky Rabbit Foot", 1, "rare"),
    ("Mithril Ore",    2, "Silversteel Sword", 1, "rare"),
    ("Phoenix Feather",1, "Troll Blood Draught", 3, "rare"),
    # Epic — rare chance per trader
    ("Dragon Scale",   3, "Mana Crystal",  2, "epic"),
    ("Phoenix Feather",2, "Elixir of Life",1, "epic"),
    ("Soul Ember",     2, "Hellfire Flask",3, "epic"),
    ("Lumeris Silver", 2, "Lumeris Signet",1, "epic"),
]

# One extra offer per continent: they want the local stuff.
REGION_TRADES = {
    "AELORIA":     [("Silverleaf Herb", 4, "Herbal Poultice", 3, "common"),
                    ("Oak Heartwood",   3, "Hunting Bow",     1, "uncommon"),
                    ("Amber Resin",     2, "Honeycake",       4, "uncommon")],
    "IRONSPIRE":   [("Coal Lump",       5, "Steel Ingot",     1, "common"),
                    ("Steel Ingot",     3, "Barbute",         1, "uncommon"),
                    ("Forge Ember",     2, "Scroll of Fireball", 2, "rare")],
    "FROSTHEIM":   [("Winter Pelt",     2, "Frostheim Mead",  2, "common"),
                    ("Yeti Fur",        2, "Wool Cloak",      1, "common"),
                    ("Mammoth Ivory",   1, "Giant's Tonic",   2, "rare")],
    "ASH SANDS":   [("Desert Glass",    3, "Sunspire Mint Tea", 2, "common"),
                    ("Scorpion Chitin", 3, "Venom Flask",     2, "uncommon"),
                    ("Djinn Dust",      1, "Scroll of Lightning", 2, "rare")],
    "SOUTH ISLES": [("Tide Shell",      3, "Coconut Water",   4, "common"),
                    ("Coral Branch",    3, "Tidecaller Grog", 3, "common"),
                    ("Pearl",           2, "Kris Knife",      1, "uncommon")],
}


# Builds an actual Item/Equipment from a name
def _make_item(name, qty=1):
    from game_items import Item, Equipment, make_item
    out = []
    for _ in range(qty):
        it = make_item(name)
        if it is None:
            # Unknown name (old data): a harmless material placeholder
            it = Item(name, "material", 0, 10)
        out.append(it)
    return out


def _region_of_town(town_name):
    """Continent name of a town, from the world's city/port lists (or None)."""
    try:
        from game_world import CONTINENTS
        for c in CONTINENTS:
            if town_name in c.get("cities", []) or town_name in c.get("ports", []):
                return c["name"]
    except Exception:
        pass
    return None


class Trader:
    """A travelling trader with a handful of barter offers."""

    TRADER_NAMES = [
        "Mira the Wanderer", "Old Gregor", "Sable the Merchant",
        "Duskwind", "Fenris the Peddler", "Lady Rova",
        "Thane the Collector", "Whisper Market", "Ironhand Trader",
    ]

    def __init__(self, town_name, seed=None, region=None):
        # Stable seed (str hash() is randomised per run, so the trader's
        # stock used to change every time you restarted the game)
        import zlib
        rng = random.Random(seed or zlib.crc32(town_name.encode("utf-8")))
        self.name   = rng.choice(self.TRADER_NAMES)
        self.town   = town_name
        self.region = (region or _region_of_town(town_name) or "").upper()
        # 2 common, 2 uncommon, 1 rare, sometimes 1 epic, + 1 regional
        pool_c = [t for t in ALL_TRADES if t[4]=="common"]
        pool_u = [t for t in ALL_TRADES if t[4]=="uncommon"]
        pool_r = [t for t in ALL_TRADES if t[4]=="rare"]
        pool_e = [t for t in ALL_TRADES if t[4]=="epic"]

        offers = (rng.sample(pool_c, min(2, len(pool_c))) +
                  rng.sample(pool_u, min(2, len(pool_u))) +
                  rng.sample(pool_r, min(1, len(pool_r))))
        if pool_e and rng.random() < 0.25:
            offers.append(rng.choice(pool_e))
        regional = REGION_TRADES.get(self.region, [])
        if regional:
            offers.append(rng.choice(regional))
        rng.shuffle(offers)
        # No two offers asking for and giving the same pair
        seen, uniq = set(), []
        for o in offers:
            key = f"{o[0]}>{o[2]}"
            if key not in seen:
                seen.add(key); uniq.append(o)
        self.offers = uniq[:7]

    def open(self, player):
        from game_items import entry_qty, remove_items, inventory_add, item_glyph, rarity_colour
        from game_icons import parse_inspect, inspect_item
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
                r_col = rarity_colour(rarity)
                have_str = f"{_DIM}(have {have.get(give_n,0)}){_R}"
                proto = _make_item(recv_n, 1)[0]
                print(C(f"{_GOLD}{_B}[{i}]{_R} {mark}  "
                        f"{_RED}Give:{_R} {_WHITE}{give_n} ×{give_q}{_R} {have_str}  "
                        f"{_GREEN}Get:{_R} {item_glyph(proto)} {proto.rarity_col()}{recv_n}{_R} {_WHITE}×{recv_q}{_R}  "
                        f"{r_col}[{rarity}]{_R}"))
                if can:
                    tradeable.append((i-1, give_n, give_q, recv_n, recv_q))

            print(C(f"\n{_opt('0','Leave trader')}   {_DIM}?# inspects what you'd get{_R}"))
            if not tradeable:
                print(C(f"\n{_DIM}You don't have enough of the required items for any trade.{_R}"))

            ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
            n = parse_inspect(ch, len(self.offers))
            if n is not None:
                inspect_item(_make_item(self.offers[n-1][2], 1)[0], player)
                continue
            if ch in ("0", ""): return
            if not ch.isdigit(): continue
            idx = int(ch)-1
            if not (0 <= idx < len(self.offers)): continue

            give_n, give_q, recv_n, recv_q, rarity = self.offers[idx]
            if have.get(give_n, 0) < give_q:
                print(C(f"\n{_RED}You need {give_q}x {give_n} for this trade.{_R}"))
                input(C(f"{_DIM}(Enter){_R}")); continue

            # Execute trade on a copy of the bag first, so a full bag can't
            # swallow the payment and drop the goods on the floor.
            import copy
            bag = copy.deepcopy(player.inventory)
            remove_items(bag, give_n, give_q)
            if not all(inventory_add(bag, item) for item in _make_item(recv_n, recv_q)):
                print(C(f"\n{_RED}Your bag is too full to take {recv_n} ×{recv_q}.{_R}"))
                input(C(f"{_DIM}(Enter){_R}")); continue
            player.inventory[:] = bag

            print(C(f"\n{_GREEN}Trade complete!{_R}"))
            print(C(f"Gave: {_RED}{give_n} ×{give_q}{_R}  →  Got: {_GREEN}{recv_n} ×{recv_q}{_R}"))
            input(C(f"{_DIM}(Press Enter){_R}"))

            # Remove this offer (one-time trade, remembered in the save)
            done.append(f"{give_n}>{recv_n}")
            self.offers.pop(idx)
            if not self.offers:
                print(C(f"\n{_DIM}{self.name} has nothing left to trade.{_R}"))
                input(C(f"{_DIM}(Enter){_R}")); return


def open_trader_in_town(player, town_name, region=None):
    """Open a trader in the given town. Seed from town name so it's consistent per session."""
    t = Trader(town_name, region=region)
    t.open(player)
