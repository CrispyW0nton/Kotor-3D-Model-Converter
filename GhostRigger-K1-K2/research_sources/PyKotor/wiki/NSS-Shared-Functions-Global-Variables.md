# Global Variables

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript global variable functions. Global variables are stored at the campaign/save game level and persist across areas and sessions.

---

## Global Variables Fundamentals

### Understanding Global Variables

Global variables are stored at the **campaign level** and persist across:

- Area transitions
- Save/load operations
- Module changes
- Multiple sessions

Global variables are defined in the `globalcat.2da` file, which specifies:

- Variable names
- Variable types (Number, Boolean, String, Location)
- Initial values

**⚠️ IMPORTANT:** Global **Numbers** are limited to **-128 to +127** (signed byte range). Values outside this range will cause errors or undefined behavior.

---

## Global Number Functions

### GetGlobalNumber

**Routine:** 580

#### Function Signature

```nss
int GetGlobalNumber(string sIdentifier);
```

#### Description

Gets the value of a global number variable. Global numbers are stored as signed bytes with a range of **-128 to +127**.

#### Parameters

- `sIdentifier`: Name of the global variable (must match name in `globalcat.2da`)

#### Returns

- Value of the global number (-128 to +127)
- `0` if the global doesn't exist

#### Usage Examples

```nss
// Get global number
int nQuestProgress = GetGlobalNumber("MyQuest_Progress");
if (nQuestProgress >= 3) {
    // Quest advanced enough
}
```

```nss
// Check quest state
int nLightsaber = GetGlobalNumber("904MAL_Lightsaber");
if (nLightsaber == 3) {
    // Third lightsaber obtained
    // Trigger event...
}
```

**Pattern: Quest Tracking**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
int nLightsaber = GetGlobalNumber("904MAL_Lightsaber");
if (nLightsaber == 3) {
    // Quest completed
    // Do something...
}
```

#### Notes

- **Range Limit:** Global numbers must be between -128 and +127
- **Variable Names:** Must be defined in `globalcat.2da` or created dynamically
- **Case Sensitivity:** Variable names are typically case-insensitive (stored lowercase)

---

### SetGlobalNumber

**Routine:** 581

#### Function Signature

```nss
void SetGlobalNumber(string sIdentifier, int nValue);
```

#### Description

Sets the value of a global number variable. **Value must be in range -128 to +127**.

#### Parameters

- `sIdentifier`: Name of the global variable
- `nValue`: Value to set (must be between -128 and +127)

#### Usage Examples

```nss
// Set global number
SetGlobalNumber("MyQuest_Progress", 1);
```

```nss
// Increment global (manual)
int nCurrent = GetGlobalNumber("Counter");
if (nCurrent < 127) {
    SetGlobalNumber("Counter", nCurrent + 1);
}
```

#### Notes

- **Range Limit:** Values outside -128 to +127 may cause errors
- **Auto-creation:** If the global doesn't exist, it may be created automatically (implementation dependent)

---

### IncrementGlobalNumber

**Routine:** 799

#### Function Signature

```nss
void IncrementGlobalNumber(string sIdentifier, int nAmount);
```

#### Description

Increments a global number by the specified amount. Convenience function that automatically handles range checking.

**⚠️ WARNING:** Will fail with a warning if the result exceeds 127 (the maximum value).

#### Parameters

- `sIdentifier`: Name of the global variable
- `nAmount`: Amount to increment by (can be negative to decrement)

#### Usage Examples

```nss
// Increment by 1
IncrementGlobalNumber("MyQuest_Progress", 1);
```

```nss
// Increment by specific amount
IncrementGlobalNumber("Counter", 5);
```

**Pattern: Quest Progress Tracking**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
IncrementGlobalNumber("904MAL_Lightsaber", 1);
if (GetGlobalNumber("904MAL_Lightsaber") == 3) {
    // Trigger event after 3 increments
}
```

#### Notes

- Only works with Number type globals, not Booleans
- Result must not exceed 127 or be less than -128
- Convenient for counters and progress tracking

