"""
rpg_systems.py — Towns, shops, quests, dungeons, combat.
All screens clear before drawing and use the colour system from game_world.
"""

import random, os
from game_items import roll_drops, town_shop_stock, CRAFTING_RECIPES
from game_enemies import generate_enemy, create_boss
from game_lang import T, set_language, LANG, LANGUAGE_NAMES
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_art import print_sprite, side_by_side, render_sprite, combat_layout

# ═══════════════════════════════════════════════════════════════
# RE-IMPORT COLOUR HELPERS  (same palette as world_map)
# ═══════════════════════════════════════════════════════════════

R      = "\033[0m"
B      = "\033[1m"
def fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"

C_GOLD   = fg(255,215,0)
C_WHITE  = fg(255,255,255)
C_DIM    = fg(120,120,120)
C_GREEN  = fg(80,200,80)
C_RED    = fg(220,60,60)
C_CYAN   = fg(80,220,220)
C_BLUE   = fg(80,130,220)
C_YELLOW = fg(240,200,60)
C_ORANGE = fg(220,140,40)
C_PURPLE = fg(180,80,220)
C_PINK   = fg(220,80,160)

def clear(): clr()

def divider(w=None, c=C_DIM):
    from game_term import _pad
    _cols=W()
    # Total visible = _pad() + w. Cap so it never exceeds terminal width.
    max_w = max(30, _cols - 2 * _pad() - 2)
    w = w or min(max_w, 120)
    return C(f"{c}{'─'*w}{R}")
def section(title, c=C_CYAN):  return C(f"\n{c}{B}══ {title} ══{R}")
def prompt(text=""):
    print(C(f"\n{C_GOLD}>{R} {C_DIM}{text}{R} "), end="")
    return input().strip()

def menu_opt(key, label, hint=""):
    k = f"{C_GOLD}{B}[{key}]{R}"
    l = f"{C_WHITE}{label}{R}"
    h = f"  {C_DIM}{hint}{R}" if hint else ""
    return f"{k} {l}{h}"   # no leading spaces — C() adds centring

