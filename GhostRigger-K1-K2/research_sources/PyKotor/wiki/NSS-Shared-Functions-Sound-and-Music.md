# Sound and Music

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript sound and music functions. These functions allow scripts to play sounds, manage background music tracks, control ambient sounds, and adjust audio volumes.

---

## Sound and Music Fundamentals

### Understanding Audio in KotOR

KotOR has multiple audio layers:

- **Background Music** - Area-specific music that plays continuously
- **Battle Music** - Music that plays during combat
- **Ambient Sounds** - Environmental sounds (wind, machinery, etc.)
- **Sound Effects** - One-off sounds (footsteps, explosions, etc.)
- **Voice Lines** - Character dialogue sounds

Music tracks are defined in `ambientmusic.2da`. Each area can have:

- Day track
- Night track
- Battle track

---

## Sound Functions

### PlaySound

**Routine:** 46

#### Function Signature

```nss
void PlaySound(string sSoundName);
```

#### Description

Plays a sound effect. The sound is played immediately from the caller's position. Sounds are typically `.wav` files.

#### Parameters

- `sSoundName`: Sound file resref (without extension, e.g., "explosion01")

#### Usage Examples

```nss
// Play sound effect
PlaySound("explosion01");
```

```nss
// Play sound from object
object oNPC = GetObjectByTag("npc");
AssignCommand(oNPC, PlaySound("footstep01"));
```

**Pattern: Sound on Event**

```nss
// Play sound when object is used
void main() {
    object oUser = GetLastUsedBy();
    if (GetIsPC(oUser)) {
        PlaySound("activation_beep");
    }
}
```

#### Notes

- Sound file must exist in game resources
- Sound plays from caller's position
- Sounds are one-shot (play once and stop)
- Typically `.wav` format files

---

## Background Music Functions

### MusicBackgroundPlay

**Routine:** 360

#### Function Signature

```nss
void MusicBackgroundPlay(object oArea);
```

#### Description

Starts playing the background music for an area. The music plays the day track by default (or current track based on time of day).

#### Parameters

- `oArea`: Area object to play music for

#### Usage Examples

```nss
// Play area music
object oArea = GetArea();
MusicBackgroundPlay(oArea);
```

**Pattern: Start Music on Area Entry**

```nss
// In area's OnEnter script
void main() {
    object oArea = GetArea();
    MusicBackgroundPlay(oArea);
}
```

---

### MusicBackgroundStop

**Routine:** 361

#### Function Signature

```nss
void MusicBackgroundStop(object oArea);
```

#### Description

Stops the background music for an area.

#### Parameters

- `oArea`: Area object to stop music for

#### Usage Examples

```nss
// Stop area music
object oArea = GetArea();
MusicBackgroundStop(oArea);
```

**Pattern: Stop Music for Cutscene**

```nss
// Stop music before cutscene
object oArea = GetArea();
MusicBackgroundStop(oArea);
// ... cutscene plays ...
// Resume music after
DelayCommand(10.0, MusicBackgroundPlay(oArea));
```

---

### MusicBackgroundChangeDay

**Routine:** 362

#### Function Signature

```nss
void MusicBackgroundChangeDay(object oArea, int nTrack);
```

#### Description

Changes the day music track for an area. The track number refers to an entry in `ambientmusic.2da`.

#### Parameters

- `oArea`: Area object to change music for
- `nTrack`: Music track index (from `ambientmusic.2da`)

#### Usage Examples

```nss
// Change day music track
object oArea = GetArea();
MusicBackgroundChangeDay(oArea, 5); // Track 5 from ambientmusic.2da
```

**Pattern: Dynamic Music Change**

```nss
// Change music based on quest state
object oArea = GetArea();
if (GetGlobalBoolean("Quest_Completed")) {
    MusicBackgroundChangeDay(oArea, 10); // Victory music
} else {
    MusicBackgroundChangeDay(oArea, 3); // Normal music
}
MusicBackgroundPlay(oArea);
```

---

### MusicBackgroundChangeNight

**Routine:** 363

#### Function Signature

```nss
void MusicBackgroundChangeNight(object oArea, int nTrack);
```

#### Description

Changes the night music track for an area. The track number refers to an entry in `ambientmusic.2da`.

#### Parameters

- `oArea`: Area object to change music for
- `nTrack`: Music track index (from `ambientmusic.2da`)

#### Usage Examples

```nss
// Change night music track
object oArea = GetArea();
MusicBackgroundChangeNight(oArea, 7);
```

---

### MusicBackgroundGetDayTrack

**Routine:** 414

#### Function Signature

```nss
int MusicBackgroundGetDayTrack(object oArea);
```

#### Description

Gets the current day music track number for an area.

#### Parameters

- `oArea`: Area object to check

#### Returns

- Day music track index (from `ambientmusic.2da`)
- `-1` if area is invalid or no track is set

#### Usage Examples

```nss
// Get current day track
object oArea = GetArea();
int nTrack = MusicBackgroundGetDayTrack(oArea);
```

---

### MusicBackgroundGetNightTrack