---

### DecrementGlobalNumber

**Routine:** 800

#### Function Signature

```nss
void DecrementGlobalNumber(string sIdentifier, int nAmount);
```

#### Description

Decrements a global number by the specified amount. Convenience function that automatically handles range checking.

**⚠️ WARNING:** Will fail with a warning if the result is less than -128 (the minimum value).

#### Parameters

- `sIdentifier`: Name of the global variable
- `nAmount`: Amount to decrement by (must be positive)

#### Usage Examples

```nss
// Decrement by 1
DecrementGlobalNumber("Lives_Remaining", 1);
```

```nss
// Decrement by specific amount
DecrementGlobalNumber("Health_Points", 10);
```

#### Notes

- Only works with Number type globals
- Result must not be less than -128

---

## Global Boolean Functions

### GetGlobalBoolean

**Routine:** 578

#### Function Signature

```nss
int GetGlobalBoolean(string sIdentifier);
```

#### Description

Gets the value of a global boolean variable. Returns `TRUE` (1) or `FALSE` (0).

#### Parameters

- `sIdentifier`: Name of the global boolean variable

#### Returns

- `TRUE` (1) if the global is `TRUE`
- `FALSE` (0) if the global is `FALSE` or doesn't exist

#### Usage Examples

```nss
// Check global boolean
if (GetGlobalBoolean("Quest_Completed")) {
    // Quest is complete
}
```

```nss
// Check if flag is set
int bHasMetNPC = GetGlobalBoolean("HasMetMerchant");
if (!bHasMetNPC) {
    // First meeting
    SetGlobalBoolean("HasMetMerchant", TRUE);
}
```

---

### SetGlobalBoolean

**Routine:** 579

#### Function Signature

```nss
void SetGlobalBoolean(string sIdentifier, int nValue);
```

#### Description

Sets the value of a global boolean variable. Any non-zero value is treated as `TRUE`, zero is `FALSE`.

#### Parameters

- `sIdentifier`: Name of the global boolean variable
- `nValue`: Value to set (`TRUE`/`FALSE` or any non-zero/zero)

#### Usage Examples

```nss
// Set global boolean
SetGlobalBoolean("Quest_Completed", TRUE);
```

```nss
// Set flag
SetGlobalBoolean("HasMetNPC", TRUE);
```

```nss
// Clear flag
SetGlobalBoolean("Temporary_Flag", FALSE);
```

---

## Global String Functions

### GetGlobalString

**Routine:** 583

#### Function Signature

```nss
string GetGlobalString(string sIdentifier);
```

#### Description

Gets the value of a global string variable. Strings can store arbitrary text data.

#### Parameters

- `sIdentifier`: Name of the global string variable

#### Returns

- String value of the global
- Empty string ("") if the global doesn't exist

#### Usage Examples

```nss
// Get global string
string sPlayerName = GetGlobalString("Player_CustomName");
if (sPlayerName != "") {
    SpeakString("Welcome back, " + sPlayerName + "!", TALKVOLUME_TALK);
}
```

```nss
// Store and retrieve save data
SetGlobalString("LastArea", "Taris_UpperCity");
string sLastArea = GetGlobalString("LastArea");
```

---

### SetGlobalString

**Routine:** 584

#### Function Signature

```nss
void SetGlobalString(string sIdentifier, string sValue);
```

#### Description

Sets the value of a global string variable.

#### Parameters

- `sIdentifier`: Name of the global string variable
- `sValue`: String value to set

#### Usage Examples

```nss
// Set global string
SetGlobalString("Player_CustomName", "Revan");
```

```nss
// Store location name
SetGlobalString("LastVisitedArea", "Dantooine_Enclave");
```

---

## Global Location Functions

### GetGlobalLocation

**Routine:** 585

#### Function Signature

```nss
location GetGlobalLocation(string sIdentifier);
```

#### Description

Gets the value of a global location variable. Locations store position (X, Y, Z) and facing angle.

