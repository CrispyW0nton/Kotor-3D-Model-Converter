# Module and Area Functions

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript module and area functions. These functions allow scripts to get area information, detect area transitions, access the player character, and manage module/area state.

---

## Module and Area Fundamentals

### Understanding Modules and Areas

- **Module**: The overall game module (e.g., "Endar Spire", "Taris Upper City"). A module contains one or more areas.
- **Area**: A specific location within a module (e.g., "Upper City Cantina"). Players transition between areas via doors, triggers, or scripts.

### Area Events

When objects enter or exit areas/triggers, event scripts are fired:

- **OnEnter**: Fired when an object enters an area or trigger
- **OnExit**: Fired when an object exits an area or trigger

---

## Area Functions

### GetArea

**Routine:** 24

#### Function Signature

```nss
object GetArea(object oTarget = OBJECT_SELF);
```

#### Description

Gets the area object that contains the specified object. Every object in the game exists within an area.

#### Parameters

- `oTarget`: Object to get the area for (default: `OBJECT_SELF`)

#### Returns

- Area object containing the target
- `OBJECT_INVALID` if object is invalid or has no area

#### Usage Examples

```nss
// Get current area
object oArea = GetArea();
```

```nss
// Get area of specific object
object oNPC = GetObjectByTag("npc");
object oNPCArea = GetArea(oNPC);
```

```nss
// Check if object is in same area
object oPC = GetFirstPC();
object oTarget = GetObjectByTag("target");
if (GetArea(oPC) == GetArea(oTarget)) {
    // Objects are in the same area
}
```

**Pattern: Area-Specific Script Logic**

```nss
// Run logic only if in specific area
object oCurrentArea = GetArea();
string sAreaTag = GetTag(oCurrentArea);
if (sAreaTag == "tar_uppercity") {
    // Logic specific to Taris Upper City
}
```

---

## Area Transition Functions

### GetEnteringObject

**Routine:** 25

#### Function Signature

```nss
object GetEnteringObject();
```

#### Description

Gets the object that last entered the caller. The behavior depends on the object type of the caller:

- **Door or Placeable**: Returns the object that last triggered/used it
- **Trigger, Area, Module, or Encounter**: Returns the object that last entered it

This function is typically used in `OnEnter` event scripts.

#### Returns

- Object that entered/triggered the caller
- `OBJECT_INVALID` if no object entered or caller is invalid

#### Usage Examples

```nss
// In a trigger's OnEnter script
void main() {
    object oEntering = GetEnteringObject();
    if (GetIsPC(oEntering)) {
        // Player entered trigger
        SpeakString("You've entered the danger zone!", TALKVOLUME_TALK);
    }
}
```

**Pattern: Area Entry Detection**

```nss
// From vendor/K1_Community_Patch/Source/k_pman_init02.nss
void main() {
    object oEntering = GetEnteringObject();
    object oPC = GetFirstPC();
    
    if (IsObjectPartyMember(oEntering) && GetIsObjectValid(oPC)) {
        // Party member entered area - do something
        // ...
    }
}
```

**Pattern: PC Entry Check**

```nss
// Common pattern in area entry scripts
object oEntering = GetEnteringObject();
if (GetIsPC(oEntering)) {
    // Player entered - trigger events
    SetGlobalBoolean("AreaVisited", TRUE);
}
```

#### Notes

- Only works in event scripts (OnEnter, OnUsed, etc.)
- Returns the last object that entered, not all objects
- Always validate the returned object with `GetIsObjectValid()`

---

### GetExitingObject

**Routine:** 26

#### Function Signature

```nss
object GetExitingObject();
```

#### Description

Gets the object that last left the caller. This function works on triggers, areas of effect, modules, areas, and encounters.

This function is typically used in `OnExit` event scripts.

#### Returns

- Object that exited the caller
- `OBJECT_INVALID` if no object exited or caller is invalid

#### Usage Examples

```nss
// In a trigger's OnExit script
void main() {
    object oExiting = GetExitingObject();
    if (GetIsPC(oExiting)) {
        // Player left trigger
        SpeakString("You've left the safe zone!", TALKVOLUME_TALK);
    }
}
```

**Pattern: Area Exit Detection**

```nss
// Track when PC leaves area
void main() {
    object oExiting = GetExitingObject();
    if (GetIsPC(oExiting)) {
        // Save state when leaving
        location lExitPos = GetLocation(oExiting);
        SetGlobalLocation("LastExitLocation", lExitPos);
    }
}
```

#### Notes

- Only works in event scripts (OnExit, etc.)
- Returns the last object that exited
- Always validate the returned object

---

## Player Character Functions

### GetFirstPC

**Routine:** 348

#### Function Signature

```nss
object GetFirstPC();
```

#### Description

Gets the first player character (PC). In KotOR, there is typically only one player character, so this returns the main player.

This is the most common way to get a reference to the player character in scripts.

#### Returns

- Player character object
- `OBJECT_INVALID` if no PC exists

#### Usage Examples

```nss
// Get player character
object oPC = GetFirstPC();
```

```nss
// Common pattern: get PC and check validity
object oPC = GetFirstPC();
if (GetIsObjectValid(oPC)) {
    // Do something with PC
    ActionStartConversation(oPC);
}
```

**Pattern: PC Interaction**

```nss
// Start conversation with PC
object oPC = GetFirstPC();
object oNPC = GetObjectByTag("merchant");
AssignCommand(oNPC, ActionStartConversation(oPC));
```

**Pattern: PC Location Check**

