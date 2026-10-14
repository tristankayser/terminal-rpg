"""
game_art.py — Colour ASCII sprites for Terminal-RPG.

Every sprite is drawn character by character in 24-bit colour:
  • art    — the picture (single-width characters only)
  • base   — default colour letter for the whole sprite
  • rows   — optional {row_index: colour letter} overrides
  • chars  — optional {character: colour letter} overrides
  • masks  — optional per-character colour masks (same shape as art)
The colour letter "A" is the ACCENT: on hero sprites it is the outfit colour
chosen in the Customise menu, so your character really changes look.

Usage:
    from game_art import print_sprite, side_by_side, player_look
    print_sprite("Wolf")
    acc, legendary = player_look(player)
    print_sprite(player.job.name, accent=acc, legendary=legendary)
"""

from __future__ import annotations

from game_term import C, W

_R = "\033[0m"
_B = "\033[1m"
def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"

# ── Palette ─────────────────────────────────────────────────────
PAL = {
    "R": (225, 60, 60),   "r": (150, 35, 40),   "O": (235, 140, 45),
    "Y": (250, 220, 80),  "L": (255, 205, 40),  "G": (95, 205, 95),
    "g": (55, 135, 60),   "B": (85, 135, 235),  "b": (55, 75, 160),
    "C": (100, 225, 235), "c": (185, 225, 255), "P": (185, 95, 235),
    "p": (110, 60, 150),  "M": (235, 95, 175),  "W": (240, 240, 240),
    "w": (165, 165, 175), "S": (195, 200, 215), "D": (95, 95, 110),
    "N": (160, 105, 60),  "n": (105, 70, 45),   "K": (240, 200, 160),
    "E": (255, 70, 70),
}
_GOLD = _fg(255, 215, 0)
_DIM  = _fg(100, 100, 100)

# Default outfit colour per class (used until a style is picked)
CLASS_ACCENT = {
    "Swordsman": (80, 130, 230),  "Mage": (150, 80, 220),  "Rogue": (90, 90, 120),
    "Tank": (150, 155, 170),      "Healer": (90, 200, 120),
    "Blade Master": (60, 110, 230), "Archmage": (120, 60, 210),
    "Shadow Assassin": (110, 50, 160), "War Titan": (170, 60, 50),
    "Arch Priest": (240, 220, 140),
}

PLAYER_CLASSES = set(CLASS_ACCENT)


# ═══════════════════════════════════════════════════════════════
# HERO SPRITES (full colour masks)
# ═══════════════════════════════════════════════════════════════

SPRITES = {}

SPRITES["Swordsman"] = dict(base="A", art=[
    r"      ___          ",
    r"     /___\    /|   ",
    r"     |o o|   / /   ",
    r"     \_-_/  / /    ",
    r"   __/▓▓▓\_/ /     ",
    r"  /_ |▓▓▓| /_/     ",
    r"     |_|_|  |      ",
    r"     /_/\_\        ",
], masks=[
    r"      SSS          ",
    r"     SSSSS    WW   ",
    r"     SW WS   W W   ",
    r"     KKKKK  W W    ",
    r"   AAAAAAANW W     ",
    r"  KK AAAAA NNN     ",
    r"     nnnnn  N      ",
    r"     nnnnnn        ",
])

SPRITES["Mage"] = dict(base="A", art=[
    r"        /\    *    ",
    r"       /  \  (O)   ",
    r"      /_**_\  |    ",
    r"       (o o)  |    ",
    r"     __/ v \__|    ",
    r"    /  \===/  |    ",
    r"   /___/   \__|    ",
    r"      /_____\      ",
], masks=[
    r"        PP    Y    ",
    r"       P  P  CCC   ",
    r"      PPYYPP  N    ",
    r"       KW WK  N    ",
    r"     AAA K AAAN    ",
    r"    A  ALLLA  N    ",
    r"   AAAAA   AAAN    ",
    r"      AAAAAAA      ",
])

SPRITES["Rogue"] = dict(base="A", art=[
    r"      _____        ",
    r"     /     \       ",
    r"    /  >.<  \      ",
    r"    \__===__/      ",
    r"  /\ /|▓▓▓|\ /\    ",
    r" /_/ \|▓▓▓|/ \_\   ",
    r"      |_|_|        ",
    r"      /_/\_\       ",
], masks=[
    r"      DDDDD        ",
    r"     D     D       ",
    r"    D  EKE  D      ",
    r"    DDDRRRDDD      ",
    r"  WW AAAAAAA WW    ",
    r" WWW AAAAAAA WWW   ",
    r"      nnnnn        ",
    r"      nnnnnn       ",
])

