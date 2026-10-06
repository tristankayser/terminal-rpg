"""
storylines.py — Main storylines and side quests for Terminal-RPG.

Main stories (pick at character creation):
  1. The Dragon's Curse      — hunt and slay the ancient dragon terrorising the world
  2. The Shadow Conspiracy   — infiltrate and destroy a cult spreading through every city
  3. The Lost Kingdom        — find fragments of an ancient map leading to legendary treasure

Side stories (discovered through exploration):
  - The Missing Merchant     — found in a tavern
  - The Haunted Mine         — found at a mine entrance
  - The Ice Witch's Trial    — found in Frostheim ruins
  - Bandit Lord Rising       — found after killing 10 bandits
  - The Sea Serpent Legend   — found at a port
"""

import random, os
from game_term import C, P, div, clr, W, H, hpbar, mpbar, box_top, box_mid, box_bot, get_size
from game_lang import T, set_language, LANG, LANGUAGE_NAMES

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0); _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60); _CYAN=_fg(80,220,220)
_YELL=_fg(240,200,60); _PURP=_fg(180,80,220); _ORAN=_fg(220,140,40)

# ── Story step types ─────────────────────────────────────────────
# "kill"        — kill N of target enemy
# "visit"       — visit a named location
# "talk"        — talk to a specific NPC keyword at any town
# "item"        — collect an item (flagged in inventory by name)
# "dungeon"     — clear a specific dungeon
# "dragon"      — slay the dragon (special)

MAIN_STORIES = {
    "dragon_curse": {
        "title":   "The Dragon's Curse",
        "colour":  _fg(220,80,60),
        "icon":    "🐉",
        "intro": (
            "An ancient dragon, Vaeltharion the Ashen, has awoken from centuries "
            "of slumber beneath the Iron Peaks. Cities burn. Villages flee. "
            "The gods themselves tremble. You are the last hope."
        ),
        "steps": [
            {
                "id": "dc_1",
                "title": "Hear the Rumours",
                "desc": "Speak to townsfolk in any city to learn of the dragon sightings.",
                "type": "talk", "target": "dragon_rumour", "required": 1,
                "reward_gold": 0, "reward_exp": 50,
                "completion_text": "The innkeeper whispers: 'They say it nests somewhere in the highest peaks... deep in a cave marked by scorched stone.'",
            },
            {
                "id": "dc_2",
                "title": "Slay the Dragon's Scouts",
                "desc": "Defeat 8 Cultists who serve Vaeltharion.",
                "type": "kill", "target": "Cultist", "required": 8,
                "reward_gold": 300, "reward_exp": 400,
                "completion_text": "Among the cultists' possessions you find a crude map fragment pointing toward the Iron Peaks.",
            },
            {
                "id": "dc_3",
                "title": "Find the Dragon Cave",
                "desc": "Explore the Ironspire peaks and find the Dragon Cave entrance [V].",
                "type": "visit", "target": "Vaeltharion's Lair", "required": 1,
                "reward_gold": 200, "reward_exp": 300,
                "completion_text": "The cave reeks of sulphur. Claw marks the size of a man scar the stone. You steel yourself.",
            },
            {
                "id": "dc_4",
                "title": "Slay Vaeltharion",
                "desc": "Enter the Dragon Cave and defeat Vaeltharion the Ashen.",
                "type": "dragon", "target": "Vaeltharion", "required": 1,
                "reward_gold": 5000, "reward_exp": 10000,
                "completion_text": "The dragon falls. The curse lifts. Songs will be sung of this day for a thousand years.",
            },
        ],
    },

    "shadow_conspiracy": {
        "title":   "The Shadow Conspiracy",
        "colour":  _fg(140,60,200),
        "icon":    "🕵",
        "intro": (
            "A secret cult called the Veil of Night has infiltrated every major "
            "city across the known world. They poison leaders, bribe guards, and "
            "corrupt the innocent. You have been chosen to stop them."
        ),
        "steps": [
            {
                "id": "sc_1",
                "title": "First Contact",
                "desc": "Find a Veil spy — defeat 5 Shadow Beasts to draw them out.",
                "type": "kill", "target": "Shadow Beast", "required": 5,
                "reward_gold": 150, "reward_exp": 200,
                "completion_text": "A dying shadow beast drops a coded letter. The cult meets in the dungeon below Ironmoor.",
            },
            {
                "id": "sc_2",
                "title": "Raid the Deep Mines",
                "desc": "Clear the Deep Mines dungeon — the cult's local headquarters.",
                "type": "dungeon", "target": "Deep Mines", "required": 1,
                "reward_gold": 400, "reward_exp": 500,
                "completion_text": "You find encrypted ledgers. The cult's leader — the Faceless One — commands from the Ash Sands.",
            },
            {
                "id": "sc_3",
                "title": "Trail Across the Sea",
                "desc": "Sail to Ash Sands continent and visit Sandreach.",
                "type": "visit", "target": "Sandreach", "required": 1,
                "reward_gold": 200, "reward_exp": 250,
                "completion_text": "A contact in Sandreach reveals: the Faceless One hides in the Sand Tomb.",
            },
            {
                "id": "sc_4",
                "title": "Unmask the Faceless One",
                "desc": "Clear the Sand Tomb dungeon and destroy the cult's leader.",
                "type": "dungeon", "target": "Sand Tomb", "required": 1,
                "reward_gold": 3000, "reward_exp": 6000,
                "completion_text": "The mask falls. The Veil of Night is shattered. The world breathes free.",
            },
        ],
    },

    "lost_kingdom": {
        "title":   "The Lost Kingdom",
        "colour":  _fg(200,170,60),
        "icon":    "🗺",
        "intro": (
            "Ancient texts speak of Valdremoor — a kingdom of unimaginable wealth "
            "that vanished overnight five hundred years ago. Its treasure still lies "
            "hidden, guarded by ancient seals. Four map fragments will reveal its location."
        ),
        "steps": [
            {
                "id": "lk_1",
                "title": "Fragment of the North",
                "desc": "Clear the Ice Cavern dungeon on the Frostheim continent.",
                "type": "dungeon", "target": "Ice Cavern", "required": 1,
                "reward_gold": 300, "reward_exp": 350,
                "completion_text": "In the dungeon's final chamber, frozen in ice, you find the first map fragment.",
            },
            {
                "id": "lk_2",
                "title": "Fragment of the West",
                "desc": "Clear the Wolf Den dungeon on the Aeloria continent.",
                "type": "dungeon", "target": "Wolf Den", "required": 1,
                "reward_gold": 300, "reward_exp": 350,
                "completion_text": "Carved into the wolf pack's lair wall — the second fragment.",
            },
            {
                "id": "lk_3",
                "title": "Fragment of the East",
                "desc": "Clear the Sand Tomb dungeon on the Ash Sands continent.",
                "type": "dungeon", "target": "Sand Tomb", "required": 1,
                "reward_gold": 300, "reward_exp": 350,
                "completion_text": "Buried beneath the sand tomb's altar — the third fragment.",
            },
            {
                "id": "lk_4",
                "title": "The Vault of Valdremoor",
                "desc": "All four fragments collected. The vault lies beneath the Sea Cavern.",
                "type": "dungeon", "target": "Sea Cavern", "required": 1,
                "reward_gold": 8000, "reward_exp": 12000,
                "completion_text": "The vault opens. Mountains of gold. Legendary weapons. The Lost Kingdom yields its secrets to you alone.",
            },
        ],
    },
}

