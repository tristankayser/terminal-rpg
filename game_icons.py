"""
game_icons.py — ASCII item icons and the "inspect item" card.

Every icon is original ASCII art, 12 columns x 6 rows, coloured by mask:
  * frame  characters take the item's RARITY colour
  * body   characters take the icon's material colour (steel, wood, glass ...)
  * accent characters take the item's ELEMENT colour (fire red, ice cyan,
    shadow purple, holy gold, poison green, arcane violet ...) or the icon's
    own accent colour (e.g. the liquid of a potion)

Public API
  item_icon(item)                 -> list[str]  coloured icon lines (12 wide)
  icon_key(item)                  -> str        which icon an item uses
  render_card(item, player=None)  -> list[str]  full inspect card (no I/O)
  inspect_item(item, player=None, actions="") -> str  show card, return key
  parse_inspect(cmd)              -> int|None   '?3' / 'x3' / 'i3' -> 3

Python 3.8+, standard library only.
"""

from game_term import C, W, clr, _vis
from game_items import (Item, Equipment, ItemStack, RARITY_LABEL, rarity_colour,
                        element_colour, describe_effect, item_category, _info,
                        AFFIXES, affix_name, affix_stats, CONSUMABLE_FX, EXTRA_STATS)

R_ = "\033[0m"
B_ = "\033[1m"