SPRITES["Tank"] = dict(base="A", art=[
    r"      _____        ",
    r"     |#####|       ",
    r"     |[o o]|       ",
    r"  ___|_____|___    ",
    r" [##]|▓▓▓▓▓|==|    ",
    r" [##]|▓▓▓▓▓|  |    ",
    r" [##]|__|__|       ",
    r"     |_| |_|       ",
], masks=[
    r"      SSSSS        ",
    r"     SSSSSSS       ",
    r"     SSE ESS       ",
    r"  SSSSSSSSSSSSS    ",
    r" LAALSAAAAASWWS    ",
    r" LAALSAAAAAS  W    ",
    r" LAALnnnnnnn       ",
    r"     nnn nnn       ",
])

SPRITES["Healer"] = dict(base="W", art=[
    r"       ___    \|/  ",
    r"      (o o)   -O-  ",
    r"       \-/    /|\  ",
    r"     __|+|__   |   ",
    r"    /  |+|  \__|   ",
    r"   /___|_|___\ |   ",
    r"      /   \    |   ",
    r"     /_____\       ",
], masks=[
    r"       YYY    YYY  ",
    r"      KW WK   YWY  ",
    r"       KKK    YNY  ",
    r"     WWWRWWW   N   ",
    r"    WW WRW  WWWN   ",
    r"   WWWWAAAWWWW N   ",
    r"      WW WW    N   ",
    r"     AAAAAAA       ",
])

SPRITES["Blade Master"] = dict(base="A", art=[
    r" \\     ___     // ",
    r"  \\   /___\   //  ",
    r"   \\  |o o|  //   ",
    r"    \\_\_-_/_//    ",
    r"     /|▓▓▓▓▓|\     ",
    r"    /_|▓▓*▓▓|_\    ",
    r"   /   |_|_|   \   ",
    r"  /___ /_/\_\ ___\ ",
], masks=[
    r" WW     LLL     WW ",
    r"  WW   LLLLL   WW  ",
    r"   WW  LW WL  WW   ",
    r"    WWKKKKKKKWW    ",
    r"     AAAAAAAAA     ",
    r"    AAAAAALAAAA    ",
    r"   R   nnnnn   R   ",
    r"  RRRR nnnnnn RRRR ",
])

SPRITES["Archmage"] = dict(base="A", art=[
    r"  *    /\    *  *  ",
    r"      /**\  (@)    ",
    r"  *  /*  *\  |   * ",
    r"    /______\ |     ",
    r"     (o o)   |     ",
    r"   __/ v \___|     ",
    r"  /  \=*=/   \     ",
    r" /____/   \___\    ",
], masks=[
    r"  Y    PP    Y  C  ",
    r"      PLLP  CMC    ",
    r"  C  PL  LP  L   Y ",
    r"    PPPPPPPP L     ",
    r"     KW WK   L     ",
    r"   AAA K AAAAL     ",
    r"  A  ALLLA   A     ",
    r" AAAAAA   AAAAA    ",
])

SPRITES["Shadow Assassin"] = dict(base="A", art=[
    r"   . _______ .     ",
    r"  : /       \ :    ",
    r"  :/  >   <  \:    ",
    r"   \___===___/     ",
    r" /\ /|▓▓▓▓▓|\ /\   ",
    r"/_/\ |▓▓▓▓▓| /\_\  ",
    r"  :   |_|_|   :    ",
    r"   . /_/ \_\ .     ",
], masks=[
    r"   P DDDDDDD P     ",
    r"  P D       D P    ",
    r"  PD  E   E  DP    ",
    r"   DDDDRRRDDDD     ",
    r" WW AAAAAAAAA WW   ",
    r"WWWW AAAAAAA WWWW  ",
    r"  P   DDDDD   P    ",
    r"   P DDD DDD P     ",
])

SPRITES["War Titan"] = dict(base="A", art=[
    r"   /\ _______ /\   ",
    r"  /  |#######|  \  ",
    r"     |[o   o]|     ",
    r" ____|_______|____ ",
    r"[###]|▓▓▓▓▓▓▓|=[]= ",
    r"[###]|▓▓▓▓▓▓▓| ||  ",
    r"[###]|___|___|     ",
    r"     |__| |__|     ",
], masks=[
    r"   RR SSSSSSS RR   ",
    r"  RR SSSSSSSSS RR  ",
    r"     SSE   ESS     ",
    r" SSSSSSSSSSSSSSSSS ",
    r"LAAALSAAAAAAASWWWW ",
    r"LAAALSAAAAAAAS WW  ",
    r"LAAALnnnnnnnnn     ",
    r"     nnnn nnnn     ",
])

