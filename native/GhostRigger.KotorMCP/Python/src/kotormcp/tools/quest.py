"""
get_quest — composite KotOR quest inspector.

Constantine/Khononov design notes
──────────────────────────────────
• Communicational cohesion: every element in this module operates on the same
  logical entity — a KotOR quest.  All output is derived from that single
  input context (the quest tag).
• Transform analysis (Constantine Ch.9): this tool is a single transform module.
  Input: quest tag string.  Output: composite Markdown document.
  It delegates to subordinate "afferent" readers (JRL, DLG, NCS) rather than
  performing I/O and logic in the same function.
• Context-free naming: "get_quest" — not "discord_quest_lookup" or
  "vscode_quest_details".  The same information is equally useful in a Discord
  bot, a VS Code extension, a CI/CD pipeline or an interactive AI session.
• Decision hiding: callers do not know whether scripts are decompiled via
  AgentDecompile, NCSDecomp, or returned as stubs.  The handler selects the
  best available strategy at runtime.
• Scope of effect ⊆ scope of control: the decision about which quest entries
  match a tag lives inside this module, not in callers.
"""

from __future__ import annotations

import textwrap
from io import BytesIO
from typing import Any, Dict, List, Optional

from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


# ── Tool definition ───────────────────────────────────────────────────────────

def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "get_quest",
            "description": (
                "Return a composite Markdown document describing a KotOR quest. "
                "Output includes: the JRL resource reference, quest plot number, "
                "all journal entry states (with strref-resolved text), the list of "
                "scripts referenced in each state (OnAccepted, OnFailed, etc.), "
                "decompiled script source where available, and DLG node excerpts "
                "that reference this quest tag. "
                "Pass just the quest tag (e.g. 'man26_genohar') — all other "
                "associations are resolved automatically. "
                "Read-only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {
                        "type": "string",
                        "description": "Game alias: k1 or k2",
                    },
                    "tag": {
                        "type": "string",
                        "description": (
                            "Quest tag as it appears in global.jrl "
                            "(e.g. 'man26_genohar', 'tat17_sandral'). "
                            "Case-insensitive. Partial prefix matches are supported."
                        ),
                    },
                    "include_dlg": {
                        "type": "boolean",
                        "description": (
                            "Whether to search module DLG files for nodes referencing "
                            "this quest tag.  Default true.  Set false to skip DLG scan "
                            "on large installs."
                        ),
                        "default": True,
                    },
                    "include_scripts": {
                        "type": "boolean",
                        "description": (
                            "Whether to attempt script decompilation for scripts "
                            "referenced by quest states.  Default true."
                        ),
                        "default": True,
                    },
                },
                "required": ["game", "tag"],
            },
        }
    ]


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle_get_quest(arguments: Dict[str, Any]) -> Dict[str, Any]:
    game_alias: str = arguments.get("game", "")
    tag: str = arguments.get("tag", "").strip()
    include_dlg: bool = arguments.get("include_dlg", True)
    include_scripts: bool = arguments.get("include_scripts", True)

    game = resolve_game(game_alias)
    if game is None:
        return json_content({"error": "game must be 'k1' or 'k2'."})
    if not tag:
        return json_content({"error": "tag is required."})

    try:
        installation = load_installation(game)
    except Exception as exc:
        return json_content({"error": f"Could not load installation: {exc}"})

    # ── 1. Load global.jrl ───────────────────────────────────────────────────
    jrl_entry = installation.get_resource("global", "jrl")
    if jrl_entry is None:
        return json_content({"error": "global.jrl not found in installation."})

    quest_categories = _parse_jrl(jrl_entry.data)

    # ── 2. Find matching quest category ──────────────────────────────────────
    matched = _find_quest(quest_categories, tag)
    if not matched:
        # Return all available tags so the caller can retry
        all_tags = sorted({c.get("tag", "") for c in quest_categories if c.get("tag")})
        return json_content({
            "error": f"Quest tag '{tag}' not found in global.jrl.",
            "available_tags_sample": all_tags[:60],
        })

    # ── 3. Resolve TLK strings ───────────────────────────────────────────────
    for cat in matched:
        _resolve_tlk_strings(cat, installation)

    # ── 4. Collect script references from quest entries ───────────────────────
    script_refs: List[str] = []
    for cat in matched:
        for entry in cat.get("entries", []):
            for field in ("Script", "OnAccept", "OnFail", "OnEnd", "OnAssign"):
                val = entry.get(field, "")
                if val and val != "****":
                    script_refs.append(val)
    script_refs = sorted(set(script_refs))

    # ── 5. Decompile scripts (optional) ──────────────────────────────────────
    script_sources: Dict[str, str] = {}
    if include_scripts and script_refs:
        script_sources = _fetch_script_sources(script_refs, installation)

    # ── 6. DLG scan (optional) ────────────────────────────────────────────────
    dlg_refs: List[Dict[str, Any]] = []
    if include_dlg:
        dlg_refs = _scan_dlg_for_quest(tag, installation)

    # ── 7. Render Markdown output ─────────────────────────────────────────────
    md = _render_markdown(matched, script_refs, script_sources, dlg_refs, tag, game_alias)

    return json_content({
        "tag": tag,
        "game": game_alias,
        "quest_count": len(matched),
        "script_refs": script_refs,
        "dlg_refs_count": len(dlg_refs),
        "markdown": md,
    })


