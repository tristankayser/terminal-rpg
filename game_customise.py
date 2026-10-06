"""
game_customise.py — Character customisation studio for Terminal-RPG.

Available in every town via [C] Customise.
Each job class has 4 distinct style options. Each gives a cosmetic look
+ a small real passive perk. Switch any time in any town, for free.
Previous perk is removed when you switch.
"""

from __future__ import annotations

import os
from game_term import C, clr, W

_R = "\033[0m"; _B = "\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD  = _fg(255,215,0);  _WHITE = _fg(255,255,255)
_DIM   = _fg(100,100,100); _GREEN = _fg(80,200,80)
_RED   = _fg(220,60,60);   _CYAN  = _fg(80,220,220)
_YELL  = _fg(240,200,60);  _PURP  = _fg(180,80,220)
_ORAN  = _fg(220,140,40);  _TEAL  = _fg(60,200,180)


# ── Style definitions ────────────────────────────────────────────
# Each style: id, label, desc, perk, colour(rgb), sprite, apply(player)

STYLE_DEFS = {

    "Swordsman": [
        dict(id="sw_valiant",   label="Valiant Knight",
             desc="Gleaming armour, noble crest. A hero straight from legend.",
             perk="+ 3 DEF  (shield instinct)",
             colour=(200,220,255), sprite="⚔",
             apply=lambda p: setattr(p,"defense",p.defense+3)),
        dict(id="sw_berserker", label="Berserker",
             desc="Torn cloak, war paint, twin blades. Fear is your weapon.",
             perk="+ 4 ATK  (rage-forged strikes)",
             colour=(220,60,40), sprite="🔥",
             apply=lambda p: setattr(p,"atk",p.atk+4)),
        dict(id="sw_duelist",   label="Duelist",
             desc="Slender rapier, sharp coat. Elegant, precise, deadly.",
             perk="+ 5% Crit  (fine blade technique)",
             colour=(255,215,0), sprite="✦",
             apply=lambda p: setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+5)),
        dict(id="sw_ronin",     label="Ronin",
             desc="Worn kimono, single katana. Wanderer without a master.",
             perk="+ 5 Stealth  (silent footsteps)",
             colour=(160,140,100), sprite="🌙",
             apply=lambda p: setattr(p,"stealth",p.stealth+5)),
    ],

    "Mage": [
        dict(id="mg_arcane",    label="Arcane Scholar",
             desc="Ink-stained robes, towering hat. Knowledge above all.",
             perk="+ 10 MP  (deep reserves)",
             colour=(120,80,220), sprite="✦",
             apply=lambda p: (setattr(p,"max_mp",p.max_mp+10),setattr(p,"mp",min(p.mp+10,p.max_mp)))),
        dict(id="mg_witch",     label="Hex Witch",
             desc="Dark cloak, cursed staff. Magic from forbidden texts.",
             perk="+ 6 ATK  (cursed power)",
             colour=(160,40,160), sprite="🌑",
             apply=lambda p: setattr(p,"atk",p.atk+6)),
        dict(id="mg_elemental", label="Elemental",
             desc="Shifting aura of fire and ice. Nature bends to your will.",
             perk="+ 15 HP  (elemental body)",
             colour=(60,200,200), sprite="⚡",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+15),setattr(p,"hp",min(p.hp+15,p.max_hp)))),
        dict(id="mg_oracle",    label="Oracle",
             desc="White robes, third eye. You see futures others cannot.",
             perk="+ 6% Crit  (foresight)",
             colour=(240,200,255), sprite="👁",
             apply=lambda p: setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+6)),
    ],

    "Rogue": [
        dict(id="rg_shadow",    label="Shadow",
             desc="All black, face wrapped. You exist only in rumour.",
             perk="+ 8 Stealth  (unseen presence)",
             colour=(80,60,120), sprite="🌑",
             apply=lambda p: setattr(p,"stealth",p.stealth+8)),
        dict(id="rg_pirate",    label="Sea Rogue",
             desc="Tricorn hat, cutlass. Sail fast, strike faster.",
             perk="+ 5 ATK  (sea-hardened blade)",
             colour=(60,160,200), sprite="⚓",
             apply=lambda p: setattr(p,"atk",p.atk+5)),
        dict(id="rg_phantom",   label="Phantom Thief",
             desc="Mask and monocle. You steal hearts — and everything else.",
             perk="+ 20 Gold per kill  (pickpocket instinct)",
             colour=(200,60,100), sprite="🎭",
             apply=lambda p: setattr(p,"_gold_bonus_kill",getattr(p,"_gold_bonus_kill",0)+20)),
        dict(id="rg_assassin",  label="Assassin",
             desc="Hooded, twin daggers. One shot. No witnesses.",
             perk="+ 8% Crit  (vital point strikes)",
             colour=(180,40,40), sprite="🗡",
             apply=lambda p: setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+8)),
    ],

    "Tank": [
        dict(id="tk_guardian",  label="Guardian",
             desc="Full plate, tower shield. Nothing gets past you.",
             perk="+ 5 DEF  (fortress stance)",
             colour=(140,160,200), sprite="🛡",
             apply=lambda p: setattr(p,"defense",p.defense+5)),
        dict(id="tk_warlord",   label="Warlord",
             desc="Horned helmet, massive axe. War is your element.",
             perk="+ 20 HP + 3 ATK  (warlord's build)",
             colour=(180,60,40), sprite="⚔",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+20),setattr(p,"hp",min(p.hp+20,p.max_hp)),setattr(p,"atk",p.atk+3))),
        dict(id="tk_golem",     label="Iron Golem",
             desc="Fused with metal. Barely human — entirely unstoppable.",
             perk="+ 30 HP  (iron constitution)",
             colour=(100,110,120), sprite="⚙",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+30),setattr(p,"hp",min(p.hp+30,p.max_hp)))),
        dict(id="tk_paladin",   label="Paladin",
             desc="Holy armour, blessed sword. Protect the weak, punish evil.",
             perk="+ 4 DEF + 5 HP  (divine aegis)",
             colour=(255,240,140), sprite="✝",
             apply=lambda p: (setattr(p,"defense",p.defense+4),setattr(p,"max_hp",p.max_hp+5),setattr(p,"hp",min(p.hp+5,p.max_hp)))),
    ],

    "Healer": [
        dict(id="hl_cleric",    label="Cleric",
             desc="Holy robes, divine staff. Light guides every step.",
             perk="+ 8 MP  (prayer reserves)",
             colour=(255,240,180), sprite="✝",
             apply=lambda p: (setattr(p,"max_mp",p.max_mp+8),setattr(p,"mp",min(p.mp+8,p.max_mp)))),
        dict(id="hl_herbalist", label="Herbalist",
             desc="Forest garb, healing pouch. Nature is the best medicine.",
             perk="Potions heal +15 HP extra",
             colour=(80,180,80), sprite="🌿",
             apply=lambda p: setattr(p,"_potion_bonus",getattr(p,"_potion_bonus",0)+15)),
        dict(id="hl_shaman",    label="Shaman",
             desc="Tribal paint, spirit mask. You commune with ancient forces.",
             perk="+ 20 HP + 6 MP  (spirit bond)",
             colour=(200,120,60), sprite="🔮",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+20),setattr(p,"hp",min(p.hp+20,p.max_hp)),setattr(p,"max_mp",p.max_mp+6),setattr(p,"mp",min(p.mp+6,p.max_mp)))),
        dict(id="hl_angel",     label="Fallen Angel",
             desc="Tattered wings, halo. Descended to heal what mortals broke.",
             perk="+ 6% Crit + 5 MP  (divine wrath)",
             colour=(220,200,255), sprite="👼",
             apply=lambda p: (setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+6),setattr(p,"max_mp",p.max_mp+5),setattr(p,"mp",min(p.mp+5,p.max_mp)))),
    ],

    "Blade Master": [
        dict(id="bm_dragon",    label="Dragon Slayer",
             desc="Scales embedded in armour. You've faced the worst.",
             perk="+ 6 ATK  (dragonbone edge)",
             colour=(200,80,40), sprite="🐉",
             apply=lambda p: setattr(p,"atk",p.atk+6)),
        dict(id="bm_wind",      label="Wind Dancer",
             desc="Silk sash, fluid movement. Your blade is faster than sight.",
             perk="+ 6 Stealth + 4% Crit  (flowing form)",
             colour=(200,240,255), sprite="💨",
             apply=lambda p: (setattr(p,"stealth",p.stealth+6),setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+4))),
        dict(id="bm_oni",       label="Oni Warrior",
             desc="Demonic mask, twin blades. Your fury is beyond human.",
             perk="+ 25 HP + 4 ATK  (demon blood)",
             colour=(160,40,60), sprite="👹",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+25),setattr(p,"hp",min(p.hp+25,p.max_hp)),setattr(p,"atk",p.atk+4))),
        dict(id="bm_void",      label="Void Blade",
             desc="Blade that absorbs light. Strikes from between dimensions.",
             perk="+ 8 DEF + 4 ATK  (void armour)",
             colour=(60,40,100), sprite="⬛",
             apply=lambda p: (setattr(p,"defense",p.defense+8),setattr(p,"atk",p.atk+4))),
    ],

    "Archmage": [
        dict(id="am_cosmic",    label="Cosmic Mage",
             desc="Stars orbit you. The universe is your spellbook.",
             perk="+ 20 MP  (infinite cosmos)",
             colour=(60,40,180), sprite="🌌",
             apply=lambda p: (setattr(p,"max_mp",p.max_mp+20),setattr(p,"mp",min(p.mp+20,p.max_mp)))),
        dict(id="am_lich",      label="Lich Lord",
             desc="Undead frame, soul gem. Death only made you stronger.",
             perk="+ 10 ATK + 10 MP  (undying power)",
             colour=(100,200,120), sprite="💀",
             apply=lambda p: (setattr(p,"atk",p.atk+10),setattr(p,"max_mp",p.max_mp+10),setattr(p,"mp",min(p.mp+10,p.max_mp)))),
        dict(id="am_storm",     label="Storm Caller",
             desc="Lightning crackles around you. Clouds follow your steps.",
             perk="+ 8 ATK  (charged strikes)",
             colour=(240,240,80), sprite="⚡",
             apply=lambda p: setattr(p,"atk",p.atk+8)),
        dict(id="am_dragonmage",label="Dragon Mage",
             desc="Dragonscale robes, draconic runes. You speak the language of fire.",
             perk="+ 30 HP + 8 MP  (draconic vitality)",
             colour=(220,100,40), sprite="🔥",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+30),setattr(p,"hp",min(p.hp+30,p.max_hp)),setattr(p,"max_mp",p.max_mp+8),setattr(p,"mp",min(p.mp+8,p.max_mp)))),
    ],

    "Shadow Assassin": [
        dict(id="sa_wraith",    label="Wraith",
             desc="Formless, soundless. Witnesses forget your face by dawn.",
             perk="+ 12 Stealth  (ghost walk)",
             colour=(80,60,120), sprite="👻",
             apply=lambda p: setattr(p,"stealth",p.stealth+12)),
        dict(id="sa_spider",    label="Spider",
             desc="Web traps, venom fangs. Patience is your deadliest weapon.",
             perk="+ 10% Crit  (venomous patience)",
             colour=(80,160,80), sprite="🕷",
             apply=lambda p: setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+10)),
        dict(id="sa_demon",     label="Demon Blade",
             desc="Cursed twin blades, corrupted eyes. Evil chose you.",
             perk="+ 10 ATK  (demonic edge)",
             colour=(180,20,20), sprite="😈",
             apply=lambda p: setattr(p,"atk",p.atk+10)),
        dict(id="sa_night",     label="Nightfall",
             desc="Dark cloak that absorbs moonlight. Born in the shadows.",
             perk="+ 8 Stealth + 6% Crit  (night hunter)",
             colour=(20,20,60), sprite="🌙",
             apply=lambda p: (setattr(p,"stealth",p.stealth+8),setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+6))),
    ],

    "War Titan": [
        dict(id="wt_colossus",  label="Colossus",
             desc="Mountain-sized presence. Enemies flee before you swing.",
             perk="+ 40 HP  (titan blood)",
             colour=(120,100,80), sprite="🗿",
             apply=lambda p: (setattr(p,"max_hp",p.max_hp+40),setattr(p,"hp",min(p.hp+40,p.max_hp)))),
        dict(id="wt_volcanic",  label="Volcanic",
             desc="Lava-forged armour, ember eyes. Destruction incarnate.",
             perk="+ 12 ATK + 10 HP  (magma core)",
             colour=(220,80,20), sprite="🌋",
             apply=lambda p: (setattr(p,"atk",p.atk+12),setattr(p,"max_hp",p.max_hp+10),setattr(p,"hp",min(p.hp+10,p.max_hp)))),
        dict(id="wt_ancient",   label="Ancient Titan",
             desc="Runic armour older than kingdoms. History walks with you.",
             perk="+ 8 DEF + 20 HP  (ancient fortitude)",
             colour=(160,140,100), sprite="⚱",
             apply=lambda p: (setattr(p,"defense",p.defense+8),setattr(p,"max_hp",p.max_hp+20),setattr(p,"hp",min(p.hp+20,p.max_hp)))),
        dict(id="wt_thunder",   label="Thunder King",
             desc="Storm-wreathed armour, hammer that calls lightning.",
             perk="+ 10 ATK + 6 DEF  (stormborn might)",
             colour=(180,180,255), sprite="⚡",
             apply=lambda p: (setattr(p,"atk",p.atk+10),setattr(p,"defense",p.defense+6))),
    ],

    "Arch Priest": [
        dict(id="ap_seraph",    label="Seraph",
             desc="Six wings, blinding light. You are the divine made flesh.",
             perk="+ 15 MP + 10 HP  (celestial grace)",
             colour=(255,255,200), sprite="👼",
             apply=lambda p: (setattr(p,"max_mp",p.max_mp+15),setattr(p,"mp",min(p.mp+15,p.max_mp)),setattr(p,"max_hp",p.max_hp+10),setattr(p,"hp",min(p.hp+10,p.max_hp)))),
        dict(id="ap_blood",     label="Blood Saint",
             desc="Red vestments, thorned staff. Sacrifice fuels the miracle.",
             perk="+ 10 ATK + 8 MP  (sacrifice power)",
             colour=(180,20,40), sprite="🩸",
             apply=lambda p: (setattr(p,"atk",p.atk+10),setattr(p,"max_mp",p.max_mp+8),setattr(p,"mp",min(p.mp+8,p.max_mp)))),
        dict(id="ap_nature",    label="Nature Sage",
             desc="Living vines for armour. The forest heals through you.",
             perk="Potions heal +20 HP extra + 8 MP  (nature's gift)",
             colour=(60,180,80), sprite="🌳",
             apply=lambda p: (setattr(p,"_potion_bonus",getattr(p,"_potion_bonus",0)+20),setattr(p,"max_mp",p.max_mp+8),setattr(p,"mp",min(p.mp+8,p.max_mp)))),
        dict(id="ap_void",      label="Void Priest",
             desc="Black halo, empty eyes. You healed so many — death owes you.",
             perk="+ 10% Crit + 10 MP  (void blessing)",
             colour=(100,60,160), sprite="⬛",
             apply=lambda p: (setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+10),setattr(p,"max_mp",p.max_mp+10),setattr(p,"mp",min(p.mp+10,p.max_mp)))),
    ],
}