SPRITES["Arch Priest"] = dict(base="W", art=[
    r"         ___         ",
    r"  .--.  (o o)  .--.  ",
    r" /    \  \-/  /    \ ",
    r"|  /\  \_|+|_/  /\  |",
    r" \/  \  /|+|\  /  \/ ",
    r"      \/_|_|_\/      ",
    r"       /     \       ",
    r"      /_______\      ",
], masks=[
    r"         LLL         ",
    r"  WWWW  KW WK  WWWW  ",
    r" WW   W  KKK  W   WW ",
    r"W  WW  WWWRWWW  WW  W",
    r" WW  W  WWRWW  W  WW ",
    r"      WWWAAAWWW      ",
    r"       W     W       ",
    r"      AAAAAAAAA      ",
])

# Crown shown above heroes wearing a legendary skin
_CROWN = (r"  .*.^.*.  ", r"  YLYLYLY  ")


# ═══════════════════════════════════════════════════════════════
# MONSTERS (base colour + character overrides)
# ═══════════════════════════════════════════════════════════════

SPRITES.update({

    "Slime": dict(base="G", chars={"o": "W", "~": "g"}, art=[
        r"      .-~~-.      ",
        r"    .'      '.    ",
        r"   /  o    o  \   ",
        r"  |     __     |  ",
        r"  |    '--'    |  ",
        r"   \__________/   ",
        r"   ~~~~~~~~~~~~   ",
    ]),

    "Goblin": dict(base="G", chars={"o": "Y", "^": "n", "▓": "N", "=": "w", "-": "g"},
                   art=[
        r"   ,          ,   ",
        r"   \\ .----. //   ",
        r"    \( o  o )/    ",
        r"     |  ^^  |     ",
        r"    __'-..-'__  = ",
        r"   /   ▓▓▓▓   \=  ",
        r"      /    \      ",
        r"     ^^    ^^     ",
    ]),

    "Wolf": dict(base="w", chars={"o": "E", "v": "D", "~": "w", "'": "W"}, art=[
        r"   /\_/\          ",
        r"  / o o \______   ",
        r" (   v   )     \~ ",
        r"  \ '-' /  ,   /  ",
        r"   |\_/|__/|__/   ",
        r"   |_| |_| |_|    ",
    ]),

    "Bandit": dict(base="N", rows={0: "n", 1: "n", 2: "R", 3: "K"},
                   chars={"o": "W", "#": "n", "▓": "r"}, art=[
        r"      _____       ",
        r"     /_____\      ",
        r"     |▓▓▓▓▓|      ",
        r"     | o o |   /| ",
        r"   __\_ - _/__/ / ",
        r"  /  |#####|  \/  ",
        r"     |_| |_|      ",
        r"     /_/ \_\      ",
    ]),

    "Harpy": dict(base="M", chars={"o": "Y", "v": "O", "▓": "P", "^": "O",
                                    "\\": "P", "/": "P"}, art=[
        r" \\\   _____   /// ",
        r"  \\\ ( o o ) ///  ",
        r"   \\\ \ v / ///   ",
        r"    \\\|▓▓▓|///    ",
        r"       |▓▓▓|       ",
        r"       /   \       ",
        r"      ^^   ^^      ",
    ]),

    "Stone Golem": dict(base="w", chars={"o": "E", "#": "D", "=": "D"}, art=[
        r"    _________     ",
        r"   [  o   o  ]    ",
        r"   [    ==   ]    ",
        r" __[_________]__  ",
        r"[  ]#########[  ] ",
        r"[__]#########[__] ",
        r"    [###][###]    ",
        r"    [___][___]    ",
    ]),

    "Sand Wyrm": dict(base="O", chars={"o": "E", "V": "W", "^": "W", "~": "Y"}, art=[
        r"       ____        ",
        r"    .-'o  o'-.     ",
        r"   /  VVVVVV  \    ",
        r"  |   ^^^^^^   |   ",
        r"   \__      __/    ",
        r"  ~~~\     /~~~~   ",
        r" ~~~~~\___/~~~~~~  ",
    ]),

    "Scorpion": dict(base="O", chars={"o": "E", ">": "R", "▓": "N"}, art=[
        r"            __     ",
        r"           /  \    ",
        r"   _ _    |  (>    ",
        r"  ( V )   |        ",
        r"   \_/____|        ",
        r"  //(o_o)\\        ",
        r" // |▓▓▓| \\       ",
        r"//  /|||\  \\      ",
    ]),

    "Dust Imp": dict(base="P", chars={">": "Y", "<": "Y", "w": "W", "~": "D", "▓": "p"},
                     art=[
        r"    /\    /\      ",
        r"   (  \__/  )     ",
        r"    \ >  < /      ",
        r"     \ ww /       ",
        r"   ~~/▓▓▓▓\~~     ",
        r"  ~ /  ||  \ ~    ",
        r"     ^^  ^^       ",
    ]),

    "Frost Wraith": dict(base="c", chars={"*": "C", "~": "B", "_": "W"}, art=[
        r"      .-'''-.      ",
        r"     /  * *  \     ",
        r"    |   ___   |    ",
        r"     \ (   ) /     ",
        r"   ~~~\     /~~~   ",
        r"    ~~ |   | ~~    ",
        r"     ~~~\ /~~~     ",
        r"        ~~~        ",
    ]),

    "Snow Beast": dict(base="W", chars={"O": "B", "v": "c", "'": "c"}, art=[
        r"     ,-''''-.      ",
        r"    / O    O \     ",
        r"   |    /\    |    ",
        r"   |  \vvvv/  |    ",
        r"  /|  ''''''  |\   ",
        r" / |          | \  ",
        r"   |___|  |___|    ",
    ]),

    "Skeleton": dict(base="W", chars={"o": "E", "=": "w", "+": "w", "|": "W"}, art=[
        r"      .---.       ",
        r"     / o o \      ",
        r"     \  ^  /      ",
        r"      |vvv|    |  ",
        r"    --=====--  |  ",
        r"   /  |===|  \-+- ",
        r"      |   |    |  ",
        r"     _|   |_      ",
    ]),

    "Cultist": dict(base="p", chars={".": "E", "=": "R", "O": "M"}, art=[
        r"       /\         ",
        r"      /  \        ",
        r"     / .. \   ,   ",
        r"    /  ''  \ (O)  ",
        r"   /_/====\_\ |   ",
        r"    |  /\  |  |   ",
        r"    | /  \ |  |   ",
        r"    |/____\|  |   ",
    ]),

    "Shadow Beast": dict(base="p", chars={">": "E", "<": "E", "v": "W", "^": "W", "~": "P"},
                         art=[
        r"   .~~~~~~~~~~.    ",
        r"  (  >      <  )   ",
        r" (   \vvvvvv/   )  ",
        r"  (   ^^^^^^   )   ",
        r"   ~(  )~~(  )~    ",
        r"    /_/    \_\     ",
    ]),

    "Armored Knight": dict(base="S", chars={"▓": "w", "#": "b", "o": "E"}, art=[
        r"     _[==]_       ",
        r"    | o||o |      ",
        r"    |==||==|      ",
        r"  __|______|__    ",
        r" |##|▓▓▓▓▓▓|##|   ",
        r" |##|▓▓▓▓▓▓|##|   ",
        r"    |__||__|      ",
        r"    [__][__]      ",
    ]),

    "Lich": dict(base="P", chars={"o": "C", "*": "C", "▓": "p", "~": "D", "v": "W"}, art=[
        r"     _/\_/\_      ",
        r"    |  ___  |     ",
        r"     \(o o)/  *   ",
        r"      \ ^ /  /|\  ",
        r"    __/vvv\__ |   ",
        r"   / /▓▓▓▓▓\ \|   ",
        r"  / /▓▓▓▓▓▓▓\ |   ",
        r"   ~~~~~~~~~~~    ",
    ]),

    "Void Stalker": dict(base="p", chars={"@": "M", ".": "P", "~": "P"}, art=[
        r"   .  .~~~~~.  .  ",
        r"     ( @   @ )    ",
        r"  .   \  ~  /   . ",
        r"    __/|||||\__   ",
        r"   /  /|||||\  \  ",
        r"  /  / ||||| \  \ ",
        r"    /  /   \  \   ",
    ]),

    "Dragon Scout": dict(base="O", chars={"o": "Y", "=": "R", "-": "R", "^": "W"}, art=[
        r"    __/\__          ",
        r"   (o    >==-       ",
        r"    \  __/  /\/\    ",
        r"  /\_\/  \_/    \   ",
        r" /  /\    /\    /   ",
        r"    ^^    ^^        ",
    ]),

    # ── BOSSES ────────────────────────────────────────────────

    "Goblin King": dict(base="G", rows={0: "L", 1: "L"},
                        chars={"o": "E", "v": "W", "▓": "r", "=": "S"}, art=[
        r"      ___/\/\/\___     ",
        r"     |__|__|__|__|     ",
        r"    ,/  o    o  \,     ",
        r"   ((   .-''-.   ))    ",
        r"    \\  \vvvv/  //     ",
        r"   __\\_'-..-'_//__    ",
        r"  /   |▓▓▓▓▓▓▓▓|   \ ==",
        r" /    |▓▓▓▓▓▓▓▓|    \  ",
        r"      |___||___|       ",
        r"      (__)  (__)       ",
    ]),

    "Dungeon Warden": dict(base="S", chars={"o": "E", "▓": "w", "#": "n", "<": "O", ">": "O"},
                           art=[
        r"      _[======]_      ",
        r"     /  [o  o]  \     ",
        r"    |   [ ## ]   |    ",
        r"  __|____________|__  ",
        r" /##|▓▓▓▓▓▓▓▓▓▓▓▓|##\ ",
        r"|###|▓▓▓▓<>▓▓▓▓▓▓|###|",
        r"|###|▓▓▓▓▓▓▓▓▓▓▓▓|###|",
        r"    |_____||_____|    ",
        r"    [_____][_____]    ",
    ]),

    "Shadow Lord": dict(base="p", chars={"@": "E", "V": "W", "▓": "P", "~": "D"}, art=[
        r"     .-~~~~~~~~~~-.     ",
        r"    /  /\      /\  \    ",
        r"   |  (  @    @  )  |   ",
        r"   |   \  ____  /   |   ",
        r"    \   \/VVVV\/   /    ",
        r"  ___\_  '----'  _/___  ",
        r" /    |▓▓▓▓▓▓▓▓▓▓|    \ ",
        r"/  /\ |▓▓▓▓▓▓▓▓▓▓| /\  \ ",
        r"   ~~ |____||____| ~~   ",
    ]),

    "Dragon": dict(base="R", chars={"o": "Y", "v": "W", "^": "W", "▓": "O", "~": "r", ">": "r"},
                   art=[
        r"       __        __        ",
        r"      /  \______/  \__     ",
        r"     / /\  o  o   /\  \    ",
        r"    / /  \  vvv  /  \  \   ",
        r"   /_/   /\_^^^_/\   \_\   ",
        r"        /  ▓▓▓▓▓  \        ",
        r"   /\  /  ▓▓▓▓▓▓▓  \  /\   ",
        r"  /  \/ /|▓▓▓▓▓▓▓|\ \/  \  ",
        r"      ~~ ^^     ^^ ~~~~~~> ",
    ]),
})

