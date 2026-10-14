"""game_capital.py — Valdmere, the white royal city of Aeloria, and the
kingdom story "The Crown's Plea".

This module owns:
  * registration + world placement of ALL THREE castles (Valdmere here, the
    Duskthorn Citadel and the Sunspire Kasbah live in game_castles.py);
  * the walkable royal city of Valdmere, the keep of Castle Lumeris and the
    undercroft / crypt beneath it;
  * KINGDOM_STORY_ID / KINGDOM_STORY (registered into MAIN_STORIES by
    game_stories) and story_lines(npc_id, player) for story-aware dialogue;
  * small helpers shared with game_castles (CastleScene, set_flag, bosses,
    rewards, title banners).

All persistent state lives in player.flags under "valdmere_*", "crowns_*"
(kingdom story) keys.  Python standard library only.
"""

from __future__ import annotations

import random

from game_term import C, W, H, clr, draw_frame, _vis
from game_scene import (Scene, Entity, Tile, fg, parse_map, R_, B_, C_GOLD,
                        C_DIM, C_WHITE, C_RED, C_GREEN, C_CYAN, C_PURP, _wrap)

# ── palette ──────────────────────────────────────────────────────
STONE = (170, 170, 180)
WHITE = (235, 235, 245)
PURPLE = (160, 90, 220)
LILAC = (200, 140, 255)
GOLDC = (255, 205, 90)

C_STONE = fg(*STONE)
C_MARBLE = fg(*WHITE)
C_ROYAL = fg(*PURPLE)
C_LILAC = fg(*LILAC)
C_GILT = fg(*GOLDC)

KINGDOM_STORY_ID = "crowns_plea"
CAPITAL_NAME = "Valdmere"
CAPITAL_GLYPH = "K"


def _T(rgb, glyph, walk=True, name="", dark=False):
    return Tile(fg(*rgb), glyph, walk, name, dark)


# ═════════════════════════════════════════════════════════════════
#  SHARED HELPERS (also used by game_castles)
# ═════════════════════════════════════════════════════════════════

def pflags(player):
    """player.flags, created if an ancient save lacks it."""
    f = getattr(player, "flags", None)
    if not isinstance(f, dict):
        f = {}
        try:
            player.flags = f
        except Exception:
            pass
    return f


def kingdom_index(player):
    """-1 if The Crown's Plea isn't the active main story, len(steps) when it
    is complete, otherwise the index of the current step."""
    st = getattr(player, "stories", None)
    if st is None or getattr(st, "main_story_id", None) != KINGDOM_STORY_ID:
        return -1
    if getattr(st, "main_complete", False):
        return len(KINGDOM_STORY["steps"])
    return int(getattr(st, "main_step_idx", 0) or 0)


def kingdom_step(player):
    """Current step id ('cp_audience', ...), 'done', or None if inactive."""
    i = kingdom_index(player)
    if i < 0:
        return None
    steps = KINGDOM_STORY["steps"]
    return "done" if i >= len(steps) else steps[i]["id"]


def kingdom_at_least(player, step_id):
    """True once the story has reached (or passed) step_id."""
    i = kingdom_index(player)
    return i >= 0 and i >= STEP_INDEX.get(step_id, 99)


def kingdom_past(player, step_id):
    """True once step_id has been completed."""
    i = kingdom_index(player)
    return i >= 0 and i > STEP_INDEX.get(step_id, 99)


def _fallback_check_flags(player):
    """Used only when StoryManager has no check_flags (pre-merge builds):
    completes current main-story 'flag' / 'choice' steps whose flag is set."""
    st = getattr(player, "stories", None)
    out = []
    if st is None:
        return out
    for _ in range(4):
        step = st.get_main_step() if hasattr(st, "get_main_step") else None
        if not step or step.get("type") not in ("flag", "choice"):
            break
        if not pflags(player).get(step.get("target")):
            break
        st.main_progress = 1
        out.append(("main", step))
        player.gold += step.get("reward_gold", 0)
        try:
            player.gain_exp(step.get("reward_exp", 0))
        except Exception:
            pass
        st.advance_main()
    return out


def check_flags(player):
    st = getattr(player, "stories", None)
    if st is None:
        return []
    try:
        if hasattr(st, "check_flags"):
            return st.check_flags(player) or []
        return _fallback_check_flags(player)
    except Exception:
        return []


def show_completions(completed, scene=None, world=None):
    """Display story completions the way the world map does."""
    if not completed:
        return

    def _show():
        if world is not None and hasattr(world, "_handle_story_completions"):
            world._handle_story_completions(completed)
        else:
            from game_stories import show_story_completion
            for stype, step in completed:
                show_story_completion(stype, step)
    try:
        if scene is not None:
            scene.modal(_show)
            scene.message(f"{C_GOLD}★ Story updated!{R_}")
        else:
            _show()
    except Exception:
        pass


def set_flag(player, key, value=True, scene=None, world=None):
    """Set a persistent flag and resolve any story steps waiting on it."""
    pflags(player)[key] = value
    done = check_flags(player)
    if done:
        show_completions(done, scene, world or getattr(scene, "world", None))
    return done


def make_boss(name, player, power=1.3):
    """Boss from the BOSSES agent's table, or a scaled stand-in."""
    lvl = max(1, getattr(player, "level", 1))
    try:
        from game_enemies import create_boss, BOSS_DEFS
        b = create_boss(name, lvl)
        if name not in BOSS_DEFS:
            b.max_hp = b.hp = int(b.max_hp * power)
            b.atk = int(b.atk * (power ** 0.5))
            b.exp_reward = int(b.exp_reward * power)
            b.gold_reward = int(b.gold_reward * power)
        b.name = name
        return b
    except Exception:
        from game_enemies import generate_enemy
        e = generate_enemy("dungeon_bottom", 5, lvl, name=name)
        e.max_hp = e.hp = int(e.max_hp * 3 * power)
        e.atk = int(e.atk * 1.3)
        return e


def make_elite(name, player, zone="dungeon_deep", danger=3, mult=1.0):
    from game_enemies import generate_enemy
    e = generate_enemy(zone, danger, max(1, getattr(player, "level", 1)), name=name)
    if mult != 1.0:
        e.max_hp = e.hp = max(1, int(e.max_hp * mult))
        e.atk = max(1, int(e.atk * (mult ** 0.5)))
        e.exp_reward = int(e.exp_reward * mult)
        e.gold_reward = int(e.gold_reward * mult)
    return e


# Unique gear the castles hand out.  game_items.make_item (ITEMS agent) is
# asked first so a richer definition wins; these are the fallbacks.
_GEAR = {
    "Lumeris, Blade of the White Crown": dict(slot="weapon", atk_bonus=34, mp_bonus=20, hp_bonus=30,
                                              rarity="legendary", sell_value=2400,
                                              description="Forged for Valdmere's first king; its edge hums with ward-light."),
    "Aegis of the Pale Tower": dict(slot="shield", def_bonus=20, hp_bonus=60, rarity="epic", sell_value=1200,
                                    description="A kite shield of white steel inlaid with amethyst."),
    "Signet of the Crown": dict(slot="ring", atk_bonus=6, def_bonus=6, mp_bonus=15, rarity="epic", sell_value=900,
                                description="The royal signet. Guards bow when they see it."),
    "Moonsilver Pendant": dict(slot="amulet", mp_bonus=30, def_bonus=4, rarity="rare", sell_value=420,
                               description="A blessing of the Temple of the Moon."),
    "Royal Guard Cloak": dict(slot="cloak", def_bonus=7, hp_bonus=25, rarity="rare", sell_value=300,
                              description="Purple wool lined with grey silk."),
    "Kharzul's Oathbrand": dict(slot="weapon", atk_bonus=40, hp_bonus=-20, rarity="legendary", sell_value=2600,
                                description="A black blade that drinks its wielder's fear. Cursed."),
    "Hellforged Mail": dict(slot="armor", def_bonus=22, hp_bonus=40, stealth_bonus=-2, rarity="epic",
                            sell_value=1300, description="Armour cooled in lava. It is always warm. Cursed."),
    "Crown of Cinders": dict(slot="helmet", atk_bonus=12, mp_bonus=25, def_bonus=4, rarity="legendary",
                             sell_value=2200, description="Kharzul's own circlet, still smouldering."),
    "Ember Pact Ring": dict(slot="ring", atk_bonus=10, hp_bonus=-10, rarity="epic", sell_value=800,
                            description="The mark of the pact. Demons nod as you pass. Cursed."),
    "Duskthorn Greatsword": dict(slot="weapon", atk_bonus=28, rarity="epic", sell_value=1100,
                                 description="Taken from the Demon Knights' armoury."),
    "Djinn-Glass Talisman": dict(slot="amulet", mp_bonus=35, atk_bonus=6, rarity="legendary", sell_value=2000,
                                 description="A shard of Azhar's prison, full of trapped wind."),
    "Sultan's Silk Cloak": dict(slot="cloak", def_bonus=6, stealth_bonus=3, hp_bonus=20, rarity="rare",
                                sell_value=380, description="Cool as shade at noon."),
    "Matriarch's Stinger": dict(slot="weapon", atk_bonus=24, rarity="epic", sell_value=900,
                                description="A dagger carved from the Scorpion Matriarch's tail. Venomous."),
    "Sunspire Scimitar": dict(slot="weapon", atk_bonus=20, stealth_bonus=1, rarity="rare", sell_value=520,
                              description="A curved blade from the Kasbah armoury."),
}


def build_gear(name):
    d = _GEAR.get(name)
    if not d:
        return None
    from game_items import Equipment
    d = dict(d)
    return Equipment(name, d.pop("slot"), **d)


def make_reward(name):
    """An item instance by name: make_item → our gear → ITEM_POOL."""
    try:
        import game_items
        mk = getattr(game_items, "make_item", None)
        if mk:
            it = mk(name)
            if it is not None:
                return it
        it = build_gear(name)
        if it is not None:
            return it
        f = game_items.ITEM_POOL.get(name)
        return f() if f else None
    except Exception:
        return None


def give_item(player, name, qty=1, scene=None):
    """Give qty of an item. Returns the number actually given."""
    n = 0
    for _ in range(max(1, qty)):
        it = make_reward(name)
        if it is None:
            break
        try:
            if not player.add_item(it):
                break
        except Exception:
            break
        n += 1
    if scene is not None and n:
        scene.message(f"{C_GOLD}Received {name}{' x%d' % n if n > 1 else ''}!{R_}")
    return n


def try_recruit(player, companion_id, scene=None, cost=None):
    """Offer a specific companion (COMPANIONS agent API). False if unavailable."""
    try:
        from game_party import offer_recruit
    except Exception:
        if scene is not None:
            scene.message(f"{C_DIM}(They cannot join you yet.){R_}")
        return False
    try:
        if scene is not None:
            return bool(scene.modal(offer_recruit, player, companion_id, scene=None, cost=cost))
        return bool(offer_recruit(player, companion_id, scene=None, cost=cost))
    except TypeError:
        try:
            return bool(offer_recruit(player, companion_id))
        except Exception:
            return False
    except Exception:
        return False


def has_companion(player, companion_id):
    try:
        for m in player.party.members:
            if getattr(m, "cid", None) == companion_id or getattr(m, "id", None) == companion_id \
                    or getattr(m, "companion_id", None) == companion_id:
                return True
    except Exception:
        pass
    return False


def wait_key():
    try:
        from game_input import _getch
        return _getch() or ""
    except Exception:
        try:
            return (input() or "\n")[:1]
        except (EOFError, KeyboardInterrupt):
            return "\x1b"


