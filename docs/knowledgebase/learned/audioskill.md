# Audio And Event Tooling Skill

Use this skill for audio-like event systems, timeline events, dynamic state
mixing, randomization, debugging tools, and future sound/foley workflows.

## Book Grounding

- `Game_Audio_Programming_-_Guy_Somberg.pdf`: audio object management,
  state-based dynamic mixing, one-shot envelopes, random sound effects,
  environmental interaction sounds, background sounds, open-world music systems,
  thread-safe command buffers, audio designer workflows, debugging tools, and
  automatic footsteps/foley.
- `Designing_games_-_Tynan_Sylvester.pdf`: emotion, feedback, atmosphere,
  information, and playtest motivation.
- `Fundamentals_of_Computer_Graphics`: signal-processing concepts such as
  sampling, convolution, filtering, and aliasing also apply to time/audio data.

## Workflow

1. Treat audio/events as data-driven state, not scattered imperative triggers.
2. Define event source, timing, payload, routing, priority, and lifetime.
3. For one-shot events, specify envelope/decay behavior and duplicate suppression
   rules.
4. For randomization, document the allowed variation space and preserve
   debuggability with seeds or emitted choice records.
5. For dynamic mixing/state changes, separate state detection from response
   policy.
6. For threaded or real-time event queues, use command buffers and explicit
   ownership. Never let producer/consumer lifetimes be implicit.
7. Build debugging surfaces that show active objects/events, recent triggers,
   states, volumes/weights, and missing assets.

## GhostRigger Applications

- Future audio/foley support.
- Animation timeline event markers.
- Footstep/foley detection from animation or contact events.
- Sequence Editor event tracks.
- Validation/event buses and debug record viewers.
- Any tool that needs reliable, inspectable state transitions.

## Validation

- Test duplicate, missing asset, stale state, and rapid-fire event cases.
- Verify deterministic playback/debug output where possible.
- For threaded queues, test shutdown/flush behavior and error propagation.