# ═══════════════════════════════════════════════════════════════
# OVERHAUL: elite enemies, boss adds and the new bosses
# ═══════════════════════════════════════════════════════════════

SPRITES.update({

    "Imp": dict(base="R", chars={">": "Y", "<": "Y", "w": "W", "▓": "r", "^": "D",
                                 ",": "O"}, art=[
        r"   ,/\      /\,   ",
        r"  // \\.--.// \\  ",
        r"  \\  ( >< )  //  ",
        r"   \\_ \ww/ _//   ",
        r"      /▓▓▓▓\   ,  ",
        r"     /_/  \_\_/   ",
        r"      ^^  ^^      ",
    ]),

    "Alley Thief": dict(base="n", chars={"-": "Y", "$": "L", "▓": "g", "†": "S"}, art=[
        r"       ____       ",
        r"     _/    \_     ",
        r"    /  -  -  \    ",
        r"    \  .__.  /    ",
        r"   __\______/__ † ",
        r"  /  |▓▓▓▓▓▓|  \| ",
        r"  \/ |▓▓$▓▓▓|  /  ",
        r"     |__||__|     ",
        r"     /_/  \_\     ",
    ]),

    "Royal Guard": dict(base="S", chars={"▓": "B", "Y": "L", "#": "L", "o": "W",
                                         "│": "N", "A": "W", "=": "K"}, art=[
        r"      _/^\_     A  ",
        r"     |_###_|   /│\ ",
        r"     | o o |    │  ",
        r"     |_===_|    │  ",
        r"   __/▓▓▓▓▓\__  │  ",
        r"  [##]▓▓Y▓▓[##]=│  ",
        r"     |▓▓▓▓▓|    │  ",
        r"     |__|__|    │  ",
        r"     [__][__]      ",
    ]),

    "Desert Assassin": dict(base="N", chars={"(": "S", ")": "S", "=": "w", "-": "E",
                                             "▓": "O", ".": "K"}, art=[
        r"       .---.      ",
        r"      /=====\     ",
        r"      | - - |     ",
        r"   (  \=====/  )  ",
        r"    \  /▓▓▓\  /   ",
        r"     \/▓▓▓▓▓\/    ",
        r"      |▓▓▓▓▓|     ",
        r"      /_/ \_\     ",
    ]),

    "Demon Knight": dict(base="D", chars={"/": "R", "\\": "R", ">": "E", "<": "E",
                                          "v": "W", "▓": "r", "#": "R", "{": "w", "}": "w"},
                         art=[
        r"   /\  _____  /\     ",
        r"  /  \/ ### \/  \    ",
        r"     | >   < |       ",
        r"     |__vvv__|   /   ",
        r"  ___/▓▓▓▓▓▓▓\__/    ",
        r" {##}|▓▓▓▓▓▓▓|{/}    ",
        r"     |▓▓▓▓▓▓▓|/      ",
        r"     |___|___|       ",
        r"     {___}{___}      ",
    ]),

    # ── New bosses ─────────────────────────────────────────────

    "Demon Lord Kharzul": dict(base="r", chars={"@": "Y", "V": "W", "~": "O", "▓": "D",
                                                "X": "E", "^": "E", "{": "w", "}": "w",
                                                "*": "Y"}, art=[
        r"  /\                   /\  ",
        r" /  \     _______     /  \ ",
        r" \   \___/ ^   ^ \___/   / ",
        r"  \      ( @   @ )      /  ",
        r"   \__    \ VVV /    __/   ",
        r"  *   \___/'---'\___/   *  ",
        r" (~~)  /|▓▓▓▓▓▓▓▓▓|\  (~~) ",
        r"  \\__/ |▓▓▓▓X▓▓▓▓| \__//  ",
        r"      ~~|▓▓▓▓▓▓▓▓▓|~~      ",
        r"        |____|____|        ",
        r"        {____}{____}       ",
    ]),

    "Hellhound Warden": dict(base="D", chars={"@": "O", "V": "W", "#": "S", "▓": "r",
                                              "~": "O", "^": "w"}, art=[
        r"   /\_/\         /\_/\    ",
        r"  / @ @ \_______/ @ @ \   ",
        r" (  ___  )#####(  ___  )  ",
        r"  \ VVV /  ###  \ VVV /   ",
        r"   \___/__/###\__\___/    ",
        r"     /  ▓▓▓▓▓▓▓▓▓  \  ~~~ ",
        r"    /  ▓▓▓▓▓▓▓▓▓▓▓  \~ ~  ",
        r"   /_/|_|       |_|\_\    ",
        r"  ^^^ ^^^       ^^^ ^^^   ",
    ]),

    "Sand Djinn Azhar": dict(base="C", rows={0: "L", 1: "L"},
                             chars={"o": "W", "=": "L", "▓": "B", "~": "Y", "*": "L",
                                    "'": "L"}, art=[
        r"         _.---._         ",
        r"        /__(*)__\        ",
        r"       |  (o o)  |   *   ",
        r"        \  \=/  /   /    ",
        r"   ~~~__/'-----'\__/     ",
        r"  ~ /   \▓▓▓▓▓▓▓/   \    ",
        r"    \___/▓▓▓▓▓▓▓\___/    ",
        r"         \▓▓▓▓▓/         ",
        r"       ~~~\▓▓▓/~~~       ",
        r"     ~~~~~~\▓/~~~~~~     ",
        r"        ~~~~~~~~~        ",
    ]),

    "Scorpion Matriarch": dict(base="O", chars={"@": "E", ">": "R", "▓": "N", "o": "Y",
                                                "W": "L", "=": "n"}, art=[
        r"                 ____       ",
        r"                /    \      ",
        r"   _       _   |    (>>     ",
        r"  ( \     / )  |            ",
        r"   \ \___/ /   |            ",
        r"    \ o o /____/            ",
        r"  __/@@@@@\__   W W W       ",
        r" / /▓▓▓▓▓▓▓\ \_/=====\      ",
        r"/ //▓▓▓▓▓▓▓\\ \=====/       ",
        r"  // //  \\ \\              ",
    ]),

    "The Hollow Regent": dict(base="D", rows={0: "L", 1: "L"},
                              chars={"*": "M", "▓": "p", "◊": "M", "~": "P", "o": "P"},
                              art=[
        r"        .^.^.^.^.        ",
        r"       [_*_*_*_*_]       ",
        r"       /  o   o  \       ",
        r"      |    ___    |      ",
        r"       \  /   \  /       ",
        r"   _____\_______/_____   ",
        r"  /  ~  |▓▓▓▓▓▓▓|  ~  \  ",
        r" /  /|  |▓▓▓◊▓▓▓|  |\  \ ",
        r"    ||  |▓▓▓▓▓▓▓|  ||    ",
        r"    ~~  /_______\  ~~    ",
    ]),

    "Archmage Veyl the Unbound": dict(base="b", chars={"*": "C", ".": "c", "@": "M",
                                                       "-": "C", "=": "w", "▓": "B",
                                                       "◊": "L", "~": "P"}, art=[
        r"     *      /\      *    ",
        r"   .     . /  \ .     .  ",
        r"          / ** \         ",
        r"   (@)   /______\   (@)  ",
        r"    \     (- -)     /    ",
        r"     \___/ \=/ \___/     ",
        r"         \|▓▓▓|/         ",
        r"     *    |▓◊▓|    *     ",
        r"         /▓▓▓▓▓\         ",
        r"      ~~/_______\~~      ",
    ]),

    "Bandit King Rourke": dict(base="N", rows={0: "n", 1: "n"},
                               chars={"~": "r", "$": "L", "▓": "r", "o": "W",
                                      "#": "S", "^": "L"}, art=[
        r"       _.-^-^-._          ",
        r"      /__________\  ___   ",
        r"      | (o)  (o) | /###\  ",
        r"      |   \__/   | \###/  ",
        r"       \ ~~~~~~ /    ||   ",
        r"    ____\~~~~~~/____ ||   ",
        r"   /   |▓▓▓$$▓▓▓|   \||   ",
        r"  /_/| |▓▓▓▓▓▓▓▓| |\_||   ",
        r"       |___||___|         ",
        r"       (___)(___)         ",
    ]),

    "Thieves' Guildmaster": dict(base="D", chars={"=": "r", "o": "Y", "▓": "p", "$": "L",
                                                  "†": "S", ".": "K"}, art=[
        r"        _______         ",
        r"       /       \        ",
        r"      /  =====  \       ",
        r"      | <o> <o> |       ",
        r"       \  ._.  /        ",
        r"  †   __\_____/__   †   ",
        r"   \ /  |▓▓▓▓▓|  \ /    ",
        r"    /  /|▓▓$▓▓|\  \     ",
        r"   /__/ |__|__| \__\    ",
        r"        /_/ \_\         ",
    ]),
})

