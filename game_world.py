"""
world_map.py — Terminal-RPG  320×120 archipelago world map.
Five continents, mines, dragon cave, story hooks, ship travel, fog of war.
"""

import os
import json, math, random
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot
from game_lang import T, set_language, LANG, LANGUAGE_NAMES
from collections import defaultdict

R_="\033[0m"; B_="\033[1m"
def fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"

C_GOLD=fg(255,215,0); C_WHITE=fg(255,255,255); C_DIM=fg(90,90,100)
C_GREEN=fg(80,200,80); C_RED=fg(220,60,60);   C_CYAN=fg(80,220,220)
C_BLUE=fg(80,130,220); C_YELL=fg(240,200,60); C_ORAN=fg(220,140,40)
C_PURP=fg(180,80,220); C_TEAL=fg(60,200,180)

OCEAN="~"; SHALLOWS=";"; PLAINS="."; FOREST="T"
MOUNTAIN="^"; SNOW="*"; HILL=","; ROAD="="; RIVER="/"; SAND=":"
PLAYER="@"; MINE_T="M"; DRAGON_T="V"; BASE_T="@"  # player base on map

TILE={
    OCEAN:    (fg(20,50,180),    "~"), SHALLOWS:(fg(40,100,220),   "~"),
    PLAINS:   (fg(55,145,55),    "."), FOREST:  (fg(20,110,20),    "T"),
    MOUNTAIN: (fg(130,125,115),  "^"), SNOW:    (fg(220,235,255),  "*"),
    HILL:     (fg(110,95,55),    ","), ROAD:    (fg(185,165,85),   "="),
    RIVER:    (fg(50,145,210),   "/"), SAND:    (fg(210,185,100),  ":"),
    PLAYER:   (fg(255,60,60)+B_, "@"),
    "P": (fg(90,170,255)+B_,"P"), "H":(fg(60,215,195)+B_,"H"),
    "X": (fg(220,60,60)+B_, "X"),  "R":(fg(175,75,215)+B_,"R"),
    "S": (fg(255,255,180)+B_,"S"),
    MINE_T:   (fg(200,160,80)+B_,"M"),
    DRAGON_T: (fg(220,60,40)+B_,"V"),
    "b":      (fg(255,200,80)+B_,"b"),   # player base marker on map
}

# ── Extension registry ───────────────────────────────────────────
# Feature modules (game_capital, game_structures, ...) register extra map
# glyphs, arrival messages and enter handlers here instead of editing the
# core world code.  See register_place_type().
TILE_NAMES = {}          # glyph -> human name for the HUD ("Capital", "Shrine")
ARRIVE_MSG = {}          # loc type -> callable(loc) -> str
ENTER_HANDLERS = {}      # loc type -> callable(world, player, loc, autosave)
BLOCKED_FOR_MONSTERS = set(["~", ";", "#", "P", "H", "X", "R", "M", "V"])

def register_place_type(loc_type, glyph, colour, name, enter=None, arrive=None,
                        symbol=None):
    """Register a new world-map place type.

    loc_type : value of loc["type"] in world.locations
    glyph    : single ASCII char stored in world.terrain (must be unique)
    colour   : ANSI colour prefix (use fg(r,g,b)+B_)
    name     : HUD tile name
    enter    : callable(world, player, loc, autosave) run when E is pressed
    arrive   : callable(loc) -> str message when stepping onto the place
    symbol   : char drawn on screen (defaults to glyph)
    """
    TILE[glyph] = (colour, symbol or glyph)
    TILE_NAMES[glyph] = name
    BLOCKED_FOR_MONSTERS.add(glyph)
    if enter:  ENTER_HANDLERS[loc_type] = enter
    if arrive: ARRIVE_MSG[loc_type] = arrive

def _load_extensions():
    """Import feature modules so they can call register_place_type()."""
    for mod in ("game_capital", "game_castles", "game_structures", "game_towns"):
        try:
            __import__(mod)
        except ImportError:
            pass
        except Exception as e:          # never let a feature module break the map
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
                    f.write(f"extension {mod} failed: {e!r}\n")
            except Exception:
                pass

def paint(ch):
    col,sym=TILE.get(ch,("",ch)); return f"{col}{sym}{R_}"