#### Parameters

- `sIdentifier`: Name of the global location variable

#### Returns

- Location value of the global
- Invalid location if the global doesn't exist

#### Usage Examples

```nss
// Get saved location
location lSavedLocation = GetGlobalLocation("LastSafeLocation");
if (GetIsObjectValid(lSavedLocation)) {
    ActionJumpToLocation(lSavedLocation);
}
```

---

### SetGlobalLocation

**Routine:** 586

#### Function Signature

```nss
void SetGlobalLocation(string sIdentifier, location lValue);
```

#### Description

Sets the value of a global location variable.

#### Parameters

- `sIdentifier`: Name of the global location variable
- `lValue`: Location value to set

#### Usage Examples

```nss
// Save current location
location lCurrent = GetLocation(GetFirstPC());
SetGlobalLocation("LastSafeLocation", lCurrent);
```

---

## Common Patterns and Best Practices

### Pattern: Quest Progress Tracking

```nss
// Track quest progress with global number
int nProgress = GetGlobalNumber("Quest_Progress");
if (nProgress < 5) {
    IncrementGlobalNumber("Quest_Progress", 1);
    nProgress = GetGlobalNumber("Quest_Progress");
    if (nProgress == 5) {
        // Quest milestone reached
        SetGlobalBoolean("Quest_MilestoneReached", TRUE);
    }
}
```

### Pattern: Flag-Based Logic

```nss
// Use boolean flags for state tracking
if (!GetGlobalBoolean("HasMetMerchant")) {
    // First interaction
    SetGlobalBoolean("HasMetMerchant", TRUE);
    // Show introduction dialogue
} else {
    // Repeat interaction
    // Show normal dialogue
}
```

### Pattern: Counter with Range Check

```nss
// Safe counter increment
int nCurrent = GetGlobalNumber("ItemCount");
if (nCurrent < 127) {
    IncrementGlobalNumber("ItemCount", 1);
} else {
    // Handle overflow - maybe use boolean flags for higher counts
    SetGlobalBoolean("ItemCount_Overflow", TRUE);
}
```

### Pattern: Quest Completion Tracking

```nss
// Mark quest as complete
SetGlobalBoolean("Quest_Completed", TRUE);
SetGlobalNumber("Quest_CompletionCount", GetGlobalNumber("Quest_CompletionCount") + 1);

// Check completion
if (GetGlobalBoolean("Quest_Completed")) {
    // Quest is done
}
```

### Best Practices

1. **Respect Number Range**: Global numbers are limited to -128 to +127
2. **Use Booleans for Flags**: For simple true/false state, use booleans instead of numbers
3. **Use Descriptive Names**: Use clear, descriptive names for globals (e.g., "Quest_Taris_Complete" not "q1")
4. **Check Before Increment**: Always check range before incrementing global numbers
5. **Initialize in globalcat.2da**: Define globals in `globalcat.2da` for better organization
6. **Use Strings for Complex Data**: For data that doesn't fit in -128 to +127, use strings or multiple numbers

---

## Related Functions

- `GetLocalNumber()` / `SetLocalNumber()` - Local object variables (see [Local Variables](NSS-Shared-Functions-Local-Variables))
- `DeleteGlobalVariable()` - Delete a global variable (if available)
- `GetModule()` - Get current module (sometimes needed for global scope)

---

## Global Variable Limitations

### Number Range

Global numbers are **strictly limited** to -128 to +127 (signed byte). This is a fundamental limitation of the engine.

**Workarounds:**

- Use multiple global numbers for larger ranges (e.g., `Counter_Low`, `Counter_High`)
- Use boolean flags for tracking states (1 = true, 0 = false)
- Use strings to store numeric data as text (requires conversion)

### Variable Initialization

Global variables should be defined in `globalcat.2da` for proper initialization. However, they can be created dynamically at runtime (implementation dependent).

### Persistence

Global variables persist in save games. They are saved in the `GLOBALS` GFF file within save game folders.
