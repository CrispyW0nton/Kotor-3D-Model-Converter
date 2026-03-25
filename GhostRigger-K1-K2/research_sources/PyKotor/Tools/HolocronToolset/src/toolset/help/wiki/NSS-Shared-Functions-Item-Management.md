# Item Management

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript item management functions. These functions allow scripts to create items, manage inventory, equip/unequip items, and manipulate item properties.

---

## Item Management Fundamentals

### Understanding Items and Inventory

Items in KotOR are objects that can be:

- **Possessed** by creatures (in inventory)
- **Equipped** in specific inventory slots
- **Stacked** (multiple instances in one stack)
- **Stored** in placeables (containers)
- **Dropped** on the ground

### Inventory Slots

Items can be equipped in specific inventory slots. Different item types go in different slots:

- **Armor Slots:** Head, Body, Hands, Implant, Belt
- **Weapon Slots:** Right Hand, Left Hand (and variants)
- **Arm Slots:** Left Arm, Right Arm

---

## Creating Items

### CreateItemOnObject

**Routine:** 31

#### Function Signature

```nss
object CreateItemOnObject(string sItemTemplate, object oTarget = OBJECT_SELF, int nStackSize = 1, int bHideMessage = 0);
```

#### Description

Creates an item from a template and adds it to the target object's inventory (creature or placeable). The item is added immediately to the inventory.

#### Parameters

- `sItemTemplate`: Item template resref (without `.uti` extension, e.g., "g_w_lghtsbr01")
- `oTarget`: Target object to add item to (creature or placeable, default: `OBJECT_SELF`)
- `nStackSize`: Number of items in the stack (default: 1)
- `bHideMessage`: If `TRUE`, hides the "Item Added" message (TSL only, default: 0)

#### Returns

- Created item object
- `OBJECT_INVALID` if creation failed or template doesn't exist

#### Usage Examples

```nss
// Create item in self's inventory
object oItem = CreateItemOnObject("g_w_lghtsbr01", OBJECT_SELF);
```

```nss
// Create item in PC's inventory
object oPC = GetFirstPC();
object oItem = CreateItemOnObject("g_i_medpac01", oPC, 5); // Stack of 5
```

```nss
// Create item in placeable container
object oContainer = GetObjectByTag("chest");
CreateItemOnObject("g_w_vibroblade01", oContainer);
```

**Pattern: Conditional Item Creation**

```nss
// Create different items based on condition
string sItemTemplate;
if (GetGlobalNumber("Lightsaber_Color") == 0) {
    sItemTemplate = "g_w_lghtsbr01"; // Blue
} else if (GetGlobalNumber("Lightsaber_Color") == 1) {
    sItemTemplate = "g_w_lghtsbr02"; // Green
} else {
    sItemTemplate = "g_w_lghtsbr03"; // Red
}
CreateItemOnObject(sItemTemplate, GetFirstPC(), 1, 1);
```

**Pattern: Create and Equip**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/950COR_Coruscant_(cutscene)/a_createpcsaber.nss
object oLightsaber = CreateItemOnObject("g_w_lghtsbr10", GetFirstPC(), 1, 1);
object oRobe = CreateItemOnObject("a_robe_08", GetFirstPC(), 1, 1);
AssignCommand(GetFirstPC(), ActionEquipItem(oLightsaber, INVENTORY_SLOT_RIGHTWEAPON, 0));
AssignCommand(GetFirstPC(), ActionEquipItem(oRobe, INVENTORY_SLOT_BODY, 0));
```

#### Notes

- Item template must exist (defined in `.uti` files)
- Items are added immediately to inventory
- If target is a creature, item goes to inventory (not automatically equipped)
- Stack size must be 1 or greater

---

## Finding Items

### GetItemPossessedBy

**Routine:** 30

#### Function Signature

```nss
object GetItemPossessedBy(object oCreature, string sItemTag);
```

#### Description

Gets an item with the specified tag from a creature's inventory (including equipped items).

#### Parameters

- `oCreature`: Creature to search in
- `sItemTag`: Tag of the item to find

#### Returns

- Item object with the specified tag
- `OBJECT_INVALID` if item not found

#### Usage Examples

```nss
// Find item in PC's inventory
object oItem = GetItemPossessedBy(GetFirstPC(), "my_custom_item");
if (GetIsObjectValid(oItem)) {
    // Item found
}
```

**Pattern: Remove Item from Player**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/a_take_item.nss
object oItem = GetItemPossessedBy(GetPartyLeader(), "quest_item");
if (GetIsObjectValid(oItem)) {
    int nStackSize = GetItemStackSize(oItem);
    int nQuantity = 1; // Amount to remove
    if (nQuantity < nStackSize) {
        SetItemStackSize(oItem, nStackSize - nQuantity);
    } else {
        DestroyObject(oItem); // Remove entire stack
    }
}
```

