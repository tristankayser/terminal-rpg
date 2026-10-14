"""
game_dungeon.py — Multi-floor dungeon system for Terminal-RPG.

Features:
  • Several floors per dungeon (3 by default) — enemies get harder each floor
  • Rooms are always connected (every room is chained to the next by a corridor)
  • Floor transitions via staircases (▼ go down, ▲ go up)
  • Teleport pads (T) warp you back to the surface
  • The bottom floor holds the dungeon boss (B) — or, once the dungeon has been
    cleared, a treasure altar (*) that still counts as reaching the bottom
  • Deep dungeons (4+ floors) have a mini-boss guarding the last staircase
  • Fog of war: you only see the parts of the floor you have explored
  • Treasure chests and hidden traps on every floor
"""

import random, time
from game_term import C, clr, draw_frame

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60);     _CYAN=_fg(80,220,220)
_YELL=_fg(240,200,60); _ORAN=_fg(220,140,40);   _PURP=_fg(180,80,220)

DEFAULT_FLOORS = 3

# Tile legend
TILE_WALL    = "#"
TILE_FLOOR   = "."
TILE_ENTRY   = "E"   # entrance / exit to surface (floor 1)
TILE_STAIRS_D= "▼"   # go deeper
TILE_STAIRS_U= "▲"   # go back up
TILE_TELEPORT= "T"   # teleport to surface
TILE_CHEST   = "C"   # treasure chest
TILE_TRAP    = "!"   # damage trap (hidden until triggered)
TILE_BOSS    = "B"   # dungeon boss
TILE_ALTAR   = "*"   # treasure altar (bottom floor of a cleared dungeon)

TILE_COLOURS = {
    TILE_WALL:    _fg(110,85,60),
    TILE_FLOOR:   _fg(70,60,50),
    TILE_ENTRY:   _fg(80,220,80),
    TILE_STAIRS_D:_fg(230,180,60),
    TILE_STAIRS_U:_fg(100,200,255),
    TILE_TELEPORT:_fg(180,80,220),
    TILE_CHEST:   _fg(255,215,0),
    TILE_TRAP:    _fg(220,60,60),
    TILE_BOSS:    _fg(255,50,50) + _B,
    TILE_ALTAR:   _fg(255,230,120) + _B,
}

# Encounter chance per step, by floor (index = floor-1, clamped)
ENCOUNTER_BASE = [0.07, 0.09, 0.11, 0.13, 0.15]
SIGHT_RADIUS   = 5


