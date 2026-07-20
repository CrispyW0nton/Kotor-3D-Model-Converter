# Map Studio PIE — Gameplay Parity Ledger

Living status of Play-in-Editor (PIE) as a game-faithful KOTOR/Odyssey gameplay
simulation for validating authored modules before a retail run. Grounded in the
`native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie*` sources
and real-module evidence. **Editor-side simulation only — a manual KOTOR warp is
the sole authoritative gameplay proof; nothing here is an in-game claim.**

Last updated 2026-07-17.

## Status legend

- **Implemented** — behavior exists, focused tests pass, exercised in a visible
  PIE workflow.
- **Partial** — core exists with clearly-tracked limitations below.
- **Reported-only** — PIE surfaces the authored intent but cannot execute it
  faithfully (usually because it runs no NWScript); it reports instead of acting.
- **Not started** — no PIE implementation yet.

## Systems

| System | Status | Owner module(s) | Evidence basis | Key limitations |
|---|---|---|---|---|
| Exploration / movement | Implemented | `map_studio_pie` | WOK spatial index, segment collision, click-to-move over connected faces | Camera collision is a clean-room approximation |
| Focus / interaction router | Implemented | `map_studio_pie_interactions` | Ghidra Q/E census (ranges, cycling) | Uses stable selection capsules, not exact posed-mesh picks |
| Dialogue traversal | Implemented | `map_studio_pie_dialogue`, `map_studio_pie_gameplay` | Ghidra DLG parse (EntryList/ReplyList/StartingList) + real DLGs; when every starting line's Active condition is unprovable (e.g. commoner one-liners `200comm`/`200comf` whose DLGs live in `dialogs.bif`) the gameplay path retries with the preview-assumption fallback so the line shows instead of nothing (verified in-app: 3 blocked one-liners rescued on 207TEL) | No arbitrary NWScript; the assumed one-liner line is a labelled preview guess, not the retail-evaluated branch |
| Dialogue conversation-context | Implemented | controller + `map_studio_pie_dialogue`, panel | Ghidra Auto-start rule; real 207luxa/207falt | Preview overrides bypass Active conditions (labelled) |
| Dialogue cameras | Implemented | `map_studio_pie_dialogue_camera` | 160-DLG CameraAngle census; real placed area cameras | Angles 0–5 are clean-room shots; animated CameraAnimation tracks fall back to a static shot |
| Journal / quests | Partial | `map_studio_pie_journal`, `map_studio_pie_gameplay` + dialogue | DLG Quest/QuestEntry fields (real 207falt) and OnEnter `AddJournalQuestEntry` writes fold into a runtime, monotonic per-plot quest log on the gameplay snapshot; seeded at Play start, advanced by dialogue nodes. Verified in-app (snapshot exposes `journal`, embedded accumulator monotonic) | Runtime preview log only — never campaign quest state; no `journal.2da` end/priority flags; entries advance but never regress or clear |
| Doors | Implemented | `map_studio_pie_doors`, `map_studio_pie_interactions`, `map_studio_pie_gameplay` | genericdoors models; auto-open + swing anim; UTD `locked`/`key_required` lock-and-key gating with runtime unlock tracking; OnOpen/OnClick action scripts now execute their bounded literal global/journal writes into the shared state; real 921srt/207TEL | Inter-module doors reported, not warped; non-literal/branching OnOpen/OnFailToOpen logic still deferred |
| Triggers / transitions | Implemented | `map_studio_pie_triggers`, `map_studio_pie_gameplay` | Real 207TEL GIT trigger polygons (local→world); crossing a non-transition trigger now executes its OnEnter script's bounded literal global/journal writes into the shared state (verified in-app: a real 207TEL trigger sets `207TEL_Benok=1`). Emits `trigger_script_executed` | Transition triggers reported, not warped; non-literal/branching OnEnter logic still deferred (no general NWScript VM) |
| Placeables / containers | Implemented | `map_studio_pie_interactions`, `map_studio_pie_gameplay` | UTP HasInventory + item lists → UTI; container/terminal/use action routing; looted items accumulate in a runtime-only player inventory; OnUsed/OnOpen action scripts now execute their bounded literal global/journal writes into the shared state (verified in-app). Emits `interaction_script_executed` | Non-literal/branching OnUsed/OnOpen logic still deferred (no general NWScript VM) |
| Inventory | Implemented | `map_studio_pie_interactions` | Container item lists; stacked runtime inventory | Player build/equipment not modelled |
| Animation (creatures/scene) | Implemented | `map_studio_pie_creatures` | OnEnter NCS ActionPlayAnimation scan; real 207TEL | Tag-consistency required; LIP/overlay/exact timing approximate |
| Audio (positional + area music) | Partial | `map_studio_pie_audio`, `map_studio_pie_scripting`, `map_studio_stock_content_preview`, controller | UTS placement sound emitters; **area ambient music** resolved from the OnEnter script — KOTOR area music is script-driven (`MusicBackgroundChangeDay`/`…Night` with a literal `ambientmusic.2da` row), not a static ARE field, so the bounded NCS reader recovers the day/night/battle track (`MusicBattleChange` 432) and the resolver maps each to the streaming resref. Verified in-app: real 207TEL → day/night track 18 → `mus_a_232`, no battle track (peaceful hub — faithful) | Area music is **reported/identified, not yet played** through the audio backend; script-conditional track changes beyond the final literal are not modelled |
| Combat (RTwP rounds) | Partial | `map_studio_pie_combat`, `map_studio_pie_resources`, `map_studio_pie_entities`, `map_studio_stock_content_preview` | Deterministic initiative/round model; hostile-retaliation, assisting-ally AND party-companion basic-attack AI; victory/defeat resolution (`combat_ended` carries the `outcome`; the snapshot exposes it); d20 critical hits with per-weapon threat/multiplier; creature HP/AC/attack from real UTC; equipped-weapon damage, armor AC (Dex cap), weapon damage type (nwscript), and Weapon Focus/Specialization feats (feat.2da, lightsaber/melee categories) all wired live from baseitems.2da and verified in-app | AI is basic-attack only (first hostile, no positional targeting); blaster-category feats + powers/on-hit item bonuses not applied (pistol/rifle focus can't be split from baseitems); item-property bonuses need in-game validation; multi-die weapons approximate via min/max range; the player uses an editor proxy unless the creator configures a `player_combat_template` UTC (then real HP/AC/attack/damage resolve, verified in-app: `203_ramana` → 8 HP/AC 10) — the PC's true custom build is campaign state |
| HUD / GUI | Implemented | window + rendering, `module_editor_viewport_panel`, `map_studio_pie_gameplay` | Ghidra 207TEL HUD/reticle/world-click audit; `mipc28x6_p.gui`. The gameplay HUD draws a **runtime validation dashboard** (`mapStudioPIEStateInspectorHUD`) from the snapshot's quest log (`journal`), global-variable state (`globals`), looted items (`interaction.player_inventory`), and combat outcome (`combat.outcome`) — verified in-app: the live 207TEL HUD label renders the real OnEnter globals and hides when empty; loot/combat rows render from data (focused HUD test) | Clean-room camera/HUD approximation, not the retail runtime; the dashboard is a compact text panel, not the retail journal/inventory/character screens |
| Cameras (exploration) | Implemented | window tick | Retail turn constants (200°/s etc.) | Clean-room integrator, not the exact Odyssey one |
| Party systems | Implemented | `map_studio_pie_party`, `map_studio_pie`, controller, window | Persisted creator-configurable `party_roster` (deduped, capped at 2) → clean-room trailing walkmesh-snapped formation → **rendered companion actors**: each roster UTC resolves its body model (appearance.2da), loads, and attaches as a separate retained actor (never the creature cohort) driven to its follow slot per tick with an idle pose. Verified in-app (companion `203_ramana` attaches behind the player). **Companions also join RTwP combat as assisting allies** — each roster UTC's combat stats (HP/AC/attack/damage from the 2DA chain) resolve into a `pie:party:N` combatant that auto-engages and lands basic attacks when combat opens (verified in-app: `participation_verified`) | Body-only when a head is unavailable; companion combat is basic-attack assist only (no companion powers/positioning); roster is a preview sandbox (party membership is campaign state) |
| Scripting state (NWScript VM) | Implemented (bounded sandbox) | `map_studio_pie_nwscript_vm`, `map_studio_pie_scripting` (fallback), controller, window | **Clean-room NCS virtual machine**: full stack machine over PyKotor-decoded bytecode (CONST/CPDOWN/CPTOP SP+BP, SAVEBP globals, JSR/JZ/JNZ control flow, DESTRUCT, typed arith/logic, STORE_STATE closures) with engine-routine dispatch per Ghidra's `CSWVirtualMachineCommands::ExecuteCommand` table contract (@0052c0d0). `AssignCommand`/`DelayCommand` closures run via the `RunScriptSituation` model (@005d4ad0: restore saved stack, OBJECT_SELF = bound target). `SetGlobalNumber` truncates to a byte per `SetValueNumber` (@00542b60). Executes module OnEnter at Play start seeded with the creator sandbox as PRE-ENTRY campaign state — campaign-gated writes fire only when their gate state is present (207TEL advances `207TEL_Benok` 1→2 only when seeded 1; clean sandbox writes nothing, matching retail first-entry). Cross-validated three ways on real 207TEL: VM tag→animation intents == static extractor's 10 intents exactly, plus stagger timing (0.1–0.8 s) and conditionals the extractor cannot see. Verified in-app (`engine: vm`, 563 instructions, conditional check green). Unknown routines return typed defaults and are census-tracked, never guessed | Editor-side sandbox: unhandled routines (census-tracked, e.g. SetCustomToken, fades) default; object validity is synthetic unless the entity registry is wired into the VM context; journal writes reported, not campaign state; bounded literal reader retained as fallback |
| Scripted events / cinematics | Partial | `map_studio_pie_scripted_events`, `map_studio_pie_nwscript_vm` | Per-entity FIFO action queues consuming VM command timelines — the editor-side analogue of retail `CSWSObject` action queues (Ghidra `ExecuteCommandMoveToObject` @0053fb00: target-position-at-queue-time, bRun walk/run, ≥0.5 arrival range; `DestroyObject` @0052ff20 delay; Pause/ResumeConversation gating). Validated against the real 207TEL Benok cantina exit (`benok.dlg` entry → `a_benokleave`): Benok walks (1.75 m/s) to GIT waypoint `wp_exitcantina` (4.46, −35.27), 207_matu +0.2 s, 207_nahata +0.4 s, all despawn +7 s, conversation pause/resume observed | Headless runtime only so far: creature actors do not yet consume move_to/despawn actions in the viewport (next visible slice); Pause/Resume gating is depth-tracked, not action-queue-sequenced; spawn commands (CreateObject) not yet handled |
| Module transitions | Reported + validated | doors/triggers, `map_studio_pie_triggers`, controller | LinkedToModule/LinkedTo; `validate_module_transitions` cross-checks each destination against the installation's module list so a creator catches a broken link before a retail black-screen. Verified in-app: real 207TEL's two Cantina doors resolve to `202tel` and are validated (honest `unverified` when the module list can't be resolved, never a false "missing") | Does not load/warp another module; existence check needs the installation's module enumeration, which was not exposed through the resolver's manager in the sampled runtime (reports `unverified` there) |

## Largest genuinely-remaining named systems

1. **Party systems** (Not started) — spawn a configurable party roster and have
   companions follow the player. Needs a party roster contract, follower actors,
   and follow/pathing. A dedicated multi-step slice.
2. **Combat feats/powers/equipment math** (Partial → deep) — 2DA-driven combat
   (baseitems, feat, spells, iprp_*), equipment effects, and the retail action
   queue. A large evidence-heavy effort (Ghidra combat formulas + 2DA).
3. **Animated dialogue camera tracks** — needs a viewport camera-track API;
   rare in real data (5 of ~2,751 sampled nodes), so lower priority.

## Remaining work — sequenced execution plan

The clean, bounded, single-pass slices are done. Each item below is a dedicated
multi-step effort; the prerequisites are what make it larger than one slice.

1. **Companion model rendering** (party → Implemented). Roster + formation +
   markers are done; only the on-screen follower *actor* remains. Concrete
   recipe traced 2026-07-17 (de-risked): for each `party_roster` UTC resref —
   (a) resolve body model via `TemplateModelResolver.creature_model(utc)`
   (appearance.2da modeltype-B `modela` / else `race`), optionally head; (b)
   `manager.load_model_strict(body_resref, game)`, compose head with
   `build_bas_preview_model` (or body-only); (c)
   `attach_map_studio_pie_actor(preview_model, actor_model,
   position=session.party_follow_targets(n)[slot-1], facing=…)`; (d) store in a
   NEW `self._map_studio_pie_party_actors` list (NOT the creature cohort), play
   `pause1`/`idlepose`; (e) each `_tick_map_studio_pie` update each actor's
   transform to the current `party_follow_targets` slot; (f) tear down in
   `_remove_map_studio_pie_runtime_actors`. Mirror the `_create/_update/_remove`
   player-actor methods. Risk: ~100-line window integration into the mature
   actor path — do it as a focused pass, guarded, parallel to creatures.
2. **Store/merchant catalog** (commerce validation). Build a headless store
   catalog (like the dialogue/quest catalogs) from the module's UTM resources:
   markup/markdown + item list → resolved UTI name/cost. **Prereq: a resource
   listing capability** — the current resolver reads by resref but cannot
   enumerate a module's UTMs; add a module-resource lister first.
3. **Combat feats/powers/on-hit item properties**. Note: a UTC's stored HP and
   attack already bake in the designer's final feat values, so *do not* re-derive
   them (that double-counts). The real gap is weapon/armor *item properties*
   (iprp_*: on-hit, enchant AC, attack/damage bonuses) from the UTI PropertiesList
   → iprp 2DAs, applied on top of the baseitems baseline already wired.
   **Empirical caveat (2026-07-17) — evidence gathered, ready to resume:**
   `itempropdef.2da` property ids — FLAT combat bonuses: id 5 `Enhancement`,
   id 22 `DamageMelee`, id 23 `DamageRanged`, id 38 `AttackBonus`. SKIP
   (situational/non-stat): id 8 `AttackPenalty`, id 35 `Regeneration`, id 39
   `AttackBonusAlignmentGroup`, id 40 `AttackBonusRacialGroup`, id 45/61 use
   limitations, id 49 `Massive_Criticals`, id 51 `Monster_damage`.
   Cost chain: a UTI property's `cost_table` indexes `iprp_costtable.2da`
   (0=`IPRP_BASE1`, 2=`IPRP_MELEECOST`, 4=`IPRP_DAMAGECOST`, …) → the cost 2DA.
   **BLOCKER (proven 2026-07-17, do not implement until resolved):** the cost 2DA
   holds the property's *credit cost*, not the bonus magnitude — `iprp_meleecost`
   row 3 = `2.9` (a price multiplier). Worse, PyKotor's `UTI.properties` for the
   **base** `g_w_lghtsbr01` reads 29 entries including FIVE `AttackBonus`
   (cost_value 3,2,3,2,1) while `w_melee_01` reads 0 — a base lightsaber does not
   grant +11 attack in-game, so the parsed property list cannot be applied as
   flat bonuses. Before any item-property wiring: determine whether PyKotor is
   mis-parsing the PropertiesList vs. these being upgrade-slot/template rows,
   find where the true bonus magnitude lives, and validate against a weapon's
   real retail stat. Shipping on the current parse would make PIE combat grossly
   unfaithful — which the goal forbids.
4. **Animated dialogue camera tracks**. Needs a viewport camera-track API the
   ArcBall renderer lacks; rare in data (5 of ~2,751 sampled nodes), so lowest
   priority. Until then PIE falls back to the solved static shot (tracked).
5. **Scripting state (general NWScript)**. The bounded global-write subset is
   **done** (2026-07-17): a module OnEnter script's literal `SetGlobalNumber`/
   `SetGlobalBoolean`/`AddJournalQuestEntry` writes are executed into the PIE
   global sandbox at Play start (`map_studio_pie_scripting.py` →
   `create_map_studio_pie_session`), verified in-app on real 207TEL. Remaining:
   local variables (`SetLocalBoolean` 680 / `SetLocalNumber` 682 — 207TEL issues
   `SetLocalBoolean` 18x; needs the object-arg → tag resolution to key PIE
   `local_booleans`), string globals (`SetGlobalString` 160), and control-flow
   routines (`OpenStore`, `ActionStartConversation`). Still no general VM: only
   literal-argument, straight-line writes are executed.

### Evidence notes for future slices

- **Weapon damage type** (baseitems.2da `damageflags`) — DONE 2026-07-17.
  The full bitfield→label map was reconstructed from KOTOR's own `nwscript.nss`
  `DAMAGE_TYPE_*` constants (1 Bludgeoning … 2048 Ion, 4096 Blaster/Energy) and
  wired live through the resolver → inspection → entity → combat stats → the
  `attack_hit` line ("N Energy damage"). Verified in-app: Lightsaber → Energy.
- **Module entry** (exploration): PIE already spawns the player at the authored
  IFO entry point + facing (`placements.entry_point`); no gap.
- **NWScript ACTION routine ids** (scripting state) — DONE 2026-07-17, and a
  correction: earlier notes listed SetGlobalNumber=577 / SetGlobalBoolean=575 /
  AddJournalQuestEntry=364. **Those are wrong.** The authoritative source is
  PyKotor's engine function table (`pykotor.common.scriptdefs.KOTOR_FUNCTIONS` /
  `TSL_FUNCTIONS`, identical for K1/K2): **GetGlobalBoolean=578,
  SetGlobalBoolean=579, GetGlobalNumber=580, SetGlobalNumber=581,
  AddJournalQuestEntry=367, SetGlobalString=160, GetGlobalString=194,
  GetLocalBoolean=679, SetLocalBoolean=680, GetLocalNumber=681,
  SetLocalNumber=682**. Confirmed against real 207TEL `k_207tel_enter` bytecode
  (`ActionPlayAnimation=40`, `GetObjectByTag=200` also match). A regression test
  (`test_routine_numbers_match_pykotor_engine_function_table`) pins these to the
  live table; do not hand-count nwscript.nss declaration order.

## Verification discipline (per slice)

Each slice: cross-check Ghidra/real-resource evidence → implement in the owning
headless core (Qt-free) → mirror across root `src/` / Scene / Tools → focused
tests → rebuild the Debug app, stage 18 payload DLLs, and run a focus-safe
visible PIE proof. Retail KOTOR remains the final authority.
