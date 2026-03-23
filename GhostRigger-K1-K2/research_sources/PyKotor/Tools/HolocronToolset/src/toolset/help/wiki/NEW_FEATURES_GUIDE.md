# Holocron Toolset - New Features Quick Guide 🚀

**10 Powerful New Features Now Available!**

---

## 🌟 Quick Start: What's New?

### 1. Navigate to Favorites Instantly ⭐
**What it does:** Jump directly to any bookmarked resource with one click

**How to use:**
1. Bookmark resources (Ctrl+B or right-click → Add to Favorites)
2. Open Favorites (Ctrl+Shift+B)
3. Select a favorite → Click "Go To"
4. ✨ Instantly navigates to that resource in the file browser

**Why it's useful:** No more searching through thousands of files to find frequently used resources!

---

### 2. Rename Resources Safely 📝
**What it does:** Rename resources with automatic validation and safety checks

**How to use:**
1. Right-click any resource in Override folder
2. Select "Rename..."
3. Enter new name (extension preserved automatically)
4. Confirm if file exists
5. ✅ Resource renamed and refreshed in browser

**Safety features:**
- Only works in Override folder (protects core game files)
- Automatically preserves file extensions
- Detects name collisions before renaming
- Shows clear error messages if something goes wrong

**Example:** Rename `my_texture.tpc` → `character_head.tpc` in seconds!

---

### 3. Move Resources (Cut/Paste) ✂️
**What it does:** Move resources between folders using familiar Cut/Paste

**How to use:**
1. Select resource(s) in Override
2. Cut (Ctrl+X or right-click → Cut)
3. Navigate to destination folder
4. Paste (Ctrl+V or right-click → Paste)
5. ✅ Resources moved, model updated automatically

**Example:** Organize your Override folder by moving all textures into a `textures/` subfolder!

---

### 4. Batch Operations 📦
**What it does:** Process dozens or hundreds of files at once with progress tracking

**How to use:**
1. Select multiple resources (Shift+Click or Ctrl+Click)
2. Right-click → "Batch Operations..." (or Ctrl+Shift+O)
3. Choose operation:
   - **Extract All** - Save all to a folder
   - **Duplicate All to Override** - Copy all to Override
   - **Delete All** - Remove all (with confirmation)
   - **Rename with Pattern** - Bulk rename with wildcards
4. Watch progress bar
5. ✅ Get summary: "Success: 47, Failed: 0, Skipped: 2"