SIDE_STORIES = {
    "missing_merchant": {
        "title":   "The Missing Merchant",
        "colour":  _fg(180,160,80),
        "trigger": "town_rumour",
        "trigger_towns": ["Greenveil","Seaview","Ironmoor"],
        "intro":   "A merchant named Pol vanished on the road between Greenveil and Ironmoor. His family offers a reward.",
        "steps": [
            {"id":"mm_1","title":"Search the Road","desc":"Defeat 3 Bandits on the Aeloria plains.",
             "type":"kill","target":"Bandit","required":3,
             "reward_gold":200,"reward_exp":150,
             "completion_text":"A survivor bandit reveals: Pol was taken to Wolf Den."},
            {"id":"mm_2","title":"Rescue Pol","desc":"Clear Wolf Den dungeon.",
             "type":"dungeon","target":"Wolf Den","required":1,
             "reward_gold":500,"reward_exp":400,
             "completion_text":"You find Pol alive. He rewards you handsomely and gives you a trade contact."},
        ],
    },
    "haunted_mine": {
        "title":   "Haunted Mine",
        "colour":  _fg(120,120,180),
        "trigger": "mine_enter",
        "trigger_towns": [],
        "intro":   "Miners refuse to work. Strange lights and screaming at night. Something dwells in the deep.",
        "steps": [
            {"id":"hm_1","title":"Investigate","desc":"Defeat 6 Skeletons in any mine.",
             "type":"kill","target":"Skeleton","required":6,
             "reward_gold":250,"reward_exp":300,
             "completion_text":"The haunting came from a mass grave. You put the spirits to rest."},
        ],
    },
    "bandit_lord": {
        "title":   "Bandit Lord Rising",
        "colour":  _fg(200,100,60),
        "trigger": "kill_bandits",
        "trigger_count": 10,
        "trigger_towns": [],
        "intro":   "Word reaches you: a notorious Bandit Lord is uniting scattered gangs across the continent.",
        "steps": [
            {"id":"bl_1","title":"Thin the Ranks","desc":"Defeat 15 more Bandits.",
             "type":"kill","target":"Bandit","required":15,
             "reward_gold":400,"reward_exp":350,
             "completion_text":"The Bandit Lord's lieutenant drops a location: their fortress is a dungeon south of Ironmoor."},
            {"id":"bl_2","title":"Destroy the Fortress","desc":"Clear the Deep Mines (Bandit Lord's base).",
             "type":"dungeon","target":"Deep Mines","required":1,
             "reward_gold":800,"reward_exp":700,
             "completion_text":"The Bandit Lord is no more. The roads are safe again."},
        ],
    },
    "sea_serpent": {
        "title":   "The Sea Serpent Legend",
        "colour":  _fg(60,180,200),
        "trigger": "port_visit",
        "trigger_towns": ["Tidereach","South Port","Coral Bay","Cliff Port"],
        "intro":   "Sailors speak of a sea serpent that has swallowed three ships. A merchant offers enormous gold to anyone who can prove it dead.",
        "steps": [
            {"id":"ss_1","title":"Gather Evidence","desc":"Defeat 4 Sand Wyrms (sea creature equivalent).",
             "type":"kill","target":"Sand Wyrm","required":4,
             "reward_gold":300,"reward_exp":300,
             "completion_text":"The serpent — actually a colony of sea wyrms — is thinned. The seas are safer."},
        ],
    },
}


