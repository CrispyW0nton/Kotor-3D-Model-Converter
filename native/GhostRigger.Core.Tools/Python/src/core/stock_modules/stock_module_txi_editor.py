"""Non-destructive TXI sidecar text edit drafts for stock Module Editor textures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleTxiEditDraft:
    source_label: str
    output_resref: str
    txi_text: str
    output_payload: bytes = b""
    validation_status: str = "not_validated"
    issues: tuple[str, ...] = ()
    status: str = "preview_only"

    @property
    def ready(self) -> bool:
        return bool(self.output_payload) and self.validation_status == "valid"

    @property
    def label(self) -> str:
        return f"{self.output_resref}.txi"

    @property
    def summary(self) -> str:
        line_count = len([line for line in self.txi_text.splitlines() if line.strip()])
        return f"{self.source_label} -> {self.label} ({line_count} TXI line(s))"


def create_txi_text_edit_draft(
    *,
    source_label: str,
    output_resref: str,
    txi_text: str,
) -> ModuleTxiEditDraft:
    """Create a validated TXI text payload without writing files or touching source data."""

    output_resref = _clean_resref(output_resref)
    text = _clean_txi_text(txi_text)
    issue = _resref_issue(output_resref) or _txi_text_issue(text)
    if issue:
        return ModuleTxiEditDraft(
            source_label=source_label,
            output_resref=output_resref,
            txi_text=text,
            validation_status="invalid",
            issues=(issue,),
        )
    payload = (text.rstrip() + "\n").encode("ascii")
    return ModuleTxiEditDraft(
        source_label=source_label,
        output_resref=output_resref,
        txi_text=payload.decode("ascii"),
        output_payload=payload,
        validation_status="valid",
    )


def _clean_resref(value: object) -> str:
    return str(value or "").strip().strip("\x00").lower()


def _clean_txi_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip("\x00")


def _resref_issue(value: str) -> str:
    if not value:
        return "TXI sidecar ResRef cannot be empty."
    if len(value) > 16:
        return "TXI sidecar ResRef exceeds the 16-character KotOR limit."
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return "TXI sidecar ResRef must be ASCII."
    if not all(character.isalnum() or character == "_" for character in value):
        return "TXI sidecar ResRef may only contain letters, numbers, and underscores."
    return ""


def _txi_text_issue(text: str) -> str:
    if not text.strip():
        return "TXI text cannot be empty."
    if "\x00" in text:
        return "TXI text cannot contain null bytes."
    if len(text.encode("utf-8")) > 32768:
        return "TXI text exceeds the 32 KB editor limit."
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return "TXI text must be ASCII for this first safe sidecar editor."
    return ""


__all__ = [
    "ModuleTxiEditDraft",
    "create_txi_text_edit_draft",
]
