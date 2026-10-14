"""
game_sell.py — Fast item selling interface for Terminal-RPG.

Features:
  • Sell individual items (stacks by quantity or whole stack)
  • Sell all materials / all consumables / all common gear (one key each)
  • Inspect any item before selling: type ?3 or x3 to see its icon card
  • Key items can never be sold; epic/legendary sales ask for confirmation
"""

import os
from game_term import C, clr, W
from game_items import (
    Equipment, Item, ItemStack, RARITIES,
    sell_all_materials, sell_all_consumables,
    inventory_remove, INVENTORY_LIMIT, item_glyph, describe_effect
)

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60);     _CYAN=_fg(80,220,220)
_YELL=_fg(240,200,60); _ORAN=_fg(220,140,40);   _PURP=_fg(180,80,220)

RARITY_ORDER = list(RARITIES)


def _row(i, entry, mult):
    """One list row: [n] glyph name (xN) — detail — price."""
    item = entry.item if isinstance(entry, ItemStack) else entry
    qty = entry.qty if isinstance(entry, ItemStack) else 1
    glyph = item_glyph(item)
    if item.item_type == "key":
        return (f"  {_GOLD}[{i:2}]{_R} {glyph} {item.rarity_col()}{item.name}{_R}  "
                f"{_DIM}key item — not for sale{_R}")
    sv = int(item.sell_value * mult)
    if isinstance(item, Equipment):
        return (f"  {_GOLD}[{i:2}]{_R} {glyph} {item.rarity_col()}{item.name}{_R}  "
                f"{_DIM}[{item.slot}] {item.stat_line()}{_R}  {_GOLD}→ {sv}g{_R}")
    qty_str = f" x{qty}" if qty > 1 else ""
    total_str = f"  {_DIM}(+{sv*qty}g total){_R}" if qty > 1 else ""
    type_col = _item_type_col(item.item_type)
    ea = " ea" if qty > 1 else ""
    return (f"  {_GOLD}[{i:2}]{_R} {glyph} {type_col}{item.name}{qty_str}{_R}  "
            f"{_DIM}{describe_effect(item)}{_R}{total_str}  {_GOLD}→ {sv}g{ea}{_R}")


