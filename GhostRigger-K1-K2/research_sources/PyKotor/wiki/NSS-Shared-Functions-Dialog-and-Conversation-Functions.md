# Dialog and Conversation Functions

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript dialog and conversation functions. These functions allow scripts to start conversations, get conversation participants, handle conversation events, and make NPCs speak.

---

## Starting Conversations

### BeginConversation

**Routine:** 255

#### Function Signature

```nss
int BeginConversation(string sResRef = "", object oObjectToDialog = OBJECT_INVALID);
```

#### Description

Starts a conversation dialog tree. **This function is typically called from an OnDialog event script** (triggered when a creature is clicked or `ActionStartConversation` is used). If no dialog resref is specified, the creature's default conversation file is used.

**⚠️ IMPORTANT:** This function is called **by the game engine** when a dialog is triggered. You typically call this from OnDialog scripts, not from regular scripts. For manual conversation starts, use `ActionStartConversation()` instead.

#### Parameters

- `sResRef`: Dialog file resref (without `.dlg` extension). If empty (""), uses the creature's default conversation
- `oObjectToDialog`: Object to start conversation with (default: `OBJECT_INVALID` - uses the object that triggered the event)

#### Returns

- `1` if conversation started successfully
- `0` if failed

#### Usage Examples

```nss
// OnDialog script - use default conversation
void main() {
    BeginConversation();
}
```

```nss
// OnDialog script - use specific dialog file
void main() {
    BeginConversation("my_custom_dialog");
}
```

```nss
// OnDialog script - start conversation with specific object
void main() {
    object oPC = GetFirstPC();
    BeginConversation("", oPC);
}
```

#### Notes

- Typically called from **OnDialog event scripts**, not regular scripts
- The OnDialog event fires when a creature is clicked or `ActionStartConversation` is executed
- If `sResRef` is empty, the creature's `Conversation` field (from UTC/GIT) is used
- The conversation system handles dialog trees, player choices, and script execution

---

### ActionStartConversation

**Routine:** 204

#### Function Signature

```nss
void ActionStartConversation(
    object oObjectToConverse,
    string sDialogResRef = "",
    int bPrivateConversation = FALSE,
    int nConversationType = CONVERSATION_TYPE_CINEMATIC,
    int bIgnoreStartRange = FALSE,
    string sNameObjectToIgnore1 = "",
    string sNameObjectToIgnore2 = "",
    string sNameObjectToIgnore3 = "",
    string sNameObjectToIgnore4 = "",
    string sNameObjectToIgnore5 = "",
    string sNameObjectToIgnore6 = "",
    int bUseLeader = FALSE,
    int nBarkX = -1,
    int nBarkY = -1,
    int bDontClearAllActions = 0
);
```

#### Description

Queues an action to start a conversation with a target object. The creature will move to within conversation range (if needed) and then start the dialog. This is the **primary way to start conversations from scripts**.

#### Parameters

- `oObjectToConverse`: Target object to start conversation with (the NPC/creature)
- `sDialogResRef`: Dialog file resref (without `.dlg`). If empty, uses the creature's default conversation
- `bPrivateConversation`: If `TRUE`, conversation is private (default: `FALSE`)
- `nConversationType`: Conversation type (default: `CONVERSATION_TYPE_CINEMATIC`):
  - `CONVERSATION_TYPE_CINEMATIC` - Standard cinematic conversation
  - `CONVERSATION_TYPE_COMPUTER` - Computer/terminal conversation
  - **Note:** In TSL, this parameter has no effect (handled by dialog editor flags), but should still be set to `CONVERSATION_TYPE_CINEMATIC` for compatibility
- `bIgnoreStartRange`: If `TRUE`, starts conversation without moving to range (default: `FALSE`)
- `sNameObjectToIgnore1` through `sNameObjectToIgnore6`: Objects (by name/tag) that don't need to be present for dialog animations to work
- `bUseLeader`: If `TRUE`, uses party leader instead of object executing action (default: `FALSE`)
- `nBarkX`, `nBarkY`: Override bark string position (for bark conversations only). `-1` = use default
- `bDontClearAllActions`: If `TRUE`, doesn't clear action queue before starting conversation (default: `FALSE`)

#### Usage Examples

```nss
// Basic conversation start
object oNPC = GetObjectByTag("merchant");
ActionStartConversation(oNPC);
```

