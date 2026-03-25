# Local Variables

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript local variable functions. Local variables are stored on individual objects (creatures, placeables, etc.) and are used for object-specific state tracking.

---

## Local Variables Fundamentals

### Understanding Local Variables

Local variables are stored **on individual objects** (creatures, placeables, doors, etc.) and are used for:

- Object-specific state tracking
- Flags and conditions unique to an object
- Temporary data that doesn't need to persist across saves (though they do persist)
- Quest/NPC state that's specific to that instance

**Key Differences from Global Variables:**

- **Scope:** Local to the object, not campaign-wide
- **Persistence:** Stored with the object, persist in save games
- **Range:** Local numbers have different range limits (see below)
- **Index-based:** Local variables use numeric indices, not string names

### Index Ranges

Local variables use **numeric indices** instead of string names:

- **Local Numbers:** Indices 12-28 (17 slots available)
- **Local Booleans:** Indices 20-63 (44 slots available)
- **Local Strings:** Indices 0-9 (10 slots available)

**⚠️ IMPORTANT:** These ranges are fixed. You cannot use indices outside these ranges.

---

## Local Number Functions

### GetLocalNumber

**Routine:** 681

#### Function Signature

```nss
int GetLocalNumber(object oObject, int nIndex);
```

#### Description

Gets the value of a local number variable on an object. Local numbers use indices **12-28** and can store values **0-255** (unsigned byte).

#### Parameters

- `oObject`: Object to get the local variable from
- `nIndex`: Index of the local number (must be 12-28)

#### Returns

- Value of the local number (0-255)
- `0` if the local variable doesn't exist or index is invalid

#### Usage Examples

```nss
// Get local number from self
int nQuestState = GetLocalNumber(OBJECT_SELF, 12);
if (nQuestState == 1) {
    // Quest state is 1
}
```

```nss
// Get local number from another object
object oNPC = GetObjectByTag("merchant");
int nTalkCount = GetLocalNumber(oNPC, 12);
```

**Pattern: Check Object State**

```nss
// Check if object has been interacted with
int nInteracted = GetLocalNumber(OBJECT_SELF, 12);
if (nInteracted == 0) {
    // First interaction
    SetLocalNumber(OBJECT_SELF, 12, 1);
}
```

#### Notes

- **Index Range:** Must be 12-28
- **Value Range:** 0-255 (unsigned byte)
- **Default:** Returns 0 if variable not set

---

### SetLocalNumber

**Routine:** 682

#### Function Signature

```nss
void SetLocalNumber(object oObject, int nIndex, int nValue);
```

#### Description

Sets the value of a local number variable on an object. **Value must be in range 0-255**.

#### Parameters

- `oObject`: Object to set the local variable on
- `nIndex`: Index of the local number (must be 12-28)
- `nValue`: Value to set (must be 0-255)

#### Usage Examples

```nss
// Set local number on self
SetLocalNumber(OBJECT_SELF, 12, 5);
```

```nss
// Set local number on another object
object oNPC = GetObjectByTag("npc");
SetLocalNumber(oNPC, 12, 1);
```

**Pattern: Increment Local Number**

```nss
// Increment a counter
int nCurrent = GetLocalNumber(OBJECT_SELF, 12);
SetLocalNumber(OBJECT_SELF, 12, nCurrent + 1);
```

