"""Qt-free application service for Head Builder project and donor commands.

This is the Core Workflow facade used by a future Tools controller.  It
coordinates Core Project persistence and Core Resources discovery while
keeping MDL decode/eligibility decisions in the owning head workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Protocol

from src.core.characters.head_builder_project import (
    EvidenceLevel,
    EvidenceOutcome,
    EvidenceRecord,
    HeadBuilderGame,
    HeadBuilderProject,
    HeadBuilderStep,
    ResourceOrigin,
    ResourceProvenance,
    ResourceView,
    StepStatus,
)
from src.core.characters.head_attachment_preview import (
    HeadAttachmentPreviewResult,
    build_head_attachment_preview,
)
from src.core.characters.head_donor_snapshot import (
    HeadDonorContractDiff,
    HeadDonorEligibilityReport,
    HeadDonorSnapshot,
    capture_head_donor_snapshot,
    compare_head_donor_contract,
    validate_head_donor_snapshot,
)
from src.core.characters.head_geometry_transplant import (
    HeadGeometryTransplantResult,
    apply_head_skin_weight_edits,
    transplant_head_geometry_and_skin,
)
from src.core.characters.head_component_catalog import (
    HeadComponentAssemblyError,
    HeadComponentAssemblyResult,
    HeadComponentInventory,
    HeadComponentRole,
    HeadComponentSourceKind,
    assemble_head_components,
    inspect_head_component_inventory,
)
from src.core.characters.head_texture_materials import (
    HeadTextureMaterialResult,
    apply_head_texture_materials,
)
from src.core.project.head_builder_repository import (
    FileHeadBuilderProjectRepository,
    HeadBuilderProjectDocument,
)
from src.core.resources.head_donor_catalog import (
    HeadDonorCandidate,
    HeadDonorResourceBundle,
)
from src.io.head_art_importer import (
    HeadArtDocument,
    HeadArtValidationReport,
)
from src.io.head_texture_asset import (
    HeadTextureAsset,
    build_head_texture_output_policy,
    inspect_head_texture,
)
from src.io.head_binary_export import (
    HeadBinaryExportResult,
    write_verified_head_binary,
)
from src.io.head_builder_package import (
    HeadInstallPreview,
    HeadInstallResult,
    HeadPackageBuildResult,
    HeadPackageInstaller,
    build_head_package,
)
from src.io.head_game_records import (
    HeadGameRecordPatch,
    load_live_twoda,
)
from src.core.validation.head_builder_preflight import (
    HeadBuilderPreflightReport,
    preflight_head_builder_export,
)
from src.math.head_alignment import (
    HeadAlignmentAnchor,
    HeadAlignmentRequest,
    HeadAlignmentResult,
)
from src.math.head_uv import build_head_uv_orientation_contract


class HeadBuilderServiceError(RuntimeError):
    """Base workflow-service error."""


class HeadBuilderNoProjectError(HeadBuilderServiceError):
    """Raised when a command needs an active project."""


class HeadBuilderDonorRejectedError(HeadBuilderServiceError):
    """Raised when a selected resource is not an eligible modular-head donor."""

    def __init__(
        self,
        message: str,
        *,
        report: HeadDonorEligibilityReport,
    ) -> None:
        super().__init__(message)
        self.report = report


class HeadBuilderDonorChangedError(HeadBuilderServiceError):
    """Raised when a reopened project's donor bytes no longer match."""


class HeadBuilderArtRejectedError(HeadBuilderServiceError):
    """Raised when custom art contains blocking mesh/topology defects."""

    def __init__(
        self,
        message: str,
        *,
        report: HeadArtValidationReport,
    ) -> None:
        super().__init__(message)
        self.report = report


class HeadBuilderArtChangedError(HeadBuilderServiceError):
    """Raised when reopened custom-art bytes or decoded facts drift."""


class HeadBuilderComponentRejectedError(HeadBuilderServiceError):
    """Raised when stock component sources cannot preserve the carrier DAG."""


class HeadProjectRepositoryPort(Protocol):
    def new_document(
        self,
        project: HeadBuilderProject,
        path: str | Path,
    ) -> HeadBuilderProjectDocument: ...

    def load(self, path: str | Path) -> HeadBuilderProjectDocument: ...

    def save(
        self,
        document: HeadBuilderProjectDocument,
        path: str | Path | None = None,
        *,
        force: bool = False,
    ) -> HeadBuilderProjectDocument: ...


class HeadDonorCatalogPort(Protocol):
    def search(
        self,
        *,
        game: str,
        resource_view: ResourceView | str,
        text: str = "",
        limit: int = 250,
        head_like_only: bool = True,
    ) -> list[HeadDonorCandidate]: ...

    def resolve(
        self,
        *,
        game: str,
        resref: str,
        resource_view: ResourceView | str,
    ) -> HeadDonorResourceBundle: ...


ModelLoader = Callable[[bytes, bytes, str], Any]
InstallVerifier = Callable[[str, str], Any]
HeadArtImporter = Callable[..., tuple[HeadArtDocument, HeadArtValidationReport]]
HeadAlignmentSolver = Callable[[HeadAlignmentRequest], HeadAlignmentResult]
_HEAD_RESREF_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


@dataclass(frozen=True, slots=True)
class HeadDonorSelection:
    candidate: HeadDonorCandidate
    snapshot: HeadDonorSnapshot
    eligibility: HeadDonorEligibilityReport
    model: Any = field(repr=False, compare=False)

    @property
    def accepted(self) -> bool:
        return self.eligibility.eligible


@dataclass(frozen=True, slots=True)
class HeadArtSelection:
    document: HeadArtDocument
    report: HeadArtValidationReport

    @property
    def accepted(self) -> bool:
        return self.report.accepted


@dataclass(frozen=True, slots=True)
class HeadComponentSourceSelection:
    candidate: HeadDonorCandidate
    inventory: HeadComponentInventory
    model: Any = field(repr=False, compare=False)

    @property
    def accepted(self) -> bool:
        return self.inventory.accepted_as_component_source


