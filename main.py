"""main.py — Terminal-RPG launcher with raw-input world loop."""

from __future__ import annotations

import sys
if sys.version_info < (3, 8):
    sys.exit("Terminal-RPG needs Python 3.8 or newer — get it from https://www.python.org/downloads/")

import os
import json
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_player import Player
from game_world import WorldMap, clear, fg, C_GOLD, C_WHITE, C_DIM, C_GREEN, C_RED, C_CYAN, C_PURP, R_, B_
from game_stories import MAIN_STORIES
from game_lang import T, set_language, LANG, LANGUAGE_NAMES, pick_language_screen, save_language_pref, load_language_pref
from game_base import BaseMenu, build_base_on_map

from game_saves import (
    save_browser, save_slot, load_slot, slot_exists,
    AutoSave, migrate_legacy_saves, AUTOSAVE_SLOT, MAX_SLOTS
)

# Sentinel raised to go back one step in character creation
class _BackSignal(Exception): pass

def div(w=None):
    w=w or min(W()-4, 120)
    return C(f"{C_DIM}{chr(8212)*w}{R_}")

def opt(key, lbl, hint=""):
    inner = (f"  {C_GOLD}{B_}[{key}]{R_} {C_WHITE}{lbl}{R_}"
             + (f"  {C_DIM}{hint}{R_}" if hint else ""))
    return C(inner)

def back_opt():
    return opt('0', 'Back', 'Return to previous screen')

_BANNER_LINES = [
    f"{C_GOLD}{B_}",
    f"████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗ █████╗ ██╗         ██████╗ ██████╗  ██████╗",
    f"╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗██║         ██╔══██╗██╔══██╗██╔════╝",
    f"   ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║███████║██║         ██████╔╝██████╔╝██║  ███╗",
    f"   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██╔══██║██║         ██╔══██╗██╔═══╝ ██║   ██║",
    f"   ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██║  ██║███████╗    ██║  ██║██║     ╚██████╔╝",
    f"   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝      ╚═════╝{R_}",
    f"{C_CYAN}Open World  ·  DnD-Style  ·  Anime Progression  ·  Real-Time Movement{R_}",
]

_SMALL_BANNER = [
    "",
    f"{C_GOLD}{B_}╔╦╗╔═╗╦═╗╔╦╗╦╔╗╔╔═╗╦    ╦═╗╔═╗╔═╗{R_}",
    f"{C_GOLD}{B_} ║ ║╣ ╠╦╝║║║║║║║╠═╣║    ╠╦╝╠═╝║ ╦{R_}",
    f"{C_GOLD}{B_} ╩ ╚═╝╩╚═╩ ╩╩╝╚╝╩ ╩╩═╝  ╩╚═╩  ╚═╝{R_}",
    f"{C_CYAN}Open World · DnD-Style · Anime Progression{R_}",
]

def BANNER():
    # The big logo is 95 columns wide — it wrapped into garbage on narrow terminals
    lines = _BANNER_LINES if W() >= 100 else _SMALL_BANNER
    return "\n".join(C(l) for l in lines)

CLASS_INFO = {
    "Swordsman": ("Balanced melee. Good HP & ATK. Crits often.",  fg(220,180,80),  "STL  0 → Blade Master"),
    "Mage":      ("High magic damage. Low HP. Status effects.",    fg(80,200,220),  "STL +3 → Archmage"),
    "Rogue":     ("Fast, high dodge & crit. Applies poison.",      fg(180,80,220),  "STL +8 → Shadow Assassin"),
    "Tank":      ("Massive HP & DEF. Nearly unkillable.",          fg(160,160,160), "STL -3 → War Titan"),
    "Healer":    ("Support & sustain. Best healing power.",        fg(80,200,120),  "STL +2 → Arch Priest"),
}

# ── Step 1: Name entry ────────────────────────────────────────────