def hp_bar(current, maximum, width=None):
    _cols=W(); width=width or max(12,min(22,_cols//5))
    frac   = current / maximum if maximum else 0
    filled = int(width * frac)
    col    = C_GREEN if frac > 0.5 else C_YELLOW if frac > 0.25 else C_RED
    bar    = f"{col}{'█'*filled}{C_DIM}{'░'*(width-filled)}{R}"
    return f"[{bar}{R}] {col}{current}/{maximum}{R}"

def mp_bar(current, maximum, width=None):
    _cols=W(); width=width or max(8,min(16,_cols//7))
    frac   = current / maximum if maximum else 0
    filled = int(width * frac)
    bar    = f"{C_BLUE}{'█'*filled}{C_DIM}{'░'*(width-filled)}{R}"
    return f"[{bar}{R}] {C_BLUE}{current}/{maximum}{R}"

def status_header(player):
    effects = (f"  {C_YELLOW}Status: " +
               ", ".join(str(e) for e in player.status_effects) + R) if player.status_effects else ""
    return (
        f"{C_WHITE}{B}{player.name}{R}  {C_DIM}Lv{R}{C_GOLD}{B}{player.level}{R}"
        f"  {C_DIM}[{player.job.name}]{R}  {C_DIM}Rank {R}{C_ORANGE}{B}{player.rank}{R}"
        f"  {C_GOLD}Gold {player.gold}{R}{effects}"
    )

# ═══════════════════════════════════════════════════════════════
# COMBAT
# ═══════════════════════════════════════════════════════════════

def _capture(log, fn, *args, **kwargs):
    """Run fn while capturing everything it prints into the combat log."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    for ln in buf.getvalue().splitlines():
        if ln.strip():
            log.append(ln.strip(" "))
    return result


def _flush_notes(log, *enemies):
    """Move weakness / break / immunity notes from enemies into the log."""
    for e in enemies:
        if e is not None and hasattr(e, "pop_notes"):
            log.extend(e.pop_notes())


def _adds_of(enemy):
    return enemy.alive_adds() if hasattr(enemy, "alive_adds") else []


def _retarget(enemy, target):
    """Keep the player's target valid. New adds grab the target (they are the
    threat to deal with first); when an add dies, the next add or the boss
    becomes the target."""
    adds = _adds_of(enemy)
    if getattr(enemy, "just_summoned", False):
        enemy.just_summoned = False
        if adds:
            return adds[-1]
    if target is enemy:
        return enemy
    if target is None or not target.is_alive() or target not in adds:
        return adds[0] if adds else enemy
    return target


def _boss_header_lines(player, enemy, adds, target):
    """Extra rows for a boss fight: phase / shield / weakness / enrage, intent, adds."""
    from game_enemies import TYPE_COLOUR
    bits = []
    ph = getattr(enemy, "phase", 1)
    bits.append(f"{fg(*enemy.colour)}{B}PHASE {ph}{R}")
    sh = enemy.shield_text()
    if sh:
        bits.append(sh)
    wk = enemy.weak_text()
    if wk:
        bits.append(f"{C_DIM}{wk}{R}")
    en = enemy.enrage_text()
    if en:
        bits.append(en)
    lines = [f"{C_DIM}  ·  {R}".join(bits)]
    it = enemy.intent_text(player)
    if it:
        lines.append(f"{C_DIM}INTENT ▶{R} {it}")
    for a in adds:
        mark = f"  {C_GOLD}{B}◀ TARGET{R}" if a is target else ""
        eff = (" " + " ".join(f"{C_PURPLE}[{e}]{R}" for e in a.status_effects)) if a.status_effects else ""
        lines.append(f"{C_ORANGE}↳ {a.name[:14]:<14}{R} HP {hp_bar(a.hp, a.max_hp, 12)}{eff}{mark}")
    return lines


def _draw_combat(player, enemy, is_boss, log, allow_escape, stunned, rnd, note="", target=None):
    clear()
    title = f"  ⚔  {'BOSS BATTLE' if is_boss else 'BATTLE'} · {enemy.name} · Round {rnd}  "
    bw = max(len(title) + 8, 56)
    side = (bw - len(title)) // 2
    tcol = C_RED if is_boss else C_ORANGE
    print()
    print(C(f"{tcol}{B}{'═'*side}{title}{'═'*(bw - side - len(title))}{R}"))

    adds = _adds_of(enemy) if is_boss else []
    boss_lines = _boss_header_lines(player, enemy, adds, target) if is_boss else []
    has_team = bool(player.party.members)

    # Fit everything into the terminal: sprites only when there is room
    rows = H()
    fixed = 13 + len(boss_lines) + (1 if has_team else 0) + (1 if note else 0)
    from game_art import player_look
    acc, leg = player_look(player)
    art = side_by_side(player.job.name, getattr(enemy, "sprite", enemy.name),
                       gap=10, left_accent=acc, left_legendary=leg)
    avail = rows - fixed
    if avail >= len(art) + 1 + 4:
        log_n = max(4, min(8, avail - len(art) - 1))
        print()
        for art_line in art:
            print(art_line)
    else:
        log_n = max(3, min(8, avail))
    print()

    eff_str = ("  " + " ".join(f"{C_PURPLE}[{e}]{R}" for e in enemy.status_effects)) if enemy.status_effects else ""
    tmark = f"  {C_GOLD}{B}◀ TARGET{R}" if adds and target is enemy else ""
    phase = ""
    if not is_boss and getattr(enemy, "phase", 1) >= 2:
        phase = f"  {C_ORANGE}{B}⚡PHASE {enemy.phase}{R}"
    print(C(f"{C_RED}{B}FOE {R} {C_RED}{enemy.name[:16]:<16}{R} HP {hp_bar(enemy.hp, enemy.max_hp)}{eff_str}{phase}{tmark}"))
    for ln in boss_lines:
        print(C(ln))
    p_eff = ("  " + " ".join(f"{C_PURPLE}[{e}]{R}" for e in player.status_effects)) if player.status_effects else ""
    buff  = (f"  {C_ORANGE}[ATK+{player.temp_atk_buff} {player.temp_atk_turns}t]{R}"
             if getattr(player, "temp_atk_turns", 0) > 0 else "")
    hero = f"{player.name[:10]} Lv{player.level}"
    print(C(f"{C_GREEN}{B}YOU {R} {C_WHITE}{B}{hero:<16}{R} HP {hp_bar(player.hp, player.max_hp)}"
            f"  MP {mp_bar(player.mp, player.max_mp)}{p_eff}{buff}"))
    if has_team:
        mates = "  ".join(
            (f"{m._col() if hasattr(m, '_col') else C_WHITE}{m.name}{R} {C_DIM}{m.hp}/{m.max_hp}{R}"
             if m.is_alive() else f"{C_DIM}{m.name} (down){R}")
            for m in player.party.members)
        print(C(f"{C_CYAN}{B}TEAM{R}  {mates}"))

    # Combat log — the last few things that happened
    print(C(f"{C_DIM}── battle log {'─'*40}{R}"))
    shown = log[-log_n:]
    for ln in [""] * (log_n - len(shown)) + shown:
        print(C(ln))
    if note:
        print(C(note))
    print(C(f"{C_DIM}{'─'*54}{R}"))

    if stunned:
        print(C(f"{C_YELLOW}⚡ {T('combat.stunned')}{R}"))
    else:
        tgt = f"   {menu_opt('T', 'Target', 'switch')}" if adds else ""
        print(C(f"{menu_opt('1', T('combat.attack'), 'Basic weapon strike')}   "
                f"{menu_opt('2', T('combat.skill'), 'Class skill (MP)')}{tgt}"))
        print(C(f"{menu_opt('3', T('combat.item'), 'Potion, bomb, buff')}   "
                f"{menu_opt('4', T('combat.defend'), 'Brace, take less damage')}"
                + (f"   {menu_opt('5', T('combat.run'), 'Attempt to flee')}" if allow_escape else "")))


def _choose_skill(player, target=None):
    """Skill picker. Returns a Skill or None.  Shows each skill's damage type
    and flags the ones the current target is weak to."""
    from game_enemies import skill_damage_type, TYPE_COLOUR
    weak = getattr(target, "weak", set()) or set()
    clear()
    print(section("SKILLS"))
    print(C(f"{C_DIM}MP {player.mp}/{player.max_mp} — if MP is short, the rest is paid with HP.{R}\n"))
    for i, sk in enumerate(player.skills, 1):
        enough = C_GREEN if player.mp >= sk.mana_cost else C_RED
        base   = (f"DMG {sk.damage}" if sk.damage else f"HEAL {sk.heal}" if sk.heal
                  else "BUFF")
        fx     = f" +{sk.status_effect.name}({sk.status_chance}%)" if sk.status_effect else ""
        typ = ""
        if sk.damage:
            t = skill_damage_type(sk, player)
            typ = f" {TYPE_COLOUR.get(t, '')}{t}{R}"
            if t in weak:
                typ += f" {C_GOLD}{B}WEAK!{R}"
        print(C(f"{menu_opt(i, sk.name, f'{base}{fx}')}{typ}  {enough}MP:{sk.mana_cost}{R}"))
        if sk.description:
            print(C(f"     {C_DIM}{sk.description}{R}"))
    print(C(f"\n{menu_opt(0, 'Cancel')}"))
    raw = prompt("Choose skill")
    if raw.isdigit() and 1 <= int(raw) <= len(player.skills):
        return player.skills[int(raw) - 1]
    return None


def _throw_bomb(player, enemy, idx, allow_escape, log):
    """Bomb items. Returns 'escaped', 'used' or None (not used)."""
    from game_items import remove_items
    it = player.inventory[idx]
    if it.name == "Smoke Bomb":
        if not allow_escape:
            log.append(f"{C_RED}The smoke clears — there is no escaping this foe!{R}")
            return None
        remove_items(player.inventory, it.name, 1)
        log.append(f"{C_PURPLE}You vanish in a cloud of smoke!{R}")
        return "escaped"
    remove_items(player.inventory, it.name, 1)
    dmg = it.value + player.level * 3 + random.randint(0, 10)
    enemy._incoming = ("fire", "bomb")
    dealt = enemy.take_damage(dmg)
    enemy._incoming = None
    log.append(f"{C_ORANGE}{B}BOOM!{R} {it.name} hits {enemy.name} for {dealt} damage!")
    if random.randint(1, 100) <= 40 and enemy.is_alive():
        from game_items import Burn
        _capture(log, enemy.add_status, Burn(duration=2, damage=5 + player.level))
        if any(e.name == "Burn" for e in enemy.status_effects):
            log.append(f"{C_ORANGE}{enemy.name} is set ablaze!{R}")
    return "used"


def _blind_miss(player, chance):
    if any(e.name == "Blind" for e in player.status_effects):
        return random.randint(1, 100) <= chance
    return False


def run_combat(player, enemy, allow_escape=True, first_strike=False):
    from game_enemies import (BossEnemy, Blind, skill_damage_type, companion_damage_type,
                              pick_target, COMBAT_ONLY_STATUSES)
    from game_items import use_entry
    is_boss = isinstance(enemy, BossEnemy)
    if is_boss:
        enemy.prepare(player)
    base_defense = player.defense
    log = []
    used_potion = False
    player._damage_this_battle = 0
    target = enemy

    if is_boss:
        title = f" {C_DIM}— {enemy.title}{R}" if enemy.title else ""
        log.append(f"{fg(*enemy.colour)}{B}{enemy.name}{R}{title}")
        intro = enemy.kit.get("intro")
        if intro:
            log.append(f"{C_YELLOW}{intro}{R}")
        if enemy.difficulty != "normal":
            log.append(f"{C_DIM}Difficulty: {enemy.difficulty.title()}{R}")

    # ── Sneak attack on first round ──────────────────────────
    if first_strike and player.in_stealth:
        base = max(1, player.combat_atk() + random.randint(0, 3))
        dmg = _capture(log, player.stealth_first_strike, base)
        enemy._incoming = ("physical", "sneak")
        dealt = enemy.take_damage(dmg)
        log.append(f"{C_PURPLE}{B}★ {T('combat.sneak_attack')} {enemy.name} → {dealt} damage!{R}")
        _flush_notes(log, enemy)
        if is_boss:
            log.extend(enemy.check_phase())

    rnd = 0
    while enemy.is_alive() and player.is_alive():
        rnd += 1
        log.append(f"{C_DIM}── Round {rnd} ──{R}")

        # ── Start of round: status ticks happen ONCE per round ──
        _capture(log, player.process_status_start)
        if not player.is_alive():
            if not _capture(log, player.check_god_potion):
                break
        stunned = any(e.name == "Stun" for e in player.status_effects)

        target = _retarget(enemy, target)
        if is_boss:
            enemy.plan(player)                 # reveal this round's intent

        # ── Player picks an action (invalid input / cancel = pick again) ──
        note = ""
        fled = False
        defending = False
        while True:
            _draw_combat(player, enemy, is_boss, log, allow_escape, stunned, rnd, note, target)
            note = ""
            if stunned:
                input(C(f"{C_DIM}(Press Enter){R}"))
                log.append(f"{C_YELLOW}You are stunned and lose your turn!{R}")
                break
            action = prompt("Choose action").lower()

            if action == "t":
                choices = [enemy] + _adds_of(enemy)
                if len(choices) > 1:
                    i = choices.index(target) if target in choices else 0
                    target = choices[(i + 1) % len(choices)]
                else:
                    note = f"{C_DIM}There is only one foe to target.{R}"
                continue

            if action == "1":
                if _blind_miss(player, Blind.MISS):
                    log.append(f"{C_YELLOW}Blinded, your swing cuts only air!{R}")
                elif target.try_dodge():
                    log.append(f"{C_DIM}{T('combat.dodged', name=target.name)}{R}")
                else:
                    base = max(1, player.combat_atk() + random.randint(-2, 3))
                    crit, dmg = player.calc_crit(base)
                    target._incoming = ("physical", "attack")
                    dealt = target.take_damage(dmg)
                    tag = f" {C_ORANGE}{B}CRITICAL!{R}" if crit else ""
                    if crit:
                        from game_customise import tick_legendary_quest as _tlq
                        _capture(log, _tlq, player, "crit_hit")
                    msg = T('combat.you_strike', crit=tag, dmg=dealt)
                    if target is not enemy:
                        msg += f" {C_DIM}({target.name}){R}"
                    log.append(f"{C_WHITE}{msg}{R}")
                break

            elif action == "2":
                if not player.skills:
                    note = f"{C_DIM}You have no skills yet.{R}"; continue
                sk = _choose_skill(player, target)
                if sk is None:
                    continue
                if not sk.can_use(player):
                    note = f"{C_RED}Not enough MP or HP to cast {sk.name}.{R}"; continue
                if sk.damage > 0 and _blind_miss(player, Blind.MISS // 2):
                    _capture(log, sk.pay_cost, player)
                    log.append(f"{C_YELLOW}Blinded, your {sk.name} goes wide!{R}")
                    break
                if sk.damage > 0:
                    target._incoming = (skill_damage_type(sk, player), "skill")
                ok = _capture(log, sk.use, player, target if sk.damage > 0 else None)
                target._incoming = None
                if not ok:
                    continue
                from game_customise import tick_legendary_quest
                _capture(log, tick_legendary_quest, player, "skill_cast")
                if sk.heal > 0:
                    _capture(log, player._tick_evolution_quest, "heal_skill")
                break

            elif action == "3":
                idx = player.pick_consumable(in_combat=True)
                if idx is None:
                    continue
                it = player.inventory[idx]
                if it.item_type == "bomb":
                    res = _throw_bomb(player, target, idx, allow_escape, log)
                    if res is None:
                        continue
                    if res == "escaped":
                        fled = True
                    break
                if it.item_type in ("heal", "mana"):
                    used_potion = True
                if _capture(log, use_entry, player.inventory, idx, player, True):
                    break
                continue

            elif action == "4":
                _capture(log, player.defend)
                defending = True
                break

            elif action == "5" and allow_escape:
                esc = 40 + player.job.dodge_bonus + player.get_stealth()
                if random.randint(1, 100) <= min(90, esc):
                    log.append(f"{C_GREEN}{T('combat.fled')}{R}")
                    fled = True
                else:
                    log.append(f"{C_RED}{T('combat.cant_flee')}{R}")
                break

            else:
                note = f"{C_RED}Invalid choice — pick one of the numbers below.{R}"

        # ── Aftermath of the hero's action ──
        _flush_notes(log, enemy, *getattr(enemy, "adds", []))
        if is_boss:
            _capture(log, enemy.resolve_counters, player)
            log.extend(enemy.check_phase())
        _report_fallen(log, enemy)

        if fled:
            player.defense = base_defense
            player.temp_atk_buff = player.temp_atk_turns = 0
            _end_of_battle_cleanup(player, COMBAT_ONLY_STATUSES)
            _draw_combat(player, enemy, is_boss, log, allow_escape, False, rnd, "", target)
            input(C(f"{C_DIM}(Press Enter){R}"))
            return "escaped"

        if not player.is_alive():
            if not _capture(log, player.check_god_potion):
                break

        _capture(log, player.process_status_end)
        _capture(log, player.tick_buffs)

        # ── Party members act (they follow the hero's target) ──
        mates_alive = player.party.alive_members()
        if enemy.is_alive() and mates_alive:
            for companion in mates_alive:
                if not enemy.is_alive():
                    break
                target = _retarget(enemy, target)
                tgt = target if target.is_alive() else enemy
                tgt._incoming = (companion_damage_type(companion), "companion")
                tgt._dodge_next = True
                try:
                    _capture(log, companion.combat_action, player, tgt, player.party.members)
                finally:
                    tgt._incoming = None
                    tgt._dodge_next = False
                _flush_notes(log, enemy, *getattr(enemy, "adds", []))
            if is_boss:
                log.extend(enemy.check_phase())
            _report_fallen(log, enemy)
        target = _retarget(enemy, target)

        # ── Boss minions act ──
        if is_boss and enemy.is_alive():
            for a in _adds_of(enemy):
                _capture(log, a.process_status_start)
                if a.is_alive():
                    if a.is_stunned():
                        log.append(f"{C_DIM}{a.name} is stunned.{R}")
                    else:
                        _capture(log, a.basic_attack,
                                 pick_target(player, player.party.alive_members()))
                _capture(log, a.process_status_end)
            _report_fallen(log, enemy)

        # ── Enemy turn ──
        alive_before = [m for m in player.party.members if m.is_alive()]
        if enemy.is_alive() and player.is_alive():
            _capture(log, enemy.process_status_start)
            if is_boss:
                log.extend(enemy.check_phase())
            if enemy.is_alive():
                if is_boss:
                    _capture(log, enemy.act, player, player.party.alive_members(),
                             defending, base_defense)
                elif enemy.is_stunned():
                    log.append(f"{C_YELLOW}{enemy.name} is stunned and can't act!{R}")
                else:
                    _capture(log, enemy.basic_attack,
                             pick_target(player, player.party.alive_members()))
            _capture(log, enemy.process_status_end)
            if is_boss:
                enemy.player_defended_last = defending
                log.extend(enemy.check_phase())
        for m in alive_before:
            if not m.is_alive():
                log.append(f"{C_RED}{m.name} is knocked out!{R}")

        if not player.is_alive():
            if not _capture(log, player.check_god_potion):
                break

        player.defense = base_defense

    player.defense = base_defense
    # Potion ATK buffs last for this battle only (they used to carry over)
    player.temp_atk_buff = player.temp_atk_turns = 0
    _end_of_battle_cleanup(player, COMBAT_ONLY_STATUSES)

    # ── Result ──
    clear()
    if not player.is_alive():
        for ln in log[-6:]:
            print(C(ln))
        print()
        print_sprite(getattr(enemy, "sprite", enemy.name), label=f"✖  DEFEATED  ✖")
        print(C(f"\n{C_RED}{B}╔══════════════════════╗"))
        print(C(f"║   ✖  DEFEATED        ║"))
        print(C(f"╚══════════════════════╝{R}\n"))
        print(C(f"{C_DIM}{enemy.name} bested you...{R}"))
        input(C(f"\n{C_DIM}(Press Enter){R}"))
        return "defeat"

    from game_art import player_look
    _acc, _leg = player_look(player)
    print_sprite(player.job.name, label=f"★  VICTORY  ★", accent=_acc, legendary=_leg)
    print(C(f"\n{C_GREEN}{B}╔══════════════════════════════╗"))
    print(C(f"║   ★  VICTORY!                ║"))
    print(C(f"╚══════════════════════════════╝{R}\n"))
    if is_boss and enemy.kit.get("last_words"):
        print(C(f"{C_DIM}{enemy.kit['last_words']}{R}\n"))
    completed = award_victory(player, enemy, used_potion)
    input(C(f"\n{C_DIM}(Press Enter){R}"))
    if completed:
        from game_stories import show_story_completion
        for stype, step in completed:
            show_story_completion(stype, step)
    return "victory"


def _report_fallen(log, enemy):
    """Log minions that died since the last check (once each)."""
    for a in getattr(enemy, "adds", []) or []:
        if not a.is_alive() and not getattr(a, "_reported", False):
            a._reported = True
            log.append(f"{C_GREEN}{a.name} falls!{R}")


def _end_of_battle_cleanup(player, combat_only):
    """Blindness and bleeding end with the battle (for hero and companions)."""
    for who in [player] + list(getattr(player.party, "members", []) or []):
        effs = getattr(who, "status_effects", None)
        if isinstance(effs, list):
            effs[:] = [e for e in effs if e.name not in combat_only]


def _boss_bonus_loot(player):
    """Guaranteed rare-or-better drop for a boss kill."""
    item = None
    try:
        from game_items import random_loot
        item = random_loot(player.level, rarity="rare")
    except Exception:
        item = None
    if item is None:
        try:
            from game_items import ITEM_POOL, Equipment
            cls = player.job.name
            pool = []
            for fac in ITEM_POOL.values():
                try:
                    it = fac()
                except Exception:
                    continue
                if isinstance(it, Equipment) and getattr(it, "rarity", "") in ("rare", "legendary") \
                        and (not it.allowed_classes or cls in it.allowed_classes):
                    pool.append(it)
            if pool:
                legend = [i for i in pool if i.rarity == "legendary"]
                item = random.choice(legend) if legend and random.randint(1, 100) <= 15 \
                    else random.choice([i for i in pool if i.rarity == "rare"] or pool)
        except Exception:
            item = None
    return item


def award_victory(player, enemy, used_potion=False):
    """Gold, EXP, loot, quest/story/legendary progress for a defeated enemy.
    Returns story completions [(type, step)] for the caller to display."""
    from game_enemies import BossEnemy
    from game_customise import tick_legendary_quest as _tlq
    is_boss = isinstance(enemy, BossEnemy)

    gold = enemy.gold_reward + getattr(player, "_gold_bonus_kill", 0)
    print(C(f"{C_GOLD}{T('combat.gold_exp', gold=gold, exp=enemy.exp_reward)}{R}"))
    player.gold += gold
    stolen = getattr(enemy, "stolen_gold", 0)
    if stolen:
        player.gold += stolen
        enemy.stolen_gold = 0
        print(C(f"{C_GOLD}You recover {stolen} stolen gold!{R}"))
    player.gain_exp(enemy.exp_reward)
    player.update_quests_on_kill(enemy.name)

    _tlq(player, "kill", enemy.name)
    if is_boss:
        _tlq(player, "kill_boss")
    if getattr(player, "_damage_this_battle", 0) == 0:
        _tlq(player, "no_damage_battle")
    if not used_potion:
        # Tank awakening: "Survive 5 battles without using any potions"
        player._tick_evolution_quest("survive")

    if is_boss and hasattr(player, "bases"):
        for base in player.bases.bases.values():
            if base.add_trophy(enemy.name, base.continent_id):
                print(C(f"{C_GOLD}🏆 Trophy added to {base.name}: {enemy.name}!{R}"))
                break

    drops = roll_drops(enemy.name)
    if is_boss:
        bonus = _boss_bonus_loot(player)
        if bonus is not None:
            drops = list(drops or []) + [bonus]
    if drops:
        print(C(f"\n{C_YELLOW}Loot dropped:{R}"))
        for item in drops:
            if player.add_item(item):
                print(C(f"  {C_WHITE}→ {item}{R}"))
            else:
                print(C(f"  {C_DIM}→ {item} (no room — left behind){R}"))
    else:
        print(C(f"\n{C_DIM}{T('combat.no_drops')}{R}"))

    # Story progress (used to only be counted on the world map, so story
    # steps that need dungeon enemies — e.g. 8 Cultists — were impossible)
    completed = []
    if hasattr(player, "stories"):
        completed = player.stories.on_kill(enemy.name, player)
    return completed


# ═══════════════════════════════════════════════════════════════
# NPC DIALOGUE
# ═══════════════════════════════════════════════════════════════

TOWNSFOLK = [
    {"name":"Gruff the Innkeeper","icon":"[INN]","personality":"grumpy but kind",
     "lines":["Rest well traveller. The roads grow more dangerous each day.",
              "Strange creatures spotted near the old fortress last night.",
              "A dragon was seen circling the Iron Peaks. Bold or mad.",
              "I had an adventurer like you once. Now she's a legend. Or dead.",
              "The cellar keeps flooding with something... it's not water."],
     "offer":None},
    {"name":"Elder Voss","icon":"[SCH]","personality":"wise historian",
     "lines":["This land was once ruled by the Dragon Court. Five hundred years ago it fell.",
              "The five continents were once connected. A cataclysm split them apart.",
              "The God Potions — they were not created by alchemy. Something older made them.",
              "Every dungeon has a guardian. Not all of them are monsters.",
              "There are ruins beneath every city. We built on old bones."],
     "offer":"lore"},
    {"name":"Merchant Dalia","icon":"[MRC]","personality":"shrewd trader",
     "lines":["Dragon scales? I'll triple your asking price. Don't tell the guild.",
              "The black market thrives in shadows. Not that I'd know anything about that.",
              "My wares are the finest because I source from the bravest fools — like you.",
              "Gold flows toward the bold. Are you bold enough?",
              "I once sold a god potion back to a god. The markup was divine."],
     "offer":"tip"},
    {"name":"Zara the Blacksmith","icon":"[SMT]","personality":"passionate craftsperson",
     "lines":["Bring me Dragon Scale and Iron Ore. I'll forge you something that sings.",
              "A good blade is like a good friend — reliable when things get bloody.",
              "The secret to great armor: metal, heart, and stubbornness.",
              "I can repair anything. Except bad decisions.",
              "Wolf Pelt makes surprisingly good padding under chain mail."],
     "offer":"crafting_tip"},
    {"name":"Captain Marek","icon":"[CPT]","personality":"battle-hardened soldier",
     "lines":["I've fought in twelve wars. The one coming will be the thirteenth.",
              "Never enter a dungeon without potions. Watched good people die over that.",
              "The Shadow Beasts have been pushing further west. Something drives them.",
              "Your class defines your style, not your fate.",
              "Keep your back to the wall. Always."],
     "offer":"combat_tip"},
    {"name":"Sister Mara","icon":"[HLR]","personality":"gentle healer",
     "lines":["I see wounds in your eyes that potions can't reach. Travel safely.",
              "The light doesn't judge the darkness you've walked through.",
              "A Healer's power is not in their spells but in their resolve.",
              "There is a holy site deep in the Frost Mountains. Ancient power lingers.",
              "Even God Potions have limits. The soul must be willing to survive."],
     "offer":"blessing"},
    {"name":"Riko the Wanderer","icon":"[EXP]","personality":"cheerful explorer",
     "lines":["I mapped every continent. Except the one that maps itself — it changes.",
              "The South Isles have fruits that restore MP just by smelling them!",
              "Found a cave once with walls that whispered. Left. Quickly.",
              "Fast travel saves time but you miss the adventures in between.",
              "There's a ship captain in Greenport who sails without wind or crew."],
     "offer":"map_hint"},
    {"name":"The Masked One","icon":"[???]","personality":"cryptic and unsettling",
     "lines":["There is a dungeon to the east no one has fully cleared...",
              "God Potions were not crafted. They were negotiated.",
              "An awakened warrior once slew a dragon with one strike. Still running.",
              "The world has five regions. One of them is wrong.",
              "I know who you are. Do you?"],
     "offer":"secret"},
]

OFFER_RESPONSES = {
    "lore":         ["Elder Voss traces an ancient map. 'This was all one land, once.'",
                     "The elder's eyes grow distant. The past weighs heavily on him."],
    "tip":          ["Dalia slips you a folded note. 'Don't open it near guards.'",
                     "The merchant whispers a trade route only she knows."],
    "crafting_tip": ["Zara shows a hidden compartment — better tools than she sells.",
                     "'See this seam?' She points at your armor. 'I can reinforce that. This once.'"],
    "combat_tip":   ["Marek demonstrates a feint. Your reflexes feel sharper somehow.",
                     "The captain sketches a dungeon layout. 'Enemy choke points: here, here.'"],
    "blessing":     ["Sister Mara murmurs a quiet prayer. Your HP fully restores!",
                     "The sister presses a warm hand to your shoulder. You feel lighter."],
    "map_hint":     ["Riko marks a hidden path — cuts travel time considerably.",
                     "'Shortcut through the hills,' Riko says, sketching in the air."],
    "secret":       ["The figure vanishes. A gold coin sits where they stood.",
                     "'Remember me when you find it,' echoes from nowhere."],
}

NPC_LINES = {t["name"]: t["lines"] for t in TOWNSFOLK}


CLANS = {
    "Iron Fist":      ("Warrior clan",  C_RED,    "DEF +5, ATK +3"),
    "Shadow Weavers": ("Rogue clan",    C_PURPLE, "DODGE +8, CRIT +5"),
    "Silver Dragons": ("Mage clan",     C_CYAN,   "MP +20, Skill Power +4"),
    "Holy Order":     ("Healer clan",   C_GREEN,  "Heal Power +10, DEF +3"),
}


# ═══════════════════════════════════════════════════════════════
# TOWN
# ═══════════════════════════════════════════════════════════════

class Town:
    def __init__(self, player, town_name, region_name=""):
        self.player      = player
        self.town_name   = town_name
        self.region_name = region_name
        self.shop_stock  = town_shop_stock(region_name)
        self._companion_cb  = None   # set by world map
        self._continent_id  = None
        self._base_x        = 0
        self._base_y        = 0
        self._world_map     = None
        self._ship          = None
        self._ship_player   = None

    def set_companion_callback(self, cb):
        self._companion_cb = cb

    def set_base_info(self, continent_id, x, y):
        self._continent_id = continent_id
        self._base_x = x
        self._base_y = y

    def set_ship(self, world_map, ship, player):
        """Store ship reference so port towns can offer boarding."""
        self._world_map = world_map
        self._ship      = ship
        self._ship_player = player

    def set_world(self, world_map, autosave=None):
        """World reference — needed to save the game from inside a town."""
        self._world_map = world_map
        self._autosave  = autosave

    def _save_game(self):
        if not self._world_map:
            print(C(f"\n{C_RED}Saving isn't available here.{R}"))
            input(C(f"{C_DIM}(Press Enter){R}")); return
        from game_saves import save_browser
        save_browser(mode="save", current_player=self.player,
                     current_world=self._world_map,
                     autosave=getattr(self, "_autosave", None))

    def _header(self, subtitle=""):
        clear()
        print(C(f"\n{C_GOLD}{B}╔══════════════════════════════════════════╗"))
        print(C(f"║  {self.town_name.upper():<40}║"))
        if subtitle:
            print(C(f"║  {C_DIM}{subtitle:<40}{C_GOLD}║"))
        print(C(f"╚══════════════════════════════════════════╝{R}"))
        print(C(f"\n{status_header(self.player)}"))
        print(divider())

    # ── INN ──────────────────────────────────────────────────

    def inn(self):
        cost = max(5, 10 + self.player.level * 2)
        self._header(f"{T('town.inn')}  —  {T('town.inn_cost', cost=cost)}")
        print(C(f"\n{C_WHITE}Rest fully? {C_GOLD}HP & MP{R} restored, {C_GREEN}status cleared{R}."))
        print(C(f"\n{menu_opt('Y','Rest & pay')} {C_DIM}({cost} gold){R}"))
        print(C(f"{menu_opt('N','Leave')}"))
        ch = prompt("Choice").lower()
        if ch == "y":
            if self.player.gold >= cost:
                self.player.gold -= cost
                self.player.hp = self.player.max_hp
                self.player.mp = self.player.max_mp
                self.player.status_effects.clear()
                for m in self.player.party.members:
                    m.rest()
                print(C(f"\n{C_GREEN}You rest deeply. Fully restored!{R}"))
                pass_day(self.player)
            else:
                print(C(f"\n{C_RED}{T('ui.not_enough_gold')} (have {self.player.gold}g){R}"))
        input(C(f"\n{C_DIM}(Press Enter){R}"))

    # ── SHOP ─────────────────────────────────────────────────

    def shop(self):
        while True:
            self._header("Shop")
            print(C(f"\n{menu_opt('1','Browse & Buy')}"))
            print(C(f"{menu_opt('2','Sell items')}"))
            print(C(f"{menu_opt('0','Leave shop')}"))
            ch = prompt("Choice")
            if ch == "1":   self._buy()
            elif ch == "2": self._sell()
            elif ch == "0": break

    def _buy(self):
        import copy
        from game_items import STACKABLE_TYPES, item_count
        from game_player import Player
        msg = ""
        while True:
            self._header("Shop — Buy")
            pc = self.player.job.name
            print(C(f"\n{C_GOLD}Your gold: {self.player.gold}g{R}  {C_DIM}Class: {C_CYAN}{pc}{R}\n"))
            for i,(item,price) in enumerate(self.shop_stock, 1):
                ac = getattr(item,"allowed_classes",None)
                can_use = (ac is None or pc in ac)
                rcol = item.rarity_col() if hasattr(item,"rarity_col") else C_WHITE
                if hasattr(item, "stat_line"):
                    stat = f"  {C_DIM}{item.stat_line()}{R}"
                    have = self.player.equipped.get(item.slot)
                    if have and have.name == item.name:
                        stat += f" {C_GREEN}[equipped]{R}"
                else:
                    owned = item_count(self.player.inventory, item.name)
                    stat = (f"  {C_DIM}{Player.describe_consumable(item)}{R}"
                            + (f" {C_DIM}(have {owned}){R}" if owned else ""))
                if not can_use:
                    col = C_DIM
                    cnote = f"  {C_RED}({', '.join(ac[:2])} only){R}"
                else:
                    col = rcol if self.player.gold >= price else C_DIM
                    cnote = ""
                print(C(f"{C_GOLD}{B}[{i:>2}]{R} {col}{item.name:<20}{R} {C_GOLD}{price:>4}g{R}{stat}{cnote}"))
            if msg:
                print(C(f"\n{msg}")); msg = ""
            print(C(f"\n{menu_opt(0,'Done')}   {C_DIM}Tip: '3x5' buys five of item 3{R}"))
            ch = prompt("Buy item #").lower().replace(" ", "")
            if ch in ("0", ""): return
            qty = 1
            if "x" in ch:
                ch, _, q = ch.partition("x")
                qty = int(q) if q.isdigit() and int(q) > 0 else 1
            if not ch.isdigit(): continue
            idx = int(ch)-1
            if not (0 <= idx < len(self.shop_stock)): continue
            item,price = self.shop_stock[idx]
            if item.item_type not in STACKABLE_TYPES:
                qty = 1
            note = ""
            ac = getattr(item, "allowed_classes", None)
            if ac and pc not in ac:
                note = f"  {C_YELLOW}(Note: a {pc} can't equip it — you can still resell it.){R}"
            total = price * qty
            if self.player.gold < total:
                msg = f"{C_RED}Not enough gold! {qty}x {item.name} costs {total}g.{R}"; continue
            bought = 0
            for _ in range(qty):
                if not self.player.add_item(copy.deepcopy(item)):
                    break
                bought += 1
            self.player.gold -= price * bought
            if bought:
                msg = f"{C_GREEN}Bought {bought}x {item.name} for {price*bought}g.{R}{note}"
            else:
                msg = f"{C_RED}Your bag is full!{R}"

    def _sell(self):
        # Stack-aware sell screen (the old one sold a whole stack for the
        # price of a single item)
        from game_sell import open_sell_screen
        open_sell_screen(self.player, shop_sell_multiplier=1.0)

    # ── QUEST BOARD ───────────────────────────────────────────

    def quest_board(self):
        while True:
            self._header("Quest Board")
            print(C(f"\n{menu_opt('1','Take a guild quest')}"))
            print(C(f"{menu_opt('2','Turn in completed quests')}"))
            print(C(f"{menu_opt('3','Start class awakening quest')}"))
            print(C(f"{menu_opt('4','View active quests')}"))
            print(C(f"{menu_opt('0','Leave')}"))
            ch = prompt("Choice")
            if ch == "1":   self._offer_guild_quest()
            elif ch == "2": self.player.turn_in_quests(); input(C(f"\n{C_DIM}(Press Enter){R}"))
            elif ch == "3": self.player.start_evolution_quest(); input(C(f"\n{C_DIM}(Press Enter){R}"))
            elif ch == "4": self._show_quests()
            elif ch == "0": break

    def _show_quests(self):
        clear()
        print(section("ACTIVE QUESTS"))
        print()
        any_q = False
        for q in self.player.active_quests:
            prog = q.get("progress",0); req = q.get("required",1)
            bar  = f"{C_GREEN}{'█'*prog}{C_DIM}{'░'*(req-prog)}{R}"
            print(C(f"{C_CYAN}◆{R} {C_WHITE}{q['title']}{R}"))
            print(C(f"  {C_DIM}{q['desc']}{R}"))
            print(C(f"Progress: [{bar}] {C_GOLD}{prog}/{req}{R}  "
                  f"Reward: {C_GOLD}{q['reward_gold']} gold{R}, {C_CYAN}{q['reward_exp']} EXP{R}\n"))
            any_q = True
        eq = self.player.evolution_quest
        if eq and not eq.get("done"):
            prog = eq.get("progress",0); req = eq.get("required",1)
            bar  = f"{C_ORANGE}{'█'*prog}{C_DIM}{'░'*(req-prog)}{R}"
            print(C(f"{C_ORANGE}★{R} {C_WHITE}[CLASS QUEST] {eq['title']}{R}"))
            print(C(f"  {C_DIM}{eq['desc']}{R}"))
            print(C(f"  Progress: [{bar}] {C_GOLD}{prog}/{req}{R}\n"))
            any_q = True
        if not any_q:
            print(C(f"{C_DIM}No active quests.{R}"))
        if self.player.completed_quests:
            print(C(f"\n{C_GREEN}Completed: {len(self.player.completed_quests)} quest(s){R}"))
        input(C(f"\n{C_DIM}(Press Enter){R}"))

    def _offer_guild_quest(self):
        if len(self.player.active_quests) >= 3:
            print(C(f"\n{C_RED}You already have 3 active quests. Turn some in first.{R}"))
            input(C(f"{C_DIM}(Press Enter){R}")); return
        from game_player import GUILD_QUEST_TARGETS
        target   = random.choice(GUILD_QUEST_TARGETS)
        required = random.randint(2,5)
        g,e = required*45, required*35
        quest = {"title":f"Hunt {required}x {target}","desc":f"Eliminate {required} {target}(s) for the guild.",
                 "type":"kill","target":target,"required":required,"progress":0,
                 "reward_gold":g,"reward_exp":e}
        clear()
        print(section("QUEST OFFERED"))
        print(C(f"\n{C_CYAN}◆{R} {C_WHITE}{quest['title']}{R}"))
        print(C(f"{C_DIM}{quest['desc']}{R}"))
        print(C(f"Reward: {C_GOLD}{g} gold{R}  {C_CYAN}{e} EXP{R}"))
        print(C(f"\n{menu_opt('Y','Accept quest')}"))
        print(C(f"{menu_opt('N','Decline')}"))
        if prompt("Choice").lower() == "y":
            self.player.active_quests.append(quest)
            print(C(f"\n{C_GREEN}Quest accepted!{R}"))
        else:
            print(C(f"\n{C_DIM}Declined.{R}"))
        input(C(f"{C_DIM}(Press Enter){R}"))

    # ── GUILD ─────────────────────────────────────────────────

    def adventure_guild(self):
        while True:
            self._header("Adventurers Guild")
            evo_hint = f"  {C_ORANGE}★ READY TO AWAKEN!{R}" if self.player.can_awaken() else ""
            print(C(f"\n{menu_opt('1','Rank up',       f'Current: {self.player.rank}')}"))
            clan_cur = self.player.clan or 'None'
            print(C(f"{menu_opt('2','Join / change clan', f'Current: {clan_cur}')}"))
            print(C(f"{menu_opt('3','Awaken your class', 'Evolve into your next form')}{evo_hint}"))
            print(C(f"{menu_opt('0','Leave')}"))
            ch = prompt("Choice")
            if ch == "1":   self.player.promote_rank(); input(C(f"\n{C_DIM}(Press Enter){R}"))
            elif ch == "2": self._clan_menu()
            elif ch == "3": self.player.awaken(); input(C(f"\n{C_DIM}(Press Enter){R}"))
            elif ch == "0": break

    def _clan_menu(self):
        clear()
        print(section("CLANS"))
        print()
        clan_list = list(CLANS.items())
        for i,(name,(role,col,bonus)) in enumerate(clan_list, 1):
            cur = f"  {C_GREEN}← current{R}" if self.player.clan == name else ""
            print(C(f"{menu_opt(i, name, role)}  {col}{bonus}{R}{cur}"))
        print(C(f"\n{menu_opt(0,'Cancel')}"))
        ch = prompt("Choose clan")
        if ch == "0" or not ch.isdigit(): return
        idx = int(ch)-1
        if 0 <= idx < len(clan_list):
            self.player.join_clan(clan_list[idx][0])
            col = clan_list[idx][1][1]
            print(C(f"\n{col}Welcome to the {self.player.clan}!{R}  {C_DIM}Perks: {clan_list[idx][1][2]}{R}"))
            input(C(f"{C_DIM}(Press Enter){R}"))

    # ── NPC DIALOGUE ─────────────────────────────────────────

    def talk_to_npcs(self):
        while True:
            self._header("Talk to Townsfolk")
            print(C(f"\n{C_DIM}The streets are lively. Who catches your eye?{R}\n"))
            for i, npc in enumerate(TOWNSFOLK, 1):
                print(C(f"{C_GOLD}{B}[{i:>2}]{R} {C_WHITE}{npc['icon']} {npc['name']:<24}{R}  {C_DIM}{npc['personality']}{R}"))
            print(C(f"\n{menu_opt(0,'Leave')}"))
            ch = prompt("Talk to")
            if ch == "0": break
            if not ch.isdigit(): continue
            idx = int(ch)-1
            if not (0 <= idx < len(TOWNSFOLK)): continue
            npc = TOWNSFOLK[idx]
            line = random.choice(npc["lines"])
            clear()
            print(C(f"\n{C_GOLD}{B}╔{'═'*36}╗"))
            print(C(f"║  {npc['icon']} {npc['name']:<32}║"))
            print(C(f"╚{'═'*36}╝{R}"))
            print(C(f"  {C_DIM}{npc['personality']}{R}\n"))
            print(C(f"  {C_WHITE}\"{line}\"{R}\n"))
            offer = npc.get("offer")
            if offer and offer in OFFER_RESPONSES:
                print(C(f"\n{C_CYAN}(They seem willing to share more...)"))
                print(C(f"\n{menu_opt('Y','Interact further')}"))
                print(C(f"{menu_opt('N','Just listen')}"))
                ans = input(C(f"\n{C_GOLD}>{R} ")).strip().lower()
                if ans == "y":
                    resp = random.choice(OFFER_RESPONSES[offer])
                    print(C(f"\n{C_CYAN}{resp}{R}"))
                    if offer == "blessing":
                        self.player.hp = self.player.max_hp
                        print(C(f"  {C_GREEN}Your HP is fully restored!{R}"))
            input(C(f"\n{C_DIM}(Press Enter){R}"))
            # Main story: "Speak to townsfolk in any city"
            completed = self.player.stories.on_talk("dragon_rumour", self.player)
            if completed:
                from game_stories import show_story_completion
                for stype, step in completed:
                    show_story_completion(stype, step)


    # ── CRAFTING ─────────────────────────────────────────────

    def crafting_bench(self):
        from game_items import material_counts, remove_items, inventory_add
        msg = ""
        while True:
            self._header("Crafting Bench")
            mat_count = material_counts(self.player.inventory)

            print(C(f"\n{C_CYAN}Your materials:{R}"))
            if not mat_count:
                print(C(f"{C_DIM}None. Defeat monsters and visit mines to collect materials.{R}"))
            else:
                mats = [f"{C_WHITE}{m}{R} {C_GOLD}x{q}{R}" for m, q in sorted(mat_count.items())]
                for i in range(0, len(mats), 4):
                    print(C("   ".join(mats[i:i+4])))

            print(C(f"\n{C_CYAN}Recipes:{R}  {C_DIM}([OK] craftable  [--] missing materials  [CLS] other class){R}"))
            available = []
            pc = self.player.job.name
            for rec in CRAFTING_RECIPES:
                can = all(mat_count.get(k,0) >= v for k,v in rec["needs"].items())
                cls_ok = (rec.get("classes") is None or pc in rec.get("classes",[]))
                if can and cls_ok:
                    available.append(rec)
                    mark = f"{C_GREEN}[{len(available):>2}]{R}"
                elif not cls_ok:
                    mark = f"{C_YELLOW}[CLS]{R}"
                else:
                    mark = f"{C_RED}[--]{R}"
                needs = ", ".join(
                    f"{(C_GREEN if mat_count.get(k,0) >= v else C_RED)}{k} {mat_count.get(k,0)}/{v}{R}"
                    for k,v in rec["needs"].items())
                qty = f" x{rec['qty']}" if rec.get("qty", 1) > 1 else ""
                print(C(f"{mark} {C_WHITE}{rec['name'] + qty:<22}{R} {needs}  {C_DIM}{rec.get('desc','')}{R}"))

            if msg:
                print(C(f"\n{msg}")); msg = ""
            if not available:
                print(C(f"\n{C_DIM}Nothing you can craft right now.{R}"))
                input(C(f"{C_DIM}(Press Enter){R}")); return

            print(C(f"\n{C_DIM}Type the number shown in green to craft it.{R}  {menu_opt(0,'Leave')}"))
            ch = prompt("Craft #")
            if ch == "0" or not ch.isdigit(): return
            idx = int(ch)-1
            if not (0 <= idx < len(available)): continue
            rec = available[idx]
            results = [rec["result"]() for _ in range(rec.get("qty", 1))]
            # Dry run on a copy: the old check let a full bag eat the
            # materials when a new stackable result had no stack to join
            import copy
            trial = copy.deepcopy(self.player.inventory)
            for mat_name, qty in rec["needs"].items():
                remove_items(trial, mat_name, qty)
            if not all(inventory_add(trial, copy.deepcopy(r)) for r in results):
                msg = f"{C_RED}Your bag is full — make room first.{R}"; continue
            for mat_name, qty in rec["needs"].items():
                remove_items(self.player.inventory, mat_name, qty)
            for r in results:
                self.player.add_item(r)
            msg = f"{C_GREEN}Crafted: {results[0]}{' x'+str(len(results)) if len(results) > 1 else ''}!{R}"

    # ── INVENTORY ─────────────────────────────────────────────

    def inventory_screen(self):
        from game_items import INVENTORY_LIMIT, GuildStorage, ItemStack, remove_items, use_entry
        player = self.player
        if not hasattr(player, "guild_storage"):
            player.guild_storage = GuildStorage()
        gs = player.guild_storage
        while True:
            self._header("Inventory & Storage")
            inv = player.inventory
            limit = INVENTORY_LIMIT
            print(C(f"\n{C_CYAN}EQUIPPED{R}"))
            worn = [(s, it) for s, it in player.equipped.items() if it]
            if not worn:
                print(C(f"  {C_DIM}Nothing equipped.{R}"))
            for s, it in worn:
                print(C(f"  {C_DIM}{s:<7}{R} {it.rarity_col()}{it.name:<22}{R} {C_DIM}{it.stat_line()}{R}"))
            print(C(f"\n{C_CYAN}YOUR BAG  {C_DIM}({len(inv)}/{limit} slots){R}"))
            if not inv:
                print(C(f"  {C_DIM}Empty. Defeat enemies and open chests to collect items.{R}"))
            else:
                from game_player import Player
                for i, it in enumerate(inv, 1):
                    rcol = it.rarity_col() if hasattr(it,"rarity_col") else C_WHITE
                    slot_tag = f"{C_DIM}[{it.slot}]{R}" if hasattr(it,"slot") else f"{C_DIM}[{it.item_type}]{R}"
                    stat = (f"  {C_DIM}{it.stat_line()}{R}" if hasattr(it,"stat_line")
                            else f"  {C_GREEN}{Player.describe_consumable(it)}{R}")
                    print(C(f"{C_GOLD}{B}[{i:>2}]{R} {rcol}{str(it):<26}{R} {slot_tag}{stat}"))
            print()
            print(C(f"  {C_GOLD}[E]{R}{C_DIM} Equip  {C_GOLD}[R]{R}{C_DIM} Unequip  {C_GOLD}[U]{R}{C_DIM} Use  "
                    f"{C_GOLD}[D]{R}{C_DIM} Drop  {C_GOLD}[G]{R}{C_DIM} Guild Storage  {C_GOLD}[0]{R}{C_DIM} Back{R}"))
            ch = prompt("Choice").lower()
            if ch == "0": break
            elif ch == "e": player.equip_item()
            elif ch == "r": player.unequip_item()
            elif ch == "u": player.use_inventory_item()
            elif ch == "d":
                ch2 = prompt("Drop item # (or 0 to cancel)")
                if ch2.isdigit() and 1<=int(ch2)<=len(inv):
                    it = inv[int(ch2)-1]
                    n = 1
                    if isinstance(it, ItemStack) and it.qty > 1:
                        q = prompt(f"Drop how many? (1-{it.qty}, Enter = all)")
                        n = int(q) if q.isdigit() and 1 <= int(q) <= it.qty else it.qty
                    if it.item_type == "god":
                        if prompt(f"Really drop {it.name}? It saves your life! (y/n)").lower() != "y":
                            continue
                    name = it.name
                    if isinstance(it, ItemStack):
                        remove_items(inv, name, n)
                    else:
                        inv.remove(it)
                    print(C(f"{C_DIM}Dropped {n}x {name}.{R}")); input(C(f"{C_DIM}(Enter){R}"))
            elif ch == "g":
                self._guild_storage_screen(player, gs)

    def _guild_storage_screen(self, player, gs):
        from game_items import STORAGE_LIMIT
        while True:
            clear()
            print(C(f"\n{C_GOLD}{B}══  GUILD STORAGE  ══{R}  {C_DIM}({len(gs.items)}/{STORAGE_LIMIT} slots  ·  {gs.DEPOSIT_FEE}g/item deposit){R}\n"))
            if not gs.items:
                print(C(f"  {C_DIM}Empty. Store items here to free up bag space.{R}"))
            else:
                for i, it in enumerate(gs.items, 1):
                    rcol = it.rarity_col() if hasattr(it,"rarity_col") else C_WHITE
                    stat = f"  {C_DIM}{it.stat_line()}{R}" if hasattr(it,"stat_line") else ""
                    print(C(f"{C_GOLD}{B}[{i:>2}]{R} {rcol}{str(it):<26}{R}{stat}"))
            print()
            print(C(f"  {C_GOLD}[W]{R}{C_DIM} Withdraw  {C_GOLD}[S]{R} Store from bag  {C_GOLD}[0]{R} Back{R}"))
            ch = prompt("Choice").lower()
            if ch == "0": break
            elif ch == "w":
                ch2 = prompt("Withdraw slot # (0=cancel)")
                if ch2.isdigit() and 1<=int(ch2)<=len(gs.items):
                    ok, msg = gs.withdraw(int(ch2)-1, player)
                    print(C(f"{C_GREEN if ok else C_RED}{msg}{R}")); input(C(f"{C_DIM}(Enter){R}"))
            elif ch == "s":
                if not player.inventory:
                    print(C(f"{C_DIM}Your bag is empty.{R}")); input(C(f"{C_DIM}(Enter){R}")); continue
                for i,it in enumerate(player.inventory,1):
                    print(C(f"  {C_GOLD}[{i}]{R} {it}"))
                ch2 = prompt("Store bag slot # (0=cancel)")
                if ch2.isdigit() and 1<=int(ch2)<=len(player.inventory):
                    it = player.inventory[int(ch2)-1]
                    ok, msg = gs.deposit(it, player)
                    if ok: player.inventory.pop(int(ch2)-1)
                    print(C(f"{C_GREEN if ok else C_RED}{msg}{R}")); input(C(f"{C_DIM}(Enter){R}"))


    # ── MAIN LOOP ─────────────────────────────────────────────

    def enter(self):
        self.player.location_name = self.town_name
        while True:
            self._header(f"Region: {self.region_name}")
            print()
            # Two columns keep the whole menu on screen even on short terminals
            left = [
                menu_opt('1', T('town.inn'),        T('town.inn_cost', cost=max(5,10+self.player.level*2))),
                menu_opt('2', T('town.shop'),       'Buy & sell'),
                menu_opt('3', T('town.quest_board'), f'Active: {len(self.player.active_quests)}/3'),
                menu_opt('4', T('town.guild'),      'Rank, clan, awaken'),
                menu_opt('5', T('town.talk'),       'NPC dialogue'),
                menu_opt('6', T('town.crafting'),   'Craft gear'),
                menu_opt('7', T('town.status'),     'Character sheet'),
                menu_opt('8', T('town.inventory'),  'Bag & equipment'),
            ]
            right = [
                menu_opt('R', T('town.recruit'),    'Party & clan'),
                menu_opt('T', T('town.trade'),      'Barter'),
                menu_opt('C', 'Customise',          'Look & style perk'),
                menu_opt('H', T('town.base'),       'Your base'),
                menu_opt('K', T('town.codex'),      'Encyclopedia'),
                menu_opt('S', T('town.save'),       'Save to a slot'),
            ]
            if self._ship:
                right.append(menu_opt('V', 'Board Ship', 'Sail away'))
            right.append(menu_opt('0', T('town.leave'), 'Back to the map'))
            from game_term import _vis
            colw = max(_vis(x) for x in left) + 4
            for i in range(max(len(left), len(right))):
                l = left[i] if i < len(left) else ""
                r_ = right[i] if i < len(right) else ""
                print(C(l + " " * (colw - _vis(l)) + r_))

            if self.player.can_awaken():
                print(C(f"\n{C_ORANGE}{B}★  Your class awakening is ready! Visit the Guild [4].  ★{R}"))

            ch = prompt("Choice").lower()
            if ch == "1":   self.inn()
            elif ch == "2": self.shop()
            elif ch == "3": self.quest_board()
            elif ch == "4": self.adventure_guild()
            elif ch == "5": self.talk_to_npcs()
            elif ch == "6": self.crafting_bench()
            elif ch == "7":
                clear(); self.player.show_status(); input(C(f"\n{C_DIM}(Press Enter){R}"))
            elif ch == "8": self.inventory_screen()
            elif ch == "s": self._save_game()
            elif ch == "r":
                if self._companion_cb:
                    self._companion_cb()
                else:
                    print(C(f"\n{C_DIM}No adventurers for hire here.{R}"))
                    input(C(f"{C_DIM}(Press Enter){R}"))
            elif ch == "h":
                self._base_menu()
            elif ch == "t":
                from game_trading import open_trader_in_town
                open_trader_in_town(self.player, self.town_name)
            elif ch == "k":
                from game_codex import open_encyclopedia
                open_encyclopedia(self.player)
            elif ch == "c":
                # (a second, unreachable [C] entry used to call a function
                #  that doesn't exist — choosing it crashed the game)
                from game_customise import open_customise
                open_customise(self.player)
            elif ch == "v":
                if self._ship and self._world_map and self._ship_player:
                    if self._world_map._board_ship(self._ship_player, self._ship):
                        return   # sailed away — leave the town
                else:
                    print(C(f"\n{C_DIM}No ship available here.{R}"))
                    input(C(f"{C_DIM}(Enter){R}"))
            elif ch in ("0", "q"):
                return
            elif ch == "":
                continue


    def _base_menu(self):
        """Open the player base menu for this town's continent."""
        from game_base import BaseMenu, buy_plot_in_city
        player = self.player
        cid = getattr(self, '_continent_id', 'A')
        bx  = getattr(self, '_base_x', 0)
        by  = getattr(self, '_base_y', 0)
        if hasattr(player, 'bases') and player.bases.has_base(cid):
            base = player.bases.get_base(cid)
            BaseMenu(player, base).enter()
        else:
            buy_plot_in_city(player, self.town_name, cid, bx, by)


# ═══════════════════════════════════════════════════════════════
# TIME
# ═══════════════════════════════════════════════════════════════

def pass_day(player):
    """One night's rest at an inn or base: the player's clan earns income."""
    clan = getattr(player, "owned_clan", None)
    if clan:
        earned = clan.tick(1)
        print(C(f"{C_GOLD}Your clan '{clan.name}' earned {earned}g today "
                f"(collect it from the Clan menu).{R}"))


# Dungeons live in game_dungeon.py (multi-floor). Kept for old imports.
def Dungeon(name, danger=2, player_level=1, has_boss=False, boss_override=None, **_):
    from game_dungeon import DungeonManager
    return DungeonManager(name, danger=danger,
                          boss_name=(boss_override if has_boss else None))