def show_banner(art, title_lines, colours, subtitle="", note=""):
    """Full-screen title card: art lines (keys→colour via `colours`
    callable(ch,x,y)->ansi or plain str colour) + caption.  Waits for a key."""
    rows = H()
    out = []
    pad_top = max(0, (rows - len(art) - len(title_lines) - 6) // 2)
    out.extend([""] * pad_top)
    for y, line in enumerate(art):
        if callable(colours):
            seg, last = [], None
            for x, ch in enumerate(line):
                col = colours(ch, x, y)
                if col != last:
                    seg.append(R_ + col)
                    last = col
                seg.append(ch)
            out.append(C("".join(seg) + R_))
        else:
            out.append(C(f"{colours}{line}{R_}"))
    out.append("")
    for t in title_lines:
        out.append(C(t))
    if subtitle:
        out.append(C(f"{C_DIM}{subtitle}{R_}"))
    if note:
        out.append("")
        for chunk in _wrap(note, 70):
            out.append(C(f"{C_WHITE}{chunk}{R_}"))
    out.append("")
    out.append(C(f"{C_DIM}(press any key){R_}"))
    clr()
    draw_frame(out)
    wait_key()
    clr()


class CastleScene(Scene):
    """Scene with story-aware dialogue that surfaces story completions
    (the base Scene only flashes 'Story updated')."""

    def __init__(self, *a, **kw):
        self.world = kw.pop("world", None)
        super().__init__(*a, **kw)

    def _talk(self, ent, player):
        st = getattr(player, "stories", None)
        done = []
        if st is not None and ent.npc_id and hasattr(st, "on_talk"):
            try:
                done = st.on_talk(f"npc:{ent.npc_id}", player) or []
            except TypeError:
                try:
                    done = st.on_talk(f"npc:{ent.npc_id}") or []
                except Exception:
                    done = []
            except Exception:
                done = []
        if done:
            show_completions(done, self, self.world)
        if self.result is not None:
            return
        if ent.interact:
            try:
                msg = ent.interact(self, player, ent)
            except Exception as e:      # never crash the game over dialogue
                _log(f"interact {ent.name}: {e!r}")
                msg = None
            if msg:
                self.message(msg)
            return
        lines = None
        if ent.npc_id:
            try:
                lines = story_lines(ent.npc_id, player)
            except Exception:
                lines = None
            if not lines and st is not None and hasattr(st, "npc_dialogue"):
                try:
                    lines = st.npc_dialogue(ent.npc_id, player)
                except Exception:
                    lines = None
        if lines:
            for line in (lines if isinstance(lines, (list, tuple)) else [lines]):
                self.talk_box(ent, line, player)
        else:
            self.talk_box(ent, None, player)

    def say_lines(self, ent, lines, player=None):
        for line in lines:
            self.talk_box(ent, line, player or self.player)

    def fight_enemy(self, player, enemy, first_strike=False, allow_escape=True):
        """fight() that never raises; returns 'victory'|'defeat'|'escaped'."""
        try:
            res = self.fight(player, enemy, first_strike=first_strike, allow_escape=allow_escape)
        except Exception as e:
            _log(f"fight {getattr(enemy, 'name', '?')}: {e!r}")
            res = "escaped"
        if res == "defeat" or not player.is_alive():
            self.result = "defeat"
            return "defeat"
        return res


def _log(msg):
    try:
        import os
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
            f.write(f"game_capital: {msg}\n")
    except Exception:
        pass


def lines_with_story(npc_id, player, default):
    try:
        s = story_lines(npc_id, player)
    except Exception:
        s = None
    return list(s) if s else list(default)


def pick(lines):
    return random.choice(lines) if lines else "..."


# ═════════════════════════════════════════════════════════════════
#  THE CROWN'S PLEA — kingdom story
# ═════════════════════════════════════════════════════════════════

def _s(sid, title, desc, typ, target, gold, exp, text, required=1):
    return {"id": sid, "title": title, "desc": desc, "type": typ, "target": target,
            "required": required, "reward_gold": gold, "reward_exp": exp,
            "completion_text": text}


KINGDOM_STORY = {
    "title": "The Crown's Plea",
    "colour": fg(*LILAC),
    "icon": "♛",
    "intro": (
        "Valdmere, the white city of Aeloria, is dimming. The ward-light that has "
        "shielded its walls for four hundred years flickers like a dying candle, and "
        "King Aldren IV grows weaker by the day. A royal herald finds you on the road "
        "with a sealed letter: the Crown has need of a sword it can trust."
    ),
    "steps": [
        _s("cp_summons", "The Royal Summons",
           "Travel to Valdmere, the white city of Aeloria, and present the King's letter.",
           "visit", CAPITAL_NAME, 50, 120,
           "The Grand Gate opens before you. Purple banners stir over white walls, and "
           "the herald bows: 'His Majesty will receive you in Castle Lumeris at once.'"),
        _s("cp_audience", "Audience at Castle Lumeris",
           "Enter the keep and kneel before King Aldren IV in the throne room.",
           "talk", "npc:king_aldren", 120, 220,
           "'Rise, traveller. Valdmere's wards are failing, and I with them. Since the "
           "coronation feast I have worn the Crown of Lumeris and felt it drink from me. "
           "Speak with my Archmage, Ilvaris. Find who has done this to my realm.'"),
        _s("cp_archmage", "The Fading Wards",
           "Speak with Royal Archmage Ilvaris in the throne room.",
           "talk", "npc:archmage_ilvaris", 80, 260,
           "'The wards are being siphoned, not merely failing. The thread leads to the "
           "Starfall Tower: my former apprentice, Veyl, who vanished a season ago. The "
           "Royal Library holds a codex on crown-curses. Read it.'"),
        _s("cp_codex", "The Forbidden Codex",
           "Ask Librarian Quill for access and read the Forbidden Codex in the Royal Library.",
           "flag", "valdmere_clue_codex", 60, 300,
           "The codex describes a 'Hollow Crown': a circlet that drains a bloodline and "
           "pours its strength into whoever holds the other end of the chain. The page "
           "about breaking it has been cut out, very neatly."),
        _s("cp_informant", "Whispers in Lantern Alley",
           "Find Wren, an informant who trades secrets in the dark of Lantern Alley.",
           "talk", "npc:informant_wren", 150, 300,
           "Wren grins in the dark: 'Veyl's acolytes stole the Starfall Sigil, the key "
           "to his tower's seal, and holed up in Blackroot Crypt. Bring it back and the "
           "tower opens for you. Mind the pickpockets on your way out.'"),
        _s("cp_sigil", "The Starfall Sigil",
           "Clear Blackroot Crypt in Aeloria and recover the Starfall Sigil.",
           "dungeon", "Blackroot Crypt", 300, 600,
           "At the bottom of the crypt, among guttered candles, lies a disc of star-iron "
           "engraved with Valdmere's crest. The Starfall Sigil is yours."),
        _s("cp_veyl", "The Unbound",
           "Use the Sigil to open the Starfall Tower at the Royal Academy and defeat Archmage Veyl.",
           "kill", "Archmage Veyl the Unbound", 500, 900,
           "Veyl falls, laughing through blood: 'Fool... I stole the ward-light to STARVE "
           "the crown, not feed it. Ask who brought it to court. It came from the "
           "desert — from the Sultan's vault at Sunspire.'"),
        _s("cp_sands", "The Road to Sunspire",
           "Sail to the Ash Sands and find the Sunspire Kasbah.",
           "visit", "Sunspire Kasbah", 200, 500,
           "Sandstone towers shimmer above palm gardens and a still blue oasis. Music "
           "drifts over the walls. It is very hard to believe anything evil came from here."),
        _s("cp_sultan", "Tea with the Sultan",
           "Ask Sultan Rahzim about the crown that left his vault.",
           "talk", "npc:sultan_rahzim", 250, 600,
           "'A circlet of white gold? Sold eleven months ago to a Valdmeran envoy. He "
           "carried a chancellor's seal. My vault djinn, Azhar, witnessed the sale and "
           "keeps the Dawnglass Shard — the only thing that can crack such a crown. He "
           "will not give it up politely.'"),
        _s("cp_djinn", "The Djinn's Shard",
           "Descend into the Sunspire vault and defeat the Sand Djinn Azhar for the Dawnglass Shard.",
           "kill", "Sand Djinn Azhar", 600, 1100,
           "The storm collapses into glittering glass. Inside lies the Dawnglass Shard, "
           "and Azhar's last whisper: 'The crown was forged in Duskthorn, in demonfire. "
           "Only its maker can unmake it — or his death will cut its anchor.'"),
        _s("cp_demon", "The Demon's Due",
           "Reach the Duskthorn Citadel in Ironspire. Make a pact with Demon Lord Kharzul, or storm his throne.",
           "choice", "crowns_demon_resolved", 500, 1300,
           "Duskthorn has given its answer. Whatever you decided there, the Hollow Crown "
           "has lost its anchor in the fire. Return to Valdmere — before its holder notices."),
        _s("cp_queen", "The Queen's Secret",
           "Return to Castle Lumeris and speak with Queen Seraphine.",
           "talk", "npc:queen_seraphine", 300, 700,
           "'It was Morvane,' the Queen says quietly. 'Our Lord Chancellor gave the crown "
           "as a coronation gift. Tonight he named himself Regent and went down into the "
           "Crypt of Kings with the chain-key. End this.'"),
        _s("cp_regent", "The Hollow Regent",
           "Descend beneath the castle, open the Crypt of Kings and defeat the Hollow Regent.",
           "kill", "The Hollow Regent", 1200, 2200,
           "The Hollow Crown shatters against the Dawnglass Shard. Morvane's hollow shape "
           "crumbles to ash, and far above, every ward in Valdmere blazes white again."),
        _s("cp_crowned", "Long Live the King",
           "Return to the throne room and stand before King Aldren IV.",
           "talk", "npc:king_aldren", 2000, 2500,
           "The court kneels — to you. 'By my hand and my restored crown, rise, "
           "Knight-Protector of Valdmere.' The treasury is opened in your honour, and "
           "Princess Elowen steps down from the dais with a question in her eyes."),
    ],
}

STEP_INDEX = {s["id"]: i for i, s in enumerate(KINGDOM_STORY["steps"])}


def story_lines(npc_id, player):
    """Story-aware dialogue for castle NPCs (kingdom story + castle side
    quests).  Returns a list of lines or None.  Called by our scenes and may
    be called by game_stories.npc_dialogue()."""
    if not npc_id:
        return None
    f = pflags(player)
    k = kingdom_step(player)
    pact = bool(f.get("demon_pact"))
    war = bool(f.get("demon_war"))
    title = f.get("valdmere_title")

    if npc_id == "king_aldren":
        if k == "done" or title:
            return ["Rise, Knight-Protector. While I breathe, Valdmere's gates and treasury are yours.",
                    "My daughter tells me you two have been plotting adventures. I pretend not to hear."]
        if k in ("cp_summons", "cp_audience"):
            return ["Ah — the one my herald found. Come closer. The court will wait."]
        if k == "cp_archmage":
            return ["Speak with Ilvaris; she stands at my left hand. She has watched the wards since I was a boy."]
        if k in ("cp_codex", "cp_informant", "cp_sigil", "cp_veyl"):
            return ["Every day the crown sits heavier. Do not let my weakness hurry you into error.",
                    "If my Archmage says Veyl is behind this, then find Veyl. Valdmere's gold is at your disposal."]
        if k in ("cp_sands", "cp_sultan", "cp_djinn"):
            return ["Sunspire? Sultan Rahzim and I traded poems once, and insults. He is honest — in his way."]
        if k == "cp_demon":
            return ["Duskthorn. My forebears never set foot there and came back. Do what you must.",
                    "I will not ask what bargains a demon offers. Only that you return."]
        if k == "cp_queen":
            return ["My Queen wished to speak with you. She has been... quieter than usual."]
        if k == "cp_regent":
            return ["Morvane? He sat at my council for twenty years. Go. Bring me his crown or his head."]
        if k == "cp_crowned":
            return ["Kneel."]
        return None

    if npc_id == "queen_seraphine":
        if k == "cp_queen":
            return ["Come. Not here — the walls have ears. ...Very well, here then."]
        if k == "cp_regent":
            return ["The crypt lies beneath the guard room. The gaoler will open the way — tell him I sent you."]
        if k == "done" or title:
            return ["Valdmere sings again. I had forgotten how bright the wards were."]
        return None

    if npc_id == "archmage_ilvaris":
        if k == "cp_codex":
            return ["The Royal Library is through the west door of the throne room. Ask Quill for the Forbidden Codex."]
        if k == "cp_informant":
            return ["A cut page... Then someone at court knew what that book held. Find out who. Try the alleys — gossip runs downhill."]
        if k == "cp_sigil":
            return ["Blackroot Crypt lies in the old woods of Aeloria. Bring the Sigil and I will tell the tower to open."]
        if k == "cp_veyl":
            return ["With the Sigil the Starfall Tower will open for you. It stands beside the Academy, to the north-west.",
                    "Veyl was my brightest student. Do not hesitate because of that."]
        if kingdom_past(player, "cp_veyl") and k not in ("done", None):
            return ["Veyl was not feeding on the wards... he was starving the crown. I was blind. Follow the thread to its end."]
        return None

    if npc_id == "princess_elowen":
        if k is None:
            return ["Have you seen the Academy's tower at night? The stars come down to meet it. Father says I study too much."]
        if k == "done" or title:
            return ["You did what all of Father's knights could not. I have a question for you, when you are ready."]
        if k == "cp_demon" and not pact and not war:
            return ["If you go to Duskthorn... a demon who keeps his word is more dangerous than one who doesn't. Remember that."]
        return ["The crown frightens me. Father smiles when he wears it, but only with his mouth."]

    if npc_id == "chancellor_morvane":
        if k in ("cp_queen", "cp_regent"):
            return None
        if k in ("cp_codex", "cp_informant"):
            return ["Cut pages? Mice, I expect. The library has a dreadful mouse problem.",
                    "Do report your findings to me first. His Majesty must not be troubled."]
        if k and k != "done":
            return ["The realm's ledgers do not balance themselves, adventurer. Be brief.",
                    "The crown was a gift of goodwill. Do not let anyone tell you otherwise."]
        return None

    if npc_id == "lord_commander":
        if war:
            return ["You stormed Duskthorn? Then you have my respect, and the respect of every blade in Valdmere."]
        if pact:
            return ["You smell of brimstone. My guards watch you, and so do I. Give me a reason, and they will act."]
        return None

    if npc_id == "informant_wren":
        if k == "cp_informant":
            return None
        if k in ("cp_sigil",):
            return ["Blackroot Crypt. West of here, in the old woods. Go on, shoo."]
        return ["Secrets cost coin, friend. Today I'm fresh out of secrets worth yours."]

    if npc_id == "sultan_rahzim":
        if k == "cp_djinn":
            return ["The vault is beneath the courtyard. Azhar will not like you. He does not like anyone. Take this — sweet tea for courage."]
        if k == "cp_demon":
            return ["Duskthorn? Ah. Bring a cloak. And perhaps a priest."]
        return None

    if npc_id == "demon_kharzul":
        if k == "cp_demon" and not pact and not war:
            return ["You carry the stench of my forefathers' crown. So the Hollow Crown has found a fool to wear it, and another fool to come asking."]
        return None

    if npc_id == "herald_pell":
        if k == "cp_summons" or k == "cp_audience":
            return ["You carry the King's letter! The keep lies straight up the Grand Avenue, past the Royal Gardens."]
        if title:
            return ["Make way! Make way for the Knight-Protector of Valdmere!"]
        return None
    return None


# ═════════════════════════════════════════════════════════════════
#  WORLD REGISTRATION + PLACEMENT
# ═════════════════════════════════════════════════════════════════

def _arrive_capital(loc):
    return (f"{C_MARBLE}{B_}♛ {loc['name']}{R_} {C_LILAC}— the white royal city of Aeloria.{R_} "
            f"{C_DIM}[E] to enter.{R_}")


def _enter_capital(world, player, loc, autosave=None):
    enter_valdmere(world, player, loc, autosave)


try:
    from game_world import register_place_type as _reg
    _reg("capital", CAPITAL_GLYPH, fg(235, 235, 250) + B_, "Royal City",
         enter=_enter_capital, arrive=_arrive_capital, symbol="♛")
except Exception:          # world module unavailable (tests / tools)
    pass


def _free_spot(world, x, y, gap):
    for l in world.locations:
        if abs(l["x"] - x) <= gap and abs(l["y"] - y) <= gap:
            return False
    return True


def _land_ok(world, x, y):
    from game_world import OCEAN, SHALLOWS
    return world.terrain[y][x] not in (OCEAN, SHALLOWS)


def surround_score(world, x, y, terrains, r=2):
    """Negative count of `terrains` tiles around (x,y): lower = more nestled."""
    from game_world import WIDTH, HEIGHT
    n = 0
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            yy, xx = y + dy, x + dx
            if 0 <= yy < HEIGHT and 0 <= xx < WIDTH and world.terrain[yy][xx] in terrains:
                n += 1
    return -n


def find_site(world, rng, cont, terrains, gap=4, near=None, ideal=0, spread=6, inland=0,
              avoid=None, score_fn=None):
    """Pick a deterministic site on continent `cont` with terrain in
    `terrains`, at least `gap` tiles from any location, preferring a
    distance of `ideal` from `near`.  Returns (x, y) or None."""
    from game_world import WIDTH, HEIGHT, OCEAN, SHALLOWS
    cands = []
    for y in range(2, HEIGHT - 2):
        row = world.terrain[y]
        crow = world.cont_map[y]
        for x in range(2, WIDTH - 2):
            if crow[x] != cont or row[x] not in terrains:
                continue
            if avoid and (x, y) in avoid:
                continue
            # needs walkable neighbours so the player can step on and off
            nb = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                     if world.terrain[y + dy][x + dx] not in (OCEAN, SHALLOWS))
            if nb < 3:
                continue
            if inland:
                wet = False
                for dy in range(-inland, inland + 1):
                    for dx in range(-inland, inland + 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < HEIGHT and 0 <= xx < WIDTH and world.terrain[yy][xx] in (OCEAN, SHALLOWS):
                            wet = True
                            break
                    if wet:
                        break
                if wet:
                    continue
            if not _free_spot(world, x, y, gap):
                continue
            if near is not None:
                d = abs(x - near[0]) + abs(y - near[1])
                score = abs(d - ideal)
            else:
                score = 0
            if score_fn is not None:
                score += score_fn(x, y)
            cands.append((score, y, x))
    if not cands:
        return None
    cands.sort()
    best = cands[: max(1, spread)]
    _, y, x = best[rng.randrange(len(best))]
    return x, y


def connect_to_road(world, x, y, max_len=30):
    """Lay a road from (x,y) to the nearest existing road, over open land
    only (never through locations or water).  No RNG involved."""
    from game_world import WIDTH, HEIGHT, ROAD, PLAINS, HILL, FOREST, SAND
    open_t = (PLAINS, HILL, FOREST, SAND, ROAD)
    taken = {(l["x"], l["y"]) for l in world.locations}
    prev = {(x, y): None}
    q = [(x, y)]
    hit = None
    for cur in q:
        cx, cy = cur
        if cur != (x, y) and world.terrain[cy][cx] == ROAD:
            hit = cur
            break
        if abs(cx - x) + abs(cy - y) > max_len:
            continue
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT) or (nx, ny) in prev:
                continue
            if (nx, ny) in taken or world.terrain[ny][nx] not in open_t:
                continue
            if world.cont_map[ny][nx] != world.cont_map[y][x]:
                continue
            prev[(nx, ny)] = cur
            q.append((nx, ny))
    if not hit:
        return False
    p = prev[hit]
    while p is not None and p != (x, y):
        px, py = p
        world.terrain[py][px] = ROAD
        p = prev[p]
    return True


