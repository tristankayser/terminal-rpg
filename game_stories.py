"""
game_stories.py — Main storylines, side stories and the story engine.

Main stories (one is picked at character creation; 4+ supported — feature
modules such as game_capital register extra ones into MAIN_STORIES):
  The Dragon's Curse · The Shadow Conspiracy · The Lost Kingdom
  (+ The Crown's Plea, registered by game_capital when present)

Side stories are discovered while exploring (towns, ports, mines, world
structures, flags set by castles ...).

STEP SCHEMA (all keys except id/title/type are optional)
  id               stable id — saves remember progress by id, so steps can be
                   inserted/reordered later without breaking old saves
  title, desc      journal text
  type             kill | dungeon | dragon | visit | talk | flag | choice | item
  target           str or list of str (any of them counts)
                     kill    enemy name            dungeon/dragon  dungeon name
                     visit   location name, or "type:<loc type>" (any of that type)
                     talk    keyword or "npc:<id>"; "npc:prefix*" wildcard
                     flag    player.flags key (list = all of them)
                     item    item name in the bag
  required         count (default 1). visit/talk count DISTINCT targets
                   (3-clue rule: target=[a, b, c], required=1 or 2)
  any_npc          talk: talking to any npc ("npc:*") also counts
  alt              extra [{"type":..,"target":..}] that also satisfy the step
  options          choice: [{"key","label","flag","desc"}] — the step completes
                   when one option's flag is set (by us or by castle content)
  prompt           choice: question text shown in the decision popup
  at               choice: only offer the decision popup when visiting this
                   location name (otherwise right away / from the journal)
  external         choice: decided elsewhere (e.g. at a castle) — never popped up
  consume          item: remove the items when the step completes
  requires_level   chapter gate: progress only counts from this level on
  needs/fallback   needs="castles": if game_capital is missing, the step uses
                   fallback={type,target,desc} instead (stories never soft-lock)
  skip_if/only_if  flag name(s): step is skipped when advancing
  act              chapter heading shown in the journal from this step on
  hint             where to look (journal)
  reward_gold, reward_exp, reward_items[list of names], set_flags[list],
  unlock_side[list of side story ids]
  completion_text  popup text when done
  dialogue         {npc_id: [lines]} — what that NPC says (story-aware) while
                   this step is current, or right after they completed it
  events           {npc_id: {"lines":[..], "fight":"Boss", "flag":"key"}} —
                   returned by npc_event() while this step is current

Cross-module contract (used by game_scene, castles, towns, structures):
  on_kill / on_dungeon_clear / on_visit(name, player, loc_type=None)
  on_talk(keyword, player)       — keyword may be "npc:<id>"; side stories too
  check_flags(player)            — call after setting flags; also checks items
  npc_dialogue(npc_id, player)   -> list[str] | None
  npc_event(npc_id, player)      -> dict | None
  flush_story_popups()           — show completions that happened inside scenes
All hooks return a list of (kind, step) completions ("main"/"side").
"""

from __future__ import annotations

import os
import random
from game_term import C, clr, W, H, _vis

_R = "\033[0m"; _B = "\033[1m"
def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"
_GOLD = _fg(255, 215, 0); _WHITE = _fg(255, 255, 255); _DIM = _fg(110, 110, 120)
_GREEN = _fg(80, 200, 80); _RED = _fg(220, 60, 60); _CYAN = _fg(80, 220, 220)
_YELL = _fg(240, 200, 60); _PURP = _fg(180, 80, 220); _ORAN = _fg(220, 140, 40)
_GREY = _fg(160, 160, 170)

STORY_SAVE_VERSION = 2

# Step ids of the ORIGINAL (save version 1) stories, in their old order.
# Version-1 saves only stored a step INDEX; this table maps that index to the
# step id, which is then looked up in the (longer) current story.
LEGACY_STEP_IDS = {
    "dragon_curse":      ["dc_1", "dc_2", "dc_3", "dc_4"],
    "shadow_conspiracy": ["sc_1", "sc_2", "sc_3", "sc_4"],
    "lost_kingdom":      ["lk_1", "lk_2", "lk_3", "lk_4"],
    "missing_merchant":  ["mm_1", "mm_2"],
    "haunted_mine":      ["hm_1"],
    "bandit_lord":       ["bl_1", "bl_2"],
    "sea_serpent":       ["ss_1"],
}

from game_story_data import MAIN_STORIES, SIDE_STORIES, EPILOGUES  # noqa: E402

# ── Kingdom story registration (cross-team contract #2) ──────────
KINGDOM_STORY_ID_DEFAULT = "crowns_plea"
try:
    from game_capital import KINGDOM_STORY_ID, KINGDOM_STORY
    MAIN_STORIES[KINGDOM_STORY_ID] = KINGDOM_STORY
except Exception:
    pass


# ═════════════════════════════════════════════════════════════════
# Definitions: normalising and external registration
# ═════════════════════════════════════════════════════════════════

def _log(msg):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "a") as f:
            f.write(f"stories: {msg}\n")
    except Exception:
        pass


def _normalise_story(sid, story):
    """Fill in defaults so partial story dicts (from other modules) are safe."""
    if not isinstance(story, dict):
        return False
    story.setdefault("title", sid.replace("_", " ").title())
    story.setdefault("colour", _GOLD)
    story.setdefault("icon", "*")
    story.setdefault("intro", "")
    steps = story.get("steps")
    if not isinstance(steps, list) or not steps:
        return False
    seen = set()
    for i, st in enumerate(steps):
        st.setdefault("id", f"{sid}_{i + 1}")
        if st["id"] in seen:
            _log(f"duplicate step id {st['id']} in {sid}")
        seen.add(st["id"])
        st.setdefault("title", f"Chapter {i + 1}")
        st.setdefault("desc", "")
        st.setdefault("type", "flag")
        st.setdefault("target", "")
        st.setdefault("required", 1)
        st.setdefault("reward_gold", 0)
        st.setdefault("reward_exp", 0)
        st.setdefault("completion_text", "")
        if st["type"] == "choice":
            st.setdefault("options", [])
    return True


def _normalise_all():
    for table in (MAIN_STORIES, SIDE_STORIES):
        for sid in list(table):
            if not _normalise_story(sid, table[sid]):
                _log(f"story {sid} is malformed and was ignored")
                table.pop(sid, None)


_EXT_TRIES = [0]


def ensure_external_stories():
    """(Re)try registering stories owned by feature modules. Cheap after the
    first success; gives up after a few failed attempts (module missing)."""
    if KINGDOM_STORY_ID_DEFAULT in MAIN_STORIES or _EXT_TRIES[0] >= 3:
        return
    _EXT_TRIES[0] += 1
    try:
        from game_capital import KINGDOM_STORY_ID, KINGDOM_STORY
        if KINGDOM_STORY_ID not in MAIN_STORIES and _normalise_story(KINGDOM_STORY_ID, KINGDOM_STORY):
            MAIN_STORIES[KINGDOM_STORY_ID] = KINGDOM_STORY
    except Exception:
        pass