class HeadBuilderService:
    """Single command path for project lifecycle and native donor selection."""

    def __init__(
        self,
        *,
        repository: HeadProjectRepositoryPort | None = None,
        donor_catalog: HeadDonorCatalogPort,
        model_loader: ModelLoader | None = None,
        install_verifier: InstallVerifier | None = None,
        art_importer: HeadArtImporter | None = None,
        alignment_solver: HeadAlignmentSolver | None = None,
        package_installer: HeadPackageInstaller | None = None,
    ) -> None:
        self.repository = repository or FileHeadBuilderProjectRepository()
        self.donor_catalog = donor_catalog
        self.model_loader = model_loader or _load_model
        self.install_verifier = (
            install_verifier or self._default_install_verifier
        )
        self.art_importer = art_importer or _import_head_art
        self.alignment_solver = alignment_solver or _solve_head_alignment
        self.package_installer = (
            package_installer or HeadPackageInstaller()
        )
        self._project: HeadBuilderProject | None = None
        self._document: HeadBuilderProjectDocument | None = None
        self._selected_model: Any = None
        self._imported_art: HeadArtDocument | None = None
        self._alignment_result: HeadAlignmentResult | None = None
        self._transplant_result: HeadGeometryTransplantResult | None = None
        self._component_result: HeadComponentAssemblyResult | None = None
        self._texture_result: HeadTextureMaterialResult | None = None
        self._preview_result: HeadAttachmentPreviewResult | None = None
        self._preflight_report: HeadBuilderPreflightReport | None = None
        self._binary_export_result: HeadBinaryExportResult | None = None
        self._package_result: HeadPackageBuildResult | None = None
        self._install_preview: HeadInstallPreview | None = None
        self._install_result: HeadInstallResult | None = None
        self._dirty = False

    @property
    def project(self) -> HeadBuilderProject:
        if self._project is None:
            raise HeadBuilderNoProjectError("No Head Builder project is open")
        return self._project

    @property
    def document_path(self) -> Path | None:
        return self._document.path if self._document is not None else None

    @property
    def selected_model(self) -> Any:
        return self._selected_model

    @property
    def imported_art(self) -> HeadArtDocument | None:
        return self._imported_art

    @property
    def alignment_result(self) -> HeadAlignmentResult | None:
        return self._alignment_result

    @property
    def transplant_result(self) -> HeadGeometryTransplantResult | None:
        return self._transplant_result

    @property
    def texture_result(self) -> HeadTextureMaterialResult | None:
        return self._texture_result

    @property
    def component_result(self) -> HeadComponentAssemblyResult | None:
        return self._component_result

    @property
    def preview_result(self) -> HeadAttachmentPreviewResult | None:
        return self._preview_result

    @property
    def preflight_report(self) -> HeadBuilderPreflightReport | None:
        return self._preflight_report

    @property
    def binary_export_result(self) -> HeadBinaryExportResult | None:
        return self._binary_export_result

    @property
    def package_result(self) -> HeadPackageBuildResult | None:
        return self._package_result

    @property
    def install_preview(self) -> HeadInstallPreview | None:
        return self._install_preview

    @property
    def install_result(self) -> HeadInstallResult | None:
        return self._install_result

    @property
    def candidate_model(self) -> Any:
        return (
            self._texture_result.model
            if self._texture_result is not None
            else (
                self._component_result.model
                if self._component_result is not None
                else (
                    self._transplant_result.model
                    if self._transplant_result is not None
                    else None
                )
            )
        )

    @property
    def dirty(self) -> bool:
        return self._dirty

    def snapshot_project(self) -> dict[str, Any]:
        """Return a JSON-safe project snapshot for product-surface undo."""

        return self.project.to_dict()

    def restore_project_snapshot(
        self,
        payload: Mapping[str, Any],
    ) -> HeadBuilderProject:
        """Restore project state without pretending runtime models survived."""

        project = HeadBuilderProject.from_dict(payload)
        self._project = project
        if self._document is not None:
            self._document.project = project
        self._selected_model = None
        self._imported_art = None
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._package_result = None
        self._install_preview = None
        self._install_result = None
        self._dirty = True
        return project

    def new_project(
        self,
        *,
        display_name: str = "Untitled Head",
        game: HeadBuilderGame | str = HeadBuilderGame.K2,
        path: str | Path | None = None,
    ) -> HeadBuilderProject:
        project = HeadBuilderProject.new(
            display_name=display_name,
            game=HeadBuilderGame(game),
        )
        self._project = project
        self._document = (
            self.repository.new_document(project, path)
            if path is not None
            else None
        )
        self._selected_model = None
        self._imported_art = None
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._package_result = None
        self._install_preview = None
        self._install_result = None
        self._dirty = True
        return project

    def verify_game_install(self, install_dir: str | None = None) -> Any:
        """Run the injected Core Resources read-only installation gate."""

        project = self.project
        selected_dir = str(
            project.game_install_dir
            if install_dir is None
            else install_dir
        )
        if not selected_dir:
            raise HeadBuilderServiceError(
                "Select a game installation directory before verification"
            )
        verification = self.install_verifier(
            project.game.value,
            selected_dir,
        )
        if not hasattr(verification, "verified") or not hasattr(
            verification,
            "to_dict",
        ):
            raise HeadBuilderServiceError(
                "The installation verifier returned an invalid result"
            )
        project.game_install_dir = selected_dir
        project.extensions["game_install_verification"] = (
            verification.to_dict()
        )
        verified = bool(verification.verified)
        fingerprint = str(
            getattr(verification, "fingerprint_sha256", "") or ""
        )
        evidence = EvidenceRecord(
            evidence_id=(
                f"head-install-{project.game.value.lower()}-"
                f"{fingerprint[:12] or 'unverified'}"
            ),
            check_id="head.game_install.read_only",
            label=f"{project.game.value} installation read-only verification",
            level=EvidenceLevel.STRUCTURAL,
            outcome=(
                EvidenceOutcome.PASS
                if verified
                else EvidenceOutcome.FAIL
            ),
            message=(
                "Executable, chitin.key, and a stock MDL/MDX pair were "
                "fingerprinted without modifying the installation."
                if verified
                else "The selected installation failed one or more read-only gates."
            ),
            hashes=_install_hashes(verification),
            metadata={"verification": verification.to_dict()},
        )
        project.record_evidence(evidence)
        if not verified:
            project.mark_step(
                HeadBuilderStep.PROJECT_GAME,
                StepStatus.BLOCKED,
                evidence_ids=[evidence.evidence_id],
            )
        elif (
            project.output_project_dir
            and valid_head_output_resref(project.output_head_resref)
        ):
            project.mark_step(
                HeadBuilderStep.PROJECT_GAME,
                StepStatus.COMPLETE,
                evidence_ids=[evidence.evidence_id],
            )
        else:
            project.mark_step(
                HeadBuilderStep.PROJECT_GAME,
                StepStatus.IN_PROGRESS,
                evidence_ids=[evidence.evidence_id],
            )
        self._dirty = True
        return verification

    def open_project(self, path: str | Path) -> HeadBuilderProject:
        document = self.repository.load(path)
        self._document = document
        self._project = document.project
        self._selected_model = None
        self._imported_art = None
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._package_result = None
        self._install_preview = None
        self._install_result = None
        self._dirty = bool(document.migrated_from_version is not None)
        return document.project

    def save_project(
        self,
        path: str | Path | None = None,
        *,
        force: bool = False,
    ) -> HeadBuilderProjectDocument:
        project = self.project
        if self._document is None:
            if path is None:
                raise HeadBuilderServiceError(
                    "A new Head Builder project needs a Save As path"
                )
            self._document = self.repository.new_document(project, path)
        document = self.repository.save(
            self._document,
            path,
            force=force,
        )
        self._project = document.project
        self._dirty = False
        return document

    def configure_game(
        self,
        *,
        game: HeadBuilderGame | str,
        resource_view: ResourceView | str,
        game_install_dir: str = "",
        output_project_dir: str = "",
        output_head_resref: str = "",
        character_context: dict[str, Any] | None = None,
    ) -> HeadBuilderProject:
        project = self.project
        project.game = HeadBuilderGame(game)
        project.resource_view = ResourceView(resource_view)
        project.game_install_dir = str(game_install_dir or "")
        project.output_project_dir = str(output_project_dir or "")
        project.output_head_resref = str(output_head_resref or "").strip()
        if character_context is not None:
            project.character_context = dict(character_context)
        project.mark_step(
            HeadBuilderStep.PROJECT_GAME,
            StepStatus.IN_PROGRESS,
        )
        self._dirty = True
        return project

    def import_custom_art(
        self,
        path: str | Path,
        *,
        source_axis: str = "auto",
        unit_scale_to_kotor: float = 1.0,
        flip_v: bool = True,
        source_texture_paths: tuple[str | Path, ...] = (),
        cleanup_policy: Mapping[str, Any] | None = None,
        raise_on_rejection: bool = True,
        fbx_loader: Callable[..., Any] | None = None,
    ) -> HeadArtSelection:
        """Import, audit, and record custom art without persisting mesh blobs."""

        project = self.project
        cleanup = dict(cleanup_policy or {})
        normal_policy = str(cleanup.get("normal_policy") or "preserve")
        if normal_policy not in {"preserve", "recalculate_missing"}:
            raise HeadBuilderServiceError(
                f"Unsupported custom-art normal policy: {normal_policy!r}"
            )
        if cleanup.get("weld_exact_duplicates"):
            raise HeadBuilderServiceError(
                "Exact duplicate welding is not available in this release; "
                "turn it off so vertex identities remain explicit"
            )
        if cleanup.get("triangulate", True) is False:
            raise HeadBuilderServiceError(
                "KOTOR head output requires triangle faces; keep triangulation enabled"
            )
        texture_paths = tuple(
            Path(value).expanduser().resolve()
            for value in source_texture_paths
            if str(value or "").strip()
        )
        missing_textures = [str(value) for value in texture_paths if not value.is_file()]
        if missing_textures:
            raise HeadBuilderServiceError(
                "One or more source textures do not exist: "
                + ", ".join(missing_textures[:4])
            )
        document, report = self.art_importer(
            path,
            source_axis=source_axis,
            unit_scale_to_kotor=unit_scale_to_kotor,
            flip_v=flip_v,
            fbx_loader=fbx_loader,
        )
        if not isinstance(document, HeadArtDocument) or not isinstance(
            report,
            HeadArtValidationReport,
        ):
            raise HeadBuilderServiceError(
                "The custom-art importer returned an invalid contract"
            )
        selection = HeadArtSelection(document=document, report=report)
        evidence = _art_evidence(document, report)
        had_accepted_art = isinstance(
            dict(project.import_art or {}).get("document"),
            dict,
        )
        project.record_evidence(evidence)
        if not report.accepted:
            if not had_accepted_art:
                project.mark_step(
                    HeadBuilderStep.IMPORT_CUSTOM_ART,
                    StepStatus.BLOCKED,
                    evidence_ids=[evidence.evidence_id],
                )
            self._dirty = True
            if raise_on_rejection:
                raise HeadBuilderArtRejectedError(
                    "Custom head art failed one or more blocking topology gates",
                    report=report,
                )
            return selection

        project.put_resource(
            ResourceProvenance(
                resource_id="custom_head_art",
                resource_type=document.source_format,
                origin=ResourceOrigin.IMPORTED_FILE,
                source_path=document.source_path,
                sha256=document.source_sha256,
                stock=False,
                metadata={
                    "structural_sha256": document.structural_sha256,
                    "source_axis": document.source_axis,
                    "unit_scale_to_kotor": document.unit_scale_to_kotor,
                    "part_count": len(document.parts),
                    "vertex_count": document.vertex_count,
                    "face_count": document.face_count,
                },
            )
        )
        for index, texture_path in enumerate(texture_paths):
            project.put_resource(
                ResourceProvenance(
                    resource_id=f"custom_head_source_texture_{index + 1}",
                    resource_type=texture_path.suffix.lstrip(".").upper() or "IMAGE",
                    origin=ResourceOrigin.IMPORTED_FILE,
                    source_path=str(texture_path),
                    sha256=_file_sha256(texture_path),
                    stock=False,
                    metadata={"role": "source_texture"},
                )
            )
        _reset_workflow_from(
            project,
            HeadBuilderStep.ALIGN_NECK_AND_HOOK,
        )
        project.import_art = {
            "document": document.project_facts(),
            "validation": report.to_dict(),
            "settings": {
                "source_axis": document.source_axis,
                "unit_scale_to_kotor": document.unit_scale_to_kotor,
                "flip_v": document.flip_v,
                "normal_policy": normal_policy,
                "weld_exact_duplicates": False,
                "triangulate": True,
                "source_texture_paths": [
                    str(texture_path) for texture_path in texture_paths
                ],
            },
        }
        project.appearance_customization = {
            "schema": "ghostrigger.head_builder_component_recipe",
            "version": 1,
            "mode": "custom_mesh",
            "recipe_name": project.display_name,
            "species_mode": str(
                project.character_context.get("species_mode")
                or "human_or_near_human"
            ),
            "custom_head_art_resource_id": "custom_head_art",
            "custom_head_art_structural_sha256": (
                document.structural_sha256
            ),
        }
        project.mark_step(
            HeadBuilderStep.IMPORT_CUSTOM_ART,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(
            HeadBuilderStep.ALIGN_NECK_AND_HOOK
            if isinstance(
                dict(project.donor_contract or {}).get("snapshot"),
                dict,
            )
            else HeadBuilderStep.SELECT_NATIVE_DONOR
        )
        self._imported_art = document
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return selection

    def rehydrate_custom_art(self) -> HeadArtSelection:
        """Reload saved custom art and prove both bytes and decoded facts."""

        project = self.project
        saved = _project_art_document(project)
        resource = project.resources.get("custom_head_art")
        source_path = str(
            (resource.source_path if resource is not None else "")
            or saved.get("source_path")
            or ""
        )
        if not source_path:
            raise HeadBuilderServiceError(
                "The active project has no custom-art source path"
            )
        settings = dict(project.import_art.get("settings") or {})
        document, report = self.art_importer(
            source_path,
            source_axis=str(
                settings.get("source_axis")
                or saved.get("source_axis")
                or "auto"
            ),
            unit_scale_to_kotor=float(
                settings.get(
                    "unit_scale_to_kotor",
                    saved.get("unit_scale_to_kotor", 1.0),
                )
            ),
            flip_v=bool(
                settings.get("flip_v", saved.get("flip_v", True))
            ),
            fbx_loader=None,
        )
        expected_sha = str(
            (resource.sha256 if resource is not None else "")
            or saved.get("source_sha256")
            or ""
        )
        if document.source_sha256.casefold() != expected_sha.casefold():
            raise HeadBuilderArtChangedError(
                "The custom-art source bytes no longer match the saved project; "
                "reimport the art explicitly before continuing."
            )
        expected_structural = str(saved.get("structural_sha256") or "")
        if (
            not expected_structural
            or document.structural_sha256.casefold()
            != expected_structural.casefold()
        ):
            raise HeadBuilderArtChangedError(
                "The custom-art decoded topology no longer matches the saved project."
            )
        if not report.accepted:
            raise HeadBuilderArtRejectedError(
                "The saved custom art no longer passes current topology gates",
                report=report,
            )
        self._imported_art = document
        return HeadArtSelection(document=document, report=report)

    def inspect_component_source(
        self,
        resref: str,
    ) -> HeadComponentSourceSelection:
        """Resolve and classify one stock model as a reusable head source."""

        project = self.project
        clean_resref = str(resref or "").strip()
        if not clean_resref:
            raise HeadBuilderServiceError(
                "A vanilla component source ResRef is required"
            )
        bundle = self.donor_catalog.resolve(
            game=project.game.value,
            resref=clean_resref,
            resource_view=project.resource_view,
        )
        model = self.model_loader(
            bundle.mdl_bytes,
            bundle.mdx_bytes,
            project.game.value,
        )
        if model is None:
            raise HeadBuilderServiceError(
                f"Ghost Studio could not decode component source "
                f"{project.game.value}:{clean_resref}"
            )
        inventory = inspect_head_component_inventory(
            model,
            game=project.game.value,
            resref=bundle.candidate.resref,
        )
        return HeadComponentSourceSelection(
            candidate=bundle.candidate,
            inventory=inventory,
            model=model,
        )

    def configure_vanilla_component_recipe(
        self,
        *,
        face_resref: str = "",
        eyes_resref: str = "",
        eyelashes_resref: str = "",
        hair_resref: str = "",
        species_mode: str = "human_or_near_human",
        recipe_name: str = "Custom combination",
    ) -> HeadComponentAssemblyResult:
        """Assemble compatible stock payloads into the selected carrier DAG."""

        project = self.project
        if self._selected_model is None:
            raise HeadBuilderServiceError(
                "Select or rehydrate a native carrier donor first"
            )
        carrier_snapshot = _project_snapshot(project)
        carrier_inventory = inspect_head_component_inventory(
            self._selected_model,
            game=project.game.value,
            resref=carrier_snapshot.resref,
        )
        normalized_species = str(species_mode or "").strip().lower()
        if normalized_species in {"ithorian", "unsupported_ithorian"}:
            raise HeadBuilderComponentRejectedError(
                "Ithorians are full-body replacements and cannot be combined "
                "with a player headless body."
            )
        if normalized_species == "humanoid_alien":
            if (
                carrier_inventory.source_kind
                is not HeadComponentSourceKind.ALIEN_MODULAR_HEAD
            ):
                raise HeadBuilderComponentRejectedError(
                    "Humanoid alien recipes require a verified modular alien "
                    "carrier such as a Twi'lek head, not a human carrier or a "
                    "full-body alien model."
                )
        elif carrier_inventory.source_kind is not (
            HeadComponentSourceKind.STANDARD_MODULAR_HEAD
        ):
            raise HeadBuilderComponentRejectedError(
                "Human/near-human recipes require a standard modular player "
                "head carrier."
            )

        requested = {
            HeadComponentRole.FACE: face_resref,
            HeadComponentRole.EYES: eyes_resref,
            HeadComponentRole.EYELASHES: eyelashes_resref,
            HeadComponentRole.HAIR: hair_resref,
        }
        source_selections: dict[
            HeadComponentRole,
            HeadComponentSourceSelection,
        ] = {}
        source_bundles: dict[
            HeadComponentRole,
            HeadDonorResourceBundle,
        ] = {}
        for role, raw_resref in requested.items():
            clean = str(raw_resref or carrier_snapshot.resref).strip()
            bundle = self.donor_catalog.resolve(
                game=project.game.value,
                resref=clean,
                resource_view=project.resource_view,
            )
            model = self.model_loader(
                bundle.mdl_bytes,
                bundle.mdx_bytes,
                project.game.value,
            )
            if model is None:
                raise HeadBuilderServiceError(
                    f"Ghost Studio could not decode {role.value} source "
                    f"{project.game.value}:{clean}"
                )
            inventory = inspect_head_component_inventory(
                model,
                game=project.game.value,
                resref=bundle.candidate.resref,
            )
            source_selections[role] = HeadComponentSourceSelection(
                candidate=bundle.candidate,
                inventory=inventory,
                model=model,
            )
            source_bundles[role] = bundle

        try:
            result = assemble_head_components(
                carrier_model=self._selected_model,
                carrier_snapshot=carrier_snapshot,
                carrier_inventory=carrier_inventory,
                sources={
                    role: (selection.model, selection.inventory)
                    for role, selection in source_selections.items()
                },
            )
        except HeadComponentAssemblyError as exc:
            raise HeadBuilderComponentRejectedError(str(exc)) from exc
        if not result.report.accepted:
            raise HeadBuilderComponentRejectedError(
                "The vanilla component recipe did not pass its carrier contract"
            )

        _reset_workflow_from(
            project,
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
        )
        donor_payload = dict(project.donor_contract or {})
        donor_payload["snapshot"] = result.donor_snapshot.to_dict()
        project.donor_contract = donor_payload
        for role, bundle in source_bundles.items():
            project.put_resource(
                _resource_provenance(
                    bundle,
                    restype="MDL",
                    resource_id=f"head_component_{role.value}_mdl",
                )
            )
            project.put_resource(
                _resource_provenance(
                    bundle,
                    restype="MDX",
                    resource_id=f"head_component_{role.value}_mdx",
                )
            )
        project.appearance_customization = {
            "schema": "ghostrigger.head_builder_component_recipe",
            "version": 1,
            "mode": "vanilla_components",
            "recipe_name": str(recipe_name or "").strip()
            or "Custom combination",
            "species_mode": normalized_species,
            "carrier": carrier_inventory.to_dict(),
            "sources": {
                role.value: selection.inventory.to_dict()
                for role, selection in source_selections.items()
            },
            "selections": {
                role.value: selection.inventory.resref
                for role, selection in source_selections.items()
            },
            "assembly_report": result.report.to_dict(),
        }
        evidence = EvidenceRecord(
            evidence_id=(
                "head-components-"
                f"{result.report.component_payload_sha256[:16]}"
            ),
            check_id="head.components.stock_recipe",
            label=(
                "Vanilla head component recipe: "
                f"{project.appearance_customization['recipe_name']}"
            ),
            level=EvidenceLevel.STRUCTURAL,
            outcome=EvidenceOutcome.PASS,
            message=(
                "Face, mouth, eyes, eyelids/lashes, and hair were rebased "
                "into existing carrier payload nodes while preserving its "
                "DAG, palette order, bind arrays, identities, and raw bounds."
            ),
            hashes={
                "component_payload_sha256": (
                    result.report.component_payload_sha256
                ),
                "carrier_structural_sha256": (
                    result.donor_snapshot.structural_sha256
                ),
            },
            metadata={
                "species_mode": normalized_species,
                "assembly": result.report.to_dict(),
            },
        )
        project.record_evidence(evidence)
        for step in (
            HeadBuilderStep.IMPORT_CUSTOM_ART,
            HeadBuilderStep.ALIGN_NECK_AND_HOOK,
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
        ):
            project.mark_step(
                step,
                StepStatus.COMPLETE,
                evidence_ids=[evidence.evidence_id],
            )
        project.set_current_step(
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS
        )
        project.import_art = {}
        project.alignment = {}
        project.skin_transfer = {}
        self._imported_art = None
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = result
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def rehydrate_vanilla_component_recipe(
        self,
    ) -> HeadComponentAssemblyResult:
        """Rebuild a saved stock recipe and verify all source fingerprints."""

        project = self.project
        if self._selected_model is None:
            raise HeadBuilderServiceError(
                "Rehydrate the selected carrier before component sources"
            )
        payload = dict(project.appearance_customization or {})
        if payload.get("schema") != (
            "ghostrigger.head_builder_component_recipe"
        ) or int(payload.get("version") or 0) != 1:
            raise HeadBuilderServiceError(
                "The active project has no supported vanilla component recipe"
            )
        carrier_snapshot = _project_snapshot(project)
        carrier_inventory = inspect_head_component_inventory(
            self._selected_model,
            game=project.game.value,
            resref=carrier_snapshot.resref,
        )
        selections = dict(payload.get("selections") or {})
        sources: dict[
            HeadComponentRole,
            tuple[Any, HeadComponentInventory],
        ] = {}
        for role in (
            HeadComponentRole.FACE,
            HeadComponentRole.EYES,
            HeadComponentRole.EYELASHES,
            HeadComponentRole.HAIR,
        ):
            resref = str(selections.get(role.value) or "")
            if not resref:
                raise HeadBuilderServiceError(
                    f"Saved component recipe has no {role.value} source"
                )
            bundle = self.donor_catalog.resolve(
                game=project.game.value,
                resref=resref,
                resource_view=project.resource_view,
            )
            for restype, digest in (
                ("mdl", bundle.mdl_sha256),
                ("mdx", bundle.mdx_sha256),
            ):
                resource = project.resources.get(
                    f"head_component_{role.value}_{restype}"
                )
                if (
                    resource is None
                    or resource.sha256.casefold() != digest.casefold()
                ):
                    raise HeadBuilderDonorChangedError(
                        f"Saved {role.value} {restype.upper()} bytes no longer "
                        "match the component recipe"
                    )
            model = self.model_loader(
                bundle.mdl_bytes,
                bundle.mdx_bytes,
                project.game.value,
            )
            inventory = inspect_head_component_inventory(
                model,
                game=project.game.value,
                resref=bundle.candidate.resref,
            )
            sources[role] = (model, inventory)
        result = assemble_head_components(
            carrier_model=self._selected_model,
            carrier_snapshot=carrier_snapshot,
            carrier_inventory=carrier_inventory,
            sources=sources,
        )
        saved_report = dict(payload.get("assembly_report") or {})
        if str(saved_report.get("component_payload_sha256") or "") != (
            result.report.component_payload_sha256
        ):
            raise HeadBuilderDonorChangedError(
                "Rebuilt vanilla component payload no longer matches the project"
            )
        self._component_result = result
        self._transplant_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        return result

    def align_custom_art(
        self,
        anchors: list[HeadAlignmentAnchor | dict[str, Any]],
        *,
        headhook_to_body: Any,
        body_resref: str,
        headhook_node_path: str,
        scale_mode: str = "fixed",
        maximum_rms_error: float = 0.01,
    ) -> HeadAlignmentResult:
        """Solve and record custom art into an exact body headhook bind space."""

        project = self.project
        document = self._imported_art
        if document is None:
            raise HeadBuilderServiceError(
                "Import or rehydrate custom art before alignment"
            )
        saved_art = _project_art_document(project)
        if (
            document.structural_sha256.casefold()
            != str(saved_art.get("structural_sha256") or "").casefold()
        ):
            raise HeadBuilderArtChangedError(
                "Runtime custom art does not match the project's accepted import"
            )
        donor = _project_snapshot(project)
        normalized_body = str(body_resref or "").strip()
        if not valid_head_output_resref(normalized_body):
            raise HeadBuilderServiceError(
                "Body context requires a valid 1-16 character Odyssey ResRef"
            )
        hook_path = str(headhook_node_path or "").strip()
        hook_name = re.split(r"[\\/]", hook_path)[-1].casefold()
        if hook_name != "headhook":
            raise HeadBuilderServiceError(
                "Body alignment requires the exact native headhook node"
            )
        tolerance = float(maximum_rms_error)
        if not math.isfinite(tolerance) or tolerance < 0.0:
            raise HeadBuilderServiceError(
                "maximum_rms_error must be finite and non-negative"
            )
        normalized_anchors = tuple(
            row
            if isinstance(row, HeadAlignmentAnchor)
            else HeadAlignmentAnchor(**dict(row))
            for row in anchors
        )
        result = self.alignment_solver(
            HeadAlignmentRequest(
                anchors=normalized_anchors,
                headhook_to_body=headhook_to_body,
                scale_mode=scale_mode,
            )
        )
        if not isinstance(result, HeadAlignmentResult):
            raise HeadBuilderServiceError(
                "The head alignment solver returned an invalid contract"
            )
        _reset_workflow_from(
            project,
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
        )
        within_tolerance = result.rms_error <= tolerance
        project.alignment = {
            "schema": "ghostrigger.head_builder_alignment",
            "version": 1,
            "body_context": {
                "game": project.game.value,
                "body_resref": normalized_body,
                "headhook_node_path": hook_path,
                "headhook_node_name": "headhook",
            },
            "anchors": [row.to_dict() for row in normalized_anchors],
            "maximum_rms_error": tolerance,
            "within_tolerance": within_tolerance,
            "result": result.to_dict(),
        }
        project.character_context["body_resref"] = normalized_body
        evidence = _alignment_evidence(
            document=document,
            donor=donor,
            result=result,
            body_resref=normalized_body,
            headhook_node_path=hook_path,
            maximum_rms_error=tolerance,
            within_tolerance=within_tolerance,
        )
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.ALIGN_NECK_AND_HOOK,
            (
                StepStatus.COMPLETE
                if within_tolerance
                else StepStatus.IN_PROGRESS
            ),
            evidence_ids=[evidence.evidence_id],
        )
        if within_tolerance:
            project.set_current_step(
                HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN
            )
        self._alignment_result = result
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def rehydrate_alignment(self) -> HeadAlignmentResult:
        """Verify and restore the saved named-space alignment matrices."""

        project = self.project
        if self._imported_art is None:
            raise HeadBuilderServiceError(
                "Rehydrate custom art before restoring alignment"
            )
        _project_snapshot(project)
        payload = dict(project.alignment or {})
        result_payload = payload.get("result")
        if not isinstance(result_payload, dict):
            raise HeadBuilderServiceError(
                "The active project has no accepted alignment result"
            )
        try:
            result = HeadAlignmentResult.from_dict(result_payload)
        except Exception as exc:
            raise HeadBuilderArtChangedError(
                f"The saved alignment contract is invalid: {exc}"
            ) from exc
        if not bool(payload.get("within_tolerance", False)):
            raise HeadBuilderServiceError(
                "The saved alignment has not passed its RMS tolerance"
            )
        self._alignment_result = result
        return result

    def transplant_geometry_and_skin(
        self,
        *,
        part_modes: dict[str, str] | None,
        neck_vertex_ids: list[str],
        maximum_surface_distance: float,
        allow_distance_fallback: bool = True,
        rigid_fallback_bone: str = "head_g",
        minimum_neck_weight: float = 0.05,
    ) -> HeadGeometryTransplantResult:
        """Replace only the donor's mutable rendered skin payload."""

        project = self.project
        if self._selected_model is None:
            raise HeadBuilderServiceError(
                "Select or rehydrate the pristine donor before transplant"
            )
        if self._imported_art is None:
            raise HeadBuilderServiceError(
                "Import or rehydrate custom art before transplant"
            )
        if self._alignment_result is None:
            raise HeadBuilderServiceError(
                "Solve or rehydrate headhook alignment before transplant"
            )
        snapshot = _project_snapshot(project)
        result = transplant_head_geometry_and_skin(
            donor_model=self._selected_model,
            donor_snapshot=snapshot,
            art_document=self._imported_art,
            alignment=self._alignment_result,
            part_modes=part_modes,
            neck_vertex_ids=neck_vertex_ids,
            maximum_surface_distance=maximum_surface_distance,
            allow_distance_fallback=allow_distance_fallback,
            rigid_fallback_bone=rigid_fallback_bone,
            minimum_neck_weight=minimum_neck_weight,
        )
        if not result.report.accepted:
            raise HeadBuilderServiceError(
                "The donor-preserving transplant did not pass its contract"
            )
        _reset_workflow_from(
            project,
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
        )
        project.skin_transfer = {
            "schema": "ghostrigger.head_builder_skin_transfer",
            "version": 1,
            "settings": {
                "part_modes": {
                    str(key): str(value)
                    for key, value in dict(part_modes or {}).items()
                },
                "neck_vertex_ids": [
                    str(value) for value in neck_vertex_ids
                ],
                "maximum_surface_distance": float(
                    maximum_surface_distance
                ),
                "allow_distance_fallback": bool(
                    allow_distance_fallback
                ),
                "rigid_fallback_bone": str(rigid_fallback_bone),
                "minimum_neck_weight": float(minimum_neck_weight),
            },
            "manual_edits": {},
            "report": result.report.to_dict(),
        }
        evidence = _transplant_evidence(snapshot, result)
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS
        )
        self._transplant_result = result
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def rehydrate_transplant(self) -> HeadGeometryTransplantResult:
        """Deterministically rebuild saved geometry/weights and verify hashes."""

        project = self.project
        if self._selected_model is None:
            raise HeadBuilderServiceError(
                "Rehydrate the pristine donor before rebuilding its payload"
            )
        if self._imported_art is None:
            raise HeadBuilderServiceError(
                "Rehydrate custom art before rebuilding its payload"
            )
        if self._alignment_result is None:
            self.rehydrate_alignment()
        payload = dict(project.skin_transfer or {})
        if payload.get("schema") != "ghostrigger.head_builder_skin_transfer":
            raise HeadBuilderServiceError(
                "The active project has no saved skin-transfer contract"
            )
        if int(payload.get("version") or 0) != 1:
            raise HeadBuilderServiceError(
                "Unsupported saved skin-transfer version"
            )
        settings = dict(payload.get("settings") or {})
        result = transplant_head_geometry_and_skin(
            donor_model=self._selected_model,
            donor_snapshot=_project_snapshot(project),
            art_document=self._imported_art,
            alignment=self._alignment_result,
            part_modes=dict(settings.get("part_modes") or {}),
            neck_vertex_ids=list(
                settings.get("neck_vertex_ids") or []
            ),
            maximum_surface_distance=float(
                settings.get("maximum_surface_distance")
            ),
            allow_distance_fallback=bool(
                settings.get("allow_distance_fallback", True)
            ),
            rigid_fallback_bone=str(
                settings.get("rigid_fallback_bone") or "head_g"
            ),
            minimum_neck_weight=float(
                settings.get("minimum_neck_weight", 0.05)
            ),
        )
        edits = {
            str(vertex_id): {
                str(bone): float(weight)
                for bone, weight in dict(weights or {}).items()
            }
            for vertex_id, weights in dict(
                payload.get("manual_edits") or {}
            ).items()
        }
        if edits:
            result = apply_head_skin_weight_edits(
                result,
                donor_snapshot=_project_snapshot(project),
                edits=edits,
            )
            _validate_saved_neck_weight_floor(project, result)
        saved_report = dict(payload.get("report") or {})
        for key, actual in (
            ("geometry_sha256", result.report.geometry_sha256),
            (
                "final_weight_rows_sha256",
                result.report.final_weight_rows_sha256,
            ),
            ("payload_sha256", result.report.payload_sha256),
        ):
            if str(saved_report.get(key) or "") != actual:
                raise HeadBuilderArtChangedError(
                    f"Rebuilt transplant {key} does not match the saved project"
                )
        self._transplant_result = result
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        return result

    def edit_skin_weights(
        self,
        vertex_id: str,
        weights_by_bone: dict[str, float],
    ) -> HeadGeometryTransplantResult:
        """Apply one sparse, donor-palette-safe manual weight edit."""

        project = self.project
        if self._transplant_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate the donor payload before editing weights"
            )
        payload = dict(project.skin_transfer or {})
        edits = {
            str(key): dict(value or {})
            for key, value in dict(payload.get("manual_edits") or {}).items()
        }
        edits[str(vertex_id)] = {
            str(bone): float(weight)
            for bone, weight in dict(weights_by_bone or {}).items()
        }
        result = apply_head_skin_weight_edits(
            self._transplant_result,
            donor_snapshot=_project_snapshot(project),
            edits=edits,
        )
        _validate_saved_neck_weight_floor(project, result)
        payload["manual_edits"] = edits
        payload["report"] = result.report.to_dict()
        project.skin_transfer = payload
        evidence = _transplant_evidence(
            _project_snapshot(project),
            result,
        )
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        _reset_workflow_from(
            project,
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
        )
        project.set_current_step(HeadBuilderStep.UV_TEXTURES_AND_MATERIALS)
        self._transplant_result = result
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def reset_skin_weight_edit(
        self,
        vertex_id: str,
    ) -> HeadGeometryTransplantResult:
        """Remove one sparse edit and regenerate all remaining rows."""

        project = self.project
        if self._transplant_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate the donor payload before resetting weights"
            )
        payload = dict(project.skin_transfer or {})
        edits = {
            str(key): dict(value or {})
            for key, value in dict(payload.get("manual_edits") or {}).items()
        }
        edits.pop(str(vertex_id), None)
        result = apply_head_skin_weight_edits(
            self._transplant_result,
            donor_snapshot=_project_snapshot(project),
            edits=edits,
        )
        _validate_saved_neck_weight_floor(project, result)
        payload["manual_edits"] = edits
        payload["report"] = result.report.to_dict()
        project.skin_transfer = payload
        evidence = _transplant_evidence(
            _project_snapshot(project),
            result,
        )
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        _reset_workflow_from(
            project,
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
        )
        project.set_current_step(HeadBuilderStep.UV_TEXTURES_AND_MATERIALS)
        self._transplant_result = result
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def reset_all_skin_weight_edits(self) -> HeadGeometryTransplantResult:
        """Restore every candidate weight row to the deterministic baseline."""

        project = self.project
        if self._transplant_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate the donor payload before resetting weights"
            )
        payload = dict(project.skin_transfer or {})
        result = apply_head_skin_weight_edits(
            self._transplant_result,
            donor_snapshot=_project_snapshot(project),
            edits={},
        )
        _validate_saved_neck_weight_floor(project, result)
        payload["manual_edits"] = {}
        payload["report"] = result.report.to_dict()
        project.skin_transfer = payload
        evidence = _transplant_evidence(
            _project_snapshot(project),
            result,
        )
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        _reset_workflow_from(
            project,
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
        )
        project.set_current_step(HeadBuilderStep.UV_TEXTURES_AND_MATERIALS)
        self._transplant_result = result
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def configure_uv_texture_materials(
        self,
        texture_path: str | Path,
        *,
        output_texture_resref: str,
        output_format: str,
        serialized_uv_transform: str,
        preview_uv_transform: str,
        txi_path: str | Path | None = None,
        txi_delivery: str = "auto",
        alpha_mode: str = "opaque",
        environment_map_resref: str = "",
        bumpmap_resref: str = "",
        clamp_s: bool = False,
        clamp_t: bool = False,
        mipmap: bool = True,
        preserve_source_txi: bool = True,
    ) -> HeadTextureMaterialResult:
        """Apply one explicit UV/material policy to the transplanted head."""

        project = self.project
        payload_result = self._component_result or self._transplant_result
        if payload_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate a custom or vanilla head payload before "
                "assigning texture"
            )
        if self._imported_art is None and self._component_result is None:
            raise HeadBuilderServiceError(
                "Import or rehydrate custom art before assigning texture"
            )
        asset = inspect_head_texture(texture_path, txi_path=txi_path)
        if not asset.accepted:
            raise HeadBuilderServiceError(
                "Texture source failed its KOTOR dimension/decode contract"
            )
        output_policy = build_head_texture_output_policy(
            asset,
            output_resref=output_texture_resref,
            output_format=output_format,
            txi_delivery=txi_delivery,
            alpha_mode=alpha_mode,
            environment_map_resref=environment_map_resref,
            bumpmap_resref=bumpmap_resref,
            clamp_s=clamp_s,
            clamp_t=clamp_t,
            mipmap=mipmap,
            preserve_source_txi=preserve_source_txi,
        )
        node = _transplant_payload_node(payload_result)
        uv_contract = build_head_uv_orientation_contract(
            list(getattr(node, "uvs", ()) or ()),
            list(getattr(node, "faces", ()) or ()),
            source_v_flip_applied=(
                self._imported_art.flip_v
                if self._imported_art is not None
                else False
            ),
            serialized_transform=serialized_uv_transform,
            preview_transform=preview_uv_transform,
        )
        result = apply_head_texture_materials(
            payload_result,
            donor_snapshot=_project_snapshot(project),
            asset=asset,
            output_policy=output_policy,
            uv_contract=uv_contract,
        )
        if not result.report.accepted:
            raise HeadBuilderServiceError(
                "UV, material, and texture policy did not pass its contract"
            )
        _reset_workflow_from(
            project,
            HeadBuilderStep.ATTACHMENT_AND_ANIMATION_PREVIEW,
        )
        project.put_resource(
            ResourceProvenance(
                resource_id="custom_head_texture",
                resource_type=asset.source_format,
                resref=output_policy.output_resref,
                origin=ResourceOrigin.IMPORTED_FILE,
                source_path=asset.source_path,
                sha256=asset.source_sha256,
                stock=False,
                metadata={
                    "decoded_rgba_sha256": asset.decoded_rgba_sha256,
                    "width": asset.width,
                    "height": asset.height,
                    "mipmap_count": asset.mipmap_count,
                    "txi_origin": asset.txi_origin,
                    "txi_path": asset.txi_path,
                    "txi_sha256": asset.txi_sha256,
                },
            )
        )
        project.texture_materials = {
            "schema": "ghostrigger.head_builder_texture_materials",
            "version": 1,
            "source": asset.project_facts(),
            "output_policy": output_policy.to_dict(),
            "uv_orientation": uv_contract.to_dict(),
            "report": result.report.to_dict(),
        }
        evidence = _texture_material_evidence(result)
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.UV_TEXTURES_AND_MATERIALS,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(
            HeadBuilderStep.ATTACHMENT_AND_ANIMATION_PREVIEW
        )
        self._texture_result = result
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def rehydrate_uv_texture_materials(
        self,
    ) -> HeadTextureMaterialResult:
        """Rebuild the saved texture/UV decision and verify all fingerprints."""

        project = self.project
        payload_result = self._component_result or self._transplant_result
        if payload_result is None:
            raise HeadBuilderServiceError(
                "Rehydrate the custom or vanilla head payload before restoring "
                "materials"
            )
        if self._imported_art is None and self._component_result is None:
            raise HeadBuilderServiceError(
                "Rehydrate custom art before restoring materials"
            )
        payload = dict(project.texture_materials or {})
        if payload.get("schema") != "ghostrigger.head_builder_texture_materials":
            raise HeadBuilderServiceError(
                "The active project has no saved UV/material contract"
            )
        if int(payload.get("version") or 0) != 1:
            raise HeadBuilderServiceError(
                "Unsupported saved UV/material contract version"
            )
        source = dict(payload.get("source") or {})
        source_path = str(source.get("source_path") or "")
        if not source_path:
            raise HeadBuilderServiceError(
                "Saved texture source path is unavailable"
            )
        saved_txi_path = str(source.get("txi_path") or "")
        asset = inspect_head_texture(
            source_path,
            txi_path=(saved_txi_path or None),
        )
        for key, actual in (
            ("source_sha256", asset.source_sha256),
            ("decoded_rgba_sha256", asset.decoded_rgba_sha256),
            ("txi_sha256", asset.txi_sha256),
        ):
            if str(source.get(key) or "") != actual:
                raise HeadBuilderArtChangedError(
                    f"Reopened texture {key} no longer matches the project"
                )
        saved_policy = dict(payload.get("output_policy") or {})
        output_policy = build_head_texture_output_policy(
            asset,
            output_resref=str(saved_policy.get("output_resref") or ""),
            output_format=str(saved_policy.get("output_format") or ""),
            txi_delivery=str(saved_policy.get("txi_delivery") or ""),
            alpha_mode=str(saved_policy.get("alpha_mode") or ""),
            environment_map_resref=str(
                saved_policy.get("environment_map_resref") or ""
            ),
            bumpmap_resref=str(saved_policy.get("bumpmap_resref") or ""),
            clamp_s=bool(saved_policy.get("clamp_s", False)),
            clamp_t=bool(saved_policy.get("clamp_t", False)),
            mipmap=bool(saved_policy.get("mipmap", True)),
            preserve_source_txi=bool(
                saved_policy.get("preserve_source_txi", True)
            ),
        )
        saved_uv = dict(payload.get("uv_orientation") or {})
        node = _transplant_payload_node(payload_result)
        uv_contract = build_head_uv_orientation_contract(
            list(getattr(node, "uvs", ()) or ()),
            list(getattr(node, "faces", ()) or ()),
            source_v_flip_applied=bool(
                saved_uv.get("source_v_flip_applied", False)
            ),
            serialized_transform=str(
                saved_uv.get("serialized_transform") or ""
            ),
            preview_transform=str(
                saved_uv.get("preview_transform") or ""
            ),
        )
        result = apply_head_texture_materials(
            payload_result,
            donor_snapshot=_project_snapshot(project),
            asset=asset,
            output_policy=output_policy,
            uv_contract=uv_contract,
        )
        saved_report = dict(payload.get("report") or {})
        for key, actual in (
            (
                "source_texture_sha256",
                result.report.source_texture_sha256,
            ),
            ("serialized_uv_sha256", result.report.serialized_uv_sha256),
            (
                "material_payload_sha256",
                result.report.material_payload_sha256,
            ),
        ):
            if str(saved_report.get(key) or "") != actual:
                raise HeadBuilderArtChangedError(
                    f"Rebuilt material {key} does not match the saved project"
                )
        self._texture_result = result
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        return result

    def preview_attachment_and_animations(
        self,
        *,
        body_resref: str,
        selected_animation_names: tuple[str, ...] = (
            "tlknorm",
            "talk",
            "listen",
            "walk",
        ),
    ) -> HeadAttachmentPreviewResult:
        """Build and record an exact-headhook inherited-animation preview."""

        project = self.project
        candidate = self.candidate_model
        if self._texture_result is None or candidate is None:
            raise HeadBuilderServiceError(
                "Assign and verify the head texture before attachment preview"
            )
        resolved_bundles: dict[str, HeadDonorResourceBundle] = {}
        resolved_models: dict[str, Any] = {}

        def load_resource(resref: str) -> Any | None:
            key = str(resref or "").strip().casefold()
            if not key:
                return None
            if key in resolved_models:
                return resolved_models[key]
            try:
                bundle = self.donor_catalog.resolve(
                    game=project.game.value,
                    resref=resref,
                    resource_view=project.resource_view,
                )
                model = self.model_loader(
                    bundle.mdl_bytes,
                    bundle.mdx_bytes,
                    project.game.value,
                )
            except Exception:
                return None
            resolved_bundles[key] = bundle
            resolved_models[key] = model
            return model

        body_model = load_resource(body_resref)
        if body_model is None:
            raise HeadBuilderServiceError(
                f"Preview body '{body_resref}' could not be resolved"
            )
        result = build_head_attachment_preview(
            body_model=body_model,
            head_model=candidate,
            game=project.game.value,
            body_resref=body_resref,
            head_resref=project.output_head_resref,
            supermodel_loader=load_resource,
            selected_animation_names=selected_animation_names,
        )
        donor_diff = self.compare_donor_contract(candidate)
        if not donor_diff.structurally_compatible:
            raise HeadBuilderServiceError(
                "Attachment preview candidate no longer preserves the donor contract"
            )
        if not result.report.accepted:
            raise HeadBuilderServiceError(
                "Attachment or inherited-animation preview failed its contract: "
                + "; ".join(result.report.blocking_issues)
            )

        _reset_workflow_from(
            project,
            HeadBuilderStep.ATTACHMENT_AND_ANIMATION_PREVIEW,
        )
        resource_rows = _preview_resource_rows(
            resolved_bundles,
            body_resref=body_resref,
        )
        for index, row in enumerate(resource_rows):
            bundle = resolved_bundles[row["resref"].casefold()]
            prefix = (
                "preview_body"
                if row["role"] == "body"
                else f"preview_supermodel_{index:02d}"
            )
            project.put_resource(
                _resource_provenance(
                    bundle,
                    restype="MDL",
                    resource_id=f"{prefix}_mdl",
                )
            )
            project.put_resource(
                _resource_provenance(
                    bundle,
                    restype="MDX",
                    resource_id=f"{prefix}_mdx",
                )
            )
        project.attachment_preview = {
            "schema": "ghostrigger.head_builder_attachment_preview",
            "version": 1,
            "body_resref": str(body_resref),
            "selected_animation_names": list(selected_animation_names),
            "resources": resource_rows,
            "report": _attachment_preview_project_report(result),
            "donor_contract_diff": donor_diff.to_dict(),
        }
        evidence = _attachment_preview_evidence(result, donor_diff)
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.ATTACHMENT_AND_ANIMATION_PREVIEW,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        skip_evidence = _optional_physics_skipped_evidence(
            result.report.contract_sha256
        )
        project.record_evidence(skip_evidence)
        project.physics = {
            "enabled": False,
            "status": "not_requested",
            "message": (
                "Optional hair/accessory physics is outside this project scope."
            ),
        }
        project.mark_step(
            HeadBuilderStep.OPTIONAL_HAIR_PHYSICS,
            StepStatus.COMPLETE,
            evidence_ids=[skip_evidence.evidence_id],
        )
        project.set_current_step(HeadBuilderStep.BINARY_PREFLIGHT)
        self._preview_result = result
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return result

    def rehydrate_attachment_preview(self) -> HeadAttachmentPreviewResult:
        """Rebuild the saved preview and verify resource/report fingerprints."""

        project = self.project
        candidate = self.candidate_model
        if self._texture_result is None or candidate is None:
            raise HeadBuilderServiceError(
                "Rehydrate texture/material state before attachment preview"
            )
        payload = dict(project.attachment_preview or {})
        if payload.get("schema") != (
            "ghostrigger.head_builder_attachment_preview"
        ):
            raise HeadBuilderServiceError(
                "The active project has no saved attachment preview"
            )
        if int(payload.get("version") or 0) != 1:
            raise HeadBuilderServiceError(
                "Unsupported saved attachment preview version"
            )
        body_resref = str(payload.get("body_resref") or "")
        requested = tuple(
            str(value)
            for value in list(
                payload.get("selected_animation_names") or []
            )
            if str(value)
        )
        resolved_bundles: dict[str, HeadDonorResourceBundle] = {}
        resolved_models: dict[str, Any] = {}

        def load_resource(resref: str) -> Any | None:
            key = str(resref or "").strip().casefold()
            if not key:
                return None
            if key in resolved_models:
                return resolved_models[key]
            try:
                bundle = self.donor_catalog.resolve(
                    game=project.game.value,
                    resref=resref,
                    resource_view=project.resource_view,
                )
                model = self.model_loader(
                    bundle.mdl_bytes,
                    bundle.mdx_bytes,
                    project.game.value,
                )
            except Exception:
                return None
            resolved_bundles[key] = bundle
            resolved_models[key] = model
            return model

        body_model = load_resource(body_resref)
        if body_model is None:
            raise HeadBuilderServiceError(
                f"Saved preview body '{body_resref}' could not be resolved"
            )
        result = build_head_attachment_preview(
            body_model=body_model,
            head_model=candidate,
            game=project.game.value,
            body_resref=body_resref,
            head_resref=project.output_head_resref,
            supermodel_loader=load_resource,
            selected_animation_names=requested,
        )
        saved_resources = list(payload.get("resources") or [])
        actual_resources = _preview_resource_rows(
            resolved_bundles,
            body_resref=body_resref,
        )
        if saved_resources != actual_resources:
            raise HeadBuilderDonorChangedError(
                "Reopened preview body/supermodel bytes no longer match"
            )
        saved_report = dict(payload.get("report") or {})
        if str(saved_report.get("contract_sha256") or "") != (
            result.report.contract_sha256
        ):
            raise HeadBuilderArtChangedError(
                "Rebuilt attachment/animation contract does not match the project"
            )
        donor_diff = self.compare_donor_contract(candidate)
        if not donor_diff.structurally_compatible or not result.report.accepted:
            raise HeadBuilderServiceError(
                "Reopened attachment preview no longer passes its contract"
            )
        self._preview_result = result
        self._preflight_report = None
        self._binary_export_result = None
        return result

    def run_binary_preflight(self) -> HeadBuilderPreflightReport:
        """Run every structural and binary/readback gate without writing files."""

        project = self.project
        candidate = self.candidate_model
        if self._preview_result is None or candidate is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate attachment preview before binary preflight"
            )
        if self._texture_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate UV/material state before binary preflight"
            )
        report = preflight_head_builder_export(
            candidate,
            donor_snapshot=_project_snapshot(project),
            game=project.game.value,
            output_resref=project.output_head_resref,
            texture_report=self._texture_result.report,
            attachment_report=self._preview_result.report,
            acknowledged_warning_ids=project.acknowledged_warnings,
        )
        _reset_workflow_from(project, HeadBuilderStep.BINARY_PREFLIGHT)
        project.export_plan = {
            "schema": "ghostrigger.head_builder_export_plan",
            "version": 1,
            "output_resref": project.output_head_resref,
            "preflight": report.to_dict(),
            "binary_export": {},
        }
        evidence = _binary_preflight_evidence(report)
        project.record_evidence(evidence)
        status = (
            StepStatus.COMPLETE
            if report.export_allowed
            else (
                StepStatus.BLOCKED
                if report.blocking_issues
                else StepStatus.IN_PROGRESS
            )
        )
        project.mark_step(
            HeadBuilderStep.BINARY_PREFLIGHT,
            status,
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(
            HeadBuilderStep.GAME_RECORDS_AND_PACKAGE
            if report.export_allowed
            else HeadBuilderStep.BINARY_PREFLIGHT
        )
        self._preflight_report = report
        self._binary_export_result = None
        self._dirty = True
        return report

    def rehydrate_binary_preflight(self) -> HeadBuilderPreflightReport:
        """Restore the saved preflight runtime report without mutating project."""

        project = self.project
        candidate = self.candidate_model
        if self._preview_result is None or candidate is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate attachment preview before binary preflight"
            )
        if self._texture_result is None:
            raise HeadBuilderServiceError(
                "Build or rehydrate UV/material state before binary preflight"
            )
        export_plan = dict(project.export_plan or {})
        saved_preflight = dict(export_plan.get("preflight") or {})
        saved_sha256 = str(saved_preflight.get("report_sha256") or "")
        if not saved_sha256:
            raise HeadBuilderServiceError(
                "The saved project does not contain a binary preflight report"
            )
        report = preflight_head_builder_export(
            candidate,
            donor_snapshot=_project_snapshot(project),
            game=project.game.value,
            output_resref=project.output_head_resref,
            texture_report=self._texture_result.report,
            attachment_report=self._preview_result.report,
            acknowledged_warning_ids=project.acknowledged_warnings,
        )
        if report.report_sha256 != saved_sha256:
            raise HeadBuilderServiceError(
                "Reopened binary preflight no longer matches the saved project"
            )
        self._preflight_report = report
        self._binary_export_result = None
        return report

    def acknowledge_preflight_warnings(
        self,
        warning_ids: tuple[str, ...],
    ) -> HeadBuilderPreflightReport:
        """Explicitly acknowledge only warnings surfaced by the last report."""

        if self._preflight_report is None:
            raise HeadBuilderServiceError(
                "Run binary preflight before acknowledging warnings"
            )
        known = {
            issue.check_id
            for issue in self._preflight_report.warning_issues
        }
        requested = {
            str(value)
            for value in warning_ids
            if str(value)
        }
        unknown = sorted(requested - known)
        if unknown:
            raise HeadBuilderServiceError(
                "Cannot acknowledge warnings not present in the report: "
                + ", ".join(unknown)
            )
        project = self.project
        project.acknowledged_warnings = sorted(
            set(project.acknowledged_warnings) | requested
        )
        self._dirty = True
        return self.run_binary_preflight()

    def export_verified_binary(
        self,
        *,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> HeadBinaryExportResult:
        """Atomically publish the already verified MDL/MDX candidate."""

        project = self.project
        report = self._preflight_report
        if (
            report is None
            or not report.export_allowed
            or report.binary_build is None
        ):
            raise HeadBuilderServiceError(
                "Binary export requires an accepted, warning-acknowledged preflight"
            )
        destination = str(
            output_dir
            if output_dir is not None
            else project.output_project_dir
        )
        if not destination:
            raise HeadBuilderServiceError(
                "Select an output project directory before binary export"
            )
        result = write_verified_head_binary(
            report.binary_build,
            output_dir=destination,
            overwrite=overwrite,
            manifest_metadata={
                "project_id": project.project_id,
                "display_name": project.display_name,
                "game": project.game.value,
                "donor": _project_snapshot(project).resref,
                "acknowledged_warning_ids": list(
                    report.acknowledged_warning_ids
                ),
                "preflight_sha256": report.report_sha256,
            },
        )
        project.export_plan["binary_export"] = {
            "mdl_path": result.mdl_path,
            "mdx_path": result.mdx_path,
            "manifest_path": result.manifest_path,
            "inspection": result.inspection.to_dict(),
        }
        project.put_resource(
            ResourceProvenance(
                resource_id="generated_head_mdl",
                resource_type="MDL",
                resref=project.output_head_resref,
                origin=ResourceOrigin.GENERATED,
                source_path=result.mdl_path,
                sha256=result.inspection.mdl_sha256,
                stock=False,
                metadata={
                    "inspection_sha256": (
                        result.inspection.inspection_sha256
                    )
                },
            )
        )
        project.put_resource(
            ResourceProvenance(
                resource_id="generated_head_mdx",
                resource_type="MDX",
                resref=project.output_head_resref,
                origin=ResourceOrigin.GENERATED,
                source_path=result.mdx_path,
                sha256=result.inspection.mdx_sha256,
                stock=False,
                metadata={
                    "inspection_sha256": (
                        result.inspection.inspection_sha256
                    )
                },
            )
        )
        evidence = _binary_export_evidence(result)
        project.record_evidence(evidence)
        preflight_evidence_ids = list(
            project.workflow_steps[
                HeadBuilderStep.BINARY_PREFLIGHT
            ].evidence_ids
        )
        project.mark_step(
            HeadBuilderStep.BINARY_PREFLIGHT,
            StepStatus.COMPLETE,
            evidence_ids=preflight_evidence_ids + [evidence.evidence_id],
        )
        project.set_current_step(
            HeadBuilderStep.GAME_RECORDS_AND_PACKAGE
        )
        self._binary_export_result = result
        self._dirty = True
        return result

    def build_game_records_package(
        self,
        *,
        appearance_donor_label: str,
        package_directory: str | Path | None = None,
        appearance_label: str = "",
        portrait_resref: str = "",
        portrait_donor_resref: str = "",
        portrait_files: tuple[str | Path, ...] = (),
        utc_template_path: str | Path | None = None,
        head_texture_columns: dict[str, str] | None = None,
        launcher_process_names: tuple[str, ...] = (),
        allow_overwrite: bool = False,
    ) -> HeadPackageBuildResult:
        """Build dynamic 2DA metadata and a portable, restorable package."""

        project = self.project
        if self._binary_export_result is None:
            raise HeadBuilderServiceError(
                "Export and read back the verified MDL/MDX before packaging"
            )
        if self._texture_result is None:
            raise HeadBuilderServiceError(
                "Rehydrate the saved texture/material contract before packaging"
            )
        if not project.game_install_dir:
            raise HeadBuilderServiceError(
                "Select and verify an installed KOTOR game before packaging"
            )
        verification = dict(
            project.extensions.get("game_install_verification") or {}
        )
        if not bool(verification.get("verified", False)):
            raise HeadBuilderServiceError(
                "The selected game must pass read-only installation verification"
            )
        body_resref = str(
            project.character_context.get("body_resref")
            or project.attachment_preview.get("body_resref")
            or dict(project.alignment.get("body_context") or {}).get(
                "body_resref"
            )
            or ""
        ).strip()
        if not body_resref:
            raise HeadBuilderServiceError(
                "Select the compatible preview body before packaging"
            )
        existing_patch = dict(
            project.package_state.get("game_record_patch") or {}
        )
        stable_appearance_label = str(
            appearance_label
            or existing_patch.get("appearance_label")
            or (
                f"GhostStudio_{project.output_head_resref}_"
                f"{project.project_id[:8]}"
            )
        )
        patch = HeadGameRecordPatch(
            game=project.game.value,
            output_head_resref=project.output_head_resref,
            texture_resref=(
                self._texture_result.output_policy.output_resref
            ),
            donor_head_resref=_project_snapshot(project).resref,
            body_resref=body_resref,
            appearance_donor_label=appearance_donor_label,
            appearance_label=stable_appearance_label,
            portrait_resref=portrait_resref,
            portrait_donor_resref=portrait_donor_resref,
            head_texture_columns=dict(head_texture_columns or {}),
        )
        game_root = Path(project.game_install_dir)
        try:
            heads_bytes = load_live_twoda(game_root, "heads")
            appearance_bytes = load_live_twoda(
                game_root,
                "appearance",
            )
            portraits_bytes = (
                load_live_twoda(game_root, "portraits")
                if patch.portrait_resref
                else None
            )
        except Exception as exc:
            raise HeadBuilderServiceError(str(exc)) from exc
        destination = Path(
            package_directory
            if package_directory is not None
            else (
                Path(project.output_project_dir)
                / f"{project.output_head_resref}_head_package"
            )
        )
        result = build_head_package(
            project_id=project.project_id,
            display_name=project.display_name,
            binary_export=self._binary_export_result,
            texture_asset=self._texture_result.asset,
            texture_policy=self._texture_result.output_policy,
            game_record_patch=patch,
            reference_heads_bytes=heads_bytes,
            reference_appearance_bytes=appearance_bytes,
            reference_portraits_bytes=portraits_bytes,
            destination=destination,
            utc_template_path=utc_template_path,
            portrait_files=portrait_files,
            launcher_process_names=launcher_process_names,
            allow_overwrite=allow_overwrite,
        )
        if not result.ok or result.reference_merge is None:
            raise HeadBuilderServiceError(
                result.error or "Head package build failed"
            )
        _reset_workflow_from(
            project,
            HeadBuilderStep.GAME_RECORDS_AND_PACKAGE,
        )
        project.package_state = {
            "schema": "ghostrigger.head_builder_package_state",
            "version": 1,
            "game_record_patch": patch.to_dict(),
            "package_directory": result.package_directory,
            "package_report_path": result.report_path,
            "install_plan_path": result.install_plan_path,
            "package_hashes": dict(result.hashes),
            "reference_merge": dict(result.reference_merge.report),
            "install_preview": {},
            "install_session": {},
            "restore": {},
        }
        package_report_hash = _file_sha256(result.report_path)
        project.put_resource(
            ResourceProvenance(
                resource_id="generated_head_package",
                resource_type="HEAD_PACKAGE",
                resref=project.output_head_resref,
                origin=ResourceOrigin.GENERATED,
                source_path=result.report_path,
                sha256=package_report_hash,
                stock=False,
                metadata={
                    "package_directory": result.package_directory,
                    "heads_row": result.reference_merge.heads_row,
                    "appearance_row": (
                        result.reference_merge.appearance_row
                    ),
                    "portraits_row": (
                        result.reference_merge.portraits_row
                    ),
                },
            )
        )
        evidence = EvidenceRecord(
            evidence_id=(
                f"head-package-{package_report_hash[:16].lower()}"
            ),
            check_id="head.package.dynamic_merge",
            label="Dynamic game records and portable package",
            level=EvidenceLevel.STRUCTURAL,
            outcome=EvidenceOutcome.PASS,
            message=(
                "heads.2da and appearance.2da were re-found by stable "
                "values, unrelated rows were preserved, and a reversible "
                "package with a TSLPatcher alternative was built."
            ),
            artifact_paths=[
                result.report_path,
                result.install_plan_path,
                result.patch_path,
            ],
            hashes={
                "package_report": package_report_hash,
                **{
                    key: value
                    for key, value in result.hashes.items()
                    if key in {
                        "additional/head-game-records.patch.json",
                        "additional/install-plan.json",
                        "tslpatchdata/changes.ini",
                    }
                },
            },
            metadata={
                "heads_row": result.reference_merge.heads_row,
                "appearance_row": (
                    result.reference_merge.appearance_row
                ),
                "portraits_row": result.reference_merge.portraits_row,
                "no_existing_row_modified": bool(
                    result.reference_merge.report.get(
                        "no_existing_row_modified"
                    )
                ),
            },
        )
        project.record_evidence(evidence)
        project.mark_step(
            HeadBuilderStep.GAME_RECORDS_AND_PACKAGE,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            StepStatus.READY,
        )
        project.set_current_step(HeadBuilderStep.SAFE_RETAIL_TEST)
        self._package_result = result
        self._install_preview = None
        self._install_result = None
        self._dirty = True
        return result

    def prepare_test_install(self) -> HeadInstallPreview:
        """Read the live tables and stage an exact, non-mutating install view."""

        project = self.project
        package_directory = str(
            project.package_state.get("package_directory") or ""
        )
        if not package_directory:
            raise HeadBuilderServiceError(
                "Build the Custom Head package before preparing a test install"
            )
        preview = self.package_installer.preview(
            package_directory,
            project.game_install_dir,
        )
        evidence = _install_preview_evidence(preview)
        project.record_evidence(evidence)
        project.package_state["install_preview"] = preview.to_dict()
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            (
                StepStatus.IN_PROGRESS
                if preview.ok
                else StepStatus.BLOCKED
            ),
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(HeadBuilderStep.SAFE_RETAIL_TEST)
        self._install_preview = preview if preview.ok else None
        self._install_result = None
        self._dirty = True
        if not preview.ok:
            raise HeadBuilderServiceError(preview.error)
        return preview

    def install_prepared_test(
        self,
        *,
        confirmed_preview_id: str,
    ) -> HeadInstallResult:
        """Install only the exact preview after a running-game guard."""

        project = self.project
        preview = self._install_preview
        if preview is None:
            saved = dict(
                project.package_state.get("install_preview") or {}
            )
            if saved:
                preview = HeadInstallPreview.from_dict(saved)
        if preview is None or not preview.ok:
            raise HeadBuilderServiceError(
                "Prepare a valid test-install preview before installation"
            )
        result = self.package_installer.install(
            preview,
            confirmed_preview_id=confirmed_preview_id,
        )
        evidence = _test_install_evidence(result)
        project.record_evidence(evidence)
        if result.ok:
            project.package_state["install_session"] = result.to_dict()
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            (
                StepStatus.IN_PROGRESS
                if result.ok
                else StepStatus.BLOCKED
            ),
            evidence_ids=[evidence.evidence_id],
        )
        self._install_result = result
        self._dirty = True
        if not result.ok:
            raise HeadBuilderServiceError(result.error)
        return result

    def restore_previous_test(
        self,
        session_manifest: str | Path | None = None,
    ) -> HeadInstallResult:
        """Restore verified pre-test bytes without overwriting later changes."""

        project = self.project
        saved_session = dict(
            project.package_state.get("install_session") or {}
        )
        manifest = str(
            session_manifest
            if session_manifest is not None
            else saved_session.get("session_manifest")
            or ""
        )
        if not manifest:
            raise HeadBuilderServiceError(
                "No installed Custom Head test is available to restore"
            )
        result = self.package_installer.restore(manifest)
        evidence = _test_restore_evidence(result)
        project.record_evidence(evidence)
        project.package_state["restore"] = result.to_dict()
        self._install_result = result
        self._dirty = True
        if not result.ok:
            raise HeadBuilderServiceError(result.error)
        return result

    def confirm_retail_test_pass(
        self,
        *,
        observer_session: str,
        checklist: dict[str, bool],
        artifact_paths: tuple[str | Path, ...],
        confirmed_by_user: bool,
    ) -> EvidenceRecord:
        """Record the external retail pass only with explicit observer proof."""

        project = self.project
        required = {
            "idle",
            "movement",
            "combat",
            "dialogue",
            "save_load",
            "warp",
            "attachment",
            "texture",
        }
        completed = {
            str(key)
            for key, value in checklist.items()
            if bool(value)
        }
        missing = sorted(required - completed)
        if missing:
            raise HeadBuilderServiceError(
                "Retail checklist is incomplete: " + ", ".join(missing)
            )
        if not confirmed_by_user:
            raise HeadBuilderServiceError(
                "Retail pass requires explicit user confirmation"
            )
        observer = str(observer_session or "").strip()
        if not observer:
            raise HeadBuilderServiceError(
                "Retail pass requires an observer session identifier"
            )
        paths = [
            Path(value).expanduser().resolve()
            for value in artifact_paths
        ]
        if not paths or any(not path.is_file() for path in paths):
            raise HeadBuilderServiceError(
                "Retail pass requires one or more saved observer artifacts"
            )
        hashes = {
            path.name: _file_sha256(path)
            for path in paths
        }
        install_session = dict(
            project.package_state.get("install_session") or {}
        )
        if not bool(install_session.get("ok", False)):
            raise HeadBuilderServiceError(
                "Retail pass requires the recorded transactional test install"
            )
        evidence = EvidenceRecord(
            evidence_id=(
                f"head-retail-{_mapping_sha256(hashes)[:16]}"
            ),
            check_id="head.retail.observed_acceptance",
            label="Observed KOTOR retail Custom Head acceptance",
            level=EvidenceLevel.RETAIL_OBSERVED,
            outcome=EvidenceOutcome.PASS,
            message=(
                "The user explicitly confirmed attachment and texture "
                "through idle, movement, combat, dialogue, save/load, and warp."
            ),
            artifact_paths=[str(path) for path in paths],
            hashes=hashes,
            observer_session=observer,
            confirmed_by_user=True,
            metadata={
                "checklist": {
                    key: bool(checklist.get(key, False))
                    for key in sorted(required)
                },
                "install_session_manifest": str(
                    install_session.get("session_manifest") or ""
                ),
            },
        )
        project.record_evidence(evidence)
        project.retail_test = {
            "schema": "ghostrigger.head_builder_retail_test",
            "version": 1,
            "passed": True,
            "observer_session": observer,
            "confirmed_by_user": True,
            "checklist": dict(evidence.metadata["checklist"]),
            "artifact_paths": [str(path) for path in paths],
            "hashes": hashes,
            "evidence_id": evidence.evidence_id,
        }
        prior_ids = list(
            project.workflow_steps[
                HeadBuilderStep.SAFE_RETAIL_TEST
            ].evidence_ids
        )
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            StepStatus.COMPLETE,
            evidence_ids=prior_ids + [evidence.evidence_id],
        )
        self._dirty = True
        return evidence

    def search_donors(
        self,
        text: str = "",
        *,
        limit: int = 250,
        include_nonstandard: bool = False,
    ) -> list[HeadDonorCandidate]:
        project = self.project
        return self.donor_catalog.search(
            game=project.game.value,
            resource_view=project.resource_view,
            text=text,
            limit=limit,
            head_like_only=not include_nonstandard,
        )

    def select_donor(
        self,
        resref: str,
        *,
        compatibility: dict[str, Any] | None = None,
        raise_on_rejection: bool = True,
    ) -> HeadDonorSelection:
        project = self.project
        bundle = self.donor_catalog.resolve(
            game=project.game.value,
            resref=resref,
            resource_view=project.resource_view,
        )
        model = self.model_loader(
            bundle.mdl_bytes,
            bundle.mdx_bytes,
            project.game.value,
        )
        if model is None:
            raise HeadBuilderServiceError(
                f"Ghost Studio could not decode donor {project.game.value}:{resref}"
            )
        snapshot = capture_head_donor_snapshot(
            model,
            game=project.game.value,
            resref=bundle.candidate.resref,
            resource_view=project.resource_view.value,
            mdl_sha256=bundle.mdl_sha256,
            mdx_sha256=bundle.mdx_sha256,
            provenance=bundle.provenance_dict(),
            compatibility=compatibility,
        )
        report = validate_head_donor_snapshot(snapshot)
        selection = HeadDonorSelection(
            candidate=bundle.candidate,
            snapshot=snapshot,
            eligibility=report,
            model=model,
        )
        evidence = _donor_evidence(snapshot, report)
        had_accepted_contract = isinstance(
            dict(project.donor_contract or {}).get("snapshot"),
            dict,
        )
        project.record_evidence(evidence)
        if not report.eligible:
            if not had_accepted_contract:
                project.mark_step(
                    HeadBuilderStep.SELECT_NATIVE_DONOR,
                    StepStatus.BLOCKED,
                    evidence_ids=[evidence.evidence_id],
                )
            self._dirty = True
            if raise_on_rejection:
                raise HeadBuilderDonorRejectedError(
                    f"Resource {project.game.value}:{resref} is not an "
                    "eligible modular-head donor",
                    report=report,
                )
            return selection

        project.put_resource(
            _resource_provenance(bundle, restype="MDL")
        )
        project.put_resource(
            _resource_provenance(bundle, restype="MDX")
        )
        project.donor_contract = {
            "snapshot": snapshot.to_dict(),
            "eligibility": report.to_dict(),
        }
        project.appearance_customization = {}
        _reset_workflow_from(
            project,
            HeadBuilderStep.ALIGN_NECK_AND_HOOK,
        )
        project.mark_step(
            HeadBuilderStep.SELECT_NATIVE_DONOR,
            StepStatus.COMPLETE,
            evidence_ids=[evidence.evidence_id],
        )
        project.set_current_step(HeadBuilderStep.ALIGN_NECK_AND_HOOK)
        self._selected_model = model
        self._alignment_result = None
        self._transplant_result = None
        self._component_result = None
        self._texture_result = None
        self._preview_result = None
        self._preflight_report = None
        self._binary_export_result = None
        self._dirty = True
        return selection

    def rehydrate_selected_donor(self) -> HeadDonorSelection:
        """Reload a saved donor and prove its source bytes did not drift."""

        project = self.project
        snapshot = _project_snapshot(project)
        bundle = self.donor_catalog.resolve(
            game=snapshot.game,
            resref=snapshot.resref,
            resource_view=snapshot.resource_view,
        )
        if (
            bundle.mdl_sha256.lower() != snapshot.mdl_sha256.lower()
            or bundle.mdx_sha256.lower() != snapshot.mdx_sha256.lower()
        ):
            raise HeadBuilderDonorChangedError(
                "The selected donor bytes no longer match the saved project; "
                "reselect the donor explicitly before continuing."
            )
        model = self.model_loader(
            bundle.mdl_bytes,
            bundle.mdx_bytes,
            snapshot.game,
        )
        if model is None:
            raise HeadBuilderServiceError(
                f"Ghost Studio could not decode saved donor "
                f"{snapshot.game}:{snapshot.resref}"
            )
        current = capture_head_donor_snapshot(
            model,
            game=snapshot.game,
            resref=snapshot.resref,
            resource_view=snapshot.resource_view,
            mdl_sha256=bundle.mdl_sha256,
            mdx_sha256=bundle.mdx_sha256,
            provenance=bundle.provenance_dict(),
            compatibility=snapshot.compatibility,
        )
        if current.structural_sha256 != snapshot.structural_sha256:
            raise HeadBuilderDonorChangedError(
                "The selected donor's decoded structural contract no longer "
                "matches the saved project."
            )
        report = validate_head_donor_snapshot(current)
        if not report.eligible:
            raise HeadBuilderDonorRejectedError(
                "The saved donor no longer passes current eligibility rules",
                report=report,
            )
        self._selected_model = model
        return HeadDonorSelection(
            candidate=bundle.candidate,
            snapshot=current,
            eligibility=report,
            model=model,
        )

    def compare_donor_contract(
        self,
        model: Any | None = None,
        *,
        output_resref: str | None = None,
    ) -> HeadDonorContractDiff:
        project = self.project
        snapshot = _project_snapshot(project)
        candidate = (
            model
            if model is not None
            else (
                self._texture_result.model
                if self._texture_result is not None
                else (
                    self._component_result.model
                    if self._component_result is not None
                    else (
                        self._transplant_result.model
                        if self._transplant_result is not None
                        else self._selected_model
                    )
                )
            )
        )
        if candidate is None:
            raise HeadBuilderServiceError(
                "Reload the saved donor before comparing its contract"
            )
        return compare_head_donor_contract(
            snapshot,
            candidate,
            output_resref=(
                project.output_head_resref
                if output_resref is None
                else output_resref
            ),
        )

    def _default_install_verifier(self, game: str, install_dir: str) -> Any:
        from src.core.resources.head_game_install import (
            verify_head_game_install,
        )

        return verify_head_game_install(
            game=game,
            install_dir=install_dir,
            donor_catalog=self.donor_catalog,
        )