```nss
// Start conversation with specific dialog file
object oNPC = GetObjectByTag("quest_giver");
ActionStartConversation(oNPC, "quest_dialog");
```

```nss
// Start conversation ignoring range (for cutscenes)
object oBoss = GetObjectByTag("final_boss");
ActionStartConversation(oBoss, "", FALSE, CONVERSATION_TYPE_CINEMATIC, TRUE);
```

**Pattern: Cutscene Conversation**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
object oKreia = GetObjectByTag("kreia", 0);
AssignCommand(oKreia, ActionJumpToObject(GetObjectByTag("sp_kreia", 0), 1));
DelayCommand(0.2, AssignCommand(oKreia, 
    ActionStartConversation(GetFirstPC(), "", 0, 0, 0, "", "", "", "", "", "", 0, 0xFFFFFFFF, 0xFFFFFFFF, 0)));
```

**Pattern: Object Starts Conversation with Itself**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/905MAL_Malachor_V_Trayus_Crescent/a_cellopen.nss
object oNPC = GetObjectByTag("npc_tag");
AssignCommand(oNPC, ClearAllActions());
AssignCommand(oNPC, ActionStartConversation(oNPC, "", 0, 0, 0, "", "", "", "", "", "", 0, 0xFFFFFFFF, 0xFFFFFFFF, 0));
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/action/startconversation.cpp`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/action/startconversation.cpp)
- Conversation starts when actor reaches within 4.0 meters of target (unless `bIgnoreStartRange` is `TRUE`)

---

## Conversation Information Functions

### GetLastSpeaker

**Routine:** 254

#### Function Signature

```nss
object GetLastSpeaker();
```

#### Description

Gets the object that is speaking in the current conversation. **Use this in conversation scripts** (scripts attached to dialog nodes) to get the conversation participant. Returns `OBJECT_INVALID` if not in a conversation context.

#### Returns

- Object of the current speaker in conversation
- `OBJECT_INVALID` if not in conversation context or invalid

#### Usage Examples

```nss
// In a conversation script - get the NPC speaking
void main() {
    object oSpeaker = GetLastSpeaker();
    if (GetIsObjectValid(oSpeaker)) {
        // Do something with the speaker
        SetLocalInt(oSpeaker, "HasTalked", 1);
    }
}
```

```nss
// Check if speaker is specific NPC
void main() {
    object oSpeaker = GetLastSpeaker();
    object oNPC = GetObjectByTag("important_npc");
    if (oSpeaker == oNPC) {
        // Important NPC is speaking
    }
}
```

#### Notes

- Primarily used in **conversation scripts** (attached to dialog nodes)
- The "last speaker" is the object whose dialog node just executed
- In dialog scripts, this typically refers to the NPC/creature, not the PC

---

### GetIsInConversation

**Routine:** 445

#### Function Signature

```nss
int GetIsInConversation(object oObject = OBJECT_SELF);
```

#### Description

Returns `TRUE` if the specified object is currently in a conversation.

#### Parameters

- `oObject`: Object to check (default: `OBJECT_SELF`)

#### Returns

- `TRUE` if object is in conversation
- `FALSE` if not in conversation or invalid

#### Usage Examples

```nss
// Check if self is in conversation
if (GetIsInConversation()) {
    // Do something only during conversation
}
```

```nss
// Check if NPC is busy talking
object oNPC = GetObjectByTag("merchant");
if (GetIsInConversation(oNPC)) {
    // NPC is already talking, don't interrupt
    return;
}
ActionStartConversation(oNPC);
```

---

### GetIsConversationActive

**Routine:** 701

#### Function Signature

```nss
int GetIsConversationActive();
```

#### Description

Returns `TRUE` if any conversation is currently active in the game.

#### Returns

- `TRUE` if a conversation is active
- `FALSE` if no conversation is active

#### Usage Examples

```nss
// Check if any conversation is active
if (GetIsConversationActive()) {
    // Don't start new conversation while one is active
    return;
}
```

---

### EventConversation

**Routine:** 295

#### Function Signature

```nss
void EventConversation();
```

#### Description

Triggers the OnConversation event script on the caller. Used to execute conversation-related logic when a conversation event occurs.

#### Usage Examples

```nss
// Trigger conversation event
EventConversation();
```

#### Notes

