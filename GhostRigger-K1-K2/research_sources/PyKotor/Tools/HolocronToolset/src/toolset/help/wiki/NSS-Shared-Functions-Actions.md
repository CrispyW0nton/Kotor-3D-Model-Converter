# Actions

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript action functions. Actions are queued behaviors that execute sequentially on objects (typically creatures). Actions are non-blocking - they are added to an object's action queue and executed asynchronously.

---

## Action Queue Fundamentals

### Understanding the Action Queue

All actions are added to an object's **action queue**. The queue processes actions sequentially - each action must complete (or fail) before the next begins. Actions execute asynchronously, meaning script execution continues immediately after queuing an action.

### Key Concepts

- **Action Queue**: Each creature/object has a queue of pending actions
- **Sequential Execution**: Actions execute one at a time, in order
- **Non-Blocking**: Script execution continues immediately after queuing
- **Action Context**: Actions execute "as" the object (OBJECT_SELF refers to the acting object)
- **Movement Blocking**: Many actions (especially animations) require the object to be stationary

### Critical Function: ClearAllActions()

**⚠️ IMPORTANT:** Many actions (especially animations) **will not execute** if the object is moving or has movement actions queued. Always call `ClearAllActions()` first when you need reliable action execution.

---

## Core Action Queue Functions

### ClearAllActions

**Routine:** 9  
**Category:** Main Functions (not an action itself)

#### Function Signature

```nss
void ClearAllActions();
```

#### Description

Clears all actions from the caller's action queue and stops movement immediately. Sets the creature's movement type to `None`, which is required for many actions (especially animations) to execute.

**⚠️ Critical for ActionPlayAnimation and similar functions** - animations will not play if the creature is moving.

#### Usage Examples

```nss
// Stop current actions and prepare for new ones
ClearAllActions();
ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, -1.0);
```

```nss
// Clear actions on another object
object oNPC = GetObjectByTag("my_npc");
AssignCommand(oNPC, ClearAllActions());
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/object/creature.cpp:251-254`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/object/creature.cpp#L251-L254) - Sets movement type to None

---

### AssignCommand

**Routine:** 6  
**Category:** Main Functions

#### Function Signature

```nss
void AssignCommand(object oActionSubject, action aActionToAssign);
```

#### Description

Queues an action to execute on a different object. This is the primary way to make NPCs or other objects perform actions. The action executes "as" the target object (OBJECT_SELF in the action context refers to `oActionSubject`).

#### Parameters

- `oActionSubject`: The object that will execute the action
- `aActionToAssign`: The action to queue (any function that returns an `action` type)

#### Usage Examples

```nss
// Make an NPC move to a waypoint
object oNPC = GetObjectByTag("guard");
object oWaypoint = GetObjectByTag("wp_guard_spot");
AssignCommand(oNPC, ActionMoveToObject(oWaypoint, FALSE, 1.0));
```

```nss
// Chain multiple actions on another object
object oNPC = GetObjectByTag("patrol_guard");
AssignCommand(oNPC, ClearAllActions());
AssignCommand(oNPC, ActionMoveToLocation(lDestination, FALSE));
AssignCommand(oNPC, ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, -1.0));
```

#### Common Patterns

**Pattern: Execute Action After Movement**

```nss
object oNPC = GetObjectByTag("npc");
AssignCommand(oNPC, ActionMoveToObject(oTarget, FALSE, 1.0));
DelayCommand(2.0, AssignCommand(oNPC, ActionSpeakString("I've arrived!", TALKVOLUME_TALK)));
```

**Pattern: Clear Actions on Another Object**

```nss
AssignCommand(oNPC, ClearAllActions());
DelayCommand(0.2, AssignCommand(oNPC, ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL, 1.0, -1.0)));
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/script/routine/impl/main.cpp:130-141`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/script/routine/impl/main.cpp#L130-L141)

---

### DelayCommand

**Routine:** 7  
**Category:** Main Functions

#### Function Signature

```nss
void DelayCommand(float fSeconds, action aActionToDelay);
```

#### Description

Delays execution of an action by a specified number of seconds. The delayed action executes "as" the calling object (OBJECT_SELF in the delayed action refers to the caller, not necessarily the object that called DelayCommand).

#### Parameters

- `fSeconds`: Delay duration in seconds (can be fractional, e.g., 0.5)
- `aActionToDelay`: The action to execute after the delay

#### Usage Examples

```nss
// Delay a single action
DelayCommand(2.0, ActionSpeakString("This happens after 2 seconds", TALKVOLUME_TALK));
```