**Routine:** 415

#### Function Signature

```nss
int MusicBackgroundGetNightTrack(object oArea);
```

#### Description

Gets the current night music track number for an area.

#### Parameters

- `oArea`: Area object to check

#### Returns

- Night music track index (from `ambientmusic.2da`)
- `-1` if area is invalid or no track is set

#### Usage Examples

```nss
// Get current night track
object oArea = GetArea();
int nNightTrack = MusicBackgroundGetNightTrack(oArea);
```

---

### MusicBackgroundGetBattleTrack

**Routine:** 569

#### Function Signature

```nss
int MusicBackgroundGetBattleTrack(object oArea);
```

#### Description

Gets the battle music track number for an area. Battle music plays automatically during combat.

#### Parameters

- `oArea`: Area object to check

#### Returns

- Battle music track index (from `ambientmusic.2da`)
- `-1` if area is invalid or no track is set

#### Usage Examples

```nss
// Get battle track
object oArea = GetArea();
int nBattleTrack = MusicBackgroundGetBattleTrack(oArea);
```

---

### MusicBackgroundSetDelay

**Routine:** 427

#### Function Signature

```nss
void MusicBackgroundSetDelay(object oArea, int nDelay);
```

#### Description

Sets the delay (in milliseconds) before background music starts playing in an area.

#### Parameters

- `oArea`: Area object to set delay for
- `nDelay`: Delay in milliseconds before music starts

#### Usage Examples

```nss
// Set music delay (in milliseconds)
object oArea = GetArea();
MusicBackgroundSetDelay(oArea, 5000); // Wait 5 seconds (5000ms) before music starts
MusicBackgroundPlay(oArea);
```

#### Notes

- Delay is in milliseconds, not seconds
- 1000 milliseconds = 1 second

---

### MusicBattlePlay

**Routine:** 430

#### Function Signature

```nss
void MusicBattlePlay(object oArea);
```

#### Description

Starts playing the battle music for an area. Battle music typically plays automatically during combat, but can be triggered manually.

#### Parameters

- `oArea`: Area object to play battle music for

#### Usage Examples

```nss
// Play battle music
object oArea = GetArea();
MusicBattlePlay(oArea);
```

---

### MusicBattleStop

**Routine:** 431

#### Function Signature

```nss
void MusicBattleStop(object oArea);
```

#### Description

Stops the battle music for an area.

#### Parameters

- `oArea`: Area object to stop battle music for

#### Usage Examples

```nss
// Stop battle music
object oArea = GetArea();
MusicBattleStop(oArea);
```

---

### MusicBattleChange

**Routine:** 432

#### Function Signature

```nss
void MusicBattleChange(object oArea, int nTrack);
```

#### Description

Changes the battle music track for an area. The track number refers to an entry in `ambientmusic.2da`.

#### Parameters

- `oArea`: Area object to change battle music for
- `nTrack`: Battle music track index (from `ambientmusic.2da`)

#### Usage Examples

```nss
// Change battle music track
object oArea = GetArea();
MusicBattleChange(oArea, 20); // Boss battle music
```

---

## Ambient Sound Functions

### AmbientSoundPlay

**Routine:** 367

#### Function Signature

```nss
void AmbientSoundPlay(object oArea);
```

#### Description

Starts playing the ambient sound for an area. Ambient sounds are environmental audio effects (wind, machinery, etc.).

#### Parameters

- `oArea`: Area object to play ambient sound for

#### Usage Examples

```nss
// Play ambient sound
object oArea = GetArea();
AmbientSoundPlay(oArea);
```

---

### AmbientSoundStop

**Routine:** 368

#### Function Signature

```nss
void AmbientSoundStop(object oArea);
```

#### Description

Stops the ambient sound for an area.

#### Parameters

- `oArea`: Area object to stop ambient sound for

#### Usage Examples

```nss
// Stop ambient sound
object oArea = GetArea();
AmbientSoundStop(oArea);
```

---

### AmbientSoundChangeDay

**Routine:** 369

#### Function Signature

```nss
void AmbientSoundChangeDay(object oArea, int nTrack);
```

#### Description

Changes the day ambient sound track for an area.

#### Parameters

- `oArea`: Area object to change ambient sound for
- `nTrack`: Ambient sound track index

#### Usage Examples

```nss
// Change day ambient sound
object oArea = GetArea();
AmbientSoundChangeDay(oArea, 2);
```

---

### AmbientSoundChangeNight

**Routine:** 370

#### Function Signature

```nss
void AmbientSoundChangeNight(object oArea, int nTrack);
```

#### Description

Changes the night ambient sound track for an area.

#### Parameters

- `oArea`: Area object to change ambient sound for
- `nTrack`: Ambient sound track index

#### Usage Examples

```nss
// Change night ambient sound
object oArea = GetArea();
AmbientSoundChangeNight(oArea, 3);
```

---

### AmbientSoundSetDayVolume

**Routine:** 567

#### Function Signature

```nss
void AmbientSoundSetDayVolume(object oArea, int nVolume);
```

#### Description

Sets the volume for the day ambient sound in an area.

