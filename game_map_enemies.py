"""
map_enemies.py
World-map enemy entities: patrol paths, sight cones, chase AI.
Separate from combat enemies — these are the overworld sprites.
"""

import random, math

# ── Colour helpers (inline, same palette) ───────────────────────
_R = "\033[0m"; _B = "\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"

# Enemy type definitions: (display_char, colour, zone, base_detection, base_stealth, danger)
MAP_ENEMY_TYPES = {
    # name:          (char, colour_rgb,        zone,       detect, stealth, danger)
    "Goblin":        ("g", (180,220,60),       "plains",   4,      3,       1),
    "Wolf":          ("w", (160,120,80),       "forest",   5,      5,       2),
    "Bandit":        ("B", (200,80,60),        "plains",   4,      6,       2),
    "Skeleton":      ("s", (210,210,180),      "dungeon",  3,      2,       2),
    "Harpy":         ("h", (220,120,200),      "mountain", 6,      4,       3),
    "Stone Golem":   ("G", (140,140,120),      "mountain", 3,      1,       3),
    "Sand Wyrm":     ("W", (220,180,60),       "desert",   5,      3,       4),
    "Ice Wolf":      ("i", (180,220,255),      "snow",     5,      6,       3),
    "Shadow Beast":  ("S", (120,60,160),       "dungeon",  7,      8,       5),
    "Frost Wraith":  ("F", (160,200,255),      "snow",     6,      7,       4),
    "Cultist":       ("c", (160,60,160),       "dungeon",  5,      6,       3),
    "Desert Raider": ("r", (200,140,60),       "desert",   5,      5,       3),
}

ZONE_ENEMY_POOL = {
    "plains":   ["Goblin","Goblin","Bandit","Wolf"],
    "forest":   ["Wolf","Wolf","Bandit","Harpy"],
    "mountain": ["Stone Golem","Harpy","Stone Golem"],
    "desert":   ["Sand Wyrm","Desert Raider","Sand Wyrm"],
    "snow":     ["Ice Wolf","Frost Wraith","Ice Wolf"],
    "dungeon":  ["Skeleton","Cultist","Shadow Beast"],
}

TERRAIN_ZONE = {
    ".": "plains", "T": "forest", "^": "mountain",
    "*": "snow",   ",": "plains", "/": "plains", "=": "plains",
}
# Sand (":") is beach on most continents; on the Ash Sands it is real desert.
# (The old table looked for a "D" tile that never exists, so desert
#  monsters never spawned on the map.)
DESERT_CONTINENT = "D"


