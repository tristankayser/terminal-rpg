"""
game_recruits.py — companion data and spawn rules for Terminal-RPG.

Pure data plus a few deterministic helpers.  Nothing here imports another
game module at load time, so every module (game_party, game_towns,
game_capital ...) can import it freely.

  COMPANION_DEFS   id -> definition dict (42 companions, 5 rarities)
  PASSIVES         passive_id -> {name, desc}          (effects: game_party)
  TRAITS           trait_id   -> {name, desc, mods}
  RARITIES         rarity     -> {label, colour, cost_mult, growth}
  COMPANION_STYLES role       -> list of cosmetic colour styles
  tavern_recruits(town_name, day, player=None) -> [ids in that tavern today]
  hire_cost(cid, level, player=None)            -> gold
  is_starborn(seed, cid, day)                   -> 1-in-512 shiny roll

Spawn types ("spawn" field, a dict with at least "type"):
  tavern     regular at fixed town tavern(s)            ("towns": [...])
  rotation   rare traveller: appears in ONE tavern of its continents on
             roughly half of all days (deterministic per day)
  wander     met on the world map (wandering_recruit_event)
  prisoner   freed from a dungeon after a boss clear
  ruins      mysterious stranger in ruins
  defeated   a beaten enemy asks to join ("enemies": [...])
  special    placed by another module's scene (castles) via offer_recruit
  story      only through a story reward (offer_recruit from the story)
"""

import zlib

DEF_VERSION = 2
DAY_TURNS = 200          # world-map turns per in-game day (matches town day/night)

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
RARITIES = {
    "common":    dict(label="Common",    colour=(185, 185, 185), cost_mult=1.0, growth=1.00, stars=1),
    "uncommon":  dict(label="Uncommon",  colour=(90, 210, 110),  cost_mult=1.3, growth=1.06, stars=2),
    "rare":      dict(label="Rare",      colour=(80, 150, 240),  cost_mult=1.8, growth=1.12, stars=3),
    "epic":      dict(label="Epic",      colour=(190, 100, 240), cost_mult=2.6, growth=1.20, stars=4),
    "legendary": dict(label="Legendary", colour=(255, 175, 40),  cost_mult=4.0, growth=1.30, stars=5),
}
STARBORN_ODDS = 512
STARBORN_ACCENT = (255, 215, 90)

ROLES = ("warrior", "rogue", "mage", "healer")
ROLE_COLOUR = {"warrior": (225, 80, 70), "rogue": (235, 200, 70),
               "mage": (180, 100, 235), "healer": (90, 205, 110)}
ROLE_SPRITE = {"warrior": "Swordsman", "rogue": "Rogue", "mage": "Mage", "healer": "Healer"}
# Which player classes' gear a role may wear (Equipment.allowed_classes)
ROLE_CLASSES = {
    "warrior": ["Swordsman", "Tank", "Blade Master", "War Titan"],
    "rogue":   ["Rogue", "Shadow Assassin"],
    "mage":    ["Mage", "Archmage"],
    "healer":  ["Healer", "Arch Priest"],
}
# Companion gear slots and which Equipment slots fit in them
GEAR_SLOTS = {"weapon": ("weapon",), "armor": ("armor", "helmet", "shield"),
              "trinket": ("ring", "amulet", "cloak")}

# Base stats at level 1 and growth per level, per role.  Kept well under the
# player's own curve (player ATK grows 2-4/level plus gear) so companions help
# without out-fighting the hero.
ROLE_STATS = {
    "warrior": dict(base=dict(hp=70, atk=8, df=4, mp=10),  grow=dict(hp=12.0, atk=1.20, df=0.80, mp=1.0)),
    "rogue":   dict(base=dict(hp=55, atk=9, df=2, mp=20),  grow=dict(hp=9.0,  atk=1.40, df=0.50, mp=1.5)),
    "mage":    dict(base=dict(hp=45, atk=10, df=1, mp=50), grow=dict(hp=7.0,  atk=1.50, df=0.40, mp=3.0)),
    "healer":  dict(base=dict(hp=50, atk=5, df=2, mp=60),  grow=dict(hp=8.0,  atk=0.80, df=0.60, mp=3.5)),
}

# Regular skill per role (used every third round when MP allows)
ROLE_SKILL = {
    "warrior": dict(name="Cleave",        effect="strike", mult=1.5, mp=6),
    "rogue":   dict(name="Backstab",      effect="strike", mult=1.7, mp=6),
    "mage":    dict(name="Arcane Bolt",   effect="strike", mult=1.8, mp=10),
    "healer":  dict(name="Mending Wave",  effect="heal_all", mult=0.6, mp=12),
}

# Signature skill effects (unlocked at Loyal affinity)
SIGNATURE_EFFECTS = {
    "smite":     "a crushing blow (x2.2 damage)",
    "volley":    "three rapid hits (x0.8 each)",
    "stun":      "a heavy strike (x1.5) that stuns",
    "inferno":   "flames (x1.8) that leave the foe burning",
    "venom":     "a poisoned strike (x1.4) that leaves the foe poisoned",
    "sanctuary": "heals everyone (x1.3 heal power)",
    "drain":     "a draining strike (x1.6) that heals the caster",
    "rally":     "a war cry: everyone regenerates for 3 rounds",
}

# ── Passives (effects live in game_party.PASSIVE_FX) ─────────────

PASSIVES = {
    "bulwark":         dict(name="Bulwark",          desc="+3 DEF to you while standing; draws enemy attention."),
    "keen_eye":        dict(name="Keen Eye",         desc="All companions +10% crit; +3 stealth to you."),
    "field_medicine":  dict(name="Field Medicine",   desc="Heals earlier (below 70% HP) and heals cost 2 MP less."),
    "sand_step":       dict(name="Sand Step",        desc="All companions +8% dodge; +2 stealth to you."),
    "iron_grip":       dict(name="Iron Grip",        desc="+15 max HP to every companion."),
    "tailwind":        dict(name="Tailwind",         desc="+4 stealth to you (easier escapes); companions +5% dodge."),
    "frost_aura":      dict(name="Frost Aura",       desc="Chills the foe at the start of battle: enemy ATK -8%."),
    "permafrost":      dict(name="Permafrost",       desc="10% chance to block a hit entirely; +2 DEF to you."),
    "icebloom_mend":   dict(name="Icebloom Mend",    desc="After each victory, heals you and all companions 15 HP (+1/level)."),
    "mirage":          dict(name="Mirage",           desc="+15% dodge for herself."),
    "sandstorm":       dict(name="Sandstorm",        desc="Enemy crit chance -10 and ATK -5% at battle start."),
    "oasis_blessing":  dict(name="Oasis Blessing",   desc="After each victory, restores 10 MP to you and all companions."),
    "sea_legs":        dict(name="Sea Legs",         desc="Immune to Poison and Burn; +2 DEF to you."),
    "siren_song":      dict(name="Siren Song",       desc="Distracts the foe at battle start: enemy ATK -5 (min -10%)."),
    "tidal_mend":      dict(name="Tidal Mend",       desc="Heals also restore 20% of the target's missing HP."),
    "wanderers_edge":  dict(name="Wanderer's Edge",  desc="+15% crit chance for himself."),
    "void_step":       dict(name="Void Step",        desc="First attack of every battle deals +50% damage."),
    "arcane_overflow": dict(name="Arcane Overflow",  desc="+10% damage while above half MP; +3 skill power to you."),
    "holy_aura":       dict(name="Holy Aura",        desc="Everyone in the party regenerates 3 HP (+1 per 10 levels) each round."),
    "storm_fists":     dict(name="Storm Fists",      desc="Critical hits strike twice."),
    "prayer":          dict(name="Wayside Prayer",   desc="Heals you 8 HP (+level/2) at the start of every battle."),
    "trapper":         dict(name="Trapper",          desc="20% chance after a victory to skin a Wolf Pelt or Feather."),
    "shield_wall":     dict(name="Shield Wall",      desc="+4 DEF to you while standing."),
    "frostbite":       dict(name="Frostbite",        desc="Attacks have a 12% chance to freeze (stun) the foe."),
    "lance_charge":    dict(name="Lance Charge",     desc="First attack of every battle deals double damage."),
    "pearl_diver":     dict(name="Pearl Diver",      desc="+10% gold from victories."),
    "tide_ward":       dict(name="Tide Ward",        desc="Her heals also cleanse Poison and Burn."),
    "brawler":         dict(name="Brawler",          desc="+25% damage while below half HP."),
    "scavenger":       dict(name="Scavenger",        desc="25% chance after a victory to pocket extra gold."),
    "gelatinous":      dict(name="Gelatinous",       desc="Takes 15% less damage."),
    "cheap_shot":      dict(name="Cheap Shot",       desc="Attacks have a 15% chance to stun the foe."),
    "forbidden_lore":  dict(name="Forbidden Lore",   desc="Attacks have a 25% chance to set the foe ablaze."),
    "riposte":         dict(name="Riposte",          desc="Counter-attacks whenever she dodges."),
    "starlight":       dict(name="Starlight",        desc="All companions +5% crit; +4 skill power to you."),
    "pathfinder":      dict(name="Pathfinder",       desc="+6 stealth to you (ambush-proof, easier escapes)."),
    "hex_ward":        dict(name="Hex Ward",         desc="Curses the foe at battle start: enemy ATK -6%."),
    "royal_guard":     dict(name="Royal Guard",      desc="+5 DEF to you; draws enemy attention."),
    "royal_ward":      dict(name="Royal Ward",       desc="+3 DEF and +6 skill power to you; party regenerates 2 HP per round."),
    "hellfire_blade":  dict(name="Hellfire Blade",   desc="Attacks have a 30% chance to set the foe ablaze."),
    "desert_eyes":     dict(name="Desert Eyes",      desc="+5 stealth to you and +10% gold from victories."),
    "old_guard":       dict(name="Old Guard",        desc="Blocks the first hit of every battle; +2 DEF to you."),
    "dragonheart":     dict(name="Dragonheart",      desc="+20% damage against bosses; immune to Burn."),
}

