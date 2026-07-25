# Vanilla KOTOR Module Spatial Semantics

Evidence scan: **199 shipping modules**, **27132 staged GIT objects** across KOTOR 1 and 2.
The full per-object evidence (position, template, inferred purpose, confidence, threshold/path distance, density, perimeter/centre placement, and pairing) is stored in `Saved/Codex/vanilla_module_spatial_semantics.json`.

## What the retail maps teach Map Studio

1. **Doors are thresholds, never loose props.** A door belongs to a wall opening, controls circulation, and may carry a module transition. Map Studio must reject or warn on an unanchored door.
2. **Decoration reinforces function.** Repeated statues, lamps, consoles, and banners commonly form door-flanking pairs or architectural rhythms; they are not uniformly scattered.
3. **Furniture defines activity nodes.** Chairs, tables, beds, bars, and terminals should be placed as coherent use areas with facing and clearance, not as generic filler.
4. **Waypoints and PTH points reveal intended circulation.** Functional objects sit beside paths; clutter must preserve the route instead of occupying it.
5. **Perimeter and centre have different jobs.** Utility, storage, cover, and most dressing stay near edges. Monuments and navigation landmarks may occupy controlled central nodes.
6. **Encounter, trigger, camera, and sound objects author invisible experience layers.** Their positions express pacing, arrival, reveal, combat, and ambience even when they have no visible mesh.

## Observed role counts

| Purpose role | Instances |
|---|---:|
| Script Or Patrol Anchor | 4,759 |
| Ambient Audio Zone | 3,949 |
| Decorative Or Utility Prop | 2,680 |
| Navigation Landmark | 2,378 |
| Authored Viewpoint | 2,346 |
| Narrative Actor | 1,592 |
| Interactive Prop | 1,537 |
| Functional Threshold | 1,394 |
| Scripted Event Volume | 1,291 |
| Ambient Population | 1,052 |
| Storage Or Reward Container | 802 |
| Activity Furniture | 725 |
| Combat Or Security Actor | 662 |
| Spawn Or Transition Anchor | 421 |
| Gameplay Hazard Volume | 384 |
| Interactive Terminal | 327 |
| Environmental Dressing | 267 |
| Functional Transition Gate | 155 |
| Functional Transition Volume | 125 |
| Combat Spawn Zone | 120 |
| Landmark Or Civic Decor | 70 |
| Service Inventory | 54 |
| Combat Support Prop | 20 |
| Service Actor | 13 |
| Lighting Fixture | 9 |

## Spatial relationship counts

| Relationship | Instances |
|---|---:|
| Perimeter | 7,936 |
| Clustered | 4,480 |
| Isolated | 3,640 |
| Circulation Adjacent | 2,925 |
| Central | 2,707 |
| Threshold Adjacent | 395 |
| Door Flanking Pair | 310 |

## Product rules derived from the evidence

- Every Content Browser item should declare a placement role: structural threshold, functional interaction, activity furniture, landmark, perimeter dressing, combat support, ambience, or script volume.
- Functional thresholds require a wall/portal anchor and a clear walkable approach on both sides.
- Decorative pairs require a shared anchor and deliberate symmetry or rhythm; the editor should offer paired placement instead of random duplication.
- Activity props require an activity node, facing target, and clearance envelope.
- The placement audit should report path blockage, unanchored doors, isolated utility objects, unsupported centre clutter, and decorative objects with no stated rationale.
- Automatic staging may suggest evidence-backed arrangements, but authored meaning must remain explicit and editable by the level designer.

## Families covered

- Dantooine: 15 module(s)
- Dxun: 7 module(s)
- Ebon Hawk: 12 module(s)
- Endar Spire: 2 module(s)
- Harbinger: 4 module(s)
- Kashyyyk: 8 module(s)
- Korriban: 13 module(s)
- Leviathan: 4 module(s)
- Malachor/Coruscant: 8 module(s)
- Manaan: 11 module(s)
- Nar Shaddaa: 9 module(s)
- Onderon: 9 module(s)
- Other: 21 module(s)
- Peragus: 7 module(s)
- Ravager/M4-78: 3 module(s)
- Star Forge: 4 module(s)
- Taris: 23 module(s)
- Tatooine: 12 module(s)
- Telos: 17 module(s)
- Unknown World: 9 module(s)
- Yavin: 1 module(s)