def _step_name(prev=None):
    """Ask for character name. Returns name str, or raises _BackSignal."""
    clear()
    print(BANNER())
    print(div())
    print(C(f"\n{C_CYAN}{B_}══════  NEW GAME  ──  Step 1 of 4: NAME  ══════{R_}\n"))
    print(back_opt())
    default = prev or "Hero"
    print(C(f"\n{C_DIM}Enter your character's name (or press Enter for '{default}'):{R_}"))
    val = input(C(f"\n{C_GOLD}>{R_} ")).strip()
    if val == "0": raise _BackSignal
    # Keep names printable and short enough for every UI box
    val = "".join(ch for ch in val if ch.isprintable())[:16].strip()
    return val or default

# ── Step 2: Class selection ───────────────────────────────────────

def _step_class(name):
    """Ask for class. Returns job_name str, or raises _BackSignal."""
    from game_jobs import STARTER_JOBS, create_job
    while True:
        clear()
        print(BANNER())
        print(div())
        print(C(f"\n{C_CYAN}{B_}══════  {name}  ──  Step 2 of 4: CLASS  ══════{R_}\n"))
        if W() >= 104:
            from game_art import render_sprite, sprite_width
            arts = [render_sprite(j) for j in STARTER_JOBS]
            ws = [sprite_width(j) for j in STARTER_JOBS]
            h = max(len(a) for a in arts)
            arts = [[" " * w] * (h - len(a)) + a for a, w in zip(arts, ws)]
            for row in range(h):
                print(C(" ".join(a[row] for a in arts)))
            labels = []
            for i, (j, w) in enumerate(zip(STARTER_JOBS, ws), 1):
                col = CLASS_INFO.get(j, ("", C_WHITE, ""))[1]
                labels.append(f"{col}{B_}{f'[{i}] {j}':^{w}}{R_}")
            print(C(" ".join(labels)))
            print()
        for i, job in enumerate(STARTER_JOBS, 1):
            desc, col, evo = CLASS_INFO.get(job, ("", C_WHITE, ""))
            j = create_job(job)
            stats = f"HP {100+j.hp_bonus:<3} ATK {10+j.atk_bonus:<2} MP {30+j.mp_bonus:<3} DEF {5+j.defend_bonus:<2}"
            print(C(f"{C_GOLD}{B_}[{i}]{R_} {col}{B_}{job:<10}{R_} {C_DIM}{desc:<44}{R_} {C_PURP}{evo}{R_}"))
            print(C(f"    {C_DIM}{stats}   Skills: {', '.join(s.name for s in j.skills)}{R_}"))
        print()
        print(back_opt())
        ch = input(C(f"\n{C_GOLD}>{R_} Choose class (1-{len(STARTER_JOBS)}): ")).strip()
        if ch == "0": raise _BackSignal
        if ch.isdigit() and 1 <= int(ch) <= len(STARTER_JOBS):
            return STARTER_JOBS[int(ch)-1]

# ── Step 3: Movement mode ─────────────────────────────────────────

def _step_movement(name):
    """Ask for movement mode. Returns 'wasd' or 'numpad', or raises _BackSignal."""
    while True:
        clear()
        print(BANNER())
        print(div())
        print(C(f"\n{C_CYAN}{B_}══════  {name}  ──  Step 3 of 4: MOVEMENT  ══════{R_}\n"))
        print(opt('1', T('move.wasd'),  'W/A/S/D — classic cardinal movement'))
        print(opt('2', T('move.8dir'),  'Number keys 1-9 (numpad layout) — includes diagonals'))
        print(C(f"\n{C_DIM}Arrow keys always work in both modes. You can switch any time from the help screen [?].{R_}"))
        print()
        print(back_opt())
        ch = input(C(f"\n{C_GOLD}>{R_} Choose mode (1/2): ")).strip()
        if ch == "0": raise _BackSignal
        if ch in ("1", ""): return "wasd"
        if ch == "2": return "numpad"

# ── Step 4: Story selection ───────────────────────────────────────

def _step_story(name):
    """Ask for main story. Returns story_id, or raises _BackSignal.
    Handles any number of main stories (feature modules register more)."""
    from game_stories import story_selection_screen

    def _header():
        if H() >= 44:
            print(BANNER())
            print(div())

    sid = story_selection_screen(name=f"{name}  ──  Step 4 of 4", allow_back=True, header=_header)
    if sid is None:
        raise _BackSignal
    return sid