# ══════════════════════════════════════════════════════════════════
# LEGENDARY SKINS — unlocked via special difficult quests
# Each job has 1 golden legendary skin + a hard quest to unlock it
# ══════════════════════════════════════════════════════════════════

LEGENDARY_QUESTS = {
    "Swordsman": dict(
        quest_id   = "lq_swordsman",
        title      = "Blade of Legend",
        desc       = "Slay 20 Armored Knights AND defeat the Goblin King boss.",
        steps      = [
            {"type":"kill", "target":"Armored Knight", "required":20, "progress":0,
             "label":"Armored Knights slain"},
            {"type":"kill", "target":"Goblin King",    "required":1,  "progress":0,
             "label":"Goblin King defeated"},
        ],
        reward_gold = 2000, reward_exp = 5000,
    ),
    "Mage": dict(
        quest_id   = "lq_mage",
        title      = "Grand Arcanum",
        desc       = "Defeat 15 Shadow Beasts AND slay the Shadow Lord boss.",
        steps      = [
            {"type":"kill","target":"Shadow Beast","required":15,"progress":0,
             "label":"Shadow Beasts destroyed"},
            {"type":"kill","target":"Shadow Lord", "required":1, "progress":0,
             "label":"Shadow Lord slain"},
        ],
        reward_gold = 2000, reward_exp = 5000,
    ),
    "Rogue": dict(
        quest_id   = "lq_rogue",
        title      = "Phantom of the World",
        desc       = "Kill 20 Frost Wraiths AND defeat the Frost Dragon.",
        steps      = [
            {"type":"kill","target":"Frost Wraith","required":20,"progress":0,
             "label":"Frost Wraiths eliminated"},
            {"type":"kill","target":"Frost Dragon","required":1, "progress":0,
             "label":"Frost Dragon slain"},
        ],
        reward_gold = 2000, reward_exp = 5000,
    ),
    "Tank": dict(
        quest_id   = "lq_tank",
        title      = "Immovable Fortress",
        desc       = "Survive 10 battles taking 0 damage AND defeat any boss.",
        steps      = [
            {"type":"no_damage_battle","target":"","required":10,"progress":0,
             "label":"No-damage battles survived"},
            {"type":"kill_boss",       "target":"",  "required":1, "progress":0,
             "label":"Boss defeated"},
        ],
        reward_gold = 2000, reward_exp = 5000,
    ),
    "Healer": dict(
        quest_id   = "lq_healer",
        title      = "Saint of the Realm",
        desc       = "Fully heal yourself 25 times AND complete 10 guild quests.",
        steps      = [
            {"type":"full_heal",  "target":"","required":25,"progress":0,
             "label":"Full heals performed"},
            {"type":"guild_quest","target":"","required":10,"progress":0,
             "label":"Guild quests completed"},
        ],
        reward_gold = 2000, reward_exp = 5000,
    ),
    "Blade Master": dict(
        quest_id   = "lq_blademaster",
        title      = "Sword Saint",
        desc       = "Land 50 critical hits AND defeat Vaeltharion the Dragon.",
        steps      = [
            {"type":"crit_hit","target":"","required":50,"progress":0,
             "label":"Critical hits landed"},
            {"type":"kill",    "target":"Dragon","required":1,"progress":0,
             "label":"Vaeltharion slain"},
        ],
        reward_gold = 3000, reward_exp = 8000,
    ),
    "Archmage": dict(
        quest_id   = "lq_archmage",
        title      = "Archmage Supreme",
        desc       = "Cast 40 skills AND defeat Vaeltharion the Dragon.",
        steps      = [
            {"type":"skill_cast","target":"","required":40,"progress":0,
             "label":"Skills cast"},
            {"type":"kill",     "target":"Dragon","required":1,"progress":0,
             "label":"Vaeltharion slain"},
        ],
        reward_gold = 3000, reward_exp = 8000,
    ),
    "Shadow Assassin": dict(
        quest_id   = "lq_shadow_assassin",
        title      = "Death's Herald",
        desc       = "Perform 30 stealth kills AND defeat the Shadow Lord.",
        steps      = [
            {"type":"stealth_kill","target":"","required":30,"progress":0,
             "label":"Stealth kills"},
            {"type":"kill",        "target":"Shadow Lord","required":1,"progress":0,
             "label":"Shadow Lord slain"},
        ],
        reward_gold = 3000, reward_exp = 8000,
    ),
    "War Titan": dict(
        quest_id   = "lq_war_titan",
        title      = "Titan of Ages",
        desc       = "Take 5000 total damage (show your endurance) AND defeat the Goblin King.",
        steps      = [
            {"type":"damage_taken","target":"","required":5000,"progress":0,
             "label":"Total damage tanked"},
            {"type":"kill","target":"Goblin King","required":1,"progress":0,
             "label":"Goblin King crushed"},
        ],
        reward_gold = 3000, reward_exp = 8000,
    ),
    "Arch Priest": dict(
        quest_id   = "lq_arch_priest",
        title      = "Divine Incarnate",
        desc       = "Restore 10000 total HP through healing AND defeat Vaeltharion.",
        steps      = [
            {"type":"hp_healed","target":"","required":10000,"progress":0,
             "label":"Total HP restored"},
            {"type":"kill","target":"Dragon","required":1,"progress":0,
             "label":"Vaeltharion slain"},
        ],
        reward_gold = 3000, reward_exp = 8000,
    ),
}