def add_location(world, loc_type, glyph, name, x, y, cont):
    world.terrain[y][x] = glyph
    loc = {"type": loc_type, "icon": glyph, "name": name, "x": x, "y": y,
           "continent": cont, "region": cont}
    world.locations.append(loc)
    return loc


def place_capital(world, rng):
    """Called by WorldMap._place_extras with a dedicated RNG.  Places
    Valdmere, then the two castles from game_castles."""
    from game_world import PLAINS, HILL
    if any(l.get("type") == "capital" for l in world.locations):
        return
    cities = [l for l in world.locations if l["type"] == "city"]
    start_city = next((c for c in cities if c.get("continent") == "A"), cities[0] if cities else None)
    near = (start_city["x"], start_city["y"]) if start_city else None
    avoid = set()
    if cities:     # the player is dropped one tile north of the first city
        c0 = cities[0]
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                avoid.add((c0["x"] + dx, c0["y"] + dy))
    site = (find_site(world, rng, "A", (PLAINS, HILL), gap=5, near=near, ideal=16, spread=8, avoid=avoid)
            or find_site(world, rng, "A", (PLAINS, HILL), gap=3, avoid=avoid)
            or find_site(world, rng, "A", (PLAINS, HILL, "T"), gap=2, avoid=avoid))
    if site:
        x, y = site
        add_location(world, "capital", CAPITAL_GLYPH, CAPITAL_NAME, x, y, "A")
        try:
            connect_to_road(world, x, y)
        except Exception as e:
            _log(f"road: {e!r}")
    try:
        import game_castles
        game_castles.place_castles(world, rng)
    except Exception as e:
        _log(f"castles placement: {e!r}")


# ═════════════════════════════════════════════════════════════════
#  VALDMERE — maps
# ═════════════════════════════════════════════════════════════════

CITY_MAP = r"""
                                         i                                    i                                         
                                        iAi                ii                iAi                                        
                                        AAA               iAAi               AAA                                        
XXXX#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#qXX EYEYE       i     EYEEYE     i       EYEYE XXq#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#XXXX
#..................................... YYjYY      iAi    YjYYjY    iAi      YYjYY .....................................#
#..5HHHHHHHHHHHHHHHHHHHH6m5HHHHHH6.... YYYYY      EYE   EYYYYYYE   EYE      YYYYY ....5HHHHHHHHHHHH6,T,5HHHHHHHHHHHH6..#
#.OVPPPPPPPPPPPPPPPPPPPPVmVPPPPPPV.... YYjYYEWEWEWYjYEWEYYjYYjYYEWEYjYWEWEWEYYjYY ....VRRRRRRRRRRRRV,f,VRRRRRRRRRRRRV..#
#..VPPPPPPPPPPPPPPPPPPPPVmVPPPPPPV.... YYYYYWWWWWWYYYWWWYYYYYYYYWWWYYYWWWWWWYYYYY ....VRRRRRRRRRRRRVf,fVRRRRRRRRRRRRV..#
#..VPPPPPPPPPPPPPPPPPPPPVmVPPAAPPV.... YYjYYWnWWWWWWWWnWYYjYYjYYWnWWWWWWWWnWYYjYY ....VRRRRRRRRRRRRV,u,VRRRRRRRRRRRRV..#
#..VPPPPPPPPPPPPPPPPPPPPVmVPPPPPPV.... YYYYYWnWWjWWjWWnWYYYYYYYYWnWWjWWjWWnWYYYYY ....VRRRRRRRRRRRRVf,fVRRRRRRRRRRRRV..#
#..VPPPPPPPPPPPPPPPPPPPPVmVPPPPPPV.... YYjYYWnWWWWWWWWnWYYYzzYYYWnWWWWWWWWnWYYjYY ....VRRRRRRRRRRRRV,f,VRRRRRRRRRRRRV..#
#.OVPPPPPPPPPPPPPPPPPPPPVmVPPPPPPV.... YYYYYWWWWWWWWWWWWYYYzzYYYWWWWWWWWWWWWYYYYY ....VRRRRRRRRRRRRV,T,VRRRRRRRRRRRRV..#
#..7HHHHHHHHH9HHHHHHHHHH8m7HH?HHH8....EYYYYYWWWWWWWWWWWWYYYKKYYYWWWWWWWWWWWWYYYYYE....7HHHHHNHHHHHH8,,,7HHHHHNHHHHHH8..#
X............................L::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::L............................X
#............................:::::::::::n::::::S::::::::::::::::::::::::S::::::n:::::::::::............................#
#............................L::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::L............................#
#..5HHHHHHHHHHHHHHHHHHHHHH6....hhhhhhhhhhhhhhhhhhhhhhhhhhhh::hhhhhhhhhhhhhhhhhhhhhhhhhhhh..5HHHHHHHHHHHHHHHHHHHHHHHH6..#
#..VMMMMMMMMMMMMMMMMMMMMMMV....hf,T,f,,f,T,,f,u,f,,T,f,,f,,::,,f,,f,T,,f,u,f,,T,f,,f,T,fh..VRRRRRRRRRRRRRRRRRRRRRRRRV..#
#..VMMMMMMMMMMMMMMMMMMMMMMV....h,f,,T,f,,f,T,,,,,T,f,,f,T,f::f,T,f,,f,T,,,,,T,f,,f,T,,f,h..VRRRRRRRRRRRRRRRRRRRRRRRRV..#
#..7HHHHHHHHHHUHHHHHHHHHHH8....hhhhhhh,,hhhhhhhhhhhhhhhhhhh::hhhhhhhhhhhhhhhhhhh,,hhhhhhh..7HHHHHHHHHHHZHHHHHHHHHHHH8..#
#......................................................................................................................#
g~~~~~~~~~~~~~~~~eee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eeeeee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eee~~~~~~~~~~~~~~~~g
g~~~~~~~~~~~~~~~~eee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eeeeee~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~eee~~~~~~~~~~~~~~~~g
X......................................................................................................................X
#..5HHHHHHHHHHHHHH6...5HHHHHHHHHHHH6..............T::::::::::::::::::T...5HHHHHHHHHHHHHHHHHH6....5HHHHHHHHHHHHHHHHHH6..#
#..VRRRRRRRRRRRRRRV...VRRRRRRRRRRFRV..............::::::::::::::::::::...VRRRRRRRRRRRRRRRRRRV....VRRRRRRRRRRRRRRRRRRV..#
#..VRRRRRRRRRRRRRRV...VRRRRRRRRRRRRV..............::::::::::::::::::::...VRRRRRRRRRRRRRRRRRRV....VRRRRRRRRRRRRRRRRRRV..#
#..7HHHHHH$HHHHHHH8...7HHHHH0HHHHHH8..............::::::::::::::::::::...7HHHHHHHH&HHHHHHHHH8....7HHHHHHHHH!HHHHHHHH8..#
#.s.s.s....c..b......s.s.s.......cc.........L....::::::::::uu::::::::::...t.t..t.t.....................................#
#...............o................................L:::::::::uu:::::::::L................................................#
#.s.s.s.....b.........s.s.s.......s.s.s..........:::::::::::::::::::::::..t.t..t.t.....L..........................b.c..#
#........c...........................c...........T::::::::S::S::::::::T................................................#
#5HHH6aaaaa5HHHH6aaaa5HH6aaaaaaa5HHHHH6..........L::::::::::::::::::::L....5HHHH6..5HHHH6..,T,..5HHHH6..5HHHH6..,T,....#
XVRRRVa5H6aVRRRRVa5H6VRRVa5HHH6aVRRRRRV...........::::::::::::::::::::.....VRRRRV..VRRRRV..,f,..VRRRRV..VRRRRV..,f,....X
#VRRRVaVRVaaaaaaaaVRVVRRVaVRRRVaaaaaaaaaaaaaaaaa.L::::::::::::::::::::L....VRRRRV..VRRRRV..f,f..VRRRRV..VRRRRV..f,f....#
#7HHH8a7H8aVRRRRVa7H87HH8a7HHH8aVRRRRRV...........::::::::::::::::::::.....7HHHH8..7HHHH8..,,,..7HHHH8..7HHHH8..,,,....#
#aaaaaaaaaa7HHHH8aaaaaaaaaaaaaaa7HHHHH8..........L::::::::::::::::::::L................................................#
#..5HHHHHHHH6...5HHHH6....5HHHH6..................::::::::::::::::::::..................5HHHH6....5HHHHHH6.............#
#..V________V...VRRRRV....VRRRRV......T....T.....L::::::::::::::::::::L.....T....T......VRRRRV....VRRRRRRV....c.b......#
#..V__b__b__V...7HHHH8....7HHHH8..................::::::::::::::::::::..................7HHHH8....VRRRRRRV.............#
#..7HHH..HHH8...........,,,,,,,,,,................::::::::::::::::::::..............,,,,,,,,,,....7HHHHHH8.............#
#.................................................:::::nn::::::nn:::::.................................................#
X#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#XXXXXDDXXXXX#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#q#X
T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,L::::L,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,
,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,::::,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,T,,,,,,,,,,,,
"""