---

### GetItemPossessor

**Routine:** 29

#### Function Signature

```nss
object GetItemPossessor(object oItem);
```

#### Description

Gets the creature or placeable that possesses (has in inventory) the specified item.

#### Parameters

- `oItem`: Item to find the possessor of

#### Returns

- Object that possesses the item
- `OBJECT_INVALID` if item has no possessor or is invalid

#### Usage Examples

```nss
// Find who has an item
object oItem = GetObjectByTag("special_item");
object oOwner = GetItemPossessor(oItem);
if (GetIsObjectValid(oOwner)) {
    // Item is owned by oOwner
}
```

---

### GetItemInSlot

**Routine:** 202

#### Function Signature

```nss
object GetItemInSlot(int nInventorySlot, object oCreature = OBJECT_SELF);
```

#### Description

Gets the item equipped in a specific inventory slot on a creature.

#### Parameters

- `nInventorySlot`: Inventory slot constant:
  - `INVENTORY_SLOT_HEAD` (0) - Head slot
  - `INVENTORY_SLOT_BODY` (1) - Body/armor slot
  - `INVENTORY_SLOT_HANDS` (3) - Hands/gloves slot
  - `INVENTORY_SLOT_RIGHTWEAPON` (4) - Right hand weapon
  - `INVENTORY_SLOT_LEFTWEAPON` (5) - Left hand weapon
  - `INVENTORY_SLOT_LEFTARM` (7) - Left arm slot
  - `INVENTORY_SLOT_RIGHTARM` (8) - Right arm slot
  - `INVENTORY_SLOT_IMPLANT` (9) - Implant slot
  - `INVENTORY_SLOT_BELT` (10) - Belt slot
  - `INVENTORY_SLOT_CWEAPON_L` (14) - Concealed weapon left (TSL)
  - `INVENTORY_SLOT_CWEAPON_R` (15) - Concealed weapon right (TSL)
  - `INVENTORY_SLOT_CWEAPON_B` (16) - Concealed weapon both (TSL)
  - `INVENTORY_SLOT_CARMOUR` (17) - Concealed armor (TSL)
- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Item equipped in the slot
- `OBJECT_INVALID` if no item in slot or slot is invalid

#### Usage Examples

```nss
// Get equipped weapon
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
if (GetIsObjectValid(oWeapon)) {
    // Creature has a weapon equipped
}
```

```nss
// Get all equipped items
object oHead = GetItemInSlot(INVENTORY_SLOT_HEAD, GetFirstPC());
object oBody = GetItemInSlot(INVENTORY_SLOT_BODY, GetFirstPC());
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
```

