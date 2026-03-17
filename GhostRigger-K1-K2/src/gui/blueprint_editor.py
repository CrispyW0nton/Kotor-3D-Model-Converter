"""
GhostRigger — Blueprint Editor Panel (UTC / UTP / UTD)

A Tkinter panel that provides a human-readable GFF field editor for
KotOR creature/placeable/door blueprints.

Blueprint spec from GHOSTWORKS_BLUEPRINT.md Section 5.3.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, Dict, Any

log = logging.getLogger(__name__)

try:
    from ..formats.gff_types import (
        GffFieldType, GffField, GffStruct, GffFile,
        LocString, ResRef, UTC_FIELDS, UTP_FIELDS, UTD_FIELDS, BLUEPRINT_FIELDS,
    )
    from ..formats.gff_reader import read_gff
    from ..formats.gff_writer import write_gff
    _GFF_AVAILABLE = True
except ImportError:
    _GFF_AVAILABLE = False
    log.warning("GFF formats not available — blueprint editor disabled")


# ─── Color palette (matches GhostRigger dark theme) ──────────────────────────
_C = {
    'bg':      '#1e1e1e',
    'bg2':     '#252526',
    'panel':   '#2d2d2d',
    'border':  '#3e3e42',
    'accent':  '#4fc3f7',
    'green':   '#4ec9b0',
    'yellow':  '#dcdcaa',
    'red':     '#f44747',
    'text':    '#d4d4d4',
    'text2':   '#9d9d9d',
    'sel':     '#264f78',
    'gold':    '#dcdcaa',
}

_SCRIPT_SLOTS = [
    "OnSpawn", "OnDeath", "OnDamaged", "OnAttacked", "OnHeartbeat",
    "OnBlocked", "OnConversation", "OnDisturbance", "OnEndConversation",
    "OnUserDefined",
]

_FACTION_NAMES = {
    1: "Friendly", 2: "Hostile", 3: "Neutral", 4: "Predator",
    5: "Prey", 6: "Trap", 7: "Endar Spire", 8: "Rancor",
    9: "Gizka", 10: "Infected", 14: "Rakghoul", 29: "Bounty Hunter",
}

_GENDER_NAMES = {0: "Male", 1: "Female", 2: "Both", 3: "None", 4: "Other"}
_RACE_NAMES   = {0: "Human", 2: "Wookiee", 3: "Rodian", 4: "Twilek",
                 5: "Zabrak", 6: "Unknown", 8: "Ithorian"}
_CLASS_NAMES  = {
    0: "Soldier", 1: "Scout", 2: "Scoundrel", 3: "Jedi Guardian",
    4: "Jedi Consular", 5: "Jedi Sentinel", 8: "Combat Droid",
    9: "Expert Droid", 10: "Minion", 255: "(None)",
}


# ─── Small helper widgets ─────────────────────────────────────────────────────

def _lbl(parent, text: str, width: int = 20, anchor='w', **kw) -> tk.Label:
    return tk.Label(parent, text=text, fg=_C['text2'], bg=_C['bg2'],
                    width=width, anchor=anchor, **kw)


def _entry(parent, var: tk.Variable, width: int = 24) -> tk.Entry:
    e = tk.Entry(parent, textvariable=var, width=width,
                 bg=_C['panel'], fg=_C['text'], insertbackground=_C['text'],
                 relief='flat', highlightthickness=1,
                 highlightbackground=_C['border'], highlightcolor=_C['accent'])
    return e


def _combo(parent, var: tk.Variable, values, width: int = 22) -> ttk.Combobox:
    cb = ttk.Combobox(parent, textvariable=var, values=values,
                      width=width, state='readonly')
    return cb


def _row(parent, label: str, widget: tk.Widget, row: int, label_width: int = 20):
    """Helper: place label + widget in a grid row."""
    _lbl(parent, label, width=label_width).grid(row=row, column=0, sticky='w', padx=(4, 2), pady=1)
    widget.grid(row=row, column=1, sticky='ew', padx=(0, 4), pady=1)


# ─── Blueprint Editor Panel ───────────────────────────────────────────────────

class BlueprintEditorPanel(tk.Frame):
    """
    A scrollable panel for editing KotOR GFF blueprints (UTC / UTP / UTD).

    Features:
    - Human-readable field names (maps GFF labels to plain-English names)
    - Script slot fields with IPC "Open in GhostScripter" buttons
    - Faction / Gender / Race / Class dropdowns
    - Load from bytes / Save to bytes
    - Dirty tracking with visual indicator
    - IPC notification on save (calls GModular port 7003)
    """

    def __init__(self, parent, ipc_client=None, **kw):
        super().__init__(parent, bg=_C['bg2'], **kw)
        self._ipc_client: Optional[Any] = ipc_client
        self._gff:        Optional[GffFile] = None
        self._resref:     str = ""
        self._bp_type:    str = ""   # "UTC", "UTP", "UTD"
        self._dirty:      bool = False
        self._on_save_cb: Optional[Callable] = None
        self._vars:       Dict[str, tk.Variable] = {}
        self._build_ui()

    # ─── Build UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header bar ──────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_C['bg'], height=32)
        hdr.pack(fill='x', side='top')
        hdr.pack_propagate(False)

        self._title_var = tk.StringVar(value="No blueprint loaded")
        tk.Label(hdr, textvariable=self._title_var,
                 fg=_C['accent'], bg=_C['bg'],
                 font=('Segoe UI', 10, 'bold')).pack(side='left', padx=8)

        self._dirty_lbl = tk.Label(hdr, text="", fg=_C['yellow'], bg=_C['bg'],
                                   font=('Segoe UI', 9))
        self._dirty_lbl.pack(side='left', padx=4)

        # Buttons
        btn_frame = tk.Frame(hdr, bg=_C['bg'])
        btn_frame.pack(side='right', padx=4)

        def _btn(text, cmd, color=_C['text']):
            b = tk.Button(btn_frame, text=text, command=cmd,
                          bg=_C['panel'], fg=color, relief='flat',
                          activebackground=_C['sel'], activeforeground=_C['text'],
                          padx=6, pady=2, font=('Segoe UI', 9),
                          cursor='hand2')
            b.pack(side='right', padx=2)
            return b

        _btn("💾 Save",    self._on_save,  _C['green'])
        _btn("📂 Load GFF", self._on_load)
        _btn("🆕 New UTC",  self._on_new_utc)
        _btn("🆕 New UTP",  self._on_new_utp)
        _btn("🆕 New UTD",  self._on_new_utd)

        # ── Scrollable content area ──────────────────────────────────────────
        container = tk.Frame(self, bg=_C['bg2'])
        container.pack(fill='both', expand=True)

        self._canvas = tk.Canvas(container, bg=_C['bg2'], highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient='vertical',
                                 command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self._scroll_frame = tk.Frame(self._canvas, bg=_C['bg2'])
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor='nw')
        self._scroll_frame.bind('<Configure>', self._on_scroll_configure)
        self._canvas.bind('<Configure>', self._on_canvas_configure)
        self._canvas.bind_all('<MouseWheel>', self._on_mousewheel)

        # ── Placeholder ──────────────────────────────────────────────────────
        tk.Label(self._scroll_frame,
                 text="Load a .utc / .utp / .utd file to edit blueprint fields.\n\n"
                      "Or use 🆕 New UTC / UTP / UTD to create a blank blueprint.",
                 fg=_C['text2'], bg=_C['bg2'],
                 justify='center',
                 font=('Segoe UI', 10)).pack(padx=20, pady=40)

    # ─── Scroll helpers ───────────────────────────────────────────────────────

    def _on_scroll_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _on_canvas_configure(self, event=None):
        self._canvas.itemconfig(self._canvas_window,
                                width=self._canvas.winfo_width())

    def _on_mousewheel(self, event):
        if self._canvas.winfo_exists():
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    # ─── Load / New / Save ───────────────────────────────────────────────────

    def load_bytes(self, data: bytes, resref: str = "", bp_type: str = ""):
        """Load GFF data from bytes and populate the editor."""
        if not _GFF_AVAILABLE:
            messagebox.showerror("GFF Error", "GFF format library not available.")
            return
        try:
            gff = read_gff(data)
            self._gff = gff
            self._resref = resref
            # Auto-detect type from GFF header
            if not bp_type:
                ft = gff.file_type.strip().upper()
                if ft in ('UTC', 'UTP', 'UTD'):
                    bp_type = ft
                else:
                    bp_type = "UTC"  # fallback
            self._bp_type = bp_type
            self._dirty = False
            self._rebuild_fields()
            log.info(f"Blueprint loaded: {resref!r} ({bp_type})")
        except Exception as e:
            log.error(f"Failed to load GFF: {e}")
            messagebox.showerror("GFF Load Error", str(e))

    def load_file(self, path: str):
        """Load a GFF file from disk."""
        try:
            with open(path, 'rb') as f:
                data = f.read()
            ext = os.path.splitext(path)[1].upper().lstrip('.')
            resref = os.path.splitext(os.path.basename(path))[0].lower()
            self.load_bytes(data, resref=resref, bp_type=ext)
        except Exception as e:
            log.error(f"Error loading file {path}: {e}")

    def new_blueprint(self, bp_type: str):
        """Create a new blank blueprint of the given type."""
        if not _GFF_AVAILABLE:
            return
        gff = GffFile(file_type=f"{bp_type} ", file_version="V3.2")
        field_defs = BLUEPRINT_FIELDS.get(bp_type, {})
        for label, (human_name, ftype, default) in field_defs.items():
            if default is None:
                default = LocString()
            gff.set(label, ftype, default)
        self._gff = gff
        self._resref = f"new_{bp_type.lower()}"
        self._bp_type = bp_type
        self._dirty = True
        self._rebuild_fields()
        log.info(f"New {bp_type} blueprint created")

    def get_bytes(self) -> Optional[bytes]:
        """Serialize the current blueprint to bytes."""
        if not _GFF_AVAILABLE or self._gff is None:
            return None
        self._flush_vars_to_gff()
        return write_gff(self._gff)

    def set_on_save_callback(self, cb: Callable):
        self._on_save_cb = cb

    # ─── Build field widgets ─────────────────────────────────────────────────

    def _rebuild_fields(self):
        """Clear and rebuild the scrollable field editor."""
        # Destroy old content
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()
        self._vars.clear()

        if self._gff is None:
            return

        bp_type = self._bp_type
        field_defs = BLUEPRINT_FIELDS.get(bp_type, {})
        title = f"📋 {bp_type} Blueprint — {self._resref}"
        self._title_var.set(title)

        f = self._scroll_frame
        row = 0

        # ── Section: Identity ────────────────────────────────────────────────
        row = self._section(f, "Identity", row)
        for label in ("Tag", "TemplateResRef", "FirstName", "LocalizedName"):
            if label in field_defs and (label in self._gff.root.fields or True):
                row = self._add_field_row(f, label, field_defs[label], row)

        # ── Section: Stats (UTC only) ────────────────────────────────────────
        if bp_type == "UTC":
            row = self._section(f, "Class & Level", row)
            for label in ("Appearance_Type", "Gender", "Race", "Class1", "Level",
                          "Class2", "Level2"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

            row = self._section(f, "Attributes", row)
            for label in ("Str", "Dex", "Con", "Int", "Wis", "Cha"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

            row = self._section(f, "Hit Points & Saves", row)
            for label in ("MaxHitPoints", "CurrentHitPoints", "MaxFP", "CurrentFP",
                          "fortbonus", "refbonus", "willbonus"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

            row = self._section(f, "Skills", row)
            for label in ("ComputerUsed", "Demolitions", "Stealth", "Awareness",
                          "Persuade", "Repair", "SecuritySkill", "TreatInjury"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

        # ── Section: Placeable stats (UTP) ───────────────────────────────────
        if bp_type == "UTP":
            row = self._section(f, "Appearance & Stats", row)
            for label in ("Appearance", "MaxHP", "CurrentHP", "Static",
                          "Useable", "HasInventory"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

        # ── Section: Door stats (UTD) ─────────────────────────────────────────
        if bp_type == "UTD":
            row = self._section(f, "Door Properties", row)
            for label in ("GenericType", "LinkedTo", "LinkedToFlags",
                          "MaxHP", "CurrentHP", "Static",
                          "Locked", "LockDC", "KeyRequired", "KeyName"):
                if label in field_defs:
                    row = self._add_field_row(f, label, field_defs[label], row)

        # ── Section: Faction ─────────────────────────────────────────────────
        row = self._section(f, "Faction & Behavior", row)
        for label in ("FactionID", "Faction", "Conversation", "SoundSetFile",
                      "BodyBag", "IsPC", "WillNotRender", "NoPermDeath",
                      "Disarmable", "Plot", "Min1HP"):
            if label in field_defs:
                row = self._add_field_row(f, label, field_defs[label], row)

        # ── Section: Script Slots ────────────────────────────────────────────
        row = self._section(f, "Script Slots", row)
        script_labels = [l for l in field_defs if field_defs[l][1] == GffFieldType.RESREF
                         and l.startswith('On')]
        for label in script_labels:
            row = self._add_script_row(f, label, field_defs[label], row)

        # Update dirty indicator
        self._set_dirty(self._dirty)
        self._on_scroll_configure()

    def _section(self, parent, title: str, row: int) -> int:
        """Add a section header separator."""
        frm = tk.Frame(parent, bg=_C['border'], height=1)
        frm.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0), padx=2)
        row += 1
        tk.Label(parent, text=title, fg=_C['accent'], bg=_C['bg2'],
                 font=('Segoe UI', 9, 'bold')).grid(
            row=row, column=0, columnspan=2, sticky='w', padx=6, pady=(2, 4))
        return row + 1

    def _add_field_row(self, parent, label: str, field_def: tuple, row: int) -> int:
        """Add a single field row (label + widget)."""
        human_name, ftype, default = field_def

        # Get current value from GFF or default
        if self._gff and label in self._gff.root.fields:
            cur_val = self._gff.root.fields[label].value
        else:
            cur_val = default

        # Create variable and widget
        if ftype == GffFieldType.CEXOLOCSTRING:
            var = tk.StringVar(value=cur_val.english if isinstance(cur_val, LocString) else str(cur_val or ""))
            widget = _entry(parent, var)
        elif ftype == GffFieldType.RESREF:
            val_str = str(cur_val) if cur_val is not None else str(default or "")
            var = tk.StringVar(value=val_str)
            widget = _entry(parent, var)
        elif label == "FactionID" or label == "Faction":
            names = list(_FACTION_NAMES.values())
            cur_id = int(cur_val or 1)
            cur_name = _FACTION_NAMES.get(cur_id, str(cur_id))
            var = tk.StringVar(value=cur_name)
            widget = _combo(parent, var, names)
        elif label == "Gender":
            names = list(_GENDER_NAMES.values())
            cur_name = _GENDER_NAMES.get(int(cur_val or 0), "Male")
            var = tk.StringVar(value=cur_name)
            widget = _combo(parent, var, names)
        elif label == "Race":
            names = list(_RACE_NAMES.values())
            cur_name = _RACE_NAMES.get(int(cur_val or 6), "Unknown")
            var = tk.StringVar(value=cur_name)
            widget = _combo(parent, var, names)
        elif label in ("Class1", "Class2", "Class3"):
            names = list(_CLASS_NAMES.values())
            cur_name = _CLASS_NAMES.get(int(cur_val or 0), "Soldier")
            var = tk.StringVar(value=cur_name)
            widget = _combo(parent, var, names)
        elif ftype in (GffFieldType.BYTE, GffFieldType.CHAR,
                       GffFieldType.UINT16, GffFieldType.INT16,
                       GffFieldType.UINT32, GffFieldType.INT32):
            var = tk.IntVar(value=int(cur_val or 0))
            widget = tk.Spinbox(parent, textvariable=var, from_=-32768, to=65535,
                                width=10, bg=_C['panel'], fg=_C['text'],
                                relief='flat', insertbackground=_C['text'],
                                buttonbackground=_C['panel'])
        elif ftype == GffFieldType.FLOAT:
            var = tk.DoubleVar(value=float(cur_val or 0.0))
            widget = _entry(parent, var, width=12)
        else:
            var = tk.StringVar(value=str(cur_val or ""))
            widget = _entry(parent, var)

        var.trace_add('write', lambda *_: self._set_dirty(True))
        self._vars[label] = var
        _row(parent, human_name, widget, row)
        parent.columnconfigure(1, weight=1)
        return row + 1

    def _add_script_row(self, parent, label: str, field_def: tuple, row: int) -> int:
        """Add a script slot row with 'Open in GhostScripter' IPC button."""
        human_name, ftype, default = field_def

        if self._gff and label in self._gff.root.fields:
            cur_val = self._gff.root.fields[label].value
        else:
            cur_val = default
        val_str = str(cur_val) if cur_val is not None else ""

        var = tk.StringVar(value=val_str)
        var.trace_add('write', lambda *_: self._set_dirty(True))
        self._vars[label] = var

        _lbl(parent, human_name, width=20).grid(
            row=row, column=0, sticky='w', padx=(4, 2), pady=1)

        # Container for entry + IPC button
        frm = tk.Frame(parent, bg=_C['bg2'])
        frm.grid(row=row, column=1, sticky='ew', padx=(0, 4), pady=1)
        frm.columnconfigure(0, weight=1)

        ent = _entry(frm, var, width=18)
        ent.grid(row=0, column=0, sticky='ew')

        def _open_scripter(l=label, v=var):
            self._ipc_open_script(l, v.get())

        edit_btn = tk.Button(frm, text="✏", command=_open_scripter,
                             bg=_C['panel'], fg=_C['accent'], relief='flat',
                             width=2, font=('Segoe UI', 9), cursor='hand2',
                             activebackground=_C['sel'])
        edit_btn.grid(row=0, column=1, padx=(2, 0))

        return row + 1

    # ─── IPC helpers ─────────────────────────────────────────────────────────

    def _ipc_open_script(self, slot: str, resref: str):
        """Tell GhostScripter to open a script for the given slot."""
        if self._ipc_client is None:
            log.info(f"IPC not available — would open script {resref!r} for slot {slot}")
            return
        try:
            from ..ipc.client import open_script_in_scripter
            open_script_in_scripter(
                resref=resref or self._resref + "_" + slot.lower(),
                slot=slot,
                object_tag=self._resref,
            )
        except Exception as e:
            log.warning(f"IPC open_script failed: {e}")

    # ─── Dirty tracking ───────────────────────────────────────────────────────

    def _set_dirty(self, dirty: bool):
        self._dirty = dirty
        self._dirty_lbl.config(text="● Unsaved changes" if dirty else "")

    # ─── Flush vars → GFF ────────────────────────────────────────────────────

    def _flush_vars_to_gff(self):
        """Write all widget variable values back into the GffFile."""
        if self._gff is None:
            return
        field_defs = BLUEPRINT_FIELDS.get(self._bp_type, {})
        for label, var in self._vars.items():
            if label not in field_defs:
                continue
            human_name, ftype, default = field_defs[label]
            try:
                raw = var.get()
            except Exception:
                continue

            if ftype == GffFieldType.CEXOLOCSTRING:
                loc = LocString()
                loc.english = str(raw)
                self._gff.set(label, ftype, loc)
            elif ftype == GffFieldType.RESREF:
                self._gff.set(label, ftype, ResRef(str(raw)))
            elif label == "FactionID" or label == "Faction":
                rev = {v: k for k, v in _FACTION_NAMES.items()}
                self._gff.set(label, GffFieldType.UINT32, rev.get(str(raw), 1))
            elif label == "Gender":
                rev = {v: k for k, v in _GENDER_NAMES.items()}
                self._gff.set(label, ftype, rev.get(str(raw), 0))
            elif label == "Race":
                rev = {v: k for k, v in _RACE_NAMES.items()}
                self._gff.set(label, ftype, rev.get(str(raw), 6))
            elif label in ("Class1", "Class2", "Class3"):
                rev = {v: k for k, v in _CLASS_NAMES.items()}
                self._gff.set(label, ftype, rev.get(str(raw), 0))
            elif ftype in (GffFieldType.BYTE, GffFieldType.CHAR,
                           GffFieldType.UINT16, GffFieldType.INT16,
                           GffFieldType.UINT32, GffFieldType.INT32):
                self._gff.set(label, ftype, int(raw))
            elif ftype == GffFieldType.FLOAT:
                self._gff.set(label, ftype, float(raw))
            else:
                self._gff.set(label, ftype, str(raw))

    # ─── Button callbacks ─────────────────────────────────────────────────────

    def _on_save(self):
        if self._gff is None:
            messagebox.showinfo("Save", "No blueprint loaded.")
            return
        self._flush_vars_to_gff()
        data = write_gff(self._gff)

        path = filedialog.asksaveasfilename(
            title="Save Blueprint",
            defaultextension=f".{self._bp_type.lower()}",
            filetypes=[(f"{self._bp_type} Blueprint", f"*.{self._bp_type.lower()}"),
                       ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, 'wb') as fh:
                    fh.write(data)
                self._set_dirty(False)
                log.info(f"Saved blueprint to {path}")
                # IPC: notify GModular
                try:
                    from ..ipc.client import notify_blueprint_saved
                    notify_blueprint_saved(self._resref, self._bp_type.lower())
                except Exception as e:
                    log.debug(f"IPC notify failed (ok if GModular not running): {e}")
                if self._on_save_cb:
                    self._on_save_cb(self._resref, self._bp_type.lower(), path)
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    def _on_load(self):
        path = filedialog.askopenfilename(
            title="Open Blueprint",
            filetypes=[
                ("KotOR Blueprints", "*.utc *.utp *.utd"),
                ("Creature Blueprint", "*.utc"),
                ("Placeable Blueprint", "*.utp"),
                ("Door Blueprint", "*.utd"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.load_file(path)

    def _on_new_utc(self):
        self.new_blueprint("UTC")

    def _on_new_utp(self):
        self.new_blueprint("UTP")

    def _on_new_utd(self):
        self.new_blueprint("UTD")

    # ─── Public helpers ───────────────────────────────────────────────────────

    def refresh(self, model=None):
        """Called by main window on model load (unused, kept for compatibility)."""
        pass