_normalise_all()

_FEATURES = {}


def _feature(name):
    """Is an optional feature module available? ('castles' -> game_capital)."""
    if name not in _FEATURES:
        mod = {"castles": "game_capital", "structures": "game_structures"}.get(name, name)
        try:
            import importlib.util
            _FEATURES[name] = importlib.util.find_spec(mod) is not None
        except Exception:
            _FEATURES[name] = False
    return _FEATURES[name]


def effective_step(step):
    """The step as it applies in this installation (castle fallbacks)."""
    if step and step.get("needs") and step.get("fallback") and not _feature(step["needs"]):
        eff = dict(step)
        eff.update(step["fallback"])
        return eff
    return step


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _step_pairs(step):
    """All (type, target) pairs that satisfy a step."""
    t = "dungeon" if step["type"] == "dragon" else step["type"]
    pairs = [(t, x) for x in _as_list(step.get("target"))]
    for a in step.get("alt", []) or []:
        try:
            at = "dungeon" if a["type"] == "dragon" else a["type"]
            for x in _as_list(a["target"]):
                pairs.append((at, x))
        except Exception:
            pass
    return pairs


def _with_option(step, opt):
    """A copy of a choice step carrying the chosen option's text/rewards."""
    s = dict(step)
    s["chosen"] = opt.get("key")
    s["chosen_label"] = opt.get("label", opt.get("key"))
    if opt.get("text"):
        s["completion_text"] = opt["text"]
    for k in ("reward_gold", "reward_exp"):
        if opt.get(k):
            s[k] = (s.get(k, 0) or 0) + opt[k]
    for k in ("reward_items", "set_flags", "unlock_side"):
        if opt.get(k):
            s[k] = list(s.get(k, []) or []) + list(opt[k])
    return s


def _make_item(name):
    try:
        from game_items import make_item
        it = make_item(name)
        if it is not None:
            return it
    except Exception:
        pass
    try:
        from game_items import ITEM_POOL
        if name in ITEM_POOL:
            return ITEM_POOL[name]()
    except Exception:
        pass
    return None


def _new_state():
    return {"step_idx": 0, "progress": 0, "complete": False, "step_id": None, "hits": []}


# ═════════════════════════════════════════════════════════════════
# Popup queue — completions that happen inside scenes / hooks are queued
# here and shown by show_story_completion / flush_story_popups.
# ═════════════════════════════════════════════════════════════════

_QUEUE = []      # dicts: {"kind": main|side|unlock|choice|epilogue, ...}


def _queue(entry):
    _QUEUE.append(entry)


def pending_popups():
    return len(_QUEUE)


def clear_popups():
    del _QUEUE[:]


# ═════════════════════════════════════════════════════════════════
# StoryManager
# ═════════════════════════════════════════════════════════════════

def _prop(key):
    return property(lambda s: s._main[key], lambda s, v: s._main.__setitem__(key, v))