```nss
// Delay with AssignCommand for another object
object oNPC = GetObjectByTag("npc");
DelayCommand(1.5, AssignCommand(oNPC, ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL, 1.0, -1.0)));
```

**Pattern: Staggered Party Movement**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/a_move_party.nss
int i;
for(i = 1; i < 4; i++) {
    object oPC = GetPartyMemberByIndex(i - 1);
    if(GetIsObjectValid(oPC)) {
        DelayCommand(IntToFloat(iDelay + (iInterval * i)), 
            AssignCommand(oPC, ClearAllActions()));
        DelayCommand(IntToFloat(iDelay + (iInterval * i)),
            AssignCommand(oPC, ActionForceMoveToLocation(GetLocation(oWP), iRun)));
    }
}
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/script/routine/impl/main.cpp:143-154`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/script/routine/impl/main.cpp#L143-L154)

---

### ActionDoCommand

**Routine:** 294  
**Category:** Actions

#### Function Signature

```nss
void ActionDoCommand(action aActionToDo);
```

#### Description

Wraps a non-action function (or complex expression) so it can be queued as an action. This allows non-action functions like `SetFacing()`, `SetLocalString()`, or custom functions to be queued in the action sequence.

#### Parameters

- `aActionToDo`: An action (typically a function call that doesn't return an action)

#### Usage Examples

```nss
// Set facing as part of action queue
ActionMoveToLocation(lDestination, FALSE);
ActionDoCommand(SetFacing(GetFacingFromLocation(lDestination)));
ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, -1.0);
```

```nss
// Set local variables during action sequence
ActionMoveToObject(oTarget, FALSE, 1.0);
ActionDoCommand(SetLocalInt(OBJECT_SELF, "HasArrived", 1));
```

**Pattern: Face Target After Movement**

```nss
// From vendor/K1_Community_Patch/Source/cp_inc_k1.nss
void CP_ReturnToBase(location lLoc, int bRun = FALSE) {
    ClearAllActions();
    ActionMoveToLocation(lLoc, bRun);
    ActionDoCommand(SetFacing(GetFacingFromLocation(lLoc)));
    ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, 0.1);
}
```

#### Implementation Reference

- [`vendor/KotOR.js/src/actions/ActionDoCommand.ts`](https://github.com/th3w1zard1/KotOR.js/blob/master/src/actions/ActionDoCommand.ts)

---

## Movement Actions

### ActionMoveToObject

**Routine:** 22

#### Function Signature

```nss
void ActionMoveToObject(object oMoveTo, int bRun = FALSE, float fRange = 1.0);
```

#### Description

Moves the caller to a target object. The movement follows the walkmesh and avoids obstacles. Movement can be interrupted by combat or other actions.

#### Parameters

- `oMoveTo`: Target object to move towards
- `bRun`: Movement speed (0 = walk, 1 = run, non-zero = run)
- `fRange`: Distance to stop from the target (default 1.0 meters)

#### Usage Examples

```nss
// Walk to an NPC
object oTarget = GetObjectByTag("merchant");
ActionMoveToObject(oTarget, FALSE, 1.5);
```

```nss
// Run to a waypoint
object oWaypoint = GetWaypointByTag("wp_meeting");
ActionMoveToObject(oWaypoint, TRUE, 0.5);
```

#### Notes

- Movement follows walkmesh pathfinding
- Can be interrupted by combat or `ClearAllActions()`
- If `oMoveTo` becomes invalid during movement, the action completes immediately

---

### ActionMoveToLocation

**Routine:** 21

#### Function Signature

```nss
void ActionMoveToLocation(location lDestination, int bRun = FALSE);
```

#### Description

Moves the caller to a specific location. The movement follows the walkmesh to the nearest walkable point.

#### Parameters

- `lDestination`: Target location (created with `Location()` function)
- `bRun`: Movement speed (0 = walk, 1 = run, non-zero = run)

#### Usage Examples

```nss
// Move to a specific location
location lTarget = Location(GetArea(OBJECT_SELF), Vector(10.0, 20.0, 0.0), 0.0);
ActionMoveToLocation(lTarget, FALSE);
```

```nss
// Move to a waypoint's location
object oWP = GetWaypointByTag("wp_meeting");
ActionMoveToLocation(GetLocation(oWP), TRUE);
```

---

### ActionForceMoveToObject

**Routine:** 383 (TSL only)

#### Function Signature

```nss
void ActionForceMoveToObject(object oMoveTo, int bRun, float fRange, float fTimeout);
```

#### Description

Forces movement to an object with a timeout. Unlike `ActionMoveToObject`, this action will fail if it doesn't complete within the timeout period.

#### Parameters

- `oMoveTo`: Target object
- `bRun`: Movement speed (0 = walk, 1 = run)
- `fRange`: Distance to stop from target
- `fTimeout`: Maximum time in seconds before the action times out

#### Usage Examples

```nss
// Force move with 30 second timeout
object oTarget = GetObjectByTag("quest_target");
ActionForceMoveToObject(oTarget, FALSE, 1.0, 30.0);
```

**Pattern: Move PC to Cutscene Position**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/TSLRCM/Modules/306NAR_Nar_Shaddaa_Entertainment_Promenade/a_hit_move.nss
object oPC = GetFirstPC();
object oHitman = GetObjectByTag("Hitman", 0);
AssignCommand(oPC, ClearAllActions());
AssignCommand(oPC, ActionForceMoveToObject(GetObjectByTag("WP_hitman_spot", 0), 0, 1.0, 30.0));
AssignCommand(oPC, DelayCommand(0.8, SetFacingPoint(GetPosition(oHitman))));
```