# ── Traits (Battle Brothers style backgrounds/quirks) ────────────
# mods keys: hp_pct atk_pct def crit dodge xp_pct heal_pct aff_mult
#            immune (list of status names) cost_pct

TRAITS = {
    "brave":      dict(name="Brave",      desc="+5% ATK. Hates running away.",        mods=dict(atk_pct=5)),
    "tough":      dict(name="Tough",      desc="+10% max HP.",                        mods=dict(hp_pct=10)),
    "quick":      dict(name="Quick",      desc="+5% dodge.",                          mods=dict(dodge=5)),
    "lucky":      dict(name="Lucky",      desc="+5% crit.",                           mods=dict(crit=5)),
    "bookworm":   dict(name="Bookworm",   desc="+15% XP.",                            mods=dict(xp_pct=15)),
    "greedy":     dict(name="Greedy",     desc="Hire cost +15%. Loves gold gifts.",   mods=dict(cost_pct=15)),
    "drunkard":   dict(name="Drunkard",   desc="+10% max HP, -3% dodge.",             mods=dict(hp_pct=10, dodge=-3)),
    "iron_jaw":   dict(name="Iron Jaw",   desc="Cannot be stunned.",                  mods=dict(immune=["Stun"])),
    "hothead":    dict(name="Hothead",    desc="+8% ATK, -2 DEF.",                    mods=dict(atk_pct=8, df=-2)),
    "stout":      dict(name="Stout",      desc="+2 DEF.",                             mods=dict(df=2)),
    "gentle":     dict(name="Gentle",     desc="+10% healing.",                       mods=dict(heal_pct=10)),
    "keen_eyed":  dict(name="Keen-Eyed",  desc="+3% crit, +2% dodge.",                mods=dict(crit=3, dodge=2)),
    "devoted":    dict(name="Devoted",    desc="Affinity grows 50% faster.",          mods=dict(aff_mult=50)),
    "scarred":    dict(name="Scarred",    desc="+3 DEF, but slow to trust (-25% affinity gains).",
                       mods=dict(df=3, aff_mult=-25)),
    "studious":   dict(name="Studious",   desc="+10% XP, +5% heal.",                  mods=dict(xp_pct=10, heal_pct=5)),
    "starborn":   dict(name="Starborn",   desc="Touched by a falling star: +10% to every stat.",
                       mods=dict(hp_pct=10, atk_pct=10, def_pct=10, mp_pct=10, crit=3)),
}
# Traits that a Starborn may roll as their bonus trait
BONUS_TRAIT_POOL = ["brave", "tough", "quick", "lucky", "bookworm", "stout",
                    "keen_eyed", "devoted", "studious", "iron_jaw"]

# Affinity topics used by gifts / talk choices
TOPICS = ("kindness", "humour", "honesty", "gold", "battle", "boss", "stealth",
          "comfort", "faith", "knowledge", "demons")


def _c(cid, name, title, role, rarity, sprite, accent, spawn, *, continent="ANY",
       bio="", passive="", traits=(), likes=(), dislikes=(), gifts=(),
       recruit=None, cost=100, mod=None, signature=None, skill_name=None,
       alt=None, hire=(), idle=(), loyal=(), leave=None, legacy_passive=""):
    return dict(
        id=cid, name=name, title=title, role=role, rarity=rarity,
        sprite=sprite, accent=tuple(accent), continent=continent, spawn=spawn,
        bio=bio, passive_id=passive,
        passive=(f"{PASSIVES[passive]['name']}: {PASSIVES[passive]['desc']}"
                 if passive in PASSIVES else legacy_passive),
        traits=list(traits), likes=list(likes), dislikes=list(dislikes),
        gifts=list(gifts), recruit=dict(recruit or {}), cost=cost,
        mod=dict(mod or {}),
        signature=dict(signature or {"name": "Heroic Strike", "effect": "smite"}),
        skill_name=skill_name,
        alt=dict(alt or {"label": "Veteran's Garb", "accent": accent}),
        dialogue=dict(hire=list(hire), idle=list(idle), loyal=list(loyal),
                      leave=[leave] if leave else []),
        # v1 compatibility fields (other modules used to read these)
        town=(spawn.get("towns") or ["Random"])[0] if spawn.get("type") == "tavern" else "Random",
        hire_cost=cost,
    )


