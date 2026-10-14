import random, copy

def _C(text=""):
    try:
        from game_term import C
        return C(text)
    except ImportError:
        return text

# ═══════════════════════════════════════════════════════════════
# STATUS EFFECTS
# ═══════════════════════════════════════════════════════════════

class StatusEffect:
    def __init__(self, name, duration):
        self.name = name; self.duration = duration
    def on_turn_start(self, target): pass
    def on_turn_end(self, target): self.duration -= 1
    def is_active(self): return self.duration > 0
    def __repr__(self): return f"{self.name}({self.duration})"
    def to_dict(self): return {"type": self.__class__.__name__, "duration": self.duration}

class Poison(StatusEffect):
    def __init__(self, duration=3, damage=5):
        super().__init__("Poison", duration); self.damage = damage
    def on_turn_start(self, target):
        target.hp = max(0, target.hp - self.damage)
        print(_C(f"[X] {target.name} takes {self.damage} poison damage!"))
    def to_dict(self): return {"type":"Poison","duration":self.duration,"damage":self.damage}

class Burn(StatusEffect):
    def __init__(self, duration=3, damage=4):
        super().__init__("Burn", duration); self.damage = damage
    def on_turn_start(self, target):
        target.hp = max(0, target.hp - self.damage)
        print(_C(f"[~] {target.name} burns for {self.damage} damage!"))
    def to_dict(self): return {"type":"Burn","duration":self.duration,"damage":self.damage}

class Regen(StatusEffect):
    def __init__(self, duration=3, heal=6):
        super().__init__("Regen", duration); self.heal = heal
    def on_turn_start(self, target):
        old = target.hp; target.hp = min(target.max_hp, target.hp + self.heal)
        if target.hp > old:
            print(_C(f"[+] {target.name} regenerates {target.hp - old} HP!"))
    def to_dict(self): return {"type":"Regen","duration":self.duration,"heal":self.heal}

class Stun(StatusEffect):
    def __init__(self, duration=1): super().__init__("Stun", duration)
    def to_dict(self): return {"type":"Stun","duration":self.duration}

def status_from_dict(d):
    t = d["type"]
    if t=="Poison": return Poison(d["duration"],d.get("damage",5))
    if t=="Burn":   return Burn(d["duration"],d.get("damage",4))
    if t=="Regen":  return Regen(d["duration"],d.get("heal",6))
    if t=="Stun":   return Stun(d["duration"])
    return StatusEffect(t,d["duration"])


# ═══════════════════════════════════════════════════════════════
# SKILLS
# ═══════════════════════════════════════════════════════════════

class Skill:
    def __init__(self, name, damage=0, heal=0, mana_cost=0,
                 status_effect=None, status_chance=0, description="",
                 heal_ally=False):
        self.name=name; self.damage=damage; self.heal=heal
        self.mana_cost=mana_cost; self.status_effect=status_effect
        self.status_chance=status_chance; self.description=description
        self.heal_ally = heal_ally   # True = healer will use this on party members

    def pay_cost(self, user):
        if user.mp >= self.mana_cost:
            user.mp -= self.mana_cost
        else:
            # Force-cast: the missing MP is paid with HP, but it can never
            # kill the caster (that used to be a silent suicide button).
            overflow = self.mana_cost - user.mp
            user.mp = 0; user.hp = max(1, user.hp - overflow)
            print(_C(f"[!] {user.name} force-casts {self.name}, burning {overflow} HP!"))

    def can_use(self, user):
        """MP is enough, or HP can cover the shortfall and still leave 1 HP."""
        return user.mp >= self.mana_cost or user.hp > (self.mana_cost - user.mp)

    def use(self, user, target=None):
        if not self.can_use(user):
            print(_C(f"Not enough MP (or HP) to use {self.name}!")); return False
        self.pay_cost(user)
        if self.damage > 0 and target:
            if target.try_dodge():
                print(_C(f"{target.name} dodged {self.name}!")); return True
            power = user.job.skill_power_bonus
            if hasattr(user, "party_skill_power"):
                power += user.party_skill_power()
            atk = user.combat_atk() if hasattr(user, "combat_atk") else user.atk
            base = self.damage + atk + power
            crit, dmg = user.calc_crit(base)
            dealt = target.take_damage(dmg)
            tag = " [CRIT!]" if crit else ""
            print(_C(f"(*) {user.name} used {self.name}{tag} → {dealt} damage!"))
            if crit:
                try:
                    from game_customise import tick_legendary_quest as _tlq
                    _tlq(user, "crit_hit")
                except Exception: pass
            if self.status_effect and random.randint(1,100) <= self.status_chance:
                target.add_status(copy.deepcopy(self.status_effect))
        elif self.heal > 0:
            amount = self.heal + user.job.heal_power_bonus
            if hasattr(user, "heal_power_extra"):
                amount += user.heal_power_extra()
            old = user.hp; user.hp = min(user.max_hp, user.hp + amount)
            healed = user.hp - old
            print(_C(f"(+) {user.name} used {self.name} → healed {healed} HP!"))
            if self.status_effect and random.randint(1,100) <= self.status_chance:
                user.add_status(copy.deepcopy(self.status_effect))
            try:
                from game_customise import tick_legendary_quest as _tlq
                _tlq(user,"hp_healed",healed)
                if user.hp >= user.max_hp: _tlq(user,"full_heal")
            except Exception: pass
        elif self.status_effect:
            # Pure buff skills (Battle Cry, Taunt) — apply to self.
            # These used to do nothing at all except cost MP.
            if random.randint(1,100) <= self.status_chance:
                user.add_status(copy.deepcopy(self.status_effect))
            print(_C(f"(+) {user.name} used {self.name}!"))
        return True

    def __repr__(self):
        base = f"DMG {self.damage}" if self.damage else f"HEAL {self.heal}" if self.heal else "?"
        fx = f" +{self.status_effect.name}({self.status_chance}%)" if self.status_effect else ""
        return f"{self.name} [{base}{fx}] MP:{self.mana_cost}"


# ═══════════════════════════════════════════════════════════════
# INVENTORY — STACKED ITEMS
# ═══════════════════════════════════════════════════════════════

INVENTORY_LIMIT = 30    # max distinct stacks in bag
STORAGE_LIMIT   = 80    # guild storage slots
MAX_STACK       = 64    # max items per stack for stackable types

STACKABLE_TYPES = {"heal", "mana", "god", "material", "bomb", "antidote", "buff", "key"}


class ItemStack:
    """Wraps an Item with a quantity for inventory display/logic."""
    def __init__(self, item, qty=1):
        self.item = item
        self.qty  = max(1, int(qty))

    @property
    def name(self): return self.item.name
    @property
    def item_type(self): return self.item.item_type
    @property
    def sell_value(self): return self.item.sell_value
    @property
    def value(self): return self.item.value

    def is_stackable(self):
        return self.item.item_type in STACKABLE_TYPES

    def total_sell(self):
        return self.sell_value * self.qty

    def use(self, player, in_combat=False):
        result = self.item.use(player, in_combat)
        if result:
            self.qty -= 1
        return result

    def to_dict(self):
        return {"stack": True, "item": self.item.to_dict(), "qty": self.qty}

    @staticmethod
    def from_dict(d):
        item = item_from_dict(d["item"])
        return ItemStack(item, d.get("qty", 1))

    def __repr__(self):
        if self.qty > 1:
            return f"{self.item.name} x{self.qty}"
        return self.item.name


# ═══════════════════════════════════════════════════════════════
# RARITY & ELEMENT COLOURS
# ═══════════════════════════════════════════════════════════════

def _fg(r, g, b): return f"\033[38;2;{r};{g};{b}m"

RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
RARITY_RGB = {
    "common":    (200, 200, 205),   # grey / white
    "uncommon":  (80, 220, 80),     # green
    "rare":      (70, 140, 240),    # blue
    "epic":      (185, 95, 245),    # purple
    "legendary": (255, 150, 30),    # orange-gold
}
RARITY_LABEL = {r: r.capitalize() for r in RARITIES}

ELEMENTS = ("fire", "ice", "shadow", "holy", "poison", "arcane",
            "storm", "water", "earth", "blood")
ELEMENT_RGB = {
    "fire":   (240, 85, 50),
    "ice":    (120, 225, 255),
    "shadow": (160, 90, 225),
    "holy":   (255, 220, 100),
    "poison": (110, 225, 90),
    "arcane": (205, 125, 255),
    "storm":  (250, 240, 120),
    "water":  (70, 170, 240),
    "earth":  (190, 150, 95),
    "blood":  (210, 45, 70),
}


def rarity_colour(rarity):
    """24-bit ANSI colour for a rarity name (unknown -> common)."""
    return _fg(*RARITY_RGB.get(rarity, RARITY_RGB["common"]))


def rarity_rank(rarity):
    return RARITIES.index(rarity) if rarity in RARITIES else 0


def element_colour(element):
    rgb = ELEMENT_RGB.get(element)
    return _fg(*rgb) if rgb else ""


# Extra (non core-stat) bonuses gear may carry. Keys are Player attributes
# that the game already reads: crit chance, potion strength, gold per kill.
EXTRA_STATS = {
    "_crit_bonus_custom": "CRIT",
    "_potion_bonus":      "POT",
    "_gold_bonus_kill":   "GOLD",
}

# Consumable effects beyond item.value, keyed by item name.
#   mp:      extra MP restored by a heal item      heal: extra HP for mana items
#   regen:   (turns, hp_per_turn)                  cure: statuses removed
#   turns:   buff duration                         hp_cost: fraction of max HP paid
CONSUMABLE_FX = {
    "Tincture":    {"mp": 25},
    "Hero's Brew": {"mp": 50},
    "Regen Tonic": {"regen": (3, 10)},
    "Holy Water":  {"cure": ("Poison", "Burn", "Stun")},
}

# Bombs/scrolls that end the battle instead of dealing damage.
ESCAPE_ITEMS = {"Smoke Bomb", "Escape Scroll", "Sandveil Powder"}
# Status a thrown bomb may inflict: name -> (status, chance%)
BOMB_STATUS = {}


def bomb_status(name, level=1):
    """(StatusEffect or None, chance%) a thrown bomb inflicts. Default: Burn 40%."""
    kind, chance = BOMB_STATUS.get(name, ("burn", 40))
    lv = max(1, int(level or 1))
    if kind == "burn":   return Burn(duration=2, damage=5 + lv), chance
    if kind == "poison": return Poison(duration=3, damage=4 + lv), chance
    if kind == "stun":   return Stun(duration=1), chance
    return None, 0