class StoryManager:
    """Tracks the main story, side stories and their step progress."""

    main_step_idx = _prop("step_idx")
    main_progress = _prop("progress")
    main_complete = _prop("complete")
    main_step_id = _prop("step_id")
    main_hits = _prop("hits")

    def __init__(self):
        self.main_story_id = None
        self._main = _new_state()
        self.side_stories = {}       # sid -> state dict (step_idx, progress, complete, step_id, hits)
        self.bandit_kill_count = 0
        self.choices = {}            # "story:step" -> option key
        self.log = []                # ["story:step", ...] completed, in order
        self.epilogues_seen = []
        self.slain = []              # distinct enemy names ever defeated (retro kill steps)
        self._last_talk = None       # (npc_id, step) — for npc_dialogue
        self._in_dialogue = False

    # ── lookups ──────────────────────────────────────────────────
    def get_main_story(self):
        if self.main_story_id and self.main_story_id not in MAIN_STORIES:
            ensure_external_stories()
        return MAIN_STORIES.get(self.main_story_id)

    @staticmethod
    def _story(kind, sid):
        return (MAIN_STORIES if kind == "main" else SIDE_STORIES).get(sid)

    def _state(self, kind, sid):
        if kind == "main":
            return self._main if sid == self.main_story_id else None
        return self.side_stories.get(sid)

    def _cur(self, story, st):
        """Raw current step of a track (self-heals the index from step_id)."""
        if not story or not st or st.get("complete"):
            return None
        steps = story["steps"]
        idx = st.get("step_idx", 0)
        sid = st.get("step_id")
        if sid and (not (0 <= idx < len(steps)) or steps[idx]["id"] != sid):
            for i, s in enumerate(steps):
                if s["id"] == sid:
                    st["step_idx"] = idx = i
                    break
        if not (0 <= idx < len(steps)):
            return None
        if not sid:
            st["step_id"] = steps[idx]["id"]
        return steps[idx]

    def get_main_step(self):
        return effective_step(self._cur(self.get_main_story(), self._main))

    def get_side_step(self, story_id):
        return effective_step(self._cur(SIDE_STORIES.get(story_id), self.side_stories.get(story_id)))

    def _tracks(self):
        out = []
        story = self.get_main_story()
        if story and not self._main["complete"]:
            out.append(("main", self.main_story_id, story, self._main))
        for sid, st in list(self.side_stories.items()):
            s = SIDE_STORIES.get(sid)
            if s and not st.get("complete"):
                out.append(("side", sid, s, st))
        return out

    def has_completed(self, step_id, story_id=None):
        if story_id:
            return f"{story_id}:{step_id}" in self.log
        return any(e.split(":", 1)[-1] == step_id for e in self.log)

    def is_current(self, step_id):
        for kind, sid, story, st in self._tracks():
            cur = self._cur(story, st)
            if cur and cur["id"] == step_id:
                return True
        return False

    def choice_of(self, step_id):
        for k, v in self.choices.items():
            if k.split(":", 1)[-1] == step_id:
                return v
        return None

    def side_done_count(self):
        return sum(1 for st in self.side_stories.values() if st.get("complete"))

    @staticmethod
    def _gated(step, player):
        lv = step.get("requires_level", 0) or 0
        return bool(lv and player is not None and getattr(player, "level", 99) < lv)

    @staticmethod
    def _skipped(step, player):
        flags = getattr(player, "flags", {}) if player is not None else {}
        if step.get("skip_if") and any(flags.get(f) for f in _as_list(step["skip_if"])):
            return True
        if step.get("only_if") and not all(flags.get(f) for f in _as_list(step["only_if"])):
            return True
        return False

    # ── main story control ───────────────────────────────────────
    def start_main(self, story_id):
        ensure_external_stories()
        self.main_story_id = story_id
        self._main = _new_state()
        story = MAIN_STORIES.get(story_id)
        if story:
            self._main["step_id"] = story["steps"][0]["id"]

    def advance_main(self, player=None):
        story = self.get_main_story()
        if story:
            self._advance("main", self.main_story_id, story, self._main, player)

    # ── side stories ─────────────────────────────────────────────
    def unlock_side(self, story_id, player=None, announce=False):
        """Start a side story. Returns True if it was newly unlocked."""
        if story_id in self.side_stories or story_id not in SIDE_STORIES:
            return False
        st = _new_state()
        st["step_id"] = SIDE_STORIES[story_id]["steps"][0]["id"]
        self.side_stories[story_id] = st
        if announce:
            _queue({"kind": "unlock", "sid": story_id})
        return True

    def advance_side(self, story_id, player=None):
        story = SIDE_STORIES.get(story_id)
        st = self.side_stories.get(story_id)
        if story and st and not st.get("complete"):
            self._advance("side", story_id, story, st, player)

    # ── core progression ─────────────────────────────────────────
    def _advance(self, kind, sid, story, st, player):
        steps = story["steps"]
        i = st.get("step_idx", 0) + 1
        while i < len(steps) and (self._skipped(steps[i], player)
                                  or f"{sid}:{steps[i]['id']}" in self.log):
            i += 1
        if i >= len(steps):
            st["complete"] = True
            st["step_idx"] = len(steps) - 1
            st["step_id"] = steps[-1]["id"]
            st["progress"] = 0
            st["hits"] = []
            if kind == "main":
                _queue({"kind": "epilogue", "sid": sid, "mgr": self, "player": player})
            return None
        nxt = steps[i]
        st.update(step_idx=i, step_id=nxt["id"], progress=0, hits=[])
        if (nxt["type"] == "choice" and not nxt.get("at") and not nxt.get("external")):
            _queue({"kind": "choice", "story_kind": kind, "sid": sid, "step_id": nxt["id"],
                    "mgr": self, "player": player})
        return nxt

    def _complete(self, kind, sid, story, st, step, player, completed):
        """Grant rewards, log and advance. `step` is the effective step."""
        st["progress"] = step.get("required", 1)
        items = []
        if player is not None:
            player.gold += step.get("reward_gold", 0) or 0
            if step.get("reward_exp"):
                try:
                    player.gain_exp(step["reward_exp"])
                except Exception:
                    pass
            for name in step.get("reward_items", []) or []:
                it = _make_item(name)
                if it is not None:
                    try:
                        if player.add_item(it):
                            items.append(it.name)
                    except Exception:
                        pass
            flags = getattr(player, "flags", None)
            if isinstance(flags, dict):
                for f in step.get("set_flags", []) or []:
                    flags[f] = True
        for side in step.get("unlock_side", []) or []:
            self.unlock_side(side, player, announce=True)
        key = f"{sid}:{step['id']}"
        if key not in self.log:
            self.log.append(key)
        completed.append((kind, step))
        nxt = self._advance(kind, sid, story, st, player)
        _queue({"kind": kind, "sid": sid, "step": step, "next": effective_step(nxt),
                "items": items, "story_done": st.get("complete", False)})

    def _hit(self, step, etype, key, loc_type):
        for t, target in _step_pairs(step):
            if t != etype or target is None:
                continue
            if etype == "visit":
                if target == key or (isinstance(target, str) and target.startswith("type:")
                                     and loc_type and target[5:] == loc_type):
                    return key
            elif etype == "talk":
                if target == key:
                    return key
                if isinstance(target, str) and target.endswith("*") and key.startswith(target[:-1]):
                    return key
            elif target == key:
                return key
        if etype == "talk" and step.get("any_npc") and str(key).startswith("npc:"):
            return key
        return None

    def _event(self, etype, key, player, loc_type=None):
        completed = []
        for kind, sid, story, st in self._tracks():
            step = effective_step(self._cur(story, st))
            if not step or self._gated(step, player):
                continue
            hit = self._hit(step, etype, key, loc_type)
            if hit is None:
                continue
            if etype in ("visit", "talk") or step.get("unique"):
                hits = st.setdefault("hits", [])
                if hit in hits:
                    continue
                hits.append(hit)
                st["progress"] = len(hits)
            else:
                st["progress"] = st.get("progress", 0) + 1
            if etype == "talk" and str(key).startswith("npc:"):
                self._last_talk = (key[4:], step)
            if st["progress"] >= step.get("required", 1):
                self._complete(kind, sid, story, st, step, player, completed)
        completed.extend(self.check_flags(player))
        return completed

    # ── event hooks ──────────────────────────────────────────────
    def on_kill(self, enemy_name, player):
        """Call after every kill. Returns list of (kind, step) completed."""
        if enemy_name == "Bandit":
            self.bandit_kill_count += 1
        if enemy_name and enemy_name not in self.slain and len(self.slain) < 500:
            self.slain.append(enemy_name)
        self._check_unlocks(player)
        return self._event("kill", enemy_name, player)

    def on_dungeon_clear(self, dungeon_name, player):
        return self._event("dungeon", dungeon_name, player)

    def on_visit(self, location_name, player, loc_type=None):
        """Any location (city, castle, structure ...). loc_type enables
        'type:<loc type>' targets."""
        self._check_unlocks(player, visit=(location_name, loc_type))
        return self._event("visit", location_name, player, loc_type)

    def on_talk(self, keyword, player=None):
        """keyword: a legacy keyword ('dragon_rumour') or 'npc:<id>'."""
        self._check_unlocks(player, talk=keyword)
        return self._event("talk", keyword, player)

    def on_step(self, player):
        """Cheap per-move check (flags / items / level unlocks)."""
        return self.check_flags(player)

    def check_flags(self, player):
        """Complete flag / choice / item steps that are satisfied now."""
        completed = []
        if player is None:
            return completed
        self._check_unlocks(player)
        flags = getattr(player, "flags", {}) or {}
        for _ in range(32):                       # cascade through chained steps
            progressed = False
            for kind, sid, story, st in self._tracks():
                step = effective_step(self._cur(story, st))
                if not step or self._gated(step, player):
                    continue
                t = step["type"]
                ok = False
                if t == "kill" and step.get("retro"):
                    ok = any(n in self.slain for n in _as_list(step.get("target")))
                elif t == "flag":
                    names = _as_list(step.get("target"))
                    have = sum(1 for f in names if flags.get(f))
                    st["progress"] = min(have, step.get("required", 1)) if len(names) > 1 else (1 if have else 0)
                    ok = bool(names) and have >= len(names)
                elif t == "choice":
                    for opt in step.get("options", []):
                        if opt.get("flag") and flags.get(opt["flag"]):
                            self.choices[f"{sid}:{step['id']}"] = opt.get("key", opt["flag"])
                            step = _with_option(step, opt)
                            ok = True
                            break
                elif t == "item":
                    cnt = 0
                    try:
                        from game_items import item_count
                        cnt = sum(item_count(player.inventory, n) for n in _as_list(step.get("target")))
                    except Exception:
                        cnt = 0
                    req = step.get("required", 1)
                    st["progress"] = min(cnt, req)
                    ok = cnt >= req
                    if ok and step.get("consume"):
                        try:
                            from game_items import remove_items
                            left = req
                            for n in _as_list(step.get("target")):
                                left -= remove_items(player.inventory, n, left)
                                if left <= 0:
                                    break
                        except Exception:
                            pass
                if ok:
                    self._complete(kind, sid, story, st, step, player, completed)
                    progressed = True
                    break
            if not progressed:
                break
        return completed

    def _check_unlocks(self, player, visit=None, talk=None):
        """Side stories with trigger 'flag', 'level', 'visit', 'talk' or
        'kill_bandits'."""
        flags = getattr(player, "flags", {}) if player is not None else {}
        for sid, story in SIDE_STORIES.items():
            if sid in self.side_stories:
                continue
            trig = story.get("trigger")
            go = False
            if trig == "kill_bandits":
                go = self.bandit_kill_count >= story.get("trigger_count", 10)
            elif trig == "flag":
                go = any(flags.get(f) for f in _as_list(story.get("trigger_flag")))
            elif trig == "level" and player is not None:
                go = getattr(player, "level", 0) >= story.get("trigger_level", 99)
            elif trig == "visit" and visit:
                name, ltype = visit
                for t in _as_list(story.get("trigger_targets")):
                    if t == name or (ltype and t == f"type:{ltype}"):
                        go = True
            elif trig == "talk" and talk:
                go = talk in _as_list(story.get("trigger_targets"))
            if go and story.get("trigger_min_level") and player is not None:
                go = getattr(player, "level", 0) >= story["trigger_min_level"]
            if go:
                self.unlock_side(sid, player, announce=True)

    def on_port_visit(self, port_name, player):
        for sid, story in SIDE_STORIES.items():
            if story.get("trigger") == "port_visit" and port_name in story.get("trigger_towns", []):
                if sid not in self.side_stories:
                    self.unlock_side(sid)
                    return sid
        return None

    def on_town_visit(self, town_name, player):
        unlocked = []
        for sid, story in SIDE_STORIES.items():
            if story.get("trigger") == "town_rumour" and town_name in story.get("trigger_towns", []):
                if sid not in self.side_stories:
                    self.unlock_side(sid)
                    unlocked.append(sid)
        return unlocked

    # ── story-aware NPC hooks ────────────────────────────────────
    def npc_dialogue(self, npc_id, player=None):
        """Story-aware lines for an NPC, or None."""
        if self._in_dialogue:
            return None
        self._in_dialogue = True
        try:
            lines = []
            if self._last_talk and self._last_talk[0] == npc_id:
                d = (self._last_talk[1].get("dialogue") or {}).get(npc_id)
                lines.extend(_as_list(d))
            self._last_talk = None
            for kind, sid, story, st in self._tracks():
                step = effective_step(self._cur(story, st))
                if step and not self._gated(step, player):
                    d = (step.get("dialogue") or {}).get(npc_id)
                    for line in _as_list(d):
                        if line not in lines:
                            lines.append(line)
            try:
                import game_capital
                fn = getattr(game_capital, "story_lines", None)
                extra = fn(npc_id, player) if fn else None
                for line in _as_list(extra):
                    if line and line not in lines:
                        lines.append(line)
            except Exception:
                pass
            return lines or None
        finally:
            self._in_dialogue = False

    def npc_event(self, npc_id, player=None):
        """A one-off story event for this NPC: {"lines","fight","flag"} or None."""
        flags = getattr(player, "flags", {}) if player is not None else {}
        for kind, sid, story, st in self._tracks():
            step = effective_step(self._cur(story, st))
            if not step or self._gated(step, player):
                continue
            ev = (step.get("events") or {}).get(npc_id)
            if not isinstance(ev, dict):
                continue
            if ev.get("flag") and flags.get(ev["flag"]):
                continue
            return dict(ev)
        return None

    # ── HUD / journal helpers ────────────────────────────────────
    def hud_text(self, player=None):
        """One-line HUD summary of the current main step ('' if none)."""
        story = self.get_main_story()
        step = self.get_main_step()
        if not story or not step:
            return ""
        col = story.get("colour", _GOLD)
        if self._gated(step, player):
            return f"  {col}★{step['title']}{_R} {_RED}(Lv {step['requires_level']}){_R}"
        req = step.get("required", 1)
        if step["type"] == "choice":
            return f"  {col}★{step['title']}{_R} {_DIM}[decide]{_R}"
        return f"  {col}★{step['title']}{_R} {_DIM}[{min(self.main_progress, req)}/{req}]{_R}"

    def pending_choices(self, player=None):
        """Choice steps the player can decide right now from the journal."""
        out = []
        for kind, sid, story, st in self._tracks():
            step = effective_step(self._cur(story, st))
            if (step and step["type"] == "choice" and not step.get("external")
                    and not self._gated(step, player)):
                out.append((kind, sid, step))
        return out

    def decide(self, sid, step_id, option_key, player):
        """Resolve a choice step by option key (sets the option's flag)."""
        for kind, s, story, st in self._tracks():
            step = effective_step(self._cur(story, st))
            if s == sid and step and step["id"] == step_id and step["type"] == "choice":
                for opt in step.get("options", []):
                    if opt.get("key") == option_key and opt.get("flag"):
                        player.flags[opt["flag"]] = True
                        return self.check_flags(player)
        return []

    def show_journal(self, player=None):
        try:
            _journal(self, player)
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception as e:      # the journal must never take the game down
            _log(f"journal failed: {e!r}")

    # ── serialise ────────────────────────────────────────────────
    def to_dict(self):
        for kind, sid, story, st in self._tracks():
            self._cur(story, st)                      # make sure step_id is set
        sides = {}
        for sid, st in self.side_stories.items():
            sides[sid] = dict(st, hits=list(st.get("hits", [])))
        return {
            "version":          STORY_SAVE_VERSION,
            "main_story_id":    self.main_story_id,
            "main_step_idx":    self._main["step_idx"],
            "main_progress":    self._main["progress"],
            "main_complete":    self._main["complete"],
            "main_step_id":     self._main.get("step_id"),
            "main_hits":        list(self._main.get("hits", [])),
            "side_stories":     sides,
            "bandit_kill_count": self.bandit_kill_count,
            "choices":          dict(self.choices),
            "log":              list(self.log),
            "epilogues_seen":   list(self.epilogues_seen),
            "slain":            list(self.slain),
        }

    @classmethod
    def from_dict(cls, d):
        """Load any save format. Version-1 saves stored only step indices of
        the old 4-step stories; those are mapped to step ids and then to the
        same step in the current (longer) stories."""
        ensure_external_stories()
        clear_popups()                    # nothing from a previous session
        d = d if isinstance(d, dict) else {}
        sm = cls()
        legacy = int(d.get("version", 1) or 1) < 2
        sm.main_story_id = d.get("main_story_id")
        m = sm._main
        m["step_idx"] = _int(d.get("main_step_idx", 0))
        m["progress"] = _int(d.get("main_progress", 0))
        m["complete"] = bool(d.get("main_complete", False))
        m["step_id"] = d.get("main_step_id")
        m["hits"] = list(d.get("main_hits", []) or [])
        for sid, s in (d.get("side_stories") or {}).items():
            if not isinstance(s, dict):
                continue
            st = _new_state()
            st.update(s)
            st["step_idx"] = _int(st.get("step_idx", 0))
            st["progress"] = _int(st.get("progress", 0))
            st["complete"] = bool(st.get("complete", False))
            st["hits"] = list(st.get("hits", []) or [])
            sm.side_stories[sid] = st
        sm.bandit_kill_count = _int(d.get("bandit_kill_count", 0))
        sm.choices = dict(d.get("choices", {}) or {})
        sm.log = list(d.get("log", []) or [])
        sm.epilogues_seen = list(d.get("epilogues_seen", []) or [])
        sm.slain = list(d.get("slain", []) or [])
        if sm.main_story_id:
            sm._migrate(sm.main_story_id, MAIN_STORIES.get(sm.main_story_id), m, legacy)
        for sid, st in sm.side_stories.items():
            sm._migrate(sid, SIDE_STORIES.get(sid), st, legacy)
        return sm

    def _migrate(self, sid, story, st, legacy):
        if not story:
            return                      # unknown story: keep the raw state untouched
        steps = story["steps"]
        ids = [s["id"] for s in steps]
        old_idx = st.get("step_idx", 0)
        saved_id = st.get("step_id")
        target_id = None
        if saved_id in ids:
            target_id = saved_id
        elif legacy and sid in LEGACY_STEP_IDS:
            old = LEGACY_STEP_IDS[sid]
            if 0 <= old_idx < len(old) and old[old_idx] in ids:
                target_id = old[old_idx]
            if not any(e.startswith(f"{sid}:") for e in self.log):
                done = old if st.get("complete") else old[:max(0, old_idx)]
                self.log.extend(f"{sid}:{x}" for x in done)
        if target_id is None:
            new_idx = min(max(0, old_idx), len(steps) - 1)
            if saved_id and saved_id not in ids:
                st["progress"] = 0
                st["hits"] = []
        else:
            new_idx = ids.index(target_id)
        st["step_idx"] = new_idx
        st["step_id"] = ids[new_idx]
        req = steps[new_idx].get("required", 1)
        st["progress"] = max(0, min(st.get("progress", 0), req))
        if st.get("complete"):
            st["step_idx"] = len(steps) - 1
            st["step_id"] = ids[-1]


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ═════════════════════════════════════════════════════════════════
# UI helpers
# ═════════════════════════════════════════════════════════════════