def div(w=70,c=C_DIM): return f"  {c}{'─'*w}{R_}"
def hpbar(c,m,w=None):
    w=w or max(12,min(24,W()//5))
    frac=c/m if m else 0; f=int(w*frac)
    col=C_GREEN if frac>.5 else C_YELL if frac>.25 else C_RED
    return f"[{col}{'█'*f}{C_DIM}{'░'*(w-f)}{R_}] {col}{c}/{m}{R_}"
def mpbar(c,m,w=None):
    w=w or max(8,min(16,W()//7))
    frac=c/m if m else 0; f=int(w*frac)
    return f"[{C_BLUE}{'█'*f}{C_DIM}{'░'*(w-f)}{R_}] {C_BLUE}{c}/{m}{R_}"
from game_term import clr as clear, draw_frame

# Dungeon difficulty and bosses per continent / dungeon name
CONTINENT_DANGER = {"A": 1, "E": 2, "B": 3, "D": 3, "C": 4}
DUNGEON_BOSSES = {
    "Wolf Den": "Goblin King",       "Mosshaven Ruins": "Dungeon Warden",
    "Blackroot Crypt": "Shadow Lich",
    "Deep Mines": "Dungeon Warden",  "Shattered Peak": "Goblin King",
    "Forge Depths": "Shadow Lich",
    "Ice Cavern": "Frost Dragon",    "Frozen Vault": "Shadow Lich",
    "Sand Tomb": "Shadow Lord",      "Dust Shrine": "Dungeon Warden",
    "Scorpion Den": "Goblin King",
    "Sea Cavern": "Shadow Lich",     "Tide Tomb": "Dungeon Warden",
}
MIN_MAP_ENEMIES = 30

WIDTH=320; HEIGHT=120
SAVE_FILE="world_save.json"
# Viewport dimensions computed dynamically from terminal size
def get_viewport():
    """Return (view_w, view_h) fitting the current terminal, leaving room for UI."""
    try:
        import shutil
        size = shutil.get_terminal_size(fallback=(80, 24))
        cols, rows = size.columns, size.lines
    except Exception:
        cols, rows = 80, 24
    view_w = max(30, min(cols - 4, WIDTH))
    view_h = max(10, min(rows - 11, HEIGHT))
    return view_w, view_h

VIEW_W=72; VIEW_H=28  # fallback defaults (overridden at render time)

CONTINENTS=[
    {"id":"A","name":"AELORIA","col":fg(80,210,100),"biome":"forest",
     "cx_f":0.18,"cy_f":0.22,"base_rx":32,"base_ry":20,"nblobs":6,
     "cities":["Greenveil","Oakwatch","Mossford"],
     "ports":["Tidereach","Greenport"],
     "dungeons":["Wolf Den","Mosshaven Ruins","Blackroot Crypt"]},
    {"id":"B","name":"IRONSPIRE","col":fg(165,150,120),"biome":"mountain",
     "cx_f":0.55,"cy_f":0.28,"base_rx":34,"base_ry":22,"nblobs":7,
     "cities":["Ironmoor","Stonehelm","Hammerfast"],
     "ports":["Cliff Port","Anvil Docks"],
     "dungeons":["Deep Mines","Shattered Peak","Forge Depths"]},
    {"id":"C","name":"FROSTHEIM","col":fg(180,220,255),"biome":"snow",
     "cx_f":0.40,"cy_f":0.08,"base_rx":20,"base_ry":12,"nblobs":4,
     "cities":["Frostheim","Glacierhold"],
     "ports":["Ice Harbour"],
     "dungeons":["Ice Cavern","Frozen Vault"]},
    {"id":"D","name":"ASH SANDS","col":fg(230,190,60),"biome":"desert",
     "cx_f":0.78,"cy_f":0.68,"base_rx":30,"base_ry":18,"nblobs":5,
     "cities":["Sandreach","Dunewatch","Oasis Keep"],
     "ports":["Sand Docks","Desert Port"],
     "dungeons":["Sand Tomb","Dust Shrine","Scorpion Den"]},
    {"id":"E","name":"SOUTH ISLES","col":fg(80,200,160),"biome":"tropical",
     "cx_f":0.25,"cy_f":0.78,"base_rx":26,"base_ry":16,"nblobs":5,
     "cities":["Seaview","Palmhaven","Coralwatch"],
     "ports":["South Port","Coral Bay","Pearl Harbour"],
     "dungeons":["Sea Cavern","Tide Tomb"]},
]

ENC_RATE={PLAINS:.02,HILL:.04,FOREST:.06,MOUNTAIN:.07,SNOW:.06,
          SAND:.03,RIVER:.02,ROAD:.0,OCEAN:.0,SHALLOWS:.0}
DANGER_LVL={PLAINS:1,HILL:2,FOREST:2,MOUNTAIN:3,SNOW:3,SAND:2,RIVER:1,ROAD:1}
BIOME_ZONE={"forest":"forest","mountain":"mountain","snow":"snow",
            "desert":"desert","tropical":"plains"}


class WorldMap:
    def __init__(self,seed=None):
        self.seed=seed or random.randint(1,9_999_999)
        random.seed(self.seed)
        self.terrain   =[[OCEAN]*WIDTH for _ in range(HEIGHT)]
        self.heightmap =[[0]*WIDTH for _ in range(HEIGHT)]
        self.cont_map  =[[" "]*WIDTH for _ in range(HEIGHT)]
        self.discovered=[[False]*WIDTH for _ in range(HEIGHT)]
        self.locations =[]
        self.ships     =[]
        self.map_enemies=[]
        self.player_x=WIDTH//2; self.player_y=HEIGHT//2
        self.turn_count=0
        self.dragon_alive=True
        self.last_msg=(f"{C_GREEN}{T('world.title')}!{R_}  "
                       f"{C_DIM}Explore a 320×120 world. [?] for help.{R_}")
        self._generate()
        self._place_player_near_city()
        self._spawn_enemies()
        # The world layout is seeded, but gameplay randomness must not be:
        # otherwise every load of a save replays the exact same "random"
        # fights, loot and events.
        random.seed()

    # ── GENERATION ──────────────────────────────────────────────

    def _noise(self,x,y,freq=1.0):
        s=self.seed
        return(math.sin(x*.11*freq+s*.0013)*.8+math.cos(y*.13*freq+s*.0017)*.7
              +math.sin((x+y)*.07*freq)*.6+math.cos((x-y)*.05*freq+s*.002)*.5
              +math.sin(x*.03*freq-y*.04)*.4)

    def _ellipse(self,x,y,cx,cy,rx,ry):
        return ((x-cx)**2/rx**2)+((y-cy)**2/ry**2)<=1

    def _generate(self):
        self._gen_continents()
        self._assign_terrain()
        self._add_beaches()
        self._add_rivers()
        self._place_locations()
        self._place_mines()
        self._place_dragon_cave()
        self._place_roads()
        self._place_ships()
        self._compute_cont_labels()
        # Must stay LAST among the RNG users: anything that consumes random
        # numbers before this point defines the map layout that old save
        # files rely on.
        self._place_ruins()
        # New content (castles, walkable towns, structures) uses its OWN
        # seeded RNG so the base layout above stays identical for old saves.
        self._place_extras()
        # Deterministic repairs (no RNG): ports dropped on inland desert sand
        # had no ship, and some towns/dungeons ended up on islands with no
        # way to reach them — e.g. story targets like Sandreach.
        self._fix_shipless_ports()
        self._ensure_reachable()

    RUIN_NAMES = {
        "A": ["Old Watchtower", "Elderwood Shrine"],
        "B": ["Fallen Forge", "Giant's Stair"],
        "C": ["Frozen Chapel", "Icebound Keep"],
        "D": ["Buried Obelisk", "Sunken Bazaar"],
        "E": ["Coral Temple", "Wreck of the Gull"],
    }

    def _place_ruins(self):
        """Ruins were on the map legend but never generated."""
        for cont in CONTINENTS:
            cid=cont["id"]
            land=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                  if self.cont_map[y][x]==cid and self.terrain[y][x] in (PLAINS,FOREST,HILL)]
            if not land: continue
            for name in self.RUIN_NAMES.get(cid,[]):
                for _ in range(60):
                    lx,ly=random.choice(land)
                    if not any(abs(l["x"]-lx)<5 and abs(l["y"]-ly)<5 for l in self.locations):
                        self.terrain[ly][lx]="R"
                        self.locations.append({"type":"ruins","icon":"R","name":name,
                                               "x":lx,"y":ly,"continent":cid,"region":cid})
                        break

    def _place_extras(self):
        _load_extensions()
        rng = random.Random(self.seed * 7919 + 17)
        for mod, fn in (("game_capital", "place_capital"),
                        ("game_structures", "place_structures")):
            try:
                m = __import__(mod)
            except ImportError:
                continue
            f = getattr(m, fn, None)
            if f:
                try:
                    f(self, rng)
                except Exception as e:
                    try:
                        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as fh:
                            fh.write(f"{mod}.{fn} failed: {e!r}\n")
                    except Exception:
                        pass

    def _fix_shipless_ports(self):
        """Move ports with no water nearby to the closest real shoreline."""
        moved=False
        docked={s["port_name"] for s in self.ships}
        for loc in self.locations:
            if loc["type"]!="port" or loc["name"] in docked: continue
            cid=loc["continent"]
            taken={(l["x"],l["y"]) for l in self.locations}
            shore=[(x,y) for y in range(1,HEIGHT-1) for x in range(1,WIDTH-1)
                   if self.cont_map[y][x]==cid and self.terrain[y][x] in (SAND,PLAINS,FOREST,HILL,ROAD)
                   and (x,y) not in taken
                   and any(self.terrain[y+dy][x+dx] in (OCEAN,SHALLOWS)
                           for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))]
            if not shore: continue
            nx,ny=min(shore,key=lambda p:((p[0]-loc["x"])**2+(p[1]-loc["y"])**2,p[1],p[0]))
            self.terrain[loc["y"]][loc["x"]]=SAND
            self.terrain[ny][nx]="H"
            loc["x"],loc["y"]=nx,ny
            moved=True
        if moved:
            self._place_ships()

    def _land_component(self,start):
        """4-connected walkable tiles reachable on foot (WASD has no diagonals)."""
        seen={start}; todo=[start]
        while todo:
            x,y=todo.pop()
            for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if (0<=nx<WIDTH and 0<=ny<HEIGHT and (nx,ny) not in seen
                        and self.terrain[ny][nx] not in (OCEAN,SHALLOWS)):
                    seen.add((nx,ny)); todo.append((nx,ny))
        return seen

    def _reachable_tiles(self,start):
        """Tiles reachable from start on foot plus by ship between docked ports."""
        docked={s["port_name"] for s in self.ships}
        ports=[(l["x"],l["y"]) for l in self.locations
               if l["type"]=="port" and l["name"] in docked]
        reach=set(); todo=[start]; sailed=False
        while todo:
            s=todo.pop()
            if s in reach: continue
            reach|=self._land_component(s)
            if not sailed and any(p in reach for p in ports):
                sailed=True; todo.extend(ports)
        return reach

    def _ensure_reachable(self):
        """Lay a sandbar from any stranded location to the reachable world."""
        cities=[l for l in self.locations if l["type"]=="city"]
        if not cities: return
        reach=self._reachable_tiles((cities[0]["x"],cities[0]["y"]))
        for loc in self.locations:
            start=(loc["x"],loc["y"])
            if start in reach: continue
            same=[p for p in reach if self.cont_map[p[1]][p[0]]==loc["continent"]]
            goal=set(same) if same else reach
            # BFS over every tile to the nearest reachable one, then fill water
            prev={start:None}; q=[start]; hit=None
            for cur in q:
                if cur in goal: hit=cur; break
                x,y=cur
                for nxt in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if 0<=nxt[0]<WIDTH and 0<=nxt[1]<HEIGHT and nxt not in prev:
                        prev[nxt]=cur; q.append(nxt)
            if hit is None: continue
            p=hit
            while p is not None:
                x,y=p
                if self.terrain[y][x] in (OCEAN,SHALLOWS):
                    self.terrain[y][x]=SAND
                    self.cont_map[y][x]=loc["continent"]
                p=prev[p]
            reach=self._reachable_tiles((cities[0]["x"],cities[0]["y"]))

    def _gen_continents(self):
        for cont in CONTINENTS:
            cx=int(cont["cx_f"]*WIDTH); cy=int(cont["cy_f"]*HEIGHT)
            blobs=[]
            for _ in range(cont["nblobs"]):
                bx=cx+random.randint(-cont["base_rx"]//2,cont["base_rx"]//2)
                by=cy+random.randint(-cont["base_ry"]//2,cont["base_ry"]//2)
                rx=cont["base_rx"]+random.randint(-4,4)
                ry=cont["base_ry"]+random.randint(-3,3)
                blobs.append((bx,by,max(5,rx),max(4,ry)))
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if not any(self._ellipse(x,y,bx,by,rx,ry) for bx,by,rx,ry in blobs): continue
                    n=self._noise(x,y)
                    if n<-1.1: continue
                    if self.terrain[y][x]==OCEAN:
                        self.terrain[y][x]=PLAINS
                        md=min(math.sqrt((x-bx)**2/rx**2+(y-by)**2/ry**2) for bx,by,rx,ry in blobs)
                        h=int((1.0-md)*50+self._noise(x,y,2.0)*10)
                        self.heightmap[y][x]=max(0,h)
                        self.cont_map[y][x]=cont["id"]

    def _assign_terrain(self):
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.terrain[y][x]!=PLAINS: continue
                cid=self.cont_map[y][x]
                cont=next((c for c in CONTINENTS if c["id"]==cid),None)
                biome=cont["biome"] if cont else "forest"
                h=self.heightmap[y][x]; n=self._noise(x*1.3,y*1.5,1.5)
                if   h>=46: self.terrain[y][x]=SNOW
                elif h>=38: self.terrain[y][x]=MOUNTAIN
                elif h>=28:
                    self.terrain[y][x]=(SNOW if biome=="snow" else SAND if biome=="desert" else HILL)
                else:
                    if   biome=="forest":   self.terrain[y][x]=FOREST if n>-0.3 else PLAINS
                    elif biome=="snow":     self.terrain[y][x]=SNOW   if h>=15  else PLAINS
                    elif biome=="desert":   self.terrain[y][x]=SAND   if n>-0.8 else PLAINS
                    elif biome=="mountain": self.terrain[y][x]=FOREST if n>.2 else PLAINS if n>-.4 else HILL
                    elif biome=="tropical": self.terrain[y][x]=FOREST if n>.0  else PLAINS

    def _add_beaches(self):
        beach=set()
        for y in range(1,HEIGHT-1):
            for x in range(1,WIDTH-1):
                if self.terrain[y][x] in (PLAINS,FOREST,HILL):
                    for dy in range(-1,2):
                        for dx in range(-1,2):
                            if self.terrain[y+dy][x+dx]==OCEAN: beach.add((x,y))
        for (x,y) in beach:
            if self.terrain[y][x] not in (MOUNTAIN,SNOW,RIVER,ROAD):
                self.terrain[y][x]=SAND
        for y in range(1,HEIGHT-1):
            for x in range(1,WIDTH-1):
                if self.terrain[y][x]==OCEAN:
                    for dy in range(-1,2):
                        for dx in range(-1,2):
                            if self.terrain[y+dy][x+dx] not in (OCEAN,SHALLOWS):
                                self.terrain[y][x]=SHALLOWS; break

    def _add_rivers(self):
        starts=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                if self.terrain[y][x] in (MOUNTAIN,HILL) and self.heightmap[y][x]>30]
        random.shuffle(starts)
        for sx,sy in starts[:8]:
            cx,cy=sx,sy
            for _ in range(random.randint(8,22)):
                if not(0<cx<WIDTH-1 and 0<cy<HEIGHT-1): break
                if self.terrain[cy][cx] not in (MOUNTAIN,HILL,PLAINS,FOREST,SAND): break
                self.terrain[cy][cx]=RIVER
                best=None; bh=self.heightmap[cy][cx]
                for dy in [-1,0,1]:
                    for dx in [-1,0,1]:
                        nx,ny=cx+dx,cy+dy
                        if 0<=nx<WIDTH and 0<=ny<HEIGHT:
                            nh=self.heightmap[ny][nx]
                            if nh<bh and self.terrain[ny][nx] not in (OCEAN,SHALLOWS,RIVER):
                                bh=nh; best=(nx,ny)
                if best: cx,cy=best
                else: cx+=random.choice([-1,0,1]); cy+=1

    def _place_locations(self):
        for cont in CONTINENTS:
            cid=cont["id"]
            land=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                  if self.cont_map[y][x]==cid
                  and self.terrain[y][x] not in (OCEAN,SHALLOWS,RIVER,MOUNTAIN,SNOW,SAND)]
            coast=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                   if self.cont_map[y][x]==cid and self.terrain[y][x]==SAND]
            deep=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                  if self.cont_map[y][x]==cid
                  and self.terrain[y][x] in (HILL,MOUNTAIN,FOREST,PLAINS)]
            if not land: continue
            for name in cont["cities"]:
                for _ in range(50):
                    lx,ly=random.choice(land)
                    if not any(abs(l["x"]-lx)<6 and abs(l["y"]-ly)<6 for l in self.locations): break
                self.terrain[ly][lx]="P"
                self.locations.append({"type":"city","icon":"P","name":name,
                                       "x":lx,"y":ly,"continent":cid,"region":cid})
            for name in cont["ports"]:
                pool=coast if coast else land
                for _ in range(50):
                    lx,ly=random.choice(pool)
                    if not any(abs(l["x"]-lx)<5 and abs(l["y"]-ly)<5 for l in self.locations): break
                self.terrain[ly][lx]="H"
                self.locations.append({"type":"port","icon":"H","name":name,
                                       "x":lx,"y":ly,"continent":cid,"region":cid})
            for name in cont["dungeons"]:
                pool=deep if deep else land
                for _ in range(50):
                    lx,ly=random.choice(pool)
                    if not any(abs(l["x"]-lx)<5 and abs(l["y"]-ly)<5 for l in self.locations): break
                self.terrain[ly][lx]="X"
                self.locations.append({"type":"dungeon","icon":"X","name":name,
                                       "x":lx,"y":ly,"continent":cid,"region":cid})

    def _place_mines(self):
        from game_mining import generate_mine_locations
        for cont in CONTINENTS:
            mines=generate_mine_locations(
                cont["id"],cont["biome"],self.terrain,self.cont_map,WIDTH,HEIGHT,
                count=random.randint(2,4))
            for m in mines:
                if not any(abs(l["x"]-m["x"])<4 and abs(l["y"]-m["y"])<4 for l in self.locations):
                    self.terrain[m["y"]][m["x"]]=MINE_T
                    self.locations.append(m)

    def _place_dragon_cave(self):
        """Place ONE dragon cave on the highest mountain tiles of continent B (IRONSPIRE)."""
        peaks=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
               if self.cont_map[y][x]=="B"
               and self.terrain[y][x] in (MOUNTAIN,SNOW)
               and self.heightmap[y][x]>=40]
        if not peaks:
            peaks=[(x,y) for y in range(HEIGHT) for x in range(WIDTH)
                   if self.cont_map[y][x]=="B" and self.terrain[y][x]==MOUNTAIN]
        if not peaks: return
        # Pick the highest point
        peaks.sort(key=lambda p:-self.heightmap[p[1]][p[0]])
        # Prefer a peak with some room around it, but always place the lair:
        # the Dragon's Curse story can't be finished without it (mines often
        # took every spot among the 20 highest peaks).
        taken={(l["x"],l["y"]) for l in self.locations}
        roomy=[p for p in peaks
               if not any(abs(l["x"]-p[0])<6 and abs(l["y"]-p[1])<6 for l in self.locations)]
        free=[p for p in peaks if p not in taken]
        spot=(roomy or free or [None])[0]
        if not spot: return
        lx,ly=spot
        self.terrain[ly][lx]=DRAGON_T
        self.locations.append({
            "type":"dragon_cave","icon":DRAGON_T,
            "name":"Vaeltharion's Lair",
            "x":lx,"y":ly,"continent":"B","region":"B"
        })

    def _place_roads(self):
        for cont in CONTINENTS:
            cid=cont["id"]
            nodes=[l for l in self.locations if l["continent"]==cid
                   and l["type"] in ("city","port")]
            for i in range(len(nodes)-1):
                ax,ay=nodes[i]["x"],nodes[i]["y"]
                bx,by=nodes[i+1]["x"],nodes[i+1]["y"]
                cx,cy=ax,ay; steps=0
                while(cx!=bx or cy!=by) and steps<400:
                    if abs(cx-bx)>abs(cy-by): cx+=1 if cx<bx else -1
                    else: cy+=1 if cy<by else -1
                    t=self.terrain[cy][cx]
                    if(0<=cx<WIDTH and 0<=cy<HEIGHT
                       and t not in (OCEAN,SHALLOWS,RIVER,"P","H","X","R",MINE_T,DRAGON_T)
                       and self.cont_map[cy][cx]==cid):
                        self.terrain[cy][cx]=ROAD
                    steps+=1

    def _place_ships(self):
        self.ships=[]
        for loc in self.locations:
            if loc["type"]!="port": continue
            px,py=loc["x"],loc["y"]
            for r in range(1,6):
                found=False
                for dy in range(-r,r+1):
                    for dx in range(-r,r+1):
                        if abs(dx)!=r and abs(dy)!=r: continue
                        nx,ny=px+dx,py+dy
                        if(0<=nx<WIDTH and 0<=ny<HEIGHT
                           and self.terrain[ny][nx] in (OCEAN,SHALLOWS)
                           and not any(s["x"]==nx and s["y"]==ny for s in self.ships)):
                            self.ships.append({"x":nx,"y":ny,
                                               "port_name":loc["name"],
                                               "port_x":px,"port_y":py})
                            found=True; break
                    if found: break
                if found: break

    def _compute_cont_labels(self):
        sums=defaultdict(lambda:[0,0,0])
        for y in range(HEIGHT):
            for x in range(WIDTH):
                cid=self.cont_map[y][x]
                if cid!=" ": sums[cid][0]+=x; sums[cid][1]+=y; sums[cid][2]+=1
        self.cont_labels=[(cid,sx//cnt,sy//cnt)
                          for cid,(sx,sy,cnt) in sums.items() if cnt]

    def _place_player_near_city(self):
        cities=[l for l in self.locations if l["type"]=="city"]
        if cities:
            c=cities[0]; self.player_x=c["x"]; self.player_y=max(0,c["y"]-1)
        self._reveal(radius=8)

    def _spawn_enemies(self):
        from game_map_enemies import spawn_world_enemies
        self.map_enemies=spawn_world_enemies(
            self.locations,self.terrain,WIDTH,HEIGHT,count=40,cont_map=self.cont_map)

    def _reveal(self,radius=6):
        for dy in range(-radius,radius+1):
            for dx in range(-radius,radius+1):
                nx,ny=self.player_x+dx,self.player_y+dy
                if 0<=nx<WIDTH and 0<=ny<HEIGHT: self.discovered[ny][nx]=True

    # ── RENDER ──────────────────────────────────────────────────

    def render(self,player=None):
        if player and hasattr(player,"bases"):
            self.update_base_positions(player)
        import shutil
        sz=shutil.get_terminal_size(fallback=(80,24))
        cols,rows=sz.columns,sz.lines

        # ─────────────────────────────────────────────────────────────────
        # LAYOUT:
        #   top divider · title bar · divider
        #   MAP (fills as much vertical space as possible)
        #   divider · info line · controls · last message
        # The whole frame is written in one go (cursor-home + overwrite),
        # so walking around no longer flickers.
        # ─────────────────────────────────────────────────────────────────
        TOP_ROWS    = 3
        BOTTOM_ROWS = 4
        view_h = max(6, min(rows - TOP_ROWS - BOTTOM_ROWS - 1, HEIGHT))

        MAX_MAP_W  = 120
        content_w  = min(cols - 1, MAX_MAP_W)
        view_w     = max(20, min(content_w, WIDTH))

        map_pad = max(0, (cols - view_w) // 2)
        P = " " * map_pad
        DIV = P + f"{C_DIM}{'─'*view_w}{R_}"
        out = []

        # ── TOP BAR ───────────────────────────────────────────────────────
        turn_str = T("world.turn", n=self.turn_count)
        if player:
            imm = f" {C_GOLD}{B_}★{player.god_immunity_turns}{R_}" if getattr(player,"god_immunity_turns",0)>0 else ""
            stl = f" {C_PURP}[hidden]{R_}" if player.in_stealth else ""
            party_lbl = f" {C_TEAL}[{','.join(m.name for m in player.party.members)}]{R_}" if player.party.members else ""
            if view_w >= 100:
                hp_w = max(8, min(16, view_w // 8))
                mp_w = max(5, min(10, view_w // 12))
                title_line = (
                    f"{C_CYAN}{B_}Terminal-RPG{R_}  {C_DIM}{turn_str}{R_}  "
                    f"{C_WHITE}{B_}{player.name}{R_} {C_DIM}Lv{R_}{C_GOLD}{B_}{player.level}{R_} "
                    f"{C_DIM}[{C_PURP}{player.job.name}{R_}{C_DIM}]{R_}  "
                    f"HP {hpbar(player.hp,player.max_hp,hp_w)}  "
                    f"MP {mpbar(player.mp,player.max_mp,mp_w)}  "
                    f"{C_GOLD}G:{player.gold}{R_}{party_lbl}{imm}{stl}"
                )
            else:
                frac_hp = player.hp/player.max_hp if player.max_hp else 0
                hp_col  = C_GREEN if frac_hp>.5 else C_YELL if frac_hp>.25 else C_RED
                title_line = (
                    f"{C_WHITE}{B_}{player.name}{R_} "
                    f"{C_GOLD}Lv{player.level}{R_} "
                    f"HP {hp_col}{player.hp}/{player.max_hp}{R_}  "
                    f"MP {C_BLUE}{player.mp}/{player.max_mp}{R_}  "
                    f"{C_GOLD}G:{player.gold}{R_}{imm}{stl}"
                )
        else:
            title_line = f"{C_CYAN}{B_}Terminal-RPG{R_}  {C_DIM}{turn_str}{R_}"

        out.append(DIV)
        out.append(C(title_line))
        out.append(DIV)

        # ── MAP ───────────────────────────────────────────────────────────
        hw,hh = view_w//2, view_h//2
        cam_x = max(hw, min(self.player_x, WIDTH-hw))
        cam_y = max(hh, min(self.player_y, HEIGHT-hh))
        sx,sy = cam_x-hw, cam_y-hh
        enemy_at = {(e.x,e.y):e for e in self.map_enemies}
        ship_at  = {(s["x"],s["y"]):s for s in self.ships}

        for dy in range(view_h):
            y = sy+dy
            row = [P]
            for dx in range(view_w):
                x = sx+dx
                if not (0<=x<WIDTH and 0<=y<HEIGHT):
                    row.append(" "); continue
                if x==self.player_x and y==self.player_y:
                    row.append(paint(PLAYER))
                elif not self.discovered[y][x]:
                    row.append(" ")
                else:
                    e = enemy_at.get((x,y))
                    if e: row.append(e.display)
                    elif (x,y) in ship_at: row.append(paint("S"))
                    elif self._is_base_tile(x,y): row.append(paint("b"))
                    else: row.append(paint(self.terrain[y][x]))
            out.append("".join(row))

        # ── BOTTOM BAR ────────────────────────────────────────────────────
        out.append(DIV)

        ter  = self.terrain[self.player_y][self.player_x]
        cid  = self.cont_map[self.player_y][self.player_x]
        cont = next((c for c in CONTINENTS if c["id"]==cid), None)
        tname= {OCEAN:"Ocean",SHALLOWS:"Shallows",PLAINS:"Plains",
                FOREST:"Forest",MOUNTAIN:"Mountains",SNOW:"Snow",
                HILL:"Hills",ROAD:"Road",RIVER:"River",SAND:"Sand",
                MINE_T:"Mine",DRAGON_T:"Dragon Cave","P":"City","H":"Port",
                "X":"Dungeon","R":"Ruins",**TILE_NAMES}.get(ter,"?")
        cont_col  = cont["col"] if cont else C_WHITE
        cont_name = cont["name"] if cont else "Open Sea"
        loc  = self._loc_at(self.player_x, self.player_y)
        ship = next((s for s in self.ships if s["x"]==self.player_x and s["y"]==self.player_y), None)
        loc_str = ""
        if loc:   loc_str = f"  {C_GOLD}{B_}▶ {loc['name']} [E]{R_}"
        elif ship: loc_str = f"  {fg(255,255,180)}⚓ Ship [E]{R_}"
        nearby_parts = []
        for e in self.map_enemies:
            dist = math.sqrt((e.x-self.player_x)**2+(e.y-self.player_y)**2)
            if dist<=3 and self.discovered[e.y][e.x]:
                c=fg(255,80,80) if e.chasing else fg(220,160,60)
                nearby_parts.append(f"{c}{'⚔' if e.chasing else '●'}{e.name}{R_}")
        nearby_str = f"  {C_RED}⚠ {','.join(nearby_parts)}{R_}" if nearby_parts else ""
        story_str = ""
        if player and player.stories.get_main_step():
            step  = player.stories.get_main_step()
            story = player.stories.get_main_story()
            col   = story["colour"] if story else C_GOLD
            prog  = player.stories.main_progress
            req   = step["required"]
            story_str = f"  {col}★{step['title']}{R_} {C_DIM}[{prog}/{req}]{R_}"
        out.append(C(f"{cont_col}{cont_name}{R_}  {C_DIM}{tname}{R_}"
                     f"{loc_str}{nearby_str}{story_str}"))

        mhint = f"{C_GOLD}WASD{R_}" if (not player or player.movement_mode=="wasd") else f"{C_GOLD}Numpad{R_}"
        if view_w >= 110:
            out.append(C(f"{mhint}{C_DIM}=move  {R_}"
                    f"{C_GOLD}[E]{R_}{C_DIM}Enter  {R_}"
                    f"{C_GOLD}[I]{R_}{C_DIM}Bag  {R_}"
                    f"{C_GOLD}[F]{R_}{C_DIM}Fast  {R_}"
                    f"{C_GOLD}[O]{R_}{C_DIM}Overview  {R_}"
                    f"{C_GOLD}[J]{R_}{C_DIM}Journal  {R_}"
                    f"{C_GOLD}[N]{R_}{C_DIM}Party  {R_}"
                    f"{C_GOLD}[C]{R_}{C_DIM}Codex  {R_}"
                    f"{C_GOLD}[B]{R_}{C_DIM}Base  {R_}"
                    f"{C_GOLD}[P]{R_}{C_DIM}Save  {R_}"
                    f"{C_GOLD}[?]{R_}{C_DIM}Help  {R_}"
                    f"{C_GOLD}[Q]{R_}{C_DIM}Quit{R_}"))
        else:
            out.append(C(f"{mhint}{C_DIM}=move  {R_}"
                    f"{C_GOLD}[E]{R_}{C_DIM}Enter  {R_}"
                    f"{C_GOLD}[I]{R_}{C_DIM}Bag  {R_}"
                    f"{C_GOLD}[J]{R_}{C_DIM}Journal  {R_}"
                    f"{C_GOLD}[P]{R_}{C_DIM}Save  {R_}"
                    f"{C_GOLD}[?]{R_}{C_DIM}Help  {R_}"
                    f"{C_GOLD}[Q]{R_}{C_DIM}Quit{R_}"))

        draw_frame(out, C(f"{self.last_msg}  {C_GOLD}{B_}›{R_}"))

    def move_player(self,dx,dy,player):
        nx,ny=self.player_x+dx,self.player_y+dy
        if not(0<=nx<WIDTH and 0<=ny<HEIGHT):
            self.last_msg=f"{C_RED}Edge of the world.{R_}"; return
        ter=self.terrain[ny][nx]
        if ter in (OCEAN,SHALLOWS):
            self.last_msg=f"{C_BLUE}The sea blocks you. Find a port and board a ship.{R_}"; return
        self.player_x,self.player_y=nx,ny
        self.turn_count+=1; self._reveal(radius=6); player.tick_stealth()
        player.party.scale_all(player.level, turn=self.turn_count, world=self, player=player)
        # Tick god immunity
        if getattr(player,"god_immunity_turns",0) > 0:
            player.god_immunity_turns -= 1
            if player.god_immunity_turns == 0:
                self.last_msg = f"{C_GOLD}{T('world.immunity_fade')}{R_}"

        loc=self._loc_at(nx,ny)
        ship=next((s for s in self.ships if s["x"]==nx and s["y"]==ny),None)
        if loc:
            msgs={"city":f"{C_GOLD}{T('world.arrived_city', name=loc['name'])}{R_} {C_DIM}{T('world.enter_prompt')}{R_}",
                  "port":f"{C_TEAL}Port: {loc['name']}.{R_} {C_DIM}[E] to enter or board ship.{R_}",
                  "dungeon":f"{C_RED}Dungeon: {loc['name']}.{R_} {C_DIM}[E] to enter.{R_}",
                  "ruins":f"{C_PURP}Ruins: {loc['name']}.{R_} {C_DIM}[E] to explore.{R_}",
                  "mine":f"{C_ORAN}Mine: {loc['name']}.{R_} {C_DIM}[E] to enter and mine.{R_}",
                  "dragon_cave":f"{C_RED}{B_}★ DRAGON CAVE: {loc['name']}!{R_} {C_DIM}[E] to enter.{R_}"}
            if loc["type"] in ARRIVE_MSG:
                try: msgs[loc["type"]] = ARRIVE_MSG[loc["type"]](loc)
                except Exception: pass
            self.last_msg=msgs.get(loc["type"],f"{C_GOLD}{loc['name']}.{R_} {C_DIM}[E] to enter.{R_}")
            # story hooks
            completed=player.stories.on_visit(loc["name"],player)
            self._handle_story_completions(completed)
            # port side story trigger
            if loc["type"]=="port":
                sid=player.stories.on_port_visit(loc["name"],player)
                if sid:
                    from game_stories import SIDE_STORIES
                    s=SIDE_STORIES[sid]
                    self.last_msg+=f"  {s['colour']}[New side story: {s['title']}!]{R_}"
        elif ship:
            self.last_msg=f"{fg(255,255,180)}⚓ Ship docked — [E] to board.{R_}"
        else:
            cid=self.cont_map[ny][nx]
            cont=next((c for c in CONTINENTS if c["id"]==cid),None)
            cn=cont["name"] if cont else "Unknown"; ccol=cont["col"] if cont else C_WHITE
            tn={PLAINS:"Plains",FOREST:"Forest",MOUNTAIN:"Mountains",SNOW:"Snow",
                HILL:"Hills",ROAD:"Road",RIVER:"River",SAND:"Beach"}.get(ter,"")
            self.last_msg=f"{C_DIM}Travelling through {ccol}{cn}{R_} {C_DIM}— {tn}.{R_}"
            # Town visit story triggers
            unlocked=player.stories.on_town_visit(cn,player)
            if unlocked:
                from game_stories import SIDE_STORIES
                for sid in unlocked:
                    s=SIDE_STORIES[sid]
                    self.last_msg+=f"  {s['colour']}[New side story: {s['title']}!]{R_}"

        if self.turn_count % 25 == 0:
            self._respawn_enemies()

        for e in self.map_enemies[:]:
            if e.step(nx,ny,player.get_stealth(),self.terrain,WIDTH,HEIGHT):
                self._enemy_contact(e,player); return

        if loc or ship:
            return   # no ambushes on the doorstep of a town / dungeon
        enc=ENC_RATE.get(ter,0.0)
        # Interesting world events fire more often than combat
        if random.random() < 0.04:   # 4% chance per step of a discovery
            self._world_event(player,ter,self.cont_map[ny][nx])
        elif enc>0 and random.random()<enc:
            self._random_encounter(player,ter,self.cont_map[ny][nx])

    def _handle_story_completions(self,completed):
        from game_stories import show_story_completion
        for stype,step in completed:
            show_story_completion(stype,step)

    def _enemy_contact(self,map_enemy,player):
        # God potion immunity
        if getattr(player,"god_immunity_turns",0) > 0:
            self.last_msg=f"{C_PURP}★ Enemies sense your divine protection and back away.{R_}"
            map_enemy.calm(); return
        if player.try_stealth_evade():
            self.last_msg=(f"{C_PURP}You slip past the {map_enemy.name} undetected! "
                           f"{C_DIM}(hidden — your next attack is a sneak attack){R_}")
            map_enemy.calm(); return
        from game_enemies import generate_enemy
        from game_systems import run_combat
        enemy=generate_enemy(map_enemy.zone,map_enemy.danger,player.level,name=map_enemy.name)
        first_strike=player.in_stealth
        self.last_msg=f"{C_RED}!! {map_enemy.name} attacks!{R_}"
        self.render(player)
        import time; time.sleep(0.3)
        outcome=run_combat(player,enemy,first_strike=first_strike)
        if outcome=="defeat":
            map_enemy.calm()
            self._handle_defeat(player)
        elif outcome=="escaped":
            map_enemy.calm()
            self.last_msg=f"{C_DIM}You got away from the {map_enemy.name}.{R_}"
        else:
            if map_enemy in self.map_enemies:
                self.map_enemies.remove(map_enemy)
            self.last_msg=f"{C_GREEN}Defeated the {map_enemy.name}!{R_}"

    def _random_encounter(self,player,terrain,cid):
        # God potion immunity — skip all encounters
        if getattr(player,"god_immunity_turns",0) > 0:
            return
        from game_enemies import generate_enemy; from game_systems import run_combat
        cont=next((c for c in CONTINENTS if c["id"]==cid),None)
        zone=BIOME_ZONE.get(cont["biome"] if cont else "forest","plains")
        danger=DANGER_LVL.get(terrain,1) + (CONTINENT_DANGER.get(cid,1) - 1)
        enemy=generate_enemy(zone,danger,player.level)
        if player.try_stealth_evade():
            self.last_msg=f"{C_PURP}A {enemy.name} lurks nearby... you slip past unseen.{R_}"; return
        first_strike=player.in_stealth
        self.last_msg=f"{C_RED}!! A {enemy.name} appears!{R_}"
        self.render(player); import time; time.sleep(0.3)
        outcome=run_combat(player,enemy,first_strike=first_strike)
        if outcome=="defeat": self._handle_defeat(player)
        elif outcome=="escaped": self.last_msg=f"{C_DIM}You escaped the {enemy.name}.{R_}"
        else: self.last_msg=f"{C_GREEN}Defeated the {enemy.name}!{R_}"

    def _respawn_enemies(self):
        """Keep the world alive: top up roaming monsters far from the player."""
        if len(self.map_enemies) >= MIN_MAP_ENEMIES:
            return
        from game_map_enemies import spawn_world_enemies
        fresh = spawn_world_enemies(self.locations, self.terrain, WIDTH, HEIGHT,
                                    count=6, cont_map=self.cont_map)
        for e in fresh:
            if abs(e.x - self.player_x) + abs(e.y - self.player_y) > 25:
                self.map_enemies.append(e)

    def _world_event(self,player,terrain,cid):
        """Random positive/interesting discovery while exploring."""
        cont=next((c for c in CONTINENTS if c["id"]==cid),None)
        biome=cont["biome"] if cont else "forest"

        events=[
            ("hidden_chest",  0.25),
            ("ancient_shrine",0.15),
            ("wanderer",      0.12),
            ("herb_patch",    0.18),
            ("lost_cache",    0.10),
            ("nothing",       0.20),
        ]
        r=random.random(); cumul=0
        etype="nothing"
        for name,chance in events:
            cumul+=chance
            if r<=cumul: etype=name; break

        if etype=="nothing":
            return  # no message, stay silent

        if etype=="hidden_chest":
            gold=random.randint(20,80)
            player.gold+=gold
            from game_items import ITEM_POOL
            loot_fn=random.choice(list(ITEM_POOL.values()))
            loot=loot_fn()
            player.add_item(loot)
            self.last_msg=(f"{C_GOLD}★ Hidden chest! +{gold}g and {loot.name}!{R_}")
        elif etype=="ancient_shrine":
            choices=["HP","MP","STL"]
            pick=random.choice(choices)
            if pick=="HP":
                player.max_hp+=3; player.hp=min(player.hp+3,player.max_hp)
                self.last_msg=f"{C_CYAN}★ Ancient shrine blesses you. Max HP +3!{R_}"
            elif pick=="MP":
                player.max_mp+=3; player.mp=min(player.mp+3,player.max_mp)
                self.last_msg=f"{C_CYAN}★ Ancient shrine blesses you. Max MP +3!{R_}"
            else:
                player.stealth+=1
                self.last_msg=f"{C_PURP}★ Ancient shrine blesses you. Stealth +1!{R_}"
        elif etype=="wanderer":
            lines=[
                "A wandering monk offers you a blessing.",
                "An old hermit shares a map rumour.",
                "A wounded soldier gives you a potion.",
                "A street musician lifts your spirits — you feel refreshed.",
            ]
            msg=random.choice(lines)
            from game_items import ITEM_POOL
            gift=ITEM_POOL["Potion"]()
            player.add_item(gift)
            player.hp=min(player.max_hp,player.hp+20)
            player.mp=min(player.max_mp,player.mp+10)
            self.last_msg=f"{C_GREEN}★ {msg} +Potion, +20HP, +10MP{R_}"
        elif etype=="herb_patch":
            from game_items import ITEM_POOL
            qty=random.randint(1,3)
            for _ in range(qty):
                player.add_item(ITEM_POOL["Potion"]())
            self.last_msg=f"{C_GREEN}★ You spot wild herbs and gather {qty} Potion(s)!{R_}"
        elif etype=="lost_cache":
            gold=random.randint(40,150)
            player.gold+=gold
            self.last_msg=f"{C_GOLD}★ Lost adventurer's cache! +{gold}g!{R_}"

    def _handle_defeat(self,player):
        clear()
        print(C(f"\n{C_RED}{B_}You were defeated...{R_}\n"))
        if player.gold>0:
            lost=min(player.gold,max(5,player.gold//10))
            player.gold-=lost; print(C(f"{C_RED}Lost {lost} gold.{R_}"))
        player.hp=max(1,player.max_hp//3); player.mp=max(0,player.max_mp//3)
        player.status_effects.clear()
        player.god_immunity_turns=max(getattr(player,"god_immunity_turns",0),8)
        # Wake up in the nearest city on the SAME continent (it used to always
        # be the first city generated — possibly across the ocean)
        here=self.cont_map[self.player_y][self.player_x]
        cities=[l for l in self.locations if l["type"]=="city"]
        same=[l for l in cities if l.get("continent")==here] or cities
        if same:
            c=min(same,key=lambda l:abs(l["x"]-self.player_x)+abs(l["y"]-self.player_y))
            self.player_x,self.player_y=c["x"],c["y"]
            self._reveal(radius=6)
            print(C(f"{C_DIM}You wake up in {C_GOLD}{c['name']}{R_}{C_DIM}, bandaged and sore...{R_}"))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))
        self.last_msg=f"{C_DIM}You recover after defeat. Monsters keep their distance for a few steps.{R_}"

    def _after_adventure(self,player):
        """Common cleanup after any sub-location that can kill the player."""
        if not player.is_alive():
            self._handle_defeat(player)
            return True
        return False

    # ── ENTER LOCATION ───────────────────────────────────────────

    def enter_location(self,player,autosave=None):
        ship=next((s for s in self.ships if s["x"]==self.player_x and s["y"]==self.player_y),None)
        if ship: self._board_ship(player,ship); return
        loc=self._loc_at(self.player_x,self.player_y)
        if not loc:
            self.last_msg=f"{C_DIM}Nothing to enter here.{R_}"; return

        if loc["type"] in ENTER_HANDLERS:
            ENTER_HANDLERS[loc["type"]](self, player, loc, autosave)
            return

        if loc["type"] in ("city","port"):
            # Ports no longer ask "enter town / board ship" first: the ship is
            # docked in the walkable harbour (gangplank, captain, dockmaster).

            # story triggers
            completed=player.stories.on_visit(loc["name"],player)
            self._handle_story_completions(completed)
            unlocked=player.stories.on_town_visit(loc["name"],player)
            if unlocked:
                from game_stories import SIDE_STORIES
                for sid in unlocked:
                    s=SIDE_STORIES[sid]; clear()
                    print(C(f"\n{s['colour']}{B_}NEW SIDE STORY UNLOCKED: {s['title']}{R_}"))
                    print(C(f"\n{C_DIM}{s['intro']}{R_}"))
                    input(C(f"\n{C_DIM}(Press Enter){R_}"))
            # Walkable town (game_towns); [M] inside still opens the classic
            # menu, and run_town falls back to it if the scene can't be built.
            try:
                from game_towns import run_town, make_town
            except Exception as e:
                run_town=None
                try:
                    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"crash.log"),"a") as fh:
                        fh.write(f"game_towns import failed: {e!r}\n")
                except Exception:
                    pass
            if run_town is not None:
                town=make_town(self, player, loc, autosave)
                result=run_town(self, player, loc, autosave, town)
            else:
                from game_systems import Town
                from game_party import recruit_menu as town_recruitment_menu
                cont=next((c for c in CONTINENTS if c["id"]==loc.get("continent","")),None)
                town=Town(player,loc["name"],cont["name"] if cont else "")
                town.set_companion_callback(lambda: town_recruitment_menu(player,loc["name"]))
                town.set_base_info(loc.get("continent",""), loc["x"], loc["y"])
                town.set_world(self, autosave)
                _ship_ref=next((s for s in self.ships if s["port_name"]==loc["name"]),None)
                if loc["type"]=="port" and _ship_ref:
                    town.set_ship(self,_ship_ref,player)
                town.enter()
                result="left"
            if result=="left" and self._loc_at(self.player_x,self.player_y) is loc:
                self.last_msg=f"{C_GOLD}Left {loc['name']}.{R_}"

        elif loc["type"]=="dungeon":
            from game_dungeon import DungeonManager
            name=loc["name"]
            cleared=player.flags.get(f"dungeon_cleared_{name}",False)
            boss=None if cleared else DUNGEON_BOSSES.get(name,"Goblin King")
            danger=CONTINENT_DANGER.get(loc.get("continent",""),2)
            d=DungeonManager(name,danger=danger,boss_name=boss)
            result=d.enter(player)
            if result=="cleared":
                player.flags[f"dungeon_cleared_{name}"]=True
                if not cleared:   # first clear: a prisoner may be in the cells (game_party)
                    try:
                        from game_party import dungeon_prisoner_event; dungeon_prisoner_event(player,name,danger)
                    except Exception: pass
                completed=player.stories.on_dungeon_clear(name,player)
                self._handle_story_completions(completed)
                self.last_msg=f"{C_GOLD}★ {name} conquered!{R_}"
            elif not self._after_adventure(player):
                self.last_msg=f"{C_DIM}Left {name}.{R_}"

        elif loc["type"]=="mine":
            from game_mining import Mine
            # Entering any mine reveals the "Haunted Mine" side story
            if "haunted_mine" not in player.stories.side_stories:
                from game_stories import SIDE_STORIES
                player.stories.unlock_side("haunted_mine")
                s=SIDE_STORIES["haunted_mine"]; clear()
                print(C(f"\n{s['colour']}{B_}NEW SIDE STORY UNLOCKED: {s['title']}{R_}"))
                print(C(f"\n{C_DIM}{s['intro']}{R_}"))
                input(C(f"\n{C_DIM}(Press Enter){R_}"))
            m=Mine(loc["name"],loc["continent"],loc.get("biome","mountain"))
            gold=m.enter(player)
            if not self._after_adventure(player):
                self.last_msg=f"{C_ORAN}Left mine: {loc['name']}. Earned {gold}g.{R_}"

        elif loc["type"]=="dragon_cave":
            self._enter_dragon_cave(player,loc)
            self._after_adventure(player)

        elif loc["type"]=="ruins":
            self._explore_ruins(player,loc)
            self._after_adventure(player)

    def _enter_dragon_cave(self,player,loc):
        if not self.dragon_alive:
            clear(); print(C(f"\n{C_DIM}The cave is silent. Vaeltharion is dead.{R_}"))
            input(C(f"{C_DIM}(Press Enter){R_}"))
            # Slain before the story got this far: credit the step now,
            # otherwise "Slay Vaeltharion" could never complete.
            if player.flags.get("dragon_slain"):
                completed=player.stories.on_dungeon_clear("Vaeltharion",player)
                self._handle_story_completions(completed)
            return
        from game_dungeon import DungeonManager
        clear()
        print(C(f"\n{C_RED}{B_}╔══════════════════════════════════════════╗"))
        print(C(f"║  ★  VAELTHARION'S LAIR                   ║"))
        print(C(f"╚══════════════════════════════════════════╝{R_}\n"))
        print(C(f"{C_DIM}The stench of sulphur fills the air. The walls are scorched."))
        print(C(f"Claw marks the size of a man scar the stone."))
        print(C(f"Deep within, something breathes...{R_}\n"))
        print(C(f"{C_DIM}Four floors deep. A guardian blocks the final stairway, and the"))
        print(C(f"dragon itself waits at the bottom. Come prepared.{R_}\n"))
        print(C(f"{C_GOLD}[E]{R_}{C_DIM} Enter the cave{R_}"))
        print(C(f"{C_GOLD}[0]{R_}{C_DIM} Turn back{R_}"))
        ch=input(C(f"\n{C_GOLD}>{R_} ")).strip()
        if ch.lower()!="e": return
        d=DungeonManager("Vaeltharion's Lair",danger=5,boss_name="Dragon",floors=4)
        result=d.enter(player)
        if result=="cleared":
            self.dragon_alive=False
            player.flags["dragon_slain"]=True
            completed=player.stories.on_dungeon_clear("Vaeltharion",player)
            self._handle_story_completions(completed)
            self.last_msg=f"{C_GOLD}{B_}★ VAELTHARION IS SLAIN! The world is saved! ★{R_}"
        elif player.is_alive():
            self.last_msg=f"{C_DIM}You retreat from the dragon's lair.{R_}"

    def _explore_ruins(self,player,loc):
        clear(); print(C(f"\n{C_PURP}{B_}══ RUINS: {loc['name']} ══{R_}\n"))
        key=f"ruins_explored_{loc['name']}"
        if player.flags.get(key):
            print(C(f"{C_DIM}You have already picked these ruins clean. Only dust remains.{R_}"))
            input(C(f"\n{C_DIM}(Press Enter){R_}"))
            self.last_msg=f"{C_DIM}{loc['name']} — already explored.{R_}"
            return
        player.flags[key]=True
        from game_party import try_world_companion_event
        events=[
            (f"{C_GOLD}You find a hidden chest!{R_}","chest"),
            (f"{C_RED}Monsters lurk in the shadows!{R_}","fight"),
            (f"{C_CYAN}An ancient inscription — you feel stronger.{R_}","stat"),
            (f"{C_YELL}A mysterious stranger sits by a fire...{R_}","companion"),
        ]
        desc,etype=random.choice(events); print(C(desc)); print()
        if etype=="companion" and not player.party.members:
            etype="chest"
        if etype=="chest":
            gold=random.randint(40,160); player.gold+=gold
            from game_items import ITEM_POOL
            loot=random.choice(list(ITEM_POOL.values()))(); player.add_item(loot)
            print(C(f"{C_GOLD}Found {gold} gold{R_} and {C_WHITE}{loot}{R_}!"))
        elif etype=="fight":
            from game_enemies import generate_enemy; from game_systems import run_combat
            e=generate_enemy("dungeon",CONTINENT_DANGER.get(loc.get("continent",""),2),player.level)
            input(C(f"{C_DIM}(Press Enter to fight){R_}"))
            outcome=run_combat(player,e)
            if outcome=="defeat":
                return
            if outcome=="escaped":
                player.flags.pop(key,None)   # the stash is still there
                self.last_msg=f"{C_DIM}You fled the ruins of {loc['name']}.{R_}"
                return
            clear()
            gold=random.randint(30,90); player.gold+=gold
            print(C(f"{C_GOLD}Behind the {e.name} you find a stash: +{gold} gold.{R_}"))
        elif etype=="stat":
            player.max_hp+=5; player.hp=min(player.hp+5,player.max_hp)
            print(C(f"{C_GREEN}Max HP +5!{R_}"))
        elif etype=="companion":
            try_world_companion_event(player,"ruins_event")
        input(C(f"\n{C_DIM}(Press Enter){R_}"))
        self.last_msg=f"{C_PURP}Explored ruins: {loc['name']}.{R_}"

    # ── SHIP TRAVEL ──────────────────────────────────────────────

    def _board_ship(self,player,ship):
        clear()
        print(C(f"\n{fg(255,255,180)}{B_}╔══════════════════════════════════════╗"))
        print(C(f"║  ⚓  SHIP: {ship['port_name']:<27}║"))
        print(C(f"╚══════════════════════════════════════╝{R_}\n"))
        other=[l for l in self.locations if l["type"]=="port"
               and not(l["x"]==ship["port_x"] and l["y"]==ship["port_y"])]
        for i,port in enumerate(other,1):
            dist=math.sqrt((ship["port_x"]-port["x"])**2+(ship["port_y"]-port["y"])**2)
            cost=max(10,int(dist*0.5))
            cont=next((c for c in CONTINENTS if c["id"]==port.get("continent","")),None)
            ccol=cont["col"] if cont else C_WHITE; cname=cont["name"] if cont else "?"
            aff=C_WHITE if player.gold>=cost else C_DIM
            print(C(f"{C_GOLD}{B_}[{i}]{R_} {aff}{port['name']:<22}{R_}  {ccol}{cname:<16}{R_}  {C_GOLD}{cost}g{R_}  {C_DIM}({dist:.0f}L){R_}"))
        print(C(f"\n{C_GOLD}[0]{R_}{C_DIM} Stay  Gold: {C_GOLD}{player.gold}{R_}\n"))
        ch=input(C(f"{C_GOLD}>{R_} Choose destination: ")).strip()
        if ch=="0" or not ch.isdigit(): return False
        idx=int(ch)-1
        if not(0<=idx<len(other)): return False
        dest=other[idx]
        dist=math.sqrt((ship["port_x"]-dest["x"])**2+(ship["port_y"]-dest["y"])**2)
        cost=max(10,int(dist*0.5))
        if player.gold<cost:
            print(C(f"\n{C_RED}Need {cost}g.{R_}")); input(C(f"{C_DIM}(Enter){R_}")); return False
        player.gold-=cost; clear()
        print(C(f"\n{fg(255,255,180)}{B_}Setting sail for {dest['name']}...{R_}\n"))
        voyage=["  The anchor is raised. Sails fill with wind.",
                "  Seabirds cry as the coast fades behind you.",
                "  Stars guide your path through the night.",
                "  A pod of dolphins races alongside the hull.",
                "  The open ocean stretches endlessly around you."]
        for l in random.sample(voyage,3): print(C(f"{C_DIM}{l.strip()}{R_}"))
        if dist>40 and random.random()<0.2:
            dmg=random.randint(15,40); player.hp=max(1,player.hp-dmg)
            lost=random.randint(10,30); player.gold=max(0,player.gold-lost)
            print(C(f"\n{C_RED}!! STORM! {dmg} damage, {lost} gold lost!{R_}"))
        else: print(C(f"\n{C_GREEN}Fair winds!{R_}"))
        # Land ON the port tile (the tile above it was often open water)
        self.player_x=dest["x"]; self.player_y=dest["y"]; self._reveal(radius=8)
        cont=next((c for c in CONTINENTS if c["id"]==dest.get("continent","")),None)
        print(C(f"\n{C_GOLD}Arrived at {dest['name']}, {cont['name'] if cont else '?'}.{R_}"))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))
        self.last_msg=f"{C_GOLD}{T('ship.arrived', dest=dest['name'])}{R_}"
        completed=player.stories.on_visit(dest["name"],player)
        self._handle_story_completions(completed)
        sid=player.stories.on_port_visit(dest["name"],player)
        if sid:
            from game_stories import SIDE_STORIES
            self.last_msg+=f"  {SIDE_STORIES[sid]['colour']}[New side story: {SIDE_STORIES[sid]['title']}!]{R_}"
        return True

    # ── FAST TRAVEL, OVERVIEW, LOCATIONS, HELP ───────────────────

    def fast_travel(self,player):
        cities=[l for l in self.locations if l["type"] in ("city","port")]
        clear(); print(C(f"\n{C_CYAN}{B_}══════  FAST TRAVEL  ══════{R_}\n"))
        print(C(f"{C_DIM}Gold: {C_GOLD}{player.gold}{R_}  {C_DIM}(same continent only — use ships for others){R_}\n"))
        my_cont=self.cont_map[self.player_y][self.player_x]
        same=[l for l in cities if l.get("continent")==my_cont]
        other=[l for l in cities if l.get("continent")!=my_cont]
        def show(lst,hdr):
            if not lst: return
            print(C(f"{C_CYAN}{hdr}{R_}"))
            for i,loc in enumerate(lst,1):
                dist=abs(self.player_x-loc["x"])+abs(self.player_y-loc["y"])
                cost=max(0,dist//8)
                cont=next((c for c in CONTINENTS if c["id"]==loc.get("continent","")),None)
                ccol=cont["col"] if cont else C_WHITE
                here=""
                if loc["x"]==self.player_x and loc["y"]==self.player_y: here=f"  {C_DIM}← here{R_}"
                note=f"{C_GOLD}{cost}g{R_}" if loc.get("continent")==my_cont else f"{C_DIM}(use ship){R_}"
                print(C(f"{C_GOLD}{B_}[{i}]{R_} {paint(loc['icon'])} {C_WHITE}{loc['name']:<20}{R_}  "
                        f"{ccol}{(cont['name'] if cont else '?'):<16}{R_}  {note}{here}" ))
        show(same,"── Same Continent ───────────────────────")
        show(other,"── Other Continents (board a ship) ─────")
        all_list=same+other
        print(C(f"\n{C_GOLD}[0]{R_}{C_DIM} Cancel{R_}"))
        print(C(f"\n{C_GOLD}>{R_} "),end="",flush=True); ch=input().strip()
        if ch=="0" or not ch.isdigit(): return
        idx=int(ch)-1
        if not(0<=idx<len(all_list)): return
        dest=all_list[idx]
        if dest.get("continent")!=my_cont:
            print(C(f"\n{C_RED}Board a ship to reach {dest['name']}.{R_}"))
            input(C(f"{C_DIM}(Enter){R_}")); return
        dist=abs(self.player_x-dest["x"])+abs(self.player_y-dest["y"])
        cost=max(0,dist//8)
        if cost>0:
            if player.gold<cost: self.last_msg=f"{C_RED}Need {cost}g.{R_}"; return
            player.gold-=cost
        self.player_x=dest["x"]; self.player_y=dest["y"]; self._reveal()
        self.last_msg=f"{C_GOLD}{T('ship.arrived', dest=dest['name'])}{R_}"

    def show_overview(self):
        import shutil
        sz=shutil.get_terminal_size(fallback=(80,24)); cols,rows=sz.columns,sz.lines
        clear(); SCALE=4; ow=min(WIDTH//SCALE, (cols-4))//1; oh=min(HEIGHT//SCALE, rows-12)
        print(C(f"\n{C_CYAN}{B_}══════  WORLD OVERVIEW  ══════{R_}\n"))
        _ov_pad = " " * max(0,(cols-ow)//2)
        for oy in range(oh):
            line=_ov_pad
            for ox in range(ow):
                x=ox*SCALE+SCALE//2; y=oy*SCALE+SCALE//2
                if not(0<=x<WIDTH and 0<=y<HEIGHT): line+=" "; continue
                if abs(x-self.player_x)<=SCALE//2 and abs(y-self.player_y)<=SCALE//2:
                    line+=f"{fg(255,60,60)}{B_}@{R_}"; continue
                ch=self.terrain[y][x]
                sym={OCEAN:"~",SHALLOWS:"~",PLAINS:".",FOREST:"f",MOUNTAIN:"^",
                     SNOW:"*",HILL:",",ROAD:"-",RIVER:"/",SAND:":","P":"P","H":"H",
                     "X":"X","R":"R",MINE_T:"M",DRAGON_T:"V"}.get(ch, TILE[ch][1] if ch in TILE_NAMES else ".")
                col_,_=TILE.get(ch,("",ch)); line+=f"{col_}{sym}{R_}"
            print(line)
        print(C(f"\n{C_CYAN}{B_}CONTINENTS{R_}"))  # overview
        for cid,rx,ry in sorted(self.cont_labels):
            cont=next((c for c in CONTINENTS if c["id"]==cid),None)
            if cont: print(C(f"{cont['col']}{B_}{cont['name']:<18}{R_}  {C_DIM}~({rx},{ry}){R_}"))
        print(C(f"\n{C_CYAN}{B_}DISCOVERED{R_}"))
        disc=[l for l in self.locations if self.discovered[l["y"]][l["x"]]]
        if not disc: print(C(f"{C_DIM}Explore to discover!{R_}"))
        for l in disc:
            cont=next((c for c in CONTINENTS if c["id"]==l.get("continent","")),None)
            ccol=cont["col"] if cont else C_WHITE
            print(C(f"  {paint(l['icon'])}  {C_WHITE}{l['name']:<22}{R_}  {ccol}{(cont['name'] if cont else '?'):<16}{R_}  {C_DIM}{l['type']}{R_}"))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))

    def show_locations(self):
        clear(); print(C(f"\n{C_CYAN}{B_}══════  DISCOVERED LOCATIONS  ══════{R_}\n"))
        disc=[l for l in self.locations if self.discovered[l["y"]][l["x"]]]
        if not disc: print(C(f"{C_DIM}None yet.{R_}"))
        for l in disc:
            cont=next((c for c in CONTINENTS if c["id"]==l.get("continent","")),None)
            ccol=cont["col"] if cont else C_WHITE
            print(C(f"{paint(l['icon'])}  {C_WHITE}{l['name']:<22}{R_}  "
                    f"{ccol}{(cont['name'] if cont else '?'):<16}{R_}  {C_DIM}{l['type']}{R_}"))
        input(C(f"\n{C_DIM}(Press Enter){R_}"))

    def show_help(self):
        clear()
        lines_h = [
            f"{C_CYAN}{B_}══════  TERMINAL-RPG — HELP  ══════{R_}",
            "",
            f"{C_GOLD}WASD{R_} / {C_GOLD}Numpad 1-9{R_} / {C_GOLD}Arrow keys{R_} — Move (set at character creation)",
            "",
            f"{C_GOLD}[E]{R_}  Enter city/dungeon/mine/ruins/dragon cave — board ship",
            f"{C_GOLD}[I]{R_}  Quick bag — use potions, equip gear while walking",
            f"{C_GOLD}[F]{R_}  Fast travel (same continent)",
            f"{C_GOLD}[O]{R_}  World overview + continent names",
            f"{C_GOLD}[J]{R_}  Story journal",
            f"{C_GOLD}[C]{R_}  Encyclopedia — enemies, shops, crafting guide",
            f"{C_GOLD}[B]{R_}  Build base / enter existing base",
            f"{C_GOLD}[N]{R_}  Party & clan management",
            f"{C_GOLD}[M]{R_}  Discovered locations list",
            f"{C_GOLD}[P]{R_}  Save game",
            f"{C_GOLD}[?]{R_}  This help screen",
            f"{C_GOLD}[Q]{R_}  Quit / save prompt",
            "",
            f"{C_CYAN}{B_}MAP LEGEND{R_}",
            f"{paint('@')} You   {paint('P')} City   {paint('H')} Port   {paint('S')} Ship",
            f"{paint('X')} Dungeon   {paint('R')} Ruins   {paint('M')} Mine   {paint('V')} Dragon Cave",
            f"{paint('.')} Plains   {paint('T')} Forest   {paint('^')} Mountain   {paint('*')} Snow",
            f"{paint(',')} Hills   {paint(':')} Beach   {paint('~')} Ocean   {paint('=')} Road",
            "",
            f"{C_CYAN}{B_}KEY SYSTEMS{R_}",
            f"{C_ORAN}Mines [M]{R_}  — Enter to mine ore and gold. Watch for cave-ins!",
            f"{C_RED}Dragon Cave [V]{R_}  — Hidden in the highest Iron Peaks. Slay Vaeltharion.",
            f"{C_TEAL}Ships [S]{R_}  — Board at ports to sail between continents.",
            f"{C_PURP}Stealth{R_}  — Higher STL shrinks enemy sight, enables sneak attacks.",
            f"{C_CYAN}Party{R_}  — Recruit companions in towns. They fight and give passive bonuses.",
            f"{C_GOLD}Stories{R_}  — Pick main story at start. Side stories found by exploring.",
        ]
        print()
        for l in lines_h: print(C(l))
        print()
        input(C(f"{C_DIM}(Press Enter){R_}"))

    # ── HELPERS ──────────────────────────────────────────────────

    def _loc_at(self,x,y):
        for l in self.locations:
            if l["x"]==x and l["y"]==y: return l
        return None

    def _is_base_tile(self,x,y):
        """True if a player base sits on this tile (shown as 'b' on map)."""
        # Requires player context — checked lazily in render_with_player
        return getattr(self,"_base_positions",set()).__contains__((x,y))

    def update_base_positions(self,player):
        """Pre-compute base tile positions for this frame."""
        self._base_positions={
            (b.x,b.y) for b in player.bases.bases.values()
        }

    # ── SAVE / LOAD ──────────────────────────────────────────────

    def to_dict(self):
        return {"seed":self.seed,"player_x":self.player_x,"player_y":self.player_y,
                "discovered":self.discovered,"turn_count":self.turn_count,
                "dragon_alive":self.dragon_alive,
                "map_enemies":[e.to_dict() for e in self.map_enemies]}

    def save(self,filename=SAVE_FILE):
        with open(filename,"w",encoding="utf-8") as f: json.dump(self.to_dict(),f)

    @classmethod
    def load(cls,filename=SAVE_FILE):
        with open(filename,"r",encoding="utf-8") as f: d=json.load(f)
        w=cls(seed=d["seed"])
        w.player_x=d["player_x"]; w.player_y=d["player_y"]
        w.discovered=d["discovered"]; w.turn_count=d["turn_count"]
        w.dragon_alive=d.get("dragon_alive",True)
        from game_map_enemies import MapEnemy
        w.map_enemies=[MapEnemy.from_dict(e) for e in d.get("map_enemies",[])]
        return w