# Golden legendary skin per job — unlocked after quest completion
LEGENDARY_SKINS = {
    "Swordsman": dict(
        id="lskin_swordsman", label="⭐ Legend of the Blade",
        desc="Radiant golden armour. Songs are sung of your victories.",
        perk="+ 8 ATK + 5 DEF + 5% Crit  (legendary might)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+8),
            setattr(p,"defense",p.defense+5),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+5),
        ),
    ),
    "Mage": dict(
        id="lskin_mage", label="⭐ Arcane Sovereign",
        desc="Golden robes etched with every spell known to mankind.",
        perk="+ 10 ATK + 20 MP + 6% Crit  (sovereign power)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+10),
            setattr(p,"max_mp",p.max_mp+20),
            setattr(p,"mp",min(p.mp+20,p.max_mp)),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+6),
        ),
    ),
    "Rogue": dict(
        id="lskin_rogue", label="⭐ Phantom King",
        desc="A shadow that gleams gold. The most feared name in every city.",
        perk="+ 10 ATK + 12 Stealth + 8% Crit  (phantom legend)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+10),
            setattr(p,"stealth",p.stealth+12),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+8),
        ),
    ),
    "Tank": dict(
        id="lskin_tank", label="⭐ Eternal Bulwark",
        desc="Golden fortress armour. The world breaks before you do.",
        perk="+ 10 DEF + 50 HP + 5 ATK  (eternal endurance)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"defense",p.defense+10),
            setattr(p,"max_hp",p.max_hp+50),
            setattr(p,"hp",min(p.hp+50,p.max_hp)),
            setattr(p,"atk",p.atk+5),
        ),
    ),
    "Healer": dict(
        id="lskin_healer", label="⭐ Holy Incarnate",
        desc="Golden vestments that radiate warmth. Death itself hesitates.",
        perk="Potions+30 HP + 20 MP + 5% Crit  (divine presence)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"_potion_bonus",getattr(p,"_potion_bonus",0)+30),
            setattr(p,"max_mp",p.max_mp+20),
            setattr(p,"mp",min(p.mp+20,p.max_mp)),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+5),
        ),
    ),
    "Blade Master": dict(
        id="lskin_blademaster", label="⭐ Sword Saint",
        desc="A golden katana that hums with legend. None can match your edge.",
        perk="+ 14 ATK + 8% Crit + 8 Stealth  (saint's edge)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+14),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+8),
            setattr(p,"stealth",p.stealth+8),
        ),
    ),
    "Archmage": dict(
        id="lskin_archmage", label="⭐ Supreme Archmage",
        desc="Star-gold robes. The laws of magic bend for you alone.",
        perk="+ 14 ATK + 30 MP + 8% Crit  (supreme mastery)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+14),
            setattr(p,"max_mp",p.max_mp+30),
            setattr(p,"mp",min(p.mp+30,p.max_mp)),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+8),
        ),
    ),
    "Shadow Assassin": dict(
        id="lskin_shadow_assassin", label="⭐ Death's Herald",
        desc="A golden mask in absolute darkness. You are the end of things.",
        perk="+ 14 ATK + 15 Stealth + 10% Crit  (herald's curse)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+14),
            setattr(p,"stealth",p.stealth+15),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+10),
        ),
    ),
    "War Titan": dict(
        id="lskin_war_titan", label="⭐ Titan of Ages",
        desc="Golden titan armour forged in the heart of a volcano.",
        perk="+ 12 ATK + 12 DEF + 60 HP  (age of titans)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"atk",p.atk+12),
            setattr(p,"defense",p.defense+12),
            setattr(p,"max_hp",p.max_hp+60),
            setattr(p,"hp",min(p.hp+60,p.max_hp)),
        ),
    ),
    "Arch Priest": dict(
        id="lskin_arch_priest", label="⭐ Divine Incarnate",
        desc="Golden wings, blinding halo. You are a living miracle.",
        perk="Potions+25 HP + 25 MP + 10% Crit  (miracle of god)",
        colour=(255,215,0), sprite="👑",
        apply=lambda p: (
            setattr(p,"_potion_bonus",getattr(p,"_potion_bonus",0)+25),
            setattr(p,"max_mp",p.max_mp+25),
            setattr(p,"mp",min(p.mp+25,p.max_mp)),
            setattr(p,"_crit_bonus_custom",getattr(p,"_crit_bonus_custom",0)+10),
        ),
    ),
}


