"""Read-only KOTOR installation verification for Head Builder.

Core Resources owns installation discovery and byte provenance.  Verification
fingerprints the executable and KEY index, then proves that a stock MDL/MDX
head pair can be read through the same catalog used for donor selection.
Nothing is written to the game directory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from src.core.characters.head_builder_project import ResourceView
from src.core.resources.head_donor_catalog import (
    HeadDonorCatalog,
    HeadDonorCatalogError,
)


@dataclass(frozen=True, slots=True)
class HeadGameInstallIssue:
    check_id: str
    severity: str
    message: str
    facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HeadGameInstallVerification:
    game: str
    install_dir: str
    executable_path: str
    executable_size: int
    executable_sha256: str
    chitin_key_path: str
    chitin_key_size: int
    chitin_key_sha256: str
    chitin_signature: str
    resource_probe_resref: str
    resource_probe_mdl_sha256: str
    resource_probe_mdx_sha256: str
    resource_probe_source: str
    resource_probe_readable: bool
    issues: tuple[HeadGameInstallIssue, ...] = ()

    @property
    def verified(self) -> bool:
        return (
            self.resource_probe_readable
            and bool(self.executable_sha256)
            and bool(self.chitin_key_sha256)
            and not any(row.severity == "error" for row in self.issues)
        )

    @property
    def fingerprint_sha256(self) -> str:
        facts = {
            "game": self.game,
            "executable_size": self.executable_size,
            "executable_sha256": self.executable_sha256,
            "chitin_key_size": self.chitin_key_size,
            "chitin_key_sha256": self.chitin_key_sha256,
            "chitin_signature": self.chitin_signature,
            "resource_probe_resref": self.resource_probe_resref,
            "resource_probe_mdl_sha256": self.resource_probe_mdl_sha256,
            "resource_probe_mdx_sha256": self.resource_probe_mdx_sha256,
        }
        encoded = json.dumps(
            facts,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "fingerprint_sha256": self.fingerprint_sha256,
            "game": self.game,
            "install_dir": self.install_dir,
            "executable_path": self.executable_path,
            "executable_size": self.executable_size,
            "executable_sha256": self.executable_sha256,
            "chitin_key_path": self.chitin_key_path,
            "chitin_key_size": self.chitin_key_size,
            "chitin_key_sha256": self.chitin_key_sha256,
            "chitin_signature": self.chitin_signature,
            "resource_probe_resref": self.resource_probe_resref,
            "resource_probe_mdl_sha256": self.resource_probe_mdl_sha256,
            "resource_probe_mdx_sha256": self.resource_probe_mdx_sha256,
            "resource_probe_source": self.resource_probe_source,
            "resource_probe_readable": self.resource_probe_readable,
            "issues": [row.to_dict() for row in self.issues],
        }


def verify_head_game_install(
    *,
    game: str,
    install_dir: str | Path,
    donor_catalog: HeadDonorCatalog | None,
    probe_resref: str = "",
) -> HeadGameInstallVerification:
    """Fingerprint an installation and perform one stock read-only probe."""

    normalized_game = str(game or "").strip().upper()
    root = Path(install_dir).expanduser()
    issues: list[HeadGameInstallIssue] = []

    def issue(
        check_id: str,
        message: str,
        *,
        severity: str = "error",
        **facts: Any,
    ) -> None:
        issues.append(
            HeadGameInstallIssue(
                check_id=check_id,
                severity=severity,
                message=message,
                facts=facts,
            )
        )

    if normalized_game not in {"K1", "K2"}:
        issue(
            "head.install.game",
            "Head Builder requires a KOTOR I or KOTOR II installation.",
            game=normalized_game,
        )
    if not root.is_dir():
        issue(
            "head.install.directory",
            "The selected game installation directory does not exist.",
            path=str(root),
        )

    executable_name = "swkotor.exe" if normalized_game == "K1" else "swkotor2.exe"
    executable_path = root / executable_name
    executable_size, executable_sha256 = _fingerprint_file(executable_path)
    if not executable_sha256:
        issue(
            "head.install.executable",
            f"The selected folder does not contain a readable {executable_name}.",
            path=str(executable_path),
        )

    chitin_path = root / "chitin.key"
    chitin_size, chitin_sha256 = _fingerprint_file(chitin_path)
    chitin_signature = _file_prefix(chitin_path, 8)
    if not chitin_sha256:
        issue(
            "head.install.chitin_key",
            "The selected folder does not contain a readable chitin.key.",
            path=str(chitin_path),
        )
    elif not chitin_signature.startswith("KEY "):
        issue(
            "head.install.chitin_signature",
            "chitin.key does not have an Odyssey KEY signature.",
            signature=chitin_signature,
        )

    selected_resref = ""
    probe_mdl_sha256 = ""
    probe_mdx_sha256 = ""
    probe_source = ""
    probe_readable = False
    if donor_catalog is None:
        issue(
            "head.install.resource_provider",
            "No game-resource provider is available for the read-only stock probe.",
        )
    else:
        try:
            selected_resref = str(probe_resref or "").strip()
            if not selected_resref:
                rows = donor_catalog.search(
                    game=normalized_game,
                    resource_view=ResourceView.STOCK_ONLY,
                    limit=1,
                    head_like_only=True,
                )
                if rows:
                    selected_resref = rows[0].resref
            if not selected_resref:
                raise HeadDonorCatalogError(
                    "No stock modular-head candidates were found"
                )
            bundle = donor_catalog.resolve(
                game=normalized_game,
                resref=selected_resref,
                resource_view=ResourceView.STOCK_ONLY,
            )
            if not bundle.candidate.stock:
                raise HeadDonorCatalogError(
                    "The stock probe resolved outside stock resource layers"
                )
            probe_mdl_sha256 = bundle.mdl_sha256
            probe_mdx_sha256 = bundle.mdx_sha256
            probe_source = str(bundle.candidate.mdl_record.source or "")
            probe_readable = bool(bundle.mdl_bytes and bundle.mdx_bytes)
        except (HeadDonorCatalogError, OSError, ValueError) as exc:
            issue(
                "head.install.stock_resource_probe",
                "Ghost Studio could not read a stock MDL/MDX head pair from "
                f"the selected installation: {exc}",
                resref=selected_resref,
            )

    return HeadGameInstallVerification(
        game=normalized_game,
        install_dir=str(root.resolve()) if root.exists() else str(root),
        executable_path=str(executable_path),
        executable_size=executable_size,
        executable_sha256=executable_sha256,
        chitin_key_path=str(chitin_path),
        chitin_key_size=chitin_size,
        chitin_key_sha256=chitin_sha256,
        chitin_signature=chitin_signature,
        resource_probe_resref=selected_resref,
        resource_probe_mdl_sha256=probe_mdl_sha256,
        resource_probe_mdx_sha256=probe_mdx_sha256,
        resource_probe_source=probe_source,
        resource_probe_readable=probe_readable,
        issues=tuple(issues),
    )


def _fingerprint_file(path: Path) -> tuple[int, str]:
    try:
        size = path.stat().st_size
        if not path.is_file() or size <= 0:
            return max(0, int(size)), ""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return int(size), digest.hexdigest()
    except OSError:
        return 0, ""


def _file_prefix(path: Path, count: int) -> str:
    try:
        with path.open("rb") as stream:
            return stream.read(count).decode("ascii", errors="replace")
    except OSError:
        return ""


__all__ = [
    "HeadGameInstallIssue",
    "HeadGameInstallVerification",
    "verify_head_game_install",
]