# ── Step 5: Summary ───────────────────────────────────────────────

def _step_summary(name, job_name, movement_mode, story_id):
    """Show the finished character. Returns a Player, or raises _BackSignal."""
    player = Player(name, job_name)
    player.movement_mode = movement_mode
    player.stories.start_main(story_id)

    _, col, _ = CLASS_INFO.get(job_name, ("", C_WHITE, ""))
    from game_stories import ensure_external_stories
    ensure_external_stories()
    story = MAIN_STORIES.get(story_id)
    clear()
    print(BANNER())
    print(div())
    title = f"{name} the {job_name} begins their journey!"
    print(C(f"\n{C_GOLD}{B_}╔{'═'*(len(title)+4)}╗"))
    print(C(f"║  {title}  ║"))
    print(C(f"╚{'═'*(len(title)+4)}╝{R_}\n"))
    from game_art import print_sprite
    print_sprite(job_name, indent=2)
    print()
    print(C(f"{col}HP:{player.max_hp}  ATK:{player.atk}  MP:{player.max_mp}  DEF:{player.defense}  Stealth:{player.get_stealth()}{R_}"))
    print(C(f"\n{C_WHITE}Starting skills:{R_}"))
    for sk in player.skills:
        base = f"DMG {sk.damage}" if sk.damage else f"HEAL {sk.heal}" if sk.heal else "BUFF"
        print(C(f"  {C_CYAN}→{R_} {C_WHITE}{sk.name}{R_}  {C_DIM}[{base}, MP:{sk.mana_cost}] {sk.description}{R_}"))
    print(C(f"\n{C_GOLD}You carry 1 God Potion.{R_} {C_DIM}Auto-activates at 0 HP. Guard it.{R_}"))
    print(C(f"\n{C_PURP}Movement:{R_} {C_WHITE}{'WASD (4-dir)' if movement_mode=='wasd' else '8-Direction (number keys)'}{R_}"))
    if story:
        print(C(f"\n{story['colour']}{B_}Main Story: {story['title']}{R_}"))
    print(C(f"{C_DIM}[J] journal  ·  [?] help  ·  [C] encyclopedia has a full game guide.{R_}"))
    print()
    print(back_opt())
    val = input(C(f"\n{C_GOLD}>{R_} Press Enter to begin (or 0 to go back): ")).strip()
    if val == "0":
        raise _BackSignal
    return player

# ── Character creation — orchestrates all steps ───────────────────

def character_creation():
    """
    Walks through the steps with full back-navigation.
    Returns a ready Player, or None if the user backs all the way out.
    """
    step = 1
    name = job_name = movement_mode = story_id = None
    while True:
        try:
            if step == 1:
                name = _step_name(name); step = 2
            elif step == 2:
                job_name = _step_class(name); step = 3
            elif step == 3:
                movement_mode = _step_movement(name); step = 4
            elif step == 4:
                story_id = _step_story(name); step = 5
            else:
                return _step_summary(name, job_name, movement_mode, story_id)
        except _BackSignal:
            step -= 1
            if step < 1:
                return None


# ── World loop ────────────────────────────────────────────────────

# The session currently being played — used for an emergency autosave if the
# game is interrupted (Ctrl+C) or something unexpected goes wrong.
_SESSION = {"player": None, "world": None, "autosave": None}


def _switch_movement(player, inp):
    player.movement_mode = "numpad" if player.movement_mode == "wasd" else "wasd"
    inp.mode = player.movement_mode
    return (f"{C_GREEN}Movement mode: "
            f"{'WASD (4-dir)' if player.movement_mode == 'wasd' else '8-direction (number keys 1-9)'}{R_}")