def _load_model(mdl_bytes: bytes, mdx_bytes: bytes, game: str) -> Any:
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.geometry.model_data import GameVersion

    version = GameVersion.K2 if str(game).upper() == "K2" else GameVersion.K1
    return load_model_from_bytes(
        mdl_bytes,
        mdx_bytes,
        game_version=version,
    )


def _import_head_art(path: str | Path, **kwargs: Any) -> tuple[
    HeadArtDocument,
    HeadArtValidationReport,
]:
    from src.io.head_art_importer import import_head_art

    return import_head_art(path, **kwargs)


def _solve_head_alignment(
    request: HeadAlignmentRequest,
) -> HeadAlignmentResult:
    from src.math.head_alignment import solve_headhook_alignment

    return solve_headhook_alignment(request)


def valid_head_output_resref(value: str) -> bool:
    """Return whether a head output identity fits Odyssey's ResRef field."""

    return bool(_HEAD_RESREF_RE.fullmatch(str(value or "").strip()))


def _install_hashes(verification: Any) -> dict[str, str]:
    values = {
        "install_fingerprint_sha256": getattr(
            verification,
            "fingerprint_sha256",
            "",
        ),
        "executable_sha256": getattr(
            verification,
            "executable_sha256",
            "",
        ),
        "chitin_key_sha256": getattr(
            verification,
            "chitin_key_sha256",
            "",
        ),
        "probe_mdl_sha256": getattr(
            verification,
            "resource_probe_mdl_sha256",
            "",
        ),
        "probe_mdx_sha256": getattr(
            verification,
            "resource_probe_mdx_sha256",
            "",
        ),
    }
    return {
        key: str(value)
        for key, value in values.items()
        if str(value or "")
    }