def _wrap(text, width=72):
    out = []
    for para in str(text).split("\n"):
        words = para.split()
        cur = ""
        for w in words:
            if cur and _vis(cur) + 1 + _vis(w) > width:
                out.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}" if cur else w
        out.append(cur)
    return out


def _wait(msg="(Press Enter)"):
    try:
        input(C(f"\n{_DIM}{msg}{_R}"))
    except (EOFError, KeyboardInterrupt):
        pass


def _bar(prog, req, col, width=20):
    req = max(1, req)
    prog = max(0, min(prog, req))
    if req <= width:
        return f"{col}{'█' * prog}{_DIM}{'░' * (req - prog)}{_R}"
    f = int(width * prog / req)
    return f"{col}{'█' * f}{_DIM}{'░' * (width - f)}{_R}"


def _banner(title, col, width=46):
    t = f" {title} "
    pad = max(0, width - _vis(t))
    l = pad // 2
    return [C(f"{col}{_B}╔{'═' * width}╗"),
            C(f"║{' ' * l}{t}{' ' * (pad - l)}║"),
            C(f"╚{'═' * width}╝{_R}")]


def _act_of(story, idx):
    act = None
    for i, s in enumerate(story["steps"]):
        if i > idx:
            break
        if s.get("act"):
            act = s["act"]
    return act