def world_loop(player, world, autosave: "AutoSave | None" = None):
    from game_input import InputHandler
    from game_player import quick_inventory
    inp = InputHandler(mode=player.movement_mode)
    if autosave is None:
        autosave = AutoSave(interval=30)
    _SESSION.update(player=player, world=world, autosave=autosave)
    clear()

    while True:
        if not player.is_alive():
            # Safety net — every location now handles defeat itself
            world._handle_defeat(player)

        world.render(player)
        action = inp.get_action()

        if action[0] == 'move':
            _, dx, dy = action
            world.move_player(dx, dy, player)
            if autosave.tick(player, world):
                world.last_msg += f"  {C_DIM}[Autosaved]{R_}"

        elif action[0] == 'cmd':
            cmd = action[1]
            if   cmd == 'enter':
                world.enter_location(player, autosave)
                autosave.force(player, world)      # checkpoint after every visit
            elif cmd == 'fast':     world.fast_travel(player)
            elif cmd == 'overview': world.show_overview()
            elif cmd == 'map':      world.show_locations()
            elif cmd == 'help':
                world.show_help()
                print(C(f"{C_GOLD}[M]{R_} {C_DIM}Switch movement mode (currently "
                        f"{'WASD' if player.movement_mode == 'wasd' else '8-direction'}){R_}   "
                        f"{C_GOLD}[Enter]{R_} {C_DIM}Back{R_}"))
                if input(C(f"{C_GOLD}>{R_} ")).strip().lower() == "m":
                    world.last_msg = _switch_movement(player, inp)
            elif cmd == 'journal':  player.stories.show_journal(player)
            elif cmd == 'inventory':
                quick_inventory(player)
            elif cmd == 'codex':
                from game_codex import open_encyclopedia
                open_encyclopedia(player)
            elif cmd == 'base':
                ter = world.terrain[world.player_y][world.player_x]
                cid = world.cont_map[world.player_y][world.player_x]
                if ter in ('~', ';'):
                    world.last_msg = f"{C_RED}Can't build on water.{R_}"
                else:
                    if hasattr(player,'bases') and player.bases.has_base(cid):
                        player_base = player.bases.get_base(cid)
                        if player_base.x == world.player_x and player_base.y == world.player_y:
                            BaseMenu(player, player_base).enter()
                        else:
                            world.last_msg = (f"{C_DIM}Your base on this continent is elsewhere "
                                              f"({player_base.location_name}). Enter it via [H] in a city here.{R_}")
                    else:
                        built = build_base_on_map(player, world.player_x, world.player_y, cid)
                        if built:
                            world.last_msg = f"{C_GREEN}Base built! Press [B] here or [H] in a city to use it.{R_}"
            elif cmd == 'party':
                # (used to call a Party.show() method that doesn't exist → crash)
                from game_party import recruit_menu
                recruit_menu(player)
            elif cmd == 'save':
                result = save_browser(mode="save", current_player=player,
                                      current_world=world, autosave=autosave)
                if result:
                    world.last_msg = f"{C_GREEN}Saved to slot {result}!{R_}"
            elif cmd == 'quit':
                clear()
                print(C(f"\n{C_CYAN}Save before quitting?{R_}\n"))
                print(opt('S', 'Save to a slot & quit'))
                print(opt('A', 'Autosave & quit'))
                print(opt('N', 'Quit without saving'))
                print(opt('C', 'Cancel — keep playing'))
                ch = input(C(f"\n{C_GOLD}>{R_} ")).strip().lower()
                if ch not in ('s', 'a', 'n'):
                    continue
                if ch == 's':
                    if save_browser(mode="save", current_player=player,
                                    current_world=world, autosave=autosave) is None:
                        continue      # backed out of the save screen — keep playing
                elif ch == 'a':
                    autosave.force(player, world)
                    print(C(f"\n{C_GREEN}Autosaved!{R_}"))
                    input(C(f"{C_DIM}(Press Enter){R_}"))
                _SESSION.update(player=None, world=None, autosave=None)
                return
            clear()


def _emergency_save():
    """Best-effort autosave of the running session. Returns True on success."""
    p, w, a = _SESSION["player"], _SESSION["world"], _SESSION["autosave"]
    if p is None or w is None:
        return False
    try:
        if not p.is_alive():
            p.hp = 1
        return save_slot(AUTOSAVE_SLOT, p, w, a.playtime() if a else 0)
    except Exception:
        return False