class Item:
    # Kept for backwards compatibility (now lives in CONSUMABLE_FX)
    COMBO_MP = {"Tincture": 25, "Hero's Brew": 50}

    def __init__(self, name, item_type, value=0, sell_value=0):
        self.name=name; self.item_type=item_type
        self.value=value; self.sell_value=sell_value or max(1,value//2)
        info = _info(name)
        self.rarity = info.get("rarity", "common")
        self.description = info.get("desc", "")

    def rarity_col(self):
        return rarity_colour(getattr(self, "rarity", "common"))

    def use(self, player, in_combat=False):
        fx = CONSUMABLE_FX.get(self.name, {})
        if self.item_type == "heal":
            amount = self.value + getattr(player, "_potion_bonus", 0)
            old=player.hp; player.hp=min(player.max_hp,player.hp+amount)
            msg = f"Used {self.name}: restored {player.hp-old} HP"
            extra_mp = fx.get("mp", 0)
            if extra_mp:
                oldm = player.mp; player.mp = min(player.max_mp, player.mp + extra_mp)
                msg += f" and {player.mp-oldm} MP"
            if fx.get("regen"):
                t, h = fx["regen"]
                player.add_status(Regen(duration=t, heal=h))
                msg += f", regenerating {h} HP for {t} turns"
            cured = self._cure(player, fx.get("cure", ()))
            if cured:
                msg += f", cured {', '.join(cured)}"
            print(_C(msg + ".")); return True
        if self.item_type == "mana":
            old=player.mp; player.mp=min(player.max_mp,player.mp+self.value)
            msg = f"Used {self.name}: restored {player.mp-old} MP"
            if fx.get("heal"):
                oldh = player.hp; player.hp = min(player.max_hp, player.hp + fx["heal"])
                msg += f" and {player.hp-oldh} HP"
            print(_C(msg + ".")); return True
        if self.item_type == "god":
            print(_C(f"{self.name} activates automatically at 0 HP!")); return False
        if self.item_type == "antidote":
            bad = fx.get("cure", ("Poison", "Burn"))
            cured = self._cure(player, bad)
            healed = 0
            if fx.get("heal"):
                oldh = player.hp; player.hp = min(player.max_hp, player.hp + fx["heal"])
                healed = player.hp - oldh
            if not cured and not healed:
                print(_C(f"You have no ailments that {self.name} can cure.")); return False
            parts = []
            if cured:  parts.append(f"cured {', '.join(cured)}")
            if healed: parts.append(f"restored {healed} HP")
            print(_C(f"Used {self.name}: {' and '.join(parts)}.")); return True
        if self.item_type == "bomb":
            if not in_combat:
                print(_C(f"{self.name} can only be used in battle.")); return False
            # Actual effect is applied by the combat engine
            print(_C(f"Threw {self.name}!")); return True
        if self.item_type == "buff":
            turns = fx.get("turns", 3)
            cost = int(player.max_hp * fx.get("hp_cost", 0))
            if cost and player.hp <= cost:
                print(_C(f"You are too weak to survive {self.name} right now.")); return False
            # Refresh rather than stack (drinking five used to give ATK+50)
            cur = getattr(player,"temp_atk_buff",0) if getattr(player,"temp_atk_turns",0) > 0 else 0
            player.temp_atk_buff  = max(cur, self.value)
            player.temp_atk_turns = max(getattr(player,"temp_atk_turns",0), turns)
            msg = f"Used {self.name}: ATK+{self.value} for {turns} turns"
            if cost:
                player.hp -= cost
                msg += f" (it burns: -{cost} HP)"
            print(_C(msg + "!")); return True
        if self.item_type == "key":
            print(_C(f"{self.name} is a key item. Keep it safe.")); return False
        print(_C("Can't use that here.")); return False

    @staticmethod
    def _cure(player, names):
        if not names:
            return []
        cured = [s for s in player.status_effects if s.name in names]
        for s in cured:
            player.status_effects.remove(s)
        return [s.name for s in cured]

    def to_dict(self):
        return {"cls":"Item","name":self.name,"item_type":self.item_type,
                "value":self.value,"sell_value":self.sell_value}

    @staticmethod
    def from_dict(d):
        return Item(d["name"],d["item_type"],d.get("value",0),d.get("sell_value",0))

    def __repr__(self): return self.name


class Equipment(Item):
    """Wearable gear with stat bonuses.

    Optional extras (all saved only when set, so old saves load unchanged):
      base       name of the base item an affixed item was rolled from
      affixes    [{"id": affix_id, "tier": 1-3}]  — stats are already baked in
      item_level level the item was generated for
      extra      {player_attr: amount} for crit / potion / gold bonuses
      power      named power text of a legendary unique
      set_name   gear-set membership (display only)
      icon       explicit icon key for game_icons
      element    explicit element (otherwise taken from the first affix)
    """
    VALID_SLOTS = ("weapon","armor","helmet","shield","cloak","ring","amulet")

    def __init__(self, name, slot, hp_bonus=0, atk_bonus=0, mp_bonus=0,
                 def_bonus=0, sell_value=0, stealth_bonus=0,
                 allowed_classes=None, rarity="common", description="",
                 base=None, affixes=None, item_level=0, extra=None,
                 power=None, set_name=None, icon=None, element=None):
        super().__init__(name,"equipment",sell_value=sell_value)
        self.slot=slot; self.hp_bonus=hp_bonus; self.atk_bonus=atk_bonus
        self.mp_bonus=mp_bonus; self.def_bonus=def_bonus
        self.stealth_bonus=stealth_bonus
        self.allowed_classes = allowed_classes
        self.rarity = rarity
        self.description = description or self.description
        self.base = base
        self.affixes = list(affixes) if affixes else []
        self.item_level = int(item_level or 0)
        self.extra = {k: int(v) for k, v in (extra or {}).items()
                      if k in EXTRA_STATS and v}
        self.power = power
        self.set_name = set_name
        self.icon = icon
        self._element = element

    @property
    def element(self):
        if self._element:
            return self._element
        for a in self.affixes:
            el = AFFIXES.get(a.get("id"), {}).get("element") if isinstance(a, dict) else None
            if el:
                return el
        return _info(self.base or self.name).get("element")

    def base_name(self):
        return self.base or self.name

    def can_equip(self, player_class):
        if self.allowed_classes is None: return True
        return player_class in self.allowed_classes

    def stat_pairs(self):
        """[(label, value)] of every non-zero bonus, core stats first."""
        p = [("HP", self.hp_bonus), ("ATK", self.atk_bonus), ("MP", self.mp_bonus),
             ("DEF", self.def_bonus), ("STL", self.stealth_bonus)]
        p = [(k, v) for k, v in p if v]
        for attr, label in EXTRA_STATS.items():
            v = self.extra.get(attr, 0) if self.extra else 0
            if v:
                p.append((label, v))
        return p

    def stat_line(self):
        p = []
        for k, v in self.stat_pairs():
            suf = "%" if k == "CRIT" else ""
            p.append(f"{k}{v:+d}{suf}")
        return ", ".join(p) if p else "no bonuses"

    def rarity_col(self):
        return rarity_colour(self.rarity)

    def to_dict(self):
        d = {"cls":"Equipment","name":self.name,"slot":self.slot,
             "hp_bonus":self.hp_bonus,"atk_bonus":self.atk_bonus,
             "mp_bonus":self.mp_bonus,"def_bonus":self.def_bonus,
             "stealth_bonus":self.stealth_bonus,"sell_value":self.sell_value,
             "allowed_classes":self.allowed_classes,"rarity":self.rarity,
             "description":self.description}
        if self.base:        d["base"] = self.base
        if self.affixes:     d["affixes"] = [dict(a) for a in self.affixes]
        if self.item_level:  d["ilvl"] = self.item_level
        if self.extra:       d["extra"] = dict(self.extra)
        if self.power:       d["power"] = self.power
        if self.set_name:    d["set"] = self.set_name
        if self.icon:        d["icon"] = self.icon
        if self._element:    d["element"] = self._element
        return d

    @staticmethod
    def fix_slot(name, slot):
        """Old workshop recipes produced an 'accessory' slot that can't be
        equipped (and vanished on reload). Map it to a real slot."""
        if slot in Equipment.VALID_SLOTS:
            return slot
        n = name.lower()
        if "crown" in n or "helm" in n: return "helmet"
        if "cloak" in n:                return "cloak"
        if "shield" in n:               return "shield"
        if any(k in n for k in ("amulet", "orb", "compass", "pendant")): return "amulet"
        return "ring"

    @staticmethod
    def from_dict(d):
        affixes = [a for a in (d.get("affixes") or []) if isinstance(a, dict) and "id" in a]
        rarity = d.get("rarity", "common")
        if rarity not in RARITIES:
            rarity = "common"
        return Equipment(d["name"],Equipment.fix_slot(d["name"], d.get("slot","ring")),
                         d.get("hp_bonus",0),
                         d.get("atk_bonus",0),d.get("mp_bonus",0),
                         d.get("def_bonus",0),d.get("sell_value",0),
                         d.get("stealth_bonus",0),
                         d.get("allowed_classes"),rarity,
                         d.get("description",""),
                         base=d.get("base"), affixes=affixes,
                         item_level=d.get("ilvl", 0), extra=d.get("extra"),
                         power=d.get("power"), set_name=d.get("set"),
                         icon=d.get("icon"), element=d.get("element"))

    def __repr__(self):
        return f"{self.name} [{self.slot}] ({self.stat_line()})"


def item_from_dict(d):
    if d.get("stack"):  return ItemStack.from_dict(d)
    if d.get("cls") == "Equipment": return Equipment.from_dict(d)
    return Item.from_dict(d)

# ═══════════════════════════════════════════════════════════════
# INVENTORY HELPERS — stacking logic
# ═══════════════════════════════════════════════════════════════

def inventory_add(inventory, item):
    """
    Add item to inventory. Stacks stackable items up to MAX_STACK.
    Returns True on success, False if bag is full and item won't stack.
    item can be a plain Item/Equipment or an ItemStack.
    """
    # Unwrap qty if already a stack
    if isinstance(item, ItemStack):
        raw, qty = item.item, item.qty
    else:
        raw, qty = item, 1

    if raw.item_type in STACKABLE_TYPES:
        # All-or-nothing: a partial add used to return False after merging
        # some of the qty, which duplicated items on a failed storage withdraw.
        room = sum(MAX_STACK - s.qty for s in inventory
                   if isinstance(s, ItemStack) and s.item.name == raw.name)
        room += max(0, INVENTORY_LIMIT - len(inventory)) * MAX_STACK
        if room < qty:
            return False
        # Try to add to existing stack
        for stack in inventory:
            if isinstance(stack, ItemStack) and stack.item.name == raw.name and stack.qty < MAX_STACK:
                can_add = min(qty, MAX_STACK - stack.qty)
                stack.qty += can_add
                qty -= can_add
                if qty <= 0:
                    return True
        # Remaining qty goes into new stacks
        while qty > 0:
            if len(inventory) >= INVENTORY_LIMIT:
                return False
            batch = min(qty, MAX_STACK)
            inventory.append(ItemStack(raw, batch))
            qty -= batch
        return True
    else:
        # Equipment — one per slot
        if len(inventory) >= INVENTORY_LIMIT:
            return False
        inventory.append(item)
        return True


def inventory_remove(inventory, index, qty=1):
    """Remove qty from stack at index. Returns removed item or None."""
    if not (0 <= index < len(inventory)):
        return None
    entry = inventory[index]
    if isinstance(entry, ItemStack):
        take = min(qty, entry.qty)
        entry.qty -= take
        removed = ItemStack(entry.item, take)
        if entry.qty <= 0:
            inventory.pop(index)
        return removed
    else:
        return inventory.pop(index)


def entry_qty(entry):
    """Quantity represented by one inventory entry (stack or single item)."""
    return entry.qty if isinstance(entry, ItemStack) else 1


def entry_item(entry):
    """The underlying Item/Equipment of an inventory entry."""
    return entry.item if isinstance(entry, ItemStack) else entry


def item_count(inventory, name):
    """Total quantity of a named item across all stacks."""
    return sum(entry_qty(e) for e in inventory if e.name == name)


def material_counts(inventory):
    """{material_name: total_qty} — stack-aware."""
    counts = {}
    for e in inventory:
        if e.item_type == "material":
            counts[e.name] = counts.get(e.name, 0) + entry_qty(e)
    return counts


def remove_items(inventory, name, qty):
    """Remove qty of a named item (across stacks). Returns how many were removed."""
    removed = 0
    i = 0
    while i < len(inventory) and removed < qty:
        e = inventory[i]
        if e.name != name:
            i += 1; continue
        if isinstance(e, ItemStack):
            take = min(e.qty, qty - removed)
            e.qty -= take; removed += take
            if e.qty <= 0:
                inventory.pop(i); continue
        else:
            inventory.pop(i); removed += 1; continue
        i += 1
    return removed


def use_entry(inventory, index, player, in_combat=False):
    """Use ONE item from the entry at index. Removes empty stacks. Returns bool."""
    if not (0 <= index < len(inventory)):
        return False
    e = inventory[index]
    ok = e.use(player, in_combat)
    if ok and (not isinstance(e, ItemStack) or e.qty <= 0):
        inventory.remove(e)
    return ok


def sell_all_materials(inventory, player, mult=1.0):
    """Sell all material-type stacks. Returns total gold earned."""
    total = 0
    to_remove = []
    for i, entry in enumerate(inventory):
        if entry.item_type == "material":
            total += int(entry_item(entry).sell_value * mult) * entry_qty(entry)
            to_remove.append(i)
    for i in reversed(to_remove):
        inventory.pop(i)
    player.gold += total
    return total


def sell_all_consumables(inventory, player, mult=1.0):
    """Sell all consumable stacks. Returns total gold earned."""
    total = 0
    to_remove = []
    consumable_types = {"heal","mana","antidote","bomb","buff"}
    for i, entry in enumerate(inventory):
        if entry.item_type in consumable_types:
            total += int(entry_item(entry).sell_value * mult) * entry_qty(entry)
            to_remove.append(i)
    for i in reversed(to_remove):
        inventory.pop(i)
    player.gold += total
    return total


# ═══════════════════════════════════════════════════════════════
# GUILD STORAGE
# ═══════════════════════════════════════════════════════════════

class GuildStorage:
    DEPOSIT_FEE = 5

    def __init__(self):
        self.items = []

    def deposit(self, item, player):
        if len(self.items) >= STORAGE_LIMIT:
            return False, "Storage is full!"
        if player.gold < self.DEPOSIT_FEE:
            return False, f"Need {self.DEPOSIT_FEE}g deposit fee."
        player.gold -= self.DEPOSIT_FEE
        self.items.append(item)
        return True, f"Deposited {item.name} (-{self.DEPOSIT_FEE}g fee)"

    def withdraw(self, idx, player):
        if not (0 <= idx < len(self.items)):
            return False, "Invalid slot."
        item = self.items.pop(idx)
        ok = inventory_add(player.inventory, item)
        if not ok:
            self.items.insert(idx, item)
            return False, "Your bag is full!"
        return True, f"Withdrew {item.name}"

    def to_dict(self):
        return {"items": [it.to_dict() if hasattr(it,'to_dict') else it.item.to_dict() for it in self.items]}

    @classmethod
    def from_dict(cls, d):
        gs = cls()
        gs.items = [item_from_dict(i) for i in d.get("items",[])]
        return gs

# ═══════════════════════════════════════════════════════════════
# ITEM CATALOGUE
#
#   ITEM_POOL    everyday items: safe for random chests / NPC gifts
#   SET_POOL     epic continent / kingdom gear sets
#   UNIQUE_POOL  legendary uniques with named powers
#   KEY_ITEMS    quest & key items (never sold, never random)
#   ITEM_INFO    name -> {rarity, desc, cat, icon, lvl, region, element}
#
# Every pool maps name -> zero-argument factory, so ITEM_POOL[name]()
# keeps working exactly as before. make_item(name) searches all of them.
# ═══════════════════════════════════════════════════════════════

ITEM_POOL   = {}
SET_POOL    = {}
UNIQUE_POOL = {}
KEY_ITEMS   = {}
ITEM_INFO   = {}

ALL_POOLS = (ITEM_POOL, SET_POOL, UNIQUE_POOL, KEY_ITEMS)

# Class groups
WAR  = ["Swordsman", "Tank", "Blade Master", "War Titan"]
SWD  = ["Swordsman", "Blade Master"]
TNK  = ["Tank", "War Titan"]
MAG  = ["Mage", "Archmage"]
HEA  = ["Healer", "Arch Priest"]
CAST = ["Mage", "Healer", "Archmage", "Arch Priest"]
ROG  = ["Rogue", "Shadow Assassin"]
RNG  = ["Rogue", "Shadow Assassin", "Swordsman", "Blade Master"]
HOLY = ["Tank", "Healer", "War Titan", "Arch Priest"]


def _info(name):
    """Catalogue metadata for an item name ({} when unknown)."""
    return ITEM_INFO.get(name, {}) if "ITEM_INFO" in globals() else {}


def _lvl_from_sell(sell):
    return max(1, min(40, int(round(sell / 12.0))))


def _con(name, typ, value, sell, desc, rarity="common", icon=None, fx=None,
         pool=None, region=None, bomb=None, element=None):
    """Register a consumable / material / key item."""
    pool = ITEM_POOL if pool is None else pool
    def factory(n=name, t=typ, v=value, s=sell):
        return Item(n, t, v, s)
    pool[name] = factory
    cat = {"heal": "potion", "mana": "potion", "god": "potion", "antidote": "potion",
           "buff": "food", "bomb": "bomb", "material": "material",
           "key": "key"}.get(typ, typ)
    ITEM_INFO[name] = {"rarity": rarity, "desc": desc, "cat": cat, "type": typ,
                       "icon": icon, "lvl": _lvl_from_sell(sell), "region": region,
                       "element": element}
    if fx:
        CONSUMABLE_FX[name] = fx
    if bomb:
        BOMB_STATUS[name] = bomb


def _gear(name, slot, rarity, desc="", classes=None, icon=None, pool=None,
          hp=0, atk=0, mp=0, df=0, stl=0, sell=10, extra=None, power=None,
          set_name=None, element=None, region=None):
    """Register an Equipment base."""
    pool = ITEM_POOL if pool is None else pool
    cls = list(classes) if classes else None
    ex = dict(extra) if extra else None
    def factory():
        return Equipment(name, slot, hp_bonus=hp, atk_bonus=atk, mp_bonus=mp,
                         def_bonus=df, sell_value=sell, stealth_bonus=stl,
                         allowed_classes=list(cls) if cls else None,
                         rarity=rarity, description=desc,
                         extra=dict(ex) if ex else None, power=power,
                         set_name=set_name, icon=icon, element=element)
    pool[name] = factory
    ITEM_INFO[name] = {"rarity": rarity, "desc": desc, "cat": slot, "type": "equipment",
                       "icon": icon, "lvl": _lvl_from_sell(sell), "region": region,
                       "element": element, "slot": slot, "set": set_name}


# ── Healing ──────────────────────────────────────────────────────
_con("Potion",          "heal",  40,   5, "A cork-stoppered vial of red tonic. Restores 40 HP.")
_con("Hi-Potion",       "heal",  80,  15, "A stronger red draught. Restores 80 HP.")
_con("Full Potion",     "heal", 200,  50, "Thick crimson syrup that knits deep wounds.", "uncommon")
_con("Mega Potion",     "heal", 400, 120, "Alchemist-grade healing for veteran adventurers.", "rare")
_con("Elixir of Life",  "heal", 999, 350, "Liquid sunrise. Heals any wound completely.", "epic", icon="elixir")
_con("Regen Tonic",     "heal",  60,  20, "Heals 60 HP, then keeps healing for 3 turns.", "uncommon")
_con("Bandage",         "heal",  25,   3, "Clean linen strips. Restores 25 HP.", icon="bandage")
_con("Traveller's Bread","heal", 30,   4, "Dense road bread. Restores 30 HP.", icon="food")
_con("Honeycake",       "heal",  45,   8, "Aelorian honeycake: 45 HP plus gentle regeneration.",
     fx={"regen": (2, 6)}, icon="food", region="AELORIA")
_con("Herbal Poultice", "heal",  60,  14, "Silverleaf paste. Restores 60 HP and draws out poison.",
     "uncommon", fx={"cure": ("Poison",)}, icon="herb", region="AELORIA")
_con("Roast Boar Haunch","heal", 90,  22, "Smoky, greasy and glorious. Restores 90 HP.",
     "uncommon", icon="food")
_con("Coconut Water",   "heal",  50,  10, "Sweet island water: 50 HP and 10 MP.",
     fx={"mp": 10}, icon="tea", region="SOUTH ISLES")
_con("Sunspire Mint Tea","heal", 70,  20, "Desert mint tea, poured from a height: 70 HP, 30 MP.",
     "uncommon", fx={"mp": 30}, icon="tea", region="ASH SANDS")
_con("Frostheim Mead",  "heal", 120,  35, "Honey-dark mead. 120 HP and it thaws the bones.",
     "uncommon", fx={"cure": ("Stun",)}, icon="mead", region="FROSTHEIM")
_con("Troll Blood Draught","heal",150, 55, "Foul and green. 150 HP, then fierce regeneration.",
     "rare", fx={"regen": (3, 18)}, icon="potion_green")
_con("Royal Cordial",   "heal", 250,  90, "Valdmere court cordial: 250 HP and 60 MP.",
     "rare", fx={"mp": 60}, icon="elixir", region="VALDMERE")

# ── Mana ─────────────────────────────────────────────────────────
_con("Ether",           "mana",  25,   8, "Blue vapour in glass. Restores 25 MP.")
_con("Hi-Ether",        "mana",  50,  20, "Concentrated ether. Restores 50 MP.")
_con("Elixir",          "mana", 120,  60, "A mage's elixir. Restores 120 MP.", "uncommon", icon="potion_purple")
_con("Mega Ether",      "mana", 250, 130, "Shimmering mana distillate. Restores 250 MP.", "rare")
_con("Mana Crystal",    "mana", 500, 300, "A crystal you crush to flood your mind with power.", "epic", icon="gem")
_con("Moonwater",       "mana",  80,  25, "Water left under a full moon. 80 MP.", "uncommon", region="FROSTHEIM")
_con("Arcane Tea",      "mana",  60,  18, "Bitter sage tea of the dune scholars: 60 MP, 20 HP.",
     fx={"heal": 20}, icon="tea", region="ASH SANDS")
_con("Starlight Ether", "mana", 180,  95, "Ether distilled under starlight. 180 MP.", "rare")

# ── Combo / special ──────────────────────────────────────────────
_con("Tincture",        "heal",  50,  25, "Heals 50 HP and 25 MP.", "uncommon", icon="potion_purple")
_con("Hero's Brew",     "heal", 150,  80, "Heals 150 HP and 50 MP.", "rare", icon="elixir")
_con("God Potion",      "god",    5, 500, "Revives you automatically when you fall at 0 HP.",
     "legendary", icon="god")
_con("Antidote",        "antidote", 0, 10, "Cures poison and burns.")
_con("Holy Water",      "antidote", 0, 25, "Blessed water: cures poison, burn and stun.", "uncommon",
     icon="holy_water", element="holy")
_con("Smelling Salts",  "antidote", 0, 12, "A sharp sniff clears a stun.", fx={"cure": ("Stun",)},
     icon="potion_small")
_con("Panacea",         "antidote", 0, 70, "Cures every ailment and restores 80 HP.", "rare",
     fx={"cure": ("Poison", "Burn", "Stun"), "heal": 80}, icon="elixir", element="holy")

# ── Bombs & scrolls (thrown/used in battle) ──────────────────────
_con("Fire Bomb",       "bomb",   35, 18, "Clay pot of lamp oil. Damages and may burn.", element="fire")
_con("Smoke Bomb",      "bomb",    0, 20, "Vanish in a cloud of smoke: escape any normal fight.", icon="smoke")
_con("Frost Bomb",      "bomb",   45, 24, "Shatters into freezing shards.", "uncommon",
     bomb=("none", 0), element="ice")
_con("Venom Flask",     "bomb",   30, 20, "Bursts into toxic mist. Poisons often.", "uncommon",
     bomb=("poison", 70), element="poison")
_con("Thunder Flask",   "bomb",   60, 34, "Storm in a bottle. Heavy damage.", "rare",
     bomb=("none", 0), element="storm")
_con("Holy Grenade",    "bomb",   80, 45, "A reliquary packed with blessed powder.", "rare",
     bomb=("none", 0), element="holy")
_con("Hellfire Flask",  "bomb",  110, 60, "Duskthorn brimstone. Massive fire damage.", "epic",
     bomb=("burn", 80), element="fire", region="DUSKTHORN")
_con("Sand Bomb",       "bomb",   25, 14, "A sack of grit that blinds and stings.",
     bomb=("none", 0), region="ASH SANDS", element="earth")
_con("Escape Scroll",   "bomb",    0, 30, "Read aloud to be whisked out of a normal fight.",
     "uncommon", icon="scroll", element="arcane")
_con("Sandveil Powder", "bomb",    0, 26, "Desert powder that hides you in a whirl of sand.",
     "uncommon", icon="smoke", region="ASH SANDS")
_con("Scroll of Fireball","bomb", 70, 40, "Unleashes a single fireball.", "rare", icon="scroll",
     element="fire")
_con("Scroll of Lightning","bomb", 90, 52, "Calls down a lightning strike.", "rare",
     icon="scroll", bomb=("none", 0), element="storm")

# ── Buffs, foods & brews ─────────────────────────────────────────
_con("Strength Draught","buff",   10, 40, "ATK+10 for 3 turns.", "uncommon", icon="potion_red")
_con("Spiced Jerky",    "buff",    6, 10, "Chewy and fiery. ATK+6 for 3 turns.", icon="food")
_con("Tidecaller Grog", "buff",    8, 16, "Island rum with a kick. ATK+8 for 4 turns.",
     fx={"turns": 4}, icon="mead", region="SOUTH ISLES")
_con("Berserker Draught","buff",  15, 50, "ATK+15 for 3 turns.", "rare", icon="potion_red")
_con("Giant's Tonic",   "buff",   20, 70, "ATK+20 for 5 turns.", "rare", fx={"turns": 5}, icon="potion_red")
_con("Demon Brew",      "buff",   25, 45, "Smoking black brew. ATK+25 for 4 turns, costs 15% HP.",
     "epic", fx={"turns": 4, "hp_cost": 0.15}, icon="brew", element="fire", region="DUSKTHORN")
_con("Ashen Blood Wine","buff",   18, 38, "Duskthorn vintage. ATK+18 for 4 turns, costs 10% HP.",
     "rare", fx={"turns": 4, "hp_cost": 0.10}, icon="brew", element="blood", region="DUSKTHORN")

# ── Materials ────────────────────────────────────────────────────
for _n, _s, _d, _r, _ic, _reg in [
    # Classic drops
    ("Wolf Pelt",       20, "Thick grey fur from a forest wolf.",             "common",   "pelt", None),
    ("Bone Shard",      15, "A splinter of old bone.",                        "common",   "bone", None),
    ("Iron Ore",        25, "Rust-red ore, ready for the smelter.",           "common",   "ore",  None),
    ("Feather",         12, "A long flight feather.",                         "common",   "feather", None),
    ("Frost Crystal",   35, "Never melts, even in a forge.",                  "uncommon", "gem",  "FROSTHEIM"),
    ("Scale Fragment",  40, "A hard, glossy scale.",                          "uncommon", "scale", None),
    ("Dark Shard",      60, "A splinter of crystallised shadow.",             "uncommon", "gem",  None),
    ("Dragon Scale",   200, "Still warm. Nothing pierces it.",                "epic",     "scale", "IRONSPIRE"),
    ("Mana Stone",      45, "A pebble that hums with magic.",                 "uncommon", "gem",  None),
    ("Shadow Cloth",    55, "Cloth that drinks the light.",                   "uncommon", "cloth", None),
    ("Holy Relic",      80, "A saint's bone in a silver case.",               "rare",     "relic", None),
    ("Venom Fang",      30, "Still drips venom.",                             "common",   "fang", "ASH SANDS"),
    ("Runic Stone",     70, "Carved runes glow faintly.",                     "rare",     "rune", None),
    ("Phoenix Feather",150, "Warm to the touch and faintly glowing.",         "epic",     "feather", None),
    ("Obsidian Shard",  90, "Volcanic glass, razor sharp.",                   "rare",     "gem",  "IRONSPIRE"),
    # Generic
    ("Leather Strip",    6, "Tanned leather for straps and grips.",           "common",   "cloth", None),
    ("Linen Cloth",      6, "A bolt of plain linen.",                         "common",   "cloth", None),
    ("Gold Nugget",     60, "A lump of raw gold.",                            "uncommon", "ore",  None),
    ("Ruby",            90, "A blood-red gemstone.",                          "rare",     "gem",  None),
    ("Sapphire",        90, "A deep blue gemstone.",                          "rare",     "gem",  None),
    ("Emerald",         90, "A vivid green gemstone.",                        "rare",     "gem",  None),
    ("Ancient Coin",    30, "A coin from a forgotten kingdom.",               "uncommon", "coin", None),
    # Aeloria (forest)
    ("Oak Heartwood",   18, "The dense core of an old oak.",                  "common",   "wood", "AELORIA"),
    ("Silverleaf Herb", 12, "A healing herb with silver-veined leaves.",      "common",   "herb", "AELORIA"),
    ("Ranger's Twine",  10, "Waxed bowstring twine.",                         "common",   "cloth", "AELORIA"),
    ("Boar Hide",       22, "Tough bristled hide.",                           "common",   "pelt", "AELORIA"),
    ("Amber Resin",     40, "Golden resin with something trapped inside.",    "uncommon", "gem",  "AELORIA"),
    # Ironspire (mountains)
    ("Mithril Ore",     95, "Light as tin, hard as steel.",                   "rare",     "ore",  "IRONSPIRE"),
    ("Coal Lump",        8, "Forge fuel.",                                    "common",   "ore",  "IRONSPIRE"),
    ("Steel Ingot",     45, "A bar of good Ironspire steel.",                 "uncommon", "ingot","IRONSPIRE"),
    ("Forge Ember",     55, "An ember that never goes out.",                  "uncommon", "ember","IRONSPIRE"),
    ("Granite Core",    30, "The heart of a stone golem.",                    "common",   "ore",  "IRONSPIRE"),
    # Ash Sands (desert)
    ("Desert Glass",    28, "Lightning-fused sand.",                          "common",   "gem",  "ASH SANDS"),
    ("Sun Topaz",       85, "Holds the desert sun inside.",                   "rare",     "gem",  "ASH SANDS"),
    ("Scorpion Chitin", 32, "Light, hard plates of chitin.",                  "common",   "scale","ASH SANDS"),
    ("Djinn Dust",     110, "Glittering dust left by a djinn.",               "rare",     "dust", "ASH SANDS"),
    ("Silk Bolt",       40, "Fine Sunspire silk.",                            "uncommon", "cloth","ASH SANDS"),
    # Frostheim (snow)
    ("Mammoth Ivory",   75, "A great curved tusk.",                           "rare",     "bone", "FROSTHEIM"),
    ("Winter Pelt",     36, "White fur that sheds snow.",                     "uncommon", "pelt", "FROSTHEIM"),
    ("Rime Silver",     70, "Silver that frosts over in your hand.",          "rare",     "ingot","FROSTHEIM"),
    ("Yeti Fur",        48, "Shaggy, warm and smelly.",                       "uncommon", "pelt", "FROSTHEIM"),
    # South Isles (tropical)
    ("Pearl",           65, "A perfect lustrous pearl.",                      "uncommon", "pearl","SOUTH ISLES"),
    ("Coral Branch",    26, "Bright red coral.",                              "common",   "coral","SOUTH ISLES"),
    ("Sea Silk",        50, "Thread spun from shellfish.",                    "uncommon", "cloth","SOUTH ISLES"),
    ("Kraken Ink",      80, "Black ink that writes on water.",                "rare",     "ink",  "SOUTH ISLES"),
    ("Tide Shell",      18, "A shell that hums like the sea.",                "common",   "shell","SOUTH ISLES"),
    # Valdmere (royal) and Duskthorn (demonic)
    ("Lumeris Silver", 120, "Valdmere royal silver with a violet sheen.",     "epic",     "ingot","VALDMERE"),
    ("Violet Silk",     70, "Royal purple silk of Valdmere.",                 "rare",     "cloth","VALDMERE"),
    ("Demon Horn",      85, "A blackened, spiralled horn.",                   "rare",     "horn", "DUSKTHORN"),
    ("Brimstone",       35, "Yellow rock that smells of the pit.",            "uncommon", "ore",  "DUSKTHORN"),
    ("Hellforged Iron",110, "Iron quenched in demon blood.",                  "epic",     "ingot","DUSKTHORN"),
    ("Soul Ember",     140, "A trapped spark that whispers.",                 "epic",     "ember","DUSKTHORN"),
]:
    _con(_n, "material", 0, _s, _d, _r, icon=_ic, region=_reg)

# ── Key & quest items (never random, never sold) ─────────────────
for _n, _d, _r, _ic in [
    ("Rusty Key",            "Opens some long-forgotten lock.",                         "common",    "key"),
    ("Royal Signet",         "The seal of Valdmere's crown. Guards bow to it.",         "epic",      "ring_key"),
    ("Crown Shard",          "A fragment of the cursed Hollow Crown.",                  "epic",      "crown"),
    ("Sunspire Vault Key",   "A sun-shaped key to the Kasbah vault.",                   "rare",      "key"),
    ("Duskthorn Sigil",      "A burning sigil that opens the citadel gate.",            "epic",      "rune"),
    ("Ancient Map Fragment", "Part of a map to something buried.",                      "uncommon",  "scroll"),
    ("Sealed Letter",        "A letter under wax. It is not addressed to you.",         "common",    "scroll"),
    ("Thieves' Guild Token", "A clipped coin: proof of guild membership.",              "rare",      "coin"),
    ("Dragon Egg Shell",     "Fragment of a dragon egg, iridescent and warm.",          "legendary", "scale"),
]:
    _con(_n, "key", 0, 0, _d, _r, icon=_ic, pool=KEY_ITEMS)

# ── Weapons ──────────────────────────────────────────────────────
# Original game weapons (stats unchanged so old saves stay identical)
_gear("Iron Sword", "weapon", "common", "A plain, reliable soldier's sword.", atk=5, sell=40)
_gear("Steel Sword", "weapon", "uncommon", "Well-balanced Ironspire steel.", WAR, atk=9, sell=75)
_gear("Broad Sword", "weapon", "uncommon", "A wide blade that hits like a door.", WAR, atk=13, sell=120)
_gear("Dragon Sword", "weapon", "rare", "Forged around a dragon's tooth.", SWD, atk=22, sell=280, element="fire")
_gear("Runic Greatsword", "weapon", "rare", "Ancient runes run the length of the blade.", WAR,
      icon="greatsword", atk=18, df=5, sell=220, element="arcane")
_gear("Iron Staff", "weapon", "common", "An iron-shod focus staff.", CAST, atk=3, mp=15, sell=45)
_gear("Crystal Staff", "weapon", "uncommon", "Capped with a clear focusing crystal.", CAST, atk=5, mp=30, sell=90)
_gear("Arcane Rod", "weapon", "rare", "A rod humming with stored spells.", MAG, icon="wand", atk=8, mp=50,
      sell=160, element="arcane")
_gear("Void Staff", "weapon", "legendary", "Channels the void itself.", MAG, atk=12, mp=70, sell=240,
      element="shadow")
_gear("Short Sword", "weapon", "common", "Quick and quiet.", ROG, icon="dagger", atk=6, stl=2, sell=50)
_gear("Shadow Blade", "weapon", "uncommon", "Strikes from the dark.", ROG, icon="dagger", atk=11, stl=5,
      sell=100, element="shadow")
_gear("Assassin Dagger", "weapon", "rare", "Thin, black and patient.", ROG, atk=16, stl=8, sell=180)
_gear("Twin Fang Blades", "weapon", "legendary", "A matched pair of fang-curved knives.", ROG,
      icon="dagger", atk=20, stl=10, sell=260)
_gear("War Hammer", "weapon", "common", "A heavy hammer for heavy armour.", TNK, icon="hammer", atk=10, df=3, sell=80)
_gear("Tower Shield", "shield", "uncommon", "A wall you carry.", TNK, df=18, hp=30, sell=110)
_gear("Titan Axe", "weapon", "rare", "Only giants swing it one-handed.", TNK, icon="axe", atk=15, hp=20, sell=160)
_gear("Holy Mace", "weapon", "common", "A flanged mace blessed at the chapel.", HEA, icon="mace", atk=6, mp=10,
      sell=70, element="holy")
_gear("Angel's Sceptre", "weapon", "rare", "Its head is a gilded halo.", HEA, icon="mace", atk=4, mp=40, hp=20,
      sell=150, element="holy")
_gear("Sacred Tome", "weapon", "legendary", "Every page is a prayer.", HEA, icon="tome", atk=2, mp=55, hp=30,
      sell=200, element="holy")
_gear("Wolf Fang Blade", "weapon", "uncommon", "Savage blade from wolf remains.", atk=8, sell=60)
_gear("Frost Blade", "weapon", "rare", "Chills enemies on contact.", atk=12, sell=90, element="ice")
_gear("Bone Staff", "weapon", "uncommon", "Bone-carved focus for mages.", CAST, atk=4, mp=25, sell=70)
_gear("Venom Dagger", "weapon", "uncommon", "Poisons on every hit.", ROG, atk=9, stl=4, sell=80, element="poison")

# New weapons — swords & greatswords
_gear("Bronze Sword", "weapon", "common", "Soft bronze, sharpened often.", atk=4, sell=24)
_gear("Knight's Longsword", "weapon", "uncommon", "A knight's sidearm with a cross guard.", SWD, atk=11, sell=95)
_gear("Bastard Sword", "weapon", "uncommon", "Hand-and-a-half grip, all-day reach.", WAR, atk=12, hp=10, sell=110)
_gear("Silversteel Sword", "weapon", "rare", "Mirror-bright and frighteningly sharp.", SWD, atk=19, sell=230,
      extra={"_crit_bonus_custom": 3})
_gear("Iron Greatsword", "weapon", "common", "Two hands, one swing.", WAR, icon="greatsword", atk=9, sell=58)
_gear("Claymore", "weapon", "uncommon", "A highland greatsword.", WAR, icon="greatsword", atk=15, sell=140)
_gear("Executioner's Blade", "weapon", "rare", "Square-tipped and grim.", WAR, icon="greatsword", atk=24, df=-2,
      sell=270)
# Daggers
_gear("Rusty Dagger", "weapon", "common", "Better than bare hands. Barely.", ROG, icon="dagger", atk=4, stl=1, sell=18)
_gear("Stiletto", "weapon", "uncommon", "A needle for finding gaps in armour.", ROG, icon="dagger", atk=10, stl=4,
      sell=90, extra={"_crit_bonus_custom": 2})
_gear("Kris Knife", "weapon", "uncommon", "A wavy island blade.", ROG, icon="dagger", atk=12, stl=3, sell=105,
      region="SOUTH ISLES")
_gear("Nightfang Dirk", "weapon", "rare", "Its edge vanishes in the dark.", ROG, icon="dagger", atk=17, stl=9,
      sell=210, element="shadow")
# Bows
_gear("Hunting Bow", "weapon", "common", "Yew bow for game and goblins.", RNG, icon="bow", atk=6, stl=1, sell=42)
_gear("Longbow", "weapon", "uncommon", "Taller than its archer.", RNG, icon="bow", atk=11, stl=2, sell=100)
_gear("Elven Recurve", "weapon", "rare", "Silent, swift and beautifully curved.", RNG, icon="bow", atk=17, stl=5,
      sell=215, extra={"_crit_bonus_custom": 3})
# Staves & wands
_gear("Oak Staff", "weapon", "common", "A walking stick that remembers being a tree.", CAST, icon="staff",
      atk=2, mp=12, sell=30, region="AELORIA")
_gear("Ember Staff", "weapon", "uncommon", "Its tip smoulders.", MAG, icon="staff", atk=7, mp=28, sell=110,
      element="fire")
_gear("Glacier Staff", "weapon", "rare", "Rimed in permanent frost.", MAG, icon="staff", atk=10, mp=48, sell=200,
      element="ice")
_gear("Apprentice Wand", "weapon", "common", "Slightly scorched.", CAST, icon="wand", atk=3, mp=10, sell=28)
_gear("Spark Wand", "weapon", "uncommon", "Snaps and crackles.", MAG, icon="wand", atk=8, mp=20, sell=95,
      element="storm")
_gear("Wand of Embers", "weapon", "rare", "Flicks out darts of flame.", MAG, icon="wand", atk=13, mp=30, sell=190,
      element="fire")
# Maces, axes, hammers, spears, tomes
_gear("Flanged Mace", "weapon", "uncommon", "Steel flanges that crack shields.", HOLY, icon="mace", atk=10, mp=8,
      sell=90)
_gear("Morning Star", "weapon", "rare", "A spiked ball on a haft.", HOLY, icon="mace", atk=16, mp=12, sell=185)
_gear("Hand Axe", "weapon", "common", "A woodsman's axe.", WAR, icon="axe", atk=7, sell=35)
_gear("Battle Axe", "weapon", "uncommon", "Double-bitted and hungry.", WAR, icon="axe", atk=14, sell=125)
_gear("Maul", "weapon", "uncommon", "A sledgehammer for people.", TNK, icon="hammer", atk=15, df=4, sell=135)
_gear("Iron Spear", "weapon", "common", "Reach is safety.", WAR, icon="spear", atk=7, df=1, sell=38)
_gear("Halberd", "weapon", "uncommon", "Axe, spear and hook in one.", WAR, icon="spear", atk=13, df=3, sell=130)
_gear("Prayer Book", "weapon", "common", "Worn prayers in a leather cover.", HEA, icon="tome", atk=1, mp=18, hp=10,
      sell=36)
_gear("Grimoire of Ash", "weapon", "rare", "Burnt pages, burning spells.", MAG, icon="tome", atk=9, mp=55,
      sell=210, element="fire")

# ── Armour ───────────────────────────────────────────────────────
_gear("Leather Armor", "armor", "common", "Boiled leather. Better than a shirt.", hp=20, df=4, sell=20)
_gear("Chain Mail", "armor", "uncommon", "Thousands of riveted rings.", WAR, hp=35, df=8, sell=60)
_gear("Plate Armor", "armor", "rare", "Full plate for the front line.", TNK, hp=60, df=15, sell=130)
_gear("Dragon Scale Armor", "armor", "legendary", "Near-impervious to damage.", hp=80, df=22, sell=300,
      element="fire")
_gear("Obsidian Plate", "armor", "rare", "Volcanic glass in steel frames.", WAR, hp=70, df=18, sell=200)
_gear("Mage Robe", "armor", "common", "Robes with plenty of pockets.", CAST, icon="robe", hp=10, mp=40, sell=55)
_gear("Archmage Vestment", "armor", "rare", "Embroidered with spell diagrams.", MAG, icon="robe", hp=20, mp=70,
      sell=130)
_gear("Celestial Robe", "armor", "legendary", "Woven from the night sky.", MAG, icon="robe", hp=30, mp=90,
      sell=220, element="arcane")
_gear("Shadow Suit", "armor", "uncommon", "Matte black and silent.", ROG, hp=25, stl=6, sell=80)
_gear("Void Wraps", "armor", "rare", "Bindings that blur your outline.", ROG, hp=35, stl=10, sell=160,
      element="shadow")
_gear("Priest Vestment", "armor", "uncommon", "White and gold vestments.", HEA, icon="robe", hp=30, mp=25, sell=75)
_gear("Hunter Vest", "armor", "uncommon", "Hardened wolf leather.", hp=25, df=5, sell=50)
_gear("Obsidian Armor", "armor", "rare", "Forged from volcanic rock.", hp=65, df=16, sell=180)
_gear("Padded Tunic", "armor", "common", "Quilted cloth armour.", hp=12, df=2, sell=12)
_gear("Studded Leather", "armor", "uncommon", "Leather riveted with steel.", hp=28, df=6, stl=1, sell=65)
_gear("Brigandine", "armor", "uncommon", "Steel plates hidden under cloth.", WAR, hp=40, df=9, sell=95)
_gear("Knight's Plate", "armor", "rare", "Polished plate with a tabard.", WAR, hp=55, df=14, sell=170)
_gear("Apprentice Robe", "armor", "common", "Plain grey wool.", CAST, icon="robe", hp=6, mp=20, sell=18)
_gear("Silk Robe", "armor", "uncommon", "Light silk that channels mana.", CAST, icon="robe", hp=15, mp=50, sell=100)
_gear("Monk's Habit", "armor", "common", "Simple, humble, oddly comfortable.", HEA, icon="robe", hp=18, mp=15, sell=26)
_gear("Nightstalker Leathers", "armor", "rare", "Soft-soled and dyed with soot.", ROG, hp=40, stl=9, df=4, sell=175)

# ── Helmets ──────────────────────────────────────────────────────
_gear("Iron Helm", "helmet", "common", "A simple iron cap.", hp=10, df=3, sell=25)
_gear("Steel Helm", "helmet", "uncommon", "A visored steel helm.", WAR, hp=20, df=6, sell=55)
_gear("Mage Hood", "helmet", "common", "A deep hood that hides your eyes.", CAST, icon="hood", hp=5, mp=20, sell=40)
_gear("Rogue Hood", "helmet", "common", "Good for lurking.", ROG, icon="hood", stl=4, hp=8, sell=45)
_gear("Dragon Skull Helm", "helmet", "rare", "A dragon's skull, hollowed out.", hp=40, df=10, sell=180)
_gear("Leather Cap", "helmet", "common", "Keeps the rain off.", hp=6, df=1, sell=8)
_gear("Barbute", "helmet", "uncommon", "A T-visored helm.", WAR, hp=18, df=7, sell=70)
_gear("Horned Helm", "helmet", "uncommon", "Intimidating, and only slightly impractical.", hp=22, df=5, atk=2, sell=80)
_gear("Wizard Hat", "helmet", "common", "Pointy. Of course it's pointy.", CAST, icon="hat", mp=15, hp=3, sell=22)
_gear("Circlet of Focus", "helmet", "uncommon", "A thin silver band set with a moonstone.", CAST,
      icon="crown", mp=30, hp=8, sell=85)

# ── Shields ──────────────────────────────────────────────────────
_gear("Wooden Shield", "shield", "common", "Planks and a strap.", df=5, hp=5, sell=20)
_gear("Iron Shield", "shield", "common", "Dented but dependable.", df=10, hp=10, sell=50)
_gear("Steel Shield", "shield", "uncommon", "A steel heater shield.", df=14, hp=20, sell=90)
_gear("Holy Shield", "shield", "rare", "Blessed by divine power.", HOLY, df=12, hp=25, mp=10, sell=110, element="holy")
_gear("Mirror Shield", "shield", "rare", "Polished to show foes their own fear.", df=16, hp=15, sell=140)
_gear("Runic Shield", "shield", "rare", "Runic inscriptions absorb damage.", df=15, hp=20, mp=15, sell=130,
      element="arcane")
_gear("Buckler", "shield", "common", "A fist-sized parrying shield.", df=3, stl=1, sell=12)
_gear("Kite Shield", "shield", "uncommon", "Long and tapered, protects the legs.", df=12, hp=15, sell=80)
_gear("Spiked Shield", "shield", "rare", "Shield bash, but pointier.", TNK, df=14, atk=6, hp=15, sell=165)

# ── Cloaks ───────────────────────────────────────────────────────
_gear("Travel Cloak", "cloak", "common", "Mud-hemmed and well loved.", hp=8, stl=1, sell=15)
_gear("Shadow Cloak", "cloak", "uncommon", "Fades into shadows.", hp=15, mp=15, stl=6, sell=80, element="shadow")
_gear("Frost Cloak", "cloak", "uncommon", "Lined with white fur.", hp=30, mp=10, stl=2, sell=60, element="ice")
_gear("Mage Shroud", "cloak", "uncommon", "Woven with arcane thread.", MAG, mp=30, sell=70)
_gear("Phantom Shroud", "cloak", "legendary", "You can see the wall through it.", hp=20, mp=20, stl=12, sell=200,
      element="shadow")
_gear("Wool Cloak", "cloak", "common", "Warm and scratchy.", hp=10, sell=10)
_gear("Hunter's Cloak", "cloak", "uncommon", "Leaf-green and hooded.", hp=14, stl=4, sell=60)

# ── Rings & amulets (trinkets) ───────────────────────────────────
_gear("Iron Ring", "ring", "common", "A plain iron band.", atk=2, sell=20)
_gear("Mana Ring", "ring", "common", "A ring with a tiny blue stone.", mp=20, sell=35)
_gear("Power Ring", "ring", "uncommon", "Amplifies physical strength.", atk=5, hp=10, sell=60)
_gear("Dragon Ring", "ring", "rare", "A ring shaped like a coiled dragon.", atk=8, hp=20, mp=15, sell=150,
      element="fire")
_gear("Titan Ring", "ring", "rare", "Forged for titans.", hp=40, df=8, sell=180)
_gear("Copper Ring", "ring", "common", "Turns your finger green.", hp=8, sell=8)
_gear("Silver Ring", "ring", "uncommon", "Polished silver.", mp=12, hp=12, sell=45)
_gear("Ring of Vigor", "ring", "uncommon", "Your heart beats stronger.", hp=30, sell=55)
_gear("Ring of Focus", "ring", "uncommon", "Clears the mind.", mp=30, sell=55)
_gear("Thief's Band", "ring", "uncommon", "Never seems to catch the light.", stl=4, sell=50,
      extra={"_gold_bonus_kill": 5})
_gear("Gambler's Coin Ring", "ring", "rare", "Heads you win, tails they lose.", atk=3,
      extra={"_crit_bonus_custom": 4, "_gold_bonus_kill": 8}, icon="ring", sell=140)
_gear("Amulet of Life", "amulet", "uncommon", "A green stone on a cord.", hp=30, sell=50)
_gear("Mana Amulet", "amulet", "uncommon", "Expands arcane reservoir.", mp=30, sell=50)
_gear("Hero Amulet", "amulet", "rare", "Worn by heroes of old.", atk=5, hp=20, mp=20, sell=130)
_gear("Phoenix Pendant", "amulet", "legendary", "Reborn from the flame.", hp=50, mp=25, sell=220, element="fire")
_gear("Bone Charm", "amulet", "common", "Knucklebones on a string.", hp=6, df=1, sell=10)
_gear("Lucky Rabbit Foot", "amulet", "uncommon", "Not lucky for the rabbit.", stl=1,
      extra={"_crit_bonus_custom": 3}, icon="charm", sell=60)
_gear("Talisman of Warding", "amulet", "rare", "A silver disc etched with a ward.", df=6, hp=25, mp=10, sell=150,
      element="holy")
_gear("Herbalist's Locket", "amulet", "uncommon", "Smells of silverleaf.", hp=10,
      extra={"_potion_bonus": 10}, sell=60, region="AELORIA")

# ── Epic gear sets ───────────────────────────────────────────────
def _set(set_name, region, element, pieces):
    for (name, slot, desc, classes, icon, stats) in pieces:
        _gear(name, slot, "epic", desc, classes, icon=icon, pool=SET_POOL,
              set_name=set_name, element=element, region=region, **stats)

_set("Aeloria Ranger", "AELORIA", "earth", [
    ("Ranger's Hood", "helmet", "Green hood with a leaf-clasp.", None, "hood", dict(hp=22, stl=6, atk=2, sell=150)),
    ("Ranger's Jerkin", "armor", "Supple leather in forest colours.", None, None, dict(hp=50, df=10, stl=5, sell=230)),
    ("Ranger's Mantle", "cloak", "Moss-green mantle; leaves cling to it.", None, None, dict(hp=25, stl=8, sell=170)),
    ("Ranger's Longbow", "weapon", "A tall bow of Aelorian heartwood.", RNG, "bow",
     dict(atk=22, stl=6, sell=290, extra={"_crit_bonus_custom": 4})),
])
_set("Ironspire Forgeguard", "IRONSPIRE", "fire", [
    ("Forgeguard Helm", "helmet", "Riveted helm still warm from the forge.", WAR, None, dict(hp=35, df=12, sell=180)),
    ("Forgeguard Plate", "armor", "Plate tempered in the Forge Depths.", WAR, None, dict(hp=90, df=24, sell=330)),
    ("Forgeguard Bulwark", "shield", "A slab of glowing steel.", WAR, None, dict(hp=40, df=20, sell=260)),
    ("Forgeguard Hammer", "weapon", "A forge hammer turned to war.", TNK, "hammer", dict(atk=26, df=6, sell=310)),
])
_set("Sunveil", "ASH SANDS", "holy", [
    ("Sunveil Wrap", "helmet", "A desert head-wrap that keeps you cool.", CAST, "hood", dict(mp=35, hp=15, sell=160)),
    ("Sunveil Robe", "armor", "White linen stitched with gold suns.", CAST, "robe", dict(hp=35, mp=80, df=5, sell=280)),
    ("Sunveil Mantle", "cloak", "Shimmers like heat haze.", None, None, dict(mp=30, stl=6, hp=20, sell=180)),
    ("Sunveil Sceptre", "weapon", "A sceptre topped with a golden sun disc.", CAST, "mace",
     dict(atk=12, mp=60, hp=20, sell=300)),
])
_set("Wintermark", "FROSTHEIM", "ice", [
    ("Wintermark Helm", "helmet", "Bear-skull helm rimed with frost.", None, None, dict(hp=40, df=10, sell=175)),
    ("Wintermark Hauberk", "armor", "Mail over white fur.", None, None, dict(hp=85, df=18, sell=300)),
    ("Wintermark Cloak", "cloak", "A cloak that has never been warm.", None, None, dict(hp=45, df=4, mp=10, sell=180)),
    ("Wintermark Axe", "weapon", "Bearded axe of blue ice-steel.", WAR, "axe", dict(atk=25, hp=25, sell=310)),
])
_set("Tidecaller", "SOUTH ISLES", "water", [
    ("Tidecaller Circlet", "helmet", "Coral circlet set with a pearl.", CAST, "crown", dict(mp=40, hp=15, sell=170)),
    ("Tidecaller Vestment", "armor", "Sea-silk robes that never dry.", CAST, "robe", dict(hp=40, mp=85, sell=290)),
    ("Tidecaller Pearl", "amulet", "A black pearl that hums with the tide.", None, "amulet",
     dict(mp=40, hp=30, sell=230, extra={"_potion_bonus": 15})),
    ("Tidecaller Trident", "weapon", "Three prongs of coral-bronze.", None, "spear", dict(atk=20, mp=35, sell=300)),
])
_set("Lumeris", "VALDMERE", "holy", [
    ("Lumeris Helm", "helmet", "Silver helm plumed in royal violet.", None, None, dict(hp=40, df=12, mp=10, sell=200)),
    ("Lumeris Plate", "armor", "Silver-violet plate of the Valdmere guard.", WAR + HEA, None,
     dict(hp=95, df=24, mp=15, sell=360)),
    ("Lumeris Kite Shield", "shield", "Bears the crowned star of Valdmere.", None, None,
     dict(hp=40, df=18, mp=10, sell=260)),
    ("Lumeris Blade", "weapon", "A silver longsword with a violet gem.", SWD + TNK, "sword",
     dict(atk=26, hp=20, sell=340, extra={"_crit_bonus_custom": 3})),
    ("Lumeris Signet", "ring", "A royal signet: doors open, prices drop.", None, "ring",
     dict(hp=15, mp=15, atk=4, sell=210, extra={"_gold_bonus_kill": 10})),
])
_set("Duskthorn", "DUSKTHORN", "shadow", [
    ("Duskthorn Greathelm", "helmet", "Cursed: it whispers. Great protection, less magic.", None, "helm",
     dict(hp=45, df=16, mp=-20, sell=190)),
    ("Duskthorn Carapace", "armor", "Cursed: demon-plate that weighs on the soul (STL and MP penalty).", None, None,
     dict(hp=120, df=28, stl=-6, mp=-25, sell=340)),
    ("Duskthorn Cleaver", "weapon", "Cursed: enormous power, but it drinks your life (HP penalty).", WAR, "greatsword",
     dict(atk=36, hp=-40, sell=360)),
    ("Duskthorn Band", "ring", "Cursed: strength bought with your guard (DEF penalty).", None, "ring",
     dict(atk=12, df=-6, sell=200, extra={"_crit_bonus_custom": 5})),
])
_set("Sunspire", "ASH SANDS", "storm", [
    ("Sunspire Scimitar", "weapon", "A curved blade of the Kasbah guard.", RNG + ["Tank", "War Titan"], "scimitar",
     dict(atk=23, stl=4, sell=300, extra={"_crit_bonus_custom": 3})),
    ("Sunspire Turban", "helmet", "Silk turban with a topaz brooch.", None, "hood", dict(hp=25, stl=4, mp=15, sell=160)),
    ("Sunspire Silks", "armor", "Layered silks that turn blades.", None, "robe", dict(hp=55, df=10, stl=6, sell=260)),
    ("Sunspire Sun-Disc", "amulet", "A golden disc that remembers noon.", None, "amulet",
     dict(hp=25, mp=25, atk=4, sell=220, extra={"_gold_bonus_kill": 6})),
])

# ── Legendary uniques with named powers ──────────────────────────
for (_n, _slot, _desc, _cls, _icon, _el, _pow, _st) in [
    ("Dawnbreaker", "weapon", "A sword that glows at first light.", SWD, "sword", "holy",
     "Dawnstrike: +10% critical chance.", dict(atk=34, hp=30, sell=520, extra={"_crit_bonus_custom": 10})),
    ("Vaeltharion's Fang", "weapon", "Carved from the Ashen Dragon's own tooth.", WAR, "greatsword", "fire",
     "Ashen Wrath: huge ATK and +6% crit.", dict(atk=42, df=6, sell=600, extra={"_crit_bonus_custom": 6})),
    ("Frostfang", "weapon", "The Wolf-Queen's tooth set in a hilt of ice.", ROG, "dagger", "ice",
     "Winter's Bite: +8% critical chance.", dict(atk=28, stl=12, sell=480, extra={"_crit_bonus_custom": 8})),
    ("Staff of a Thousand Stars", "weapon", "Constellations drift inside the crystal.", MAG, "staff", "arcane",
     "Starfall: immense mana pool.", dict(atk=18, mp=120, hp=20, sell=540)),
    ("Veyl's Unbound Codex", "weapon", "The renegade archmage's spellbook, still warm.", CAST, "tome", "arcane",
     "Unbound: mana and power beyond the royal limit.", dict(atk=16, mp=100, sell=520,
                                                          extra={"_crit_bonus_custom": 4})),
    ("Ironspire Anvilheart", "weapon", "A hammer with a beating forge-heart.", TNK, "hammer", "fire",
     "Anvilheart: ATK and DEF in one.", dict(atk=30, df=12, hp=40, sell=520)),
    ("Tidebreaker", "weapon", "A trident that parts the sea.", None, "spear", "water",
     "Undertow: potions heal +25.", dict(atk=26, mp=40, sell=480, extra={"_potion_bonus": 25})),
    ("Matriarch's Stinger", "weapon", "The Scorpion Matriarch's barbed tail.", ROG, "dagger", "poison",
     "Venom Queen: +7% crit, +5 stealth.", dict(atk=27, stl=10, sell=470, extra={"_crit_bonus_custom": 7})),
    ("Rourke's Lucky Cutlass", "weapon", "The Bandit King swore it never missed a purse.", RNG, "scimitar", None,
     "Plunder: +30 gold from every kill.", dict(atk=22, stl=6, sell=420, extra={"_gold_bonus_kill": 30})),
    ("Aegis of Valdmere", "shield", "The kingdom's own shield, sworn to its protector.", None, "shield", "holy",
     "Bulwark of Kings: towering defence.", dict(df=30, hp=60, mp=20, sell=520)),
    ("Hollow Crown", "helmet", "The Regent's cursed crown, now quiet. Mostly.", None, "crown", "arcane",
     "Hollow Majesty: power at a cost of DEF.", dict(atk=12, mp=50, hp=30, df=-5, sell=500,
                                                    extra={"_crit_bonus_custom": 5})),
    ("Kharzul's Ember Heart", "amulet", "The Demon Lord's heart, still smouldering.", None, "amulet", "fire",
     "Hellheart: raw power, burning life.", dict(atk=15, hp=-20, mp=30, sell=540,
                                                 extra={"_crit_bonus_custom": 6})),
    ("Azhar's Sandglass", "amulet", "The djinn's hourglass; the sand flows upward.", None, "hourglass", "storm",
     "Borrowed Time: potions heal +40.", dict(hp=40, mp=40, stl=4, sell=500, extra={"_potion_bonus": 40})),
    ("Guildmaster's Shadowcloak", "cloak", "The Thieves' Guildmaster's own cloak.", None, "cloak", "shadow",
     "Unseen Hand: +18 stealth, +15 gold per kill.", dict(stl=18, hp=25, sell=460, extra={"_gold_bonus_kill": 15})),
    ("Ring of the Wolf-Queen", "ring", "A silver ring with two tiny ruby eyes.", None, "ring", "blood",
     "Pack Leader: ATK, HP and crit.", dict(atk=10, hp=35, sell=440, extra={"_crit_bonus_custom": 4})),
]:
    _gear(_n, _slot, "legendary", _desc, _cls, icon=_icon, pool=UNIQUE_POOL, power=_pow, element=_el, **_st)


# ═══════════════════════════════════════════════════════════════
# AFFIXES  (Diablo-style: prefix + base + suffix)
#   names: tier 1/2/3; stats per tier; tier gated by item level.
#   stat keys: hp atk mp df stl crit pot gold
# ═══════════════════════════════════════════════════════════════

AFFIX_TIER_LEVEL = (1, 8, 16)
_W = ("weapon",)
_A = ("armor", "helmet", "shield", "cloak")
_J = ("ring", "amulet")
_ALL = _W + _A + _J

AFFIXES = {}


def _affix(aid, kind, names, stats, slots=_ALL, element=None, group=None):
    AFFIXES[aid] = {"id": aid, "kind": kind, "names": names, "stats": stats,
                    "slots": slots, "element": element, "group": group or aid}

# Prefixes
_affix("flaming",   "prefix", ("Smouldering", "Flaming", "Infernal"),   [{"atk": 2}, {"atk": 4}, {"atk": 7}], _W, "fire", "elem")
_affix("frozen",    "prefix", ("Chilled", "Frozen", "Glacial"),          [{"atk": 2}, {"atk": 4}, {"atk": 7}], _W, "ice", "elem")
_affix("venomous",  "prefix", ("Noxious", "Venomous", "Virulent"),       [{"atk": 2}, {"atk": 4}, {"atk": 7}], _W, "poison", "elem")
_affix("shadowed",  "prefix", ("Dusky", "Shadowed", "Umbral"),           [{"atk": 2, "stl": 1}, {"atk": 4, "stl": 2}, {"atk": 6, "stl": 3}], _W, "shadow", "elem")
_affix("crackling", "prefix", ("Crackling", "Thundering", "Tempest"),    [{"atk": 3}, {"atk": 5}, {"atk": 8}], _W, "storm", "elem")
_affix("hallowed",  "prefix", ("Blessed", "Hallowed", "Radiant"),        [{"atk": 1, "hp": 5}, {"atk": 3, "hp": 10}, {"atk": 5, "hp": 20}], _W + _A, "holy", "elem")
_affix("arcane",    "prefix", ("Runed", "Arcane", "Mystic"),             [{"mp": 8}, {"mp": 16}, {"mp": 28}], _ALL, "arcane", "elem")
_affix("tidal",     "prefix", ("Brackish", "Tidal", "Abyssal"),          [{"mp": 5, "hp": 5}, {"mp": 10, "hp": 10}, {"mp": 18, "hp": 15}], _ALL, "water", "elem")
_affix("vampiric",  "prefix", ("Leeching", "Vampiric", "Sanguine"),      [{"atk": 2, "hp": 5}, {"atk": 4, "hp": 10}, {"atk": 6, "hp": 15}], _W, "blood", "elem")
_affix("emberforged","prefix",("Warm", "Emberforged", "Sunforged"),      [{"df": 1, "hp": 5}, {"df": 3, "hp": 10}, {"df": 5, "hp": 20}], _A, "fire", "elem")
_affix("frostforged","prefix",("Rimed", "Frostforged", "Wintry"),        [{"df": 2, "hp": 8}, {"df": 3, "hp": 14}, {"df": 5, "hp": 24}], _A, "ice", "elem")
_affix("thorned",   "prefix", ("Thorned", "Barbed", "Bramblewoven"),     [{"df": 2, "atk": 1}, {"df": 3, "atk": 2}, {"df": 5, "atk": 3}], _A, "earth", "elem")
_affix("sharp",     "prefix", ("Sharp", "Keen", "Razor"),                [{"crit": 2}, {"crit": 4}, {"crit": 6}], _W)
_affix("heavy",     "prefix", ("Heavy", "Crushing", "Titanic"),          [{"atk": 3, "stl": -1}, {"atk": 6, "stl": -2}, {"atk": 9, "stl": -3}], _W)
_affix("savage",    "prefix", ("Savage", "Brutal", "Merciless"),         [{"atk": 3, "crit": 1}, {"atk": 5, "crit": 2}, {"atk": 8, "crit": 3}], _W)
_affix("sturdy",    "prefix", ("Sturdy", "Reinforced", "Bulwark"),       [{"df": 2}, {"df": 4}, {"df": 7}], _A)
_affix("vital",     "prefix", ("Hale", "Vital", "Mighty"),               [{"hp": 10}, {"hp": 20}, {"hp": 35}], _A + _J)
_affix("swift",     "prefix", ("Light", "Swift", "Fleet"),               [{"stl": 2}, {"stl": 3}, {"stl": 5}], _A + _J)
_affix("lucky",     "prefix", ("Lucky", "Charmed", "Fated"),             [{"crit": 2}, {"crit": 3}, {"crit": 5}], _J)
_affix("gilded",    "prefix", ("Gilded", "Golden", "Opulent"),           [{"gold": 4}, {"gold": 8}, {"gold": 15}], _ALL)
_affix("warded",    "prefix", ("Warded", "Spellguard", "Aegis"),         [{"df": 1, "mp": 5}, {"df": 3, "mp": 10}, {"df": 5, "mp": 15}], _A)
_affix("cursed",    "prefix", ("Hexed", "Cursed", "Damned"),             [{"atk": 5, "hp": -10}, {"atk": 9, "hp": -20}, {"atk": 14, "hp": -35}], _ALL, "shadow")
_affix("masterwork","prefix", ("Fine", "Masterwork", "Exquisite"),       [{"atk": 1, "df": 1}, {"atk": 3, "df": 2}, {"atk": 5, "df": 4}], _ALL)
_affix("sagely",    "prefix", ("Scholarly", "Sagely", "Enlightened"),    [{"mp": 10}, {"mp": 18, "pot": 5}, {"mp": 30, "pot": 10}], _ALL, None, "arcane")

# Suffixes
_affix("bear",     "suffix", ("of the Badger", "of the Bear", "of the Mammoth"),     [{"hp": 10}, {"hp": 22}, {"hp": 40}])
_affix("fox",      "suffix", ("of the Fox", "of the Lynx", "of the Phantom"),        [{"stl": 1}, {"stl": 3}, {"stl": 5}])
_affix("owl",      "suffix", ("of the Owl", "of the Sage", "of the Archmage"),       [{"mp": 8}, {"mp": 15}, {"mp": 28}])
_affix("might",    "suffix", ("of Might", "of Strength", "of the Titan"),            [{"atk": 2}, {"atk": 4}, {"atk": 7}])
_affix("guarding", "suffix", ("of Guarding", "of Warding", "of the Fortress"),       [{"df": 2}, {"df": 4}, {"df": 7}])
_affix("hawk",     "suffix", ("of Precision", "of the Hawk", "of the Eagle"),        [{"crit": 2}, {"crit": 4}, {"crit": 6}])
_affix("wealth",   "suffix", ("of Coin", "of Plunder", "of the Dragon Hoard"),       [{"gold": 5}, {"gold": 10}, {"gold": 20}])
_affix("mending",  "suffix", ("of Herbs", "of Mending", "of Renewal"),               [{"pot": 5}, {"pot": 10}, {"pot": 20}])
_affix("leech",    "suffix", ("of Thirst", "of the Leech", "of the Vampire"),        [{"atk": 1, "hp": 5}, {"atk": 2, "hp": 10}, {"atk": 4, "hp": 15}], _ALL, "blood")
_affix("embers",   "suffix", ("of Sparks", "of Embers", "of the Inferno"),           [{"atk": 1}, {"atk": 3}, {"atk": 5}], _ALL, "fire")
_affix("frost",    "suffix", ("of Rime", "of Frost", "of the Glacier"),              [{"df": 1, "atk": 1}, {"df": 2, "atk": 2}, {"df": 4, "atk": 3}], _ALL, "ice")
_affix("serpent",  "suffix", ("of Venom", "of the Serpent", "of the Hydra"),         [{"atk": 2}, {"atk": 3}, {"atk": 5}], _ALL, "poison")
_affix("shadows",  "suffix", ("of Dusk", "of Shadows", "of the Void"),               [{"stl": 2}, {"stl": 3, "atk": 1}, {"stl": 5, "atk": 3}], _ALL, "shadow")
_affix("light",    "suffix", ("of Dawn", "of Light", "of the Sun"),                  [{"hp": 5, "mp": 5}, {"hp": 12, "mp": 8}, {"hp": 20, "mp": 12}], _ALL, "holy")
_affix("tides",    "suffix", ("of the Shallows", "of the Tides", "of the Deep"),     [{"mp": 6, "hp": 6}, {"mp": 12, "hp": 12}, {"mp": 20, "hp": 20}], _ALL, "water")
_affix("storms",   "suffix", ("of Gusts", "of Storms", "of the Tempest"),            [{"atk": 2, "stl": 1}, {"atk": 3, "stl": 1}, {"atk": 5, "stl": 2}], _ALL, "storm")
_affix("mountain", "suffix", ("of Stone", "of the Mountain", "of Ironspire"),        [{"df": 2, "hp": 5}, {"df": 4, "hp": 10}, {"df": 6, "hp": 15}], _ALL, "earth")
_affix("wolf",     "suffix", ("of the Pup", "of the Wolf", "of the Alpha"),          [{"atk": 1, "hp": 4}, {"atk": 3, "hp": 8}, {"atk": 5, "hp": 14}])
_affix("sorcery",  "suffix", ("of Cantrips", "of Sorcery", "of the Magus"),          [{"mp": 5, "atk": 1}, {"mp": 10, "atk": 2}, {"mp": 18, "atk": 4}], _ALL, "arcane")
_affix("crown",    "suffix", ("of the Squire", "of the Knight", "of the Crown"),     [{"atk": 1, "df": 1, "hp": 5}, {"atk": 2, "df": 2, "hp": 10}, {"atk": 4, "df": 4, "hp": 15}])
_affix("pit",      "suffix", ("of Brimstone", "of the Pit", "of Kharzul"),           [{"atk": 3, "df": -1}, {"atk": 6, "df": -2}, {"atk": 10, "df": -4}], _ALL, "fire")
_affix("dunes",    "suffix", ("of Sand", "of the Dunes", "of the Mirage"),           [{"stl": 1, "crit": 1}, {"stl": 2, "crit": 2}, {"stl": 4, "crit": 3}], _ALL, "earth")
_affix("fortune",  "suffix", ("of Chance", "of Fortune", "of Destiny"),              [{"crit": 1, "gold": 3}, {"crit": 2, "gold": 6}, {"crit": 3, "gold": 10}])

PREFIXES = [a for a in AFFIXES.values() if a["kind"] == "prefix"]
SUFFIXES = [a for a in AFFIXES.values() if a["kind"] == "suffix"]

_STAT_ATTR = {"hp": "hp_bonus", "atk": "atk_bonus", "mp": "mp_bonus",
              "df": "def_bonus", "stl": "stealth_bonus"}
_EXTRA_ATTR = {"crit": "_crit_bonus_custom", "pot": "_potion_bonus", "gold": "_gold_bonus_kill"}
AFFIX_COUNT = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 3}