**Pattern: Store Equipment Before Change**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/950COR_Coruscant_(cutscene)/a_createpcsaber.nss
object oBodyItem = GetItemInSlot(INVENTORY_SLOT_BODY, GetFirstPC());
object oLWeapItem = GetItemInSlot(INVENTORY_SLOT_LEFTWEAPON, GetFirstPC());
object oRWeapItem = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
object oBeltItem = GetItemInSlot(INVENTORY_SLOT_BELT, GetFirstPC());
object oHeadItem = GetItemInSlot(INVENTORY_SLOT_HEAD, GetFirstPC());
// Store items in placeables, then create new items...
```

---

## Equipment Actions

### ActionEquipItem

**Routine:** 32

#### Function Signature

```nss
void ActionEquipItem(object oItem, int nInventorySlot, int bInstant = FALSE);
```

#### Description

Queues an action to equip an item into a specific inventory slot. The item must be in the creature's inventory.

#### Parameters

- `oItem`: Item to equip (must be in creature's inventory)
- `nInventorySlot`: Inventory slot constant (see `GetItemInSlot` for list)
- `bInstant`: If `TRUE`, equips immediately without animation (default: `FALSE`)

#### Usage Examples

```nss
// Equip item from inventory
object oItem = GetItemPossessedBy(GetFirstPC(), "g_w_lghtsbr01");
if (GetIsObjectValid(oItem)) {
    ActionEquipItem(oItem, INVENTORY_SLOT_RIGHTWEAPON);
}
```

```nss
// Create and equip immediately
object oItem = CreateItemOnObject("g_w_vibroblade01", GetFirstPC());
ActionEquipItem(oItem, INVENTORY_SLOT_RIGHTWEAPON, TRUE); // Instant equip
```

**Pattern: Create and Equip Sequence**

```nss
// Create item and equip it
object oLightsaber = CreateItemOnObject("g_w_lghtsbr01", GetFirstPC(), 1, 1);
AssignCommand(GetFirstPC(), ActionEquipItem(oLightsaber, INVENTORY_SLOT_RIGHTWEAPON, 0));
```

#### Notes

- Item must be in the creature's inventory first
- If slot already has an item, the old item is unequipped
- Use `bInstant = TRUE` for cutscenes or immediate equip needs

---

### ActionUnequipItem

**Routine:** 33

#### Function Signature

```nss
void ActionUnequipItem(object oItem, int bInstant = FALSE);
```

#### Description

Queues an action to unequip an item. The item remains in inventory but is no longer equipped.

#### Parameters

- `oItem`: Item to unequip
- `bInstant`: If `TRUE`, unequips immediately without animation (default: `FALSE`)

#### Usage Examples

```nss
// Unequip current weapon
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
if (GetIsObjectValid(oWeapon)) {
    ActionUnequipItem(oWeapon);
}
```

```nss
// Unequip all equipment
object oHead = GetItemInSlot(INVENTORY_SLOT_HEAD, GetFirstPC());
object oBody = GetItemInSlot(INVENTORY_SLOT_BODY, GetFirstPC());
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());

if (GetIsObjectValid(oHead)) ActionUnequipItem(oHead, TRUE);
if (GetIsObjectValid(oBody)) ActionUnequipItem(oBody, TRUE);
if (GetIsObjectValid(oWeapon)) ActionUnequipItem(oWeapon, TRUE);
```

---

## Item Transfer Actions

### ActionGiveItem

**Routine:** 135

#### Function Signature

```nss
void ActionGiveItem(object oItem, object oGiveTo);
```

#### Description

Queues an action to give an item to another creature. The item is transferred from the giver's inventory to the receiver's inventory.

#### Parameters

- `oItem`: Item to give (must be in the acting creature's inventory)
- `oGiveTo`: Creature to give the item to

#### Usage Examples

```nss
// Give item to NPC
object oItem = GetItemPossessedBy(GetFirstPC(), "quest_item");
object oNPC = GetObjectByTag("merchant");
ActionGiveItem(oItem, oNPC);
```

**Pattern: Store Equipment**

```nss
// Store equipped items in a placeable
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
object oStorage = GetObjectByTag("storage_chest");
AssignCommand(GetFirstPC(), ActionGiveItem(oWeapon, oStorage));
```

---

### ActionTakeItem

**Routine:** 136

#### Function Signature

```nss
void ActionTakeItem(object oItem, object oTakeFrom);
```

#### Description

Queues an action to take an item from another creature or placeable. The item is transferred to the acting creature's inventory.

#### Parameters

- `oItem`: Item to take
- `oTakeFrom`: Creature or placeable to take the item from

#### Usage Examples

```nss
// Take item from NPC
object oNPC = GetObjectByTag("merchant");
object oItem = GetItemPossessedBy(oNPC, "quest_item");
ActionTakeItem(oItem, oNPC);
```

---

### ActionPickUpItem

**Routine:** 34

#### Function Signature

```nss
void ActionPickUpItem(object oItem);
```

#### Description

Queues an action to pick up an item from the ground. The item is added to the creature's inventory.

#### Parameters

- `oItem`: Item on the ground to pick up

#### Usage Examples

```nss
// Pick up item from ground
object oItem = GetObjectByTag("dropped_item");
ActionPickUpItem(oItem);
```

---

### ActionPutDownItem

**Routine:** 35

#### Function Signature

```nss
void ActionPutDownItem(object oItem);
```

#### Description

Queues an action to drop an item on the ground at the creature's feet. The item is removed from inventory and placed as a ground object.

#### Parameters

- `oItem`: Item to drop (must be in creature's inventory)

#### Usage Examples

```nss
// Drop item on ground
object oItem = GetItemPossessedBy(GetFirstPC(), "unwanted_item");
ActionPutDownItem(oItem);
```

---

## Item Properties

### GetItemStackSize

**Routine:** 722 (TSL only, may be available in K1)

#### Function Signature

```nss
int GetItemStackSize(object oItem);
```

#### Description

Gets the stack size (quantity) of an item. Stackable items (like medpacs, grenades) can have multiple instances in one stack.

#### Parameters

- `oItem`: Item to check

#### Returns

- Stack size (number of items in the stack, 1 if not stackable)
- `0` if item is invalid

#### Usage Examples

```nss
// Check stack size
object oItem = GetItemPossessedBy(GetFirstPC(), "g_i_medpac01");
if (GetIsObjectValid(oItem)) {
    int nStack = GetItemStackSize(oItem);
    if (nStack < 10) {
        // Low on medpacs
    }
}
```

**Pattern: Remove Quantity from Stack**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/a_take_item.nss
object oItem = GetItemPossessedBy(GetPartyLeader(), "quest_item");
if (GetIsObjectValid(oItem)) {
    int nStackSize = GetItemStackSize(oItem);
    int nQuantity = 1; // Amount to remove
    if (nQuantity < nStackSize) {
        SetItemStackSize(oItem, nStackSize - nQuantity);
    } else if (nQuantity >= nStackSize) {
        DestroyObject(oItem); // Remove entire stack
    }
}
```