def _project_snapshot(project: HeadBuilderProject) -> HeadDonorSnapshot:
    payload = dict(project.donor_contract or {})
    snapshot_payload = payload.get("snapshot")
    if not isinstance(snapshot_payload, dict):
        raise HeadBuilderServiceError(
            "The active project has no accepted donor contract"
        )
    return HeadDonorSnapshot.from_dict(snapshot_payload)


def _project_art_document(project: HeadBuilderProject) -> dict[str, Any]:
    payload = dict(project.import_art or {})
    document = payload.get("document")
    if not isinstance(document, dict):
        raise HeadBuilderServiceError(
            "The active project has no accepted custom-art contract"
        )
    return dict(document)


def _art_evidence(
    document: HeadArtDocument,
    report: HeadArtValidationReport,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=(
            f"head-art-{document.source_sha256[:12]}-"
            f"{document.structural_sha256[:12]}"
        ),
        check_id="head.art.import_topology",
        label=f"Custom head art import: {Path(document.source_path).name}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if report.accepted
            else EvidenceOutcome.FAIL
        ),
        message=(
            "Custom art decoded deterministically and passed blocking "
            "topology gates."
            if report.accepted
            else "Custom art contains blocking channel or topology defects."
        ),
        hashes={
            "source_sha256": document.source_sha256,
            "structural_sha256": document.structural_sha256,
        },
        metadata={
            "document": document.project_facts(),
            "validation": report.to_dict(),
        },
    )