class StoryManager:
    """Tracks active storylines and step progress for the player."""

    def __init__(self):
        self.main_story_id   = None   # which main story is active
        self.main_step_idx   = 0      # current step index (0-based)
        self.main_progress   = 0      # progress within current step
        self.main_complete   = False

        self.side_stories    = {}     # {story_id: {"step_idx": N, "progress": N, "complete": False}}
        self.bandit_kill_count = 0    # tracks for bandit_lord trigger

    # ── Main story ───────────────────────────────────────────────

    def start_main(self, story_id):
        self.main_story_id = story_id
        self.main_step_idx = 0
        self.main_progress = 0
        self.main_complete = False

    def get_main_story(self):
        return MAIN_STORIES.get(self.main_story_id)

    def get_main_step(self):
        story = self.get_main_story()
        if not story or self.main_complete: return None
        steps = story["steps"]
        if self.main_step_idx >= len(steps): return None
        return steps[self.main_step_idx]

    def advance_main(self):
        story = self.get_main_story()
        if not story: return
        steps = story["steps"]
        if self.main_step_idx + 1 >= len(steps):
            self.main_complete = True
        else:
            self.main_step_idx += 1
            self.main_progress = 0

    # ── Side stories ─────────────────────────────────────────────

    def unlock_side(self, story_id):
        if story_id not in self.side_stories:
            self.side_stories[story_id] = {"step_idx":0,"progress":0,"complete":False}

    def get_side_step(self, story_id):
        if story_id not in self.side_stories: return None
        s = self.side_stories[story_id]
        if s["complete"]: return None
        story = SIDE_STORIES.get(story_id)
        if not story: return None
        steps = story["steps"]
        idx = s["step_idx"]
        if idx >= len(steps): return None
        return steps[idx]

    def advance_side(self, story_id):
        if story_id not in self.side_stories: return
        s = self.side_stories[story_id]
        story = SIDE_STORIES.get(story_id)
        if not story: return
        if s["step_idx"] + 1 >= len(story["steps"]):
            s["complete"] = True
        else:
            s["step_idx"] += 1
            s["progress"] = 0

    # ── Event hooks ──────────────────────────────────────────────

    def on_kill(self, enemy_name, player):
        """Call this after every kill. Returns list of (story_title, step_title) completed."""
        completed = []

        # Track bandits
        if enemy_name == "Bandit":
            self.bandit_kill_count += 1
            if self.bandit_kill_count >= 10:
                self.unlock_side("bandit_lord")

        # Main story step
        step = self.get_main_step()
        if step and step["type"] == "kill" and step["target"] == enemy_name:
            self.main_progress += 1
            if self.main_progress >= step["required"]:
                completed.append(("main", step))
                player.gold += step["reward_gold"]
                player.gain_exp(step["reward_exp"])
                self.advance_main()

        # Side story steps
        for sid, sdata in list(self.side_stories.items()):
            if sdata["complete"]: continue
            sstep = self.get_side_step(sid)
            if sstep and sstep["type"] == "kill" and sstep["target"] == enemy_name:
                sdata["progress"] += 1
                if sdata["progress"] >= sstep["required"]:
                    completed.append(("side", sstep))
                    player.gold += sstep["reward_gold"]
                    player.gain_exp(sstep["reward_exp"])
                    self.advance_side(sid)

        return completed

    def on_dungeon_clear(self, dungeon_name, player):
        completed = []
        step = self.get_main_step()
        if step and step["type"] in ("dungeon","dragon") and step["target"] == dungeon_name:
            self.main_progress = 1
            completed.append(("main", step))
            player.gold += step["reward_gold"]
            player.gain_exp(step["reward_exp"])
            self.advance_main()
        for sid, sdata in list(self.side_stories.items()):
            if sdata["complete"]: continue
            sstep = self.get_side_step(sid)
            if sstep and sstep["type"] == "dungeon" and sstep["target"] == dungeon_name:
                sdata["progress"] = 1
                completed.append(("side", sstep))
                player.gold += sstep["reward_gold"]
                player.gain_exp(sstep["reward_exp"])
                self.advance_side(sid)
        return completed

    def on_visit(self, location_name, player):
        completed = []
        step = self.get_main_step()
        if step and step["type"] == "visit" and step["target"] == location_name:
            self.main_progress = 1
            completed.append(("main", step))
            player.gold += step["reward_gold"]
            player.gain_exp(step["reward_exp"])
            self.advance_main()
        return completed

    def on_talk(self, keyword, player):
        completed = []
        step = self.get_main_step()
        if step and step["type"] == "talk" and step["target"] == keyword:
            self.main_progress = 1
            completed.append(("main", step))
            player.gold += step["reward_gold"]
            player.gain_exp(step["reward_exp"])
            self.advance_main()
        return completed

    def on_port_visit(self, port_name, player):
        for sid, story in SIDE_STORIES.items():
            if story.get("trigger") == "port_visit" and port_name in story.get("trigger_towns",[]):
                if sid not in self.side_stories:
                    self.unlock_side(sid)
                    return sid
        return None

    def on_town_visit(self, town_name, player):
        unlocked = []
        for sid, story in SIDE_STORIES.items():
            if story.get("trigger") == "town_rumour" and town_name in story.get("trigger_towns",[]):
                if sid not in self.side_stories:
                    self.unlock_side(sid)
                    unlocked.append(sid)
        return unlocked

    # ── Display ──────────────────────────────────────────────────

    def show_journal(self, player=None):
        clr()
        print(C(f"\n{_GOLD}{_B}════  STORY JOURNAL  ════{_R}\n"))

        # Main story
        story = self.get_main_story()
        if story:
            col = story["colour"]
            step = self.get_main_step()
            print(C(f"{col}{_B}MAIN: {story['title']}{_R}"))
            if self.main_complete:
                print(C(f"{_GREEN}  ★ COMPLETED!{_R}"))
            elif step:
                prog = self.main_progress
                req  = step["required"]
                bar  = f"{_GOLD}{'█'*prog}{_DIM}{'░'*(req-prog)}{_R}"
                print(C(f"{_WHITE}  ► {step['title']}{_R}"))
                print(C(f"  {_DIM}{step['desc']}{_R}"))
                print(C(f"  [{bar}] {_GOLD}{prog}/{req}{_R}"))
            print()

        # Side stories
        if self.side_stories:
            print(C(f"{_CYAN}{_B}SIDE STORIES:{_R}"))
            for sid, sdata in self.side_stories.items():
                story_def = SIDE_STORIES.get(sid)
                if not story_def: continue
                col = story_def["colour"]
                sstep = self.get_side_step(sid)
                complete_str = f"  {_GREEN}✓ Done{_R}" if sdata["complete"] else ""
                print(C(f"\n{col}{story_def['title']}{_R}{complete_str}"))
                if sstep and not sdata["complete"]:
                    prog = sdata["progress"]; req = sstep["required"]
                    bar  = f"{_YELL}{'█'*prog}{_DIM}{'░'*(req-prog)}{_R}"
                    print(C(f"{_WHITE}  ► {sstep['title']}{_R}"))
                    print(C(f"  {_DIM}{sstep['desc']}{_R}"))
                    print(C(f"  [{bar}] {_YELL}{prog}/{req}{_R}"))

        if not story and not self.side_stories:
            print(C(f"{_DIM}No active stories. Explore the world to discover them.{_R}"))

        # Guild / class / legendary quests in one place
        if player is not None:
            if player.active_quests:
                print(C(f"\n{_CYAN}{_B}GUILD QUESTS:{_R}"))
                for q in player.active_quests:
                    prog = q.get("progress", 0); req = q.get("required", 1)
                    done = f"  {_GREEN}✓ turn in at a Quest Board{_R}" if prog >= req else ""
                    print(C(f"  {_WHITE}{q['title']}{_R}  {_GOLD}{min(prog,req)}/{req}{_R}{done}"))
            eq = getattr(player, "evolution_quest", None)
            if eq and not eq.get("done"):
                prog = eq.get("progress", 0); req = eq.get("required", 1)
                done = f"  {_GREEN}✓ turn in at a Quest Board{_R}" if prog >= req else ""
                print(C(f"\n{_ORAN}{_B}CLASS QUEST:{_R} {_WHITE}{eq['title']}{_R}  {_GOLD}{min(prog,req)}/{req}{_R}{done}"))
                print(C(f"  {_DIM}{eq['desc']}{_R}"))
            lq = getattr(player, "_legendary_quest", None)
            if lq:
                print(C(f"\n{_GOLD}{_B}LEGENDARY QUEST:{_R} {_WHITE}{lq['title']}{_R}"))
                for st in lq.get("steps", []):
                    print(C(f"  {_DIM}{st['label']}:{_R} {_GOLD}{st['progress']}/{st['required']}{_R}"))

        input(C(f"\n{_DIM}(Press Enter){_R}"))

    # ── Serialise ────────────────────────────────────────────────

    def to_dict(self):
        return {
            "main_story_id":    self.main_story_id,
            "main_step_idx":    self.main_step_idx,
            "main_progress":    self.main_progress,
            "main_complete":    self.main_complete,
            "side_stories":     self.side_stories,
            "bandit_kill_count":self.bandit_kill_count,
        }

    @classmethod
    def from_dict(cls, d):
        sm = cls()
        sm.main_story_id    = d.get("main_story_id")
        sm.main_step_idx    = d.get("main_step_idx", 0)
        sm.main_progress    = d.get("main_progress", 0)
        sm.main_complete    = d.get("main_complete", False)
        sm.side_stories     = d.get("side_stories", {})
        sm.bandit_kill_count= d.get("bandit_kill_count", 0)
        return sm