def affix_name(aff):
    """Display name of an affix entry {"id","tier"}."""
    a = AFFIXES.get(aff.get("id")) if isinstance(aff, dict) else None
    if not a:
        return "?"
    t = max(1, min(3, int(aff.get("tier", 1))))
    return a["names"][t - 1]


def affix_stats(aff):
    a = AFFIXES.get(aff.get("id")) if isinstance(aff, dict) else None
    if not a:
        return {}
    t = max(1, min(3, int(aff.get("tier", 1))))
    return dict(a["stats"][t - 1])


def max_affix_tier(level):
    lv = max(1, int(level or 1))
    return sum(1 for need in AFFIX_TIER_LEVEL if lv >= need)


def apply_affixes(item, affixes, level=1):
    """Return a NEW Equipment: `item` with the given affixes baked in.
    affixes: [{"id","tier"}]. Name becomes 'Prefix(es) Base Suffix'."""
    import copy as _copy
    new = _copy.deepcopy(item)
    base = item.base or item.name
    pre = [a for a in affixes if AFFIXES.get(a["id"], {}).get("kind") == "prefix"]
    suf = [a for a in affixes if AFFIXES.get(a["id"], {}).get("kind") == "suffix"]
    words = [affix_name(a) for a in pre] + [base] + [affix_name(a) for a in suf[:1]]
    new.name = " ".join(words)
    new.base = base
    new.affixes = list(item.affixes) + [{"id": a["id"], "tier": int(a["tier"])} for a in affixes]
    new.item_level = max(int(level or 1), item.item_level or 0)
    tier_sum = 0
    for a in affixes:
        tier_sum += int(a["tier"])
        for k, v in affix_stats(a).items():
            if k in _STAT_ATTR:
                setattr(new, _STAT_ATTR[k], getattr(new, _STAT_ATTR[k]) + v)
            elif k in _EXTRA_ATTR:
                attr = _EXTRA_ATTR[k]
                new.extra[attr] = new.extra.get(attr, 0) + v
    new.extra = {k: v for k, v in new.extra.items() if v}
    by_count = RARITIES[min(len(new.affixes), 3)]
    if rarity_rank(by_count) > rarity_rank(new.rarity):
        new.rarity = by_count
    new.sell_value = int(item.sell_value * (1 + 0.3 * len(affixes)) + 6 * tier_sum)
    return new