# ═════════════════════════════════════════════════════════════════
# Popups: completions, unlocks, choices, epilogues
# ═════════════════════════════════════════════════════════════════

def show_story_completion(story_type, step):
    """Show a story step completion (called by world/combat code with the
    (kind, step) tuples the hooks return). Afterwards, any queued unlock,
    decision or epilogue popups that followed this completion are shown."""
    entry = None
    for e in _QUEUE:
        if e.get("step") is step and e.get("kind") == story_type:
            entry = e
            break
    if entry is None:
        entry = {"kind": story_type, "step": step, "next": None, "items": [], "sid": None}
    else:
        _QUEUE.remove(entry)
    _show_completion(entry)
    # drain non-step popups unless another step completion is still waiting
    if not any(e.get("kind") in ("main", "side") for e in _QUEUE):
        flush_story_popups()


def flush_story_popups(player=None):
    """Show everything still queued (completions from scenes, unlocks,
    decisions, epilogues). Safe to call any time; returns number shown."""
    shown = 0
    guard = 0
    while _QUEUE and guard < 64:
        guard += 1
        e = _QUEUE.pop(0)
        try:
            k = e.get("kind")
            if k in ("main", "side"):
                _show_completion(e)
            elif k == "unlock":
                _show_unlock(e["sid"])
            elif k == "choice":
                _show_choice(e, player)
            elif k == "epilogue":
                _show_epilogue(e, player)
            shown += 1
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception as ex:
            _log(f"popup failed: {ex!r}")
    return shown