def get_legendary_skin(job_name: str) -> dict | None:
    return LEGENDARY_SKINS.get(job_name)


def get_legendary_quest(job_name: str) -> dict | None:
    return LEGENDARY_QUESTS.get(job_name)


def is_legendary_unlocked(player) -> bool:
    job = player.job.name
    q   = get_legendary_quest(job)
    if not q:
        return False
    return q["quest_id"] in getattr(player,"completed_quests",[])


def legendary_quest_active(player) -> dict | None:
    """Return the active legendary quest dict if running, else None."""
    return getattr(player,"_legendary_quest",None)


def start_legendary_quest(player) -> str:
    job = player.job.name
    qdef = get_legendary_quest(job)
    if not qdef:
        return "No legendary quest available for your class."
    if is_legendary_unlocked(player):
        return "Legendary skin already unlocked!"
    if legendary_quest_active(player):
        return "Already on this quest."
    import copy
    player._legendary_quest = copy.deepcopy(qdef)
    return f"Quest started: {qdef['title']}"


def tick_legendary_quest(player, event_type: str, value: int = 1):
    """
    Call this whenever a relevant event happens.
    event_type: kill, crit_hit, skill_cast, stealth_kill,
                no_damage_battle, kill_boss, full_heal,
                guild_quest, damage_taken, hp_healed
    value: amount to add (usually 1, damage_taken/hp_healed use actual numbers)
    """
    lq = legendary_quest_active(player)
    if not lq:
        return False

    changed = False
    for step in lq.get("steps", []):
        if step.get("progress", 0) >= step.get("required", 1):
            continue
        if step["type"] == event_type:
            # for kill steps also match target
            if event_type == "kill" and step["target"] and step["target"] != value:
                continue
            step["progress"] = min(step["progress"] + (1 if event_type != "damage_taken" and event_type != "hp_healed" else value),
                                   step["required"])
            changed = True

    if changed:
        _check_legendary_complete(player)
    return changed