_DEFS = [
    # ── AELORIA (A) ───────────────────────────────────────────────
    _c("aldric", "Aldric", "Knight of Greenveil", "warrior", "common", "Swordsman", (90, 140, 230),
       dict(type="tavern", towns=["Greenveil"]), continent="A",
       bio="A hedge knight who guards Greenveil's roads for bread and honour.",
       passive="bulwark", traits=["brave", "stout"], likes=["battle", "honesty", "boss"],
       dislikes=["demons", "gold"], gifts=["Iron Shield", "type:equipment"],
       recruit=dict(gold=True), cost=80, mod=dict(hp=10, df=2),
       signature=dict(name="Oath of Greenveil", effect="stun"),
       alt=dict(label="Greenveil Tabard", accent=(60, 170, 90)),
       hire=["I swore to protect the innocent. You count, I suppose."],
       idle=["My sword arm is yours. Let's move.", "Greenveil needs heroes. Glad I found one.",
             "Watch your flanks. I'll take the front.", "Victory or death. I prefer victory."],
       loyal=["I'd ride into a dragon's mouth for you. Please don't make me."],
       leave="Honour has limits. I'm going home to Greenveil."),
    _c("lyra", "Lyra", "Forest Scout", "rogue", "common", "Rogue", (70, 160, 90),
       dict(type="tavern", towns=["Oakwatch"]), continent="A",
       bio="Grew up in the Oakwatch canopy; reads tracks like other people read books.",
       passive="keen_eye", traits=["keen_eyed", "quick"], likes=["stealth", "humour"],
       dislikes=["comfort"], gifts=["Feather", "Wolf Pelt", "Rogue Hood"],
       recruit=dict(gold=True), cost=90, mod=dict(atk=1),
       signature=dict(name="Arrow Storm", effect="volley"),
       alt=dict(label="Autumn Cloak", accent=(200, 110, 50)),
       hire=["I know every path in this forest. Follow me quietly."],
       idle=["Stealth is the only armour you truly need.", "Did you hear that? Something's following us.",
             "I'll scout ahead. Don't move until I whistle.", "My arrows find their mark even in the dark."],
       loyal=["You walk quieter these days. I'm taking the credit."],
       leave="I'm going back to the trees. They never let me down."),
    _c("mira", "Mira", "Herbalist Healer", "healer", "common", "Healer", (120, 200, 120),
       dict(type="tavern", towns=["Greenveil"]), continent="A",
       bio="Runs a herb stall in Greenveil and patches up every fool who stumbles in.",
       passive="field_medicine", traits=["gentle"], likes=["kindness", "comfort"],
       dislikes=["demons", "gold"], gifts=["type:heal", "Feather"],
       recruit=dict(gold=True), cost=100, mod=dict(mp=10),
       signature=dict(name="Verdant Bloom", effect="sanctuary"),
       alt=dict(label="Spring Robes", accent=(240, 170, 200)),
       hire=["I've patched up worse. Hold still."],
       idle=["My herbs can cure most things. Almost.", "You look terrible. Drink this.",
             "Healing is an art. And I am very good at my craft.", "Stay close. I can't heal what I can't see."],
       loyal=["I keep a vial with your name on it. Literally. I labelled it."],
       leave="I can't keep mending someone who won't stop bleeding for the wrong reasons."),
    _c("tomas", "Brother Tomas", "Wayside Friar", "healer", "common", "Healer", (200, 170, 120),
       dict(type="tavern", towns=["Mossford"]), continent="A",
       bio="A cheerful friar who blesses travellers at the Mossford ford for a copper.",
       passive="prayer", traits=["devoted", "gentle"], likes=["faith", "kindness", "comfort"],
       dislikes=["demons", "gold"], gifts=["Holy Water", "Sacred Tome", "type:heal"],
       recruit=dict(gold=True), cost=70,
       signature=dict(name="Benediction", effect="sanctuary"),
       alt=dict(label="Pilgrim's Habit", accent=(150, 110, 70)),
       hire=["Bless you! And bless your coin purse, if it's feeling generous."],
       idle=["Every road is a pilgrimage if you walk it long enough.", "I pray for you. Twice on bad days.",
             "Mind the ford. The ford does not mind you."],
       loyal=["You're the best sermon I never had to preach."],
       leave="My conscience asks me to walk a different road. Go with grace."),
    _c("fen", "Fennick", "Mossford Poacher", "rogue", "common", "Rogue", (140, 110, 70),
       dict(type="tavern", towns=["Mossford"]), continent="A",
       bio="Poaches the lord's deer and sells the lord the pelts. Charming about it.",
       passive="trapper", traits=["lucky"], likes=["humour", "stealth", "gold"],
       dislikes=["honesty"], gifts=["Wolf Pelt", "type:material"],
       recruit=dict(item=["Wolf Pelt", 2]), cost=0,
       signature=dict(name="Snare and Stab", effect="stun"),
       alt=dict(label="Lord's Stolen Coat", accent=(170, 40, 50)),
       hire=["Two pelts and I'm yours. Don't ask where the last two went."],
       idle=["Rabbits are just tiny, delicious bandits.", "If anyone asks, I was never here.",
             "Snares don't care how big you are."],
       loyal=["I'd never poach from you. Probably."],
       leave="I'm off before the lord's bailiff and your temper catch me."),
    _c("salt_meg", "Salty Meg", "Harbour Brawler", "warrior", "common", "Tank", (70, 130, 170),
       dict(type="tavern", towns=["Tidereach", "Greenport"]), continent="A",
       bio="Won the Tidereach arm-wrestling crown nine years running. Lost it once, drunk.",
       passive="brawler", traits=["drunkard", "tough"], likes=["battle", "humour", "comfort"],
       dislikes=["knowledge"], gifts=["Hero's Brew", "Strength Draught"],
       recruit=dict(gold=True), cost=75,
       signature=dict(name="Anchor Drop", effect="stun"),
       alt=dict(label="Captain's Coat", accent=(180, 40, 40)),
       hire=["Buy me a pint and point me at something rude."],
       idle=["Seen bigger waves in a bathtub.", "I don't swim. I wade, angrily.",
             "Hit 'em where the barnacles are."],
       loyal=["You'd make a fine first mate. Don't let it go to your head."],
       leave="The sea's calling. Louder than you."),

    # ── IRONSPIRE (B) ─────────────────────────────────────────────
    _c("gorath", "Gorath", "Iron Miner", "warrior", "common", "Tank", (150, 150, 165),
       dict(type="tavern", towns=["Stonehelm"]), continent="B",
       bio="Thirty years swinging a pick in the Deep Mines. Swings a sword the same way.",
       passive="iron_grip", traits=["tough", "drunkard"], likes=["battle", "honesty"],
       dislikes=["knowledge"], gifts=["Iron Ore", "Runic Stone"],
       recruit=dict(gold=True), cost=95, mod=dict(hp=20, df=2),
       signature=dict(name="Cave-In", effect="stun"),
       alt=dict(label="Foreman's Plate", accent=(220, 160, 60)),
       hire=["Aye, I can swing a pickaxe AND a sword."],
       idle=["Give me a minute. These legs aren't what they used to be.", "Stone doesn't lie. Neither do I.",
             "I've seen deeper darkness in the mines. This is fine.", "Stay behind me. I've got the thickest skull here."],
       loyal=["You're solid. Like granite. That's a compliment from a miner."],
       leave="I'm going back underground. People are simpler down there."),
    _c("zephyr", "Zephyr", "Wind Mage", "mage", "uncommon", "Mage", (150, 210, 240),
       dict(type="tavern", towns=["Ironmoor"]), continent="B",
       bio="A drifting scholar of the four winds who never stays anywhere long.",
       passive="tailwind", traits=["quick", "bookworm"], likes=["knowledge", "humour"],
       dislikes=["comfort"], gifts=["Feather", "Phoenix Feather", "type:mana"],
       recruit=dict(gold=True, min_level=4), cost=130, mod=dict(mp=10),
       signature=dict(name="Gale Lances", effect="volley"),
       alt=dict(label="Stormcaller Robes", accent=(90, 110, 220)),
       hire=["The wind whispers secrets to those who listen."],
       idle=["I've mastered three winds. The fourth still eludes me.", "My magic isn't flashy. It simply works.",
             "Don't blink. Wind moves faster than you.", "The storms of Ironspire forged my resolve."],
       loyal=["The fourth wind... I think it's you. Don't laugh."],
       leave="The wind changes. So do I."),
    _c("brennan", "Brennan", "Sea Brawler", "warrior", "common", "Swordsman", (60, 120, 200),
       dict(type="tavern", towns=["Hammerfast", "Cliff Port"]), continent="B",
       bio="A dockside bruiser who signs on with anyone who pays fair.",
       passive="sea_legs", traits=["tough", "hothead"], likes=["battle", "gold", "humour"],
       dislikes=["stealth"], gifts=["Hero's Brew", "type:buff"],
       recruit=dict(gold=True), cost=105, mod=dict(hp=15, atk=1),
       signature=dict(name="Keelhaul", effect="smite"),
       alt=dict(label="Bosun's Stripes", accent=(230, 230, 240)),
       hire=["Pay me fair and I'll die for you. Simple as that."],
       idle=["I've brawled in every port from here to the north isles.", "My fists are my weapons. Don't let the size fool you.",
             "The sea hardens you. Look at me. Very hard.", "First rule of a sea fight: hit first, hit hard."],
       loyal=["I'd not die for you for coin any more. I'd do it for free. Don't test it."],
       leave="Pay's stopped feeling fair. I'm back to the docks."),
    _c("hilda", "Hilda Ironbraid", "Shieldmaiden", "warrior", "uncommon", "Tank", (200, 120, 60),
       dict(type="tavern", towns=["Hammerfast"]), continent="B",
       bio="Hammerfast's champion shieldmaiden. She only follows those who have bled on the mountain.",
       passive="shield_wall", traits=["brave", "iron_jaw"], likes=["battle", "boss", "honesty"],
       dislikes=["stealth", "gold"], gifts=["Tower Shield", "Runic Shield", "Iron Ore"],
       recruit=dict(quest=dict(id="hilda_golems", kill=["Golem"], count=4,
                               desc="Smash 4 golems (any kind) and come back to Hammerfast.")),
       cost=0, mod=dict(df=3, hp=10),
       signature=dict(name="Shield Bash", effect="stun"),
       alt=dict(label="Champion's Braids", accent=(230, 200, 90)),
       hire=["Four golems. Then we talk.", "You did it? Then my shield is yours."],
       idle=["A shield is a promise. Mine never breaks.", "Stand behind me and count to ten.",
             "The mountain respects strength. So do I."],
       loyal=["We are shield-kin now. That is forever, in Hammerfast."],
       leave="You've forgotten what the shield is for. I haven't."),
    _c("rex", "Rex", "Wandering Swordmaster", "warrior", "rare", "Blade Master", (200, 200, 210),
       dict(type="rotation", continents=["A", "B", "C", "D", "E"]),
       bio="Nobody knows where Rex trained. Rex says 'everywhere' and changes the subject.",
       passive="wanderers_edge", traits=["brave", "lucky"], likes=["battle", "boss", "humour"],
       dislikes=["comfort"], gifts=["type:equipment", "Runic Greatsword"],
       recruit=dict(duel=True, gold=True, min_level=6), cost=200, mod=dict(atk=2),
       signature=dict(name="Thousand Cuts", effect="volley"),
       alt=dict(label="Masterless Haori", accent=(180, 50, 60)),
       hire=["Beat me and I'll follow you. Lose and buy me a drink."],
       idle=["I go where the wind takes me. Today it brought me to you.", "Don't ask where I've been. It's classified.",
             "I've faced dragons before. Twice.", "No guild. No master. Just the road."],
       loyal=["Finally, a road worth staying on."],
       leave="The road calls. It's a better listener than you."),
    _c("yuki", "Yuki", "Storm Monk", "warrior", "rare", "Swordsman", (120, 180, 255),
       dict(type="rotation", continents=["B", "C"]),
       bio="A monk of the Thunder Steps who left her monastery to test her discipline.",
       passive="storm_fists", traits=["quick", "iron_jaw"], likes=["knowledge", "honesty", "battle"],
       dislikes=["gold", "humour"], gifts=["Sacred Tome", "Holy Water"],
       recruit=dict(gold=True, quest=dict(id="yuki_discipline", kill=["*"], count=6,
                                          desc="Defeat 6 foes in honest battle, then find her again.")),
       cost=180, mod=dict(atk=2),
       signature=dict(name="Thunder Palm", effect="stun"),
       alt=dict(label="Thunder Steps Gi", accent=(250, 230, 120)),
       hire=["Show me discipline: six honest battles. Then I walk with you."],
       idle=["The mountain does not fear the storm. Neither do I.", "My monastery taught peace. I taught myself the rest.",
             "Speed is strength. I have both.", "Breathe. Fight. Win. Simple."],
       loyal=["You are the storm I was looking for."],
       leave="My discipline cannot follow your path. Farewell."),

    # ── FROSTHEIM (C) ─────────────────────────────────────────────
    _c("seraphine", "Seraphine", "Ice Witch", "mage", "uncommon", "Mage", (150, 200, 255),
       dict(type="tavern", towns=["Frostheim"]), continent="C",
       bio="Froze a troll solid as a girl and has never quite stopped looking pleased about it.",
       passive="frost_aura", traits=["bookworm"], likes=["knowledge", "honesty"],
       dislikes=["humour", "comfort"], gifts=["Frost Crystal", "Frost Cloak"],
       recruit=dict(gold=True, min_level=6), cost=150, mod=dict(atk=1, mp=10),
       signature=dict(name="Glacial Spike", effect="stun"),
       alt=dict(label="Aurora Gown", accent=(120, 240, 190)),
       hire=["The cold doesn't bother me. You might, though."],
       idle=["I froze a troll solid once. He's still there.", "Every snowflake has a story. This blizzard tells mine.",
             "Don't touch the staff. Please.", "Frostheim's warmth is within, apparently."],
       loyal=["You've thawed something. Don't tell anyone."],
       leave="I'm colder than I let on. Goodbye."),
    _c("bramwyn", "Bramwyn", "Frost Knight", "warrior", "uncommon", "Tank", (170, 210, 240),
       dict(type="tavern", towns=["Glacierhold"]), continent="C",
       bio="Fifteen winters of training on the Glacierhold ice. He is very proud of every one.",
       passive="permafrost", traits=["stout", "iron_jaw"], likes=["honesty", "battle"],
       dislikes=["stealth", "humour"], gifts=["Frost Crystal", "Steel Shield", "Plate Armor"],
       recruit=dict(gold=True), cost=140, mod=dict(hp=15, df=3),
       signature=dict(name="Avalanche", effect="smite"),
       alt=dict(label="Glacierhold Regalia", accent=(240, 240, 255)),
       hire=["The cold is my shield. Do not question it."],
       idle=["I trained for fifteen winters on this glacier.", "Glacierhold produces the finest knights. I am the finest.",
             "We push forward. The cold will follow.", "In Frostheim, we do not retreat. We advance differently."],
       loyal=["You fight like a Glacierhold knight. Highest praise I have."],
       leave="My oath was to a worthier cause. I return to the ice."),
    _c("solenne", "Solenne", "Blizzard Healer", "healer", "uncommon", "Healer", (190, 225, 255),
       dict(type="tavern", towns=["Frostheim"]), continent="C",
       bio="Has mended wounds in blizzards so thick she healed by touch alone.",
       passive="icebloom_mend", traits=["gentle", "studious"], likes=["kindness", "faith"],
       dislikes=["demons"], gifts=["type:heal", "Frost Crystal"],
       recruit=dict(gold=True), cost=160, mod=dict(mp=10),
       signature=dict(name="Snowdrop Grace", effect="sanctuary"),
       alt=dict(label="Midwinter Vestments", accent=(170, 140, 255)),
       hire=["Ice and healing go together. Trust me."],
       idle=["A cool head and a warm heart. That's the Frostheim way.", "I've mended wounds in blizzards. This is calm.",
             "Your HP is concerning. Drink the vial.", "Even the hardest frost yields to care."],
       loyal=["Even the hardest frost yields to care. You proved it."],
       leave="I can't heal what you keep breaking on purpose."),
    _c("ingrid", "Ingrid Snowveil", "Ice-Harbour Smuggler", "rogue", "uncommon", "Rogue", (200, 230, 255),
       dict(type="tavern", towns=["Ice Harbour"]), continent="C",
       bio="Smuggles hot spices into Frostheim and cold steel out of it.",
       passive="frostbite", traits=["quick", "greedy"], likes=["gold", "stealth"],
       dislikes=["faith", "honesty"], gifts=["type:material", "Venom Fang"],
       recruit=dict(gold=True, min_level=8), cost=150,
       signature=dict(name="Whiteout", effect="volley"),
       alt=dict(label="Blackice Leathers", accent=(60, 70, 110)),
       hire=["My rates are frozen. Unlike my heart. That's for sale too."],
       idle=["Never trust a frozen lake or a smiling harbourmaster.", "I know a shortcut. It's illegal.",
             "Cold hands, quick knives."],
       loyal=["You're the only cargo I'd never sell."],
       leave="Better offer came in. Nothing personal. Mostly."),

    # ── ASH SANDS (D) ─────────────────────────────────────────────
    _c("kael", "Kael", "Desert Drifter", "rogue", "uncommon", "Rogue", (210, 170, 90),
       dict(type="tavern", towns=["Sandreach"]), continent="D",
       bio="Sells directions, water and silence across the Ash Sands. Silence costs extra.",
       passive="sand_step", traits=["greedy", "quick"], likes=["gold", "stealth"],
       dislikes=["kindness", "faith"], gifts=["gold", "type:material"],
       recruit=dict(gold=True), cost=110, mod=dict(atk=1),
       signature=dict(name="Dune Viper", effect="venom"),
       alt=dict(label="Sandstorm Wraps", accent=(150, 60, 40)),
       hire=["Gold first. Loyalty second. That's the desert way."],
       idle=["The sand hides many things. Including me.", "I've survived worse than this. Probably.",
             "Don't get between me and the exit.", "I know people in Sandreach who can help. For a price."],
       loyal=["Loyalty second, I said. Seems I lied."],
       leave="The desert way: when the water runs out, you leave."),
    _c("rashid", "Rashid", "Sand Mage", "mage", "uncommon", "Mage", (230, 190, 110),
       dict(type="tavern", towns=["Sandreach"]), continent="D",
       bio="Learned his craft from the old dune-singers who live beneath the Dust Shrine.",
       passive="sandstorm", traits=["bookworm"], likes=["knowledge", "faith"],
       dislikes=["gold"], gifts=["Runic Stone", "type:mana"],
       recruit=dict(gold=True, min_level=5), cost=135, mod=dict(mp=10),
       signature=dict(name="Thousand Grains", effect="volley"),
       alt=dict(label="Dune-Singer Robes", accent=(200, 90, 50)),
       hire=["Sand is everywhere. Sand is everything."],
       idle=["They call it a wasteland. I call it home.", "My spells carry the sting of a thousand grains.",
             "The desert has its own magic. Ancient and merciless.", "Never underestimate what hides beneath the dunes."],
       loyal=["The dunes sing your name now. Quietly. They're shy."],
       leave="The sands call me home."),
    _c("thalia", "Thalia", "Dune Dancer", "rogue", "uncommon", "Rogue", (235, 150, 80),
       dict(type="tavern", towns=["Oasis Keep"]), continent="D",
       bio="Crossed the Ash Sands alone three times. Danced at the sultan's court once, and left with his ring.",
       passive="mirage", traits=["quick", "lucky"], likes=["humour", "comfort"],
       dislikes=["honesty"], gifts=["type:equipment", "Phoenix Pendant"],
       recruit=dict(gold=True), cost=120, mod=dict(atk=1),
       signature=dict(name="Mirage Waltz", effect="volley"),
       alt=dict(label="Courtly Silks", accent=(230, 80, 160)),
       hire=["The desert kills the slow. I am not slow."],
       idle=["Watch my feet. The dance decides who dies.", "I've crossed the Ash Sands alone. Three times.",
             "Pretty weapons matter less than fast ones.", "Sand gets everywhere. So do my blades."],
       loyal=["I'd dance for you. Only for you. And for money."],
       leave="The music's stopped. I'm leaving."),
    _c("nur", "Nur", "Desert Cleric", "healer", "common", "Healer", (240, 220, 150),
       dict(type="tavern", towns=["Oasis Keep"]), continent="D",
       bio="Tends the Oasis Keep shrine and anyone who crawls to it out of the dunes.",
       passive="oasis_blessing", traits=["gentle", "devoted"], likes=["faith", "kindness"],
       dislikes=["demons", "gold"], gifts=["Holy Water", "type:mana"],
       recruit=dict(gold=True), cost=115, mod=dict(mp=10),
       signature=dict(name="Oasis Rain", effect="sanctuary"),
       alt=dict(label="Starfollower Mantle", accent=(110, 160, 240)),
       hire=["The oasis gives life. So shall I."],
       idle=["Faith is armour. Mine is well-fitted.", "I've healed warriors, merchants, and one very large camel.",
             "The desert heat is no obstacle to divine mercy.", "Follow the star. I'll keep you alive until we get there."],
       loyal=["The star I followed led me to you."],
       leave="My faith and your path have parted ways."),
    _c("tarik", "Tarik", "Dune Lancer", "warrior", "uncommon", "Swordsman", (220, 160, 70),
       dict(type="tavern", towns=["Dunewatch"]), continent="D",
       bio="A lancer of the Dunewatch riders, hopelessly in love with a certain dancer.",
       passive="lance_charge", traits=["brave", "hothead"], likes=["battle", "humour", "boss"],
       dislikes=["stealth"], gifts=["type:equipment", "Steel Sword"],
       recruit=dict(gold=True, companion="thalia"), cost=120,
       signature=dict(name="Dune Charge", effect="smite"),
       alt=dict(label="Rider's Crimson", accent=(200, 40, 40)),
       hire=["Thalia rides with you? Then so does my lance."],
       idle=["A good lance and a good horse. I have one of those.", "Charge first. Plan later. Works mostly.",
             "Has Thalia mentioned me? Don't tell her I asked."],
       loyal=["You're family now. Thalia agrees. I asked."],
       leave="My lance returns to Dunewatch."),
    _c("nisa_sandwalker", "Nisa Sandwalker", "Desert Scout", "rogue", "rare", "Rogue", (225, 180, 110),
       dict(type="special", where="Sunspire Kasbah", wander=["D"]), continent="D",
       bio="Scout of the Sunspire caravans. She can find water in a dune and a lie in a smile.",
       passive="desert_eyes", traits=["keen_eyed", "quick"], likes=["stealth", "honesty", "knowledge"],
       dislikes=["gold", "demons"], gifts=["type:material", "Travel Cloak"],
       recruit=dict(gold=True, min_level=8), cost=170,
       signature=dict(name="Sunspire Volley", effect="volley"),
       alt=dict(label="Kasbah Silks", accent=(80, 170, 200)),
       hire=["The sultan pays me to watch roads. You look like a road worth watching."],
       idle=["Tracks don't lie. People do.", "Water is three dunes east. Trust me.",
             "In Sunspire we say: the sun sees all, so wear a hood."],
       loyal=["I would cross the Ash Sands for you. I already have, twice."],
       leave="The caravans need me more than you do."),

    # ── SOUTH ISLES (E) ───────────────────────────────────────────
    _c("coral", "Coral", "Siren Scholar", "mage", "uncommon", "Mage", (80, 200, 200),
       dict(type="tavern", towns=["Seaview"]), continent="E",
       bio="Keeper of the Siren Library in Seaview, on an extended and unapproved field trip.",
       passive="siren_song", traits=["bookworm", "studious"], likes=["knowledge", "humour"],
       dislikes=["battle"], gifts=["Sacred Tome", "type:mana"],
       recruit=dict(gold=True), cost=140, mod=dict(mp=10),
       signature=dict(name="Lorelei", effect="stun"),
       alt=dict(label="Pearl Scholar Gown", accent=(240, 220, 240)),
       hire=["Knowledge is power. I have a great deal of both."],
       idle=["The seas hold secrets older than any kingdom.", "Don't be distracted by my voice. Others have been.",
             "Magic flows like water. I am very good at water.", "The Siren Library in Seaview is magnificent. Miss it already."],
       loyal=["I've started a chapter about you. It's long."],
       leave="My library misses me. Unlike some people."),
    _c("petra", "Petra", "Tide Healer", "healer", "uncommon", "Healer", (90, 170, 220),
       dict(type="tavern", towns=["Seaview"]), continent="E",
       bio="Stitched sailors back together mid-storm for twelve years on the Seaview cutters.",
       passive="tidal_mend", traits=["tough", "gentle"], likes=["kindness", "honesty"],
       dislikes=["demons"], gifts=["type:heal", "Elixir"],
       recruit=dict(gold=True), cost=155, mod=dict(mp=10),
       signature=dict(name="Spring Tide", effect="sanctuary"),
       alt=dict(label="Stormwatch Oilskin", accent=(240, 200, 60)),
       hire=["The tide heals all things. Given enough time."],
       idle=["I've stitched sailors back together mid-storm.", "You're lucky I'm here. Very lucky.",
             "The sea provides. I simply channel it.", "My healing isn't magic — it's dedication. Mostly."],
       loyal=["You're the steadiest deck I've ever stood on."],
       leave="The tide's turned. I'm going with it."),
    _c("kiri", "Kiri Wavecutter", "Pearl Diver", "rogue", "common", "Rogue", (60, 200, 170),
       dict(type="tavern", towns=["Palmhaven", "Coral Bay"]), continent="E",
       bio="Holds her breath for four minutes and her tongue for none.",
       passive="pearl_diver", traits=["lucky"], likes=["humour", "gold", "comfort"],
       dislikes=["knowledge"], gifts=["gold", "type:buff"],
       recruit=dict(gold=True), cost=85,
       signature=dict(name="Riptide", effect="volley"),
       alt=dict(label="Lagoon Wraps", accent=(250, 120, 90)),
       hire=["Pearls, gold, adventure. In that order. Let's go!"],
       idle=["Everything's better with a bit of sea in it.", "I found a pearl in a monster once. Long story. Gross.",
             "Race you to the next fight!"],
       loyal=["You're my favourite pearl. Don't tell the pearls."],
       leave="Going back to the reef. It's less complicated."),
    _c("leilani", "Leilani", "Reef Priestess", "healer", "uncommon", "Healer", (240, 140, 180),
       dict(type="tavern", towns=["Coralwatch", "Pearl Harbour"]), continent="E",
       bio="Priestess of the reef spirits; her songs close wounds and calm the tides.",
       passive="tide_ward", traits=["gentle", "devoted"], likes=["faith", "kindness", "comfort"],
       dislikes=["demons", "battle"], gifts=["Holy Water", "type:heal"],
       recruit=dict(gold=True, min_level=4), cost=150, mod=dict(mp=10),
       signature=dict(name="Reef Chorus", effect="sanctuary"),
       alt=dict(label="Moonreef Vestments", accent=(120, 120, 240)),
       hire=["The reef spirits say you need looking after. They're very blunt."],
       idle=["Listen — the tide is singing.", "Every wound is a story that wants a gentle ending.",
             "Breathe with the waves. Slower. Good."],
       loyal=["The reef spirits named you. It's a nice name."],
       leave="The spirits call me back to the reef."),

    # ── Travellers, prisoners, strangers, turncoats ───────────────
    _c("sable", "Sable", "Masked Duelist", "rogue", "rare", "Rogue", (40, 40, 60),
       dict(type="rotation", continents=["A", "D", "E"]),
       bio="A masked duelist who has never lost — or never admitted to losing.",
       passive="riposte", traits=["quick", "scarred"], likes=["battle", "honesty"],
       dislikes=["humour", "comfort"], gifts=["Assassin Dagger", "type:equipment"],
       recruit=dict(duel=True, min_level=8), cost=0,
       signature=dict(name="Crimson Riposte", effect="drain"),
       alt=dict(label="Unmasked", accent=(200, 30, 60)),
       hire=["Cross blades with me. If you win, the mask follows you."],
       idle=["The mask stays on.", "Every fight is a conversation. Most people are dull talkers.",
             "Steel never flatters."],
       loyal=["Perhaps... one day I'll show you my face."],
       leave="Our duel is over. I leave unbeaten."),
    _c("orrin", "Orrin Starglass", "Astronomer", "mage", "rare", "Archmage", (110, 140, 240),
       dict(type="prisoner"),
       bio="Was charting a comet when cultists dragged him underground to read the stars for them.",
       passive="starlight", traits=["bookworm", "studious"], likes=["knowledge", "kindness"],
       dislikes=["battle", "demons"], gifts=["Sacred Tome", "Mana Stone", "type:mana"],
       recruit=dict(), cost=0, mod=dict(mp=15),
       signature=dict(name="Meteor Shower", effect="volley"),
       alt=dict(label="Comet-Watcher Robes", accent=(250, 250, 200)),
       hire=["You freed me! The comet waits for no one — but I'll wait for you."],
       idle=["Did you know the stars are just very far away campfires? Roughly.", "I calculated our odds. Let's not discuss them.",
             "Look up more often. The sky is free."],
       loyal=["I named a star after you. It's a small one, but it's bright."],
       leave="My comet is returning. I must go."),
    _c("ilsa", "Ilsa Wayfinder", "Cartographer", "rogue", "rare", "Rogue", (180, 140, 90),
       dict(type="prisoner"),
       bio="Mapped half the world's dungeons — and got locked inside the last one.",
       passive="pathfinder", traits=["keen_eyed", "devoted"], likes=["knowledge", "humour", "stealth"],
       dislikes=["comfort"], gifts=["Travel Cloak", "Feather"],
       recruit=dict(), cost=0,
       signature=dict(name="Shortcut", effect="stun"),
       alt=dict(label="Expedition Coat", accent=(60, 120, 60)),
       hire=["My map of this place is finished! And so am I, almost. Thank you!"],
       idle=["Left, left, right... no, other left.", "There's always another way out. I'll find it.",
             "This would look lovely on a map."],
       loyal=["I've drawn us onto every map I own. Together."],
       leave="Uncharted country is calling. Goodbye, friend."),
    _c("magnus", "Magnus", "Grand Paladin", "healer", "epic", "Arch Priest", (240, 220, 140),
       dict(type="prisoner", min_danger=3),
       bio="Once led the Order of the Dawn. Captured guarding its last relic, he never stopped praying.",
       passive="holy_aura", traits=["devoted", "tough"], likes=["faith", "honesty", "boss"],
       dislikes=["demons", "gold"], gifts=["Holy Relic", "Holy Water", "Holy Mace"],
       recruit=dict(min_level=10), cost=0, mod=dict(hp=20, df=2),
       signature=dict(name="Dawnbreak", effect="sanctuary"),
       alt=dict(label="Dawn Order Plate", accent=(255, 255, 255)),
       hire=["The light does not abandon us. Neither shall I."],
       idle=["I've led armies. A small party is refreshing.", "Heal first. Then smite. In that order.",
             "My order disbanded. Their loss. Your gain.", "The divine favours the prepared. Let us be prepared."],
       loyal=["The Order of the Dawn lives again — in you."],
       leave="I cannot serve the light beside you any longer."),
    _c("elara", "Elara", "Arcane Wanderer", "mage", "epic", "Archmage", (170, 110, 240),
       dict(type="ruins"),
       bio="Studied in seven academies, was expelled from six and left the seventh on fire.",
       passive="arcane_overflow", traits=["bookworm", "hothead"], likes=["knowledge", "humour"],
       dislikes=["faith", "comfort"], gifts=["Mana Stone", "Arcane Rod", "type:mana"],
       recruit=dict(min_level=12, item=["Mana Stone", 1], gold=True), cost=220, mod=dict(atk=2, mp=20),
       signature=dict(name="Seventh Academy", effect="inferno"),
       alt=dict(label="Prismatic Robes", accent=(90, 230, 230)),
       hire=["Bring me a Mana Stone and coin for my research. Then I'll consider you."],
       idle=["I've studied in seven academies. Left them all.", "Theory is overrated. Results matter.",
             "This staff has seen three continents. Wants a fourth.", "Do not ask me to explain the math. Just trust the explosion."],
       loyal=["You're the first experiment I don't want to end."],
       leave="Magic is limitless. My patience isn't. Goodbye."),
    _c("wren", "Wren", "Hedge Witch", "healer", "rare", "Healer", (130, 90, 160),
       dict(type="ruins"),
       bio="Lives among broken stones and talks to the crows, who mostly talk back.",
       passive="hex_ward", traits=["studious", "scarred"], likes=["knowledge", "honesty", "stealth"],
       dislikes=["faith", "gold"], gifts=["Bone Shard", "Dark Shard", "Feather"],
       recruit=dict(item=["Bone Shard", 3]), cost=0,
       signature=dict(name="Crow's Feast", effect="drain"),
       alt=dict(label="Raven Feather Cloak", accent=(30, 30, 40)),
       hire=["Three bone shards for the crows. They're owed."],
       idle=["The crows say you're alright. Mostly.", "Old stones remember. Ask nicely.",
             "Hex first, apologise later."],
       loyal=["The crows have adopted you. There's no undoing that."],
       leave="The crows are leaving. So am I."),
    _c("vex", "Vex", "Void Rogue", "rogue", "epic", "Shadow Assassin", (120, 60, 180),
       dict(type="wander", continents=["A", "B", "C", "D", "E"], min_level=10),
       bio="Stepped out of the void one day with no memory and a very sharp knife.",
       passive="void_step", traits=["quick", "lucky"], likes=["stealth", "humour", "gold"],
       dislikes=["faith", "honesty"], gifts=["Dark Shard", "Shadow Cloak", "Shadow Blade"],
       recruit=dict(gold=True, min_level=10, item=["Dark Shard", 3]), cost=220, mod=dict(atk=2),
       signature=dict(name="Void Rend", effect="drain"),
       alt=dict(label="Starless Shroud", accent=(20, 20, 30)),
       hire=["Three dark shards and a purse. The void is expensive."],
       idle=["You can't see me unless I want you to.", "The void calls. I answer. Then bill someone.",
             "Don't follow me. Seriously. Stop.", "I've stolen from kings. You seem nicer."],
       loyal=["Death? Been there. Got bored. Staying with you is more interesting."],
       leave="Back to the void. Don't wait up."),
    _c("ysolde", "Ysolde", "the Dragonsworn", "warrior", "legendary", "War Titan", (255, 120, 60),
       dict(type="wander", continents=["B", "C"], min_level=25),
       bio="Sworn to the last dragon-hunting order. She walks the high passes looking for a worthy blade.",
       passive="dragonheart", traits=["brave", "tough"], likes=["boss", "battle", "honesty"],
       dislikes=["stealth", "comfort"], gifts=["Dragon Scale", "Dragon Sword", "Dragon Scale Armor"],
       recruit=dict(flag="dragon_slain", flag_text="Slay the dragon Vaeltharion", duel=True, min_level=25),
       cost=0, mod=dict(hp=30, atk=3, df=3),
       signature=dict(name="Wyrmfall", effect="inferno"),
       alt=dict(label="Wyrmscale Plate", accent=(200, 40, 30)),
       hire=["You slew Vaeltharion? Then face me, dragonslayer."],
       idle=["Every scar is a dragon that did not get a second chance.", "The high passes are quiet now. Too quiet.",
             "Fear is a dragon. Slay it daily."],
       loyal=["My oath had one blade left in it. It's yours."],
       leave="The order calls me back to the passes."),
    _c("snag", "Snag", "Goblin Turncoat", "rogue", "common", "Goblin", (120, 200, 90),
       dict(type="defeated", enemies=["Goblin"]),
       bio="Lost a fight, lost his tribe, found you. In that order.",
       passive="scavenger", traits=["lucky", "greedy"], likes=["gold", "humour"],
       dislikes=["honesty", "faith"], gifts=["gold", "type:material"],
       recruit=dict(), cost=20,
       signature=dict(name="Shiny Grab", effect="venom"),
       alt=dict(label="Fancy Hat", accent=(230, 60, 160)),
       hire=["Snag good! Snag useful! Snag only bite enemies. Mostly."],
       idle=["Snag found shiny. Snag keeping shiny.", "Big folk fight loud. Goblins fight smart.",
             "Is that edible? Snag check."],
       loyal=["You Snag's tribe now. Best tribe."],
       leave="Snag go find new tribe. Bye bye."),
    _c("gloop", "Gloop", "Friendly Slime", "warrior", "uncommon", "Slime", (90, 210, 120),
       dict(type="defeated", enemies=["Slime"]),
       bio="A slime that decided it would rather be hugged than hit. It is surprisingly sturdy.",
       passive="gelatinous", traits=["tough", "devoted"], likes=["comfort", "kindness", "humour"],
       dislikes=["battle"], gifts=["type:heal", "type:material"],
       recruit=dict(), cost=0, mod=dict(hp=25, df=2),
       signature=dict(name="Big Wobble", effect="stun"),
       alt=dict(label="Golden Jelly", accent=(250, 210, 60)),
       hire=["*wobbles happily*"],
       idle=["*blorp*", "*jiggles protectively*", "*absorbs a pebble, looks proud*"],
       loyal=["*forms a small, wobbly heart*"],
       leave="*oozes away sadly*"),
    _c("ragna", "Ragna Redhand", "Bandit Turncoat", "warrior", "uncommon", "Bandit", (200, 70, 60),
       dict(type="defeated", enemies=["Bandit", "Desert Raider", "Cutthroat", "Alley Thief"]),
       bio="Ran with the worst crews on the roads until somebody finally beat her fairly.",
       passive="cheap_shot", traits=["hothead", "scarred"], likes=["gold", "battle", "honesty"],
       dislikes=["faith", "kindness"], gifts=["gold", "Venom Dagger"],
       recruit=dict(), cost=40,
       signature=dict(name="Dirty Trick", effect="stun"),
       alt=dict(label="Reformed Leathers", accent=(90, 140, 90)),
       hire=["You hit like you mean it. Pay me forty and I'll hit for you instead."],
       idle=["Road rules: never trust a smiling merchant.", "I know every ambush spot from here to the coast.",
             "Old crew would laugh at me now. Let them."],
       loyal=["You gave me a road worth walking straight. Thanks."],
       leave="Back to the roads. Stay out of my way on them."),
    _c("kesh", "Kesh the Lapsed", "Cult Defector", "mage", "rare", "Cultist", (220, 100, 60),
       dict(type="defeated", enemies=["Cultist", "Dragon Cultist"]),
       bio="A dragon-cult acolyte who lost his faith — but kept the fireballs.",
       passive="forbidden_lore", traits=["bookworm", "scarred"], likes=["knowledge", "kindness"],
       dislikes=["faith", "demons"], gifts=["Dark Shard", "Sacred Tome", "type:mana"],
       recruit=dict(min_level=6), cost=0, mod=dict(atk=1),
       signature=dict(name="Heretic's Flame", effect="inferno"),
       alt=dict(label="Penitent's Robes", accent=(240, 240, 240)),
       hire=["Spare me and I'll turn the cult's fire against them."],
       idle=["The chanting still echoes in my head. Fireballs help.", "Don't ask what the robes smell like.",
             "Every cult promises the end of the world. It keeps not ending."],
       loyal=["I found something to believe in after all. It's you. Awkward."],
       leave="Maybe I just swapped one master for another. I'm leaving."),

    # ── Contract companions (castles / kingdom story) ─────────────
    _c("old_bram", "Old Bram", "Retired Royal Guard", "warrior", "uncommon", "Tank", (130, 120, 160),
       dict(type="tavern", towns=["Valdmere"]), continent="A",
       bio="Forty years on the walls of Castle Lumeris. Now he guards a corner seat in the tavern.",
       passive="old_guard", traits=["stout", "scarred"], likes=["honesty", "comfort", "humour"],
       dislikes=["demons", "stealth"], gifts=["Hero's Brew", "type:buff", "Steel Helm"],
       recruit=dict(gold=True, min_level=3), cost=60, mod=dict(df=3),
       signature=dict(name="Wall of Lumeris", effect="rally"),
       alt=dict(label="Royal Guard Livery", accent=(150, 90, 220)),
       hire=["Buy an old man a drink and he'll guard your back like it's the king's own."],
       idle=["In my day, the walls of Lumeris never fell. Not once.", "My knees creak. My shield doesn't.",
             "The young knights could learn a thing or two from these old bones."],
       loyal=["I stood guard for three kings. You're the first I'd call a friend."],
       leave="Time I went back to my corner seat."),
    _c("knight_cassia", "Dame Cassia", "Knight of the Silver Lily", "warrior", "epic", "Swordsman", (170, 120, 230),
       dict(type="special", where="Valdmere"), continent="A",
       bio="Youngest knight ever admitted to Valdmere's Silver Lily order. She duels anyone who doubts it.",
       passive="royal_guard", traits=["brave", "devoted"], likes=["honesty", "battle", "faith"],
       dislikes=["demons", "stealth", "gold"], gifts=["Holy Shield", "Mirror Shield", "type:equipment"],
       recruit=dict(duel=True, min_level=10), cost=0, mod=dict(hp=15, atk=2, df=3),
       signature=dict(name="Silver Lily Oath", effect="rally"),
       alt=dict(label="Ceremonial Silver", accent=(235, 235, 250)),
       hire=["The Silver Lily serves the worthy. Prove yourself, blade to blade."],
       idle=["For Valdmere and the crown.", "A knight's word is the strongest steel.",
             "Stand straight. You represent Valdmere now."],
       loyal=["I would renounce the order before I left your side."],
       leave="My oath to the crown outweighs my oath to you."),
    _c("elowen", "Princess Elowen", "Heir of Valdmere", "mage", "legendary", "Archmage", (200, 140, 255),
       dict(type="story", where="Valdmere"), continent="A",
       bio="Valdmere's princess and a prodigy of the royal academy, who would rather see the world than rule it.",
       passive="royal_ward", traits=["studious", "devoted"], likes=["knowledge", "kindness", "honesty"],
       dislikes=["demons", "gold"], gifts=["Celestial Robe", "Crystal Staff", "type:mana"],
       recruit=dict(story=True), cost=0, mod=dict(atk=3, mp=30, hp=10),
       signature=dict(name="Starfall of Lumeris", effect="inferno"),
       alt=dict(label="Coronation Gown", accent=(255, 215, 120)),
       hire=["Father will be furious. Let's go before he finds out."],
       idle=["The academy never taught me how much I'd like mud.", "A crown is just a very heavy hat.",
             "I've read about these places. Reading undersold them."],
       loyal=["Whatever crown I wear one day, you'll stand beside it."],
       leave="I must return to Valdmere. My people need me."),
    _c("zhaal", "Zhaal", "Oathbound Demon Knight", "warrior", "epic", "Death Knight", (200, 40, 40),
       dict(type="special", where="Duskthorn Citadel"), continent="B",
       bio="Kharzul's own champion, bound by the pact to fight at your side. Honourable in a terrifying way.",
       passive="hellfire_blade", traits=["brave", "iron_jaw"], likes=["battle", "boss", "honesty", "demons"],
       dislikes=["faith", "kindness"], gifts=["Obsidian Shard", "Dark Shard", "Obsidian Plate"],
       recruit=dict(flag="demon_pact", flag_text="Seal the pact with Demon Lord Kharzul", min_level=12),
       cost=0, mod=dict(hp=20, atk=3, df=2),
       signature=dict(name="Infernal Verdict", effect="inferno"),
       alt=dict(label="Pactbreaker Armour", accent=(255, 140, 30)),
       hire=["The pact binds me. My blade is yours, mortal."],
       idle=["Your kind fear fire. Mine bathes in it.", "Kharzul keeps his word. So do I.",
             "Do not mistake my courtesy for kindness."],
       loyal=["The pact no longer binds me. I stay by choice."],
       leave="The pact is broken. Pray we do not meet again."),
]