# Re-coloured variants of existing sprites
VARIANTS = {
    "Cutthroat":       ("Alley Thief", {"g": "r", "n": "D", "Y": "E"}),
    "Sand Scorpion":   ("Scorpion", {"O": "Y", "N": "O", "E": "R"}),
    "Mirror Image":    ("Archmage Veyl the Unbound",
                        {"b": "w", "B": "c", "C": "W", "M": "c", "L": "c", "P": "w", "c": "W"}),
    "Hollow Regent Unmasked": ("The Hollow Regent",
                               {"D": "p", "p": "M", "L": "E", "M": "E", "P": "E"}),
    "Bandit Thug":     ("Bandit", {"N": "D", "R": "w", "r": "D"}),
    "Ice Wolf":       ("Wolf", {"w": "c", "E": "C", "D": "B", "W": "W"}),
    "Rock Wolf":      ("Wolf", {"w": "N", "E": "O", "D": "n"}),
    "Ice Golem":      ("Stone Golem", {"w": "c", "D": "C", "E": "B"}),
    "Dark Golem":     ("Stone Golem", {"w": "p", "D": "P", "E": "E"}),
    "Death Knight":   ("Armored Knight", {"S": "D", "w": "p", "b": "r", "E": "E"}),
    "Desert Raider":  ("Bandit", {"R": "Y", "N": "O", "r": "Y", "n": "N"}),
    "Dragon Cultist": ("Cultist", {"p": "r", "R": "O", "M": "Y"}),
    "Wyvern":         ("Dragon Scout", {"O": "g", "Y": "E", "R": "G"}),
    "Shadow Lich":    ("Lich", {"P": "M", "p": "P", "C": "E", "D": "p"}),
    "Frost Dragon":   ("Dragon", {"R": "c", "O": "C", "Y": "B", "r": "b"}),
    "Vaeltharion":    ("Dragon", {}),
}