def _check_legendary_complete(player):
    lq = getattr(player, "_legendary_quest", None)
    if not lq:
        return
    all_done = all(s["progress"] >= s["required"] for s in lq.get("steps",[]))
    if not all_done:
        return

    # Complete!
    from game_term import C, clr
    clr()
    _GLD = "\033[38;2;255;215;0m"; _B = "\033[1m"; _R = "\033[0m"
    _GRN = "\033[38;2;80;200;80m"; _WHT = "\033[38;2;255;255;255m"
    print(C(f"\n{_GLD}{_B}╔══════════════════════════════════════════════════╗"))
    print(C(f"║  ★  LEGENDARY QUEST COMPLETE!                    ║"))
    print(C(f"╚══════════════════════════════════════════════════╝{_R}\n"))
    print(C(f"  {_GLD}{_B}{lq['title']}{_R}"))
    print(C(f"  {_GRN}+{lq['reward_gold']} gold   +{lq['reward_exp']} EXP{_R}\n"))

    # Rewards
    player.gold += lq["reward_gold"]
    # Add EXP quietly (no UI level-up screen mid-quest-completion)
    player.exp += lq["reward_exp"]
    while player.exp >= player.exp_to_next:
        player.exp -= player.exp_to_next
        player.level += 1
        player.max_hp += 10; player.hp = min(player.hp + 10, player.max_hp)
        player.atk    += 1
        player.exp_to_next = int(player.exp_to_next * 1.4)

    # Trophy
    trophy_name = f"★ {lq['title']} Trophy"
    if hasattr(player, "bases"):
        for base in player.bases.bases.values():
            base.trophies.append({"name": trophy_name, "desc": lq["title"]})
            break

    # Unlock golden skin
    skin = get_legendary_skin(player.job.name)
    if skin:
        print(C(f"  {_GLD}{_B}GOLDEN SKIN UNLOCKED: {skin['label']}{_R}"))
        print(C(f"  {_GLD}{skin['sprite']}  {skin['perk']}{_R}\n"))

    player.completed_quests.append(lq["quest_id"])
    player._legendary_quest = None
    input(C(f"  \033[38;2;100;100;100m(Press Enter){_R}"))