- Typically called by the game engine during conversation flow
- Triggers OnConversation event scripts on objects
- Can be used to trigger conversation-related logic programmatically

---

## Speaking Functions

### SpeakString

**Routine:** 221

#### Function Signature

```nss
void SpeakString(string sStringToSpeak, int nTalkVolume = TALKVOLUME_TALK);
```

#### Description

Makes the caller speak a string immediately. This is a **non-queued function** (executes immediately, not an action).

#### Parameters

- `sStringToSpeak`: Text to speak
- `nTalkVolume`: Volume constant (default: `TALKVOLUME_TALK`):
  - `TALKVOLUME_TALK` - Normal talking volume
  - `TALKVOLUME_WHISPER` - Whisper volume
  - `TALKVOLUME_SHOUT` - Shout volume
  - `TALKVOLUME_SILENT_TALK` - Silent (no audio, subtitles only)

#### Usage Examples

```nss
// Simple speak
SpeakString("Hello there!", TALKVOLUME_TALK);
```

```nss
// Whisper
SpeakString("Psst... over here.", TALKVOLUME_WHISPER);
```

```nss
// Shout
SpeakString("Charge!", TALKVOLUME_SHOUT);
```

#### Notes

- Executes **immediately** (not queued as an action)
- Use `ActionSpeakString()` if you need to queue speaking as part of an action sequence

---

### ActionSpeakString

**Routine:** 39

#### Function Signature

```nss
void ActionSpeakString(string sStringToSpeak, int nTalkVolume = TALKVOLUME_TALK);
```

#### Description

Queues an action to speak a string. The action completes when the speech finishes. Use this when you need to speak as part of an action sequence.

#### Parameters

- `sStringToSpeak`: Text to speak
- `nTalkVolume`: Volume constant (same as `SpeakString()`)

#### Usage Examples

```nss
// Queue speaking action
ActionSpeakString("I'll say this after moving.", TALKVOLUME_TALK);
ActionMoveToObject(oTarget, FALSE, 1.0);
```

```nss
// Speak on another object
object oNPC = GetObjectByTag("guard");
AssignCommand(oNPC, ActionSpeakString("Halt!", TALKVOLUME_SHOUT));
```

---

### ActionSpeakStringByStrRef

**Routine:** 240

#### Function Signature

```nss
void ActionSpeakStringByStrRef(int nStrRef, int nTalkVolume = TALKVOLUME_TALK);
```

#### Description

Queues an action to speak a string from the talk table (TLK file) using a string reference ID. This is the preferred method for localized/modded content.

#### Parameters

- `nStrRef`: String reference ID from TLK file
- `nTalkVolume`: Volume constant (same as `SpeakString()`)

#### Usage Examples

```nss
// Speak using string reference
ActionSpeakStringByStrRef(12345, TALKVOLUME_TALK);
```

---

### BarkString

**Routine:** 671

#### Function Signature

```nss
void BarkString(object oCreature, int strRef);
```

#### Description

Makes a creature bark (speak a one-liner) using a string reference from the TLK file. Barks are brief, context-free statements often used for ambient dialogue.

#### Parameters

- `oCreature`: Creature to bark
- `strRef`: String reference ID from TLK file

#### Usage Examples

```nss
// Make NPC bark
object oNPC = GetObjectByTag("guard");
BarkString(oNPC, 10001);
```

---

### SpeakOneLinerConversation

**Routine:** 417

#### Function Signature

```nss
void SpeakOneLinerConversation(string sDialogResRef, object oTokenTarget = OBJECT_INVALID);
```

#### Description

Speaks a one-liner from a dialog file. The dialog file should have a single starting node that plays as a bark/one-liner.

#### Parameters

- `sDialogResRef`: Dialog file resref (without `.dlg` extension)
- `oTokenTarget`: Target object for dialog tokens (default: `OBJECT_INVALID`)

#### Usage Examples

```nss
// Speak one-liner from dialog
SpeakOneLinerConversation("guard_barks");
```

---

## Conversation Control Actions

### ActionPauseConversation

**Routine:** 205

#### Function Signature

```nss
void ActionPauseConversation();
```

#### Description

Queues an action to pause the current conversation. The conversation can be resumed later with `ActionResumeConversation()`.

#### Usage Examples

```nss
// Pause conversation
ActionPauseConversation();
```

