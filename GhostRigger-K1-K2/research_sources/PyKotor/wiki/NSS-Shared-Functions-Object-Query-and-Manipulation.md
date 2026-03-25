# Object Query and Manipulation Functions

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript object query and manipulation functions. These functions allow scripts to find objects, check object validity, get object properties, and manipulate objects in the game world.

---

## Object Validation

### GetIsObjectValid

**Routine:** 291

#### Function Signature

```nss
int GetIsObjectValid(object oObject);
```

#### Description

Checks if an object is valid (exists and is accessible). **Always use this function** before using an object returned from other functions, as they may return `OBJECT_INVALID` if no object is found.

#### Parameters

- `oObject`: Object to validate

#### Returns

- `TRUE` if object is valid
- `FALSE` if object is invalid or `OBJECT_INVALID`

#### Usage Examples

```nss
// Validate object before use
object oNPC = GetObjectByTag("merchant");
if (GetIsObjectValid(oNPC)) {
    ActionStartConversation(oNPC);
}
```

```nss
// Check if object exists before operations
object oTarget = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oTarget)) {
    ActionAttack(oTarget);
} else {
    // No enemy found
}
```

**Pattern: Always Validate Objects**

```nss
// Standard pattern for object queries
object oResult = GetObjectByTag("my_object");
if (GetIsObjectValid(oResult)) {
    // Safe to use oResult
    DoSomething(oResult);
} else {
    // Object not found, handle error
}
```

#### Notes

- **Critical:** Always validate objects before use to avoid script errors
- Functions like `GetObjectByTag()`, `GetNearestCreature()` return `OBJECT_INVALID` if no object is found
- Using invalid objects in functions can cause script errors or crashes

---

## Finding Objects by Tag

### GetObjectByTag

**Routine:** 3046

#### Function Signature

```nss
object GetObjectByTag(string sTag, int nNth = 0);
```

#### Description

Finds an object by its tag. Tags are unique identifiers assigned to objects in the game editor. If multiple objects share the same tag, use `nNth` to get a specific instance.

#### Parameters

- `sTag`: Tag of the object to find (case-sensitive)
- `nNth`: Which instance to return if multiple objects share the tag (0 = first, 1 = second, etc.)

#### Returns

- Object with the specified tag
- `OBJECT_INVALID` if no object with that tag is found

#### Usage Examples

```nss
// Get first object with tag
object oNPC = GetObjectByTag("merchant");
if (GetIsObjectValid(oNPC)) {
    ActionStartConversation(oNPC);
}
```

```nss
// Get specific instance (second object with tag)
object oWaypoint = GetObjectByTag("wp_patrol", 1);
```