def roll_affixes(slot, count, level=1, rng=None, exclude=(), allow_suffix=True):
    """Pick `count` compatible affixes at tiers allowed by `level`.
    Layout: 1 -> prefix or suffix, 2 -> prefix + suffix, 3 -> 2 prefixes +
    suffix (prefixes only when the base name already reads '... of X').
    No two affixes share a group and elements never clash."""
    rng = rng or random
    top = max_affix_tier(level)
    if count <= 0:
        return []
    if not allow_suffix:
        kinds = ["prefix"] * min(count, 2)
    elif count == 1:
        kinds = [rng.choice(("prefix", "suffix"))]
    else:
        kinds = ["prefix"] * (min(count, 3) - 1) + ["suffix"]
    chosen, groups, elems = [], set(exclude), set()
    for kind in kinds:
        pool = SUFFIXES if kind == "suffix" else PREFIXES
        cands = [a for a in pool if slot in a["slots"] and a["group"] not in groups
                 and (not a["element"] or not elems or a["element"] in elems)]
        if not cands:
            continue
        a = rng.choice(cands)
        # Weighted toward the top allowed tier
        tier = top if rng.random() < 0.55 else rng.randint(1, top)
        chosen.append({"id": a["id"], "tier": tier})
        groups.add(a["group"])
        if a["element"]:
            elems.add(a["element"])
    return chosen