class DungeonFloor:
    W_MAP = 40
    H_MAP = 18

    def __init__(self, floor_num, dungeon_name, total_floors, boss_name=None):
        self.floor_num    = floor_num
        self.dungeon_name = dungeon_name
        self.total_floors = total_floors
        self.is_bottom    = floor_num >= total_floors
        self.boss_name    = boss_name if self.is_bottom else None
        self.grid         = [[TILE_WALL]*self.W_MAP for _ in range(self.H_MAP)]
        self.px, self.py  = 2, 2
        self.chests_opened   = set()
        self.traps_triggered = set()
        self.seen            = set()
        self.miniboss_defeated = False
        self._generate()
        self.reveal()

    # ── Generation ────────────────────────────────────────────

    def _carve_room(self):
        w = random.randint(4, 9)
        h = random.randint(3, 5)
        x = random.randint(1, self.W_MAP - w - 2)
        y = random.randint(1, self.H_MAP - h - 2)
        return (x, y, w, h)

    def _generate(self):
        rooms = []
        attempts = 0
        target = random.randint(6, 9)
        while len(rooms) < target and attempts < 200:
            attempts += 1
            r = self._carve_room()
            # Prefer rooms that don't overlap, but accept overlaps after many tries
            if attempts < 150 and any(self._overlap(r, o) for o in rooms):
                continue
            rooms.append(r)
        for (x, y, w, h) in rooms:
            for ry in range(y, y+h):
                for rx in range(x, x+w):
                    self.grid[ry][rx] = TILE_FLOOR

        # Chain every room to the next → the whole floor is connected
        rooms.sort(key=lambda r: r[0])
        for a, b in zip(rooms, rooms[1:]):
            ax, ay = a[0] + a[2]//2, a[1] + a[3]//2
            bx, by = b[0] + b[2]//2, b[1] + b[3]//2
            for x in range(min(ax, bx), max(ax, bx)+1):
                self.grid[ay][x] = TILE_FLOOR
            for y in range(min(ay, by), max(ay, by)+1):
                self.grid[y][bx] = TILE_FLOOR

        def centre(r): return (r[0] + r[2]//2, r[1] + r[3]//2)

        # Start room: entrance on floor 1, stairs up on deeper floors
        if random.random() < 0.5:
            rooms.reverse()           # vary which side the descent starts on
        sx, sy = centre(rooms[0])
        self.px, self.py = sx, sy
        self.grid[sy][sx] = TILE_ENTRY if self.floor_num == 1 else TILE_STAIRS_U

        ex, ey = centre(rooms[-1])
        if self.is_bottom:
            self.grid[ey][ex] = TILE_BOSS if self.boss_name else TILE_ALTAR
        else:
            self.grid[ey][ex] = TILE_STAIRS_D

        # Teleport pad (floors 2+) in the corner of a middle room — off the
        # corridor path, so you never warp out by accident
        if self.floor_num >= 2 and len(rooms) >= 3:
            mr = rooms[len(rooms)//2]
            for tx, ty in ((mr[0], mr[1]), (mr[0]+mr[2]-1, mr[1]),
                           (mr[0], mr[1]+mr[3]-1), (mr[0]+mr[2]-1, mr[1]+mr[3]-1)):
                if self.grid[ty][tx] == TILE_FLOOR:
                    self.grid[ty][tx] = TILE_TELEPORT
                    break

        # Chests and traps on free floor tiles away from the start
        free = [(x, y) for y in range(self.H_MAP) for x in range(self.W_MAP)
                if self.grid[y][x] == TILE_FLOOR and abs(x-sx) + abs(y-sy) > 3]
        random.shuffle(free)
        n_chests = random.randint(2, 4)
        n_traps  = random.randint(1, self.floor_num + 1)
        for x, y in free[:n_chests]:
            self.grid[y][x] = TILE_CHEST
        for x, y in free[n_chests:n_chests+n_traps]:
            self.grid[y][x] = TILE_TRAP

    @staticmethod
    def _overlap(a, b):
        ax, ay, aw, ah = a; bx, by, bw, bh = b
        return not (ax+aw+1 < bx or bx+bw+1 < ax or ay+ah+1 < by or by+bh+1 < ay)

    def reveal(self):
        for dy in range(-SIGHT_RADIUS, SIGHT_RADIUS+1):
            for dx in range(-SIGHT_RADIUS-2, SIGHT_RADIUS+3):   # cells are taller than wide
                x, y = self.px + dx, self.py + dy
                if 0 <= x < self.W_MAP and 0 <= y < self.H_MAP:
                    self.seen.add((x, y))

    # ── Rendering ─────────────────────────────────────────────

    def render(self, player, msg=""):
        from game_term import _pad
        map_pad = " " * (_pad() + 2)     # line up with the text above/below
        lines = []
        depth_col = [_GREEN, _YELL, _ORAN, _RED, _PURP][min(4, self.floor_num-1)]
        lines.append("")
        lines.append(C(f"{depth_col}{_B}{self.dungeon_name}{_R}  "
                       f"{_DIM}Floor {self.floor_num}/{self.total_floors}{_R}"
                       + (f"  {_RED}{_B}Boss floor{_R}" if self.boss_name else "")))

        hp_frac = player.hp / max(1, player.max_hp)
        hp_col  = _GREEN if hp_frac > .5 else _YELL if hp_frac > .25 else _RED
        mp_frac = player.mp / max(1, player.max_mp)
        bar_w   = 12
        hp_fill = int(bar_w * hp_frac); mp_fill = int(bar_w * mp_frac)
        hp_bar  = f"{hp_col}{'█'*hp_fill}{_DIM}{'░'*(bar_w-hp_fill)}{_R}"
        mp_bar  = f"{_CYAN}{'█'*mp_fill}{_DIM}{'░'*(bar_w-mp_fill)}{_R}"
        lines.append(C(f"HP [{hp_bar}] {hp_col}{player.hp}/{player.max_hp}{_R}   "
                       f"MP [{mp_bar}] {_CYAN}{player.mp}/{player.max_mp}{_R}   "
                       f"{_DIM}Lv{_R}{_GOLD}{player.level}{_R}  Gold: {_GOLD}{player.gold}{_R}"))
        lines.append(map_pad + f"{_DIM}{'─'*self.W_MAP}{_R}")

        for y in range(self.H_MAP):
            row = [map_pad]
            for x in range(self.W_MAP):
                if x == self.px and y == self.py:
                    row.append(f"{_RED}{_B}@{_R}")
                    continue
                if (x, y) not in self.seen:
                    row.append(" ")
                    continue
                ch  = self.grid[y][x]
                col = TILE_COLOURS.get(ch, "")
                if ch == TILE_CHEST and (x, y) in self.chests_opened:
                    ch, col = "·", TILE_COLOURS[TILE_FLOOR]
                elif ch == TILE_TRAP:
                    # Traps are hidden until you step on them
                    if (x, y) in self.traps_triggered:
                        ch, col = "x", _fg(120,40,40)
                    else:
                        ch, col = TILE_FLOOR, TILE_COLOURS[TILE_FLOOR]
                row.append(f"{col}{ch}{_R}")
            lines.append("".join(row))

        lines.append(map_pad + f"{_DIM}{'─'*self.W_MAP}{_R}")
        tc = TILE_COLOURS
        bottom = (f"{tc[TILE_BOSS]}B{_R} Boss  " if self.boss_name else
                  f"{tc[TILE_ALTAR]}*{_R} Altar  " if self.is_bottom else
                  f"{tc[TILE_STAIRS_D]}▼{_R} Down  ")
        lines.append(C(f"{_RED}@{_R} You  "
                       + (f"{tc[TILE_ENTRY]}E{_R} Exit  " if self.floor_num == 1 else
                          f"{tc[TILE_STAIRS_U]}▲{_R} Up  ")
                       + bottom
                       + f"{tc[TILE_TELEPORT]}T{_R} Teleport  "
                       f"{tc[TILE_CHEST]}C{_R} Chest"))
        lines.append(C(msg) if msg else "")
        mhint = f"{_GOLD}WASD{_R}" if getattr(player,"movement_mode","wasd")=="wasd" else f"{_GOLD}Numpad{_R}"
        lines.append(C(f"{mhint}{_DIM}/arrows=move  {_R}"
                       f"{_GOLD}[E]{_R}{_DIM}Use pad/exit  {_R}"
                       f"{_GOLD}[I]{_R}{_DIM}Bag  {_R}"
                       f"{_GOLD}[C]{_R}{_DIM}Codex  {_R}"
                       f"{_GOLD}[?]{_R}{_DIM}Help  {_R}"
                       f"{_GOLD}[Q]{_R}{_DIM}Leave dungeon{_R}"))
        draw_frame(lines)

    # ── Movement ──────────────────────────────────────────────

    def move(self, dx, dy):
        nx, ny = self.px + dx, self.py + dy
        if not (0 <= nx < self.W_MAP and 0 <= ny < self.H_MAP):
            return "blocked"
        ch = self.grid[ny][nx]
        if ch == TILE_WALL:
            return "blocked"
        if ch == TILE_BOSS:
            return "boss"        # you fight from the doorway; stay put until it's dead
        self.px, self.py = nx, ny
        self.reveal()
        if ch == TILE_ENTRY:    return "surface"
        if ch == TILE_STAIRS_D: return "stairs_down"
        if ch == TILE_STAIRS_U: return "stairs_up"
        if ch == TILE_TELEPORT: return "teleport"
        if ch == TILE_ALTAR:    return "altar"
        if ch == TILE_CHEST and (nx, ny) not in self.chests_opened: return "chest"
        if ch == TILE_TRAP  and (nx, ny) not in self.traps_triggered: return "trap"
        return "moved"

    def open_chest(self, player):
        """Open chest at current position. Returns (gold, [item names])."""
        from game_items import ITEM_POOL
        self.chests_opened.add((self.px, self.py))
        pool_weights = {
            1: [("Potion",0.5),("Ether",0.3),("Iron Ring",0.1),("Antidote",0.15)],
            2: [("Hi-Potion",0.4),("Hi-Ether",0.3),("Potion",0.3),("Mana Stone",0.2),("Fire Bomb",0.15)],
            3: [("Full Potion",0.35),("Elixir",0.25),("Frost Crystal",0.2),("Power Ring",0.1)],
            4: [("Mega Potion",0.3),("Mega Ether",0.25),("Dark Shard",0.3),("Hero Amulet",0.08)],
            5: [("Mega Potion",0.4),("Mana Crystal",0.3),("Dragon Scale",0.15),("Phoenix Pendant",0.05)],
        }
        table = pool_weights.get(min(5, self.floor_num))
        found = []
        gold  = random.randint(10, 20 + 15 * self.floor_num)
        player.gold += gold
        for name, chance in table:
            if random.random() < chance and name in ITEM_POOL:
                item = ITEM_POOL[name]()
                if player.add_item(item):
                    found.append(item.name)
        return gold, found

    def trigger_trap(self, player):
        self.traps_triggered.add((self.px, self.py))
        dmg = random.randint(6, 10 + self.floor_num * 4)
        player.hp = max(1, player.hp - dmg)
        return dmg


# =============================================================
# DUNGEON MANAGER — runs the full multi-floor dungeon loop
# =============================================================

class DungeonManager:
    """
    name      — dungeon name (used for story / clear flags)
    danger    — base danger rating (continent dependent)
    boss_name — boss waiting on the bottom floor, or None if already cleared
    floors    — number of floors (4+ adds a mini-boss on the last staircase)
    """
    def __init__(self, name, danger=2, boss_name=None, floors=DEFAULT_FLOORS):
        self.name          = name
        self.danger        = danger
        self.boss_name     = boss_name
        self.total_floors  = max(1, floors)
        self.floors        = {}
        self.current_floor = 1
        self.total_killed  = 0
        self._ensure_floor(1)

    def _ensure_floor(self, n):
        if n not in self.floors:
            self.floors[n] = DungeonFloor(n, self.name, self.total_floors,
                                          self.boss_name)
        return self.floors[n]

    def current(self):
        return self.floors[self.current_floor]

    def enter(self, player):
        """Main dungeon loop. Returns 'cleared', 'left' or 'defeat'."""
        from game_input import InputHandler
        inp = InputHandler(mode=getattr(player, "movement_mode", "wasd"))
        msg = f"{_DIM}You enter {self.name}. Find the stairs down — the boss waits at the bottom.{_R}"
        if not self.boss_name:
            msg = f"{_DIM}You return to {self.name}. Its master is gone, but treasure remains below.{_R}"
        quit_armed = False
        clr()

        while True:
            floor = self.current()
            floor.render(player, msg)
            action = inp.get_action()

            if action[0] == "cmd":
                cmd = action[1]
                if cmd == "quit":
                    if quit_armed:
                        return "left"
                    quit_armed = True
                    msg = f"{_YELL}Press Q again to leave the dungeon (floor progress is lost).{_R}"
                    continue
                quit_armed = False
                if cmd == "inventory":
                    from game_player import quick_inventory
                    quick_inventory(player)
                elif cmd == "codex":
                    from game_codex import open_encyclopedia
                    open_encyclopedia(player)
                elif cmd == "help":
                    self._show_help()
                elif cmd == "enter" and floor.grid[floor.py][floor.px] == TILE_ENTRY:
                    return "left"
                elif cmd == "enter" and floor.grid[floor.py][floor.px] == TILE_TELEPORT:
                    floor.render(player, f"{_PURP}The pad flares — you are warped to the surface!{_R}")
                    time.sleep(0.8)
                    return "left"
                msg = ""
                clr()
                continue

            if action[0] != "move":
                continue
            quit_armed = False
            _, dx, dy = action
            result = floor.move(dx, dy)
            if result != "blocked":
                player.tick_stealth()   # stealth fades per step, as on the world map
            outcome, msg = self._handle(result, player, floor)
            if outcome:
                return outcome
            if not player.is_alive():
                return "defeat"

    # ── Event handling ────────────────────────────────────────

    def _handle(self, result, player, floor):
        """Returns (outcome or None, message)."""
        if result == "blocked":
            return None, ""

        if result == "moved":
            enc = ENCOUNTER_BASE[min(len(ENCOUNTER_BASE)-1, self.current_floor-1)]
            if random.random() < enc:
                return self._fight_random(player, floor)
            return None, ""

        if result == "surface":
            return "left", ""

        if result == "teleport":
            return None, f"{_PURP}A teleport pad hums under your feet — press [E] to warp to the surface.{_R}"

        if result == "stairs_down":
            last_stairs = self.current_floor == self.total_floors - 1
            if (self.total_floors >= 4 and last_stairs and self.boss_name
                    and not floor.miniboss_defeated):
                outcome = self._fight_miniboss(player, floor)
                if outcome == "defeat":
                    return "defeat", ""
                floor.miniboss_defeated = True
            self.current_floor += 1
            self._ensure_floor(self.current_floor)
            clr()
            depth_msg = ["", "Getting darker...", "The air grows cold.",
                         "Something stirs below.", "This is where legends die."]
            text = depth_msg[min(len(depth_msg)-1, self.current_floor-1)]
            return None, f"{_GOLD}[Floor {self.current_floor}] {text}{_R}"

        if result == "stairs_up":
            if self.current_floor > 1:
                self.current_floor -= 1
                clr()
                return None, f"{_DIM}You climb back up to floor {self.current_floor}.{_R}"
            return None, ""

        if result == "chest":
            gold, items = floor.open_chest(player)
            parts = [f"{_GOLD}+{gold}g{_R}"] + [f"{_YELL}{n}{_R}" for n in items]
            return None, f"{_GOLD}★ Chest! {_R}" + "  ".join(parts)

        if result == "trap":
            dmg = floor.trigger_trap(player)
            return None, f"{_RED}!! A hidden trap springs — {dmg} damage!{_R}"

        if result == "altar":
            from game_items import ITEM_POOL
            gold = random.randint(60, 120) + player.level * 10
            player.gold += gold
            loot = random.choice(["Hi-Potion", "Hi-Ether", "Full Potion", "Power Ring",
                                  "Dark Shard", "Runic Stone", "Mana Stone"])
            player.add_item(ITEM_POOL[loot]())
            clr()
            print(C(f"\n{_GOLD}{_B}★  The treasure altar of {self.name}  ★{_R}\n"))
            print(C(f"{_GOLD}+{gold} gold{_R}  and  {_WHITE}{loot}{_R}"))
            print(C(f"\n{_DIM}A warm light carries you back to the surface.{_R}"))
            input(C(f"\n{_DIM}(Press Enter){_R}"))
            return "cleared", ""

        if result == "boss":
            return self._fight_boss(player, floor)

        return None, ""

    def _fight_random(self, player, floor):
        from game_enemies import generate_dungeon_enemy
        from game_systems import run_combat
        e = generate_dungeon_enemy(danger=self.danger + self.current_floor - 1,
                                   player_level=player.level, floor=self.current_floor)
        if player.try_stealth_evade():
            return None, f"{_PURP}A {e.name} prowls past... you stay hidden in the shadows.{_R}"
        floor.render(player, f"{_RED}!! A {e.name} emerges from the dark!{_R}")
        time.sleep(0.5)
        outcome = run_combat(player, e, first_strike=player.in_stealth)
        clr()
        if outcome == "defeat":
            return "defeat", ""
        if outcome == "escaped":
            return None, f"{_DIM}You slipped away from the {e.name}.{_R}"
        self.total_killed += 1
        return None, f"{_GREEN}The {e.name} is defeated.{_R}"

    def _fight_miniboss(self, player, floor):
        from game_enemies import create_boss, get_floor_miniboss
        from game_systems import run_combat
        from game_art import print_sprite
        name = get_floor_miniboss(self.current_floor)
        boss = create_boss(name, player.level)
        clr()
        print_sprite(name)
        print(C(f"\n{_RED}{_B}★ {name} guards the stairway down! ★{_R}"))
        input(C(f"{_DIM}(Press Enter to fight){_R}"))
        outcome = run_combat(player, boss, allow_escape=False)
        clr()
        return outcome

    def _fight_boss(self, player, floor):
        from game_enemies import create_boss
        from game_systems import run_combat
        from game_art import print_sprite
        boss = create_boss(self.boss_name, player.level)
        clr()
        print_sprite(boss.name)
        print(C(f"\n{_RED}{_B}*** THE MASTER OF {self.name.upper()}: {boss.name} ***{_R}"))
        print(C(f"{_DIM}HP {boss.max_hp}  ATK {boss.atk}  — there is no escape from this fight.{_R}"))
        print(C(f"\n{_GOLD}[F]{_R} Fight   {_GOLD}[0]{_R} {_DIM}Not yet — step back{_R}"))
        if input(C(f"\n{_GOLD}>{_R} ")).strip().lower() in ("0", "n", "b"):
            clr()
            return None, f"{_DIM}You step back from the boss chamber.{_R}"
        outcome = run_combat(player, boss, allow_escape=False)
        if outcome == "defeat":
            return "defeat", ""
        clr()
        print(C(f"\n{_GOLD}{_B}★★★  DUNGEON CLEARED: {self.name}  ★★★{_R}\n"))
        input(C(f"{_DIM}(Press Enter){_R}"))
        return "cleared", ""

    def _show_help(self):
        clr()
        print(C(f"\n{_CYAN}{_B}DUNGEON CONTROLS{_R}\n"))
        print(C(f"{_GOLD}WASD{_R}{_DIM}/Arrows (or numpad) = move{_R}"))
        print(C(f"{_GOLD}[I]{_R}{_DIM} Quick bag — use potions, equip gear{_R}"))
        print(C(f"{_GOLD}[C]{_R}{_DIM} Encyclopedia — enemies, crafting guide{_R}"))
        print(C(f"{_GOLD}[Q]{_R}{_DIM} Leave the dungeon (press twice){_R}"))
        print(C(f"\n{_GOLD}Tiles:{_R}"))
        print(C(f"  {TILE_COLOURS[TILE_ENTRY]}E{_R}  Entrance — step on it to leave"))
        print(C(f"  {TILE_COLOURS[TILE_STAIRS_D]}▼{_R}  Stairs going deeper"))
        print(C(f"  {TILE_COLOURS[TILE_STAIRS_U]}▲{_R}  Stairs going back up"))
        print(C(f"  {TILE_COLOURS[TILE_TELEPORT]}T{_R}  Teleport pad — stand on it and press [E] to warp out"))
        print(C(f"  {TILE_COLOURS[TILE_CHEST]}C{_R}  Treasure chest (step on it)"))
        print(C(f"  {TILE_COLOURS[TILE_BOSS]}B{_R}  The dungeon boss — walk into it to fight"))
        print(C(f"  {TILE_COLOURS[TILE_ALTAR]}*{_R}  Treasure altar (cleared dungeons)"))
        print(C(f"\n{_DIM}Watch out — traps are hidden in the floor. Deeper floors are harder.{_R}"))
        input(C(f"\n{_DIM}(Press Enter){_R}"))
        clr()