def _start_session(player, world, playtime=0):
    world.last_msg = f"{C_GREEN}Welcome back, {player.name}!{R_}"
    world_loop(player, world, AutoSave(interval=30, base_playtime=playtime))


def _load_and_play(slot):
    from game_saves import _load_meta
    try:
        player, world = load_slot(slot)
    except Exception as e:
        print(C(f"\n{C_RED}Could not load slot {slot}: {e}{R_}"))
        input(C(f"{C_DIM}(Press Enter){R_}"))
        return
    meta = _load_meta(slot) or {}
    print(C(f"\n{C_GREEN}Loaded: {player.name} Lv {player.level} {player.job.name}{R_}"))
    input(C(f"{C_DIM}{T('ui.press_enter')}{R_}"))
    _start_session(player, world, meta.get("playtime", 0))


# ── Main menu ─────────────────────────────────────────────────────

def main():
    import game_lang
    from game_saves import _load_meta, latest_slot
    load_language_pref()
    # One-time migration of legacy savegame.json -> saves/slot1
    migrated = migrate_legacy_saves()

    while True:
        clear()
        print(BANNER())
        print(div())
        cur_lang = LANGUAGE_NAMES.get(game_lang.LANG, game_lang.LANG)
        latest = latest_slot()
        print()
        if latest is not None:
            m = _load_meta(latest) or {}
            print(opt('C', 'Continue', f"{m.get('name','?')} Lv{m.get('level','?')} — {m.get('location','?')}"))
        print(opt('1', T('menu.new_game'),  'Start a fresh adventure'))
        print(opt('2', T('menu.load_game'), 'Choose a save slot'))
        print(opt('L', T('menu.language'),  cur_lang))
        print(opt('3', T('menu.quit'),       'Exit Terminal-RPG'))

        if migrated:
            print(C(f"\n  {C_GREEN}✓ Old save migrated to Slot 1!{R_}"))
            migrated = False

        any_save = False
        for s in range(0, MAX_SLOTS + 1):
            meta = _load_meta(s)
            if meta:
                tag  = " [AUTO]  " if s == AUTOSAVE_SLOT else f" [Slot {s}]"
                print(C(f"{C_DIM}{tag}  {meta['name']} Lv{meta['level']} "
                        f"{meta['job']} — {meta['location']}  {meta['datetime']}{R_}"))
                any_save = True
        if not any_save:
            print(C(f"\n  {C_DIM}No saves yet — choose [1] to begin.{R_}"))

        ch = input(C(f"\n{C_GOLD}>{R_} ")).strip().lower()

        if ch == "c" and latest is not None:
            _load_and_play(latest)

        elif ch == "1":
            player = character_creation()
            if player is None:
                continue
            clear()
            print(C(f"\n{C_DIM}Generating the world...{R_}"))
            world = WorldMap()
            world_loop(player, world, AutoSave(interval=30))

        elif ch == "2":
            result = save_browser(mode="load")
            if result is None:
                continue
            player, world = result
            print(C(f"\n{C_GREEN}Loaded: {player.name} Lv {player.level} {player.job.name}{R_}"))
            input(C(f"{C_DIM}{T('ui.press_enter')}{R_}"))
            _start_session(player, world, getattr(world, "_loaded_playtime", 0))

        elif ch == "l":
            pick_language_screen()
            save_language_pref()

        elif ch in ("3", "q"):
            clear()
            print(C(f"\n{C_GOLD}Thanks for playing Terminal-RPG!{R_}\n")); break


def run():
    """Entry point with graceful handling of Ctrl+C and unexpected errors."""
    import traceback, datetime
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        saved = _emergency_save()
        print("\033[0m")
        print(C(f"{C_GOLD}Game interrupted.{R_} "
                + (f"{C_GREEN}Progress autosaved to the AUTO slot.{R_}" if saved else "")))
    except Exception:
        saved = _emergency_save()
        log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        print("\033[0m")
        traceback.print_exc()
        print(f"\nSorry — Terminal-RPG hit an unexpected error. Details were written to {log}.")
        if saved:
            print("Your progress was autosaved to the AUTO slot — choose Continue next time.")


if __name__ == "__main__":
    run()