def _alignment_evidence(
    *,
    document: HeadArtDocument,
    donor: HeadDonorSnapshot,
    result: HeadAlignmentResult,
    body_resref: str,
    headhook_node_path: str,
    maximum_rms_error: float,
    within_tolerance: bool,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"head-align-{result.transform_sha256[:16]}",
        check_id="head.alignment.headhook_bind",
        label=f"Headhook bind alignment: {body_resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if within_tolerance
            else EvidenceOutcome.WARNING
        ),
        message=(
            "Custom art was solved through body bind into headhook-local "
            "space without reflection."
            if within_tolerance
            else "The named-space solve is valid, but its RMS anchor error "
            "exceeds the configured tolerance."
        ),
        hashes={
            "art_structural_sha256": document.structural_sha256,
            "donor_structural_sha256": donor.structural_sha256,
            "alignment_transform_sha256": result.transform_sha256,
        },
        metadata={
            "body_resref": body_resref,
            "headhook_node_path": headhook_node_path,
            "maximum_rms_error": maximum_rms_error,
            "within_tolerance": within_tolerance,
            "result": result.to_dict(),
        },
    )


def _transplant_evidence(
    snapshot: HeadDonorSnapshot,
    result: HeadGeometryTransplantResult,
) -> EvidenceRecord:
    report = result.report
    return EvidenceRecord(
        evidence_id=f"head-transplant-{report.payload_sha256[:16]}",
        check_id="head.geometry_skin.donor_preserving_transplant",
        label=f"Donor-preserving head payload: {snapshot.game}:{snapshot.resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if report.accepted
            else EvidenceOutcome.FAIL
        ),
        message=(
            "Custom geometry and skin rows replaced only the donor's mutable "
            "render payload; the native DAG, palette, bind arrays, hooks, "
            "raw bounds, and inheritance contract remained unchanged."
            if report.accepted
            else "The candidate did not preserve every immutable donor field."
        ),
        hashes={
            "donor_structural_sha256": snapshot.structural_sha256,
            "geometry_sha256": report.geometry_sha256,
            "weight_rows_sha256": report.final_weight_rows_sha256,
            "payload_sha256": report.payload_sha256,
        },
        metadata={"report": report.to_dict()},
    )