---

### SetItemStackSize

**Routine:** 723 (TSL only, may be available in K1)

#### Function Signature

```nss
void SetItemStackSize(object oItem, int nStackSize);
```

#### Description

Sets the stack size (quantity) of an item. The stack size determines how many of that item are in the stack.

#### Parameters

- `oItem`: Item to modify
- `nStackSize`: New stack size (must be 1 or greater)

#### Usage Examples

```nss
// Set stack size
object oItem = GetItemPossessedBy(GetFirstPC(), "g_i_medpac01");
SetItemStackSize(oItem, 10);
```

**Pattern: Increment Stack Size**

```nss
// Add to existing stack
object oItem = GetItemPossessedBy(GetFirstPC(), "g_i_medpac01");
if (GetIsObjectValid(oItem)) {
    int nCurrent = GetItemStackSize(oItem);
    SetItemStackSize(oItem, nCurrent + 5);
}
```

**Pattern: Safe Stack Size Modification**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/K1/Modules/M26AD_Manaan_Docking_Bay_manm26ad/k_man_com43.nss
int nCurrent = GetItemStackSize(oItem);
if (nAmount > 0) {
    SetItemStackSize(oItem, nCurrent + nAmount); // Add to stack
} else {
    if ((nCurrent + nAmount) <= 0) {
        SetItemStackSize(oItem, 1);
        DestroyObject(oItem); // Destroy if stack would be 0 or negative
    } else {
        SetItemStackSize(oItem, nCurrent + nAmount); // Reduce stack
    }
}
```

#### Notes

- Stack size must be 1 or greater
- Setting stack size to 0 or less may cause errors
- Destroy the item instead of setting stack to 0

---

## Inventory Slot Constants

### Common Inventory Slots

#### Equipment Slots (K1 & TSL)

- `INVENTORY_SLOT_HEAD` (0) - Head slot (helmets, headgear)
- `INVENTORY_SLOT_BODY` (1) - Body slot (armor, robes)
- `INVENTORY_SLOT_HANDS` (3) - Hands slot (gloves)
- `INVENTORY_SLOT_RIGHTWEAPON` (4) - Right hand weapon
- `INVENTORY_SLOT_LEFTWEAPON` (5) - Left hand weapon (off-hand, dual-wield)
- `INVENTORY_SLOT_LEFTARM` (7) - Left arm slot
- `INVENTORY_SLOT_RIGHTARM` (8) - Right arm slot
- `INVENTORY_SLOT_IMPLANT` (9) - Implant slot (cybernetic implants)
- `INVENTORY_SLOT_BELT` (10) - Belt slot

#### Concealed Slots (TSL only)

- `INVENTORY_SLOT_CWEAPON_L` (14) - Concealed weapon left
- `INVENTORY_SLOT_CWEAPON_R` (15) - Concealed weapon right
- `INVENTORY_SLOT_CWEAPON_B` (16) - Concealed weapon both
- `INVENTORY_SLOT_CARMOUR` (17) - Concealed armor

#### Additional Slots (TSL only)

- `INVENTORY_SLOT_RIGHTWEAPON2` (18) - Second right weapon slot
- `INVENTORY_SLOT_LEFTWEAPON2` (19) - Second left weapon slot

---

## Common Patterns and Best Practices

### Pattern: Create and Equip Item

```nss
// Create item and equip it
object oItem = CreateItemOnObject("g_w_lghtsbr01", GetFirstPC(), 1, 1);
AssignCommand(GetFirstPC(), ActionEquipItem(oItem, INVENTORY_SLOT_RIGHTWEAPON, 0));
```

### Pattern: Remove Item from Stack

```nss
// Remove quantity from stack safely
object oItem = GetItemPossessedBy(GetFirstPC(), "stackable_item");
if (GetIsObjectValid(oItem)) {
    int nStackSize = GetItemStackSize(oItem);
    int nRemove = 5;
    if (nRemove < nStackSize) {
        SetItemStackSize(oItem, nStackSize - nRemove);
    } else {
        DestroyObject(oItem); // Remove entire stack
    }
}
```

### Pattern: Check and Equip Weapon

```nss
// Check if weapon equipped, if not equip one
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, GetFirstPC());
if (!GetIsObjectValid(oWeapon)) {
    // No weapon, find one in inventory
    object oAvailableWeapon = GetItemPossessedBy(GetFirstPC(), "backup_weapon");
    if (GetIsObjectValid(oAvailableWeapon)) {
        ActionEquipItem(oAvailableWeapon, INVENTORY_SLOT_RIGHTWEAPON);
    }
}
```

### Pattern: Store All Equipment

```nss
// Store all equipped items in a container
object oStorage = GetObjectByTag("storage_chest");
object oPC = GetFirstPC();