def _fallback_styles(job_name):
    j = job_name[:2].lower()
    return [
        dict(id=f"{j}_a",label="Wanderer",desc=f"A weathered {job_name} without fixed allegiance.",perk="+ 5 Stealth",colour=(150,150,150),sprite="?",apply=lambda p:setattr(p,"stealth",p.stealth+5)),
        dict(id=f"{j}_b",label="Elite",   desc=f"Elite {job_name} trained by the royal guard.",   perk="+ 4 ATK",colour=(200,200,100),sprite="★",apply=lambda p:setattr(p,"atk",p.atk+4)),
        dict(id=f"{j}_c",label="Veteran", desc=f"Scarred veteran {job_name} who has seen too much.",perk="+ 10 HP",colour=(160,120,80),sprite="⚔",apply=lambda p:(setattr(p,"max_hp",p.max_hp+10),setattr(p,"hp",min(p.hp+10,p.max_hp)))),
        dict(id=f"{j}_d",label="Mystic",  desc=f"A {job_name} touched by an unknown power.",       perk="+ 6 MP",colour=(120,80,200),sprite="✦",apply=lambda p:(setattr(p,"max_mp",p.max_mp+6),setattr(p,"mp",min(p.mp+6,p.max_mp)))),
    ]


def get_styles(job_name: str) -> list:
    return STYLE_DEFS.get(job_name, _fallback_styles(job_name))


