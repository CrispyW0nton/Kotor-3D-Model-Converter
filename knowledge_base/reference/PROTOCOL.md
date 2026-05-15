# GhostRigger AI Developer Protocol
# ===================================
# This file defines the MANDATORY workflow for every coding task.
# It is checked into version control and must never be deleted.

## HARD RULE: Before ANY code modification, execute this sequence:

### 1. Read the mandatory checklist
```bash
cat knowledge_base/reference/MANDATORY_CHECKLIST.md
```

### 2. Identify the task in the roadmap
```bash
cat knowledge_base/roadmap/02_roadmap_2026_05.md            # current Qt-branch roadmap
cat knowledge_base/reference/ROADMAP_legacy_2026_04.md      # legacy pre-Qt roadmap (T001-T804)
```
Find the task ID (T001-T804). Note:
- What milestone it belongs to
- Its dependencies (are they complete?)
- Its acceptance criteria
- Which files to modify

### 3. Read the deliverable knowledge file
```bash
cat knowledge_base/reference/deliverables/d<N>_<name>.md
```

### 4. Check the cross-reference map
```bash
cat knowledge_base/reference/cross_reference_map.md
```
Identify:
- Which reference repos to consult
- Which book sections apply
- What the known-good patterns are

### 5. Consult book extracts for the relevant principle
```bash
cat knowledge_base/reference/book_extracts.md
```
Find the section that matches your task. Verify your planned approach aligns.

### 6. If reference repos are cloned, study the relevant code
```bash
# Example for FBX work:
cat .reference_repos/ufbx/ufbx.h | grep -A 20 "ufbx_skin_cluster"
# Example for texture work:
find .reference_repos/kotorjs -name "*.ts" | xargs grep "GL_REPEAT"
```

### 7. Read the FULL source file before editing
```bash
wc -l src/<path>/<file>.py  # Know how big it is
cat src/<path>/<file>.py     # Read it all
```

### 8. State your diagnosis and plan BEFORE writing code
Explain:
- What the current code does wrong
- What the fix is (citing reference repo or book)
- Which lines will change
- Why this approach is correct

### 9. After coding, verify:
- [ ] File parses without syntax errors
- [ ] Acceptance criteria met
- [ ] No regressions in other features
- [ ] Commit with prescribed message

---

## Why This Protocol Exists

GhostRigger has complex interdependencies between:
- KOTOR's MDL/MDX binary format (proprietary)
- FBX's object model (partially documented)
- OpenGL rendering conventions
- Multiple reference implementations in different languages

Without consulting references, it is trivially easy to:
- Get matrix conventions wrong (column-major vs row-major)
- Compute bind-pose matrices incorrectly
- Use wrong UV wrap modes
- Misunderstand KOTOR-specific structures (supermodels, hooks, TXI)

The knowledge base exists to prevent hallucinated solutions. Use it.