**Pattern: Find Object and Validate**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
object oKreia = GetObjectByTag("kreia", 0);
if (GetIsObjectValid(oKreia)) {
    AssignCommand(oKreia, ClearAllActions());
    // ... use oKreia
}
```

#### Notes

- Tags are case-sensitive
- If multiple objects share a tag, they are ordered by creation/load order
- Always validate the result with `GetIsObjectValid()`
- Tags are set in the game editor (UTC, GIT, etc.)

---

## Finding Creatures

### GetNearestCreature

**Routine:** 2271

#### Function Signature

```nss
object GetNearestCreature(
    int nFirstCriteriaType,
    int nFirstCriteriaValue,
    object oTarget = OBJECT_SELF,
    int nNth = 1,
    int nSecondCriteriaType = -1,
    int nSecondCriteriaValue = -1,
    int nThirdCriteriaType = -1,
    int nThirdCriteriaValue = -1
);
```

#### Description

Finds the nearest creature matching specified criteria. This is the primary function for finding NPCs, enemies, allies, etc. based on various filters.

#### Parameters

- `nFirstCriteriaType`: Primary search criteria type:
  - `CREATURE_TYPE_PLAYER_CHAR` - Player character
  - `CREATURE_TYPE_REPUTATION` - By reputation
  - `CREATURE_TYPE_IS_ALIVE` - Living creatures
  - `CREATURE_TYPE_IS_DEAD` - Dead creatures
  - `CREATURE_TYPE_RACE` - By race
  - `CREATURE_TYPE_CLASS` - By class
  - `CREATURE_TYPE_PERCEPTION` - By perception
  - `CREATURE_TYPE_DOES_NOT_HAVE_SPELL_EFFECT` - Without spell effect
  - `CREATURE_TYPE_HAS_SPELL_EFFECT` - With spell effect
- `nFirstCriteriaValue`: Value for first criteria (e.g., `REPUTATION_TYPE_ENEMY`, `TRUE`/`FALSE` for alive/dead)
- `oTarget`: Reference object to measure distance from (default: `OBJECT_SELF`)
- `nNth`: Which nearest creature to return (1 = nearest, 2 = second nearest, etc.)
- `nSecondCriteriaType` through `nThirdCriteriaValue`: Additional optional criteria filters

#### Returns

- Nearest creature matching criteria
- `OBJECT_INVALID` if no matching creature found

#### Usage Examples

```nss
// Find nearest enemy
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oEnemy)) {
    ActionAttack(oEnemy);
}
```

```nss
// Find nearest living creature
object oAlive = GetNearestCreature(CREATURE_TYPE_IS_ALIVE, TRUE);
```

```nss
// Find nearest enemy to specific target
object oPC = GetFirstPC();
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY, oPC);
```

**Pattern: Find Enemy for Combat**

```nss
// Standard combat AI pattern
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oEnemy) && !GetIsInCombat()) {
    ClearAllActions();
    ActionAttack(oEnemy);
}
```

**Pattern: Multiple Criteria**

```nss
// Find nearest living enemy
object oTarget = GetNearestCreature(
    CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY,
    OBJECT_SELF, 1,
    CREATURE_TYPE_IS_ALIVE, TRUE
);
```

#### Common Criteria Combinations

**Find Nearest Enemy:**

```nss
GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY)
```

**Find Nearest Ally:**

```nss
GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_FRIEND)
```

**Find Nearest Living Creature:**

```nss
GetNearestCreature(CREATURE_TYPE_IS_ALIVE, TRUE)
```

**Find Nearest Dead Creature:**

```nss
GetNearestCreature(CREATURE_TYPE_IS_DEAD, TRUE)
```

#### Implementation Reference

- [`vendor/xoreos/src/engines/kotorbase/script/functions_object.cpp:220-234`](https://github.com/th3w1zard1/xoreos/blob/master/src/engines/kotorbase/script/functions_object.cpp#L220-L234)

---

## Distance Functions

### GetDistanceBetween

**Routine:** 2825

#### Function Signature

```nss
float GetDistanceBetween(object oObjectA, object oObjectB);
```

#### Description

Gets the 3D distance (in meters) between two objects. Uses full 3D distance calculation including Z-axis (height).

#### Parameters

- `oObjectA`: First object
- `oObjectB`: Second object

#### Returns

- Distance in meters between the two objects
- `0.0` if either object is invalid

#### Usage Examples

```nss
// Check distance to target
object oTarget = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oTarget)) {
    float fDistance = GetDistanceBetween(OBJECT_SELF, oTarget);
    if (fDistance > 10.0) {
        // Target too far, move closer
        ActionMoveToObject(oTarget, FALSE, 1.0);
    }
}
```

```nss
// Check if within range
object oNPC = GetObjectByTag("merchant");
if (GetIsObjectValid(oNPC)) {
    float fDist = GetDistanceBetween(GetFirstPC(), oNPC);
    if (fDist <= 5.0) {
        // Close enough to interact
        ActionStartConversation(oNPC);
    }
}
```

---

### GetDistanceBetween2D

**Routine:** 319

#### Function Signature

```nss
float GetDistanceBetween2D(object oObjectA, object oObjectB);
```

#### Description

Gets the 2D distance (in meters) between two objects, ignoring height (Z-axis). Useful for ground-level distance calculations.

#### Parameters

- `oObjectA`: First object
- `oObjectB`: Second object

#### Returns

- 2D distance in meters (ignoring height)
- `0.0` if either object is invalid

#### Usage Examples

```nss
// Check horizontal distance (ignoring height differences)
float fDist2D = GetDistanceBetween2D(OBJECT_SELF, oTarget);
if (fDist2D <= 5.0) {
    // Within horizontal range
}
```

#### Notes

- Use `GetDistanceBetween2D()` when height differences don't matter (e.g., ground movement)
- Use `GetDistanceBetween()` when height matters (e.g., vertical distance checks)

---

## Location Functions

### GetLocation

**Routine:** 182

#### Function Signature

```nss
location GetLocation(object oObject);
```

#### Description

Gets the location (position + facing) of an object. Locations include X, Y, Z coordinates and facing angle.

#### Parameters

- `oObject`: Object to get location from

#### Returns

- Location of the object
- Invalid location if object is invalid

#### Usage Examples

```nss
// Get object's location
object oWaypoint = GetObjectByTag("wp_spawn");
location lSpawn = GetLocation(oWaypoint);

