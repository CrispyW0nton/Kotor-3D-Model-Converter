# Party Management

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript party management functions. These functions allow scripts to add/remove party members, check party membership, get party members by index, and manage the party leader.

---

## Party Management Fundamentals

### Understanding the Party System

KotOR supports a party of up to 3 members:

- **Party Leader** (index 0) - The active character controlled by the player
- **Party Member 1** (index 1) - First companion
- **Party Member 2** (index 2) - Second companion

The party leader is always at index 0. When the leader changes, party order may shift.

### NPC Constants

Party members are identified by NPC constants:

- `NPC_PLAYER` (-1) - Player character
- `NPC_BASTILA` (0) - Bastila Shan (K1)
- `NPC_CANDEROUS` (1) - Canderous Ordo (K1)
- `NPC_CARTH` (2) - Carth Onasi (K1)
- `NPC_HK_47` (3) - HK-47
- `NPC_JOLEE` (4) - Jolee Bindo (K1)
- `NPC_JUHANI` (5) - Juhani (K1)
- `NPC_MISSION` (6) - Mission Vao (K1)
- `NPC_T3_M4` (7) - T3-M4
- `NPC_ZAALBAR` (8) - Zaalbar (K1)

(TSL has different NPC constants - consult `nwscript.nss` for the full list)

---

## Party Member Access Functions

### GetPartyMemberByIndex

**Routine:** 577

#### Function Signature

```nss
object GetPartyMemberByIndex(int nIndex);
```

#### Description

Gets the party member at a specific index. The party leader is always at index 0. The order may change when the party leader changes.

#### Parameters

- `nIndex`: Party member index (0 = leader, 1 = first companion, 2 = second companion)

#### Returns

- Party member object at the specified index
- `OBJECT_INVALID` if index is invalid or no member at that index

#### Usage Examples

```nss
// Get party leader
object oLeader = GetPartyMemberByIndex(0);
```

```nss
// Get first companion
object oCompanion1 = GetPartyMemberByIndex(1);
```

**Pattern: Iterate Through Party**

```nss
// Loop through all party members
int i = 0;
object oMember = GetPartyMemberByIndex(i);
while (GetIsObjectValid(oMember)) {
    // Do something with each party member
    int nHP = GetCurrentHitPoints(oMember);
    if (nHP < 50) {
        // Heal low HP party member
        effect eHeal = EffectHeal(100);
        ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oMember);
    }
    i++;
    oMember = GetPartyMemberByIndex(i);
}
```

#### Notes

- Index 0 is always the party leader
- Party order may change when leader changes
- Always validate objects before use
- Returns `OBJECT_INVALID` if no member at that index

---

### IsObjectPartyMember

**Routine:** 576

#### Function Signature

```nss
int IsObjectPartyMember(object oCreature);
```

#### Description

Checks if a creature is currently a member of the active party.

#### Parameters

- `oCreature`: Creature to check

#### Returns

- `TRUE` (1) if the creature is a party member
- `FALSE` (0) if not a party member or object is invalid

#### Usage Examples

```nss
// Check if NPC is in party
object oNPC = GetObjectByTag("Bastila");
if (IsObjectPartyMember(oNPC)) {
    // Bastila is in the party
}
```

**Pattern: Area Entry with Party Check**

```nss
// From vendor/K1_Community_Patch/Source/k_pman_init02.nss
void main() {
    object oEntering = GetEnteringObject();
    
    if (IsObjectPartyMember(oEntering) && GetIsObjectValid(oElora)) {
        // Party member entered area - trigger event
        // ...
    }
}
```

**Pattern: Conditional Based on Party Membership**

```nss
// Check party composition
object oNPC = GetObjectByTag("Jolee");
if (IsObjectPartyMember(oNPC)) {
    // Jolee is in party - show different dialogue
} else {
    // Jolee not in party - show default dialogue
}
```

#### Notes

- Works on any creature object
- Returns `FALSE` for objects that aren't party members
- Party members are tracked dynamically

---

## Party Member Management Functions

### AddPartyMember

**Routine:** 574

#### Function Signature

```nss
int AddPartyMember(int nNPC, object oCreature);
```

#### Description

Adds a creature to the party. The creature must be available and the party must not be full (max 3 members).

#### Parameters

- `nNPC`: NPC constant (e.g., `NPC_BASTILA`, `NPC_HK_47`)
- `oCreature`: Creature object to add (must match the NPC type)

#### Returns

- `TRUE` (1) if the creature was successfully added
- `FALSE` (0) if addition failed (party full, creature already in party, etc.)

#### Usage Examples

```nss
// Add NPC to party
object oBastila = GetObjectByTag("Bastila");
int nResult = AddPartyMember(NPC_BASTILA, oBastila);
if (nResult) {
    // Successfully added to party
}
```

**Pattern: Add Party Member After Event**

```nss
// Add party member after quest completion
if (GetGlobalBoolean("Quest_Completed")) {
    object oCompanion = GetObjectByTag("new_companion");
    if (GetIsObjectValid(oCompanion)) {
        AddPartyMember(NPC_NEW_COMPANION, oCompanion);
    }
}
```

#### Notes

- Party can have at most 3 members (including leader)
- Creature must match the NPC constant type
- Returns `FALSE` if party is full or NPC is already in party
- Some NPCs may need to be "available" before they can be added

---

### RemovePartyMember

**Routine:** 575

#### Function Signature

```nss
int RemovePartyMember(int nNPC);
```

#### Description

Removes a creature from the party by NPC constant. The creature is removed from the active party but may remain available for re-adding later.

#### Parameters