---

### ActionJumpToObject

**Routine:** 196

#### Function Signature

```nss
void ActionJumpToObject(object oToJumpTo, int bWalkStraightLineToPoint = TRUE);
```

#### Description

Instantly teleports (jumps) the caller to a target object's position. Does not follow walkmesh - moves directly to the target.

#### Parameters

- `oToJumpTo`: Target object to jump to
- `bWalkStraightLineToPoint`: If TRUE, attempts to walk from current position to jump point first (for visibility); if FALSE, jumps immediately

#### Usage Examples

```nss
// Instant jump to waypoint
object oWP = GetWaypointByTag("wp_teleport");
ActionJumpToObject(oWP, FALSE);
```

```nss
// Jump after walking closer (for cutscenes)
ActionJumpToObject(oTarget, TRUE);
```

---

## Utility Actions

### ActionWait

**Routine:** 202

#### Function Signature

```nss
void ActionWait(float fSeconds);
```

#### Description

Waits for a specified duration before continuing to the next action in the queue. This is useful for timing action sequences.

#### Parameters

- `fSeconds`: Duration to wait in seconds (can be fractional)

#### Usage Examples

```nss
// Wait before speaking
ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL, 1.0, -1.0);
ActionWait(3.0);
ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, -1.0);
```

```nss
// Wait with random duration
int nRandom = Random(5) + 3; // 3-8 seconds
ActionWait(IntToFloat(nRandom));
ActionForceMoveToObject(oNextWaypoint, FALSE, 2.5, 30.0);
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/script/routine/impl/action.cpp:344-354`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/script/routine/impl/action.cpp#L344-L354)

---

## Animation Actions

### ActionPlayAnimation

**Routine:** 40

#### Function Signature

```nss
void ActionPlayAnimation(int nAnimation, float fSpeed, float fDurationSeconds);
```

#### Description

Causes the action subject to play an animation. This action is queued and executed as part of the object's action queue.

**⚠️ CRITICAL:** Animations **will not play** if the object is moving. Always call `ClearAllActions()` first.

#### Parameters

- `nAnimation`: The animation constant (must be >= 10000). Common constants:
  - `ANIMATION_LOOPING_PAUSE` - Idle pause animation
  - `ANIMATION_LOOPING_TALK_NORMAL` - Normal talking animation
  - `ANIMATION_LOOPING_TALK_FORCEFUL` - Forceful talking animation
  - `ANIMATION_LOOPING_TALK_LAUGHING` - Laughing animation
  - `ANIMATION_LOOPING_TALK_PLEADING` - Pleading animation
  - `ANIMATION_LOOPING_TALK_SAD` - Sad talking animation
  - See `Animations.2da` for all available animation indices
- `fSpeed`: Speed multiplier (1.0 = normal speed, 2.0 = double speed)
- `fDurationSeconds`: Duration control:
  - `-1.0` = Looping (plays indefinitely until next animation)
  - `0.0` = Fire-and-forget (plays once, completes when animation finishes)
  - `> 0.0` = Timed (plays for specified duration in seconds)

#### Critical Requirements

**Movement Blocking:** Animations **will not play** if `movementType != None`. Always call `ClearAllActions()` before queuing animations.

**Animation ID Requirements:** Animation constants must include the 10000 offset. Constants already include this, but if using raw indices from `Animations.2da`, add 10000.

#### Usage Examples

```nss
// Basic looping animation
ClearAllActions();
ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, -1.0);
```

```nss
// Animation on another object with delay
object oNPC = GetObjectByTag("npc");
AssignCommand(oNPC, ClearAllActions());
DelayCommand(0.2, AssignCommand(oNPC, ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL, 1.0, -1.0)));
```