def roll_affixes_for(item, count, level=1, rng=None):
    """roll_affixes() suited to an Equipment (no suffix on '... of X' bases)."""
    base = item.base or item.name
    return roll_affixes(item.slot, count, level, rng, allow_suffix=" of " not in base)


# ═══════════════════════════════════════════════════════════════
# PUBLIC LOOKUP API  (cross-team contract #5)
# ═══════════════════════════════════════════════════════════════

def _find_factory(name):
    for pool in ALL_POOLS:
        if name in pool:
            return pool[name]
    return None


def make_item(name):
    """A fresh instance of the item called `name` (any pool, incl. uniques,
    sets and key items; case-insensitive), or None if unknown."""
    if not name:
        return None
    fn = _find_factory(name)
    if fn is None:
        low = str(name).strip().lower()
        for pool in ALL_POOLS:
            for k, f in pool.items():
                if k.lower() == low:
                    fn = f; break
            if fn: break
    if fn is None:
        return None
    try:
        return fn()
    except Exception:
        return None


def all_item_names(include_keys=True):
    names = []
    for pool in ALL_POOLS:
        if pool is KEY_ITEMS and not include_keys:
            continue
        names.extend(pool)
    return names


def roll_rarity(level, rng=None):
    rng = rng or random
    lv = max(1, int(level or 1))
    weights = [
        ("common",    max(20.0, 60.0 - lv * 1.2)),
        ("uncommon",  26.0),
        ("rare",      9.0 + lv * 0.4),
        ("epic",      (1.5 + lv * 0.25) if lv >= 6 else 0.0),
        ("legendary", (0.3 + lv * 0.05) if lv >= 12 else 0.0),
    ]
    total = sum(w for _, w in weights)
    x = rng.random() * total
    for r, w in weights:
        x -= w
        if x <= 0:
            return r
    return "common"