# Item icons (status / shop screens)
SPRITES.update({
    "sword":  dict(base="S", art=[r"    /|  ", r"   / /  ", r"  / /   ", r" =/=    "]),
    "staff":  dict(base="N", chars={"*": "C"}, art=[r"  ***  ", r"   |   ", r"   |   ", r"   |   "]),
    "shield": dict(base="S", art=[r" ,---. ", r"| [ ] |", r" \   / ", r"  '-'  "]),
    "helmet": dict(base="S", art=[r" ,---, ", r"/ [ ] \ ", r"|=====|"]),
    "armor":  dict(base="S", art=[r",-----.", r"|[#][#]", r"| |=| |"]),
    "ring":   dict(base="L", art=[r" .--. ", r"( oo )", r" '--' "]),
    "potion": dict(base="G", chars={"~": "W"}, art=[r"  ,-,  ", r" (~~~) ", r"(     )", r" '---' "]),
})

_FALLBACK_ENEMY = dict(base="R", chars={"?": "Y"}, art=[
    r"   /~~~~~\   ",
    r"  ( ? ? ? )  ",
    r"   \_____/   ",
    r"   |     |   ",
])


# ═══════════════════════════════════════════════════════════════
# RENDERING
# ═══════════════════════════════════════════════════════════════

def _spec(name):
    if name in VARIANTS:
        src, remap = VARIANTS[name]
        return SPRITES[src], remap
    if name in SPRITES:
        return SPRITES[name], {}
    nl = name.lower()
    for key, words in (("sword", ("sword", "blade", "dagger", "mace", "hammer", "axe", "spear")),
                       ("staff", ("staff", "rod", "sceptre", "tome", "orb")),
                       ("shield", ("shield",)), ("helmet", ("helm", "hood", "crown")),
                       ("armor", ("armor", "mail", "robe", "vest", "suit", "plate", "cloak")),
                       ("ring", ("ring", "amulet", "pendant")),
                       ("potion", ("potion", "ether", "elixir"))):
        if any(w in nl for w in words):
            return SPRITES[key], {}
    if name in PLAYER_CLASSES:
        return SPRITES["Swordsman"], {}
    return _FALLBACK_ENEMY, {}