COMPANION_DEFS = {d["id"]: d for d in _DEFS}
COMPANION_BY_ID = COMPANION_DEFS            # legacy alias
CONTRACT_IDS = ("knight_cassia", "elowen", "zhaal", "nisa_sandwalker", "old_bram")
LEGACY_IDS = ("aldric", "lyra", "mira", "kael", "gorath", "zephyr", "seraphine",
              "bramwyn", "solenne", "thalia", "rashid", "nur", "brennan", "coral",
              "petra", "rex", "vex", "elara", "magnus", "yuki")

# v1 colour keys -> RGB (customisation used to be 8 named colours)
LEGACY_COLOURS = {
    "gold": (255, 215, 0), "green": (80, 200, 80), "cyan": (80, 220, 220),
    "purple": (180, 80, 220), "pink": (255, 150, 200), "blue": (80, 140, 255),
    "red": (220, 60, 60), "white": (255, 255, 255),
}

# ── Cosmetic colour styles per role (shape like game_customise.STYLE_DEFS) ──

COMPANION_STYLES = {
    "warrior": [
        dict(id="cw_steel",   label="Polished Steel",  desc="Bright plate, freshly oiled.",        colour=(200, 210, 230)),
        dict(id="cw_crimson", label="Crimson Vanguard", desc="Blood-red tabard of the front line.", colour=(200, 40, 50)),
        dict(id="cw_forest",  label="Forest Warden",   desc="Mossy greens for woodland patrols.",  colour=(70, 150, 70)),
        dict(id="cw_onyx",    label="Onyx Guard",      desc="Black-lacquered armour, silent.",      colour=(70, 70, 90)),
    ],
    "rogue": [
        dict(id="cr_shadow",  label="Night Shade",     desc="Deep violet wraps for moonless work.", colour=(90, 60, 140)),
        dict(id="cr_dune",    label="Dune Runner",     desc="Sun-bleached sand tones.",             colour=(220, 180, 110)),
        dict(id="cr_viper",   label="Viper",           desc="Venom green with black trim.",         colour=(90, 200, 70)),
        dict(id="cr_scarlet", label="Scarlet Rogue",   desc="Bold red — subtlety is overrated.",    colour=(230, 60, 70)),
    ],
    "mage": [
        dict(id="cm_arcane",  label="Arcane Violet",   desc="Classic academy purple.",              colour=(150, 80, 230)),
        dict(id="cm_frost",   label="Frostweave",      desc="Pale ice-blue silks.",                 colour=(160, 220, 255)),
        dict(id="cm_ember",   label="Emberweave",      desc="Smouldering orange and red.",          colour=(240, 120, 40)),
        dict(id="cm_verdant", label="Verdant Sage",    desc="Living green, smells of rain.",        colour=(80, 200, 140)),
    ],
    "healer": [
        dict(id="ch_dawn",    label="Dawn Vestments",  desc="White and gold of the morning light.", colour=(250, 230, 160)),
        dict(id="ch_lotus",   label="Lotus",           desc="Soft pink petals and calm.",           colour=(240, 150, 200)),
        dict(id="ch_tide",    label="Tidewater",       desc="Sea-blue robes.",                      colour=(80, 160, 230)),
        dict(id="ch_herbal",  label="Herbalist",       desc="Earthy browns and leaf green.",        colour=(130, 170, 80)),
    ],
}