# ── JRL parser ────────────────────────────────────────────────────────────────

def _parse_jrl(data: bytes) -> List[Dict[str, Any]]:
    """
    Parse global.jrl GFF and return a flat list of quest category dicts.

    Each dict has keys: tag, name_strref, priority, entries (list of dicts).
    Entry dicts have: id, text_strref, completes_plot, and optional script fields.
    """
    try:
        from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415
    except ImportError:
        return []

    categories = []
    try:
        gff = read_gff(BytesIO(data))
        for entry in gff.root.get_list("Categories", default=[]):
            cat: Dict[str, Any] = {
                "tag": entry.get_string("Tag", ""),
                "name_strref": _safe_get_int(entry, "Name"),
                "priority": _safe_get_int(entry, "Priority"),
                "entries": [],
            }
            for quest in entry.get_list("EntryList", default=[]):
                q: Dict[str, Any] = {
                    "id": _safe_get_int(quest, "ID"),
                    "text_strref": _safe_get_int(quest, "Text"),
                    "completes_plot": bool(_safe_get_int(quest, "End")),
                }
                # Script fields (KotOR1 and KotOR2 variants)
                for field in ("Script", "OnAccept", "OnFail", "OnEnd", "OnAssign", "SetFlag"):
                    val = quest.get_string(field, "")
                    if val and val != "****":
                        q[field] = val
                cat["entries"].append(q)
            categories.append(cat)
    except Exception:
        pass
    return categories


def _safe_get_int(struct: Any, key: str, default: int = 0) -> int:
    try:
        return struct.get_uint(key, default)
    except Exception:
        try:
            return struct.get_int(key, default)
        except Exception:
            return default


# ── Quest search ──────────────────────────────────────────────────────────────

def _find_quest(categories: List[Dict], tag: str) -> List[Dict]:
    """Return all categories whose tag starts with the given tag (case-insensitive)."""
    tag_lower = tag.lower()
    return [c for c in categories if c.get("tag", "").lower().startswith(tag_lower)]


# ── TLK resolution ────────────────────────────────────────────────────────────

def _resolve_tlk_strings(cat: Dict[str, Any], installation: Any) -> None:
    """Replace strref ints with resolved text strings in-place."""
    strref = cat.get("name_strref", 0)
    if strref:
        try:
            cat["name_text"] = installation.talktable_string(strref)
        except Exception:
            cat["name_text"] = f"<strref:{strref}>"
    for entry in cat.get("entries", []):
        strref = entry.get("text_strref", 0)
        if strref:
            try:
                entry["text"] = installation.talktable_string(strref)
            except Exception:
                entry["text"] = f"<strref:{strref}>"


# ── Script fetching ───────────────────────────────────────────────────────────

def _fetch_script_sources(script_refs: List[str], installation: Any) -> Dict[str, str]:
    """
    For each script resref, attempt to return source (NSS > NCS hex stub).

    Strategy (selected at runtime without changing the caller):
    1. If .nss source is in the installation, return it.
    2. If .ncs binary is present, return a hex stub with a decompile hint.
    3. Otherwise return a "not found" stub.

    This is Constantine's "decision hiding" applied to tool strategy selection.
    """
    results: Dict[str, str] = {}
    for ref in script_refs:
        # Try NSS source first
        nss_entry = installation.get_resource(ref, "nss")
        if nss_entry and nss_entry.data:
            try:
                results[ref] = nss_entry.data.decode("utf-8", errors="replace")
                continue
            except Exception:
                pass

        # Try NCS binary
        ncs_entry = installation.get_resource(ref, "ncs")
        if ncs_entry and ncs_entry.data:
            header = ncs_entry.data[:16].hex()
            results[ref] = (
                f"[NCS binary — {len(ncs_entry.data)} bytes]\n"
                f"Header: {header}\n"
                f"Hint: use kotor_decompile_function to decompile this script."
            )
            continue

        results[ref] = "[Script not found in installation]"
    return results


# ── DLG scanner ───────────────────────────────────────────────────────────────