def _texture_material_evidence(
    result: HeadTextureMaterialResult,
) -> EvidenceRecord:
    report = result.report
    has_warnings = bool(report.uv_warnings or report.texture_warnings)
    return EvidenceRecord(
        evidence_id=(
            f"head-material-{report.material_payload_sha256[:16]}"
        ),
        check_id="head.uv_texture_material.explicit_orientation",
        label=f"Head UV and texture policy: {report.texture_resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.WARNING
            if report.accepted and has_warnings
            else (
                EvidenceOutcome.PASS
                if report.accepted
                else EvidenceOutcome.FAIL
            )
        ),
        message=(
            "Preview and serialized UV orientation match; texture source, "
            "TXI policy, package names, and donor-safe material assignment "
            "were fingerprinted."
            if report.accepted
            else "UV or texture policy failed its structural contract."
        ),
        hashes={
            "source_texture_sha256": report.source_texture_sha256,
            "source_decoded_rgba_sha256": (
                report.source_decoded_rgba_sha256
            ),
            "serialized_uv_sha256": report.serialized_uv_sha256,
            "material_payload_sha256": report.material_payload_sha256,
        },
        metadata={"report": report.to_dict()},
    )


def _attachment_preview_evidence(
    result: HeadAttachmentPreviewResult,
    donor_diff: HeadDonorContractDiff,
) -> EvidenceRecord:
    report = result.report
    has_warnings = bool(report.warnings)
    return EvidenceRecord(
        evidence_id=(
            f"head-preview-{report.contract_sha256[:16]}"
        ),
        check_id="head.attachment_animation.exact_headhook_inheritance",
        label=(
            f"Head attachment and inherited animation: "
            f"{report.body_resref} + {report.head_resref}"
        ),
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.WARNING
            if report.accepted and has_warnings
            else (
                EvidenceOutcome.PASS
                if report.accepted
                and donor_diff.structurally_compatible
                else EvidenceOutcome.FAIL
            )
        ),
        message=(
            "A disposable preview copy attached at the body's exact headhook; "
            "facial clips resolved through the unchanged head supermodel "
            "chain without copying animations into the head."
            if report.accepted
            else "Attachment or inherited-animation preview was blocked."
        ),
        hashes={
            "attachment_preview_sha256": report.contract_sha256,
        },
        metadata={
            "report": _attachment_preview_project_report(result),
            "donor_contract_diff": donor_diff.to_dict(),
        },
    )