def story_selection_screen():
    """Show story selection at character creation. Returns story_id."""
    clr()
    print(C(f"\n{_GOLD}{_B}════  CHOOSE YOUR MAIN STORY  ════{_R}\n"))
    print(C(f"{_DIM}Side stories will be discovered as you explore.{_R}\n"))

    stories = list(MAIN_STORIES.items())
    for i, (sid, s) in enumerate(stories, 1):
        col = s["colour"]
        print(C(f"{_GOLD}{_B}[{i}]{_R} {col}{_B}{s['title']}{_R}"))
        # Word-wrap intro at 60 chars
        words = s["intro"].split()
        line = "  "; lines = []
        for w in words:
            if len(line)+len(w)+1 > 62:
                lines.append(line); line = "  "+w+" "
            else:
                line += w+" "
        if line.strip(): lines.append(line)
        for l in lines: print(C(f"{_DIM}{l}{_R}"))
        print()

    while True:
        ch = input(C(f"{_GOLD}>{_R} Choose story (1-{len(stories)}): ")).strip()
        if ch.isdigit() and 1 <= int(ch) <= len(stories):
            return stories[int(ch)-1][0]
        print(C(f"{_RED}Enter a number 1–{len(stories)}.{_R}"))


def show_story_completion(story_type, step):
    """Show a dramatic story step completion message."""
    clr()
    if story_type == "main":
        print(C(f"\n{_GOLD}{_B}╔══════════════════════════════════════════╗"))
        print(C(f"║  ★  STORY STEP COMPLETE                  ║"))
        print(C(f"╚══════════════════════════════════════════╝{_R}\n"))
    else:
        print(C(f"\n{_YELL}{_B}╔══════════════════════════════════════════╗"))
        print(C(f"║  ✓  SIDE QUEST COMPLETE                  ║"))
        print(C(f"╚══════════════════════════════════════════╝{_R}\n"))

    print(C(f"{_WHITE}{_B}{step['title']}{_R}\n"))
    print(C(f"{_DIM}{step['completion_text']}{_R}\n"))
    if step["reward_gold"]:
        print(C(f"{_GOLD}+{step['reward_gold']} Gold{_R}   {_CYAN}+{step['reward_exp']} EXP{_R}"))
    input(C(f"\n{_DIM}(Press Enter){_R}"))