KEEP_MAP = r"""
WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWnWWWWWnWWWWWWWWWWWWWWnWWWWWnWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW
W____________________________yW_______dddddddddddddddddddddddd_______W_____________________________W
W__yyyyyyyyyy____yyyyyyyyyy___W__p____ddddddddQddQQddQdddddddd____p__W____________________yyyyyyyy_W
W_____________________________WF______dddddddddddddddddddddddd______FW____________________yyyyyyyy_W
W__yyyyyyyyyy____yyyyyyyyyy___W_______dddddddddddddddddddddddd_______W_____________________________W
W_____________________________W__p____GGGGGGGGGGGddGGGGGGGGGGG____p__W__________ttt________________W
W__yyyyyyyyyy____yyyyyyyyyy___W__________________rr__________________W_____________________________W
W_____________________________W__________________rr__________________W_____________________________W
W__yyyyyyyyyy____yyyyyyyyyy___+__p_______________rr_______________p__+_____________________________W
W_____________________________WF_________________rr_________________FW_____________________________W
W__yyyyyyyyyy____yyyyyyyyyy___W__________________rr__________________W__ff_____________________O___W
W_____________tt______________W__p_______________rr_______________p__W_____________________________W
Wy____________________________W__________________rr__________________W_____________________________W
WWWWWWWWWWWWWWW+WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWrrrrWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW
W_____________________________W_________________rrrr_________________W_____________________________W
W______________n______________W_____p______p____rrrr____p______p_____W__$__$__$__$__$__$__$__$__$__W
W_____________________________W_________________rrrr_________________W_____________________________W
W_______mmmmmmmmmmmmmmm_______Wn________________rrrr________________nW_____________________________W
W_______mmmmmmmmmmmmmmm_______+_____p______p____rrrr____p______p_____+______________C______________W
W_______mmmmmmmmmmmmmmm_______W_________________rrrr_________________W_____________________________W
W_____________________________WF________________rrrr________________FW_____________________________W
W_____________________________W_____p______p____rrrr____p______p_____W__$__$__$__$__$__$__$__$__$__W
W_____________________________W_________________rrrr_________________W_____________________________W
WWWWWWWWWWWWWWW+WWWWWWWWWWWWWWWn________________rrrr________________nWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW
W_____________________________W_____p______p____rrrr____p______p_____W___________________________y_W
W_________k_________cc________W_________________rrrr_________________W___________________________y_W
W_____________________________WF________________rrrr________________FW_______________ttt_________y_W
W___vv________________________+_____p______p____rrrr____p______p_____+_____________________________W
W_____________________________W_________________rrrr_________________W_____________________________W
W_______________________b_____Wn________________rrrr________________nW__F__________________________W
W_____________________________W_____p______p____rrrr____p______p_____W_____________________________W
WWWWWWWWWWWWWWW+WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWrrrrWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW+WWWWWWWWWWWWWWW
W,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,W_n_______rrrr_______n_W,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,W
W,,T,,,T,,,T,,,T,,,T,,,T,,,T,,,T,,,T,,W_________rrrr_________W,,T,,,T,,,T,,,T,,,T,,,T,,,T,,,T,,,T,,W
W,,,,,,,,,,,,,,,,,,uu,,,,,,,,,,,,,,,,,W___S_____rrrr_____S___W,,,,,,,,,,,,,,,,,uu,,,,,,,,,,,,,,,,,,W
W,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,+_________rrrr_________+,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,W
W,,,,f,,,f,,,f,,,f,,,f,,,f,,,f,,,f,,,fW_________rrrr_________W,,,,f,,,f,,,f,,,f,,,f,,,f,,,f,,,f,,,fW
W,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,W_________rrrr_________W,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,W
WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWDDDDWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW
"""

UNDER_MAP = r"""
########################################################################
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx###########################
#.<<...........#xx_xx#xx_xx#xx_xx#xx_xx#xx_xx#######xxxxxxxxxxxxxxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxFxxxxxFxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxZZxxxxxxxxxZZxxx#
#.....tt.......#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxxxxxxxxxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxxxxxxxxxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxZZxxxxxxxxxZZxxx#
#..............#IIIII#IIIII#IIIII#IIIII#IIIII#######xxxxxxxxxxxxxxxxxxx#
#..............F...........F...........F...........#xxxxxxxxxxxxxxxxxxx#
#F.................................................grrrrrrrrrrrrrrrrrQx#
#..................................................grrrrrrrrrrrrrrrrrQx#
#..................................................#xxxxxxxxxxxxxxxxxxx#
#..............#IIIII#IIIII#IIIII#IIIII#IIIII#######xxxZZxxxxxxxxxZZxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxxxxxxxxxxxxxx#
#F.............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxxxxxxxxxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxZZxxxxxxxxxZZxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxxxxxxxxxxxxxx#
#...........bb.#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx#######xxxxxxFxxxxxFxxxxxx#
#..............#xx_xx#xx_xx#xx_xx#xx_xx#xx_xx#######xxxxxxxxxxxxxxxxxxx#
#..............#xxxxx#xxxxx#xxxxx#xxxxx#xxxxx###########################
########################################################################
"""

CITY_PAL = {
    "#": _T((150, 150, 162), "█", False, "city wall"),
    "q": _T((205, 205, 215), "▀", False, "battlement"),
    "X": _T((215, 215, 228), "█", False, "wall tower"),
    "Y": _T(WHITE, "█", False, "white tower"),
    "W": _T(STONE, "█", False, "castle wall"),
    "E": _T(WHITE, "▄", False, "crenellation"),
    "A": _T((125, 85, 175), "▲", False, "slate spire"),
    "i": _T(LILAC, "▲", False, "spire"),
    "j": _T((255, 215, 120), "▪", False, "lit window"),
    "n": _T(PURPLE, "▓", False, "royal banner"),
    "z": _T((55, 40, 80), "█", False, "great arch"),
    "K": _T(GOLDC, "▒", True, "keep gate"),
    "H": _T((200, 200, 212), "═", False, "stone wall"),
    "V": _T((200, 200, 212), "║", False, "stone wall"),
    "5": _T((200, 200, 212), "╔", False, "stone wall"),
    "6": _T((200, 200, 212), "╗", False, "stone wall"),
    "7": _T((200, 200, 212), "╚", False, "stone wall"),
    "8": _T((200, 200, 212), "╝", False, "stone wall"),
    "R": _T((105, 105, 125), "▒", False, "slate roof"),
    "P": _T((120, 80, 170), "▒", False, "academy roof"),
    "M": _T((175, 185, 220), "▒", False, "moonstone dome"),
    "O": _T(LILAC, "◊", False, "arcane pylon"),
    "m": _T((185, 125, 255), "∙", True, "glowing runes"),
    ".": _T((118, 118, 128), "·", True, "cobbles"),
    ":": _T((200, 200, 215), "·", True, "marble"),
    "h": _T((40, 110, 55), "▒", False, "hedge"),
    "f": _T((205, 150, 255), "*", False, "moon lilies"),
    "e": _T((190, 190, 205), "▒", True, "bridge"),
    "~": _T((60, 105, 205), "≈", False, "canal"),
    "g": _T((95, 95, 105), "▒", False, "water gate"),
    "u": _T((150, 190, 240), "∩", False, "fountain"),
    "S": _T((220, 220, 235), "▲", False, "statue"),
    "L": _T((255, 220, 140), "¡", False, "lamp post"),
    "F": _T((255, 140, 40), "♨", False, "forge chimney"),
    "a": _T((48, 44, 58), "░", True, "Lantern Alley", dark=True),
}

KEEP_PAL = {
    "W": _T(WHITE, "█", False, "marble wall"),
    "_": _T((112, 110, 128), "·", True, "polished floor"),
    "d": _T((190, 165, 110), "▒", True, "royal dais"),
    "G": _T(GOLDC, "▀", False, "gilded step"),
    "Q": _T((255, 215, 0), "Ω", False, "throne"),
    "r": _T((150, 80, 210), "░", True, "royal carpet"),
    "p": _T(WHITE, "‡", False, "pillar"),
    "n": _T(PURPLE, "▓", False, "banner"),
    "m": _T((120, 85, 55), "▓", False, "war table"),
    "k": _T((170, 170, 185), "╪", False, "weapon rack"),
    "C": _T(GOLDC, "▣", False, "royal coffers"),
    "$": _T((255, 215, 0), "$", False, "gold hoard"),
    "O": _T(LILAC, "◊", False, "scrying orb"),
    "+": _T((200, 170, 110), "+", True, "door"),
}

UNDER_PAL = {
    "#": _T((70, 66, 82), "█", False, "rough stone"),
    ".": _T((100, 96, 110), "·", True, "flagstones"),
    "x": _T((70, 64, 88), "·", True, "crypt floor", dark=True),
    "I": _T((150, 150, 160), "║", False, "iron bars"),
    "_": _T((150, 130, 70), "≡", False, "straw"),
    "Z": _T((150, 140, 170), "▬", False, "sarcophagus"),
    "g": _T((130, 90, 200), "▒", False, "sealed crypt gate"),
    "r": _T((110, 60, 160), "░", True, "faded carpet"),
    "Q": _T((120, 80, 170), "Ω", False, "hollow throne"),
}


# ═════════════════════════════════════════════════════════════════
#  VALDMERE — title banner
# ═════════════════════════════════════════════════════════════════

VALDMERE_ART = [
    r"                    ^                      /\                      ^                    ",
    r"                   /#\                    /##\                    /#\                   ",
    r"                   |=|        ^          /####\          ^        |=|                   ",
    r"            ^      |o|       /#\        |  []  |        /#\       |o|      ^            ",
    r"           /#\  ___|=|___    |=|   _/\_ | [  ] | _/\_   |=|    ___|=|___  /#\           ",
    r"           |o| |  |   |  |   |o|  |    ||  ||  ||    |  |o|   |  |   |  | |o|           ",
    r"         __|=|_|  | o |  |___|=|__|    ||  ||  ||    |__|=|___|  | o |  |_|=|__         ",
    r"        |  #   #  #   #  #   #   #  ~~~ |  /\  | ~~~  #   #   #  #   #  #   #  |        ",
    r"        |  o       o       o      ~ ~ ~ | /  \ | ~ ~ ~      o       o       o  |        ",
    r"        |___________________________~~~_|/____\|_~~~___________________________|        ",
]


def _valdmere_colour(ch, x, y):
    if ch in "^":
        return fg(*LILAC)
    if ch in "/\\" and y <= 4:
        return fg(*PURPLE)
    if ch == "#":
        return fg(*WHITE)
    if ch in "o[]":
        return fg(255, 215, 120)
    if ch == "~":
        return fg(*PURPLE)
    if ch == "=":
        return fg(*GOLDC)
    return fg(*STONE)