def _optional_physics_skipped_evidence(
    preview_sha256: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"head-physics-skipped-{preview_sha256[:12]}",
        check_id="head.optional_physics.not_requested",
        label="Optional hair/accessory physics not requested",
        level=EvidenceLevel.STRUCTURAL,
        outcome=EvidenceOutcome.PASS,
        message=(
            "The project explicitly excludes optional hair/accessory physics; "
            "no dangly or cloth data was authored."
        ),
        hashes={"attachment_preview_sha256": preview_sha256},
        metadata={"enabled": False, "status": "not_requested"},
    )


def _binary_preflight_evidence(
    report: HeadBuilderPreflightReport,
) -> EvidenceRecord:
    inspection = (
        report.binary_build.inspection
        if report.binary_build is not None
        else None
    )
    return EvidenceRecord(
        evidence_id=f"head-preflight-{report.report_sha256[:16]}",
        check_id="head.binary_preflight.writer_reload",
        label=f"Head binary preflight: {report.output_resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.FAIL
            if report.blocking_issues
            else (
                EvidenceOutcome.WARNING
                if report.warning_issues
                else EvidenceOutcome.PASS
            )
        ),
        message=(
            "In-memory checks, raw MDL/MDX headers, donor contract, and "
            "loader readback passed; all warnings were explicitly acknowledged."
            if report.export_allowed
            else (
                "Structural errors block MDL/MDX export."
                if report.blocking_issues
                else "Warnings require explicit acknowledgment before export."
            )
        ),
        hashes={
            "preflight_sha256": report.report_sha256,
            **(
                {
                    "mdl_sha256": inspection.mdl_sha256,
                    "mdx_sha256": inspection.mdx_sha256,
                    "binary_inspection_sha256": (
                        inspection.inspection_sha256
                    ),
                }
                if inspection is not None
                else {}
            ),
        },
        metadata={"report": report.to_dict()},
    )