#### Parameters

- `oArea`: Area object to set volume for
- `nVolume`: Volume level (0-100, where 100 is maximum)

#### Usage Examples

```nss
// Set day ambient volume
object oArea = GetArea();
AmbientSoundSetDayVolume(oArea, 75); // 75% volume
```

---

### AmbientSoundSetNightVolume

**Routine:** 568

#### Function Signature

```nss
void AmbientSoundSetNightVolume(object oArea, int nVolume);
```

#### Description

Sets the volume for the night ambient sound in an area.

#### Parameters

- `oArea`: Area object to set volume for
- `nVolume`: Volume level (0-100, where 100 is maximum)

#### Usage Examples

```nss
// Set night ambient volume
object oArea = GetArea();
AmbientSoundSetNightVolume(oArea, 50); // 50% volume
```

---

## Utility Functions

### GetStrRefSoundDuration

**Routine:** 571

#### Function Signature

```nss
float GetStrRefSoundDuration(int nStrRef);
```

#### Description

Gets the duration (in seconds) of the sound attached to a string reference. String references can have associated voice sounds.

#### Parameters

- `nStrRef`: String reference ID to check

#### Returns

- Duration in seconds of the sound
- `0.0` if no sound is attached or no duration is stored

#### Usage Examples

```nss
// Get sound duration
float fDuration = GetStrRefSoundDuration(12345);
```

**Pattern: Delay Based on Voice Duration**

```nss
// Wait for voice line to finish
int nStrRef = 12345;
float fDuration = GetStrRefSoundDuration(nStrRef);
SpeakStringByStrRef(nStrRef, TALKVOLUME_TALK);
DelayCommand(fDuration + 0.5, DoSomething()); // Wait for voice + buffer
```

---

## Common Patterns and Best Practices

### Pattern: Dynamic Music Based on Events

```nss
// Change music based on quest progress
object oArea = GetArea();
if (GetGlobalBoolean("BossBattle_Started")) {
    MusicBackgroundChangeDay(oArea, 15); // Boss music
    MusicBackgroundPlay(oArea);
} else if (GetGlobalBoolean("Quest_Completed")) {
    MusicBackgroundChangeDay(oArea, 10); // Victory music
    MusicBackgroundPlay(oArea);
}
```

### Pattern: Stop Music for Cutscene

```nss
// Stop music before important cutscene
object oArea = GetArea();
MusicBackgroundStop(oArea);
AmbientSoundStop(oArea);

// Play cutscene
// ...

// Resume music after cutscene
DelayCommand(5.0, MusicBackgroundPlay(oArea));
DelayCommand(5.0, AmbientSoundPlay(oArea));
```

### Pattern: Adjust Ambient Volume

```nss
// Lower ambient sound for dialogue
object oArea = GetArea();
int nOriginalVolume = 100; // Store original if needed
AmbientSoundSetDayVolume(oArea, 30); // Lower volume for dialogue
// ... dialogue ...
// Restore volume after
DelayCommand(10.0, AmbientSoundSetDayVolume(oArea, 100));
```

### Pattern: Sound Effects for Events

```nss
// Play sound when door opens
void main() {
    object oDoor = GetObjectByTag("vault_door");
    if (!GetLocked(oDoor)) {
        PlaySound("door_open_creak");
        ActionOpenDoor(oDoor);
    }
}
```

### Best Practices

1. **Always Get Area**: Use `GetArea()` to get area object before music/ambient functions
2. **Stop Before Change**: Stop music before changing tracks to avoid overlaps
3. **Use Delays**: Use `DelayCommand()` to sequence music changes
4. **Volume Levels**: Ambient volume is 0-100 (0 = silent, 100 = maximum)
5. **Track Numbers**: Music track numbers refer to `ambientmusic.2da` entries
6. **Validate Area**: Ensure area object is valid before using audio functions

---

## Related Functions

- `GetArea()` - Get area object (see [Module & Area](NSS-Shared-Functions-Module-and-Area))
- `SpeakString()` - Voice lines (may have associated sounds) - see [Dialog Functions](NSS-Shared-Functions-Dialog-and-Conversation-Functions)

---

## Additional Notes

### Music Track System

Music tracks are stored in `ambientmusic.2da`:

- Each track has a resource name (music file)
- Tracks can have multiple stingers (short musical cues)
- Day/night tracks automatically switch based on time of day
- Battle tracks play during combat

### Ambient Sounds

Ambient sounds:

- Play continuously while in an area
- Can have different day/night versions
- Volume can be adjusted independently
- Stop automatically when leaving area

### Sound Files

Sound files:

- Typically `.wav` format
- Stored in game resources
- Referenced by resref (without extension)
- Can be positional (3D audio) or global

### Audio Layering

Audio layers (in order of priority, highest first):

1. **Voice Lines** - Character dialogue
2. **Sound Effects** - Immediate audio events
3. **Battle Music** - Combat music
4. **Background Music** - Area music
5. **Ambient Sounds** - Environmental audio

Lower priority audio may be ducked or paused when higher priority audio plays.