def _gear_bases(max_rarity, level):
    """Equipment base names from ITEM_POOL up to max_rarity, near level."""
    out = []
    for n in ITEM_POOL:
        inf = ITEM_INFO.get(n, {})
        if inf.get("type") != "equipment":
            continue
        if rarity_rank(inf["rarity"]) > rarity_rank(max_rarity) or inf["rarity"] == "legendary":
            continue
        if inf["lvl"] <= level + 3 and inf["lvl"] >= level - 14:
            out.append(n)
    if not out:
        # Past the top of this rarity's range: offer its strongest bases
        allowed = [n for n in ITEM_POOL if ITEM_INFO.get(n, {}).get("type") == "equipment"
                   and rarity_rank(ITEM_INFO[n]["rarity"]) <= rarity_rank(max_rarity)
                   and ITEM_INFO[n]["rarity"] != "legendary"]
        allowed.sort(key=lambda n: -ITEM_INFO[n]["lvl"])
        out = allowed[:14]
    return out


def random_gear(level, rarity="uncommon", rng=None, slot=None):
    """An affixed Equipment of the given rarity, scaled to level."""
    rng = rng or random
    lv = max(1, int(level or 1))
    if rarity == "legendary":
        cands = [n for n in UNIQUE_POOL if ITEM_INFO[n]["lvl"] <= lv + 20] or list(UNIQUE_POOL)
        if slot:
            cands = [n for n in cands if ITEM_INFO[n]["slot"] == slot] or cands
        it = UNIQUE_POOL[rng.choice(cands)]()
        it.item_level = lv
        return it
    if rarity == "epic" and rng.random() < 0.5:
        cands = list(SET_POOL)
        if slot:
            cands = [n for n in cands if ITEM_INFO[n]["slot"] == slot] or cands
        it = SET_POOL[rng.choice(cands)]()
        it.item_level = lv
        return it
    base_r = {"common": "common", "uncommon": "uncommon", "rare": "rare", "epic": "rare"}.get(rarity, "uncommon")
    names = _gear_bases(base_r, lv)
    if slot:
        names = [n for n in names if ITEM_INFO[n]["slot"] == slot] or names
    if not names:
        names = [n for n in ITEM_POOL if ITEM_INFO.get(n, {}).get("type") == "equipment"
                 and ITEM_INFO[n]["rarity"] != "legendary"]
    it = ITEM_POOL[rng.choice(names)]()
    n_aff = AFFIX_COUNT.get(rarity, 0)
    if n_aff:
        it = apply_affixes(it, roll_affixes_for(it, n_aff, lv, rng), lv)
        if rarity_rank(it.rarity) < rarity_rank(rarity):
            it.rarity = rarity
    else:
        it.item_level = lv
    return it


