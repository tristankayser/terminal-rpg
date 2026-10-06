"""
game_mining.py — Mine locations and mining mini-game for Terminal-RPG.
Uses InputHandler for raw single-keypress input (same as world map).
No Enter needed — press WASD/arrow keys to move, Q to quit.
"""

import random, os
from game_term import C, W, H, div, clr
from game_lang import T, LANG

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0);  _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60);     _CYAN=_fg(80,220,220)
_YELL=_fg(240,200,60); _ORAN=_fg(220,140,40);   _PURP=_fg(180,80,220)

# ── Ore tables per region biome ──────────────────────────────────
ORE_TABLES = {
    "forest":   [("Iron Ore",0.50),("Wolf Pelt",0.30),("Bone Shard",0.20)],
    "mountain": [("Iron Ore",0.45),("Iron Ore",0.30),("Dark Shard",0.15),("Dragon Scale",0.03)],
    "snow":     [("Frost Crystal",0.50),("Iron Ore",0.30),("Feather",0.20)],
    "desert":   [("Scale Fragment",0.45),("Iron Ore",0.35),("Dark Shard",0.10)],
    "tropical": [("Feather",0.50),("Iron Ore",0.30),("Scale Fragment",0.15)],
}

MINE_NAMES = {
    "A": ["Silverwood Mine","Ashroot Hollow","Old Foxpit"],
    "B": ["Iron Ridge Mine","Stoneback Shaft","The Deep Cut","Cragmore Mine"],
    "C": ["Frostpeak Mine","Glacier Shaft"],
    "D": ["Sandstone Mine","Dunepit","Amber Hollow"],
    "E": ["Coral Mine","Saltspire Shaft"],
}

MINE_TILE = "M"


class MineNode:
    def __init__(self, x, y, ore_name):
        self.x=x; self.y=y; self.ore_name=ore_name; self.depleted=False

    def mine(self):
        if self.depleted: return None
        self.depleted=True; return self.ore_name