# ═══════════════════════════════════════════════════════════════
# Geography helpers
# ═══════════════════════════════════════════════════════════════

_FALLBACK_TOWNS = {
    "A": ["Greenveil", "Oakwatch", "Mossford", "Tidereach", "Greenport"],
    "B": ["Ironmoor", "Stonehelm", "Hammerfast", "Cliff Port", "Anvil Docks"],
    "C": ["Frostheim", "Glacierhold", "Ice Harbour"],
    "D": ["Sandreach", "Dunewatch", "Oasis Keep", "Sand Docks", "Desert Port"],
    "E": ["Seaview", "Palmhaven", "Coralwatch", "South Port", "Coral Bay", "Pearl Harbour"],
}
_EXTRA_TOWNS = {"Valdmere": "A"}       # capital (game_capital)


def continent_towns():
    """{continent_id: [town and port names]} from game_world (fallback: static)."""
    try:
        from game_world import CONTINENTS
        out = {}
        for c in CONTINENTS:
            out[c["id"]] = list(c.get("cities", [])) + list(c.get("ports", []))
        return out or dict(_FALLBACK_TOWNS)
    except Exception:
        return dict(_FALLBACK_TOWNS)


def town_continent(town_name):
    """Continent id for a town/port name, or None."""
    t = (town_name or "").strip().lower()
    if not t:
        return None
    for name, cid in _EXTRA_TOWNS.items():
        if name.lower() == t:
            return cid
    for cid, towns in continent_towns().items():
        if any(x.lower() == t for x in towns):
            return cid
    return None