// Use location for movement
ActionMoveToLocation(lSpawn, FALSE);
```

```nss
// Get PC location
location lPCLoc = GetLocation(GetFirstPC());
```

---

### Location

**Routine:** 1830

#### Function Signature

```nss
location Location(vector vPosition, float fOrientation);
```

#### Description

Creates a location from a position vector and orientation angle. Used to create custom locations for movement, effects, etc.

#### Parameters

- `vPosition`: Position vector (X, Y, Z coordinates)
- `fOrientation`: Facing angle in degrees (0 = East, 90 = North, 180 = West, 270 = South)

#### Returns

- Location object

#### Usage Examples

```nss
// Create custom location
vector vPos = Vector(10.0, 20.0, 0.0);
location lCustom = Location(vPos, 90.0); // Face north
ActionMoveToLocation(lCustom, FALSE);
```

```nss
// Create location from object's position with custom facing
object oTarget = GetObjectByTag("target");
vector vPos = GetPosition(oTarget);
location lFacing = Location(vPos, 180.0); // Face west
```

---

### GetPosition

**Routine:** 184

#### Function Signature

```nss
vector GetPosition(object oObject);
```

#### Description

Gets the position vector (X, Y, Z coordinates) of an object.

#### Parameters

- `oObject`: Object to get position from

#### Returns

- Position vector
- `[0.0, 0.0, 0.0]` if object is invalid

#### Usage Examples

```nss
// Get object position
vector vPos = GetPosition(GetFirstPC());
```

```nss
// Calculate offset position
vector vMyPos = GetPosition(OBJECT_SELF);
vector vOffset = Vector(vPos.x + 5.0, vPos.y, vPos.z);
location lNew = Location(vOffset, GetFacing(OBJECT_SELF));
```

---

### GetPositionFromLocation

**Routine:** 185

#### Function Signature

```nss
vector GetPositionFromLocation(location lLocation);
```

#### Description

Extracts the position vector from a location object.

#### Parameters

- `lLocation`: Location to extract position from

#### Returns

- Position vector from the location

#### Usage Examples

```nss
// Extract position from location
location lLoc = GetLocation(oTarget);
vector vPos = GetPositionFromLocation(lLoc);
```

---

## Object Properties

### GetTag

**Routine:** 236

#### Function Signature

```nss
string GetTag(object oObject);
```

#### Description

Gets the tag of an object. Tags are unique identifiers assigned in the game editor.

#### Parameters

- `oObject`: Object to get tag from

#### Returns

- Tag string of the object
- Empty string if object is invalid

#### Usage Examples

```nss
// Get object's tag
object oNPC = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oNPC)) {
    string sTag = GetTag(oNPC);
    // Use tag for identification
}
```

---

### GetName

**Routine:** 253

#### Function Signature

```nss
string GetName(object oObject);
```

#### Description

Gets the display name of an object (as shown to the player).

#### Parameters

- `oObject`: Object to get name from

#### Returns

- Display name of the object
- Empty string if object is invalid

#### Usage Examples

```nss
// Get object's display name
string sName = GetName(GetFirstPC());
SpeakString("Hello, " + sName + "!", TALKVOLUME_TALK);
```

---

### GetArea

**Routine:** 177

#### Function Signature

```nss
object GetArea(object oObject = OBJECT_SELF);
```

#### Description

Gets the area (module area) that contains the specified object.

#### Parameters

- `oObject`: Object to get area from (default: `OBJECT_SELF`)

#### Returns

- Area object
- `OBJECT_INVALID` if object is invalid

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

---

## Object Manipulation

### DestroyObject

**Routine:** 244

#### Function Signature

```nss
void DestroyObject(object oDestroy, float fDelay = 0.0, int bNoFade = FALSE, float fDelayUntilFade = 0.0);
```

#### Description

Destroys (removes) an object from the game world. The object is permanently removed and cannot be recovered.

#### Parameters

- `oDestroy`: Object to destroy
- `fDelay`: Delay in seconds before destruction (default: 0.0)
- `bNoFade`: If `TRUE`, object disappears instantly without fade (default: `FALSE`)
- `fDelayUntilFade`: Delay before fade starts (default: 0.0)

#### Usage Examples

```nss
// Immediate destruction
object oItem = GetObjectByTag("temp_item");
DestroyObject(oItem);
```

```nss
// Delayed destruction with fade
DestroyObject(oTarget, 2.0, FALSE, 1.0);
```

**Pattern: Destroy After Cutscene**

```nss
// Destroy object after cutscene completes
DelayCommand(5.0, DestroyObject(GetObjectByTag("cutscene_prop"), 0.0, FALSE, 0.0));
```

#### Notes

- Destroyed objects cannot be recovered
- Use with caution - ensure object is no longer needed
- Objects destroyed with delay can still be interacted with until destruction occurs

---

## Finding Waypoints

### GetWaypointByTag

**Routine:** 205

#### Function Signature

```nss
object GetWaypointByTag(string sTag);
```

#### Description

Finds a waypoint object by its tag. Waypoints are invisible markers used for movement, spawning, and scripting.

#### Parameters

- `sTag`: Tag of the waypoint to find

#### Returns

- Waypoint object
- `OBJECT_INVALID` if waypoint not found

#### Usage Examples

```nss
// Get waypoint and move to it
object oWP = GetWaypointByTag("wp_meeting");
if (GetIsObjectValid(oWP)) {
    ActionMoveToObject(oWP, FALSE, 1.0);
}
```

```nss
// Get waypoint location
object oWP = GetWaypointByTag("wp_spawn");
location lSpawn = GetLocation(oWP);
```

---

## Common Patterns and Best Practices

### Pattern: Find and Validate Object

```nss
// Standard pattern for object queries
object oResult = GetObjectByTag("my_object");
if (GetIsObjectValid(oResult)) {
    // Safe to use oResult
    DoSomething(oResult);
} else {
    // Handle error - object not found
}
```

### Pattern: Find Nearest Enemy

```nss
// Find and attack nearest enemy
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oEnemy)) {
    float fDist = GetDistanceBetween(OBJECT_SELF, oEnemy);
    if (fDist <= 10.0) {
        ClearAllActions();
        ActionAttack(oEnemy);
    } else {
        ActionMoveToObject(oEnemy, TRUE, 1.0);
    }
}
```

### Pattern: Distance Check Before Action

```nss
// Only interact if within range
object oNPC = GetObjectByTag("merchant");
if (GetIsObjectValid(oNPC)) {
    float fDist = GetDistanceBetween(GetFirstPC(), oNPC);
    if (fDist <= 5.0) {
        ActionStartConversation(oNPC);
    } else {
        ActionMoveToObject(oNPC, FALSE, 1.0);
    }
}
```

### Pattern: Find Multiple Objects

```nss
// Find all objects with same tag
int i = 0;
object oObj = GetObjectByTag("spawn_point", i);
while (GetIsObjectValid(oObj)) {
    // Do something with each object
    DoSomething(oObj);
    i++;
    oObj = GetObjectByTag("spawn_point", i);
}
```

### Best Practices

1. **Always Validate Objects**: Use `GetIsObjectValid()` before using any object returned from query functions
2. **Handle OBJECT_INVALID**: Query functions return `OBJECT_INVALID` when no object is found - always check for this
3. **Use Appropriate Distance Functions**: Use `GetDistanceBetween2D()` for ground-level checks, `GetDistanceBetween()` when height matters
4. **Cache Object References**: If you need to use an object multiple times, store it in a variable
5. **Check Tags Exist**: Verify objects exist before using their tags in scripts
6. **Use Waypoints for Movement**: Waypoints are the standard way to define movement targets

---

## Related Functions

- `GetFirstPC()` - Get the player character
- `GetEnteringObject()` - Get object that entered a trigger
- `GetExitingObject()` - Get object that exited a trigger
- `GetClickingObject()` - Get object that clicked on something
- `GetNearestObject()` - Find nearest object by type (if available)

---

## Additional Object Query Functions

Additional object query functions include:

- `GetNearestObject()` - Find nearest object by type (implementation dependent)
- `GetFirstObjectInShape()` - Find objects in a shape/area (TSL)
- `GetNextObjectInShape()` - Get next object in shape search (TSL)
- `GetObjectInArea()` - Find objects in specific area
- `GetObjectByID()` - Find object by unique ID (if available)

Each follows similar patterns to the functions documented above.
