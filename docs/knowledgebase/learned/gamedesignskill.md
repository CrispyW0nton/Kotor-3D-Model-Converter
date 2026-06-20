# Game Design And Tool Experience Skill

Use this skill when shaping GhostRigger workflows, tool feedback, validation
states, onboarding flows, task loops, or game-facing user experiences.

## Book Grounding

- `Designing_games_-_Tynan_Sylvester.pdf`: mechanics/events, emotional triggers,
  elegance, skill range, challenge, failure handling, narrative tools, world
  coherence, information availability, balance, metaphor vocabulary, playtest
  loops, planning horizons, and motivation.
- `Refactoring_UI_-_Steve_Schoger.pdf`: hierarchy, spacing, text, color, depth,
  and systematized UI decisions.
- `Game_Engine_Architecture_4Ed_-_Jason_Gregory.pdf`: tools, debug menus,
  screenshots, profiling, and runtime development support.

## Workflow

1. Identify the user task loop: trigger, action, feedback, correction, proof,
   and next action.
2. Remove mechanics/workflow steps that cost attention without adding control,
   safety, or understanding.
3. Avoid information starvation. Show enough state for the user to understand
   what happened, what is blocked, and what action is safe next.
4. Use consistent metaphor vocabulary: the same icon, label, state color, and
   interaction pattern should mean the same thing across tools.
5. Treat failure as part of the workflow. Validation errors should be specific,
   recoverable, and tied to the object/resource involved.
6. Use playtest-style visible checks for workflow changes: can a user complete
   the intended loop without hidden setup or ambiguous state?
7. Keep planning horizons short enough to learn from real tool behavior, but
   long enough to avoid incoherent one-off UI.

## Tool Experience Questions

- What is the user trying to accomplish in one sitting?
- What state must be visible before they act?
- What feedback confirms the action worked?
- What recovery path exists if validation fails?
- Which choices are meaningful and which are busywork?
- Can the same concept use the same word/icon/state across panels?
- Does the workflow teach through interaction rather than long explanatory text?

## Design Failure Patterns

- Too many controls before the user has a concrete task.
- Hidden readiness state that forces trial and error.
- Inconsistent labels for the same concept across workbenches.
- Validation messages that name symptoms but not the object/resource involved.
- Tool loops that require broad scans or exports to answer a small question.

## GhostRigger Applications

- Map Studio workflow spines and readiness panels.
- Character Studio validation/export gates.
- Retarget and Sequence Editor task flow.
- Resource Browser and content discovery.
- Error messages, proof recording, staged export, and game-test handoff.

## Validation

- Verify happy path and one blocked/error path.
- Check that the UI explains readiness without tutorial text overload.
- Prefer visible app testing for workflow state changes.
