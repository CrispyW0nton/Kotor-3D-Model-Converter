# MANDATORY PRE-TASK CHECKLIST
# ============================================================
# YOU MUST READ THIS FILE BEFORE STARTING ANY CODING TASK.
# This is not optional. Every single task begins here.
# ============================================================

## STOP. Before you write a single line of code:

### Step 1: Read the Knowledge Base Index
```
cat .ghostrigger_reference/knowledge_base/INDEX.md
```

### Step 2: Identify which deliverable your task falls under
- D1: FBX Export Fix -> read `knowledge_base/d1_fbx_export.md`
- D2: Texture Wrapping Fix -> read `knowledge_base/d2_texture_wrapping.md`
- D3: GPU Renderer Foundation -> read `knowledge_base/d3_gpu_renderer.md`
- D4: Character Builder -> read `knowledge_base/d4_character_builder.md`
- D5: Performance & Memory -> read `knowledge_base/d5_performance.md`
- D6: Module Editor & Scene -> read `knowledge_base/d6_module_scene.md`

### Step 3: Check the cross-reference map
```
cat .ghostrigger_reference/knowledge_base/cross_reference_map.md
```
Find the feature you're implementing. Note which reference repos and book sections apply.

### Step 4: Check the book knowledge extract
```
cat .ghostrigger_reference/knowledge_base/book_extracts.md
```
Find the relevant section. Make sure your approach aligns with established principles.

### Step 5: Check the roadmap for task dependencies
```
cat .ghostrigger_reference/ROADMAP.md
```
Verify your task's prerequisites are complete and you're not skipping ahead.

### Step 6: Read the specific source file you're about to modify
Always read the FULL file before editing. Never edit blind.

### Step 7: Verify your approach against the acceptance criteria
Each task has explicit acceptance criteria in the roadmap. Know them before coding.

## AFTER completing a task:
1. Run syntax check on all modified files
2. Verify no regressions in existing functionality
3. Check that acceptance criteria are met
4. Commit with prescribed message format
5. Update the roadmap status

## RED FLAGS - Stop and re-read the knowledge base if:
- You're about to create a new matrix math function (check Mukundan Ch 7 / Gregory Ch 5)
- You're writing shader code (check Hayes Ch 4, 7, 9)
- You're implementing skinning/bones (check Mukundan Ch 7.5-7.6)
- You're building a resource manager (check Gregory Ch 7.2)
- You're designing a render loop (check Gregory Ch 8)
- You're writing FBX structures (check ufbx reference, KotorBlender export)
- You're handling UV coordinates (check KotOR.js TPC/texture handling)
- You're working with MDL format (check PyKotor MDL parser, xoreos)