```nss
// Brief timed animation
ClearAllActions();
ActionPlayAnimation(ANIMATION_LOOPING_PAUSE, 1.0, 0.1);
```

#### Implementation References

- [`vendor/reone/src/libs/game/object/creature.cpp:281-283`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/object/creature.cpp#L281-L283) - Movement blocking check
- [`vendor/KotOR.js/src/actions/ActionPlayAnimation.ts:56-62`](https://github.com/th3w1zard1/KotOR.js/blob/master/src/actions/ActionPlayAnimation.ts#L56-L62) - Animation validation

---

## Speaking Actions

### ActionSpeakString

**Routine:** 39

#### Function Signature

```nss
void ActionSpeakString(string sStringToSpeak, int nTalkVolume);
```

#### Description

Makes the caller speak a string with a specified volume level. The action completes when the speech finishes.

#### Parameters

- `sStringToSpeak`: Text to speak
- `nTalkVolume`: Volume constant:
  - `TALKVOLUME_TALK` - Normal talking volume
  - `TALKVOLUME_WHISPER` - Whisper volume
  - `TALKVOLUME_SHOUT` - Shout volume
  - `TALKVOLUME_SILENT_TALK` - Silent (no audio)

#### Usage Examples

```nss
// Simple speak action
ActionSpeakString("Hello there!", TALKVOLUME_TALK);
```

```nss
// Speak after moving
ActionMoveToObject(oTarget, FALSE, 1.0);
ActionSpeakString("I've arrived!", TALKVOLUME_TALK);
```

---

### ActionSpeakStringByStrRef

**Routine:** 240

#### Function Signature

```nss
void ActionSpeakStringByStrRef(int nStrRef, int nTalkVolume);
```

#### Description

Makes the caller speak a string from the talk table (TLK file) using a string reference ID. This is the preferred method for localized/modded content.

#### Parameters

- `nStrRef`: String reference ID from TLK file
- `nTalkVolume`: Volume constant (same as ActionSpeakString)

#### Usage Examples

```nss
// Speak using string reference
ActionSpeakStringByStrRef(12345, TALKVOLUME_TALK);
```

---

## Additional Action Functions

The following action functions are also available but less commonly used. They follow the same action queue pattern:

- `ActionAttack` - Attack a target
- `ActionCastSpellAtObject` - Cast a spell on an object
- `ActionEquipItem` - Equip an item
- `ActionPickUpItem` - Pick up an item
- `ActionGiveItem` - Give an item to another object
- `ActionStartConversation` - Start a dialogue
- `ActionUseFeat` - Use a feat
- `ActionUseSkill` - Use a skill
- `ActionRandomWalk` - Random movement

---

## Common Patterns and Best Practices

### Pattern: Clear, Move, Animate

```nss
ClearAllActions();
ActionMoveToObject(oTarget, FALSE, 1.0);
ActionDoCommand(SetFacingPoint(GetPosition(oTarget)));
ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL, 1.0, -1.0);
ActionSpeakString("Hello!", TALKVOLUME_TALK);
```

### Pattern: Staggered Actions with Delay

```nss
// Execute actions on multiple objects with delays
int i;
for(i = 0; i < 3; i++) {
    object oNPC = GetObjectByTag("npc_" + IntToString(i));
    DelayCommand(IntToFloat(i * 0.5), AssignCommand(oNPC, ActionSpeakString("My turn!", TALKVOLUME_TALK)));
}
```

### Pattern: Conditional Action Sequences

```nss
ClearAllActions();
if (GetLocalInt(OBJECT_SELF, "HasMetPC") == 1) {
    ActionSpeakString("Welcome back!", TALKVOLUME_TALK);
} else {
    ActionSpeakString("Hello, stranger!", TALKVOLUME_TALK);
    ActionDoCommand(SetLocalInt(OBJECT_SELF, "HasMetPC", 1));
}
```

### Best Practices

1. **Always Clear Actions Before Animations**: Use `ClearAllActions()` before `ActionPlayAnimation()`
2. **Use AssignCommand for Other Objects**: Don't try to execute actions directly on other objects
3. **Chain Actions in Sequence**: Actions execute in the order they're queued
4. **Use DelayCommand for Timing**: Don't use loops with `ActionWait` for timing - use `DelayCommand`
5. **ActionDoCommand for Non-Actions**: Wrap non-action functions to queue them

---

## Related Functions

- `PlayAnimation()` - Immediate animation (non-queued)
- `SetFacing()` - Set facing direction (use with ActionDoCommand to queue)
- `ExecuteScript()` - Run a script on an object (non-action)
- `GetIsActionPossible()` - Check if an action can be performed (if available)