**Pattern: Script Parameter Helper**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/a_localn_set.nss
int nParam1 = GetScriptParameter(1);
int nParam2 = GetScriptParameter(2);
SetLocalNumber(OBJECT_SELF, nParam1, nParam2);
```

#### Notes

- **Index Range:** Must be 12-28
- **Value Range:** 0-255 (unsigned byte, unlike global numbers which are -128 to +127)
- **Overflow:** Values > 255 will wrap or cause errors

---

## Local Boolean Functions

### GetLocalBoolean

**Routine:** 679

#### Function Signature

```nss
int GetLocalBoolean(object oObject, int nIndex);
```

#### Description

Gets the value of a local boolean variable on an object. Local booleans use indices **20-63**.

#### Parameters

- `oObject`: Object to get the local boolean from
- `nIndex`: Index of the local boolean (must be 20-63)

#### Returns

- `TRUE` (1) if the boolean is `TRUE`
- `FALSE` (0) if the boolean is `FALSE` or not set

#### Usage Examples

```nss
// Get local boolean from self
int bHasTalked = GetLocalBoolean(OBJECT_SELF, 20);
if (!bHasTalked) {
    // First time talking
    SetLocalBoolean(OBJECT_SELF, 20, TRUE);
}
```

```nss
// Check flag on another object
object oNPC = GetObjectByTag("merchant");
if (GetLocalBoolean(oNPC, 20)) {
    // NPC has specific flag set
}
```

**Pattern: One-Time Events**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
if (!GetLocalBoolean(OBJECT_SELF, 50)) {
    SetLocalBoolean(OBJECT_SELF, 50, 1);
    // Do one-time event
}
```

---

### SetLocalBoolean

**Routine:** 680

#### Function Signature

```nss
void SetLocalBoolean(object oObject, int nIndex, int nValue);
```

#### Description

Sets the value of a local boolean variable on an object. Any non-zero value is treated as `TRUE`, zero is `FALSE`.

#### Parameters

- `oObject`: Object to set the local boolean on
- `nIndex`: Index of the local boolean (must be 20-63)
- `nValue`: Value to set (`TRUE`/`FALSE` or any non-zero/zero)

#### Usage Examples

```nss
// Set local boolean on self
SetLocalBoolean(OBJECT_SELF, 20, TRUE);
```

```nss
// Clear flag
SetLocalBoolean(OBJECT_SELF, 20, FALSE);
```

```nss
// Set flag on another object
object oNPC = GetObjectByTag("npc");
SetLocalBoolean(oNPC, 20, TRUE);
```

---

## Local String Functions

### GetLocalString

**Routine:** 683

#### Function Signature

```nss
string GetLocalString(object oObject, int nIndex);
```

#### Description

Gets the value of a local string variable on an object. Local strings use indices **0-9** (10 slots).

#### Parameters

- `oObject`: Object to get the local string from
- `nIndex`: Index of the local string (must be 0-9)

#### Returns

- String value of the local variable
- Empty string ("") if the variable doesn't exist or index is invalid

#### Usage Examples

```nss
// Get local string
string sName = GetLocalString(OBJECT_SELF, 0);
if (sName != "") {
    SpeakString("My name is " + sName, TALKVOLUME_TALK);
}
```

---

### SetLocalString

**Routine:** 684

#### Function Signature

```nss
void SetLocalString(object oObject, int nIndex, string sValue);
```

#### Description

Sets the value of a local string variable on an object.

#### Parameters

- `oObject`: Object to set the local string on
- `nIndex`: Index of the local string (must be 0-9)
- `sValue`: String value to set

#### Usage Examples

```nss
// Store data in local string
SetLocalString(OBJECT_SELF, 0, "CustomName");
```

---

## Local Object Functions

### GetLocalObject

**Routine:** 685

#### Function Signature

```nss
object GetLocalObject(object oObject, int nIndex);
```

#### Description

Gets the value of a local object variable. Stores a reference to another object.

#### Parameters

- `oObject`: Object to get the local object from
- `nIndex`: Index of the local object

#### Returns

- Object reference stored in the local variable
- `OBJECT_INVALID` if not set or invalid

#### Usage Examples

```nss
// Store and retrieve object reference
object oTarget = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
SetLocalObject(OBJECT_SELF, 0, oTarget);

// Later, retrieve it
object oStored = GetLocalObject(OBJECT_SELF, 0);
if (GetIsObjectValid(oStored)) {
    // Use stored object
}
```

---

### SetLocalObject

**Routine:** 686

#### Function Signature

```nss
void SetLocalObject(object oObject, int nIndex, object oValue);
```

#### Description

Sets the value of a local object variable.

#### Parameters

- `oObject`: Object to set the local object on
- `nIndex`: Index of the local object
- `oValue`: Object reference to store

#### Usage Examples