def valdmere_banner(player):
    f = pflags(player)
    note = ""
    k = kingdom_step(player)
    if k == "cp_summons" or k == "cp_audience":
        note = "The King's letter is heavy in your pack. The keep waits at the top of the Grand Avenue."
    elif f.get("valdmere_title"):
        note = "Trumpets sound from the gatehouse: the Knight-Protector has come home."
    elif f.get("demon_pact"):
        note = "The gate guards lower their halberds an inch as you pass. They know where you have been."
    show_banner(VALDMERE_ART,
                [f"{C_MARBLE}{B_}V  A  L  D  M  E  R  E{R_}",
                 f"{C_LILAC}~ the white city · seat of Castle Lumeris ~{R_}"],
                _valdmere_colour, subtitle="Aeloria · Royal Capital", note=note)


# ═════════════════════════════════════════════════════════════════
#  VALDMERE — the visit
# ═════════════════════════════════════════════════════════════════

ROYAL_GUARD_LINES = [
    "Move along, citizen. The King's peace is kept here.",
    "Valdmere stands. Long live King Aldren.",
    "No brawling in the Promenade. No exceptions.",
    "The wards have been dim of late. Keep your wits about you after dark.",
]
WARY_GUARD_LINES = [
    "We know where you've been. Keep your hands where we can see them.",
    "Brimstone on your boots... The Lord Commander has eyes on you.",
    "One wrong step, pact-bearer. Just one.",
]


