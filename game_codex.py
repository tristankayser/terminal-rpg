"""
encyclopedia.py — In-game encyclopedia / codex.
Tabs: Enemies (what they drop), Shops (what each town sells),
      Crafting (all recipes + materials needed), Trading (barter offers).
"""

import os
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_lang import T, set_language, LANG, LANGUAGE_NAMES

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD =_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM  =_fg(100,100,100)
_GREEN=_fg(80,200,80);  _RED  =_fg(220,60,60);   _CYAN =_fg(80,220,220)
_YELL =_fg(240,200,60); _PURP =_fg(180,80,220);  _ORAN =_fg(220,140,40)
_TEAL =_fg(60,200,180)

def _clear(): clr()
def _div(w=60): return f"  {_DIM}{'─'*w}{_R}"
def _opt(k,l,h=""): return f"    {_GOLD}{_B}[{k}]{_R} {_WHITE}{l}{_R}" + (f"  {_DIM}{h}{_R}" if h else "")
def _pause(): input(f"\n  {_DIM}(Press Enter){_R}")

# ── Enemy drop data (mirrors items.py LOOT_TABLE) ────────────────
ENEMY_CODEX = {
    # name: {zone, desc, drops: [(item, chance_pct)], special}
    "Slime":         {"zone":"Plains","desc":"Weak gelatinous creature.",
                      "drops":[("Potion","30%")],"special":"None"},
    "Goblin":        {"zone":"Plains/Forest","desc":"Small, sneaky scavenger.",
                      "drops":[("Potion","50%"),("Wolf Pelt","20%")],"special":"None"},
    "Wolf":          {"zone":"Forest","desc":"Pack hunter, high dodge.",
                      "drops":[("Wolf Pelt","65%"),("Potion","25%")],"special":"High dodge (10%)"},
    "Bandit":        {"zone":"Plains","desc":"Armoured thug, high crit.",
                      "drops":[("Potion","40%"),("Iron Sword","12%")],"special":"High crit (12%)"},
    "Skeleton":      {"zone":"Dungeon","desc":"Undead warrior.",
                      "drops":[("Bone Shard","55%"),("Ether","20%")],"special":"None"},
    "Harpy":         {"zone":"Mountain","desc":"Flying creature, high dodge.",
                      "drops":[("Feather","55%"),("Ether","20%")],"special":"High dodge (14%)"},
    "Stone Golem":   {"zone":"Mountain","desc":"Massive stone construct, very tanky.",
                      "drops":[("Iron Ore","65%"),("Potion","25%")],"special":"High DEF"},
    "Sand Wyrm":     {"zone":"Desert","desc":"Burrowing desert predator.",
                      "drops":[("Scale Fragment","45%"),("Ether","30%")],"special":"None"},
    "Scorpion":      {"zone":"Desert","desc":"Venomous giant scorpion.",
                      "drops":[("Scale Fragment","30%")],"special":"Poison chance"},
    "Desert Raider": {"zone":"Desert","desc":"Nomadic desert warrior.",
                      "drops":[("Potion","35%")],"special":"High crit"},
    "Ice Wolf":      {"zone":"Snow","desc":"Frost-touched wolf pack.",
                      "drops":[("Frost Crystal","50%"),("Potion","25%")],"special":"Dodge (8%)"},
    "Frost Wraith":  {"zone":"Snow","desc":"Ethereal ice spirit, very evasive.",
                      "drops":[("Frost Crystal","60%"),("Hi-Ether","20%")],"special":"Dodge (15%)"},
    "Snow Beast":    {"zone":"Snow","desc":"Massive arctic predator.",
                      "drops":[("Frost Crystal","30%")],"special":"High HP"},
    "Shadow Beast":  {"zone":"Dungeon","desc":"Demon of darkness.",
                      "drops":[("Dark Shard","55%"),("God Potion","3%")],"special":"High crit+dodge"},
    "Cultist":       {"zone":"Dungeon","desc":"Servant of dark forces.",
                      "drops":[("Ether","45%"),("Dark Shard","25%")],"special":"None"},
    "Armored Knight":{"zone":"Dungeon","desc":"Undead knight in heavy armour.",
                      "drops":[("Iron Ore","40%")],"special":"Very high DEF"},
    "Goblin King":   {"zone":"Boss","desc":"Boss — leads goblin armies.",
                      "drops":[("Bone Shard","100%"),("Iron Ore","80%")],"special":"Phase 2 rage"},
    "Frost Dragon":  {"zone":"Boss","desc":"Boss — winged ice dragon.",
                      "drops":[("Frost Crystal","100%"),("Dragon Scale","50%")],"special":"Venom+drain"},
    "Shadow Lord":   {"zone":"Boss","desc":"Boss — ruler of darkness.",
                      "drops":[("Dark Shard","100%"),("Dragon Scale","40%")],"special":"Drain+venom"},
    "Dragon/Vaeltharion":{"zone":"Final Boss","desc":"The ancient dragon terrorising the world.",
                      "drops":[("Dragon Scale","90%"),("God Potion","12%")],"special":"Phase 2, all skills"},
}

