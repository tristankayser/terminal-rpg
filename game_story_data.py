"""game_story_data.py — story content (main stories, side stories, epilogues).

Pure data; the engine lives in game_stories.py (see its docstring for the step
schema).  Keep existing step ids stable: saves remember progress by step id.
"""

def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"

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


EPILOGUES = []