class Mine:
    """Grid-based mine interior. Movement via raw InputHandler (same as world map)."""

    W_MAP = 36   # wider so map fills screen nicely
    H_MAP = 14

    def __init__(self, name, continent_id, biome):
        self.name         = name
        self.continent_id = continent_id
        self.biome        = biome
        self.grid         = [["#"]*self.W_MAP for _ in range(self.H_MAP)]
        self.px, self.py  = 1, 1
        self.nodes        = []
        self.danger       = max(1, {"mountain":3,"desert":2,"snow":2,"forest":1,"tropical":1}.get(biome,1))
        self.msg          = ""
        self._generate()

    def _generate(self):
        # Carve floor
        for y in range(1, self.H_MAP-1):
            for x in range(1, self.W_MAP-1):
                self.grid[y][x] = "."
        # Random support pillars
        for _ in range(int(self.W_MAP * self.H_MAP * 0.07)):
            x = random.randint(2, self.W_MAP-3)
            y = random.randint(2, self.H_MAP-3)
            self.grid[y][x] = "#"
        # Player start
        self.grid[self.py][self.px] = "."
        # Exit top-right
        self.grid[1][self.W_MAP-2] = "E"
        # Ore nodes
        ore_table = ORE_TABLES.get(self.biome, ORE_TABLES["forest"])
        n_nodes = random.randint(7, 12)
        placed = 0; attempts = 0
        while placed < n_nodes and attempts < 300:
            attempts += 1
            x = random.randint(2, self.W_MAP-3)
            y = random.randint(2, self.H_MAP-3)
            if self.grid[y][x]=="." and not any(n.x==x and n.y==y for n in self.nodes):
                ore = self._roll_ore(ore_table)
                self.grid[y][x] = "O"
                self.nodes.append(MineNode(x, y, ore))
                placed += 1

    def _roll_ore(self, table):
        r = random.random(); cumulative = 0
        for name, chance in table:
            cumulative += chance
            if r <= cumulative: return name
        return table[0][0]

    # ── Render ───────────────────────────────────────────────────

    TILE_COL = {
        "#": _fg(80,55,40), ".": _fg(55,45,35),
        "O": _fg(180,160,60), "E": _fg(80,200,80),
    }

    def render(self, player, ore_count, gold_mined):
        """Flicker-free: build the frame, then overwrite the screen in one go."""
        import io, contextlib
        from game_term import draw_frame
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._render_body(player, ore_count, gold_mined)
        draw_frame(buf.getvalue().split("\n"))

    def _render_body(self, player, ore_count, gold_mined):
        cols = W()
        # Align map rows with all other C()-centred content (same as _pad())
        from game_term import _pad
        map_pad = " " * _pad()
        # Header
        print(C(f"{_ORAN}{_B}MINE: {self.name}{_R}  {_DIM}Danger {self.danger}{_R}"))
        print(C(f"{_DIM}Ore found: {_GOLD}{ore_count}{_R}   {_DIM}Gold mined: {_GOLD}{gold_mined}{_R}"))
        print(C(f"{_DIM}{'─'*self.W_MAP}{_R}"))
        # Map rows — centred on map width, not content width
        for y in range(self.H_MAP):
            row = map_pad
            for x in range(self.W_MAP):
                if x == self.px and y == self.py:
                    row += f"{_RED}{_B}@{_R}"
                else:
                    ch  = self.grid[y][x]
                    col = self.TILE_COL.get(ch, "")
                    row += f"{col}{ch}{_R}"
            print(row)
        print(C(f"{_DIM}{'─'*self.W_MAP}{_R}"))
        # Legend
        tc = self.TILE_COL
        print(C(f"{_RED}@{_R} You  "
                f"{tc['#']}#{_R} Rock  "
                f"{tc['.']}·{_R} Tunnel  "
                f"{tc['O']}O{_R} Ore  "
                f"{tc['E']}E{_R} Exit"))
        # Player status
        hp_frac = player.hp / player.max_hp if player.max_hp else 0
        hp_col  = _GREEN if hp_frac>.5 else _YELL if hp_frac>.25 else _RED
        bar_w   = max(8, min(16, cols//9))
        filled  = int(bar_w * hp_frac)
        hp_bar  = f"{hp_col}{'█'*filled}{_DIM}{'░'*(bar_w-filled)}{_R}"
        print(C(f"{_DIM}HP [{hp_bar}] {hp_col}{player.hp}/{player.max_hp}{_R}   "
                f"{_DIM}Gold: {_GOLD}{player.gold}{_R}"))
        # Last message
        if self.msg:
            print(C(f"\n{self.msg}"))
        # Controls hint
        _mhint = f"{_GOLD}WASD{_R}" if getattr(player,"movement_mode","wasd")=="wasd" else f"{_GOLD}Numpad{_R}"
        print(C(f"\n{_mhint}{_DIM}=move  {_R}"
                f"{_GOLD}[E]{_R}{_DIM}Exit mine  {_R}"
                f"{_GOLD}[I]{_R}{_DIM}Bag  {_R}"
                f"{_GOLD}[C]{_R}{_DIM}Codex  {_R}"
                f"{_GOLD}[?]{_R}{_DIM}Help  {_R}"
                f"{_GOLD}[Q]{_R}{_DIM}Leave mine{_R}"))

    # ── Movement ─────────────────────────────────────────────────

    def move(self, dx, dy):
        nx, ny = self.px+dx, self.py+dy
        if not (0<=nx<self.W_MAP and 0<=ny<self.H_MAP): return "blocked"
        ch = self.grid[ny][nx]
        if ch == "#": return "blocked"
        self.px, self.py = nx, ny
        if ch == "O": return "ore"
        if ch == "E": return "exit"
        # (was 4%×danger cave-ins + 12% fights per step — up to 1 event in 4 steps)
        if random.random() < 0.012 * self.danger: return "cave_in"
        if random.random() < 0.04 + self.danger*0.015: return "encounter"
        return "moved"

    def mine_ore(self):
        for node in self.nodes:
            if node.x==self.px and node.y==self.py and not node.depleted:
                ore = node.mine()
                self.grid[self.py][self.px] = "."
                return ore
        return None

    # ── Main loop ─────────────────────────────────────────────────

    def enter(self, player):
        """Raw-input mine loop — single keypress per action, no Enter needed."""
        from game_input import InputHandler
        from game_items import Item, ITEM_POOL

        # Use player's chosen movement mode
        inp = InputHandler(mode=getattr(player, "movement_mode", "wasd"))

        ore_count  = 0
        gold_mined = 0
        self.msg   = f"{_DIM}Welcome to {self.name}. Find ore nodes [O] and reach the exit [E].{_R}"

        while True:
            self.render(player, ore_count, gold_mined)

            action = inp.get_action()

            # ── Commands ─────────────────────────────────────────
            if action[0] == "cmd":
                cmd = action[1]
                if cmd == "quit" or (cmd == "enter" and self.grid[self.py][self.px] == "E"):
                    self.msg = f"{_DIM}You climb out of the mine.{_R}"
                    self.render(player, ore_count, gold_mined)
                    import time; time.sleep(0.5)
                    return gold_mined
                elif cmd == "inventory":
                    from game_player import quick_inventory
                    quick_inventory(player)
                elif cmd == "codex":
                    from game_codex import open_encyclopedia
                    open_encyclopedia(player)
                elif cmd == "help":
                    from game_term import clr
                    clr()
                    print(C(f"\n{_CYAN}{_B}MINE CONTROLS{_R}\n"))
                    print(C(f"{_GOLD}WASD{_R}{_DIM}/Arrows = move{_R}"))
                    print(C(f"{_GOLD}[E]{_R}{_DIM} Use mine exit when standing on it{_R}"))
                    print(C(f"{_GOLD}[I]{_R}{_DIM} Quick bag — use potions, equip gear{_R}"))
                    print(C(f"{_GOLD}[C]{_R}{_DIM} Encyclopedia — enemies, crafting guide{_R}"))
                    print(C(f"{_GOLD}[Q]{_R}{_DIM} Climb out of the mine{_R}"))
                    input(C(f"\n{_DIM}(Press Enter){_R}"))
                self.msg = ""

            # ── Movement ─────────────────────────────────────────
            elif action[0] == "move":
                _, dx, dy = action
                result = self.move(dx, dy)

                if result == "blocked":
                    self.msg = f"{_DIM}Solid rock.{_R}"

                elif result == "moved":
                    self.msg = ""   # clear message, just re-render

                elif result == "ore":
                    ore = self.mine_ore()
                    if ore:
                        ore_count  += 1
                        gold_val    = random.randint(8, 25)
                        gold_mined += gold_val
                        player.gold += gold_val
                        import io, contextlib
                        with contextlib.redirect_stdout(io.StringIO()):
                            ok = player.add_item(ITEM_POOL[ore]() if ore in ITEM_POOL
                                                 else Item(ore, "material", 0, 15))
                        self.msg = (f"{_GOLD}★ Mined {_WHITE}{ore}{_GOLD}!  +{gold_val}g{_R}" if ok else
                                    f"{_GOLD}+{gold_val}g{_R}  {_RED}(bag full — {ore} left behind){_R}")
                    else:
                        self.msg = f"{_DIM}Already depleted.{_R}"

                elif result == "cave_in":
                    dmg = random.randint(10, 30)
                    player.hp = max(1, player.hp - dmg)
                    self.msg = f"{_RED}!! CAVE-IN! Rocks fall — {dmg} damage!{_R}"
                    if player.hp <= 5:
                        self.render(player, ore_count, gold_mined)
                        import time; time.sleep(1.0)
                        return gold_mined

                elif result == "encounter":
                    from game_enemies import generate_enemy
                    from game_systems import run_combat
                    e = generate_enemy("dungeon", self.danger, player.level)
                    self.msg = f"{_RED}!! A {e.name} lurks in the dark!{_R}"
                    self.render(player, ore_count, gold_mined)
                    import time; time.sleep(0.4)
                    outcome = run_combat(player, e)
                    if outcome == "defeat":
                        return gold_mined
                    self.msg = (f"{_DIM}You escaped the {e.name}.{_R}" if outcome == "escaped"
                                else f"{_GREEN}Enemy defeated! Keep mining.{_R}")

                elif result == "exit":
                    self.msg = f"{_GREEN}You exit the mine.  Ore: {ore_count}  Gold earned: {gold_mined}g{_R}"
                    self.render(player, ore_count, gold_mined)
                    import time; time.sleep(0.8)
                    return gold_mined

            # ── None / unknown ───────────────────────────────────
            # just re-render on next loop iteration

            if not player.is_alive():
                return gold_mined


def generate_mine_locations(continent_id, biome, terrain, region_map, width, height, count=3):
    """Place mine locations on a continent (on hill/mountain terrain)."""
    candidates = [
        (x, y) for y in range(height) for x in range(width)
        if region_map[y][x] == continent_id
        and terrain[y][x] in ("^", ",")
    ]
    if not candidates: return []

    names = MINE_NAMES.get(continent_id, ["Unknown Mine"])
    random.shuffle(candidates)
    mines = []
    for i in range(min(count, len(names), len(candidates))):
        x, y = candidates[i]
        name = names[i % len(names)]
        mines.append({
            "type": "mine", "icon": MINE_TILE,
            "name": name, "x": x, "y": y,
            "continent": continent_id, "region": continent_id,
            "biome": biome,
        })
    return mines