def _show_completion(e):
    step = e["step"]
    kind = e.get("kind", "main")
    clr()
    if kind == "main":
        story = MAIN_STORIES.get(e.get("sid")) or {}
        col = story.get("colour", _GOLD)
        for l in _banner("★  STORY CHAPTER COMPLETE  ★", _GOLD):
            print(l)
        if story:
            print(C(f"\n{col}{_B}{story.get('title', '')}{_R}"))
    else:
        story = SIDE_STORIES.get(e.get("sid")) or {}
        col = story.get("colour", _YELL)
        for l in _banner("✓  SIDE STORY PROGRESS  ✓", _YELL):
            print(l)
        if story:
            print(C(f"\n{col}{_B}{story.get('title', '')}{_R}"))
    print(C(f"\n{_WHITE}{_B}{step.get('title', '')}{_R}\n"))
    for line in _wrap(step.get("completion_text", ""), 74):
        print(C(f"{_GREY}{line}{_R}"))
    rew = []
    if step.get("reward_gold"):
        rew.append(f"{_GOLD}+{step['reward_gold']} Gold{_R}")
    if step.get("reward_exp"):
        rew.append(f"{_CYAN}+{step['reward_exp']} EXP{_R}")
    for n in e.get("items") or []:
        rew.append(f"{_PURP}+ {n}{_R}")
    if rew:
        print(C("\n" + "   ".join(rew)))
    nxt = e.get("next")
    if nxt:
        story_def = (MAIN_STORIES if kind == "main" else SIDE_STORIES).get(e.get("sid")) or {}
        if nxt.get("act") and story_def:
            print(C(f"\n{_GOLD}{_B}{nxt['act']}{_R}"))
        print(C(f"\n{_DIM}Next:{_R} {_WHITE}{nxt.get('title', '')}{_R}"))
        if nxt.get("desc"):
            for line in _wrap(nxt["desc"], 74):
                print(C(f"{_DIM}{line}{_R}"))
        if nxt.get("requires_level"):
            print(C(f"{_ORAN}Recommended level: {nxt['requires_level']}{_R}"))
    elif e.get("story_done"):
        if kind == "main":
            print(C(f"\n{_GOLD}{_B}★ THE STORY IS COMPLETE ★{_R}"))
        else:
            print(C(f"\n{_GREEN}{_B}✓ Side story complete!{_R}"))
    _wait()


def _show_unlock(sid):
    s = SIDE_STORIES.get(sid)
    if not s:
        return
    clr()
    for l in _banner("NEW SIDE STORY", s.get("colour", _YELL)):
        print(l)
    print(C(f"\n{s.get('colour', _YELL)}{_B}{s['title']}{_R}\n"))
    for line in _wrap(s.get("intro", ""), 74):
        print(C(f"{_GREY}{line}{_R}"))
    first = s["steps"][0]
    print(C(f"\n{_DIM}First:{_R} {_WHITE}{first['title']}{_R}"))
    for line in _wrap(effective_step(first).get("desc", ""), 74):
        print(C(f"{_DIM}{line}{_R}"))
    _wait()


def _show_choice(e, player):
    mgr = e.get("mgr")
    player = player or e.get("player")
    if mgr is None or player is None:
        return
    sid, step_id = e["sid"], e["step_id"]
    story = mgr._story(e.get("story_kind", "main"), sid)
    st = mgr._state(e.get("story_kind", "main"), sid)
    step = effective_step(mgr._cur(story, st)) if story else None
    if not step or step["id"] != step_id or step["type"] != "choice":
        return
    if mgr._gated(step, player):
        return
    choose_option(mgr, player, e.get("story_kind", "main"), sid, step)