def random_loot(level, rarity=None, rng=None, kind=None):
    """A random item for a player of `level`. Never returns None.

    rarity: None (rolled from level) or one of RARITIES.
    kind:   None, "gear", "consumable" or "material".
    Common rolls are mostly consumables/materials; uncommon and better are
    gear with affixes (uncommon 1, rare 2, epic 3 or a set piece,
    legendary = a unique)."""
    rng = rng or random
    lv = max(1, int(level or 1))
    if rarity not in RARITIES:
        rarity = roll_rarity(lv, rng)
    if kind is None:
        if rarity == "common":
            x = rng.random()
            kind = "consumable" if x < 0.45 else "material" if x < 0.7 else "gear"
        else:
            kind = "gear" if rarity == "legendary" or rng.random() < 0.85 else "consumable"
    if kind == "gear":
        return random_gear(lv, rarity, rng)
    want_types = ("material",) if kind == "material" else ("heal", "mana", "antidote", "bomb", "buff")
    names = [n for n in ITEM_POOL
             if ITEM_INFO.get(n, {}).get("type") in want_types
             and ITEM_INFO[n]["rarity"] == rarity and ITEM_INFO[n]["lvl"] <= lv + 6]
    if not names:
        # Best rarity available at or below the requested one
        for r in reversed(RARITIES[:rarity_rank(rarity) + 1]):
            names = [n for n in ITEM_POOL if ITEM_INFO.get(n, {}).get("type") in want_types
                     and ITEM_INFO[n]["rarity"] == r]
            if names:
                break
    if not names:
        return random_gear(lv, rarity, rng)
    return ITEM_POOL[rng.choice(names)]()


def maybe_upgrade(item, level=1, rng=None):
    """Chance for a dropped plain Equipment to roll affixes (uncommon/rare)."""
    rng = rng or random
    if not isinstance(item, Equipment) or item.affixes or item.rarity in ("epic", "legendary"):
        return item
    x = rng.random()
    n = 2 if x < 0.07 else 1 if x < 0.30 else 0
    if not n:
        return item
    return apply_affixes(item, roll_affixes_for(item, n, level, rng), level)


def describe_effect(item):
    """Plain-English effect line for any item (used by inspect / lists)."""
    it = item.item if isinstance(item, ItemStack) else item
    if isinstance(it, Equipment):
        return it.stat_line()
    fx = CONSUMABLE_FX.get(it.name, {})
    t = it.item_type
    if t == "heal":
        s = f"+{it.value} HP" if it.value < 999 else "Full HP"
        if fx.get("mp"):    s += f", +{fx['mp']} MP"
        if fx.get("regen"): s += f", regen {fx['regen'][1]}/turn x{fx['regen'][0]}"
        if fx.get("cure"):  s += ", cures " + "/".join(fx["cure"])
        return s
    if t == "mana":
        s = f"+{it.value} MP"
        if fx.get("heal"):  s += f", +{fx['heal']} HP"
        return s
    if t == "antidote":
        s = "cures " + "/".join(fx.get("cure", ("Poison", "Burn")))
        if fx.get("heal"):  s += f", +{fx['heal']} HP"
        return s
    if t == "buff":
        s = f"ATK+{it.value} for {fx.get('turns', 3)} turns"
        if fx.get("hp_cost"): s += f", costs {int(fx['hp_cost']*100)}% HP"
        return s
    if t == "bomb":
        if it.name in ESCAPE_ITEMS:
            return "escape from a normal battle"
        kind, ch = BOMB_STATUS.get(it.name, ("burn", 40))
        s = f"{it.value}+ damage"
        if kind != "none" and ch:
            s += f", {ch}% {kind}"
        return s
    if t == "god":      return "auto-revive at 0 HP"
    if t == "material": return "crafting material"
    if t == "key":      return "key item"
    return t


def item_category(item):
    it = item.item if isinstance(item, ItemStack) else item
    if isinstance(it, Equipment):
        return it.slot
    return _info(it.name).get("cat") or {
        "heal": "potion", "mana": "potion", "god": "potion", "antidote": "potion",
        "buff": "food", "bomb": "bomb", "material": "material", "key": "key"}.get(it.item_type, "misc")


# Single-width list glyph per category (east-asian width N/A — safe in
# Western terminals; verified in the items test-suite).
CATEGORY_GLYPH = {
    "weapon": "†", "armor": "■", "helmet": "∩", "shield": "Θ", "cloak": "§",
    "ring": "°", "amulet": "♦", "potion": "✚", "food": "↑", "bomb": "*",
    "material": "•", "key": "‡", "misc": "·",
}


def item_glyph(item, coloured=True):
    """1-char rarity-coloured category glyph for list rows."""
    it = item.item if isinstance(item, ItemStack) else item
    g = CATEGORY_GLYPH.get(item_category(it), "·")
    if it.item_type == "mana":
        g = "◊"
    if not coloured:
        return g
    return f"{rarity_colour(getattr(it, 'rarity', 'common'))}{g}\033[0m"


# ═══════════════════════════════════════════════════════════════
# LOOT TABLES
# ═══════════════════════════════════════════════════════════════

LOOT_TABLE = {
    "Goblin":        [("Potion",0.50),("Wolf Pelt",0.20),("Iron Ring",0.05),("Rusty Dagger",0.04)],
    "Slime":         [("Potion",0.30)],
    "Wolf":          [("Wolf Pelt",0.65),("Potion",0.25)],
    "Bandit":        [("Potion",0.40),("Iron Sword",0.10),("Iron Ring",0.06),("Ancient Coin",0.10)],
    "Skeleton":      [("Bone Shard",0.55),("Ether",0.20),("Iron Shield",0.05)],
    "Stone Golem":   [("Iron Ore",0.65),("Obsidian Shard",0.25),("Steel Helm",0.04),("Granite Core",0.30)],
    "Harpy":         [("Feather",0.55),("Ether",0.20),("Travel Cloak",0.06)],
    "Sand Wyrm":     [("Scale Fragment",0.45),("Ether",0.30),("Shadow Blade",0.04),("Venom Fang",0.35)],
    "Scorpion":      [("Venom Fang",0.60),("Scale Fragment",0.30),("Antidote",0.20),("Scorpion Chitin",0.30)],
    "Ice Wolf":      [("Frost Crystal",0.50),("Potion",0.25),("Frost Cloak",0.04),("Winter Pelt",0.25)],
    "Shadow Beast":  [("Dark Shard",0.55),("God Potion",0.03),("Shadow Cloth",0.30)],
    "Cultist":       [("Ether",0.45),("Dark Shard",0.25),("Runic Stone",0.30),("Mana Stone",0.20)],
    "Desert Raider": [("Potion",0.40),("Strength Draught",0.15),("Fire Bomb",0.10),("Desert Glass",0.20)],
    "Frost Wraith":  [("Frost Crystal",0.60),("Hi-Ether",0.20),("Mage Shroud",0.05)],
    "Armored Knight":[("Iron Ore",0.50),("Obsidian Shard",0.20),("Iron Shield",0.10),("Steel Ingot",0.15)],
    "Frost Dragon":  [("Frost Crystal",0.90),("Dragon Scale",0.50),("Phoenix Feather",0.10),("Mammoth Ivory",0.30)],
    "Goblin King":   [("Bone Shard",1.0),("Iron Ore",0.80),("Power Ring",0.15)],
    "Shadow Lord":   [("Dark Shard",1.0),("Dragon Scale",0.40),("Phoenix Pendant",0.05)],
    # Enemies that previously fell back to the generic 20% potion
    "Rock Wolf":     [("Wolf Pelt",0.45),("Iron Ore",0.35),("Potion",0.20)],
    "Dust Imp":      [("Ether",0.40),("Scale Fragment",0.25),("Smoke Bomb",0.08)],
    "Snow Beast":    [("Frost Crystal",0.45),("Wolf Pelt",0.30),("Hi-Potion",0.10),("Yeti Fur",0.25)],
    "Ice Golem":     [("Frost Crystal",0.55),("Iron Ore",0.40),("Obsidian Shard",0.15),("Rime Silver",0.06)],
    "Dark Golem":    [("Obsidian Shard",0.50),("Dark Shard",0.35),("Iron Ore",0.40)],
    "Death Knight":  [("Dark Shard",0.50),("Runic Stone",0.25),("Steel Shield",0.05)],
    "Lich":          [("Mana Stone",0.50),("Holy Relic",0.20),("Hi-Ether",0.30)],
    "Void Stalker":  [("Shadow Cloth",0.50),("Dark Shard",0.35),("Shadow Cloak",0.04)],
    "Dungeon Warden":[("Runic Stone",1.0),("Holy Relic",0.50),("Titan Ring",0.10)],
    "Shadow Lich":   [("Mana Stone",1.0),("Holy Relic",0.60),("Phoenix Feather",0.10)],
    "Vaeltharion":   [("Dragon Scale",1.0),("God Potion",0.50),("Phoenix Feather",0.30),("Vaeltharion's Fang",0.20),
                      ("Dragon Egg Shell",0.25)],
    "Dragon":        [("Dragon Scale",1.0),("God Potion",0.50),("Dragon Ring",0.25),("Phoenix Feather",0.30)],
    # Overhaul elites (contract #3)
    "Alley Thief":   [("Ancient Coin",0.30),("Smoke Bomb",0.15),("Rusty Dagger",0.06),("Thief's Band",0.03)],
    "Cutthroat":     [("Potion",0.30),("Stiletto",0.05),("Venom Flask",0.12),("Gold Nugget",0.08)],
    "Royal Guard":   [("Hi-Potion",0.35),("Lumeris Silver",0.05),("Kite Shield",0.05),("Violet Silk",0.10)],
    "Imp":           [("Brimstone",0.45),("Ether",0.25),("Fire Bomb",0.12)],
    "Desert Assassin":[("Sandveil Powder",0.15),("Silk Bolt",0.25),("Kris Knife",0.04),("Venom Fang",0.30)],
    "Sand Scorpion": [("Scorpion Chitin",0.55),("Venom Fang",0.45),("Antidote",0.20)],
    "Demon Knight":  [("Hellforged Iron",0.15),("Demon Horn",0.30),("Brimstone",0.40),("Ashen Blood Wine",0.10)],
    # Overhaul bosses (contract #3) — uniques are their signature drops
    "Demon Lord Kharzul":      [("Kharzul's Ember Heart",0.40),("Soul Ember",1.0),("Demon Horn",0.8),
                                ("Hellforged Iron",0.6),("Demon Brew",0.5)],
    "Hellhound Warden":        [("Demon Horn",0.7),("Brimstone",1.0),("Hellfire Flask",0.3)],
    "Sand Djinn Azhar":        [("Azhar's Sandglass",0.40),("Djinn Dust",1.0),("Sun Topaz",0.6)],
    "Scorpion Matriarch":      [("Matriarch's Stinger",0.35),("Scorpion Chitin",1.0),("Venom Fang",1.0),("Panacea",0.3)],
    "The Hollow Regent":       [("Hollow Crown",0.50),("Lumeris Silver",1.0),("Royal Cordial",0.6)],
    "Archmage Veyl the Unbound":[("Veyl's Unbound Codex",0.40),("Mana Crystal",0.6),("Runic Stone",1.0)],
    "Bandit King Rourke":      [("Rourke's Lucky Cutlass",0.40),("Gold Nugget",1.0),("Ancient Coin",1.0)],
    "Thieves' Guildmaster":    [("Guildmaster's Shadowcloak",0.40),("Shadow Cloth",1.0)],
}


def roll_drops(enemy_name, level=None, rng=None):
    """Loot for a defeated enemy. With `level`, dropped gear may roll affixes
    and there is a small chance of a bonus random_loot item."""
    rng = rng or random
    table = LOOT_TABLE.get(enemy_name, [("Potion", 0.20)])
    out = []
    for n, c in table:
        if c > 0 and rng.random() < c:
            it = make_item(n)
            if it is not None:
                out.append(maybe_upgrade(it, level or 1, rng) if level else it)
    if level and rng.random() < 0.04:
        out.append(random_loot(level, rng.choice(("uncommon", "uncommon", "rare")), rng, kind="gear"))
    return out


# ═══════════════════════════════════════════════════════════════
# CRAFTING RECIPES  (town bench)
# ═══════════════════════════════════════════════════════════════

def _recipe(name, needs, desc="", qty=1, classes="auto"):
    def result(n=name):
        return make_item(n)
    if classes == "auto":
        proto = make_item(name)
        classes = getattr(proto, "allowed_classes", None)
    return {"name": name, "needs": dict(needs), "result": result,
            "classes": list(classes) if classes else None, "desc": desc, "qty": qty}