def _fg(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"


C_DIM = _fg(120, 120, 130)
C_WHITE = _fg(230, 230, 230)
C_GOLD = _fg(255, 215, 0)
C_GREEN = _fg(90, 210, 110)
C_RED = _fg(230, 70, 70)
C_CYAN = _fg(80, 220, 220)

ICON_W = 12
ICON_H = 6

# Material colours
STEEL = (175, 185, 200)
WOOD = (150, 105, 60)
GLASS = (150, 190, 210)
CLOTH = (170, 150, 120)
BONE = (225, 215, 190)
GOLDC = (230, 190, 70)
STONE = (140, 135, 125)
LEATHER = (150, 100, 65)
PAPER = (215, 200, 160)
FUR = (165, 150, 135)

RED_LIQ = (225, 55, 65)
BLUE_LIQ = (70, 130, 245)
PURP_LIQ = (175, 85, 235)
GREEN_LIQ = (95, 205, 90)
GOLD_LIQ = (255, 210, 80)

# key: (art lines, accent chars, body chars, body rgb, default accent rgb)
ICONS = {
    "sword": ([
        r"     /\     ",
        r"     ||     ",
        r"     ||     ",
        r"     ||     ",
        r"   <=@@=>   ",
        r"     ##     ",
    ], "@", "|/\\", STEEL, (220, 60, 60)),
    "greatsword": ([
        r"     /\     ",
        r"    |  |    ",
        r"    |  |    ",
        r" <==|@@|==> ",
        r"     ##     ",
        r"     ()     ",
    ], "@", "|/\\", STEEL, (220, 60, 60)),
    "dagger": ([
        r"            ",
        r"     /|     ",
        r"     ||     ",
        r"   -=@@=-   ",
        r"     ##     ",
        r"     ()     ",
    ], "@", "|/", STEEL, (200, 60, 200)),
    "scimitar": ([
        r"        _   ",
        r"       / )  ",
        r"      / /   ",
        r"     / /    ",
        r"  <=@@=/    ",
        r"    ##      ",
    ], "@", "/)_", STEEL, (240, 200, 60)),
    "bow": ([
        r"    (\      ",
        r"    | \     ",
        r" >--|--@>   ",
        r"    | /     ",
        r"    (/      ",
        r"            ",
    ], "@>", "(\\/", WOOD, (200, 200, 200)),
    "staff": ([
        r"    .@.     ",
        r"   ( @ )    ",
        r"    '|'     ",
        r"     |      ",
        r"     |      ",
        r"     |      ",
    ], "@", "|", WOOD, (120, 200, 255)),
    "wand": ([
        r"     * .    ",
        r"   . \@/    ",
        r"     /      ",
        r"    /       ",
        r"   /        ",
        r"  #         ",
    ], "*@.", "/", WOOD, (255, 230, 120)),
    "mace": ([
        r"    \|/     ",
        r"   -(@)-    ",
        r"    /|\     ",
        r"     |      ",
        r"     |      ",
        r"     #      ",
    ], "@", "\\|/-()", STEEL, (255, 220, 100)),
    "axe": ([
        r"   ___      ",
        r"  /   \|    ",
        r" | @   |=   ",
        r"  \___/|    ",
        r"       |    ",
        r"       #    ",
    ], "@", "/\\_|", STEEL, (220, 60, 60)),
    "hammer": ([
        r" ________   ",
        r" |  @   |   ",
        r" |______|   ",
        r"    ||      ",
        r"    ||      ",
        r"    ##      ",
    ], "@", "_|", STEEL, (240, 120, 40)),
    "spear": ([
        r"     /\     ",
        r"     \/     ",
        r"    -@@-    ",
        r"     ||     ",
        r"     ||     ",
        r"     ||     ",
    ], "@", "/\\|", STEEL, (90, 170, 240)),
    "tome": ([
        r"  ________  ",
        r" /  ~@~  /| ",
        r"/_______/ | ",
        r"| ~~~~~ | / ",
        r"|_______|/  ",
        r"            ",
    ], "@~", "/_|", LEATHER, (200, 120, 255)),
    "shield": ([
        r"  ._____.   ",
        r"  |  @  |   ",
        r"  | -+- |   ",
        r"   \ + /    ",
        r"    \_/     ",
        r"            ",
    ], "@", "+-", STEEL, (230, 60, 60)),
    "helm": ([
        r"   _____    ",
        r"  /     \   ",
        r" |  ___  |  ",
        r" | |_@_| |  ",
        r"  \_____/   ",
        r"            ",
    ], "@", "_", STEEL, (90, 170, 240)),
    "hood": ([
        r"    __      ",
        r"   /  \     ",
        r"  / /\ \    ",
        r" | | @| |   ",
        r" |_|__|_|   ",
        r"            ",
    ], "@", "/\\", CLOTH, (240, 220, 120)),
    "hat": ([
        r"     /\     ",
        r"    /* \    ",
        r"   / @  \   ",
        r"  /______\  ",
        r" (________) ",
        r"            ",
    ], "*@", "_", CLOTH, (255, 230, 120)),
    "crown": ([
        r"            ",
        r" .  .@.  .  ",
        r" |\/   \/|  ",
        r" |  @ @  |  ",
        r" |_______|  ",
        r"            ",
    ], "@", "_", GOLDC, (200, 80, 230)),
    "armor": ([
        r"  __    __  ",
        r" /  \__/  \ ",
        r"|   |@@|   |",
        r" \_ |  | _/ ",
        r"   |____|   ",
        r"            ",
    ], "@", "_", STEEL, (230, 60, 60)),
    "robe": ([
        r"   _/\_     ",
        r"  /  @ \    ",
        r" /  /\  \   ",
        r" | /  \ |   ",
        r" |/    \|   ",
        r" /______\   ",
    ], "@", "/\\", CLOTH, (120, 180, 255)),
    "cloak": ([
        r"    _@_     ",
        r"   /   \    ",
        r"  / ~~~ \   ",
        r" /  ~~~  \  ",
        r"/_________\ ",
        r"            ",
    ], "@", "~", CLOTH, (240, 200, 60)),
    "ring": ([
        r"            ",
        r"    _@_     ",
        r"  .' @ '.   ",
        r"  |     |   ",
        r"  '.___.'   ",
        r"            ",
    ], "@", "", GOLDC, (230, 60, 80)),
    "amulet": ([
        r"  \     /   ",
        r"   \   /    ",
        r"    \_/     ",
        r"   /   \    ",
        r"  |  @  |   ",
        r"   \___/    ",
    ], "@", "\\/", GOLDC, (90, 200, 120)),
    "charm": ([
        r"  \     /   ",
        r"   \___/    ",
        r"    (@)     ",
        r"   /'''\    ",
        r"  ( ''' )   ",
        r"   '---'    ",
    ], "@", "'", FUR, (240, 200, 60)),
    "hourglass": ([
        r"  ._____.   ",
        r"   \~~~/    ",
        r"    \@/     ",
        r"    /.\     ",
        r"   /~~~\    ",
        r"  '-----'   ",
    ], "@~.", "\\/", GLASS, (240, 210, 120)),
    "potion": ([
        r"    _|_     ",
        r"    |=|     ",
        r"   /   \    ",
        r"  |~~~~~|   ",
        r"  |@@@@@|   ",
        r"   \___/    ",
    ], "~@", "=", GLASS, RED_LIQ),
    "potion_small": ([
        r"            ",
        r"    _|_     ",
        r"    | |     ",
        r"   /~~~\    ",
        r"  |@@@@@|   ",
        r"   \___/    ",
    ], "~@", "", GLASS, GREEN_LIQ),
    "elixir": ([
        r"    .^.     ",
        r"    |=|     ",
        r"   .' '.    ",
        r"  ( ~@~ )   ",
        r"  (@@@@@)   ",
        r"   \___/    ",
    ], "~@", "=", GLASS, PURP_LIQ),
    "god": ([
        r"   \ | /    ",
        r"    _|_     ",
        r"   / * \    ",
        r"  | @@@ |   ",
        r"  |@@@@@|   ",
        r"   \___/    ",
    ], "@*", "", GLASS, GOLD_LIQ),
    "holy_water": ([
        r"    _+_     ",
        r"    | |     ",
        r"   / + \    ",
        r"  |~~@~~|   ",
        r"  |@@@@@|   ",
        r"   \___/    ",
    ], "~@+", "", GLASS, (150, 220, 255)),
    "bomb": ([
        r"      ,*    ",
        r"     /      ",
        r"   .-#-.    ",
        r"  / @   \   ",
        r"  \     /   ",
        r"   '---'    ",
    ], "*@", "/,", (90, 90, 95), (255, 140, 40)),
    "smoke": ([
        r"  ( ~ ) ~   ",
        r" ~ ( ~ )    ",
        r"   .-#-.    ",
        r"  / ~@~ \   ",
        r"  \     /   ",
        r"   '---'    ",
    ], "~@", "()", (90, 90, 95), (170, 170, 190)),
    "scroll": ([
        r"  _______   ",
        r" (_)     )  ",
        r"   | ~@~ |  ",
        r"   | ~~~ |  ",
        r"  (_)____)  ",
        r"            ",
    ], "~@", "|", PAPER, (240, 120, 60)),
    "food": ([
        r"            ",
        r"   .----.   ",
        r"  / @  @ \  ",
        r" (________) ",
        r"   '----'   ",
        r"            ",
    ], "@", "", (205, 150, 90), (120, 70, 40)),
    "tea": ([
        r"    ) )     ",
        r"   ( (      ",
        r"  ._____.   ",
        r"  |~~@~~|_  ",
        r"  |     |_) ",
        r"  '-----'   ",
    ], "~@)(", "", (220, 210, 190), (120, 200, 120)),
    "mead": ([
        r"   _____    ",
        r"  (~~~~~)   ",
        r"  |  @  |\  ",
        r"  |     | ) ",
        r"  |_____|/  ",
        r"            ",
    ], "~@", "", WOOD, (240, 190, 70)),
    "brew": ([
        r"  )  (  )   ",
        r"   ~@~@~    ",
        r" (^-----^)  ",
        r"  |     |   ",
        r"   \___/    ",
        r"   /   \    ",
    ], "~@)(", "^", (70, 60, 70), (230, 60, 40)),
    "bandage": ([
        r"   _____    ",
        r"  /    /|   ",
        r" /_+__/ |   ",
        r" |    | /   ",
        r" |____|/    ",
        r"            ",
    ], "+", "", (235, 230, 215), (220, 50, 60)),
    "herb": ([
        r"    \@/     ",
        r"   \@|@/    ",
        r"    \|/     ",
        r"     |      ",
        r"    ~~~     ",
        r"            ",
    ], "@", "\\|/", (90, 170, 80), (200, 230, 200)),
    "gem": ([
        r"   ____     ",
        r"  /\__/\    ",
        r"  \@\/@/    ",
        r"   \@@/     ",
        r"    \/      ",
        r"            ",
    ], "@", "_", GLASS, (120, 200, 255)),
    "ore": ([
        r"    __      ",
        r"  _/  \_    ",
        r" / @  . \   ",
        r" \  .  @/   ",
        r"  \____/    ",
        r"            ",
    ], "@.", "", STONE, (200, 110, 70)),
    "ingot": ([
        r"            ",
        r"   ______   ",
        r"  /@@@@@/\  ",
        r" /_____/ /  ",
        r" \_____\/   ",
        r"            ",
    ], "@", "", STEEL, (220, 225, 235)),
    "pelt": ([
        r"  /\    /\  ",
        r" (  ~~~~  ) ",
        r"  \ ~@@~ /  ",
        r"  / ~~~~ \  ",
        r" (_/\  /\_) ",
        r"            ",
    ], "~@", "", FUR, (120, 110, 100)),
    "bone": ([
        r"    _  _    ",
        r"   ( \/ )   ",
        r"    \  /    ",
        r"    |@@|    ",
        r"    /  \    ",
        r"   (_/\_)   ",
    ], "@", "", BONE, (200, 190, 160)),
    "fang": ([
        r"   ______   ",
        r"   \    /   ",
        r"    \@ /    ",
        r"     \/     ",
        r"     @      ",
        r"            ",
    ], "@", "", BONE, (110, 220, 90)),
    "feather": ([
        r"        ,   ",
        r"      ,/@   ",
        r"    ,/@/    ",
        r"   /@/      ",
        r"  //        ",
        r" /          ",
    ], "@", "", (220, 220, 220), (240, 120, 60)),
    "scale": ([
        r"   _____    ",
        r"  / ^ ^ \   ",
        r" | ^ @ ^ |  ",
        r"  \ ^ ^ /   ",
        r"   \___/    ",
        r"            ",
    ], "@^", "", (120, 160, 120), (230, 90, 50)),
    "cloth": ([
        r"  ________  ",
        r" /~~~~~~~/  ",
        r"/~~~@~~~/   ",
        r"~~~~~~~/    ",
        r"            ",
        r"            ",
    ], "@~", "", CLOTH, (160, 110, 220)),
    "wood": ([
        r"            ",
        r"   _______  ",
        r"  (@)_____) ",
        r"  (@)_____) ",
        r"            ",
        r"            ",
    ], "@", "_)", WOOD, (200, 160, 100)),
    "key": ([
        r"   .--.     ",
        r"  ( @  )    ",
        r"   '--'\    ",
        r"        \   ",
        r"       =\=  ",
        r"        =\  ",
    ], "@", "\\=", GOLDC, (240, 220, 140)),
    "ring_key": ([
        r"            ",
        r"   _[@]_    ",
        r"  .'   '.   ",
        r"  |     |   ",
        r"  '.___.'   ",
        r"            ",
    ], "@", "[]", GOLDC, (180, 90, 230)),
    "rune": ([
        r"   _____    ",
        r"  /     \   ",
        r" |  |@/  |  ",
        r" |  |\   |  ",
        r"  \_____/   ",
        r"            ",
    ], "@|/\\", "", STONE, (120, 200, 255)),
    "relic": ([
        r"    _+_     ",
        r"   ( @ )    ",
        r"   |   |    ",
        r"   | + |    ",
        r"   |___|    ",
        r"            ",
    ], "@+", "", GOLDC, (255, 230, 150)),
    "coin": ([
        r"   .---.    ",
        r"  / @@@ \   ",
        r" | @ $ @ |  ",
        r"  \ @@@ /   ",
        r"   '---'    ",
        r"            ",
    ], "@$", "", GOLDC, (240, 200, 70)),
    "ember": ([
        r"    (       ",
        r"   ) (      ",
        r"  ( @ )     ",
        r"   \@/      ",
        r"  '---'     ",
        r"            ",
    ], "@()", "", STONE, (255, 120, 40)),
    "dust": ([
        r"  .  * .    ",
        r" * .@ . *   ",
        r"  . * . .   ",
        r"   (___)    ",
        r"            ",
        r"            ",
    ], "*@.", "", CLOTH, (240, 220, 140)),
    "shell": ([
        r"            ",
        r"    ___     ",
        r"  /|||\     ",
        r" /|||||\    ",
        r" \_|@|_/    ",
        r"            ",
    ], "@", "|", (235, 200, 180), (240, 170, 190)),
    "pearl": ([
        r"            ",
        r"    ___     ",
        r"   / @ \    ",
        r"   \___/    ",
        r"            ",
        r"            ",
    ], "@", "", (230, 230, 240), (250, 250, 255)),
    "coral": ([
        r"  \| |/ |   ",
        r"   \|/\/    ",
        r"    \ /     ",
        r"    |@|     ",
        r"   ~~~~~    ",
        r"            ",
    ], "@", "~", (240, 110, 100), (255, 180, 170)),
    "ink": ([
        r"    _|_     ",
        r"   (   )    ",
        r"  ( @@@ )   ",
        r"   (___)    ",
        r"            ",
        r"            ",
    ], "@", "|", GLASS, (60, 50, 90)),
    "horn": ([
        r"  __        ",
        r" (  \__     ",
        r"  \    \_   ",
        r"   \_   @\  ",
        r"     \____) ",
        r"            ",
    ], "@", "", (90, 70, 70), (230, 60, 40)),
    "misc": ([
        r"            ",
        r"   _____    ",
        r"  |  @  |   ",
        r"  |_____|   ",
        r"            ",
        r"            ",
    ], "@", "", CLOTH, (200, 200, 200)),
}

# Liquid colour for icon keys that share the potion art
_ICON_ALIAS = {
    "potion_red": ("potion", RED_LIQ),
    "potion_blue": ("potion", BLUE_LIQ),
    "potion_purple": ("potion", PURP_LIQ),
    "potion_green": ("potion", GREEN_LIQ),
    "helmet": ("helm", None),
}


def _kw(name, words):
    return any(w in name for w in words)


def icon_key(item):
    """Icon key for an item, Item, Equipment or ItemStack."""
    it = item.item if isinstance(item, ItemStack) else item
    explicit = getattr(it, "icon", None) or _info(getattr(it, "base", None) or it.name).get("icon")
    if explicit and (explicit in ICONS or explicit in _ICON_ALIAS):
        return explicit
    name = (getattr(it, "base", None) or it.name).lower()
    if isinstance(it, Equipment):
        s = it.slot
        if s == "weapon":
            if _kw(name, ("greatsword", "claymore", "cleaver", "executioner")): return "greatsword"
            if _kw(name, ("dagger", "dirk", "stiletto", "knife", "kris", "fang blade", "twin fang")): return "dagger"
            if _kw(name, ("bow", "recurve")): return "bow"
            if _kw(name, ("wand", "rod")): return "wand"
            if _kw(name, ("staff",)): return "staff"
            if _kw(name, ("mace", "sceptre", "morning star", "club")): return "mace"
            if _kw(name, ("hammer", "maul", "anvil")): return "hammer"
            if _kw(name, ("spear", "trident", "halberd", "lance", "tidebreaker")): return "spear"
            if _kw(name, ("axe",)): return "axe"
            if _kw(name, ("tome", "book", "grimoire", "codex")): return "tome"
            if _kw(name, ("scimitar", "cutlass", "sabre")): return "scimitar"
            return "sword"
        if s == "armor":
            return "robe" if _kw(name, ("robe", "vestment", "habit", "silks", "wraps")) else "armor"
        if s == "helmet":
            if _kw(name, ("hood", "turban", "wrap")): return "hood"
            if _kw(name, ("hat",)): return "hat"
            if _kw(name, ("crown", "circlet", "tiara")): return "crown"
            return "helm"
        if s == "shield": return "shield"
        if s == "cloak": return "cloak"
        if s == "ring": return "ring"
        if s == "amulet":
            return "hourglass" if "glass" in name else "amulet"
        return "misc"
    t = it.item_type
    if t == "heal":
        if CONSUMABLE_FX.get(it.name, {}).get("mp"):
            return "potion_purple"
        return "potion_red"
    if t == "mana":     return "potion_blue"
    if t == "god":      return "god"
    if t == "antidote": return "potion_small"
    if t == "bomb":     return "bomb"
    if t == "buff":     return "potion_red"
    if t == "key":      return "key"
    if t == "material":
        for words, key in ((("ore", "nugget", "coal", "granite", "brimstone"), "ore"),
                           (("pelt", "hide", "fur"), "pelt"),
                           (("bone", "ivory"), "bone"),
                           (("fang",), "fang"), (("feather",), "feather"),
                           (("scale", "chitin"), "scale"),
                           (("cloth", "silk", "linen", "twine", "strip"), "cloth"),
                           (("crystal", "shard", "stone", "glass", "ruby", "sapphire",
                             "emerald", "topaz", "amber"), "gem"),
                           (("herb", "leaf"), "herb")):
            if _kw(name, words):
                return key
        return "ore"
    return "misc"


def _resolve(key):
    """(art, accent chars, body chars, body rgb, accent rgb) for a key."""
    liquid = None
    if key in _ICON_ALIAS:
        key, liquid = _ICON_ALIAS[key]
    art, acc, body, body_rgb, acc_rgb = ICONS.get(key, ICONS["misc"])
    if liquid:
        acc_rgb = liquid
    return art, acc, body, body_rgb, acc_rgb


def _item_element(it):
    el = getattr(it, "element", None)
    if el:
        return el
    return _info(it.name).get("element")


def item_icon(item, rarity=None):
    """Coloured icon lines (each exactly ICON_W visible columns)."""
    it = item.item if isinstance(item, ItemStack) else item
    art, acc, body, body_rgb, acc_rgb = _resolve(icon_key(it))
    frame_col = rarity_colour(rarity or getattr(it, "rarity", "common"))
    el = _item_element(it)
    acc_col = element_colour(el) if el else _fg(*acc_rgb)
    body_col = _fg(*body_rgb)
    out = []
    for line in art:
        line = (line + " " * ICON_W)[:ICON_W]
        buf, cur = [], None
        for ch in line:
            if ch == " ":
                col = None
            elif ch in acc:
                col = acc_col
            elif ch in body:
                col = body_col
            else:
                col = frame_col
            if col != cur:
                buf.append(R_ if col is None else col)
                cur = col
            buf.append(ch)
        buf.append(R_)
        out.append("".join(buf))
    return out


def icon_plain(item):
    """Uncoloured icon lines (for tests and logs)."""
    it = item.item if isinstance(item, ItemStack) else item
    art = _resolve(icon_key(it))[0]
    return [(l + " " * ICON_W)[:ICON_W] for l in art]


# ═══════════════════════════════════════════════════════════════
# INSPECT CARD
# ═══════════════════════════════════════════════════════════════

_TYPE_LABEL = {"heal": "Healing", "mana": "Mana", "god": "Divine", "antidote": "Remedy",
               "bomb": "Battle item", "buff": "Tonic", "material": "Material", "key": "Key item"}


def _wrap(text, width):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        lines.append(cur)
    return lines


def _signed(v, suffix=""):
    return f"{v:+d}{suffix}"


def _compare_rows(it, player):
    """[(label, value, delta or None)] comparing to the equipped item."""
    eq = None
    if player is not None and isinstance(it, Equipment):
        cur = getattr(player, "equipped", {}).get(it.slot)
        if cur is not None and cur is not it:
            eq = cur
    mine = dict(it.stat_pairs())
    theirs = dict(eq.stat_pairs()) if eq is not None else {}
    order = ["HP", "ATK", "MP", "DEF", "STL", "CRIT", "POT", "GOLD"]
    rows = []
    for k in order:
        a, b = mine.get(k, 0), theirs.get(k, 0)
        if not a and not b:
            continue
        rows.append((k, a, (a - b) if eq is not None else None))
    return rows, eq


def render_card(item, player=None, width=None):
    """Lines of the inspect card (icon box left, details right)."""
    qty = item.qty if isinstance(item, ItemStack) else 1
    it = item.item if isinstance(item, ItemStack) else item
    rar = getattr(it, "rarity", "common")
    rcol = rarity_colour(rar)
    total_w = min(width or W(), 118)
    text_w = max(30, total_w - 20)

    # Left: icon in a rarity-coloured frame
    icon = item_icon(it)
    left = [f"{rcol}┌{'─' * ICON_W}┐{R_}"]
    left += [f"{rcol}│{R_}{ln}{rcol}│{R_}" for ln in icon]
    left.append(f"{rcol}└{'─' * ICON_W}┘{R_}")
    glyph_hint = f" {C_DIM}{item_category(it)}{R_}"
    left.append(glyph_hint + " " * max(0, ICON_W + 2 - _vis(glyph_hint)))

    # Right: details
    r = []
    title = it.name + (f"  x{qty}" if qty > 1 else "")
    r.append(f"{rcol}{B_}{title}{R_}")
    if isinstance(it, Equipment):
        kind = f"{RARITY_LABEL.get(rar, rar)} {it.slot}"
        if it.item_level:
            kind += f"  ·  item level {it.item_level}"
    else:
        kind = f"{RARITY_LABEL.get(rar, rar)} {_TYPE_LABEL.get(it.item_type, it.item_type)}"
    el = _item_element(it)
    if el:
        kind += f"  ·  {element_colour(el)}{el}{R_}"
    r.append(f"{C_DIM}{kind}{R_}")
    r.append("")

    if isinstance(it, Equipment):
        rows, eq = _compare_rows(it, player)
        if not rows:
            r.append(f"{C_DIM}No stat bonuses.{R_}")
        for k, v, d in rows:
            suf = "%" if k == "CRIT" else ""
            vcol = C_WHITE if v >= 0 else C_RED
            line = f"{C_CYAN}{k:<5}{R_}{vcol}{_signed(v, suf):>6}{R_}"
            if d is not None and d != 0:
                dcol = C_GREEN if d > 0 else C_RED
                line += f"   {dcol}{_signed(d, suf)}{R_}"
            elif d == 0:
                line += f"   {C_DIM}={R_}"
            r.append(line)
        if player is not None:
            cur = getattr(player, "equipped", {}).get(it.slot)
            if cur is it:
                r.append(f"{C_GREEN}Currently equipped.{R_}")
            elif eq is not None:
                r.append(f"{C_DIM}Compared with your {eq.name}.{R_}")
            else:
                r.append(f"{C_DIM}Nothing equipped in the {it.slot} slot.{R_}")
        if it.affixes:
            r.append("")
            r.append(f"{C_GOLD}Affixes{R_}")
            for a in it.affixes:
                st = affix_stats(a)
                stxt = ", ".join(f"{k.upper()}{v:+d}" for k, v in st.items())
                ael = AFFIXES.get(a.get("id"), {}).get("element")
                ecol = element_colour(ael) if ael else C_WHITE
                r.append(f"  {ecol}{affix_name(a)}{R_} {C_DIM}(tier {a.get('tier', 1)}: {stxt}){R_}")
        if it.power:
            r.append("")
            for i, ln in enumerate(_wrap(it.power, text_w - 7)):
                r.append((f"{C_GOLD}Power:{R_} " if i == 0 else "       ") + f"{_fg(255,180,80)}{ln}{R_}")
        if it.set_name:
            have = 0
            if player is not None:
                have = sum(1 for e in getattr(player, "equipped", {}).values()
                           if e is not None and getattr(e, "set_name", None) == it.set_name)
            r.append(f"{_fg(185,95,245)}Set: {it.set_name}{R_}" +
                     (f" {C_DIM}({have} piece{'s' if have != 1 else ''} worn){R_}" if player is not None else ""))
        ac = it.allowed_classes
        if ac:
            ok = player is None or player.job.name in ac
            col = C_DIM if ok else C_RED
            r.append(f"{col}Classes: {', '.join(ac)}{R_}")
    else:
        r.append(f"{C_GREEN}{describe_effect(it)}{R_}")

    desc = getattr(it, "description", "") or _info(it.name).get("desc", "")
    if desc:
        r.append("")
        for ln in _wrap(desc, text_w):
            r.append(f"{_fg(200,190,170)}{ln}{R_}")
    r.append("")
    if it.item_type == "key":
        r.append(f"{C_DIM}Key item — cannot be sold.{R_}")
    else:
        sv = it.sell_value
        r.append(f"{C_GOLD}Sells for {sv}g{R_}" + (f" {C_DIM}(x{qty} = {sv*qty}g){R_}" if qty > 1 else ""))

    # Merge columns
    n = max(len(left), len(r))
    lines = []
    for i in range(n):
        lt = left[i] if i < len(left) else " " * (ICON_W + 2)
        rt = r[i] if i < len(r) else ""
        lines.append(f"{lt}   {rt}")
    return lines


def inspect_item(item, player=None, actions=""):
    """Show the inspect card full-screen. `actions` is an extra hint line
    such as "[E] Equip". Returns the key the player typed (lowercase)."""
    clr()
    print()
    print(C(f"{C_GOLD}{B_}══  INSPECT  ══{R_}"))
    print()
    for ln in render_card(item, player):
        print(C("  " + ln))
    print()
    hint = (actions + "   " if actions else "") + f"{C_GOLD}[Enter]{R_}{C_DIM} Back{R_}"
    try:
        return input(C(f"{hint}  {C_GOLD}>{R_} ")).strip().lower()
    except EOFError:
        return ""


def parse_inspect(cmd, count=None):
    """'?3', 'x3', 'i3', 'l3' or 'x 3' -> 3 (1-based); None if not an inspect."""
    s = (cmd or "").strip().lower().replace(" ", "")
    if len(s) >= 2 and s[0] in "?xil" and s[1:].isdigit():
        n = int(s[1:])
        if n >= 1 and (count is None or n <= count):
            return n
    return None


def ask_inspect(entries, player=None, prompt_text="Inspect which #"):
    """Prompt for a number and inspect that entry. Returns the inspect key."""
    try:
        ch = input(C(f"{C_GOLD}{prompt_text} (0 = cancel) >{R_} ")).strip()
    except EOFError:
        return ""
    if ch.isdigit() and 1 <= int(ch) <= len(entries):
        return inspect_item(entries[int(ch) - 1], player)
    return ""