---

### ActionResumeConversation

**Routine:** 206

#### Function Signature

```nss
void ActionResumeConversation();
```

#### Description

Queues an action to resume a paused conversation.

#### Usage Examples

```nss
// Resume paused conversation
ActionResumeConversation();
```

---

## Common Patterns and Best Practices

### Pattern: Start Conversation After Movement

```nss
// Move to NPC then start conversation
object oNPC = GetObjectByTag("quest_giver");
ClearAllActions();
ActionMoveToObject(oNPC, FALSE, 1.0);
DelayCommand(1.0, ActionStartConversation(oNPC));
```

### Pattern: Conditional Conversation

```nss
// Start different conversations based on condition
object oNPC = GetObjectByTag("merchant");
if (GetLocalInt(oNPC, "HasMetPC") == 1) {
    ActionStartConversation(oNPC, "merchant_repeat");
} else {
    ActionStartConversation(oNPC, "merchant_first");
    SetLocalInt(oNPC, "HasMetPC", 1);
}
```

### Pattern: Conversation in Cutscene

```nss
// Setup for cutscene conversation
object oBoss = GetObjectByTag("boss");
object oPC = GetFirstPC();

// Stop combat
CancelCombat(oBoss);
CancelCombat(oPC);
ClearAllActions();

// Position characters
AssignCommand(oPC, ActionJumpToObject(GetWaypointByTag("wp_pc_cutscene"), FALSE));
AssignCommand(oBoss, ActionJumpToObject(GetWaypointByTag("wp_boss_cutscene"), FALSE));

// Start conversation ignoring range
DelayCommand(1.0, AssignCommand(oBoss, 
    ActionStartConversation(oPC, "boss_cutscene", FALSE, CONVERSATION_TYPE_CINEMATIC, TRUE)));
```

### Pattern: OnDialog Script

```nss
// Typical OnDialog script
void main() {
    // Use default conversation or specific one
    string sDialog = GetScriptStringParameter();
    if (sDialog == "") {
        BeginConversation(); // Use creature's default conversation
    } else {
        BeginConversation(sDialog); // Use specified dialog
    }
}
```

### Pattern: Conversation Script (Dialog Node Script)

```nss
// Script attached to a dialog node
void main() {
    object oSpeaker = GetLastSpeaker();
    
    // Set flags when certain dialogue is spoken
    if (GetIsObjectValid(oSpeaker)) {
        SetLocalInt(oSpeaker, "QuestStarted", 1);
        SetGlobalNumber("MainQuest", 1);
    }
}
```

### Best Practices

1. **Use ActionStartConversation for Scripts**: Use `ActionStartConversation()` when starting conversations from regular scripts
2. **Use BeginConversation in OnDialog**: Use `BeginConversation()` in OnDialog event scripts
3. **Clear Actions Before Conversations**: Clear action queue before starting conversations in cutscenes
4. **Use String References for Localization**: Prefer `ActionSpeakStringByStrRef()` over `ActionSpeakString()` for modded content
5. **Ignore Range for Cutscenes**: Use `bIgnoreStartRange = TRUE` when starting conversations in cutscenes where characters are already positioned
6. **Check Conversation Status**: Use `GetIsInConversation()` to avoid interrupting active conversations

---

## Related Functions

- `GetFirstPC()` - Get the player character (often needed for conversations)
- `ClearAllActions()` - Clear action queue (often needed before conversations)
- `CancelCombat()` - End combat before starting conversations
- Dialog files (`.dlg`) - GFF format files that define conversation trees

---

## Additional Dialog Functions

Additional dialog-related functions include:

- `GetLastConversation()` - Get the last conversation (Routine 711, TSL)
- `ResetDialogState()` - Reset dialog state (Routine 749, TSL)
- `SetDialogPlaceableCamera()` - Set camera for placeable dialogs (Routine 461, TSL)
- `SetLockHeadFollowInDialog()` - Control head following in dialog (Routine 506, TSL)
- `SetLockOrientationInDialog()` - Control orientation in dialog (Routine 505, TSL)
- `CancelPostDialogCharacterSwitch()` - Cancel character switch after dialog (Routine 757, TSL)
- `HoldWorldFadeInForDialog()` - Control fade during dialog (Routine 760, TSL)

Each follows similar patterns to the functions documented above.
