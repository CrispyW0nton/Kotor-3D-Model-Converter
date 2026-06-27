# Coupling Design & Rebalancing Skill

Use this skill when making the **decision** about coupling: merge vs split, when
to decouple vs when coupling is *intentional*, how to score a boundary across the
five coupling dimensions, how to evaluate module cohesion as a merge/split
signal, and how to **rebalance** coupling that has drifted into churn. This is
the decision-process companion to `learned/couplingskill.md`, which owns the
*taxonomy* (the connascence spectrum, the seven cohesion levels, patterns as
boundary tools). Read that one for "what kind of coupling is this?"; use this one
for "so what do I do about it, and is the coupling even worth keeping?"

## Book Grounding

- `Balancing_Coupling_in_Software_Design_-_Vlad_Khononov.pdf`: the **five
  dimensions** of coupling (strength, distance, volatility, type, cost),
  magnitude of coupling, the flow of knowledge, *balancing* rather than
  minimising coupling, **rebalancing** drifted coupling, and the **fractal
  geometry** of software design (same rules at function/class/package/project
  scale). Part III is the part the taxonomy skill does not cover.
- `Structured_design_-_Larry_L_Constantine.pdf`: scope of effect vs scope of
  control, span of control, fan-in/fan-out, and the transform-vs-transaction
  morphology heuristics — the *decision* machinery that sits on top of the
  cohesion levels catalogued in `couplingskill.md`.
- `Software_Design_for_Python_Programmers_-_Maximiliano_Mak.pdf`: good class
  design (cohesion, single responsibility), hide class implementations, don't
  surprise users, and design subclasses right (LSP). The Python-specific lens
  for evaluating whether a class, module, or package is genuinely *one*
  cohesive thing — and therefore a defensible boundary.

## Core Idea: Balance, Don't Minimise

Zero coupling means a system with no interactions. The goal is never zero — it
is to keep *essential* coupling (the knowledge a collaboration genuinely needs)
deliberate, explicit, and low-magnitude, and to eliminate *accidental* coupling
(knowledge leaking across a boundary for no reason, or lifecycle cost with no
benefit). Most coupling debates are lost because teams optimise a single
dimension ("decouple everything", or "merge everything") instead of balancing the
five. Score the boundary on all five; only a high-cost, high-volatility,
high-distance, high-strength boundary justifies a formal contract.

## The Five Coupling Dimensions — Score Any Boundary

For each candidate boundary, answer the five questions (1 = cheap/low, 5 =
expensive/high). The worst dimension dominates the decision.

1. **Strength** — how much knowledge flows across it? This is the connascence
   level; use the spectrum in `couplingskill.md`. A name/type coupling scores 1;
   a value/identity coupling scores 4–5 and usually says "merge, don't bridge."
2. **Distance** — how far apart are the two sides in the build/runtime/deploy
   graph? Same module = 1; same package = 2; different packages, same build = 3;
   different DLLs/builds = 4; different machines/processes = 5. High strength
   over high distance is where the pain lives.
3. **Volatility** — how often does each side change? Coupling toward a stable,
   low-volatility upstream is cheap; coupling toward a volatile downstream is
   expensive. The layering rule ("core must not import Qt") exists because Qt is
   highly volatile presentation and core is highly stable — coupling the stable
   to the volatile maximises churn.