class Valdmere:
    """One visit to the royal city: city ⇄ keep ⇄ undercroft."""

    def __init__(self, world, player, loc=None, autosave=None):
        self.world = world
        self.player = player
        self.loc = loc
        self.autosave = autosave
        self.rng = random.Random()
        self.town = self._make_town()
        self.scenes = {}

    # ── shared town services ─────────────────────────────────────
    def _make_town(self):
        try:
            from game_systems import Town
            t = Town(self.player, CAPITAL_NAME, "AELORIA")
            try:
                from game_party import recruit_menu
                t.set_companion_callback(lambda: recruit_menu(self.player, CAPITAL_NAME))
            except Exception:
                pass
            if self.loc:
                t.set_base_info(self.loc.get("continent", "A"), self.loc["x"], self.loc["y"])
            if self.world is not None:
                t.set_world(self.world, self.autosave)
            if pflags(self.player).get("demon_pact"):
                t.shop_stock = [(it, int(price * 1.25) + 1) for it, price in t.shop_stock]
            elif pflags(self.player).get("valdmere_title"):
                t.shop_stock = [(it, max(1, int(price * 0.85))) for it, price in t.shop_stock]
            return t
        except Exception as e:
            _log(f"town: {e!r}")
            return None

    def _town_call(self, method):
        def fn(scene, player):
            if self.town is None:
                return f"{C_DIM}Closed today.{R_}"
            try:
                scene.modal(getattr(self.town, method))
            except Exception as e:
                _log(f"town.{method}: {e!r}")
            return None
        return fn

    # ── main loop ────────────────────────────────────────────────
    def run(self):
        player = self.player
        valdmere_banner(player)
        nxt, entry = "city", "gate"
        result = "left"
        while True:
            if nxt == "city":
                sc = self.city(entry)
            elif nxt == "keep":
                sc = self.keep(entry)
            elif nxt == "under":
                sc = self.undercroft(entry)
            else:
                break
            res = sc.run(player)
            if res == "defeat" or not player.is_alive():
                result = "defeat"
                break
            if res == "to_keep":
                nxt, entry = "keep", "gate"
            elif res == "to_city":
                nxt, entry = "city", "keep"
            elif res == "to_under":
                nxt, entry = "under", "stairs"
            elif res == "to_keep_stairs":
                nxt, entry = "keep", "stairs"
            else:
                break
        return result

    # ── outer city ───────────────────────────────────────────────
    def city(self, entry="gate"):
        sc = self.scenes.get("city")
        if sc is None:
            sc = self._build_city()
            self.scenes["city"] = sc
        sc.result = None
        if entry == "keep":
            sc.px, sc.py = 59, 13
        else:
            sc.px, sc.py = 60, 40
        return sc

    def _build_city(self):
        player = self.player
        f = pflags(player)
        sc = CastleScene("VALDMERE", parse_map(CITY_MAP), palette=CITY_PAL, start=(60, 40),
                         subtitle="Royal City of Aeloria", colour=C_MARBLE, world=self.world)
        # door markers → triggers
        doors = {
            "$": ("Royal Emporium (shop)", self._town_call("shop")),
            "0": ("Smithy & crafting bench", self._town_call("crafting_bench")),
            "&": ("The Silver Stag (tavern & inn)", self._tavern),
            "!": ("Adventurers' Guild", self._town_call("adventure_guild")),
            "9": ("Royal Academy of the Arcane", self._academy),
            "?": ("Starfall Tower", self._starfall_tower),
            "U": ("Temple of the Moon", self._temple),
            "Z": ("Royal Barracks", self._barracks),
            "N": ("Noble manor", self._manor),
            "K": ("Castle Lumeris", lambda s, p: s.leave("to_keep")),
        }
        for ch, (label, fn) in doors.items():
            for (x, y) in sc.find(ch):
                sc.add_door(x, y, label, fn, tile="+" if ch != "K" else "K")
        for x, y in sc.find("D"):
            sc.add_door(x, y, "Leave Valdmere", lambda s, p: s.leave("left"), tile="D")
        # roof signs
        for (x, y, text, col) in (
                (6, 8, "ROYAL ACADEMY", C_LILAC), (7, 9, "OF THE ARCANE", C_LILAC),
                (26, 6, "STARFALL", fg(220, 180, 255)),
                (6, 17, "TEMPLE OF THE MOON", fg(225, 230, 255)),
                (97, 17, "ROYAL BARRACKS", C_MARBLE),
                (5, 25, "ROYAL EMPORIUM", C_GOLD), (24, 25, "SMITHY", fg(255, 160, 80)),
                (76, 25, "THE SILVER STAG", fg(220, 220, 240)),
                (99, 25, "ADVENTURERS' GUILD", C_GOLD),
                (88, 8, "HOUSE VALCREST", C_DIM), (105, 8, "HOUSE ORLAINE", C_DIM),
                (5, 38, "STABLES", fg(190, 150, 100))):
            sc.add_label(x, y, text, col)
        sc.add_key("p", "Save", self._save)
        sc.hud_extra = lambda s, p: (f"{C_LILAC}♛ Knight-Protector{R_}" if pflags(p).get("valdmere_title")
                                     else (f"{C_RED}☠ pact-bearer{R_}" if pflags(p).get("demon_pact") else ""))
        self._populate_city(sc)
        return sc

    def _save(self, scene, player):
        if self.town is None:
            return f"{C_DIM}Saving isn't available here.{R_}"
        scene.modal(self.town._save_game)
        return None

    def _guard_lines(self):
        return WARY_GUARD_LINES if pflags(self.player).get("demon_pact") else ROYAL_GUARD_LINES

    def _populate_city(self, sc):
        p = self.player
        f = pflags(p)
        guard_col = fg(200, 200, 225)
        gl = self._guard_lines()
        # gate guards + herald
        sc.add_entity(Entity(57, 41, "G", guard_col, "Gate Sergeant Hollis", kind="guard", lines=gl,
                             title="Royal Guard", npc_id="guard_hollis"))
        sc.add_entity(Entity(62, 41, "G", guard_col, "Guardsman Edric", kind="guard", lines=gl, title="Royal Guard"))
        sc.add_entity(Entity(55, 38, "@", C_GILT, "Herald Pell", npc_id="herald_pell", title="Royal Herald",
                             lines=["Hear ye! The Royal Emporium has new stock from the Ironspire forges!",
                                    "Welcome to Valdmere, the white city! Mind the canal, it's colder than it looks.",
                                    "The Temple of the Moon blesses travellers for a modest donation."]))
        # patrolling guards
        sc.add_entity(Entity(31, 14, "G", guard_col, "Royal Guard", kind="guard", lines=gl, ai="patrol",
                             patrol=[(31, 14), (88, 14)]))
        sc.add_entity(Entity(52, 24, "G", guard_col, "Royal Guard", kind="guard", lines=gl, ai="patrol",
                             patrol=[(52, 24), (52, 40), (67, 40), (67, 24)]))
        sc.add_entity(Entity(57, 21, "G", guard_col, "Bridge Watchman", kind="guard", lines=gl, title="Royal Guard"))
        sc.add_entity(Entity(57, 13, "G", guard_col, "Keep Guard", kind="guard", lines=gl, title="Castle Lumeris"))
        sc.add_entity(Entity(62, 13, "G", guard_col, "Keep Guard", kind="guard", lines=gl, title="Castle Lumeris"))
        # nobles, scholars, townsfolk
        noble = fg(210, 170, 240)
        sc.add_entity(Entity(95, 4, "@", noble, "Lady Ysolde Valcrest", ai="wander", radius=6, title="noble",
                             lines=["Have you been presented at court? You simply must be.",
                                    "The Princess is a scholar, you know. Terribly clever. Terribly sad, lately.",
                                    "My cousin swears the Lord Chancellor never sleeps. I believe it."]))
        sc.add_entity(Entity(112, 13, "@", noble, "Lord Fenwick Orlaine", ai="wander", radius=5, title="noble",
                             lines=["Valdmere's wards have stood four hundred years. A flicker is nothing. Nothing!",
                                    "One does not run in the Promenade, traveller. One promenades."]))
        sch = fg(170, 140, 240)
        sc.add_entity(Entity(10, 13, "@", sch, "Scholar Bettany", ai="wander", radius=6, title="Academy",
                             lines=["The Starfall Tower has been sealed since Master Veyl vanished. Gives me the shivers.",
                                    "Third-year illusions. Don't look at the fountain too long; it might look back."]))
        sc.add_entity(Entity(30, 4, "@", sch, "Apprentice Tobin", ai="wander", radius=4, title="Academy",
                             lines=["I'm supposed to be studying ward theory. Please don't tell the Archmage.",
                                    "The runes on the path glow brighter when Princess Elowen walks by. True story."]))
        merch = fg(230, 190, 110)
        for (x, y, n, ln) in ((4, 29, "Spice Merchant", "Saffron from Sunspire! Pepper from the Isles!"),
                              (22, 29, "Silk Merchant", "Purple silk, the royal shade. Don't wear it to court unless invited."),
                              (35, 29, "Fruit Seller", "Apples from the royal orchards! Well, near them.")):
            sc.add_entity(Entity(x, y, "@", merch, n, title="market", lines=[ln, "Buy something or move along, love."]))
        sc.add_entity(Entity(60, 18, "@", fg(120, 200, 120), "Gardener Tamsin", npc_id="gardener_tamsin",
                             title="Royal Gardens", ai="wander", radius=1,
                             lines=["The moon lilies only open for the Queen. Or so we tell the tourists.",
                                    "Please keep off the hedges. They bite. Not literally. Mostly."]))
        folk = fg(200, 200, 200)
        for (x, y, n) in ((80, 30, "Townsfolk"), (100, 36, "Washerwoman"), (40, 39, "Stablehand"),
                          (94, 25, "Bargeman")):
            sc.add_entity(Entity(x, y, "@", folk, n, ai="wander", radius=5,
                                 lines=["Lovely day for it.", "Long live the King!",
                                        "Mind the Lantern Alley after dark. Pickpockets.",
                                        "The castle looked dimmer last night. My gran says it's an omen."]))
        # Priestess (side quest), Cassia (recruit), Wren (story), quest board
        sc.add_entity(Entity(27, 17, "@", fg(215, 225, 255), "Priestess Lunara", npc_id="priestess_lunara",
                             title="Temple of the Moon", interact=self._lunara))
        if not has_companion(p, "knight_cassia") and not f.get("valdmere_cassia_joined"):
            sc.add_entity(Entity(90, 17, "K", fg(215, 205, 255), "Knight Cassia", npc_id="knight_cassia",
                                 title="Royal Knight", interact=self._cassia))
        sc.add_entity(Entity(13, 34, "@", fg(150, 130, 170), "Wren", npc_id="informant_wren", title="informant",
                             interact=self._wren))
        sc.add_entity(Entity(110, 28, "¶", C_GOLD, "Quest Board", kind="object",
                             interact=lambda s, pl, e: self._town_call("quest_board")(s, pl)))
        # Lantern Alley lurkers
        for (x, y, name) in ((3, 36, "Alley Thief"), (40, 34, "Cutthroat")):
            sc.add_entity(Entity(x, y, "t", C_RED, name, kind="bandit", hostile=True, ai="lurk", lurk=True,
                                 reveal_radius=2, on_contact=self._alley_fight))
        if f.get("valdmere_censer_quest") and not f.get("valdmere_censer_found"):
            sc.add_entity(Entity(26, 36, "t", fg(255, 120, 120), "Censer Thief", kind="bandit", hostile=True,
                                 ai="lurk", lurk=True, reveal_radius=2, on_contact=self._censer_thief))

    # ── city interactions ───────────────────────────────────────
    def _alley_fight(self, scene, player, ent):
        enemy = make_elite(ent.name, player, zone="dungeon", danger=2)
        scene.message(f"{C_RED}{ent.name} lunges from the shadows!{R_}")
        res = scene.fight_enemy(player, enemy, first_strike=False)
        if res == "victory":
            ent.alive = False
            return f"{C_GREEN}The {ent.name} won't trouble anyone tonight.{R_}"
        if res == "escaped":
            ent.cooldown = 3
        return None

    def _censer_thief(self, scene, player, ent):
        enemy = make_elite("Alley Thief", player, zone="dungeon", danger=3, mult=1.4)
        enemy.name = "Censer Thief"
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            ent.alive = False
            set_flag(player, "valdmere_censer_found", True, scene)
            return f"{C_GOLD}You recover the Moon-Silver Censer! Return it to Priestess Lunara.{R_}"
        ent.cooldown = 3
        return None

    def _lunara(self, scene, player, ent):
        f = pflags(player)
        if f.get("valdmere_censer_done"):
            scene.talk_box(ent, "The Moon remembers kindness. Come to the temple whenever you need her light.", player)
            return None
        if f.get("valdmere_censer_found"):
            scene.say_lines(ent, ["The censer! Oh — you've found it. Its silver still holds last month's moonlight.",
                                  "Take this pendant, blessed at the high altar. And the temple's gratitude, for what it's worth."])
            f["valdmere_censer_done"] = True
            player.gold += 150
            try:
                player.gain_exp(250 + 20 * player.level)
            except Exception:
                pass
            give_item(player, "Moonsilver Pendant", scene=scene)
            give_item(player, "Holy Water", 2, scene=scene)
            set_flag(player, "valdmere_censer_done", True, scene)
            return f"{C_GOLD}Side quest complete: The Moon-Silver Censer (+150g){R_}"
        if f.get("valdmere_censer_quest"):
            scene.talk_box(ent, "The thief went into Lantern Alley, south-west of the market. Please be careful.", player)
            return None
        scene.say_lines(ent, ["Peace of the Moon upon you, traveller.",
                              "Our Moon-Silver Censer was stolen from the altar three nights ago. Without it the night "
                              "rites cannot be sung, and the wards grow dimmer still."])
        ch = scene.choice_box("Will you help the temple?", [("1", "I'll find your censer."), ("2", "Not now.")], ent)
        if ch == "1":
            f["valdmere_censer_quest"] = True
            # spawn the thief now
            scene.add_entity(Entity(26, 36, "t", fg(255, 120, 120), "Censer Thief", kind="bandit", hostile=True,
                                    ai="lurk", lurk=True, reveal_radius=2, on_contact=self._censer_thief))
            return f"{C_GOLD}New side quest: The Moon-Silver Censer — search Lantern Alley.{R_}"
        return None

    def _cassia(self, scene, player, ent):
        f = pflags(player)
        if f.get("valdmere_cassia_beaten"):
            scene.talk_box(ent, "You fight like a storm with manners. I'd ride with you, if you'll have me.", player)
            if try_recruit(player, "knight_cassia", scene):
                f["valdmere_cassia_joined"] = True
                ent.alive = False
                return f"{C_GOLD}Knight Cassia joins your party!{R_}"
            return None
        scene.say_lines(ent, ["Cassia Thorne, Knight of the Pale Tower. You have the look of someone who has actually used that weapon.",
                              "The Lord Commander keeps us polishing armour while the wards fail. I am bored to tears. Spar with me?"])
        ch = scene.choice_box("Knight Cassia offers a friendly duel.", [("1", "Draw steel (sparring duel)"),
                                                                        ("2", "Another time")], ent)
        if ch != "1":
            return None
        enemy = make_elite("Royal Guard", player, zone="dungeon_deep", danger=3, mult=1.6)
        enemy.name = "Knight Cassia"
        hp_before = player.hp
        res = scene.fight_enemy(player, enemy, allow_escape=True)
        if res == "victory":
            f["valdmere_cassia_beaten"] = True
            player.hp = max(player.hp, hp_before // 2)
            scene.talk_box(ent, "Ha! Yield, yield! ...Well fought. Help me up?", player)
            return self._cassia(scene, player, ent)
        if res == "defeat":
            # a spar never kills: the knight stops the bout
            scene.result = None
            player.hp = max(1, player.max_hp // 4)
            scene.talk_box(ent, "Enough — you're down. Get some rest and come back. I'll be here, bored.", player)
        return None

    def _wren(self, scene, player, ent):
        k = kingdom_step(player)
        f = pflags(player)
        if kingdom_past(player, "cp_informant") and k == "cp_sigil":
            scene.talk_box(ent, "Blackroot Crypt, I said. West, in the old woods. Off you go.", player)
            return None
        lines = story_lines("informant_wren", player)
        if lines:
            scene.say_lines(ent, lines)
            return None
        # no story: rumours for coin
        scene.talk_box(ent, "Psst. Rumours, ten gold apiece. Fresher than the bread at the Silver Stag.", player)
        ch = scene.choice_box("Buy a rumour from Wren?", [("1", "Pay 10 gold"), ("2", "No thanks")], ent)
        if ch == "1":
            if player.gold < 10:
                return f"{C_RED}You can't afford Wren's rumours.{R_}"
            player.gold -= 10
            scene.talk_box(ent, pick([
                "The Duskthorn demons keep their word. That's what makes 'em dangerous. Iron mountains, far east.",
                "Sultan Rahzim of Sunspire pays well for anyone who can clear his scorpion pit.",
                "The Lord Chancellor's clerks bought a lot of ink last month. A LOT of ink.",
                "Knight Cassia at the barracks is itching for a sparring partner. Beat her and she might follow you anywhere.",
                "Old Bram at the Silver Stag guarded three kings. He'll guard a fourth fool, if it's you.",
                "There's a crypt under the castle no one's opened in a century. The gaoler gets twitchy if you ask.",
            ]), player)
        return None

    def _tavern(self, scene, player):
        def menu():
            from game_scene import C_GOLD as G
            while True:
                clr()
                print(C(f"\n{fg(220, 220, 240)}{B_}╔══════════════════════════════════════════╗"))
                print(C(f"║        THE SILVER STAG  ·  Valdmere        ║"))
                print(C(f"╚══════════════════════════════════════════╝{R_}\n"))
                print(C(f"{C_DIM}Lute music, pipe smoke and the clink of pewter. A stag's head wears a tiny crown.{R_}\n"))
                print(C(f"{G}[1]{R_} Rent a room (rest)"))
                print(C(f"{G}[2]{R_} Companions & party"))
                print(C(f"{G}[3]{R_} Listen to the patrons"))
                if not has_companion(player, "old_bram") and not pflags(player).get("valdmere_bram_joined"):
                    print(C(f"{G}[4]{R_} Sit with Old Bram, the retired royal guard"))
                print(C(f"{G}[0]{R_} Leave"))
                try:
                    ch = input(C(f"\n{G}>{R_} ")).strip()
                except (EOFError, KeyboardInterrupt):
                    return
                if ch == "1" and self.town:
                    self.town.inn()
                elif ch == "2" and self.town and self.town._companion_cb:
                    self.town._companion_cb()
                elif ch == "3" and self.town:
                    self.town.talk_to_npcs()
                elif ch == "4":
                    clr()
                    print(C(f"\n{fg(200, 180, 150)}{B_}Old Bram{R_} {C_DIM}· thirty years in the Royal Guard{R_}\n"))
                    print(C(f"{C_WHITE}'Guarded three kings, I did. Aldren's grandfather, his father, and Aldren{R_}"))
                    print(C(f"{C_WHITE} himself till my knees gave out. You've got a look about you. Trouble.'{R_}"))
                    print(C(f"{C_WHITE}'I'm too old for the Guard and too young to die in a tavern. Want a shield at your back?'{R_}\n"))
                    try:
                        input(C(f"{C_DIM}(Press Enter){R_}"))
                    except (EOFError, KeyboardInterrupt):
                        pass
                    if try_recruit(player, "old_bram"):
                        pflags(player)["valdmere_bram_joined"] = True
                elif ch in ("0", ""):
                    return
        scene.modal(menu)
        return None

    def _academy(self, scene, player):
        f = pflags(player)

        def menu():
            while True:
                clr()
                print(C(f"\n{C_LILAC}{B_}╔══════════════════════════════════════════════╗"))
                print(C(f"║     ROYAL ACADEMY OF THE ARCANE  ·  Valdmere     ║"))
                print(C(f"╚══════════════════════════════════════════════╝{R_}\n"))
                print(C(f"{C_DIM}Purple light pools under the domes. Chalk diagrams crawl across the floor by themselves.{R_}\n"))
                print(C(f"{C_GOLD}[1]{R_} Arcane stores (potions & ethers)"))
                print(C(f"{C_GOLD}[2]{R_} Attend a lecture on ward theory {C_DIM}(30g){R_}"))
                print(C(f"{C_GOLD}[0]{R_} Leave"))
                try:
                    ch = input(C(f"\n{C_GOLD}>{R_} ")).strip()
                except (EOFError, KeyboardInterrupt):
                    return
                if ch == "1":
                    mini_shop(player, "ARCANE STORES", [("Ether", 18), ("Hi-Ether", 40), ("Elixir", 110),
                                                         ("Hi-Potion", 30), ("Holy Water", 45)], C_LILAC)
                elif ch == "2":
                    if player.gold < 30:
                        print(C(f"{C_RED}The usher eyes your purse and shakes her head.{R_}"))
                    elif f.get("valdmere_lectures", 0) >= 5:
                        print(C(f"{C_DIM}You have heard every lecture this term. Twice.{R_}"))
                    else:
                        player.gold -= 30
                        f["valdmere_lectures"] = f.get("valdmere_lectures", 0) + 1
                        player.max_mp += 2
                        player.mp = min(player.max_mp, player.mp + 2)
                        try:
                            player.gain_exp(40 + 8 * player.level)
                        except Exception:
                            pass
                        print(C(f"{C_LILAC}Professor Hollin lectures on layered wards. Your mind sharpens: Max MP +2.{R_}"))
                    try:
                        input(C(f"{C_DIM}(Press Enter){R_}"))
                    except (EOFError, KeyboardInterrupt):
                        return
                elif ch in ("0", ""):
                    return
        scene.modal(menu)
        return None

    def _starfall_tower(self, scene, player):
        f = pflags(player)
        if f.get("valdmere_veyl_dead"):
            return f"{C_DIM}The Starfall Tower is quiet now. Stars drift down its stairwell like snow.{R_}"
        if kingdom_step(player) != "cp_veyl":
            return f"{C_LILAC}A shimmering seal bars the tower door. It hums, unimpressed.{R_}"
        lines = ["The Starfall Sigil flares in your hand. The seal unravels like smoke...",
                 "At the top of the spiral stair, a figure stands among floating stars."]
        ent = Entity(0, 0, "V", C_LILAC, "Archmage Veyl the Unbound")
        for ln in lines:
            scene.talk_box(ent, ln, player)
        scene.talk_box(ent, "'Ilvaris sends a sword instead of coming herself? Typical. You have no idea what "
                            "you are protecting. Very well — let us see what you are worth.'", player)
        boss = make_boss("Archmage Veyl the Unbound", player, power=1.25)
        res = scene.fight_enemy(player, boss, allow_escape=False)
        if res == "victory":
            f["valdmere_veyl_dead"] = True
            return f"{C_GOLD}★ Archmage Veyl is defeated.{R_}"
        return None

    def _temple(self, scene, player):
        cost = max(10, 6 + player.level * 3)

        def menu():
            clr()
            print(C(f"\n{fg(215, 225, 255)}{B_}╔══════════════════════════════════════════╗"))
            print(C(f"║          TEMPLE OF THE MOON                ║"))
            print(C(f"╚══════════════════════════════════════════╝{R_}\n"))
            print(C(f"{C_DIM}Silver light through a moonstone dome. Acolytes hum a slow, cold hymn.{R_}\n"))
            print(C(f"{C_GOLD}[1]{R_} Receive the Moon's blessing {C_DIM}(full heal, {cost}g donation){R_}"))
            print(C(f"{C_GOLD}[0]{R_} Leave"))
            try:
                ch = input(C(f"\n{C_GOLD}>{R_} ")).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if ch == "1":
                if player.gold < cost:
                    print(C(f"{C_DIM}The acolyte smiles kindly. 'The Moon accepts prayers too.'{R_}"))
                    player.hp = min(player.max_hp, player.hp + player.max_hp // 4)
                else:
                    player.gold -= cost
                    player.hp, player.mp = player.max_hp, player.max_mp
                    try:
                        player.status_effects.clear()
                    except Exception:
                        pass
                    print(C(f"{fg(215, 225, 255)}Cool light washes over you. HP and MP fully restored.{R_}"))
                try:
                    input(C(f"{C_DIM}(Press Enter){R_}"))
                except (EOFError, KeyboardInterrupt):
                    pass
        scene.modal(menu)
        return None

    def _barracks(self, scene, player):
        f = pflags(player)
        if f.get("demon_pact"):
            return f"{C_RED}The barracks sentry bars the door: 'Not you, pact-bearer.'{R_}"
        lines = ["Rows of polished breastplates. Recruits drill in the yard under a bellowing sergeant.",
                 "Sergeant Dunmore: 'Spar with the recruits for coin? Five gold says you can't last three rounds!'"]
        ent = Entity(0, 0, "G", fg(200, 200, 225), "Sergeant Dunmore", title="Royal Barracks")
        for ln in lines:
            scene.talk_box(ent, ln, player)
        ch = scene.choice_box("Spar with a recruit?", [("1", "Spar (training bout)"), ("2", "Leave")], ent)
        if ch == "1":
            enemy = make_elite("Royal Guard", player, zone="dungeon", danger=2, mult=0.8)
            enemy.name = "Barracks Recruit"
            res = scene.fight_enemy(player, enemy)
            if res == "victory":
                return f"{C_GREEN}The recruits cheer. Sergeant Dunmore grudgingly pays up.{R_}"
            if res == "defeat":
                scene.result = None
                player.hp = max(1, player.max_hp // 4)
                return f"{C_DIM}You wake up on a cot with a cold compress. The recruits are very polite about it.{R_}"
        return None

    def _manor(self, scene, player):
        return pick([f"{C_DIM}A steward bows: 'The family is at court. Do leave a card.'{R_}",
                     f"{C_DIM}The door knocker is a silver griffin. Nobody answers.{R_}"])

    # ── keep ─────────────────────────────────────────────────────
    def keep(self, entry="gate"):
        sc = self.scenes.get("keep")
        if sc is None:
            sc = self._build_keep()
            self.scenes["keep"] = sc
        sc.result = None
        if entry == "stairs":
            sc.px, sc.py = 6, 27
        else:
            sc.px, sc.py = 49, 37
            if not pflags(self.player).get("valdmere_keep_seen"):
                pflags(self.player)["valdmere_keep_seen"] = True
                sc.message(f"{C_LILAC}Light falls through high windows onto a purple carpet that runs to the throne.{R_}")
        self._refresh_keep(sc)
        return sc

    def _build_keep(self):
        sc = CastleScene("CASTLE LUMERIS", parse_map(KEEP_MAP), palette=KEEP_PAL, start=(49, 37),
                         subtitle="the keep of Valdmere", colour=C_LILAC, world=self.world)
        for x, y in sc.find("D"):
            sc.add_door(x, y, "Return to the city", lambda s, p: s.leave("to_city"), tile="D")
        for x, y in sc.find("v"):
            sc.add_door(x, y, "Stairs down to the undercroft", lambda s, p: s.leave("to_under"), tile="v")
        sc.add_door(69, 18, "Royal Treasury (vault door)", self._vault_door, step_back=False, tile="+")
        sc.add_door(84, 18, "Open the royal coffers", self._coffers, tile=None)
        for (x, y, text, col) in ((43, 7, "THRONE ROOM", C_GILT), (10, 1, "ROYAL LIBRARY", C_LILAC),
                                  (11, 14, "WAR ROOM", C_MARBLE), (11, 24, "GUARD ROOM", C_STONE),
                                  (78, 14, "ROYAL TREASURY", C_GOLD), (75, 24, "CHANCELLOR'S STUDY", C_DIM),
                                  (77, 1, "ROYAL QUARTERS", C_LILAC), (44, 14, "GRAND HALL", C_MARBLE)):
            sc.add_label(x, y, text, col)
        sc.add_key("p", "Save", self._save)
        royal = fg(240, 220, 120)
        gl = self._guard_lines()
        gc = fg(200, 200, 225)
        sc.add_entity(Entity(50, 3, "♛", royal, "King Aldren IV", npc_id="king_aldren", title="King of Valdmere",
                             interact=self._king))
        sc.add_entity(Entity(46, 3, "♛", fg(225, 200, 255), "Queen Seraphine", npc_id="queen_seraphine",
                             title="Queen of Valdmere", interact=self._queen))
        sc.add_entity(Entity(53, 3, "@", fg(235, 190, 255), "Princess Elowen", npc_id="princess_elowen",
                             title="Princess of Valdmere", interact=self._elowen))
        sc.add_entity(Entity(41, 3, "@", C_LILAC, "Archmage Ilvaris", npc_id="archmage_ilvaris",
                             title="Royal Archmage", interact=self._ilvaris))
        sc.add_entity(Entity(58, 3, "@", fg(215, 215, 235), "Lord Commander Garran Vale", npc_id="lord_commander",
                             title="Lord Commander", interact=self._commander))
        sc.add_entity(Entity(88, 27, "@", fg(170, 160, 120), "Lord Chancellor Morvane", npc_id="chancellor_morvane",
                             title="Lord Chancellor", interact=self._morvane, data={"role": "morvane"}))
        sc.add_entity(Entity(8, 12, "@", fg(200, 180, 140), "Librarian Quill", npc_id="librarian_quill",
                             title="Royal Library", interact=self._quill))
        sc.add_entity(Entity(16, 11, "▤", C_LILAC, "Forbidden Codex", kind="object", interact=self._codex))
        sc.add_entity(Entity(15, 20, "@", fg(200, 200, 225), "Captain Rhosyn", npc_id="captain_rhosyn",
                             title="Captain of the Watch",
                             lines=["The war table shows every road in Aeloria. Lately, too many red pins.",
                                    "Bandits on the south road, wolves in the north woods, and the wards flickering. Busy season."]))
        sc.add_entity(Entity(66, 19, "@", C_GOLD, "Treasurer Ostric", npc_id="treasurer_ostric", title="Royal Treasury",
                             lines=["The vault opens only by the King's word. I don't make the rules. I just count them.",
                                    "Do not lean on the vault door. It has feelings. Expensive ones."]))
        sc.add_entity(Entity(45, 36, "@", fg(210, 210, 220), "Steward Aubrey", title="Royal Steward",
                             lines=["Welcome to Castle Lumeris. The throne room lies straight ahead — kneel at the gilded step.",
                                    "The library is through the west door of the throne room. Please, no food near the codices."]))
        for (x, y) in ((47, 12), (52, 12), (46, 30), (53, 30)):
            sc.add_entity(Entity(x, y, "G", gc, "Royal Guard", kind="guard", lines=gl, title="Castle Lumeris"))
        sc.add_entity(Entity(34, 16, "G", gc, "Royal Guard", kind="guard", lines=gl, ai="patrol",
                             patrol=[(34, 16), (34, 29), (65, 29), (65, 16)]))
        sc.add_entity(Entity(10, 28, "G", gc, "Undercroft Guard", kind="guard", title="Guard Room",
                             lines=["The stairs lead down to the cells and the old crypt. Watch your head.",
                                    "Prisoners below. Mostly forgers and pickpockets. One poet. He's the worst."]))
        sc.add_entity(Entity(20, 35, "@", fg(235, 190, 255), "Lady-in-waiting Mirelle", ai="wander", radius=6,
                             lines=["The Princess walks here when she cannot sleep. Which is most nights, lately.",
                                    "Have you seen the moon lilies? They only open for the Queen."]))
        return sc

    def _refresh_keep(self, sc):
        """Morvane leaves his study once he is unmasked."""
        for e in sc.entities:
            if e.data.get("role") == "morvane":
                e.alive = not (kingdom_past(self.player, "cp_queen") or pflags(self.player).get("valdmere_regent_dead"))

    # ── royal dialogue ──────────────────────────────────────────
    def _king(self, scene, player, ent):
        f = pflags(player)
        k = kingdom_step(player)
        lines = story_lines("king_aldren", player)
        # finale already done (step just completed via on_talk) → rewards
        if kingdom_past(player, "cp_crowned") and not f.get("valdmere_title"):
            self._coronation(scene, player, ent)
            return None
        if lines:
            scene.say_lines(ent, lines)
            return None
        if k is None:
            scene.say_lines(ent, [pick([
                "Rise, traveller. Valdmere welcomes all who come in peace.",
                "You stand in Castle Lumeris, seat of the Valdmere line for four hundred years. Be welcome.",
                "Our realm is at peace — mostly. Speak with my Lord Commander if you seek honest work for your blade.",
            ])])
            if f.get("demon_pact"):
                scene.talk_box(ent, "...Though I am told you have dealings with Duskthorn. I will judge you by your deeds here, not there.", player)
        return None

    def _coronation(self, scene, player, ent):
        f = pflags(player)
        scene.say_lines(ent, [
            "By the light of the restored wards, and by my own hand — kneel.",
            "Rise, Knight-Protector of Valdmere. The Crown owes you its life, and so do I.",
            "Take Lumeris, the blade of the first king. And know that the treasury is open to you, now and always.",
        ])
        f["valdmere_title"] = "Knight-Protector of Valdmere"
        f["valdmere_treasury_open"] = True
        if not getattr(player, "title", None):
            try:
                player.title = "Knight-Protector of Valdmere"
            except Exception:
                pass
        give_item(player, "Lumeris, Blade of the White Crown", scene=scene)
        give_item(player, "Signet of the Crown", scene=scene)
        # Elowen's offer
        el = next((e for e in scene.entities if e.npc_id == "princess_elowen"), None) or ent
        scene.say_lines(el, [
            "Father. Mother. I have read every book in the Royal Library twice.",
            "The world beyond the walls is the only one left. Knight-Protector — will you take me with you?",
        ])
        if try_recruit(player, "elowen", scene):
            f["valdmere_elowen_joined"] = True
            if el is not ent:
                el.alive = False
            scene.message(f"{C_GOLD}★ Princess Elowen joins your party!{R_}")
        else:
            f["valdmere_elowen_offer"] = True
            scene.message(f"{C_LILAC}Elowen will wait in the throne room until you are ready.{R_}")

    def _queen(self, scene, player, ent):
        k = kingdom_step(player)
        lines = story_lines("queen_seraphine", player)
        if k == "cp_regent" and not pflags(player).get("valdmere_queen_told"):
            pflags(player)["valdmere_queen_told"] = True
            scene.say_lines(ent, ["Morvane took the chain-key from my husband's own neck while he slept.",
                                  "The crypt lies below the guard room, past the cells. The gaoler will open it for you now.",
                                  "Take this. My mother's — it turned a blade once. Let it turn another."])
            give_item(player, "Aegis of the Pale Tower", scene=scene)
            return None
        if lines:
            scene.say_lines(ent, lines)
            return None
        scene.talk_box(ent, pick(["Welcome to Lumeris. Do try the moon-lily tea; it is the only thing in this castle that is not cold.",
                                  "A queen hears everything, eventually. Usually from her daughter.",
                                  "Be gracious at court, traveller. Graciousness is cheaper than swords and lasts longer."]), player)
        return None

    def _elowen(self, scene, player, ent):
        f = pflags(player)
        if f.get("valdmere_elowen_offer") and not f.get("valdmere_elowen_joined"):
            scene.talk_box(ent, "Is today the day? I have packed. Twice.", player)
            if try_recruit(player, "elowen", scene):
                f["valdmere_elowen_joined"] = True
                ent.alive = False
                return f"{C_GOLD}★ Princess Elowen joins your party!{R_}"
            return None
        scene.say_lines(ent, lines_with_story("princess_elowen", player,
                                              ["The stars over the Academy are brighter than anywhere in Aeloria. I counted."]))
        return None

    def _ilvaris(self, scene, player, ent):
        lines = story_lines("archmage_ilvaris", player)
        if lines:
            scene.say_lines(ent, lines)
            return None
        scene.talk_box(ent, pick(["The wards are woven from four centuries of royal blood and moonlight. Delicate things.",
                                  "If you have talent with the arcane, the Academy lectures are open to the public. For a fee.",
                                  "I sense no great curse on you. A small one, perhaps. You stubbed your toe this morning."]), player)
        return None

    def _commander(self, scene, player, ent):
        lines = story_lines("lord_commander", player)
        if lines:
            scene.say_lines(ent, lines)
            return None
        scene.talk_box(ent, pick(["Garran Vale, Lord Commander. If you want to test yourself, Knight Cassia at the barracks has been asking for a real opponent.",
                                  "Valdmere has not fallen in four hundred years. It will not fall on my watch."]), player)
        return None

    def _morvane(self, scene, player, ent):
        lines = story_lines("chancellor_morvane", player)
        if lines:
            scene.say_lines(ent, lines)
            return None
        scene.talk_box(ent, pick(["The Lord Chancellor does not have time for adventurers. The Lord Chancellor is talking to you now. Be quick.",
                                  "Taxes, tariffs, tithes. The music of a well-run realm."]), player)
        return None

    def _quill(self, scene, player, ent):
        k = kingdom_step(player)
        f = pflags(player)
        if k == "cp_codex" and not f.get("valdmere_codex_access"):
            f["valdmere_codex_access"] = True
            scene.say_lines(ent, ["The Archmage sent you? Then you may read the Forbidden Codex. It's on the table behind me.",
                                  "Wash your hands. No, really."])
            return None
        scene.talk_box(ent, pick(["Shh. This is a library.", "Books are borrowed, never stolen. Unless they're boring.",
                                  "The Forbidden Codex is forbidden. It says so on the cover. In three languages."]), player)
        return None

    def _codex(self, scene, player, ent):
        f = pflags(player)
        if kingdom_step(player) == "cp_codex":
            if not f.get("valdmere_codex_access"):
                return f"{C_DIM}A lock of silver wire holds the codex shut. Ask Librarian Quill.{R_}"
            scene.say_lines(ent, ["You turn the brittle pages. 'On Hollow Crowns, and the Feeding Thereof'...",
                                  "'...the crown drinketh of the wearer's line, and poureth it to the one who holdeth the chain-key...'",
                                  "The next page — 'On the Breaking of Hollow Crowns' — has been cut out with a very sharp knife."])
            set_flag(player, "valdmere_clue_codex", True, scene)
            return None
        return f"{C_DIM}The Forbidden Codex, chained to its table. The lock is silver wire.{R_}"

    def _vault_door(self, scene, player):
        f = pflags(player)
        if f.get("valdmere_treasury_open"):
            return f"{C_GOLD}The vault door swings open at the sight of your signet.{R_}"
        scene.px, scene.py = 68, 18
        return f"{C_DIM}The vault door is sealed with the royal sigil. It opens only by the King's word.{R_}"

    def _coffers(self, scene, player):
        f = pflags(player)
        if not f.get("valdmere_treasury_open"):
            return None
        if f.get("valdmere_coffers_claimed"):
            return f"{C_DIM}The coffers are counted, sealed and smug about it.{R_}"
        f["valdmere_coffers_claimed"] = True
        gold = 1500 + 100 * player.level
        player.gold += gold
        give_item(player, "Royal Guard Cloak", scene=scene)
        give_item(player, "Elixir of Life", scene=scene)
        return f"{C_GOLD}★ The King's gratitude: +{gold} gold from the royal coffers!{R_}"

    # ── undercroft & crypt ───────────────────────────────────────
    def undercroft(self, entry="stairs"):
        sc = self.scenes.get("under")
        if sc is None:
            sc = self._build_under()
            self.scenes["under"] = sc
        sc.result = None
        sc.px, sc.py = 3, 3
        self._refresh_under(sc)
        return sc

    def _build_under(self):
        sc = CastleScene("THE UNDERCROFT", parse_map(UNDER_MAP), palette=UNDER_PAL, start=(3, 3),
                         subtitle="beneath Castle Lumeris", colour=fg(150, 140, 180), world=self.world,
                         fog=True, sight=8)
        for x, y in sc.find("<"):
            sc.add_door(x, y, "Stairs up to the keep", lambda s, p: s.leave("to_keep_stairs"), tile="<")
        for x, y in sc.find("g"):
            sc.add_door(x, y, "The sealed Crypt of Kings", self._crypt_gate, tile=None)
        sc.add_label(56, 1, "", C_DIM)
        sc.add_entity(Entity(8, 6, "@", fg(170, 150, 120), "Gaoler Brum", npc_id="gaoler_brum", title="Gaoler",
                             interact=self._gaoler))
        prisoners = [
            (18, 8, "Silas the Forger", "prisoner_silas", self._silas),
            (30, 8, "Pickpocket Nell", None, None),
            (24, 13, "Poet Ambrose", None, None),
            (42, 13, "Smuggler Kett", None, None),
        ]
        lines = {
            "Pickpocket Nell": ["I only borrowed it! The purse, I mean. And the horse.",
                                "Get me out and I'll teach you to lift a ring off a duke. No? Rude."],
            "Poet Ambrose": ["Oh grey stone, oh cruel bars, oh soup that tastes of shoe—",
                             "They jailed me for satire. The Chancellor has no sense of humour."],
            "Smuggler Kett": ["Sunspire silk, Duskthorn brimstone... I moved anything. Even crowns, once. Ha. Forget I said that."],
        }
        for (x, y, n, nid, fn) in prisoners:
            sc.add_entity(Entity(x, y, "@", fg(160, 150, 140), n, npc_id=nid, title="prisoner", interact=fn,
                                 lines=lines.get(n, [])))
        # crypt guardians (only while the Regent lives)
        for (x, y) in ((58, 6), (58, 15)):
            sc.add_entity(Entity(x, y, "h", fg(150, 110, 210), "Hollow Knight", kind="undead", hostile=True,
                                 ai="chase", on_contact=self._hollow_knight, data={"crypt": True}))
        sc.add_entity(Entity(67, 10, "♛", fg(170, 100, 230), "The Hollow Regent", kind="boss", hostile=True,
                             on_contact=self._regent, data={"crypt": True, "regent": True}))
        return sc

    def _refresh_under(self, sc):
        f = pflags(self.player)
        live = (not f.get("valdmere_regent_dead")) and kingdom_step(self.player) == "cp_regent"
        for e in sc.entities:
            if e.data.get("crypt") and not e.data.get("slain"):
                e.alive = live

    def _gaoler(self, scene, player, ent):
        k = kingdom_step(player)
        if k == "cp_regent":
            scene.say_lines(ent, ["The Queen's orders? Then may the old kings forgive me. Morvane went through that gate an hour past.",
                                  "I'll unseal it. Whatever's in there now, it isn't the Lord Chancellor any more."])
            pflags(player)["valdmere_crypt_open"] = True
            return None
        scene.talk_box(ent, pick(["Cells to the east. Crypt beyond. Nobody goes in the crypt.",
                                  "Brum, Gaoler of Lumeris, thirty-one years. The soup is my own recipe.",
                                  "That gate's been sealed since King Aldren the First. Don't touch it. It hums."]), player)
        return None

    def _silas(self, scene, player, ent):
        k = kingdom_step(player)
        if kingdom_at_least(player, "cp_informant") and not kingdom_past(player, "cp_regent"):
            scene.say_lines(ent, ["You're the King's hound. Listen: a year ago a man paid me to forge a Sultan's bill of sale.",
                                  "Paid in Chancellery gold. Then I was arrested for 'unrelated forgery'. Funny, that."])
            pflags(player)["valdmere_silas_clue"] = True
            return None
        scene.talk_box(ent, "I'm innocent. Mostly. Ask me again when someone important is listening.", player)
        return None

    def _crypt_gate(self, scene, player):
        f = pflags(player)
        if f.get("valdmere_regent_dead"):
            return f"{C_DIM}The Crypt of Kings lies quiet. The old kings sleep easier now.{R_}"
        if kingdom_step(player) == "cp_regent" and f.get("valdmere_crypt_open"):
            for (x, y) in scene.find("g"):
                scene.set_tile(x, y, "r")
                scene.triggers.pop((x, y), None)
            for e in scene.entities:
                if e.data.get("crypt") and not e.data.get("slain"):
                    e.alive = True
            return f"{C_LILAC}The seal dissolves with a sigh. Cold violet light spills from the Crypt of Kings.{R_}"
        if kingdom_step(player) == "cp_regent":
            return f"{C_LILAC}The gate is sealed. Gaoler Brum keeps the warding words.{R_}"
        return f"{C_DIM}A gate of black iron, sealed with violet runes. It hums faintly.{R_}"

    def _hollow_knight(self, scene, player, ent):
        enemy = make_elite("Royal Guard", player, zone="dungeon_deep", danger=4, mult=1.3)
        enemy.name = "Hollow Knight"
        res = scene.fight_enemy(player, enemy)
        if res == "victory":
            ent.alive = False
            ent.data["slain"] = True
            return f"{C_LILAC}The Hollow Knight's armour collapses, empty.{R_}"
        ent.cooldown = 3
        return None

    def _regent(self, scene, player, ent):
        f = pflags(player)
        ent_view = Entity(0, 0, "♛", fg(170, 100, 230), "The Hollow Regent")
        scene.say_lines(ent_view, [
            "Morvane sits on the hollow throne, the crown fused to his brow. His eyes are two empty rings of violet light.",
            "'Twenty years I balanced their ledgers. Twenty years they never once looked up. Now the realm will look at ME.'",
        ])
        boss = make_boss("The Hollow Regent", player, power=1.5)
        if f.get("demon_pact"):
            scene.say_lines(Entity(0, 0, "D", fg(230, 60, 40), "Demon Lord Kharzul"), [
                "Brimstone fills the crypt. Kharzul steps out of a curtain of fire, true to his word.",
                "'My forefathers forged this crown. I unmake it. Strike, mortal — I hold the chain.'",
            ])
            boss.hp = int(boss.hp * 0.65)
            try:
                boss.atk = int(boss.atk * 0.85)
            except Exception:
                pass
            player.hp = min(player.max_hp, player.hp + player.max_hp // 3)
            scene.message(f"{C_RED}Kharzul's hellfire scorches the Regent! (-35% HP){R_}")
        elif f.get("demon_war"):
            scene.message(f"{C_DIM}No demon will come to help you. You face the Regent alone.{R_}")
        try:
            if f.get("crowns_dawnglass"):
                boss.defense = max(0, int(getattr(boss, "defense", 0) * 0.7))
                scene.message(f"{C_CYAN}The Dawnglass Shard blazes — the crown's ward cracks!{R_}")
        except Exception:
            pass
        res = scene.fight_enemy(player, boss, allow_escape=False)
        if res == "victory":
            f["valdmere_regent_dead"] = True
            ent.alive = False
            for e in scene.entities:
                if e.data.get("crypt"):
                    e.alive = False
            return f"{C_GOLD}★ The Hollow Crown shatters. Return to the King.{R_}"
        return None


def mini_shop(player, title, stock, colour=C_GOLD):
    """Tiny shop for castle vendors. stock: list of (item name, price)."""
    msg = ""
    while True:
        clr()
        print(C(f"\n{colour}{B_}══ {title} ══{R_}"))
        print(C(f"{C_GOLD}Gold: {player.gold}g{R_}\n"))
        avail = []
        for name, price in stock:
            it = make_reward(name)
            if it is None:
                continue
            avail.append((name, price, it))
        for i, (name, price, it) in enumerate(avail, 1):
            desc = ""
            if hasattr(it, "stat_line"):
                desc = it.stat_line()
            elif getattr(it, "description", ""):
                desc = it.description
            col = it.rarity_col() if hasattr(it, "rarity_col") else C_WHITE
            print(C(f"{C_GOLD}[{i}]{R_} {col}{name:<32}{R_} {C_GOLD}{price:>5}g{R_}  {C_DIM}{desc}{R_}"))
        if msg:
            print(C(f"\n{msg}"))
            msg = ""
        print(C(f"\n{C_GOLD}[0]{R_} Leave"))
        try:
            ch = input(C(f"\n{C_GOLD}>{R_} ")).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if ch in ("0", ""):
            return
        if not ch.isdigit() or not (1 <= int(ch) <= len(avail)):
            continue
        name, price, it = avail[int(ch) - 1]
        if player.gold < price:
            msg = f"{C_RED}Not enough gold.{R_}"
            continue
        if player.add_item(it):
            player.gold -= price
            msg = f"{C_GREEN}Bought {name}.{R_}"
        else:
            msg = f"{C_RED}Your bag is full.{R_}"


def enter_valdmere(world, player, loc=None, autosave=None):
    """ENTER handler for the capital tile."""
    try:
        v = Valdmere(world, player, loc, autosave)
        res = v.run()
    except Exception as e:
        _log(f"valdmere crashed: {e!r}")
        import traceback
        _log(traceback.format_exc())
        res = "left"
    clr()
    if res == "defeat" or not player.is_alive():
        if world is not None:
            world._handle_defeat(player)
        return "defeat"
    if world is not None:
        world.last_msg = f"{C_MARBLE}You leave the white walls of Valdmere behind.{R_}"
    return "left"