CRAFTING_RECIPES = [
    # ── Consumables ───────────────────────────────────────────────
    _recipe("Antidote",          {"Feather": 1, "Venom Fang": 1}, "Cures poison and burn", 3),
    _recipe("Fire Bomb",         {"Mana Stone": 1, "Iron Ore": 1}, "Throwable fire explosive", 3),
    _recipe("Mega Potion",       {"Wolf Pelt": 1, "Frost Crystal": 1}, "Restores 400 HP", 2),
    _recipe("Mana Crystal",      {"Mana Stone": 3, "Runic Stone": 1}, "Restores 500 MP"),
    _recipe("Hero's Brew",       {"Holy Relic": 1, "Frost Crystal": 1, "Wolf Pelt": 1}, "Heals 150 HP and 50 MP", 2),
    _recipe("Strength Draught",  {"Venom Fang": 2, "Mana Stone": 1}, "ATK+10 for 3 turns", 2),
    _recipe("Bandage",           {"Linen Cloth": 1}, "Restores 25 HP", 3),
    _recipe("Herbal Poultice",   {"Silverleaf Herb": 2}, "60 HP and cures poison", 2),
    _recipe("Honeycake",         {"Silverleaf Herb": 1, "Amber Resin": 1}, "45 HP + regeneration", 3),
    _recipe("Spiced Jerky",      {"Boar Hide": 1, "Coal Lump": 1}, "ATK+6 for 3 turns", 3),
    _recipe("Smelling Salts",    {"Desert Glass": 1, "Silverleaf Herb": 1}, "Cures stun", 3),
    _recipe("Panacea",           {"Holy Relic": 1, "Silverleaf Herb": 3}, "Cures all, +80 HP", 2),
    _recipe("Frost Bomb",        {"Frost Crystal": 1, "Coal Lump": 1}, "Freezing shards", 3),
    _recipe("Venom Flask",       {"Venom Fang": 2, "Desert Glass": 1}, "Poison cloud", 3),
    _recipe("Thunder Flask",     {"Sun Topaz": 1, "Mana Stone": 1}, "Heavy storm damage", 2),
    _recipe("Holy Grenade",      {"Holy Relic": 1, "Coal Lump": 2}, "Blessed explosion", 2),
    _recipe("Hellfire Flask",    {"Brimstone": 2, "Soul Ember": 1}, "Massive fire damage", 2),
    _recipe("Smoke Bomb",        {"Coal Lump": 2, "Feather": 1}, "Escape any normal fight", 2),
    _recipe("Escape Scroll",     {"Linen Cloth": 1, "Mana Stone": 1}, "Escape any normal fight", 2),
    _recipe("Scroll of Fireball",{"Linen Cloth": 1, "Forge Ember": 1}, "A single fireball", 2),
    _recipe("Scroll of Lightning",{"Linen Cloth": 1, "Djinn Dust": 1}, "A lightning strike", 2),
    _recipe("Troll Blood Draught",{"Yeti Fur": 1, "Silverleaf Herb": 2}, "150 HP + strong regen", 2),
    _recipe("Starlight Ether",   {"Mana Stone": 2, "Pearl": 1}, "Restores 180 MP", 2),
    _recipe("Giant's Tonic",     {"Mammoth Ivory": 1, "Venom Fang": 1}, "ATK+20 for 5 turns", 2),
    _recipe("Demon Brew",        {"Demon Horn": 1, "Brimstone": 1}, "ATK+25, costs HP", 2),

    # ── Weapons ──────────────────────────────────────────────────
    _recipe("Wolf Fang Blade",   {"Wolf Pelt": 2, "Iron Ore": 1}, "Savage blade from wolf remains", classes=None),
    _recipe("Frost Blade",       {"Frost Crystal": 2, "Iron Ore": 2}, "Chills enemies on contact", classes=WAR),
    _recipe("Bone Staff",        {"Bone Shard": 3, "Iron Ore": 1}, "Bone-carved focus for mages"),
    _recipe("Shadow Blade",      {"Dark Shard": 2, "Iron Ore": 1}, "Strikes from the dark"),
    _recipe("Venom Dagger",      {"Venom Fang": 3, "Shadow Cloth": 1}, "Poisons on every hit"),
    _recipe("Runic Greatsword",  {"Runic Stone": 2, "Iron Ore": 4}, "Ancient runes amplify power"),
    _recipe("Void Staff",        {"Dark Shard": 4, "Mana Stone": 3, "Feather": 2}, "Channels the void itself"),
    _recipe("Hunting Bow",       {"Oak Heartwood": 1, "Ranger's Twine": 1}, "A yew hunting bow"),
    _recipe("Longbow",           {"Oak Heartwood": 2, "Ranger's Twine": 2, "Feather": 2}, "A tall war bow"),
    _recipe("Oak Staff",         {"Oak Heartwood": 2}, "A simple focus staff"),
    _recipe("Ember Staff",       {"Oak Heartwood": 1, "Forge Ember": 1, "Mana Stone": 1}, "A smouldering staff"),
    _recipe("Glacier Staff",     {"Frost Crystal": 3, "Rime Silver": 1, "Mana Stone": 1}, "A staff of eternal ice"),
    _recipe("Spark Wand",        {"Desert Glass": 2, "Mana Stone": 1}, "Crackling wand"),
    _recipe("Knight's Longsword",{"Steel Ingot": 2, "Leather Strip": 1}, "A knight's longsword"),
    _recipe("Claymore",          {"Steel Ingot": 3, "Leather Strip": 1}, "A highland greatsword"),
    _recipe("Silversteel Sword", {"Mithril Ore": 1, "Steel Ingot": 2}, "Mirror-bright blade"),
    _recipe("Battle Axe",        {"Steel Ingot": 2, "Oak Heartwood": 1}, "Double-bitted axe"),
    _recipe("Maul",              {"Granite Core": 2, "Steel Ingot": 1}, "A war sledgehammer"),
    _recipe("Halberd",           {"Steel Ingot": 2, "Oak Heartwood": 2}, "Axe, spear and hook"),
    _recipe("Stiletto",          {"Steel Ingot": 1, "Venom Fang": 1}, "Armour-piercing needle"),
    _recipe("Nightfang Dirk",    {"Shadow Cloth": 2, "Mithril Ore": 1}, "A blade the dark hides"),
    _recipe("Morning Star",      {"Steel Ingot": 2, "Holy Relic": 1}, "Spiked holy mace"),
    _recipe("Grimoire of Ash",   {"Kraken Ink": 1, "Forge Ember": 1, "Linen Cloth": 2}, "Burnt pages, burning spells"),

    # ── Armour, shields, cloaks ───────────────────────────────────
    _recipe("Hunter Vest",       {"Wolf Pelt": 3}, "Hardened wolf leather"),
    _recipe("Shadow Cloak",      {"Dark Shard": 2, "Feather": 1}, "Fades into shadows"),
    _recipe("Dragon Scale Armor",{"Dragon Scale": 2, "Iron Ore": 3}, "Near-impervious to damage"),
    _recipe("Mage Shroud",       {"Shadow Cloth": 2, "Feather": 2}, "Woven with arcane thread"),
    _recipe("Holy Shield",       {"Holy Relic": 1, "Iron Ore": 2}, "Blessed by divine power"),
    _recipe("Obsidian Armor",    {"Obsidian Shard": 3, "Iron Ore": 4}, "Forged from volcanic rock"),
    _recipe("Runic Shield",      {"Runic Stone": 2, "Iron Ore": 3}, "Runic inscriptions absorb damage"),
    _recipe("Studded Leather",   {"Boar Hide": 2, "Iron Ore": 1}, "Leather riveted with steel"),
    _recipe("Brigandine",        {"Steel Ingot": 2, "Linen Cloth": 2}, "Hidden steel plates"),
    _recipe("Silk Robe",         {"Silk Bolt": 2, "Mana Stone": 1}, "Light, mana-rich silk"),
    _recipe("Nightstalker Leathers",{"Shadow Cloth": 2, "Boar Hide": 2}, "Soot-dyed leathers"),
    _recipe("Kite Shield",       {"Steel Ingot": 1, "Oak Heartwood": 1}, "A tapered shield"),
    _recipe("Hunter's Cloak",    {"Boar Hide": 1, "Linen Cloth": 1}, "Leaf-green cloak"),
    _recipe("Horned Helm",       {"Steel Ingot": 1, "Mammoth Ivory": 1}, "Intimidating horned helm"),

    # ── Rings & amulets ───────────────────────────────────────────
    _recipe("Phoenix Pendant",   {"Phoenix Feather": 1, "Mana Stone": 2}, "Reborn from the flame"),
    _recipe("Power Ring",        {"Iron Ore": 2, "Mana Stone": 1}, "Amplifies physical strength"),
    _recipe("Mana Amulet",       {"Mana Stone": 2, "Feather": 1}, "Expands arcane reservoir"),
    _recipe("Titan Ring",        {"Obsidian Shard": 2, "Iron Ore": 3}, "Forged for titans"),
    _recipe("Silver Ring",       {"Gold Nugget": 1, "Mana Stone": 1}, "Polished band"),
    _recipe("Ring of Vigor",     {"Ruby": 1, "Iron Ore": 1}, "Strengthens the heart"),
    _recipe("Ring of Focus",     {"Sapphire": 1, "Iron Ore": 1}, "Clears the mind"),
    _recipe("Lucky Rabbit Foot", {"Wolf Pelt": 1, "Ancient Coin": 2}, "+3% crit"),
    _recipe("Herbalist's Locket",{"Silverleaf Herb": 3, "Emerald": 1}, "Potions heal more"),
    _recipe("Talisman of Warding",{"Holy Relic": 1, "Rime Silver": 1}, "A silver ward"),

    # ── Epic set pieces (need rare regional materials) ────────────
    _recipe("Ranger's Hood",     {"Boar Hide": 3, "Amber Resin": 2, "Ranger's Twine": 2}, "Aeloria Ranger set"),
    _recipe("Ranger's Longbow",  {"Oak Heartwood": 4, "Amber Resin": 2, "Phoenix Feather": 1}, "Aeloria Ranger set"),
    _recipe("Forgeguard Helm",   {"Steel Ingot": 3, "Forge Ember": 2}, "Ironspire Forgeguard set"),
    _recipe("Forgeguard Hammer", {"Mithril Ore": 2, "Forge Ember": 2, "Steel Ingot": 3}, "Ironspire Forgeguard set"),
    _recipe("Wintermark Cloak",  {"Winter Pelt": 3, "Rime Silver": 1}, "Frostheim Wintermark set"),
    _recipe("Wintermark Axe",    {"Rime Silver": 2, "Mammoth Ivory": 1, "Steel Ingot": 2}, "Frostheim Wintermark set"),
    _recipe("Sunveil Wrap",      {"Silk Bolt": 3, "Sun Topaz": 1}, "Ash Sands Sunveil set"),
    _recipe("Sunveil Sceptre",   {"Sun Topaz": 2, "Gold Nugget": 2, "Holy Relic": 1}, "Ash Sands Sunveil set"),
    _recipe("Tidecaller Pearl",  {"Pearl": 3, "Kraken Ink": 1}, "South Isles Tidecaller set"),
    _recipe("Tidecaller Trident",{"Coral Branch": 4, "Pearl": 2, "Steel Ingot": 1}, "South Isles Tidecaller set"),
    _recipe("Duskthorn Band",    {"Hellforged Iron": 1, "Demon Horn": 1}, "Cursed Duskthorn set"),
    _recipe("Duskthorn Cleaver", {"Hellforged Iron": 3, "Soul Ember": 1}, "Cursed Duskthorn set"),
    _recipe("Lumeris Signet",    {"Lumeris Silver": 1, "Violet Silk": 1, "Gold Nugget": 1}, "Valdmere Lumeris set"),
    _recipe("Sunspire Sun-Disc", {"Gold Nugget": 2, "Sun Topaz": 1, "Djinn Dust": 1}, "Sunspire royal set"),
]


# ═══════════════════════════════════════════════════════════════
# SHOP STOCK
#   Prices are always above what the shop pays back (shops buy at
#   100% of sell_value), so nothing can be bought and resold at a
#   profit — enforced by shop_price() and the items test-suite.
# ═══════════════════════════════════════════════════════════════

def shop_price(item, price):
    """Clamp a listed price so it is strictly above the item's resale value."""
    sv = getattr(item, "sell_value", 0) or 0
    return max(int(price), sv + max(2, sv // 5))


_SHOP_BASE = [
    ("Potion", 8), ("Hi-Potion", 20), ("Full Potion", 50), ("Mega Potion", 120),
    ("Ether", 10), ("Hi-Ether", 35), ("Elixir", 80), ("Antidote", 12),
    ("Bandage", 5), ("Traveller's Bread", 6), ("Smelling Salts", 16),
    ("Fire Bomb", 18), ("Smoke Bomb", 20), ("Strength Draught", 40), ("Spiced Jerky", 14),
    ("Iron Sword", 60), ("Iron Staff", 55), ("Short Sword", 50), ("War Hammer", 110),
    ("Holy Mace", 95), ("Hunting Bow", 55), ("Apprentice Wand", 36), ("Prayer Book", 48),
    ("Hand Axe", 45), ("Iron Spear", 50), ("Iron Greatsword", 75),
    ("Leather Armor", 50), ("Padded Tunic", 18), ("Mage Robe", 60), ("Apprentice Robe", 24),
    ("Monk's Habit", 34),
    ("Iron Ring", 25), ("Copper Ring", 12), ("Bone Charm", 14),
    ("Wooden Shield", 30), ("Buckler", 18),
    ("Travel Cloak", 20), ("Wool Cloak", 14),
    ("Iron Helm", 30), ("Leather Cap", 12), ("Wizard Hat", 30),
    ("Linen Cloth", 9), ("Leather Strip", 9),
]

_SHOP_REGION = {
    "AELORIA": [
        ("Steel Helm", 80), ("Shadow Suit", 90), ("Mana Ring", 45), ("Regen Tonic", 25),
        ("Honeycake", 12), ("Herbal Poultice", 20), ("Oak Staff", 40), ("Longbow", 135),
        ("Hunter's Cloak", 80), ("Herbalist's Locket", 80), ("Silverleaf Herb", 16),
        ("Oak Heartwood", 24), ("Ranger's Twine", 14),
        ("Ranger's Jerkin", 340), ("Ranger's Mantle", 250),
    ],
    "IRONSPIRE": [
        ("Steel Sword", 120), ("Chain Mail", 95), ("Steel Shield", 110), ("Titan Axe", 190),
        ("Claymore", 185), ("Battle Axe", 165), ("Maul", 175), ("Halberd", 170), ("Barbute", 95),
        ("Brigandine", 125), ("Kite Shield", 105), ("Steel Ingot", 60), ("Coal Lump", 11),
        ("Forgeguard Plate", 480), ("Forgeguard Bulwark", 380),
    ],
    "FROSTHEIM": [
        ("Frost Cloak", 130), ("Crystal Staff", 140), ("Mega Ether", 150), ("Mana Crystal", 350),
        ("Frostheim Mead", 48), ("Moonwater", 34), ("Frost Bomb", 32), ("Horned Helm", 105),
        ("Ring of Vigor", 75), ("Winter Pelt", 48),
        ("Wintermark Helm", 260), ("Wintermark Hauberk", 440),
    ],
    "ASH SANDS": [
        ("Assassin Dagger", 200), ("Priest Vestment", 95), ("Antidote", 12),
        ("Sunspire Mint Tea", 28), ("Arcane Tea", 25), ("Sand Bomb", 20), ("Sandveil Powder", 36),
        ("Venom Flask", 28), ("Silk Robe", 135), ("Stiletto", 120), ("Desert Glass", 36),
        ("Sunveil Robe", 400), ("Sunveil Mantle", 260),
    ],
    "SOUTH ISLES": [
        ("Iron Shield", 65), ("Amulet of Life", 70), ("Elixir of Life", 400), ("Hero's Brew", 100),
        ("Coconut Water", 14), ("Tidecaller Grog", 22), ("Kris Knife", 140), ("Ring of Focus", 75),
        ("Tide Shell", 24), ("Coral Branch", 34),
        ("Tidecaller Circlet", 245), ("Tidecaller Vestment", 420),
    ],
    # Special stock for the overhaul's kingdom locations (use these keys
    # with town_shop_stock("VALDMERE") etc.)
    "VALDMERE": [
        ("Royal Cordial", 130), ("Holy Water", 34), ("Knight's Plate", 230), ("Knight's Longsword", 130),
        ("Circlet of Focus", 115), ("Talisman of Warding", 200), ("Violet Silk", 95),
        ("Lumeris Helm", 290), ("Lumeris Kite Shield", 380), ("Lumeris Plate", 520), ("Lumeris Blade", 490),
    ],
    "SUNSPIRE": [
        ("Sunspire Mint Tea", 28), ("Arcane Tea", 25), ("Panacea", 95), ("Silk Bolt", 55),
        ("Sun Topaz", 120), ("Gambler's Coin Ring", 200),
        ("Sunspire Scimitar", 430), ("Sunspire Turban", 230), ("Sunspire Silks", 370),
    ],
    "DUSKTHORN": [
        ("Demon Brew", 70), ("Ashen Blood Wine", 55), ("Hellfire Flask", 85), ("Brimstone", 50),
        ("Duskthorn Greathelm", 270), ("Duskthorn Carapace", 490),
    ],
}


def _stock(entries):
    out = []
    for name, price in entries:
        it = make_item(name)
        if it is not None:
            out.append((it, shop_price(it, price)))
    return out


def town_shop_stock(region_name=""):
    """[(item, price)] for a town shop: base stock + the region's specials.
    region_name is the continent name (AELORIA, IRONSPIRE, FROSTHEIM,
    ASH SANDS, SOUTH ISLES) or a kingdom key (VALDMERE, SUNSPIRE, DUSKTHORN)."""
    base = _stock(_SHOP_BASE)
    seen = {it.name for it, _ in base}
    extra = [(it, p) for it, p in _stock(_SHOP_REGION.get((region_name or "").upper(), []))
             if it.name not in seen]
    return base + extra


def shop_regions():
    return list(_SHOP_REGION)