# Everything below is generated from the live game data (loot tables, shop
# stock, recipes, mines) so the encyclopedia can never drift out of date.
# The old hand-written tables listed shop items that didn't exist and wrong
# drop rates.


def _pager(title, lines):
    """Show lines a screen at a time."""
    per = max(8, H() - 8)
    page = 0
    pages = max(1, (len(lines) + per - 1) // per)
    while True:
        _clear()
        print(C(f"\n{_CYAN}{_B}════  {title}  ════{_R}  {_DIM}Page {page+1}/{pages}{_R}\n"))
        for ln in lines[page*per:(page+1)*per]:
            print(C(ln))
        print()
        nav = []
        if page + 1 < pages: nav.append(f"{_GOLD}[N]{_R}{_DIM} Next{_R}")
        if page > 0:         nav.append(f"{_GOLD}[P]{_R}{_DIM} Prev{_R}")
        nav.append(f"{_GOLD}[0]{_R}{_DIM} Back{_R}")
        ch = input(C("   ".join(nav) + f"   {_GOLD}>{_R} ")).strip().lower()
        if ch == "n" and page + 1 < pages: page += 1
        elif ch == "p" and page > 0:       page -= 1
        elif ch in ("0", "q", ""):         return


def open_encyclopedia(player=None):
    while True:
        _clear()
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════════╗"))
        print(C(f"║  📖  ENCYCLOPEDIA & CODEX                    ║"))
        print(C(f"╚══════════════════════════════════════════════╝{_R}\n"))
        print(C(f"{_opt('1','Enemy Bestiary',     'Where enemies live and what they drop')}"))
        print(C(f"{_opt('2','Shop Directory',     'What each continent sells')}"))
        print(C(f"{_opt('3','Crafting Guide',     'All recipes, benches and materials')}"))
        print(C(f"{_opt('4','Material Sources',   'Where to farm each crafting material')}"))
        print(C(f"{_opt('5','Game Guide',         'Classes, combat, stealth, progression tips')}"))
        if player:
            print(C(f"{_opt('6','My Discoveries',    'Quests, trophies and milestones')}"))
        print(C(f"{_opt('7','Item Compendium',    'Every item, with its icon — type a number to inspect')}"))
        print(C(f"{_opt('0','Close',              '')}"))
        ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
        if ch in ("0", "", "q"): return
        elif ch == "1": _bestiary()
        elif ch == "2": _shop_directory()
        elif ch == "3": _crafting_guide()
        elif ch == "4": _material_sources()
        elif ch == "5": _game_guide()
        elif ch == "6" and player: _my_discoveries(player)
        elif ch == "7": _item_compendium(player)


_ZONE_LABEL = {"plains":"Plains","forest":"Forest","mountain":"Mountain","desert":"Desert",
               "snow":"Snow","dungeon":"Dungeon","dungeon_deep":"Deep dungeon",
               "dungeon_bottom":"Dungeon depths"}
_ZONE_COL = {"Plains":_fg(100,180,100),"Forest":_fg(40,140,40),"Mountain":_fg(140,130,110),
             "Desert":_fg(200,170,60),"Snow":_fg(180,210,255),"Dungeon":_fg(140,80,180),
             "Deep dungeon":_fg(160,70,200),"Dungeon depths":_fg(180,60,220),"Boss":_RED}


def _bestiary():
    from game_enemies import ZONE_ENEMIES, ENEMY_STATS, BOSS_DEFS, STORY_ONLY_BOSSES
    from game_items import LOOT_TABLE
    zones = {}
    for z, names in ZONE_ENEMIES.items():
        if z == "dragon_territory":
            continue
        for n in names:
            zones.setdefault(n, [])
            lbl = _ZONE_LABEL.get(z, z)
            if lbl not in zones[n]:
                zones[n].append(lbl)
    for b in BOSS_DEFS:
        if b != "Vaeltharion":
            zones[b] = ["Boss"]

    lines = []
    for name, zs in zones.items():
        col = _ZONE_COL.get(zs[0], _WHITE)
        desc = ENEMY_CODEX.get(name, {}).get("desc", "")
        if name == "Dragon":
            desc = "Vaeltharion the Ashen — final boss of the Dragon's Lair."
        lines.append(f"{_WHITE}{_B}{name:<16}{_R} {col}{'/'.join(zs):<22}{_R} {_DIM}{desc}{_R}")
        drops = LOOT_TABLE.get(name, [("Potion", 0.20)])
        dstr = "  ".join(f"{n} {_DIM}({int(c*100)}%){_R}" for n, c in drops)
        lines.append(f"   {_DIM}Drops:{_R} {_YELL}{dstr}{_R}")
        st = ENEMY_STATS.get(name, {})
        traits = []
        if st.get("dodge", 3) >= 8:   traits.append(f"dodge {st['dodge']}%")
        if st.get("crit", 5) >= 10:   traits.append(f"crit {st['crit']}%")
        if st.get("def_m", 1) >= 1.5: traits.append("heavy armour")
        if st.get("hp_m", 1) >= 1.8:  traits.append("very tough")
        if name in BOSS_DEFS:
            traits.append("skills: " + ", ".join(sorted(set(BOSS_DEFS[name]["boss_skills"]))))
        if traits:
            lines.append(f"   {_DIM}Traits:{_R} {_ORAN}{', '.join(traits)}{_R}")
    _pager("ENEMY BESTIARY", lines)


def _shop_directory():
    from game_items import town_shop_stock, shop_regions, item_glyph, describe_effect
    base = town_shop_stock("")

    def row(item, price):
        return (f"  {item_glyph(item)} {item.rarity_col()}{item.name:<22}{_R} "
                f"{_DIM}{describe_effect(item)[:34]:<34}{_R} {_GOLD}{price}g{_R}")

    lines = [f"{_GOLD}{_B}Every town{_R}"]
    for item, price in base:
        lines.append(row(item, price))
    for region in shop_regions():
        extra = town_shop_stock(region)[len(base):]
        lines.append("")
        label = region.title() if region in ("VALDMERE", "SUNSPIRE", "DUSKTHORN") else region
        lines.append(f"{_GOLD}{_B}{label} only{_R}")
        for item, price in extra:
            lines.append(row(item, price))
    _pager("SHOP DIRECTORY", lines)


# ── Item compendium (every item, with its icon on request) ────────
_COMPENDIUM_GROUPS = [
    ("Weapons",          ("weapon",)),
    ("Armour",           ("armor", "helmet", "shield", "cloak")),
    ("Rings & amulets",  ("ring", "amulet")),
    ("Potions & remedies", ("potion",)),
    ("Foods & tonics",   ("food",)),
    ("Bombs & scrolls",  ("bomb",)),
    ("Materials",        ("material",)),
    ("Key items",        ("key",)),
]


def _compendium_entries():
    """[(group label, [items])] built from the live item pools."""
    from game_items import (ITEM_POOL, SET_POOL, UNIQUE_POOL, KEY_ITEMS,
                            item_category, rarity_rank)
    items = []
    for pool in (ITEM_POOL, SET_POOL, UNIQUE_POOL, KEY_ITEMS):
        for fn in pool.values():
            try:
                items.append(fn())
            except Exception:
                pass
    out = []
    for label, cats in _COMPENDIUM_GROUPS:
        group = [it for it in items if item_category(it) in cats]
        group.sort(key=lambda it: (rarity_rank(getattr(it, "rarity", "common")), it.name))
        if group:
            out.append((label, group))
    return out


def _item_compendium(player=None):
    from game_items import item_glyph, describe_effect
    from game_icons import inspect_item, parse_inspect
    groups = _compendium_entries()
    flat, lines = [], []
    for label, group in groups:
        lines.append(f"{_GOLD}{_B}{label}{_R}  {_DIM}({len(group)}){_R}")
        for it in group:
            flat.append(it)
            set_tag = f" {_PURP}[{it.set_name}]{_R}" if getattr(it, "set_name", None) else ""
            lines.append(f"  {_GOLD}{len(flat):>3}{_R} {item_glyph(it)} {it.rarity_col()}{it.name:<26}{_R}"
                         f" {_DIM}{describe_effect(it)[:40]}{_R}{set_tag}")
        lines.append("")
    per = max(8, H() - 9)
    page, pages = 0, max(1, (len(lines) + per - 1) // per)
    while True:
        _clear()
        print(C(f"\n{_CYAN}{_B}════  ITEM COMPENDIUM  ════{_R}  {_DIM}{len(flat)} items · Page {page+1}/{pages}{_R}\n"))
        for ln in lines[page*per:(page+1)*per]:
            print(C(ln))
        nav = []
        if page + 1 < pages: nav.append(f"{_GOLD}[N]{_R}{_DIM} Next{_R}")
        if page > 0:         nav.append(f"{_GOLD}[P]{_R}{_DIM} Prev{_R}")
        nav.append(f"{_GOLD}[#]{_R}{_DIM} Inspect{_R}")
        nav.append(f"{_GOLD}[0]{_R}{_DIM} Back{_R}")
        ch = input(C("   ".join(nav) + f"   {_GOLD}>{_R} ")).strip().lower()
        n = parse_inspect(ch, len(flat))
        if n is None and ch.isdigit() and 1 <= int(ch) <= len(flat):
            n = int(ch)
        if n is not None:
            inspect_item(flat[n - 1], player)
        elif ch == "n" and page + 1 < pages: page += 1
        elif ch == "p" and page > 0:         page -= 1
        elif ch in ("0", "q", ""):           return


def _crafting_guide():
    from game_items import CRAFTING_RECIPES
    from game_base import ADVANCED_RECIPES
    def res_str(r):
        it = r["result"]()
        return it.stat_line() if hasattr(it, "stat_line") else f"{it.item_type} {it.value or ''}".strip()
    lines = [f"{_TEAL}{_B}Town crafting bench{_R}"]
    for rec in CRAFTING_RECIPES:
        needs = "  ".join(f"{k}×{v}" for k, v in rec["needs"].items())
        cls = f" {_DIM}({', '.join(rec['classes'][:2])}…){_R}" if rec.get("classes") else ""
        qty = f" x{rec['qty']}" if rec.get("qty", 1) > 1 else ""
        lines.append(f"  {_WHITE}{rec['name']+qty:<22}{_R} {_DIM}{needs}{_R}{cls}")
        lines.append(f"     {_DIM}→ {_GREEN}{res_str(rec)}{_R}")
    for tier in (1, 2, 3):
        lines.append("")
        lines.append(f"{_ORAN}{_B}Base workshop — tier {tier}{_R}")
        for rec in ADVANCED_RECIPES:
            if rec["tier"] != tier:
                continue
            needs = "  ".join(f"{k}×{v}" for k, v in rec["needs"].items())
            lines.append(f"  {_WHITE}{rec['name']:<22}{_R} {_DIM}{needs}{_R}")
            lines.append(f"     {_DIM}→ {_GREEN}{res_str(rec)}{_R}")
    _pager("CRAFTING GUIDE", lines)


def _material_sources():
    from game_items import LOOT_TABLE, ITEM_POOL
    from game_mining import ORE_TABLES
    from game_trading import ALL_TRADES
    sources = {}
    for enemy, table in LOOT_TABLE.items():
        for name, chance in table:
            it = ITEM_POOL.get(name)
            if it and it().item_type == "material":
                sources.setdefault(name, []).append(f"{enemy} {int(chance*100)}%")
    biome_name = {"forest":"Aeloria","mountain":"Ironspire","snow":"Frostheim",
                  "desert":"Ash Sands","tropical":"South Isles"}
    for biome, table in ORE_TABLES.items():
        for name, _ in table:
            tag = f"{biome_name.get(biome, biome)} mines"
            if tag not in sources.setdefault(name, []):
                sources[name].append(tag)
    for give, gq, recv, rq, _ in ALL_TRADES:
        it = ITEM_POOL.get(recv)
        if it and it().item_type == "material":
            sources.setdefault(recv, []).append(f"trader ({give}×{gq})")
    lines = []
    for mat in sorted(sources):
        lines.append(f"{_YELL}{mat:<16}{_R} {_DIM}{', '.join(sources[mat])}{_R}")
    lines.append("")
    lines.append(f"{_DIM}God Potion: Shadow Beast 3%, Dragon bosses, or trade a Dragon Scale.{_R}")
    _pager("MATERIAL SOURCES", lines)


def _game_guide():
    lines = [
        f"{_GOLD}{_B}Getting started{_R}",
        f"  Enter the town next to you [E]. Buy potions, take a guild quest [3], then explore.",
        f"  Enemies on the map (letters) chase you when they spot you — {_PURP}stealth{_R} shrinks their sight.",
        f"  Dungeons [X] have 3 floors with a boss at the bottom. Mines [M] give ore for crafting.",
        "",
        f"{_GOLD}{_B}Combat{_R}",
        f"  One key per turn: 1 attack · 2 skill · 3 item · 4 defend · 5 flee.",
        f"  Skills cost MP; if you lack MP the rest is paid in HP (never lethal).",
        f"  Fire Bombs deal heavy damage, Smoke Bombs guarantee an escape (not from bosses).",
        f"  Strength Draught: +ATK for 3 turns. Antidote cures poison & burn.",
        f"  Bosses scale with your level and enter PHASE 2 at half health.",
        "",
        f"{_GOLD}{_B}Stealth & sneak attacks{_R}",
        f"  Slipping past an enemy hides you for 4 steps: your next fight opens with a SNEAK ATTACK.",
        f"  Rogues, stealth gear and rogue companions raise your stealth.",
        "",
        f"{_GOLD}{_B}Progression{_R}",
        f"  Guild rank-ups [4] raise max HP/MP. Join a guild faction for permanent perks.",
        f"  Class awakening: start the class quest at a Quest Board, complete it, turn it in,",
        f"  then awaken at the Adventurers Guild for a stronger class and new skills.",
        f"  Customise [C] in town: pick a style for a passive perk; legendary skins via quests.",
        "",
        f"{_GOLD}{_B}Bases & clans{_R}",
        f"  Buy a plot in a city [H] or build one on the map [B] with materials.",
        f"  Resting at an inn or base passes a day: your founded clan earns gold.",
        f"  Trophy walls turn boss kills into permanent ATK/DEF bonuses.",
        "",
        f"{_GOLD}{_B}Death{_R}",
        f"  A God Potion revives you automatically. Without one you wake in the nearest",
        f"  city of that continent, losing 10% of your gold. Autosave runs every 30 steps.",
    ]
    _pager("GAME GUIDE", lines)


def _my_discoveries(player):
    _clear()
    print(C(f"\n{_CYAN}{_B}════  YOUR DISCOVERIES  ════{_R}\n"))
    completed = getattr(player, "completed_quests", [])
    flags     = getattr(player, "flags", {})
    trophies  = []
    if hasattr(player, "bases"):
        for base in player.bases.bases.values():
            trophies.extend(t["name"] for t in base.trophies)

    print(C(f"{_WHITE}Quests completed:{_R} {_GOLD}{len(completed)}{_R}"))
    for q in completed[-10:]:
        print(C(f"  {_DIM}✓ {q}{_R}"))

    cleared = [k[len("dungeon_cleared_"):] for k, v in flags.items()
               if k.startswith("dungeon_cleared_") and v]
    print(C(f"\n{_WHITE}Dungeons conquered:{_R} {_GOLD}{len(cleared)}{_R}"))
    for d in cleared:
        print(C(f"  {_DIM}⚔ {d}{_R}"))

    print(C(f"\n{_WHITE}Boss trophies:{_R}"))
    if trophies:
        for t in trophies:
            print(C(f"  {_GOLD}🏆 {t}{_R}"))
    else:
        print(C(f"  {_DIM}None yet. Build a Trophy Wall at your base, then defeat bosses!{_R}"))

    dragon_slain = flags.get("dragon_slain", False)
    print(C(f"\n{_WHITE}Dragon slain:{_R} {(_GREEN+'Yes'+_R) if dragon_slain else (_DIM+'No'+_R)}"))
    _pause()