```nss
// Store object reference
SetLocalObject(OBJECT_SELF, 0, oTarget);
```

---

## Common Patterns and Best Practices

### Pattern: First-Time Interaction

```nss
// Check if NPC has been talked to
int bHasTalked = GetLocalBoolean(OBJECT_SELF, 20);
if (!bHasTalked) {
    SetLocalBoolean(OBJECT_SELF, 20, TRUE);
    // First interaction dialogue
} else {
    // Repeat interaction dialogue
}
```

### Pattern: Quest State Tracking

```nss
// Track quest progress on NPC
int nQuestState = GetLocalNumber(OBJECT_SELF, 12);
if (nQuestState == 0) {
    // Quest not started
} else if (nQuestState == 1) {
    // Quest in progress
} else if (nQuestState == 2) {
    // Quest completed
}
```

### Pattern: Interaction Counter

```nss
// Count interactions
int nInteractions = GetLocalNumber(OBJECT_SELF, 12);
nInteractions++;
SetLocalNumber(OBJECT_SELF, 12, nInteractions);

if (nInteractions >= 3) {
    // Third interaction special dialogue
}
```

### Pattern: Store Object Reference

```nss
// Store target for later use
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oEnemy)) {
    SetLocalObject(OBJECT_SELF, 0, oEnemy);
}

// Later, retrieve stored enemy
object oStoredEnemy = GetLocalObject(OBJECT_SELF, 0);
if (GetIsObjectValid(oStoredEnemy)) {
    ActionAttack(oStoredEnemy);
}
```

### Best Practices

1. **Use Consistent Indices**: Define constants for local variable indices at the top of scripts
2. **Respect Index Ranges**: Don't use indices outside the valid ranges (Numbers: 12-28, Booleans: 20-63, Strings: 0-9)
3. **Respect Value Ranges**: Local numbers are 0-255 (unsigned), not -128 to +127 like globals
4. **Document Index Usage**: Comment which indices are used for what purpose
5. **Validate Objects**: Always validate objects before getting/setting local variables
6. **Use Booleans for Flags**: Use boolean indices for simple true/false state
7. **Use Numbers for Counters**: Use number indices for counters and state values

### Index Organization Strategy

**Recommended Index Allocation:**

- **Numbers 12-14:** Quest/state tracking (common)
- **Numbers 15-20:** General counters and temporary values
- **Booleans 20-30:** Common flags (first interaction, quest started, etc.)
- **Booleans 31-50:** Quest-specific flags
- **Booleans 51-63:** Special/rare flags
- **Strings 0-2:** Common string data
- **Strings 3-9:** Special/rare string data

---

## Differences from Global Variables

| Feature | Global Variables | Local Variables |
|---------|------------------|-----------------|
| **Scope** | Campaign-wide | Object-specific |
| **Storage** | Campaign/save game | On individual objects |
| **Naming** | String identifiers | Numeric indices |
| **Number Range** | -128 to +127 (signed) | 0-255 (unsigned) |
| **Persistence** | Persists across all sessions | Persists with object |
| **Use Case** | Quest tracking, game state | Object state, NPC flags |

---

## Related Functions

- `GetGlobalNumber()` / `SetGlobalNumber()` - Global variables (see [Global Variables](NSS-Shared-Functions-Global-Variables))
- `GetGlobalBoolean()` / `SetGlobalBoolean()` - Global booleans
- `GetIsObjectValid()` - Validate objects before accessing local variables

---

## Additional Notes

### Index Range Validation

The engine may not validate index ranges. Using invalid indices can cause:

- Undefined behavior
- Script errors
- Save game corruption

**Always use valid index ranges:**

- Numbers: 12-28
- Booleans: 20-63
- Strings: 0-9

### Local Variable Persistence

Local variables persist in save games because they're stored on the objects themselves. When an area is saved and reloaded, local variables on objects in that area are preserved.

### Migration from Global Variables

If you need to track state per-object (not campaign-wide), use local variables:

- **Use Globals:** Quest completion, campaign-wide flags, save game state
- **Use Locals:** NPC-specific state, object interaction counts, per-instance data