def _colour(letter, accent):
    if letter == "A" and accent is not None:
        return _fg(*accent)
    rgb = PAL.get(letter)
    return _fg(*rgb) if rgb else ""


def sprite_width(name):
    spec, _ = _spec(name)
    return max(len(l) for l in spec["art"])


def render_sprite(name, accent=None, legendary=False):
    """List of coloured strings, every line padded to the sprite width."""
    spec, remap = _spec(name)
    art   = spec["art"]
    masks = spec.get("masks")
    rows  = spec.get("rows", {})
    chars = spec.get("chars", {})
    base  = spec.get("base", "W")
    width = max(len(l) for l in art)
    if accent is None and name in CLASS_ACCENT:
        accent = CLASS_ACCENT[name]
    if legendary:
        accent = (255, 205, 40)

    out = []
    if legendary:
        crown, cmask = _CROWN
        art = [crown.center(width)] + list(art)
        off = (width - len(crown)) // 2
        masks = ([" " * off + cmask] + list(masks)) if masks else None
        rows = {k + 1: v for k, v in rows.items()}
        rows[0] = "L"

    for y, line in enumerate(art):
        line = line.ljust(width)
        mline = masks[y] if masks and y < len(masks) else ""
        parts, cur = [], None
        for x, ch in enumerate(line):
            if ch == " ":
                letter = None
            else:
                m = mline[x] if x < len(mline) else " "
                letter = m if m != " " else chars.get(ch, rows.get(y, base))
                letter = remap.get(letter, letter)
            col = _colour(letter, accent) if letter else None
            if col != cur and col is not None:
                parts.append(col); cur = col
            parts.append(ch)
        parts.append(_R)
        out.append("".join(parts))
    return out