def _h(*parts):
    return zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) & 0xFFFFFFFF


def is_starborn(seed, cid, day):
    """Deterministic 1-in-512 'shiny' roll for an offer on a given day."""
    return _h("starborn", seed, cid, day) % STARBORN_ODDS == 0


def rotation_town(cid, day):
    """Where a 'rotation' traveller drinks today, or None (on the road)."""
    d = COMPANION_DEFS.get(cid)
    if not d or d["spawn"].get("type") != "rotation":
        return None
    h = _h("rot", cid, day)
    if h % 100 >= 50:                 # roughly every other day
        return None
    towns = []
    ct = continent_towns()
    for c in d["spawn"].get("continents") or sorted(ct):
        towns.extend(ct.get(c, []))
    if not towns:
        return None
    return towns[(h // 100) % len(towns)]


def tavern_recruits(town_name, day, player=None):
    """Companion ids drinking in this town's tavern on this in-game day.

    Regulars (spawn 'tavern') are always there; rare travellers rotate
    between taverns day by day; ports without regulars get one continental
    common/uncommon who is passing through.  With `player`, companions
    already in the roster (or who left for good) are filtered out.
    """
    t = (town_name or "").strip().lower()
    if not t:
        return []
    try:
        day = int(day)
    except Exception:
        day = 0
    out = []
    for cid, d in COMPANION_DEFS.items():
        sp = d["spawn"]
        if sp.get("type") == "tavern" and any(x.lower() == t for x in sp.get("towns", [])):
            out.append(cid)
    if not out:
        cont = town_continent(town_name)
        if cont:
            pool = [cid for cid, d in COMPANION_DEFS.items()
                    if d["spawn"].get("type") == "tavern" and d["continent"] == cont
                    and d["rarity"] in ("common", "uncommon")]
            if pool:
                pool.sort()
                out.append(pool[_h("port", t, day) % len(pool)])
    for cid, d in COMPANION_DEFS.items():
        if d["spawn"].get("type") == "rotation":
            rt = rotation_town(cid, day)
            if rt and rt.lower() == t and cid not in out:
                out.append(cid)
    if player is not None:
        try:
            party = player.party
            have = {c.id for c in party.roster}
            gone = set(getattr(party, "departed", {}) or {})
            out = [c for c in out if c not in have and c not in gone]
        except Exception:
            pass
    return out


def hire_cost(cid, level=1, player=None):
    """Gold to hire `cid` at the given level (0 for gold-free recruits)."""
    d = COMPANION_DEFS.get(cid)
    if not d or not d.get("cost"):
        return 0
    lvl = max(1, int(level or 1))
    cost = float(d["cost"]) * (1 + 0.12 * (lvl - 1))
    for t in d["traits"]:
        cost *= 1 + TRAITS.get(t, {}).get("mods", {}).get("cost_pct", 0) / 100.0
    if player is not None:
        clan = getattr(player, "owned_clan", None)
        if clan is not None:
            ups = getattr(clan, "upgrades", []) or []
            if "Clan Banner" in ups:
                cost *= 0.9
            if "Tavern" in ups:
                cost *= 0.9
    return max(10, int(round(cost / 5.0)) * 5)


def where_found(cid):
    """Short human description of where a companion can be found."""
    d = COMPANION_DEFS.get(cid)
    if not d:
        return "?"
    sp = d["spawn"]
    ty = sp.get("type")
    cont_names = {"A": "Aeloria", "B": "Ironspire", "C": "Frostheim", "D": "Ash Sands", "E": "South Isles"}
    if ty == "tavern":
        return "Tavern: " + ", ".join(sp.get("towns", []))
    if ty == "rotation":
        return "Travelling tavern guest (" + ", ".join(cont_names.get(c, c) for c in sp.get("continents", [])) + ")"
    if ty == "wander":
        return "Wanders the roads of " + ", ".join(cont_names.get(c, c) for c in sp.get("continents", []))
    if ty == "prisoner":
        return "Prisoner in a conquered dungeon"
    if ty == "ruins":
        return "Stranger in the ruins"
    if ty == "defeated":
        return "A beaten " + "/".join(sp.get("enemies", [])) + " may ask to join"
    if ty == "special":
        return sp.get("where", "Somewhere special")
    if ty == "story":
        return "Story reward (" + sp.get("where", "?") + ")"
    return "?"