def _scan_dlg_for_quest(tag: str, installation: Any) -> List[Dict[str, Any]]:
    """
    Scan module DLG resources for nodes that set or check this quest tag.

    Returns a list of {dlg_resref, node_type, node_index, text_excerpt, script} dicts.
    Limited to first 20 matches to keep response size bounded.
    """
    tag_lower = tag.lower()
    matches: List[Dict[str, Any]] = []

    try:
        from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415

        # Iterate over all DLG resources visible to the installation
        for entry in installation.iter_resources(location="all"):
            if entry.restype.lower() != "dlg":
                continue
            if not entry.data:
                continue
            try:
                gff = read_gff(BytesIO(entry.data))
                # Check EntryList and ReplyList node scripts and quest fields
                for list_name in ("EntryList", "ReplyList"):
                    nodes = gff.root.get_list(list_name, default=[])
                    for idx, node in enumerate(nodes):
                        # Check Quest field directly on node
                        quest_field = node.get_string("Quest", "")
                        if quest_field and tag_lower in quest_field.lower():
                            text_strref = _safe_get_int(node, "Text")
                            matches.append({
                                "dlg_resref": entry.resref,
                                "node_type": list_name.replace("List", "").lower(),
                                "node_index": idx,
                                "quest_field": quest_field,
                                "text_strref": text_strref,
                            })
                        # Check Script fields for tag hints
                        for sf in ("Script", "Script1", "Script2"):
                            sv = node.get_string(sf, "")
                            if sv and tag_lower in sv.lower():
                                matches.append({
                                    "dlg_resref": entry.resref,
                                    "node_type": list_name.replace("List", "").lower(),
                                    "node_index": idx,
                                    "script_field": sf,
                                    "script_value": sv,
                                })
                    if len(matches) >= 20:
                        break
            except Exception:
                continue
            if len(matches) >= 20:
                break
    except Exception:
        pass

    return matches[:20]


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _render_markdown(
    matched: List[Dict],
    script_refs: List[str],
    script_sources: Dict[str, str],
    dlg_refs: List[Dict],
    tag: str,
    game: str,
) -> str:
    """
    Render all quest data as a single Markdown document.

    This is a pure transform (data → text) with no side-effects.
    Constantine: all decisions about presentation live in the renderer,
    not scattered across callers.
    """
    lines: List[str] = []

    lines.append(f"# Quest: `{tag}` ({game.upper()})")
    lines.append("")
    lines.append(f"**JRL Resource**: `global.jrl`  ")
    lines.append(f"**Matched categories**: {len(matched)}")
    lines.append("")

    for cat in matched:
        lines.append(f"## Category: `{cat.get('tag', '?')}`")
        lines.append("")
        name_text = cat.get("name_text", "")
        if name_text:
            lines.append(f"**Name**: {name_text}  ")
        lines.append(f"**Priority**: {cat.get('priority', 0)}  ")
        lines.append(f"**Name StrRef**: {cat.get('name_strref', 0)}")
        lines.append("")

        entries = cat.get("entries", [])
        if entries:
            lines.append("### Journal States")
            lines.append("")
            lines.append("| ID | Text | Completes Plot | Scripts |")
            lines.append("|-----|------|---------------|---------|")
            for e in entries:
                text = e.get("text", e.get("text_strref", ""))
                if isinstance(text, int):
                    text = f"<strref:{text}>"
                text = str(text)[:120].replace("|", "\\|").replace("\n", " ")
                scripts = ", ".join(
                    f"`{e[f]}`" for f in ("Script", "OnAccept", "OnFail", "OnEnd", "OnAssign")
                    if e.get(f)
                )
                lines.append(f"| {e.get('id', '?')} | {text} | {'✓' if e.get('completes_plot') else ''} | {scripts} |")
            lines.append("")

    # ── Scripts section ──────────────────────────────────────────────────────
    if script_refs:
        lines.append("## Scripts Referenced by Quest States")
        lines.append("")
        for ref in script_refs:
            lines.append(f"### `{ref}.nss`")
            lines.append("")
            src = script_sources.get(ref, "[source not available]")
            lines.append("```nwscript")
            lines.append(textwrap.indent(src[:2000], ""))
            if len(src) > 2000:
                lines.append(f"... [{len(src) - 2000} more characters truncated]")
            lines.append("```")
            lines.append("")

    # ── DLG section ───────────────────────────────────────────────────────────
    if dlg_refs:
        lines.append("## DLG Nodes Referencing This Quest")
        lines.append("")
        lines.append("| DLG File | Node Type | Index | Quest/Script Field | Value |")
        lines.append("|----------|-----------|-------|-------------------|-------|")
        for ref in dlg_refs:
            dlg = ref.get("dlg_resref", "?")
            ntype = ref.get("node_type", "?")
            idx = ref.get("node_index", "?")
            if "quest_field" in ref:
                field = "Quest"
                val = ref.get("quest_field", "")
            else:
                field = ref.get("script_field", "Script")
                val = ref.get("script_value", "")
            lines.append(f"| `{dlg}` | {ntype} | {idx} | {field} | `{val}` |")
        lines.append("")
    elif script_refs:
        lines.append("> *DLG scan skipped or no DLG nodes found referencing this quest tag.*")
        lines.append("")

    return "\n".join(lines)