```nss
// Check PC's location
object oPC = GetFirstPC();
object oTarget = GetObjectByTag("npc");
float fDistance = GetDistanceBetween(oPC, oTarget);

if (fDistance <= 5.0) {
    // PC is close enough to interact
}
```

#### Notes

- Always returns the player character (main PC)
- In single-player games, this is the only PC
- Always validate with `GetIsObjectValid()` before use
- Prefer this over `GetPartyLeader()` for getting the main PC

---

## Common Patterns and Best Practices

### Pattern: Area Entry Detection

```nss
// In area's OnEnter script
void main() {
    object oEntering = GetEnteringObject();
    if (GetIsPC(oEntering)) {
        // Player entered area
        SetGlobalBoolean("AreaVisited", TRUE);
        
        // First-time visit logic
        if (!GetGlobalBoolean("AreaFirstVisit")) {
            SetGlobalBoolean("AreaFirstVisit", TRUE);
            // Show welcome message, etc.
        }
    }
}
```

### Pattern: Trigger-Based Events

```nss
// In trigger's OnEnter script
void main() {
    object oEntering = GetEnteringObject();
    
    if (GetIsPC(oEntering)) {
        // Player entered trigger
        object oNPC = GetObjectByTag("guard");
        if (GetIsObjectValid(oNPC)) {
            // Guard reacts to player
            AssignCommand(oNPC, ActionStartConversation(oEntering));
        }
    }
}
```

### Pattern: Area-Specific Logic

```nss
// Check current area and run area-specific code
object oCurrentArea = GetArea();
string sAreaTag = GetTag(oCurrentArea);

if (sAreaTag == "tar_uppercity") {
    // Taris Upper City specific logic
} else if (sAreaTag == "tar_lowercity") {
    // Lower City specific logic
}
```

### Pattern: PC Validation Before Actions

```nss
// Always validate PC before using
object oPC = GetFirstPC();
if (GetIsObjectValid(oPC)) {
    // Safe to use oPC
    int nHP = GetCurrentHitPoints(oPC);
    if (nHP < 50) {
        // Low HP - heal PC
        effect eHeal = EffectHeal(100);
        ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oPC);
    }
}
```

### Best Practices

1. **Always Validate Objects**: Check `GetIsObjectValid()` before using objects from `GetEnteringObject()` or `GetExitingObject()`
2. **Use GetFirstPC() for Main PC**: Use `GetFirstPC()` to get the main player character
3. **Check Object Type**: Verify objects with `GetIsPC()` before assuming they're the player
4. **Area Entry Scripts**: Use `GetEnteringObject()` in OnEnter scripts, `GetExitingObject()` in OnExit scripts
5. **Get Area Once**: Store area reference if you need it multiple times
6. **Event Scripts Only**: `GetEnteringObject()` and `GetExitingObject()` only work in event scripts

---

## Module Functions

### GetModule

**Routine:** 2900

#### Function Signature

```nss
object GetModule();
```

#### Description

Gets the module object. The module object represents the overall game module.

#### Returns

- Module object
- `OBJECT_INVALID` if module is not available

#### Usage Examples

```nss
// Get module object
object oModule = GetModule();
```

---

### StartNewModule

**Routine:** 4075

#### Function Signature

```nss
void StartNewModule(string sModuleName, string sWayPoint = "", string sMovie1 = "", string sMovie2 = "", string sMovie3 = "", string sMovie4 = "", string sMovie5 = "", string sMovie6 = "");
```

#### Description

Transitions to a new module. This loads a different module file (`.mod`). The current module is unloaded and the new module is loaded.

#### Parameters

- `sModuleName`: Name of the module file (without `.mod` extension) to load
- `sWayPoint`: Waypoint tag to spawn at in the new module (optional)
- `sMovie1` through `sMovie6`: Movie files (`.bik`) to play during transition (optional, up to 6)

#### Usage Examples

```nss
// Transition to new module
StartNewModule("new_module");
```

```nss
// Transition to module with waypoint
StartNewModule("new_module", "wp_entry");
```

```nss
// Transition with cutscene
StartNewModule("new_module", "wp_entry", "intro_cutscene.bik");
```

#### Notes

- Current module state is saved before transition
- Party members are preserved across transitions
- Module transitions can take time - scripts continue immediately but loading happens asynchronously

---

## Related Functions

- `GetObjectByTag()` - Find objects by tag (see [Object Query](NSS-Shared-Functions-Object-Query-and-Manipulation))
- `GetTag()` - Get object's tag (useful for area identification) - see [Object Query](NSS-Shared-Functions-Object-Query-and-Manipulation)
- `GetIsPC()` - Check if object is player character - see [Object Query](NSS-Shared-Functions-Object-Query-and-Manipulation)
- `GetPartyLeader()` - Get party leader (may differ from GetFirstPC in some contexts)

---

## Additional Notes

### Area Events

Area and trigger event scripts are fired automatically:

- **OnEnter**: When an object enters the area/trigger
- **OnExit**: When an object exits the area/trigger
- **OnHeartbeat**: Periodically while objects are in the area
- **OnUserDefined**: Custom events

Use `GetEnteringObject()` and `GetExitingObject()` in these event scripts to react to objects entering/exiting.

### Player Character Access

`GetFirstPC()` is the standard way to access the player character. It:

- Returns the main player character
- Works in all script contexts
- Should always be validated before use

### Area Object

The area object returned by `GetArea()`:

- Can be used with `GetTag()` to identify the area
- Contains all objects within that area
- Used for area-specific scripting

### Module vs. Area

- **Module**: The overall game module file (`.mod`)
- **Area**: A specific location within the module (`.are` file)

A module can contain multiple areas. `GetArea()` returns the current area the object is in, not the module.