4. **Type** — data / stamp / control / common-environment / content coupling
   (Constantine). Content coupling (one side reaches into the other's internals)
   is always a 5.
5. **Cost** — the engineering price of changing one side when the other changes:
   rebuild, retest, payload regeneration, DLL recompile, manifest/.rc/registry
   churn, byte-identity test updates. In GhostRigger every native package carries
   a high *cost* dimension by construction.

**Decision rule:** if strength is high AND the sides are born-together (shared
lifecycle, change together), the cost of a formal boundary exceeds its value —
merge. If strength is low but cost is high (an empty package that must still be
built/packaged/tested), the boundary is pure accidental lifecycle coupling —
delete or fold it.

## Cohesion as a Merge/Split Signal

Cohesion is the *inverse* of coupling (Constantine's key result), and it is the
more usable handle because it answers "does this belong together as a unit?"

**Cohesion evaluator** (apply to any package, module, or class):

- Can you state its purpose in one sentence that is **not** also true of another
  owner? If two owners both fit the sentence, you have an overlap → merge toward
  the canonical owner.
- Are its elements *born together* — do several of them have to change in
  lockstep to stay valid (connascence of value/algorithm/identity)? Then splitting
  them only adds a synchronisation bridge → merge.
- Does it have *no* cohesive principle at all (empty placeholder, "for later")?
  It is coincidentally cohesive at best and carries lifecycle cost with zero
  benefit → delete or fold.

**Mak's class-design reinforcement:** a class or module should have **one reason
to change** (SRP). If you can list several independent reasons it changes
(layout/theme reasons *and* interaction-model reasons *and* data reasons), that
is several owners fighting inside one unit — split the *responsibility* first,
then let each land in its owning package. And a well-designed module **hides how
and exposes what**: a module whose internal data structures are read and mutated
by many callers has low implementation hiding and therefore high accidental
coupling, regardless of how "clean" its file looks.

## When Coupling Is Intentional (Balancing, Not Minimising)

Not all coupling is a smell. Coupling is *intentional* and correct when:

- The components share a **lifecycle** (built, deployed, tested together) and the
  knowledge they share is genuinely required by the collaboration. Forcing a
  boundary here adds a bridge you then must keep in sync — net *more* coupling.
- The connascence is at the **value/algorithm/identity** end of the spectrum,
  which is precisely the signal to *keep things close*, not to decouple.
- One side is a **stable upstream** (core, math, formats) that many downstreams
  depend on; high fan-in / low fan-out on a stable leaf is the morphology
  Constantine recommends, not a problem to fix.

## Rebalancing Drifted Coupling (Khononov Part III)

Coupling that once made sense can drift into churn: a boundary that now forces
every change to touch two sides, a contract that has grown to mirror the
implementation behind it, or a split that exists only to preserve a past naming
batch. Rebalance by choosing one of two moves — never a third "add more
indirection" move:

1. **Merge** if the sides are born-together (high strength, shared lifecycle,
   same cohesive purpose). The bridge was the smell.
2. **Introduce or harden a stable contract** if they are genuinely separate: push
   a minimal name/type-coupled interface into the upstream layer, let the
   downstream implement it, and keep the contract more stable than the
   implementation. A shallow contract that is a 1:1 field copy of the
   implementation model encapsulates nothing — it is a moving part with no value;
   deepen it or delete it.

## Fractal Geometry: Same Rules at Every Scale

The coupling rules are scale-invariant. The function-level junk-drawer helper,
the `helpers.py`/`utils.py` module pile, the GUI package that also owns export
logic, and the empty `Domain.Core.*` placeholder package are the **same
anti-pattern at four different scales**. When you spot it at one scale, check the
others. AGENTS.md's "no helpers.py/utils.py piles" rule and the ownership model's
"merge thin/duplicate packages" mandate are the same instruction expressed at
module scale and package scale.

## GhostRigger Application

### The package-sprawl triage (package scale)

The native tree carries ~19 Visual Studio projects but a much larger set of
declared packages, with a known tail of empty/duplicate `Domain.Core.*` stubs
that the ownership model's "Merge Rules" section already targets. Score each
candidate against the five dimensions: an empty stub has **strength 0** (no
knowledge flows) but **cost 4–5** (it is still a payload-manifest entry, a `.rc`
RCDATA line, a registry row, and a byte-identity test target that must be
maintained in lockstep). Cost with zero strength is pure accidental lifecycle
coupling → fold into the nearest real owner or delete. A duplicate that shares
the same functional purpose with an existing owner is a cohesion overlap → merge.

### Distance dimension: the DLL-embedded payload resolution chain

Trace the import distance for one packaged module at runtime:

```
gui panel -> service -> src/core/... -> _DllPythonPayloadImporter.find_spec
   -> ctypes kernel32.FindResourceA -> LoadResource -> LockResource -> RCDATA blob
   -> compile(source, filename, "exec") -> exec into module dict
```

This chain is **long distance (5) AND high strength (byte-identity is the
contract)**. That combination is normally a warning — but here it is
**intentional coupling**: the host DLL and its embedded payload share one
lifecycle (one build, one deploy), so the strength is justified and the boundary
is correct. The rebalancing move is *not* to add indirection; it is to enforce
the existing discipline — never hand-edit a packaged copy, regenerate from
canonical `src/`, keep compile flags identical, because byte-identity is what
makes the long-distance coupling safe. The empty-file sha256 sentinel
(`e3b0c442…`) handled in `get_data` is a real edge of that contract to preserve
in any refactor.

### GUI Display vs GUI Helpers — a cohesion test that confirms a *correct* split

Apply the evaluator to the `GUI.Display` / `GUI.Helpers` split the ownership
model mandates. Display = "what the user **sees**" (panels, layout, styling,
labels, notifications) — functional cohesion around presentation. Helpers =
"what the user **interacts with** in the viewport" (gizmos, manipulators,
transform handles, pickers, snapping) — functional cohesion around interaction.
They share the viewport and Qt, but they have **different reasons to change**
(theme/layout vs interaction model). Mak's SRP: two reasons to change → two
owners. This split *passes* the cohesion test; it is correct architecture, not
sprawl. By contrast, a proposal to split Display into "left panels" and "right
panels" would fail the test — same reason to change, no distinct cohesive
principle.

### Scope of effect vs scope of control (Constantine)

When a one-line code change forces updates to imports, payload manifests, `.rc`
resource lists, the package registry, and byte-identity tests, that is
**scope of effect >> scope of control** — the signature of high accidental cost.
The ownership model's "Change Procedure" (search owners → pick canonical owner →
update imports/registry/manifests → regenerate → targeted tests) is the
discipline that keeps scope of effect proportional to scope of control.

## Merge/Split Decision Tree

1. **Does it have a single cohesive purpose no other owner already claims?**
   No / overlaps an owner → **merge** into that owner.
2. **Are its elements born-together with elements elsewhere** (change in
   lockstep)? Yes → **merge** (splitting only adds a sync bridge).
3. **Is it empty or a placeholder?** Yes → **delete or fold** (cost without
   strength).
4. **Does it have a distinct reason to change AND a distinct lifecycle/runtime/
   ABI/deployment boundary** from every other owner? Yes → it earns a separate
   package; design a minimal, stable, name/type-coupled contract at the boundary.
5. If you reached 4 only by naming, not by a durable boundary → **merge**.

## Coupling Dimensions Checklist (score 1–5; worst dominates)

| Dimension | Question | Merge signal |
|---|---|---|
| Strength | How much knowledge flows? | High + born-together → merge |
| Distance | How far apart in build/runtime/deploy? | High + low strength → accidental, fold |
| Volatility | How often does each side change? | Coupling stable←volatile → keep/merge toward stable |
| Type | data / stamp / control / common / content? | content coupling → always fix |
| Cost | Build/test/payload/DLL/registry churn per change? | High cost + low strength → merge/delete |

## Anti-Patterns to Reject

- Splitting born-together code "for cleanliness" — you traded essential coupling
  for a larger amount of accidental coupling.
- Merging genuinely-distinct reasons-to-change into one god-package — violates
  SRP and re-creates coupling inside the unit.
- Adding a shallow contract that mirrors the implementation model 1:1 — a moving
  part that encapsulates nothing.
- Optimising a single dimension ("decouple everything", or "one package per
  idea") instead of balancing the five.
- Keeping a boundary only because it already exists; the ownership model says do
  not keep a package merely because it exists.

## Cross-References

- `learned/couplingskill.md` — the connascence spectrum, the seven cohesion
  levels, and patterns-as-boundary-tools (Facade/Adapter/Bridge mapped to
  integration strength). Read it first; this skill is the decision process built
  on top of that taxonomy.
- `learned/architectureskill.md` — the WHAT of layering and ownership (which
  owner); this skill is the WHY of boundary decisions.
- `knowledge_base/package_ownership_model.md` — the merge mandate and change
  procedure this skill operationalises.
- `learned/cppnativeskill.md` — the native host / embedded Python boundary whose
  payload chain this skill analyses.
- `AGENTS.md` — layering rules and the "no helpers.py/utils.py" rule.