def choose_option(mgr, player, kind, sid, step, allow_later=True):
    """Decision popup for a choice step. Returns completions (may be [])."""
    story = mgr._story(kind, sid) or {}
    opts = step.get("options", [])
    while True:
        clr()
        for l in _banner("A DECISION AWAITS", story.get("colour", _GOLD)):
            print(l)
        print(C(f"\n{story.get('colour', _GOLD)}{_B}{story.get('title', '')}{_R}  {_DIM}·{_R} {_WHITE}{step['title']}{_R}\n"))
        for line in _wrap(step.get("prompt") or step.get("desc", ""), 74):
            print(C(f"{_GREY}{line}{_R}"))
        print()
        for i, o in enumerate(opts, 1):
            print(C(f"{_GOLD}{_B}[{i}]{_R} {_WHITE}{o.get('label', o.get('key'))}{_R}"))
            if o.get("desc"):
                for line in _wrap(o["desc"], 68):
                    print(C(f"     {_DIM}{line}{_R}"))
        if allow_later:
            print(C(f"\n{_GOLD}[0]{_R} {_DIM}Decide later (from the journal){_R}"))
        try:
            ch = input(C(f"\n{_GOLD}>{_R} ")).strip()
        except (EOFError, KeyboardInterrupt):
            return []
        if ch == "0" and allow_later:
            return []
        if ch.isdigit() and 1 <= int(ch) <= len(opts):
            o = opts[int(ch) - 1]
            try:
                c2 = input(C(f"{_DIM}This choice is permanent. Confirm? (y/n){_R} ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return []
            if c2 not in ("y", "yes"):
                continue
            return mgr.decide(sid, step["id"], o.get("key"), player)


def epilogue_text(mgr, player, sid):
    """Compose the epilogue for a finished main story: the first matching
    story ending ("kind": "ending") followed by every matching world
    paragraph ("kind": "world"). Returns [(title, text)]."""
    flags = getattr(player, "flags", {}) if player is not None else {}
    ending, world = None, []
    for ep in EPILOGUES:
        if ep.get("story") not in (None, sid):
            continue
        try:
            ok = ep["when"](flags, mgr, player) if ep.get("when") else True
        except Exception:
            ok = False
        if not ok:
            continue
        if ep.get("kind") == "ending":
            if ending is None:
                ending = (ep.get("title", ""), ep["text"])
        else:
            world.append((ep.get("title", ""), ep["text"]))
    return ([ending] if ending else []) + world


def _show_epilogue(e, player):
    mgr = e.get("mgr")
    player = player or e.get("player")
    sid = e.get("sid")
    story = MAIN_STORIES.get(sid) or {}
    paras = epilogue_text(mgr, player, sid)
    if mgr is not None and sid not in mgr.epilogues_seen:
        mgr.epilogues_seen.append(sid)
    clr()
    for l in _banner("EPILOGUE", story.get("colour", _GOLD), 50):
        print(l)
    print(C(f"\n{story.get('colour', _GOLD)}{_B}{story.get('title', '')}{_R}\n"))
    used = 8
    for title, text in paras:
        lines = _wrap(text, 76)
        if used + len(lines) + 2 > max(20, H() - 3):
            _wait("(Press Enter to continue)")
            clr()
            used = 0
        if title:
            print(C(f"{_GOLD}{title}{_R}"))
        for line in lines:
            print(C(f"{_GREY}{line}{_R}"))
        print()
        used += len(lines) + 2
    print(C(f"{_DIM}Your adventure continues — the world is still yours to explore.{_R}"))
    _wait()


# ═════════════════════════════════════════════════════════════════
# Journal
# ═════════════════════════════════════════════════════════════════

def _step_lines(mgr, story, st, step, player, col, kind):
    """Detail lines for the current step of a track."""
    out = []
    eff = effective_step(step)
    out.append(f"{_WHITE}{_B}► {eff['title']}{_R}")
    for line in _wrap(eff.get("desc", ""), 70):
        out.append(f"  {_GREY}{line}{_R}")
    if eff.get("hint"):
        for line in _wrap("Hint: " + eff["hint"], 70):
            out.append(f"  {_DIM}{line}{_R}")
    lv = eff.get("requires_level")
    if lv:
        plv = getattr(player, "level", 0) if player is not None else 0
        if plv < lv:
            out.append(f"  {_RED}Recommended Lv {lv} — this chapter will not advance until you reach it (you: Lv {plv}).{_R}")
        else:
            out.append(f"  {_DIM}Recommended Lv {lv}{_R}")
    if eff["type"] == "choice":
        for o in eff.get("options", []):
            out.append(f"  {_GOLD}◆{_R} {_WHITE}{o.get('label', o.get('key'))}{_R}")
            if o.get("desc"):
                out.append(f"      {_DIM}{o['desc']}{_R}")
        if eff.get("external"):
            out.append(f"  {_DIM}(This decision is made in person — see the hint.){_R}")
        else:
            out.append(f"  {_GOLD}Press [D] to make your decision.{_R}")
    else:
        req = eff.get("required", 1)
        prog = min(st.get("progress", 0), req)
        out.append(f"  [{_bar(prog, req, col)}] {col}{prog}/{req}{_R}")
    return out


def _main_lines(mgr, player):
    story = mgr.get_main_story()
    out = []
    if not story:
        if mgr.main_story_id:
            out.append(f"{_DIM}Your chosen story ({mgr.main_story_id}) is not available in this version.{_R}")
        else:
            out.append(f"{_DIM}No main story chosen.{_R}")
        return out
    col = story.get("colour", _GOLD)
    steps = story["steps"]
    st = mgr._main
    idx = st.get("step_idx", 0)
    out.append(f"{col}{_B}{story.get('title', '')}{_R}")
    total = path_length(story)
    done_n = total if st.get("complete") else min(total, sum(
        1 for e in mgr.log if e.startswith(f"{mgr.main_story_id}:")))
    out.append(f"{_DIM}Chapters{_R} [{_bar(done_n, total, col, 30)}] {col}{done_n}/{total}{_R}")
    out.append("")
    last_act = None
    pending_act = None
    shown_act = None
    for i, s in enumerate(steps):
        if s.get("act"):
            last_act = pending_act = s["act"]
        if i >= idx and not st.get("complete"):
            break
        k = f"{mgr.main_story_id}:{s['id']}"
        if k not in mgr.log:
            continue                      # skipped branch / never played
        if pending_act and pending_act != shown_act:
            out.append(f"{_GOLD}{pending_act}{_R}")
            shown_act = pending_act
        extra = ""
        if s["type"] == "choice":
            ch = mgr.choices.get(k)
            lbl = next((o.get("label") for o in s.get("options", []) if o.get("key") == ch), ch)
            if lbl:
                extra = f"  {_DIM}— {lbl}{_R}"
        out.append(f"  {_GREEN}✓{_R} {_GREY}{s['title']}{_R}{extra}")
    if st.get("complete"):
        out.append("")
        out.append(f"{_GREEN}{_B}★ COMPLETED!{_R}  {_DIM}Press [E] to read the epilogue again.{_R}")
        return out
    step = mgr._cur(story, st)
    if step:
        cur_act = _act_of(story, idx)
        if cur_act and cur_act != shown_act:
            out.append(f"{_GOLD}{cur_act}{_R}")
        out.extend("  " + l for l in _step_lines(mgr, story, st, step, player, col, "main"))
        left = path_length({"steps": steps[idx + 1:]})
        if left > 0:
            out.append(f"  {_DIM}… {left} more chapter{'s' if left != 1 else ''} to uncover.{_R}")
    return out


def _side_lines(mgr, player):
    out = []
    if not mgr.side_stories:
        out.append(f"{_DIM}No side stories yet. Talk to people, visit ports and mines,{_R}")
        out.append(f"{_DIM}and explore watchtowers, shrines, camps and ruins to find them.{_R}")
        return out
    active = [(sid, st) for sid, st in mgr.side_stories.items() if not st.get("complete") and sid in SIDE_STORIES]
    done = [(sid, st) for sid, st in mgr.side_stories.items() if st.get("complete") and sid in SIDE_STORIES]
    for sid, st in active:
        s = SIDE_STORIES[sid]
        col = s.get("colour", _YELL)
        n = len(s["steps"])
        out.append(f"{col}{_B}{s['title']}{_R}  {_DIM}(part {st.get('step_idx', 0) + 1}/{n}){_R}")
        step = mgr._cur(s, st)
        if step:
            out.extend("  " + l for l in _step_lines(mgr, s, st, step, player, col, "side"))
        out.append("")
    if done:
        out.append(f"{_GREEN}{_B}Completed:{_R}")
        for sid, st in done:
            out.append(f"  {_GREEN}✓{_R} {SIDE_STORIES[sid].get('colour', _YELL)}{SIDE_STORIES[sid]['title']}{_R}")
    total = len(SIDE_STORIES)
    out.append("")
    out.append(f"{_DIM}Side stories found: {len(mgr.side_stories)}/{total}   completed: {len(done)}{_R}")
    return out


def _quest_lines(player):
    out = []
    if player is None:
        return [f"{_DIM}—{_R}"]
    aq = getattr(player, "active_quests", []) or []
    if aq:
        out.append(f"{_CYAN}{_B}GUILD QUESTS{_R}")
        for q in aq:
            prog = q.get("progress", 0); req = q.get("required", 1)
            done = f"  {_GREEN}✓ turn in at a Quest Board{_R}" if prog >= req else ""
            out.append(f"  {_WHITE}{q.get('title', '?')}{_R}  {_GOLD}{min(prog, req)}/{req}{_R}{done}")
    eq = getattr(player, "evolution_quest", None)
    if eq and not eq.get("done"):
        prog = eq.get("progress", 0); req = eq.get("required", 1)
        done = f"  {_GREEN}✓ turn in at a Quest Board{_R}" if prog >= req else ""
        out.append("")
        out.append(f"{_ORAN}{_B}CLASS QUEST:{_R} {_WHITE}{eq.get('title', '')}{_R}  {_GOLD}{min(prog, req)}/{req}{_R}{done}")
        out.append(f"  {_DIM}{eq.get('desc', '')}{_R}")
    lq = getattr(player, "_legendary_quest", None)
    if lq:
        out.append("")
        out.append(f"{_GOLD}{_B}LEGENDARY QUEST:{_R} {_WHITE}{lq.get('title', '')}{_R}")
        for st in lq.get("steps", []):
            out.append(f"  {_DIM}{st.get('label', '')}:{_R} {_GOLD}{st.get('progress', 0)}/{st.get('required', 1)}{_R}")
    if not out:
        out.append(f"{_DIM}No guild, class or legendary quests. Visit a town's Quest Board.{_R}")
    return out


def _discovery_lines(player):
    out = []
    try:
        import game_structures
        return game_structures.journal_lines(player)
    except Exception:
        pass
    out.append(f"{_DIM}Explore the world to make discoveries.{_R}")
    return out


def _journal(mgr, player):
    tab = "1"
    page = 0
    while True:
        if player is not None:
            try:
                done = mgr.check_flags(player)
                if done or _QUEUE:
                    flush_story_popups(player)
            except Exception as e:
                _log(f"journal check failed: {e!r}")
        tabs = [("1", "Main story"), ("2", "Side stories"), ("3", "Quests"), ("4", "Discoveries")]
        if tab == "1":
            body = _main_lines(mgr, player)
        elif tab == "2":
            body = _side_lines(mgr, player)
        elif tab == "3":
            body = _quest_lines(player)
        else:
            body = _discovery_lines(player)
        per = max(10, H() - 9)
        pages = max(1, (len(body) + per - 1) // per)
        page = min(page, pages - 1)
        clr()
        print(C(f"\n{_GOLD}{_B}════  STORY JOURNAL  ════{_R}"))
        bar = "  ".join((f"{_GOLD}{_B}[{k}] {n}{_R}" if k == tab else f"{_DIM}[{k}] {n}{_R}") for k, n in tabs)
        print(C(bar))
        print(C(f"{_DIM}{'─' * 76}{_R}"))
        for line in body[page * per:(page + 1) * per]:
            print(C(line))
        keys = []
        if pages > 1:
            keys.append(f"{_GOLD}[N]{_R}{_DIM}ext/{_R}{_GOLD}[P]{_R}{_DIM}rev page {page + 1}/{pages}{_R}")
        choices = mgr.pending_choices(player)
        if choices:
            keys.append(f"{_GOLD}[D]{_R}{_DIM} Decide{_R}")
        story = mgr.get_main_story()
        if story and mgr.main_complete:
            keys.append(f"{_GOLD}[E]{_R}{_DIM} Epilogue{_R}")
        keys.append(f"{_GOLD}[0]{_R}{_DIM} Close{_R}")
        print(C(f"{_DIM}{'─' * 76}{_R}"))
        try:
            ch = input(C("  ".join(keys) + f"  {_GOLD}>{_R} ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if ch in ("1", "2", "3", "4"):
            tab, page = ch, 0
        elif ch == "n":
            page = (page + 1) % pages
        elif ch == "p":
            page = (page - 1) % pages
        elif ch == "d" and choices and player is not None:
            kind, sid, step = choices[0]
            choose_option(mgr, player, kind, sid, step)
            flush_story_popups(player)
        elif ch == "e" and story and mgr.main_complete:
            _show_epilogue({"mgr": mgr, "sid": mgr.main_story_id}, player)
        elif ch in ("0", "q", "", "j"):
            return


# ═════════════════════════════════════════════════════════════════
# Story selection (character creation)
# ═════════════════════════════════════════════════════════════════

def _tagline(s):
    if s.get("tagline"):
        return s["tagline"]
    intro = s.get("intro", "")
    first = intro.split(". ")[0].strip()
    return (first[:70] + "…") if len(first) > 71 else first


def path_length(story):
    """Chapters on one play-through: alternative steps sharing a "branch"
    name count once."""
    groups = set()
    n = 0
    for st in story.get("steps", []):
        b = st.get("branch")
        if b:
            if b in groups:
                continue
            groups.add(b)
        n += 1
    return n


def story_meta(s):
    """(chapter count, act count, hours estimate text) for the picker."""
    n = path_length(s)
    acts = sum(1 for st in s.get("steps", []) if st.get("act"))
    hours = s.get("length") or f"~{max(1, round(n * 0.45))}-{max(2, round(n * 0.6))} h"
    return n, acts, hours


def story_selection_screen(name=None, allow_back=False, header=None):
    """Pick a main story. Returns the story id, or None if the player backs out
    (only when allow_back=True). Works with any number of stories."""
    ensure_external_stories()
    while True:
        stories = list(MAIN_STORIES.items())
        clr()
        if header:
            header()
        title = f"{name}  ──  " if name else ""
        print(C(f"\n{_CYAN}{_B}══════  {title}CHOOSE YOUR MAIN STORY  ══════{_R}\n"))
        print(C(f"{_DIM}Side stories are discovered as you explore. Pick a number to read more.{_R}\n"))
        for i, (sid, s) in enumerate(stories, 1):
            n, acts, hours = story_meta(s)
            col = s.get("colour", _GOLD)
            diff = s.get("difficulty", "")
            meta = f"{n} chapters" + (f" · {acts} acts" if acts else "") + f" · {hours}" + (f" · {diff}" if diff else "")
            print(C(f"{_GOLD}{_B}[{i}]{_R} {col}{_B}{s['title']}{_R}  {_DIM}{meta}{_R}"))
            for line in _wrap(_tagline(s), 72)[:2]:
                print(C(f"     {_GREY}{line}{_R}"))
            print()
        if allow_back:
            print(C(f"{_GOLD}[0]{_R} {_DIM}Back{_R}"))
        try:
            ch = input(C(f"\n{_GOLD}>{_R} Story (1-{len(stories)}): ")).strip()
        except (EOFError, KeyboardInterrupt):
            if allow_back:
                return None
            raise
        if ch == "0" and allow_back:
            return None
        if ch.isdigit() and 1 <= int(ch) <= len(stories):
            sid, s = stories[int(ch) - 1]
            if _story_details(sid, s, header):
                return sid


def _story_details(sid, s, header=None):
    """Detail page. Returns True if the player confirms the story."""
    clr()
    if header and H() >= 44:
        header()
    col = s.get("colour", _GOLD)
    n, acts, hours = story_meta(s)
    print(C(f"\n{col}{_B}══  {s['title']}  ══{_R}\n"))
    for line in _wrap(s.get("intro", ""), 76):
        print(C(f"{_WHITE}{line}{_R}"))
    print()
    act_names = [st["act"] for st in s.get("steps", []) if st.get("act")]
    if act_names:
        print(C(f"{_GOLD}Structure{_R}"))
        for a in act_names:
            print(C(f"  {_DIM}·{_R} {_GREY}{a}{_R}"))
        print()
    print(C(f"{_DIM}{n} chapters · estimated {hours}{_R}"))
    if s.get("difficulty"):
        print(C(f"{_DIM}Difficulty: {s['difficulty']}{_R}"))
    print(C(f"\n{_GOLD}[Y]{_R} {_WHITE}Begin this story{_R}     {_GOLD}[0]{_R} {_DIM}Back to the list{_R}"))
    try:
        ch = input(C(f"\n{_GOLD}>{_R} ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ch in ("y", "yes", "1", "")