def get_sprite(name):
    """Compatibility helper: [(colour, plain_line)]."""
    spec, remap = _spec(name)
    col = _colour(remap.get(spec.get("base", "W"), spec.get("base", "W")), CLASS_ACCENT.get(name))
    return [(col, l) for l in spec["art"]]


def player_look(player):
    """(accent_rgb, legendary) for the player's current style."""
    sid = getattr(player, "_custom_style_id", None) or ""
    col = getattr(player, "_custom_style_colour", None)
    accent = tuple(col) if col else CLASS_ACCENT.get(player.job.name)
    return accent, sid.startswith("lskin_")


def print_sprite(name, label="", indent=0, accent=None, legendary=False):
    """Print a sprite (left-aligned in the content area) with an optional label."""
    lines = render_sprite(name, accent, legendary)
    prefix = " " * indent
    for l in lines:
        print(C(prefix + l))
    if label:
        w = sprite_width(name)
        print(C(f"{prefix}{_GOLD}{_B}{label[:max(w, len(label))]:^{w}}{_R}"))


def side_by_side(left_name, right_name, left_label="", right_label="", gap=8,
                 left_accent=None, right_accent=None, left_legendary=False):
    """Two sprites side by side, bottoms aligned, with a ⚔ between them."""
    L = render_sprite(left_name, left_accent, left_legendary)
    R_ = render_sprite(right_name, right_accent)
    lw = sprite_width(left_name)
    rw = sprite_width(right_name)
    h = max(len(L), len(R_))
    L  = [" " * lw] * (h - len(L)) + L          # align feet on the same row
    R_ = [" " * rw] * (h - len(R_)) + R_
    mid = h // 2
    rows = []
    for i, (l, r) in enumerate(zip(L, R_)):
        sep = (f"{_fg(220,60,60)}{_B}{'VS'.center(gap)}{_R}" if i == mid else " " * gap)
        rows.append(C(l + sep + r))
    if left_label or right_label:
        LL = f"{_GOLD}{_B}{left_label[:lw]:^{lw}}{_R}"
        RL = f"{_fg(220,60,60)}{_B}{right_label[:rw]:^{rw}}{_R}"
        rows.append(C(LL + " " * gap + RL))
    return rows


def combat_layout(player_name, enemy_name, player_label="", enemy_label=""):
    return side_by_side(player_name, enemy_name,
                        player_label or player_name, enemy_label or enemy_name)


def equipped_row(equipped, max_cols=120):
    """Small icons for equipped items (kept for compatibility)."""
    from game_items import Equipment as _Eq
    items = [(sl, it) for sl, it in equipped.items() if isinstance(it, _Eq)]
    if not items:
        return [C(f"  {_DIM}No equipment worn.{_R}")]
    out = []
    for sl, it in items:
        for line in render_sprite(it.name):
            out.append(C(line))
        out.append(C(f"{_GOLD}{it.name}{_R} {_DIM}{it.stat_line()}{_R}"))
        out.append("")
    return out
