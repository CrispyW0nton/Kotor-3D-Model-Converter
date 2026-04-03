"""Twine 2 HTML to DLG conversion: read Twine story format and write as KotOR dialog GFF."""

from __future__ import annotations

import uuid

from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from pykotor.common.language import Gender, Language
from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, DLGReply
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class GFFTwineReader(ResourceReader):
    """Reads Twine 2 HTML format and converts to DLG.

    Twine is an interactive fiction authoring tool. This reader converts Twine story
    format (HTML) to KotOR dialog (DLG) format for use in modding.

    References:
    ----------
        Based on swkotor.exe dialog structure:
        - CSWSDialog::LoadDialog @ 0x005a2ae0 - Loads dialog from GFF structure
        - CSWSDialog::LoadDialogBase @ 0x0059f5f0 - Loads dialog base properties
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        - Twine 2 format specification (twinejs.com)

        Note: Twine conversion is PyKotor-specific functionality, not a standard game format.
        The engine uses binary DLG (GFF) format exclusively. Twine conversion allows
        easier dialog authoring for modders using interactive fiction tools.
    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._dlg: DLG | None = None
        self._passage_map: dict[str, DLGEntry | DLGReply] = {}

    @autoclose
    def load(self, *, auto_close: bool = True) -> DLG:  # noqa: FBT001, FBT002, ARG002
        """Load Twine story data into DLG format.

        Returns:
            DLG: The constructed dialog object
        """
        self._dlg = DLG()

        data: str = self._reader.read_bytes(self._reader.size()).decode()
        root: ET.Element = ET.fromstring(data)  # noqa: S314

        # Parse story metadata
        self._dlg.word_count = 0  # Not used in Twine
        self._dlg.skippable = True  # Twine stories are always skippable

        # Parse passages
        for passage in root.findall(".//tw-passagedata"):
            pid: str = passage.get("pid", "")
            name: str = passage.get("name", "")
            tags: list[str] = passage.get("tags", "").split()
            text: str = passage.text or ""

            # Create entry or reply based on tags
            if "reply" in tags:
                node = DLGReply()
            else:
                node = DLGEntry()
                node.speaker = name

            node.text.set_data(Language.ENGLISH, Gender.MALE, text)
            self._passage_map[pid] = node

            # Handle links
            for link in passage.findall(".//link"):
                target_pid: str = link.get("pid", "")
                if target_pid in self._passage_map:
                    target: DLGEntry | DLGReply = self._passage_map[target_pid]
                    target_link = DLGLink(target)
                    node.links.append(target_link)  # pyright: ignore[reportArgumentType]

        # Set starting node
        start_pid: str | None = root.get("startnode")
        if start_pid and start_pid in self._passage_map:
            self._dlg.starters.append(DLGLink(self._passage_map[start_pid]))  # pyright: ignore[reportArgumentType]

        return self._dlg


class GFFTwineWriter(ResourceWriter):
    """Writes DLG data in Twine 2 HTML format."""

    def __init__(
        self,
        dlg: DLG,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self.dlg: DLG = dlg
        self.xml_root: ET.Element = ET.Element("tw-storydata")

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        """Write the DLG data as a Twine story."""
        # Set story metadata
        self.xml_root.set("name", "Converted Dialog")
        self.xml_root.set("ifid", str(uuid.uuid4()))
        self.xml_root.set("format", "Harlowe")
        self.xml_root.set("format-version", "3.3.7")

        # Add style/script elements
        style: ET.Element = ET.SubElement(self.xml_root, "style")
        style.set("role", "stylesheet")
        style.set("id", "twine-user-stylesheet")
        style.set("type", "text/twine-css")

        script: ET.Element = ET.SubElement(self.xml_root, "script")
        script.set("role", "script")
        script.set("id", "twine-user-script")
        script.set("type", "text/twine-javascript")

        # Convert entries and replies to passages
        entries: list[DLGEntry] = self.dlg.all_entries()
        replies: list[DLGReply] = self.dlg.all_replies()
        reply_to_index: dict[int, int] = {id(r): i for i, r in enumerate(replies)}
        entry_to_index: dict[int, int] = {id(e): i for i, e in enumerate(entries)}

        # Start with entries
        for i, entry in enumerate(entries):
            passage: ET.Element = ET.SubElement(self.xml_root, "tw-passagedata")
            passage.set("pid", str(i))
            passage.set("name", entry.speaker or f"Entry {i}")
            passage.set("tags", "entry")
            passage.set("position", f"{i * 100},{i * 100}")
            passage.text = entry.text.get(Language.ENGLISH, Gender.MALE)

            # Add links to replies
            link_to_reply: DLGLink[DLGReply]
            for link_to_reply in entry.links:
                reply_index = reply_to_index.get(id(link_to_reply.node))
                if reply_index is None:
                    continue
                link_elem: ET.Element = ET.SubElement(passage, "link")
                link_elem.set("pid", str(reply_index))

        # Then replies
        for i, reply in enumerate(replies):
            passage = ET.SubElement(self.xml_root, "tw-passagedata")
            passage.set("pid", str(len(entries) + i))
            passage.set("name", f"Reply {i}")
            passage.set("tags", "reply")
            passage.set("position", f"{i * 100},{(i + len(entries)) * 100}")
            passage.text = reply.text.get(Language.ENGLISH, Gender.MALE)

            # Add links to entries
            link_to_entry: DLGLink[DLGEntry]
            for link_to_entry in reply.links:
                entry_index = entry_to_index.get(id(link_to_entry.node))
                if entry_index is None:
                    continue
                link_elem = ET.SubElement(passage, "link")
                link_elem.set("pid", str(entry_index))

        # Set starting node if exists
        if self.dlg.starters:
            start_idx = entry_to_index.get(id(self.dlg.starters[0].node))
            if start_idx is not None:
                self.xml_root.set("startnode", str(start_idx))

        # Write the XML
        self._writer.write_bytes(ET.tostring(self.xml_root, encoding="utf-8"))