def _binary_export_evidence(
    result: HeadBinaryExportResult,
) -> EvidenceRecord:
    inspection = result.inspection
    return EvidenceRecord(
        evidence_id=(
            f"head-binary-export-{inspection.inspection_sha256[:16]}"
        ),
        check_id="head.binary_export.atomic_publish",
        label=f"Reload-verified head export: {inspection.output_resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if inspection.accepted
            else EvidenceOutcome.FAIL
        ),
        message=(
            "Verified MDL/MDX bytes and their manifest were atomically "
            "published outside the game installation."
        ),
        artifact_paths=[
            result.mdl_path,
            result.mdx_path,
            result.manifest_path,
        ],
        hashes={
            "mdl_sha256": inspection.mdl_sha256,
            "mdx_sha256": inspection.mdx_sha256,
            "binary_inspection_sha256": inspection.inspection_sha256,
        },
        metadata={"inspection": inspection.to_dict()},
    )


def _install_preview_evidence(
    preview: HeadInstallPreview,
) -> EvidenceRecord:
    preview_hash = _mapping_sha256(preview.to_dict())
    return EvidenceRecord(
        evidence_id=f"head-install-preview-{preview_hash[:16]}",
        check_id="head.install.read_only_preview",
        label="Read-only Custom Head test-install preview",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if preview.ok
            else EvidenceOutcome.FAIL
        ),
        message=(
            "Live 2DA rows and every Override destination were resolved "
            "without changing the game."
            if preview.ok
            else (
                "The read-only test-install preview was blocked: "
                f"{preview.error}"
            )
        ),
        artifact_paths=(
            [preview.candidate_directory]
            if preview.ok and preview.candidate_directory
            else []
        ),
        hashes={"preview": preview_hash},
        metadata={
            "preview_id": preview.preview_id,
            "heads_row": preview.heads_row,
            "appearance_row": preview.appearance_row,
            "portraits_row": preview.portraits_row,
            "files": [dict(value) for value in preview.files],
            "executable_edits": False,
            "cache_actions": [],
        },
    )


def _test_install_evidence(
    result: HeadInstallResult,
) -> EvidenceRecord:
    manifest_path = Path(result.session_manifest)
    hashes = (
        {"install_session": _file_sha256(manifest_path)}
        if result.ok and manifest_path.is_file()
        else {}
    )
    identity = _mapping_sha256(
        {
            "ok": result.ok,
            "manifest": result.session_manifest,
            "hashes": hashes,
            "error": result.error,
        }
    )
    return EvidenceRecord(
        evidence_id=f"head-test-install-{identity[:16]}",
        check_id="head.install.transaction",
        label="Transactional Custom Head test installation",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if result.ok
            else EvidenceOutcome.FAIL
        ),
        message=(
            "The exact preview was installed with verified timestamped "
            "backups and installed hashes."
            if result.ok
            else f"Test installation was stopped or rolled back: {result.error}"
        ),
        artifact_paths=(
            [result.session_manifest]
            if result.session_manifest
            else []
        ),
        hashes=hashes,
        metadata={
            "installed_files": list(result.installed_files),
            "messages": list(result.messages),
        },
    )


def _test_restore_evidence(
    result: HeadInstallResult,
) -> EvidenceRecord:
    manifest_path = Path(result.session_manifest)
    hashes = (
        {"restored_session": _file_sha256(manifest_path)}
        if result.ok and manifest_path.is_file()
        else {}
    )
    identity = _mapping_sha256(
        {
            "ok": result.ok,
            "manifest": result.session_manifest,
            "hashes": hashes,
            "error": result.error,
        }
    )
    return EvidenceRecord(
        evidence_id=f"head-test-restore-{identity[:16]}",
        check_id="head.install.restore",
        label="Restore Previous Custom Head test",
        level=EvidenceLevel.STRUCTURAL,
        outcome=(
            EvidenceOutcome.PASS
            if result.ok
            else EvidenceOutcome.FAIL
        ),
        message=(
            "Verified pre-test files were restored without overwriting "
            "newer work."
            if result.ok
            else f"Restore was blocked: {result.error}"
        ),
        artifact_paths=(
            [result.session_manifest]
            if result.session_manifest
            else []
        ),
        hashes=hashes,
        metadata={
            "restored_files": list(result.restored_files),
            "messages": list(result.messages),
        },
    )


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mapping_sha256(value: dict[str, Any]) -> str:
    import json

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _attachment_preview_project_report(
    result: HeadAttachmentPreviewResult,
) -> dict[str, Any]:
    """Return durable preview facts without duplicating every track target."""

    report = result.report
    payload = report.to_dict()
    rows = list(payload.pop("effective_animations", []))
    selected = {
        name.casefold()
        for name in report.selected_animation_names
    }
    payload["effective_animation_count"] = len(rows)
    payload["effective_animation_names"] = [
        str(row.get("name") or "") for row in rows
    ]
    payload["facial_animation_count"] = len(
        report.facial_animation_names
    )
    payload["selected_animations"] = [
        row
        for row in rows
        if str(row.get("name") or "").casefold() in selected
    ]
    return payload


def _preview_resource_rows(
    bundles: dict[str, HeadDonorResourceBundle],
    *,
    body_resref: str,
) -> list[dict[str, Any]]:
    body_key = str(body_resref or "").casefold()
    rows: list[dict[str, Any]] = []
    for key, bundle in bundles.items():
        rows.append(
            {
                "role": "body" if key == body_key else "supermodel",
                "resref": bundle.candidate.resref,
                "mdl_sha256": bundle.mdl_sha256,
                "mdx_sha256": bundle.mdx_sha256,
                "resource_view": bundle.candidate.resource_view.value,
                "stock": bundle.candidate.stock,
            }
        )
    return rows


def _transplant_payload_node(
    result: Any,
) -> Any:
    nodes = list(result.model.all_nodes())
    ordinal = result.report.mutable_node_ordinal
    if ordinal < 0 or ordinal >= len(nodes):
        raise HeadBuilderServiceError(
            "The active donor payload node is unavailable"
        )
    return nodes[ordinal]


def _reset_workflow_from(
    project: HeadBuilderProject,
    first_step: HeadBuilderStep,
) -> None:
    """Invalidate dependent state without discarding upstream evidence."""

    first = HeadBuilderStep.coerce(first_step)
    for step in HeadBuilderStep:
        if int(step) >= int(first):
            project.mark_step(step, StepStatus.NOT_STARTED)
    if int(first) <= int(HeadBuilderStep.ALIGN_NECK_AND_HOOK):
        project.alignment = {}
    if int(first) <= int(HeadBuilderStep.REPLACE_GEOMETRY_AND_SKIN):
        project.skin_transfer = {}
    if int(first) <= int(HeadBuilderStep.UV_TEXTURES_AND_MATERIALS):
        project.texture_materials = {}
    if int(first) <= int(
        HeadBuilderStep.ATTACHMENT_AND_ANIMATION_PREVIEW
    ):
        project.attachment_preview = {}
        project.acknowledged_warnings = []
        for resource_id in tuple(project.resources):
            if resource_id.startswith(
                ("preview_body_", "preview_supermodel_")
            ):
                project.resources.pop(resource_id, None)
    if int(first) <= int(HeadBuilderStep.OPTIONAL_HAIR_PHYSICS):
        project.physics = {}
    if int(first) <= int(HeadBuilderStep.BINARY_PREFLIGHT):
        project.export_plan = {}
        for resource_id in (
            "generated_head_mdl",
            "generated_head_mdx",
        ):
            project.resources.pop(resource_id, None)
    if int(first) <= int(HeadBuilderStep.GAME_RECORDS_AND_PACKAGE):
        project.package_state = {}
    if int(first) <= int(HeadBuilderStep.SAFE_RETAIL_TEST):
        project.retail_test = {}


def _validate_saved_neck_weight_floor(
    project: HeadBuilderProject,
    result: HeadGeometryTransplantResult,
) -> None:
    payload = dict(project.skin_transfer or {})
    settings = dict(payload.get("settings") or {})
    neck_ids = tuple(
        str(value)
        for value in list(settings.get("neck_vertex_ids") or [])
    )
    minimum = float(settings.get("minimum_neck_weight", 0.05))
    snapshot = _project_snapshot(project)
    wanted = snapshot.attachment_target_name.casefold()
    palette = tuple(result.report.palette_names)
    matches = [
        index
        for index, name in enumerate(palette)
        if str(name).casefold() == wanted
    ]
    if len(matches) != 1:
        raise HeadBuilderServiceError(
            "The immutable donor palette lost its attachment target"
        )
    neck_slot = matches[0]
    vertex_by_id = {
        vertex_id: index
        for index, vertex_id in enumerate(result.vertex_ids)
    }
    for vertex_id in neck_ids:
        index = vertex_by_id.get(vertex_id)
        if index is None:
            raise HeadBuilderServiceError(
                f"Saved neck vertex is absent from the rebuilt payload: {vertex_id}"
            )
        weight = sum(
            influence.weight
            for influence in result.rows[index].influences
            if influence.palette_slot == neck_slot
        )
        if weight + 1.0e-7 < minimum:
            raise HeadBuilderServiceError(
                f"Manual edit would reduce {vertex_id}'s "
                f"{snapshot.attachment_target_name} weight below {minimum}"
            )


def _donor_evidence(
    snapshot: HeadDonorSnapshot,
    report: HeadDonorEligibilityReport,
) -> EvidenceRecord:
    outcome = (
        EvidenceOutcome.PASS
        if report.eligible
        else EvidenceOutcome.FAIL
    )
    return EvidenceRecord(
        evidence_id=(
            f"head-donor-{snapshot.game.lower()}-"
            f"{snapshot.resref.lower()}-{snapshot.mdl_sha256[:12]}"
        ),
        check_id="head.donor.eligibility",
        label=f"Native donor eligibility: {snapshot.game}:{snapshot.resref}",
        level=EvidenceLevel.STRUCTURAL,
        outcome=outcome,
        message=(
            "Native donor DAG, attachment, inheritance, bounds, palette, "
            "bind rows, and source provenance passed."
            if report.eligible
            else "The selected resource failed one or more native donor gates."
        ),
        hashes={
            "mdl_sha256": snapshot.mdl_sha256,
            "mdx_sha256": snapshot.mdx_sha256,
            "structural_sha256": snapshot.structural_sha256,
        },
        metadata={"eligibility": report.to_dict()},
    )


def _resource_provenance(
    bundle: HeadDonorResourceBundle,
    *,
    restype: str,
    resource_id: str | None = None,
) -> ResourceProvenance:
    normalized = restype.upper()
    record = (
        bundle.candidate.mdl_record
        if normalized == "MDL"
        else bundle.candidate.mdx_record
    )
    if record is None:
        raise HeadBuilderServiceError(
            f"Accepted donor is missing its {normalized} record"
        )
    layer = str(record.layer or "").lower()
    origin = {
        "base": ResourceOrigin.CHITIN_BIF,
        "module": ResourceOrigin.MODULE,
        "override": ResourceOrigin.OVERRIDE,
    }.get(layer, ResourceOrigin.PROJECT_FILE)
    digest = (
        bundle.mdl_sha256
        if normalized == "MDL"
        else bundle.mdx_sha256
    )
    return ResourceProvenance(
        resource_id=(
            str(resource_id)
            if resource_id is not None
            else f"native_donor_{normalized.lower()}"
        ),
        resource_type=normalized,
        resref=bundle.candidate.resref,
        origin=origin,
        source_path=str(record.source_path or ""),
        container=str(record.source or ""),
        sha256=digest,
        stock=bundle.candidate.stock,
        metadata={
            "address": record.address.to_dict(),
            "resource_view": bundle.candidate.resource_view.value,
            "priority": record.priority,
            "warnings": list(bundle.candidate.warnings),
        },
    )


__all__ = [
    "HeadArtSelection",
    "HeadComponentSourceSelection",
    "HeadBuilderArtChangedError",
    "HeadBuilderArtRejectedError",
    "HeadBuilderComponentRejectedError",
    "HeadBuilderDonorChangedError",
    "HeadBuilderDonorRejectedError",
    "HeadBuilderNoProjectError",
    "HeadBuilderService",
    "HeadBuilderServiceError",
    "HeadDonorSelection",
    "HeadDonorCatalogPort",
    "HeadAlignmentSolver",
    "HeadArtImporter",
    "HeadGeometryTransplantResult",
    "HeadTextureMaterialResult",
    "HeadProjectRepositoryPort",
    "valid_head_output_resref",
]