- `nNPC`: NPC constant of the party member to remove (e.g., `NPC_BASTILA`)

#### Returns

- `TRUE` (1) if the creature was successfully removed
- `FALSE` (0) if removal failed (not in party, invalid NPC, etc.)

#### Usage Examples

```nss
// Remove NPC from party
int nResult = RemovePartyMember(NPC_BASTILA);
if (nResult) {
    // Successfully removed from party
}
```

**Pattern: Conditional Party Removal**

```nss
// Remove party member based on condition
if (GetGlobalBoolean("Bastila_Left")) {
    RemovePartyMember(NPC_BASTILA);
}
```

#### Notes

- Cannot remove the party leader (player character)
- Party must have at least 1 member (the leader)
- Returns `FALSE` if NPC is not in party
- Creature object may persist in the area after removal

---

## Party Leader Functions

### SetPartyLeader

**Routine:** 1739

#### Function Signature

```nss
int SetPartyLeader(int nNPC);
```

#### Description

Changes the party leader to the specified NPC constant. The party leader is the active character controlled by the player.

#### Parameters

- `nNPC`: NPC constant to set as leader (use `NPC_PLAYER` (-1) for player character)

#### Returns

- `TRUE` (1) if leader was successfully changed
- `FALSE` (0) if change failed (NPC not in party, etc.)

#### Usage Examples

```nss
// Set player as party leader
SetPartyLeader(NPC_PLAYER);
```

**Pattern: Reset Leader After Cutscene**

```nss
// From vendor/K1_Community_Patch/Source/k_pman_init02.nss
void main() {
    // Ensure player is party leader before cutscene
    SetPartyLeader(NPC_PLAYER);
    
    // ... cutscene logic ...
}
```

**Pattern: Switch Leader to NPC**

```nss
// Temporarily switch leader to NPC for dialogue
SetPartyLeader(NPC_BASTILA);
// Start conversation with NPC as leader
// ... conversation ...
// Switch back to player
SetPartyLeader(NPC_PLAYER);
```

#### Notes

- Use `NPC_PLAYER` (-1) to set player character as leader
- NPC must be in the party to become leader
- Party order may change when leader changes
- Leader change clears party actions

---

## Common Patterns and Best Practices

### Pattern: Check Party Composition

```nss
// Check which party members are present
object oBastila = GetObjectByTag("Bastila");
object oHK47 = GetObjectByTag("HK47");

if (IsObjectPartyMember(oBastila) && IsObjectPartyMember(oHK47)) {
    // Both Bastila and HK-47 are in party
}
```

### Pattern: Iterate Through All Party Members

```nss
// Loop through party and perform action on each
int i = 0;
object oMember = GetPartyMemberByIndex(i);
while (GetIsObjectValid(oMember) && i < 3) {
    // Heal all party members
    int nCurrentHP = GetCurrentHitPoints(oMember);
    int nMaxHP = GetMaxHitPoints(oMember);
    if (nCurrentHP < nMaxHP) {
        effect eHeal = EffectHeal(nMaxHP - nCurrentHP);
        ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oMember);
    }
    i++;
    oMember = GetPartyMemberByIndex(i);
}
```

### Pattern: Get Party Member Helper Function

```nss
// Helper function to safely get party member
object GetPartyMember(int nIndex) {
    object oMember = GetPartyMemberByIndex(nIndex);
    if (GetIsObjectValid(oMember)) {
        return oMember;
    }
    return OBJECT_INVALID;
}
```

### Pattern: Party-Based Conditional Logic

```nss
// Different behavior based on party composition
object oJolee = GetObjectByTag("Jolee");
if (IsObjectPartyMember(oJolee)) {
    // Jolee is in party - use him in conversation
    ActionStartConversation(oJolee, "dialogue_with_jolee");
} else {
    // Jolee not in party - use player
    ActionStartConversation(GetFirstPC(), "dialogue_default");
}
```

### Best Practices

1. **Always Validate Objects**: Check `GetIsObjectValid()` before using party members
2. **Check Party Membership**: Use `IsObjectPartyMember()` before assuming an NPC is in party
3. **Use NPC Constants**: Always use NPC constants (`NPC_BASTILA`, etc.) instead of magic numbers
4. **Index 0 is Leader**: Remember that index 0 is always the party leader
5. **Party Size Limit**: Maximum party size is 3 members
6. **Leader Changes**: Be aware that party order may change when leader changes

---

## Related Functions

- `GetFirstPC()` - Get the player character (see [Module & Area](NSS-Shared-Functions-Module-and-Area))
- `GetObjectByTag()` - Find creatures by tag (see [Object Query](NSS-Shared-Functions-Object-Query-and-Manipulation))

---

## Additional Notes

### Party Size Limits

- **Maximum Party Size**: 3 members (leader + 2 companions)
- **Minimum Party Size**: 1 member (the leader/player)

### Party Leader

The party leader:

- Is always at index 0 in `GetPartyMemberByIndex()`
- Is the active character controlled by the player
- Can be changed with `SetPartyLeader()`
- Cannot be removed from the party

### NPC Availability

Some NPCs must be "available" before they can be added to the party. Availability is typically managed through:

- Quest progression
- Global variables
- Special events
- Story flags

### Party Order

Party order (indices 0, 1, 2):

- **Index 0**: Party leader (always player or currently active leader)
- **Index 1**: First companion
- **Index 2**: Second companion

When the leader changes, party order may shift to maintain the new leader at index 0.

### Party Member Objects

Party member objects:

- Persist across area transitions
- Are created when added to party
- May remain in areas after removal (implementation dependent)
- Can be accessed by tag when not in party (if they exist in the area)