# ── Perk apply/revert ─────────────────────────────────────────────

def _snapshot(player) -> dict:
    return {a: getattr(player,a,0) for a in
            ["atk","defense","stealth","max_hp","max_mp",
             "_crit_bonus_custom","_gold_bonus_kill","_potion_bonus"]}

def revert_style(player):
    delta = getattr(player,"_custom_perk_delta",{})
    for attr, change in delta.items():
        setattr(player, attr, getattr(player,attr,0) - change)
    if hasattr(player,"max_hp"): player.hp = min(player.hp, player.max_hp)
    if hasattr(player,"max_mp"): player.mp = min(player.mp, player.max_mp)

def apply_style(player, style: dict):
    before = _snapshot(player)
    style["apply"](player)
    after  = _snapshot(player)
    player._custom_style_id     = style["id"]
    player._custom_style_label  = style["label"]
    player._custom_style_colour = style["colour"]
    player._custom_sprite_tag   = style.get("sprite","")
    player._custom_perk_delta   = {k:after[k]-before[k] for k in before if after[k]!=before[k]}


# ── Colour swatch ─────────────────────────────────────────────────
def _sw(rgb):
    r,g,b=rgb
    return f"\033[38;2;{r};{g};{b}m██{_R}"


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    return lines


def open_customise(player):
    """Style browser: big live preview of your hero in each style."""
    from game_art import render_sprite, sprite_width
    job_name = player.job.name
    styles   = list(get_styles(job_name))
    lskin    = get_legendary_skin(job_name)
    lquest   = get_legendary_quest(job_name)
    options  = styles + ([lskin] if lskin else [])
    current  = getattr(player, "_custom_style_id", None)
    sel      = next((i for i, s in enumerate(options) if s["id"] == current), 0)
    msg      = ""

    while True:
        unlocked  = is_legendary_unlocked(player)
        active_lq = legendary_quest_active(player)
        s         = options[sel]
        is_leg    = s["id"].startswith("lskin_")
        locked    = is_leg and not unlocked

        clr()
        print(C(f"\n{_GOLD}{_B}══════════════  🎨 CHARACTER CUSTOMISATION  ══════════════{_R}"))
        cur_lbl = getattr(player, "_custom_style_label", None) or "Default"
        print(C(f"{_WHITE}{_B}{player.name}{_R} {_DIM}the{_R} {_CYAN}{job_name}{_R}   "
                f"{_DIM}wearing:{_R} {_GOLD}{cur_lbl}{_R}"))
        print()

        # ── Big preview + details side by side ──────────────────
        art = render_sprite(job_name, accent=s["colour"], legendary=is_leg)
        aw  = sprite_width(job_name)
        head_col = _GOLD if is_leg else _WHITE
        tag = (f"{_RED}[LOCKED]{_R}" if locked else
               f"{_GREEN}✓ wearing{_R}" if s["id"] == current else "")
        info = [
            f"{_DIM}{sel+1}/{len(options)}{_R}  {_sw(s['colour'])}  {head_col}{_B}{s['label']}{_R}  {tag}",
            "",
        ]
        info += [f"{_DIM}{l}{_R}" for l in _wrap(s["desc"], 40)]
        info += ["", f"{_YELL}Perk:{_R} {_GREEN}{s['perk']}{_R}"]
        if locked and lquest:
            info += ["", f"{_ORAN}Unlock: {lquest['title']}{_R}"]
            info += [f"{_DIM}{l}{_R}" for l in _wrap(lquest["desc"], 40)]
            if active_lq:
                for st in active_lq.get("steps", []):
                    done = st["progress"] >= st["required"]
                    info.append(f"{_GREEN if done else _ORAN}{'✓' if done else '•'} "
                                f"{st['label']}: {st['progress']}/{st['required']}{_R}")
        h = max(len(art), len(info))
        art = art + [" " * aw] * (h - len(art))
        for i in range(h):
            right = info[i] if i < len(info) else ""
            print(C("  " + art[i] + "    " + right))

        # ── All styles at a glance ──────────────────────────────
        print()
        chips = []
        for i, o in enumerate(options):
            mark = "▶" if i == sel else " "
            name = o["label"].replace("⭐ ", "★ ")
            if o["id"].startswith("lskin_") and not unlocked:
                name += " (locked)"
            tick = f"{_GREEN}✓{_R}" if o["id"] == current else " "
            chips.append(f"{_GOLD}{mark}{_R}{_GOLD}[{i+1}]{_R} {_sw(o['colour'])} {name}{tick}")
        for i in range(0, len(chips), 3):
            print(C("   ".join(chips[i:i+3])))
        print()
        if msg:
            print(C(msg)); msg = ""
        keys = (f"{_GOLD}[A]{_R}/{_GOLD}[D]{_R} browse   {_GOLD}[Enter]{_R} wear this style   "
                f"{_GOLD}[1-{len(options)}]{_R} jump")
        if lskin and not unlocked and not active_lq:
            keys += f"   {_GOLD}[Q]{_R} start legendary quest"
        keys += f"   {_GOLD}[0]{_R} back"
        print(C(keys))
        ch = input(C(f"{_GOLD}>{_R} ")).strip().lower()

        if ch in ("0", "b", "x"):
            return
        if ch in ("a", "<", "4a"):
            sel = (sel - 1) % len(options); continue
        if ch in ("d", ">"):
            sel = (sel + 1) % len(options); continue
        if ch.isdigit() and 1 <= int(ch) <= len(options):
            sel = int(ch) - 1; continue
        if ch == "q" and lskin and not unlocked and not active_lq:
            msg = f"{_ORAN}{start_legendary_quest(player)}{_R}  {_DIM}(progress shows here and in the [J] journal){_R}"
            continue
        if ch in ("", "y", "e", "w"):
            if locked:
                msg = f"{_RED}Locked — complete the legendary quest '{lquest['title'] if lquest else '?'}' first.{_R}"
                continue
            if s["id"] == current:
                msg = f"{_DIM}You're already wearing {s['label']}.{_R}"
                continue
            revert_style(player)
            apply_style(player, s)
            current = s["id"]
            pre = f"{_GOLD}★" if is_leg else f"{_GREEN}✓"
            msg = f"{pre}{_B} Now wearing {s['label']}!{_R}  {_YELL}Perk active:{_R} {_GREEN}{s['perk']}{_R}"