def open_sell_screen(player, shop_sell_multiplier=0.5):
    """
    Full-screen sell interface. Called from shop or inventory.
    shop_sell_multiplier: fraction of sell_value the shop pays (default 50%).
    """
    inv = player.inventory
    page, per = 0, 10

    while True:
        clr()
        total_items = len(inv)
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════╗"))
        print(C(f"║   💰  SELL ITEMS                          ║"))
        print(C(f"╚══════════════════════════════════════════╝{_R}"))
        print(C(f"  {_DIM}Gold: {_GOLD}{player.gold}g{_R}   Bag: {total_items}/{INVENTORY_LIMIT} slots   "
                f"{_DIM}(equipped gear is never sold){_R}\n"))

        # Quick sell options
        mat_val  = _preview_sell_materials(inv, shop_sell_multiplier)
        cons_val = _preview_sell_consumables(inv, shop_sell_multiplier)
        gear_val = _preview_sell_common_gear(inv, shop_sell_multiplier)

        print(C(f"  {_GOLD}[M]{_R} Sell ALL materials   → {_GOLD}+{mat_val}g{_R}"))
        print(C(f"  {_GOLD}[P]{_R} Sell ALL consumables → {_GOLD}+{cons_val}g{_R}"))
        print(C(f"  {_GOLD}[G]{_R} Sell all COMMON gear → {_GOLD}+{gear_val}g{_R}"))
        print(C(f"  {_DIM}{'─'*42}{_R}"))

        # Individual item list
        start = page * per
        chunk = inv[start:start+per]

        if not inv:
            print(C(f"  {_DIM}Bag is empty.{_R}"))
        else:
            for i, entry in enumerate(chunk):
                print(C(_row(i + 1, entry, shop_sell_multiplier)))

        total_pages = max(1, (len(inv)-1)//per+1) if inv else 1
        print(C(f"\n  {_DIM}Page {page+1}/{total_pages}{_R}"))
        print(C(f"  {_GOLD}[#]{_R} Sell  {_GOLD}[?#]{_R} Inspect  {_GOLD}[N]{_R} Next  "
                f"{_GOLD}[B]{_R} Prev  {_GOLD}[0]{_R} Done"))

        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()

        from game_icons import parse_inspect, inspect_item
        n = parse_inspect(ch, len(chunk))
        if n is not None:
            inspect_item(chunk[n - 1], player)
            continue

        if ch == "0":
            return

        elif ch == "m":
            earned = sell_all_materials(inv, player, shop_sell_multiplier)
            if earned:
                print(C(f"{_GREEN}Sold all materials for {_GOLD}+{earned}g{_R}!"))
            else:
                print(C(f"{_DIM}No materials to sell.{_R}"))
            input(C(f"{_DIM}Enter...{_R}"))

        elif ch == "p":
            earned = sell_all_consumables(inv, player, shop_sell_multiplier)
            if earned:
                print(C(f"{_GREEN}Sold all consumables for {_GOLD}+{earned}g{_R}!"))
            else:
                print(C(f"{_DIM}No consumables to sell.{_R}"))
            input(C(f"{_DIM}Enter...{_R}"))

        elif ch == "g":
            earned = _sell_common_gear(inv, player, shop_sell_multiplier)
            if earned:
                print(C(f"{_GREEN}Sold all common gear for {_GOLD}+{earned}g{_R}!"))
            else:
                print(C(f"{_DIM}No common gear to sell.{_R}"))
            input(C(f"{_DIM}Enter...{_R}"))

        elif ch == "n":
            if (page+1)*per < len(inv):
                page += 1

        elif ch == "b":
            if page > 0:
                page -= 1

        elif ch.isdigit():
            idx = int(ch) - 1
            real_idx = start + idx
            if 0 <= idx < len(chunk):
                entry = chunk[idx]
                item_obj = entry.item if isinstance(entry, ItemStack) else entry
                if item_obj.item_type == "key":
                    print(C(f"  {_YELL}{item_obj.name} is a key item — the merchant won't touch it.{_R}"))
                    input(C(f"{_DIM}Enter...{_R}"))
                    continue
                if item_obj.item_type == "god":
                    ok = input(C(f"  {_YELL}Sell your God Potion? It revives you at 0 HP. (y/n) {_R}")).strip().lower()
                    if ok != "y":
                        continue
                elif getattr(item_obj, "rarity", "common") in ("epic", "legendary"):
                    ok = input(C(f"  {_YELL}Sell {item_obj.rarity} {item_obj.name}? (y/n) {_R}")).strip().lower()
                    if ok != "y":
                        continue
                if isinstance(entry, ItemStack) and entry.qty > 1:
                    # Ask how many to sell
                    print(C(f"  Sell how many? (1–{entry.qty}, or 'a' for all): "), end="", flush=True)
                    amt_str = input().strip().lower()
                    if amt_str == "a":
                        amt = entry.qty
                    elif amt_str.isdigit():
                        amt = min(int(amt_str), entry.qty)
                        if amt <= 0:
                            continue
                    else:
                        continue
                    sv = int(entry.item.sell_value * shop_sell_multiplier) * amt
                    entry.qty -= amt
                    if entry.qty <= 0:
                        inv.pop(real_idx)
                    player.gold += sv
                    print(C(f"{_GREEN}Sold {amt}x {entry.item.name} for {_GOLD}+{sv}g{_R}!"))
                else:
                    # Sell single item
                    sv = int(item_obj.sell_value * shop_sell_multiplier)
                    inv.pop(real_idx)
                    player.gold += sv
                    print(C(f"{_GREEN}Sold {item_obj.name} for {_GOLD}+{sv}g{_R}!"))
                input(C(f"{_DIM}Enter...{_R}"))
                # Keep page in range
                if page > 0 and start >= len(inv):
                    page -= 1


def _item_type_col(item_type):
    return {
        "heal":     _GREEN,
        "mana":     _CYAN,
        "god":      _GOLD,
        "antidote": _YELL,
        "bomb":     _ORAN,
        "buff":     _PURP,
        "material": _DIM,
    }.get(item_type, _WHITE)


def _preview_sell_materials(inv, mult):
    total = 0
    for e in inv:
        if isinstance(e, ItemStack) and e.item.item_type == "material":
            total += int(e.item.sell_value * mult) * e.qty
        elif isinstance(e, Item) and not isinstance(e, Equipment) and e.item_type == "material":
            total += int(e.sell_value * mult)
    return total


def _preview_sell_consumables(inv, mult):
    consumable_types = {"heal","mana","antidote","bomb","buff"}
    total = 0
    for e in inv:
        if isinstance(e, ItemStack) and e.item.item_type in consumable_types:
            total += int(e.item.sell_value * mult) * e.qty
        elif isinstance(e, Item) and not isinstance(e, Equipment) and e.item_type in consumable_types:
            total += int(e.sell_value * mult)
    return total


def _preview_sell_common_gear(inv, mult):
    total = 0
    for e in inv:
        if isinstance(e, Equipment) and e.rarity == "common":
            total += int(e.sell_value * mult)
    return total


def _sell_common_gear(inv, player, mult):
    to_remove = [i for i, e in enumerate(inv)
                 if isinstance(e, Equipment) and e.rarity == "common"]
    earned = sum(int(inv[i].sell_value * mult) for i in to_remove)
    for i in reversed(to_remove):
        inv.pop(i)
    player.gold += earned
    return earned