**Example:** Extract 100 texture files to `C:\Backup\Textures\` in under 10 seconds!

---

### 5. Rename with Pattern 🔤
**What it does:** Rename multiple files using wildcard patterns

**How to use:**
1. Select files to rename
2. Batch Operations → "Rename with Pattern"
3. Enter find pattern: `old_*.tpc` (use * for any text)
4. Enter replace pattern: `new_*.tpc`
5. Preview: "15 files will be renamed"
6. Click OK
7. ✅ All matching files renamed instantly!

**Examples:**
- `texture_*` → `char_*` renames `texture_001.tpc` to `char_001.tpc`
- `temp_*` → `*` removes "temp_" prefix from all files
- `*_old` → `*` removes "_old" suffix

**Why it's powerful:** Rename 50 files in seconds instead of manually one-by-one!

---

### 6. Open With... Dialog 📂
**What it does:** Choose which editor to open a resource in

**How to use:**
1. Right-click any resource
2. Select "Open With..."
3. See list of available editors:
   - **For GFF files:** Generic GFF Editor OR Specialized Editor
   - **For others:** The appropriate editor for that type
4. Select preferred editor
5. ✅ Resource opens in chosen editor

**Example:** 
- Want to edit a dialog (DLG) in the generic GFF editor to see raw structure? Choose "Generic GFF Editor"
- Want to use the specialized dialog tree editor? Choose "Dialog Editor"

**Supported editors:**
- Dialog Editor, Creature Editor, Placeable Editor, Door Editor
- Item Editor, Trigger Editor, Sound Editor, Waypoint Editor
- 2DA Editor, Script Editor, Texture Editor, Model Editor
- And many more!

---

### 7. Create New Resources 🆕
**What it does:** Create new resources from templates with one dialog

**How to use:**
1. Right-click on any folder OR File → New
2. Select "New Resource..."
3. Choose resource type from list:
   - 2DA Table, Script Source, Creatures, Placeables
   - Items, Triggers, Dialogs, Journals, and more!
4. Enter resource name
5. Confirm if file exists
6. ✅ Resource created with proper structure
7. Optional: Open immediately in appropriate editor

**What gets created:**
- **2DA files:** Minimal valid 2DA header
- **Script files (NSS):** Empty text file ready for coding
- **GFF files (UTC, DLG, etc.):** Minimal valid GFF structure with TemplateResRef
- **Text files (TXT, TXI):** Empty text file

**Example:** Create a new creature (UTC) template in 5 seconds instead of copying and clearing an existing one!

---

### 8. Save Editors (Ctrl+S) 💾
**What it does:** Save editor changes back to your installation

**How to use:**

**Single editor open:**
- Press Ctrl+S
- ✅ Editor saves immediately

**Multiple editors open:**
- Press Ctrl+S
- Dialog shows all open editors
- Choose: Save selected, Save All, or Cancel
- ✅ Chosen editors saved to Override folder

**How it works:**
- Automatically detects open editor windows
- Calls the editor's save method
- Saves to Override folder (or current location)
- Refreshes the file browser
- Shows "Saved: filename.ext" message

**Example:** Edit 3 different dialog files, press Ctrl+S → "Save All" → all changes written to disk!

---

### 9. Favorite Star Indicator ★
**What it does:** Shows ★ in status bar when selected resource is bookmarked

**How to use:**
- Just select any resource
- If it's in your favorites, status bar shows: "1 item(s) selected ★"
- No star? It's not bookmarked yet!

**Why it's useful:** Instantly know if a resource is bookmarked without opening the favorites dialog.

---

### 10. Command Palette Enhancements 🎨
**What it does:** Quick access to all features via keyboard

**How to use:**
1. Press Ctrl+Shift+P (Command Palette)
2. Type to filter: "save", "new", "batch", "open", etc.
3. Select command
4. ✅ Command executes immediately

**New commands added:**
- File: Save Editor
- File: Open With...
- File: New Resource
- All batch operations
- All navigation commands

**Example:** Press Ctrl+Shift+P, type "new", select "File: New Resource" → create dialog opens!

---

## 🎯 Workflow Examples

### Scenario 1: Organizing Mod Files
**Goal:** Move all textures to a `textures/` subfolder in Override

1. Create `Override/textures/` folder
2. Select all `.tpc` and `.tga` files in Override root
3. Cut (Ctrl+X)
4. Open `textures/` folder
5. Paste (Ctrl+V)
6. ✅ All textures organized!

---

### Scenario 2: Bulk Renaming Textures
**Goal:** Rename all mod textures to have unique prefix

1. Select all your mod's `.tpc` files
2. Batch Operations (Ctrl+Shift+O)
3. Choose "Rename with Pattern"
4. Find: `*.tpc`
5. Replace: `mymod_*.tpc`
6. Preview: "23 files will be renamed"
7. OK
8. ✅ All textures renamed: `texture.tpc` → `mymod_texture.tpc`

---

### Scenario 3: Creating a New Mod
**Goal:** Create new creature, dialog, and items from scratch

1. File → New Resource (or right-click folder)
2. Create Creature (UTC):
   - Select "Creature (.utc)"
   - Name: `my_npc`
   - Opens in Creature Editor
3. Create Dialog (DLG):
   - Select "Dialog (.dlg)"
   - Name: `my_npc_dialog`
   - Opens in Dialog Editor
4. Create Item (UTI):
   - Select "Item (.uti)"
   - Name: `my_sword`
   - Opens in Item Editor
5. ✅ All templates created with proper structure, ready to edit!

---

### Scenario 4: Backing Up Before Changes
**Goal:** Extract all Override files before making changes

1. Select all resources in Override (Ctrl+A)
2. Batch Operations (Ctrl+Shift+O)
3. Choose "Extract All"
4. Select backup folder: `C:\Backups\KotOR\2026-02-02\`
5. Watch progress: "Extracting... (150/324)"
6. ✅ Complete: "Successfully extracted 324 files"

---

### Scenario 5: Multi-Editor Workflow
**Goal:** Edit multiple files and save all at once

1. Open dialog file (DLG)
2. Open related script (NSS)
3. Open creature template (UTC)
4. Make changes in all 3 editors
5. Press Ctrl+S
6. Click "Save All"
7. ✅ All 3 files saved to Override!

---

## ⌨️ Essential Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+S** | Save current editor |
| **Ctrl+N** | New resource (if mapped) |
| **Ctrl+X** | Cut selected resources |
| **Ctrl+V** | Paste resources |
| **Ctrl+B** | Bookmark resource |
| **Ctrl+Shift+B** | Show favorites |
| **Ctrl+Shift+O** | Batch operations |
| **Ctrl+Shift+P** | Command palette |
| **F5** | Refresh browser |
| **Delete** | Delete selected |

---

## 💡 Pro Tips

### Tip 1: Use Favorites for Frequently Edited Files
Bookmark your mod's main files (master dialog, main script, key creatures) for instant access!

### Tip 2: Batch Operations Are Your Friend
Need to extract, duplicate, or delete 100+ files? Use batch operations instead of one-by-one!

### Tip 3: Pattern Renaming Saves Hours
Renaming 50 textures? Use patterns: `*.tpc` → `mymod_*.tpc` (literally 5 seconds vs 10+ minutes)

### Tip 4: Open With for Advanced Editing
Need to see raw GFF structure? Use "Open With..." → Generic GFF Editor
Need specialized editing? Use "Open With..." → Specialized Editor

### Tip 5: Create Resources from Templates
Never copy-paste templates again! Create new resources with proper structure built-in.

### Tip 6: Save All for Multi-File Edits
Working on multiple files? Open all editors, make all changes, then "Save All" at once!

### Tip 7: Command Palette Is Faster
Instead of right-click menus, press Ctrl+Shift+P and type what you want!

---

## 🛡️ Safety Features

### You're Protected By:
- ✅ **Override-only operations** - Can't accidentally modify core game files
- ✅ **Automatic backups** - Use "Extract All" before major changes
- ✅ **Collision detection** - Always prompted before overwriting files
- ✅ **Comprehensive validation** - Invalid operations prevented before execution
- ✅ **Clear error messages** - Always know what went wrong and why
- ✅ **Operation summaries** - See exactly what succeeded/failed after batch operations

---

## 🎓 Learning Path

### New to the Toolset?
1. Start with **Bookmarks** - Mark your important files (Ctrl+B)
2. Try **Rename** - Rename a single file safely
3. Use **Create New** - Make a new resource from template
4. Experiment with **Open With** - See different editor options

### Intermediate User?
1. Master **Cut/Paste** - Organize your Override folder
2. Learn **Batch Operations** - Process multiple files at once
3. Try **Pattern Rename** - Bulk rename with wildcards
4. Use **Save All** - Multi-editor workflows

### Advanced User?
1. Create complex workflows using all features together
2. Use **Command Palette** exclusively for speed
3. Build templates with **Create New**
4. Automate organization with **Batch Operations + Patterns**

---

## 📞 Need Help?

### Common Questions:

**Q: Why can't I rename this file?**
A: Only files in Override folder can be renamed. This protects core game files.

**Q: How do I undo a batch operation?**
A: Always use "Extract All" to backup before major changes. There's no undo yet.

**Q: Pattern rename didn't match anything**
A: Check your pattern syntax. `*` = any text, `?` = single character. Preview shows match count.

**Q: Save doesn't work for my editor**
A: Some editors may not support the save method. Check if the editor has its own save button.

**Q: Can I create any resource type?**
A: Yes! 15+ types supported. If you need one not listed, use Generic GFF Editor.

---

## 🎉 Start Using These Features Now!

All features are **production-ready** and **fully integrated**. Just:

1. Open the Holocron Toolset
2. Select an installation
3. Start using any new feature!

**No configuration needed. Everything just works.** ✨

---

**Enjoy your enhanced modding workflow!** 🚀