object oHead = GetItemInSlot(INVENTORY_SLOT_HEAD, oPC);
object oBody = GetItemInSlot(INVENTORY_SLOT_BODY, oPC);
object oWeapon = GetItemInSlot(INVENTORY_SLOT_RIGHTWEAPON, oPC);

if (GetIsObjectValid(oHead)) AssignCommand(oPC, ActionGiveItem(oHead, oStorage));
if (GetIsObjectValid(oBody)) AssignCommand(oPC, ActionGiveItem(oBody, oStorage));
if (GetIsObjectValid(oWeapon)) AssignCommand(oPC, ActionGiveItem(oWeapon, oStorage));
```

### Best Practices

1. **Always Validate Items**: Check `GetIsObjectValid()` before using items
2. **Check Stack Size Before Removing**: Use `GetItemStackSize()` before modifying stacks
3. **Destroy Instead of Stack Size 0**: Don't set stack size to 0, destroy the item instead
4. **Use AssignCommand for Other Objects**: Use `AssignCommand()` when giving/taking items on behalf of other creatures
5. **Clear Actions Before Equipment Changes**: In cutscenes, clear actions before changing equipment
6. **Use Instant Equip for Cutscenes**: Use `bInstant = TRUE` for immediate equipment changes in cutscenes

---

## Related Functions

- `DestroyObject()` - Remove item from game (see [Object Query](NSS-Shared-Functions-Object-Query-and-Manipulation))
- `GetTag()` - Get item's tag (useful for finding items)
- `ActionUseItem()` - Use an item (if available)

---

## Additional Item Functions

Additional item-related functions include:

- `ActionUseFeat()` - Use a feat (some items trigger feats)
- `ActionUseSkill()` - Use a skill (some items are used via skills)
- Item property functions (see [Item Properties](NSS-Shared-Functions-Item-Properties) if documented)

Each follows similar patterns to the functions documented above.
