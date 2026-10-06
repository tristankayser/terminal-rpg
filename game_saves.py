"""
game_saves.py — Multi-slot save system with autosave for Terminal-RPG.

Features:
  • 5 save slots (slot 1–5)
  • Autosave slot (slot 0) — triggers automatically on map move, enter, rest
  • Each slot stores: player data + world data + metadata (name, level, job,
    location, playtime, timestamp)
  • Save browser with slot previews
  • Delete slot
  • Autosave interval configurable (default: every 30 actions)
"""

from __future__ import annotations

import os
import json
import time
import datetime

# ── Directory & file naming ──────────────────────────────────────
# Anchored to the game folder, so launching from another working directory
# doesn't make your saves "disappear".
GAME_DIR      = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR      = os.path.join(GAME_DIR, "saves")
MAX_SLOTS     = 5
AUTOSAVE_SLOT = 0          # slot 0 is always autosave

def _ensure_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)

def _write_json_atomic(path, data, **kw):
    """Write to a temp file then rename — a crash mid-save can't corrupt a slot."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, **kw)
    os.replace(tmp, path)

def _player_path(slot: int) -> str:
    return os.path.join(SAVE_DIR, f"slot{slot}_player.json")

def _world_path(slot: int) -> str:
    return os.path.join(SAVE_DIR, f"slot{slot}_world.json")

def _meta_path(slot: int) -> str:
    return os.path.join(SAVE_DIR, f"slot{slot}_meta.json")


# ── Metadata helpers ─────────────────────────────────────────────

def _make_meta(player, slot: int, playtime_seconds: int = 0) -> dict:
    return {
        "slot":       slot,
        "name":       player.name,
        "level":      player.level,
        "job":        player.job.name,
        "location":   getattr(player, "location_name", "Unknown"),
        "gold":       player.gold,
        "playtime":   playtime_seconds,
        "timestamp":  time.time(),
        "datetime":   datetime.datetime.now().strftime("%Y-%m-%d  %H:%M"),
        "autosave":   slot == AUTOSAVE_SLOT,
    }

def _load_meta(slot: int) -> dict | None:
    p = _meta_path(slot)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def slot_exists(slot: int) -> bool:
    return (os.path.exists(_player_path(slot)) and
            os.path.exists(_world_path(slot)))


# ── Core save / load ─────────────────────────────────────────────

def save_slot(slot: int, player, world, playtime_seconds: int = 0) -> bool:
    """Save player + world to a slot. Returns True on success."""
    _ensure_dir()
    try:
        # Serialise everything first, so a failure can't leave half a slot
        pdata = player.to_dict()
        wdata = world.to_dict()
        meta  = _make_meta(player, slot, playtime_seconds)
        _write_json_atomic(_player_path(slot), pdata, indent=2)
        _write_json_atomic(_world_path(slot), wdata)
        _write_json_atomic(_meta_path(slot), meta, indent=2)
        return True
    except Exception as e:
        from game_term import C
        print(C(f"[Save error] slot {slot}: {e}"))
        return False


def load_slot(slot: int):
    """
    Load player + world from slot.
    Returns (player, world) or raises Exception.
    """
    from game_player import Player
    from game_world import WorldMap

    if not slot_exists(slot):
        raise FileNotFoundError(f"Slot {slot} is empty.")

    with open(_player_path(slot), encoding="utf-8") as f:
        player = Player.from_dict(json.load(f))

    # WorldMap uses .load(filename) classmethod
    world = WorldMap.load(_world_path(slot))

    return player, world


def delete_slot(slot: int) -> bool:
    """Delete all files for a slot. Returns True if anything was deleted."""
    deleted = False
    for path in [_player_path(slot), _world_path(slot), _meta_path(slot)]:
        if os.path.exists(path):
            os.remove(path)
            deleted = True
    return deleted


def migrate_legacy_saves():
    """
    One-time migration: if old savegame.json / world_save.json exist,
    move them into slot 1 automatically.
    """
    old_player = os.path.join(GAME_DIR, "savegame.json")
    old_world  = os.path.join(GAME_DIR, "world_save.json")
    if not (os.path.exists(old_player) and os.path.exists(old_world)):
        return False
    if slot_exists(1):
        return False   # slot 1 already occupied — don't overwrite
    _ensure_dir()
    import shutil
    try:
        shutil.copy2(old_player, _player_path(1))
        shutil.copy2(old_world,  _world_path(1))
        # Build basic meta from player file
        with open(old_player, encoding="utf-8") as f:
            pd = json.load(f)
        meta = {
            "slot": 1, "name": pd.get("name","?"),
            "level": pd.get("level",1), "job": pd.get("job","?"),
            "location": pd.get("location_name","?"),
            "gold": pd.get("gold",0), "playtime": 0,
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().strftime("%Y-%m-%d  %H:%M"),
            "autosave": False,
        }
        with open(_meta_path(1), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        # Rename old files so migration doesn't repeat
        os.rename(old_player, old_player + ".bak")
        os.rename(old_world,  old_world  + ".bak")
        return True
    except Exception as e:
        print(f"  [Migration warning] {e}")
        return False


# ── Autosave manager ─────────────────────────────────────────────

class AutoSave:
    """
    Tracks action count and triggers autosave every N actions.
    Usage:
        autosave = AutoSave(interval=30)
        autosave.tick(player, world)   # call after each player action
    """
    def __init__(self, interval: int = 30, base_playtime: int = 0):
        self.interval       = interval
        self._action_count  = 0
        self._playtime_start = time.time()
        self._base_playtime  = base_playtime   # playtime carried over from the save
        self._last_save_time = 0.0

    def playtime(self) -> int:
        """Total play time in seconds (this session + loaded save)."""
        return self._base_playtime + int(time.time() - self._playtime_start)

    def tick(self, player, world) -> bool:
        """
        Increment action counter. If interval reached, autosave.
        Returns True if an autosave was performed.
        """
        self._action_count += 1
        if self._action_count >= self.interval:
            self._action_count = 0
            ok = save_slot(AUTOSAVE_SLOT, player, world, self.playtime())
            if ok:
                self._last_save_time = time.time()
            return ok
        return False

    def force(self, player, world) -> bool:
        """Force an immediate autosave (e.g. on quit, sleep, dungeon exit)."""
        self._action_count = 0
        return save_slot(AUTOSAVE_SLOT, player, world, self.playtime())


# ── Save browser UI ──────────────────────────────────────────────

_R = "\033[0m"; _B = "\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD  = _fg(255,215,0);  _WHITE = _fg(255,255,255)
_DIM   = _fg(100,100,100); _GREEN = _fg(80,200,80)
_RED   = _fg(220,60,60);   _CYAN  = _fg(80,220,220)
_YELL  = _fg(240,200,60);  _ORAN  = _fg(220,140,40)


def _fmt_playtime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    if m < 60:
        return f"{m}m"
    return f"{m//60}h {m%60:02d}m"


def _slot_label(slot: int) -> str:
    return f"{_YELL}AUTO{_R}" if slot == AUTOSAVE_SLOT else f"Slot {slot}"


def _draw_slot(slot: int, highlight: bool = False) -> list[str]:
    """Return lines describing a slot for the browser."""
    meta = _load_meta(slot)
    border_col = _GOLD if highlight else _DIM
    lines = []
    w = 52

    from game_term import _vis

    def row(content):
        # Pad by VISIBLE width so the right border always lines up
        pad = max(0, w - _vis(content))
        return f"{border_col}│{_R}{content}{' '*pad}{border_col}│{_R}"

    num = f"{_GOLD}{_B}[{slot}]{_R} "
    lines.append(f"{border_col}┌{'─'*w}┐{_R}")
    if meta:
        auto_tag = f"  {_YELL}[AUTOSAVE]{_R}" if meta.get("autosave") else ""
        lines.append(row(f" {num}{_B}{_slot_label(slot)}{_R}{auto_tag}"))
        lines.append(row(f"  {_WHITE}{_B}{str(meta['name'])[:14]:<14}{_R}  Lv {_GREEN}{meta['level']:<3}{_R}  {_CYAN}{str(meta['job'])[:16]:<16}{_R}"))
        lines.append(row(f"  {_DIM}{str(meta['location'])[:26]:<26}  Played {_fmt_playtime(meta.get('playtime',0)):<8}{_R}"))
        lines.append(row(f"  {_DIM}{meta['datetime']:<20}  {_GOLD}{meta.get('gold',0)}g{_R}"))
    else:
        lines.append(row(f" {num}{_B}{_slot_label(slot)}{_R}"))
        lines.append(row(f"  {_DIM}— Empty —{_R}"))
    lines.append(f"{border_col}└{'─'*w}┘{_R}")
    return lines


def latest_slot():
    """Slot number of the most recent save, or None."""
    best = None
    for s in range(0, MAX_SLOTS + 1):
        m = _load_meta(s)
        if m and slot_exists(s) and (best is None or m.get("timestamp", 0) > best[1]):
            best = (s, m.get("timestamp", 0))
    return best[0] if best else None


def save_browser(mode: str = "load", current_player=None, current_world=None,
                 autosave: "AutoSave | None" = None):
    """
    Interactive save slot browser.

    mode:
      'load'  — pick a slot to load (returns (player, world) or None)
      'save'  — pick a slot to save into (returns slot number or None)
    """
    from game_term import C, clr

    slots = list(range(0, MAX_SLOTS + 1))   # 0=auto, 1-5=manual

    while True:
        clr()
        title = "LOAD GAME" if mode == "load" else "SAVE GAME"
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════════════════╗"))
        print(C(f"║  💾  {title:<48}║"))
        print(C(f"╚══════════════════════════════════════════════════════╝{_R}\n"))

        for slot in slots:
            for line in _draw_slot(slot):
                print(C(line))
            print()

        print(C(f"{_DIM}{'─'*54}{_R}"))

        if mode == "load":
            print(C(f"  {_GOLD}[0-5]{_R} Load slot   {_GOLD}[D]{_R} Delete slot   {_GOLD}[Q]{_R} Back"))
        else:
            print(C(f"  {_GOLD}[1-5]{_R} Save to slot   {_GOLD}[D]{_R} Delete slot   {_GOLD}[Q]{_R} Back"))
            print(C(f"  {_DIM}(Slot 0 = autosave, managed automatically){_R}"))

        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()

        if ch in ('q', '0') and mode == "save":
            return None
        if ch == 'q':
            return None

        # Delete
        if ch == 'd':
            ds = input(C(f"  {_RED}Delete which slot (0-5)? {_R}")).strip()
            if ds.isdigit() and 0 <= int(ds) <= MAX_SLOTS:
                slot_n = int(ds)
                if slot_exists(slot_n):
                    confirm = input(C(f"  {_RED}Delete slot {slot_n}? (y/n) {_R}")).strip().lower()
                    if confirm == 'y':
                        delete_slot(slot_n)
                        print(C(f"  {_GREEN}Slot {slot_n} deleted.{_R}"))
                else:
                    print(C(f"  {_DIM}Slot {slot_n} is already empty.{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))
            continue

        if not ch.isdigit():
            continue
        slot_n = int(ch)
        if not (0 <= slot_n <= MAX_SLOTS):
            continue

        # LOAD mode
        if mode == "load":
            if not slot_exists(slot_n):
                print(C(f"  {_RED}Slot {slot_n} is empty.{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))
                continue
            try:
                player, world = load_slot(slot_n)
                world._loaded_playtime = (_load_meta(slot_n) or {}).get("playtime", 0)
                return player, world
            except Exception as e:
                print(C(f"  {_RED}Load failed: {e}{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))

        # SAVE mode
        elif mode == "save":
            if slot_n == AUTOSAVE_SLOT:
                print(C(f"  {_DIM}Slot 0 is reserved for autosave.{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))
                continue
            if current_player is None or current_world is None:
                return slot_n   # caller handles the actual save

            # Confirm overwrite if slot occupied
            if slot_exists(slot_n):
                meta = _load_meta(slot_n)
                name = meta['name'] if meta else "?"
                confirm = input(C(f"  {_YELL}Overwrite slot {slot_n} ({name})? (y/n) {_R}")).strip().lower()
                if confirm != 'y':
                    continue

            pt = autosave.playtime() if autosave else 0
            ok = save_slot(slot_n, current_player, current_world, pt)
            if ok:
                print(C(f"  {_GREEN}✓ Saved to slot {slot_n}!{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))
                return slot_n
            else:
                print(C(f"  {_RED}Save failed!{_R}"))
                input(C(f"  {_DIM}(Press Enter){_R}"))