class MapEnemy:
    """An enemy visible and moving on the world map."""

    def __init__(self, name, x, y, patrol_points):
        self.name = name
        self.x    = x
        self.y    = y

        info = MAP_ENEMY_TYPES.get(name, ("?", (200,60,60), "plains", 4, 3, 1))
        self.char         = info[0]
        self.colour       = info[1]
        self.zone         = info[2]
        self.base_detect  = info[3]   # base sight range in tiles
        self.base_stealth = info[4]   # sneakiness of the enemy itself
        self.danger       = info[5]

        self.patrol_points = patrol_points   # list of (x,y) waypoints
        self.patrol_idx    = 0
        self.chasing       = False
        self.chase_target  = None   # (px, py) last known player pos
        self.level         = max(1, self.danger + random.randint(0,2))
        self.alert_cooldown= 0      # turns to keep chasing after losing sight
        self.calm_turns    = 0      # turns it ignores the player (after you escape/evade it)

    def calm(self, turns=6):
        """Stop chasing and leave the player alone for a few turns.
        Without this, an enemy you fled from or slipped past stayed adjacent
        and re-triggered a fight on your very next step."""
        self.chasing = False
        self.chase_target = None
        self.alert_cooldown = 0
        self.calm_turns = turns

    @property
    def display(self):
        r,g,b = self.colour
        if self.chasing:
            # Flash red when chasing
            return f"\033[38;2;255;60;60m{_B}{self.char.upper()}{_R}"
        return f"\033[38;2;{r};{g};{b}m{self.char}{_R}"

    def detection_range(self, player_stealth):
        """Effective sight range after player stealth reduces it."""
        raw = self.base_detect + self.level // 2
        # Each point of player stealth above 5 reduces detection by 0.5 tiles
        reduction = max(0, (player_stealth - 5) * 0.5)
        return max(1, raw - reduction)

    def can_see_player(self, px, py, player_stealth):
        dist = math.sqrt((self.x - px)**2 + (self.y - py)**2)
        return dist <= self.detection_range(player_stealth)

    def step(self, px, py, player_stealth, terrain_grid, width, height):
        """
        Called once per player move.
        Returns True if the enemy is now adjacent to the player (triggers encounter).
        """
        if self.calm_turns > 0:
            self.calm_turns -= 1
            self._patrol(terrain_grid, width, height)
            return False
        if self.can_see_player(px, py, player_stealth):
            self.chasing = True
            self.chase_target = (px, py)
            self.alert_cooldown = 4
        elif self.chasing:
            self.alert_cooldown -= 1
            if self.alert_cooldown <= 0:
                self.chasing = False
                self.chase_target = None

        if self.chasing and self.chase_target:
            tx, ty = self.chase_target
            self._move_toward(tx, ty, terrain_grid, width, height)
            # Update to actual player pos if still visible
            if self.can_see_player(px, py, player_stealth):
                self.chase_target = (px, py)
        else:
            self._patrol(terrain_grid, width, height)

        # Check adjacency (Chebyshev distance 1)
        return max(abs(self.x - px), abs(self.y - py)) <= 1

    def _move_toward(self, tx, ty, terrain, width, height):
        dx = 0 if tx == self.x else (1 if tx > self.x else -1)
        dy = 0 if ty == self.y else (1 if ty > self.y else -1)
        # Try direct, then axis-only fallbacks
        for (ddx, ddy) in [(dx,dy),(dx,0),(0,dy)]:
            nx, ny = self.x+ddx, self.y+ddy
            if self._walkable(nx, ny, terrain, width, height):
                self.x, self.y = nx, ny
                return True
        return False

    def _patrol(self, terrain, width, height):
        if not self.patrol_points:
            return
        tx, ty = self.patrol_points[self.patrol_idx]
        if self.x == tx and self.y == ty:
            self.patrol_idx = (self.patrol_idx + 1) % len(self.patrol_points)
            return
        if not self._move_toward(tx, ty, terrain, width, height):
            # Blocked (water, a town...): head for the next waypoint instead
            # of standing still forever.
            self.patrol_idx = (self.patrol_idx + 1) % len(self.patrol_points)

    def _walkable(self, x, y, terrain, width, height):
        if not (0 <= x < width and 0 <= y < height):
            return False
        # Ocean, shallows and location tiles (towns, dungeons...) are off-limits
        return terrain[y][x] not in ("~", ";", "#", "P", "H", "X", "R", "M", "V")

    def to_dict(self):
        return {
            "name": self.name, "x": self.x, "y": self.y,
            "patrol_points": self.patrol_points,
            "patrol_idx": self.patrol_idx,
            "chasing": self.chasing,
            "chase_target": self.chase_target,
            "alert_cooldown": self.alert_cooldown,
            "level": self.level,
            "calm_turns": self.calm_turns,
        }

    @classmethod
    def from_dict(cls, d):
        e = cls(d["name"], d["x"], d["y"], d["patrol_points"])
        e.patrol_idx    = d.get("patrol_idx", 0)
        e.chasing       = d.get("chasing", False)
        e.chase_target  = d.get("chase_target")
        e.alert_cooldown= d.get("alert_cooldown", 0)
        e.level         = d.get("level", 1)
        e.calm_turns    = d.get("calm_turns", 0)
        return e


def spawn_world_enemies(locations, terrain, width, height, count=18, cont_map=None):
    """
    Populate the world map with patrolling enemies.
    Avoids spawning on or right next to towns and other locations.
    """
    loc_positions = {(l["x"], l["y"]) for l in locations}

    # Collect walkable non-location land tiles grouped by zone
    zone_tiles = {}
    for y in range(height):
        for x in range(width):
            ch = terrain[y][x]
            if any((x+dx, y+dy) in loc_positions for dx in (-1,0,1) for dy in (-1,0,1)):
                continue
            zone = TERRAIN_ZONE.get(ch)
            if ch == ":" and cont_map is not None and cont_map[y][x] == DESERT_CONTINENT:
                zone = "desert"
            if zone:
                zone_tiles.setdefault(zone, []).append((x,y))

    enemies = []
    for _ in range(count):
        # Pick a zone that has tiles
        available_zones = [z for z in zone_tiles if zone_tiles[z]]
        if not available_zones:
            break
        zone = random.choice(available_zones)
        tiles = zone_tiles[zone]
        if not tiles:
            continue

        # Pick spawn point
        cx, cy = random.choice(tiles)
        # Don't stack enemies
        if any(abs(e.x-cx) < 2 and abs(e.y-cy) < 2 for e in enemies):
            continue

        # Pick enemy type for zone
        pool = ZONE_ENEMY_POOL.get(zone, ["Goblin"])
        name = random.choice(pool)

        # Build a short patrol path (2–4 waypoints near spawn)
        patrol = [(cx, cy)]
        for _ in range(random.randint(1, 3)):
            px = cx + random.randint(-4, 4)
            py = cy + random.randint(-3, 3)
            px = max(1, min(width-2, px))
            py = max(1, min(height-2, py))
            if (terrain[py][px] not in ("~", ";")
                    and (px, py) not in loc_positions):
                patrol.append((px, py))

        enemies.append(MapEnemy(name, cx, cy, patrol))

    return enemies
