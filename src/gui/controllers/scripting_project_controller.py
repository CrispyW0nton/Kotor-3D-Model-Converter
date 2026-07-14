"""Qt orchestration for Scripting Suite projects, history, and packaging.

The presentation pages emit intent only.  This controller translates that
intent into calls to the Qt-free project and packaging services, then publishes
plain dictionaries back to the pages.  It deliberately keeps global resources
such as ``dialog.tlk`` out of module archives and Override stages; those require
a separate, transactional game-root installer.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from PySide6 import QtCore, QtWidgets

from src.core.scripting.packaging import (
    NarrativePackageIssue,
    NarrativePackagingService,
    PackageResource,
)
from src.core.scripting.project import (
    LegacyNarrativeHistoryStore,
    NarrativeAssetDependency,
    NarrativeExportHistoryStore,
    NarrativeProject,
    NarrativeProjectService,
    NarrativeRevisionStore,
    RecentNarrativeProjectStore,
)


log = logging.getLogger(__name__)

_GLOBAL_INSTALL_TYPES = {"tlk"}


@dataclass(frozen=True)
class ProjectResourceSnapshot:
    """One in-memory workbench resource ready for an explicit project save."""

    resref: str
    restype: str
    data: bytes
    role: str = "runtime"
    game: str = ""
    dependencies: tuple[NarrativeAssetDependency, ...] = ()
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class _PackageEntry:
    resource: PackageResource
    role: str
    source_path: str = ""


def _issue_row(issue: object) -> dict[str, Any]:
    if isinstance(issue, Mapping):
        return dict(issue)
    return {
        "severity": str(getattr(issue, "severity", "warning")),
        "code": str(getattr(issue, "code", "")),
        "message": str(getattr(issue, "message", issue)),
        "resource": str(getattr(issue, "resource", "") or getattr(issue, "asset_id", "")),
        "asset_id": str(getattr(issue, "asset_id", "")),
    }


def _normalise_snapshot(value: object) -> ProjectResourceSnapshot:
    if isinstance(value, ProjectResourceSnapshot):
        return value
    if isinstance(value, Mapping):
        dependencies = tuple(
            row if isinstance(row, NarrativeAssetDependency) else NarrativeAssetDependency.from_dict(dict(row))
            for row in tuple(value.get("dependencies", ()) or ())
        )
        return ProjectResourceSnapshot(
            str(value.get("resref") or ""),
            str(value.get("restype") or ""),
            bytes(value.get("data") or b""),
            str(value.get("role") or "runtime"),
            str(value.get("game") or ""),
            dependencies,
            dict(value.get("metadata", {}) or {}),
        )
    row = tuple(value)  # type: ignore[arg-type]
    if len(row) < 3:
        raise ValueError("Project resource snapshots require resref, type, and bytes.")
    return ProjectResourceSnapshot(
        str(row[0]),
        str(row[1]),
        bytes(row[2] or b""),
        str(row[3] if len(row) > 3 else "runtime"),
        str(row[4] if len(row) > 4 else ""),
    )


class ScriptingProjectController(QtCore.QObject):
    """Own the open narrative project and safe distribution workflow."""

    projectChanged = QtCore.Signal(object)
    packageResourcesChanged = QtCore.Signal(object)
    assetActivationRequested = QtCore.Signal(str, object)
    globalTlkResultChanged = QtCore.Signal(object)
    legacyQuestOpened = QtCore.Signal(object)
    statusChanged = QtCore.Signal(str)
    operationFailed = QtCore.Signal(str)

    def __init__(
        self,
        window: Any,
        *,
        recent_store_path: str | Path | None = None,
        snapshot_provider: Callable[[], Iterable[object]] | None = None,
        asset_activator: Callable[[str, Mapping[str, Any]], object] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.project: NarrativeProject | None = None
        self.snapshot_provider = snapshot_provider or (lambda: ())
        self.asset_activator = asset_activator
        registry = Path(recent_store_path or (Path.cwd() / "Saved" / "ScriptingStudio" / "recent-projects.json"))
        self.recent_store = RecentNarrativeProjectStore(registry)
        self._loose_resources: "OrderedDict[tuple[str, str], _PackageEntry]" = OrderedDict()
        self._last_stage_path = ""
        self.project_page = self._page("project_history_page", "project_page")
        self.package_page = self._page("package_override_page", "package_page")
        self._bind()
        self._present_all()

    def _page(self, *names: str) -> Any | None:
        for name in names:
            value = getattr(self.window, name, None)
            if value is not None:
                return value
        return None

    def _bind(self) -> None:
        project_bindings = (
            ("newProjectRequested", self.create_project),
            ("openProjectRequested", self.open_project),
            ("saveProjectRequested", self.save_project),
            ("importAssetsRequested", self.import_assets),
            ("refreshInventoryRequested", self.refresh_inventory),
            ("validateProjectRequested", self.validate_project),
            ("assetActivated", self.activate_asset),
            ("createRevisionRequested", self.create_revision),
            ("recoverRevisionRequested", self.recover_revision),
            ("recoverAssetRevisionRequested", self.recover_revision_asset),
            ("recoverLegacyHistoryRequested", self.recover_legacy_history),
            ("openLegacyQuestRequested", self.open_legacy_quest_history),
            ("recentProjectActivated", self.open_project),
            ("forgetRecentRequested", self.forget_recent),
        )
        package_bindings = (
            ("addPackageFilesRequested", self.add_package_files),
            ("packageOutputBrowseRequested", self.browse_package_output),
            ("packageBuildRequested", self.build_package),
            ("stageOutputBrowseRequested", self.browse_stage_output),
            ("stageOverrideRequested", self.stage_override),
            ("stageInspectRequested", self.inspect_stage),
            ("gameRootBrowseRequested", self.browse_game_root),
            ("installOverrideRequested", self.install_override),
            ("packageResourceActivated", self.activate_package_resource),
            ("readinessRefreshRequested", self.refresh_package_readiness),
            ("installGlobalTlkRequested", self.install_global_tlk),
            ("restoreGlobalTlkRequested", self.restore_global_tlk),
        )
        for page, bindings in ((self.project_page, project_bindings), (self.package_page, package_bindings)):
            if page is None:
                continue
            for signal_name, slot in bindings:
                signal = getattr(page, signal_name, None)
                if signal is not None:
                    signal.connect(slot)

    def _dialog_parent(self) -> QtWidgets.QWidget | None:
        return self.window if isinstance(self.window, QtWidgets.QWidget) else None

    def _status(self, message: str) -> None:
        text = str(message)
        self.statusChanged.emit(text)
        status_bar = getattr(self.window, "statusBar", None)
        if callable(status_bar):
            try:
                status_bar().showMessage(text, 8000)
            except Exception:
                pass

    def _fail(self, error: Exception | str) -> bool:
        message = str(error).strip() or "Scripting project operation failed."
        if isinstance(error, Exception):
            log.error(
                "Scripting project operation failed: %s",
                message,
                exc_info=(type(error), error, error.__traceback__),
            )
        self.operationFailed.emit(message)
        self._status(message)
        return False

    # Project lifecycle -------------------------------------------------

    def create_project(
        self,
        request: Mapping[str, Any] | object = (),
        *,
        root: str | Path | None = None,
        name: str | None = None,
    ) -> NarrativeProject | None:
        values = dict(request) if isinstance(request, Mapping) else {}
        game = str(values.get("game") or "K2")
        target = Path(root or values.get("root") or "") if (root or values.get("root")) else None
        if target is None:
            selected = QtWidgets.QFileDialog.getExistingDirectory(
                self._dialog_parent(),
                "Choose an Empty Folder for the Narrative Project",
            )
            if not selected:
                return None
            target = Path(selected)
        project_name = str(name or values.get("name") or "").strip()
        if not project_name:
            project_name, accepted = QtWidgets.QInputDialog.getText(
                self._dialog_parent(),
                "New Narrative Project",
                "Project name",
                text=target.name,
            )
            if not accepted:
                return None
        try:
            project = NarrativeProjectService.create_project(target, name=project_name, game=game)
            self._activate_project(project)
            self._status(f"Created narrative project: {project.name}")
            return project
        except Exception as exc:
            self._fail(exc)
            return None

    def open_project(self, path: str | Path | None = None) -> NarrativeProject | None:
        target = Path(path) if path else None
        if target is None:
            selected, _filter = QtWidgets.QFileDialog.getOpenFileName(
                self._dialog_parent(),
                "Open GhostStudio or Legacy GhostScripter Project",
                "",
                "Narrative projects (ghoststudio-narrative.json project.json);;JSON files (*.json)",
            )
            if not selected:
                return None
            target = Path(selected)
        if target.name.casefold() == "project.json":
            destination = QtWidgets.QFileDialog.getExistingDirectory(
                self._dialog_parent(),
                "Choose an Empty Folder for the Imported GhostScripter Project",
            )
            if not destination:
                return None
            result = self.import_legacy_project(target, destination)
            return result.project if result is not None else None
        try:
            project = NarrativeProjectService.load_project(target)
            self._activate_project(project)
            self._status(f"Opened narrative project: {project.name}")
            return project
        except Exception as exc:
            self._fail(exc)
            return None

    def import_legacy_project(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        legacy_database: str | Path | None = None,
    ):
        try:
            source_path = Path(source)
            database = legacy_database
            if database is None:
                candidates = (
                    source_path.parent / "ghostscripter.db",
                    source_path.parent / "GhostScripter.db",
                    Path.home() / ".ghostscripter" / "ghostscripter.db",
                )
                database = next((row for row in candidates if row.is_file()), None)
            result = NarrativeProjectService.import_legacy_ghostscripter_project(
                source_path,
                destination,
                legacy_database=database,
            )
            self._activate_project(result.project)
            warning_suffix = f" ({len(result.warnings)} warning(s))" if result.warnings else ""
            self._status(
                f"Imported {len(result.imported_resources)} resources and preserved "
                f"{result.preserved_files} legacy files, {result.history_rows} history rows, and "
                f"{result.preference_rows} preferences{warning_suffix}."
            )
            return result
        except Exception as exc:
            self._fail(exc)
            return None

    def _activate_project(self, project: NarrativeProject) -> None:
        self.project = project
        try:
            self.recent_store.remember(project)
        except Exception as exc:
            log.warning("Could not update recent narrative projects: %s", exc)
        self._present_all()
        self.projectChanged.emit(self._project_row(project))

    def save_project(self) -> bool:
        project = self.project
        if project is None:
            return self._fail("Create or open a narrative project before saving.")
        try:
            snapshots = tuple(_normalise_snapshot(row) for row in self.snapshot_provider())
            identities: dict[tuple[str, str], bytes] = {}
            filtered: list[ProjectResourceSnapshot] = []
            for row in snapshots:
                if row.game and row.game.upper() != project.game.upper():
                    continue
                identity = (row.resref.casefold(), row.restype.lower().lstrip("."))
                if identity in identities and identities[identity] != row.data:
                    raise ValueError(f"Conflicting open documents produce {row.resref}.{row.restype}.")
                if identity not in identities:
                    identities[identity] = row.data
                    filtered.append(row)
            if filtered:
                # Each write promotes its own manifest revision.  A later failure
                # can therefore leave a valid partial save, never an untracked
                # mutation masquerading as a successful all-or-nothing save.
                for row in filtered:
                    NarrativeProjectService.write_asset(
                        project,
                        resref=row.resref,
                        restype=row.restype,
                        data=row.data,
                        role=row.role,
                        dependencies=row.dependencies,
                        metadata=dict(row.metadata or {}),
                        save=True,
                    )
            else:
                NarrativeProjectService.save_project(project)
            self.recent_store.remember(project)
            self._present_all()
            self.projectChanged.emit(self._project_row(project))
            self._status(f"Saved {project.name} at revision {project.revision}.")
            return True
        except Exception as exc:
            return self._fail(exc)

    def import_assets(self, paths: Sequence[str | Path] | None = None) -> tuple[object, ...]:
        project = self.project
        if project is None:
            self._fail("Create or open a narrative project before importing resources.")
            return ()
        selected = tuple(paths or ())
        if not selected:
            filenames, _filter = QtWidgets.QFileDialog.getOpenFileNames(
                self._dialog_parent(),
                "Import KOTOR Narrative Resources",
                "",
                "KOTOR resources (*.nss *.ncs *.dlg *.jrl *.2da *.tlk *.lip *.ssf *.utc *.uti *.utp *.utd *.ute *.utm *.uts *.utt *.utw);;All files (*)",
            )
            selected = tuple(filenames)
        imported: list[object] = []
        try:
            for source in selected:
                suffix = Path(source).suffix.lower().lstrip(".")
                role = "source" if suffix == "nss" else "global_install" if suffix in _GLOBAL_INSTALL_TYPES else "runtime"
                imported.append(NarrativeProjectService.import_asset(project, source, role=role))
            self._present_all()
            if imported:
                self._status(f"Imported {len(imported)} project resource(s).")
            return tuple(imported)
        except Exception as exc:
            self._fail(exc)
            self._present_all()
            return tuple(imported)

    def refresh_inventory(self) -> None:
        self._present_all()
        self._status("Refreshed the project inventory without accepting external file changes.")

    def validate_project(self) -> tuple[object, ...]:
        issues = tuple(NarrativeProjectService.validate_project(self.project)) if self.project is not None else ()
        self._present_project(issues)
        blocking = sum(bool(getattr(row, "blocking", False)) for row in issues)
        self._status(
            f"Project readiness: {blocking} blocking issue(s), {len(issues) - blocking} review note(s)."
            if self.project is not None else "No narrative project is open."
        )
        return issues

    # History -----------------------------------------------------------

    def create_revision(self, message: str = "") -> object | None:
        if self.project is None:
            self._fail("Open a narrative project before creating a snapshot.")
            return None
        try:
            revision = NarrativeRevisionStore(self.project).create(message=message, author="LordVaderCW")
            self._present_project()
            self._status(f"Created immutable project snapshot {revision.revision_id}.")
            return revision
        except Exception as exc:
            self._fail(exc)
            return None

    def recover_revision(self, revision_id: str, output_dir: str | Path | None = None) -> str:
        if self.project is None:
            self._fail("Open a narrative project before recovering a snapshot.")
            return ""
        target = Path(output_dir) if output_dir else None
        if target is None:
            selected = QtWidgets.QFileDialog.getSaveFileName(
                self._dialog_parent(),
                "Recover Snapshot as a New Project Folder",
                f"{self.project.name}-recovered",
                "Folder name (*)",
            )[0]
            if not selected:
                return ""
            target = Path(selected)
        try:
            manifest = NarrativeRevisionStore(self.project).materialize(revision_id, target)
            self._status(f"Recovered snapshot as a new project: {manifest}")
            return str(manifest)
        except Exception as exc:
            self._fail(exc)
            return ""

    def recover_revision_asset(
        self,
        revision_id: str,
        asset_id: str,
        output_dir: str | Path | None = None,
    ) -> str:
        """Recover one immutable resource plus its metadata into a new folder."""

        if self.project is None:
            self._fail("Open a narrative project before recovering a historical resource.")
            return ""
        target = Path(output_dir) if output_dir else None
        if target is None:
            asset = self.project.asset_by_id(str(asset_id))
            label = asset.filename if asset is not None else str(asset_id or "resource")
            selected = QtWidgets.QFileDialog.getSaveFileName(
                self._dialog_parent(),
                "Recover Historical Resource into a New Folder",
                f"{label}-recovered",
                "Folder name (*)",
            )[0]
            if not selected:
                return ""
            target = Path(selected)
        try:
            metadata_path = NarrativeRevisionStore(self.project).materialize_asset(
                revision_id,
                asset_id,
                target,
            )
            self._status(f"Recovered historical resource and metadata: {metadata_path}")
            return str(metadata_path)
        except Exception as exc:
            self._fail(exc)
            return ""

    def recover_legacy_history(
        self,
        record_id: str,
        output_dir: str | Path | None = None,
    ) -> str:
        """Recover an imported GhostScripter snapshot without changing the project."""

        if self.project is None:
            self._fail("Open a migrated narrative project before recovering legacy history.")
            return ""
        target = Path(output_dir) if output_dir else None
        if target is None:
            selected = QtWidgets.QFileDialog.getSaveFileName(
                self._dialog_parent(),
                "Recover Legacy GhostScripter Snapshot into a New Folder",
                "legacy-snapshot-recovered",
                "Folder name (*)",
            )[0]
            if not selected:
                return ""
            target = Path(selected)
        try:
            manifest = LegacyNarrativeHistoryStore(self.project).recover(record_id, target)
            self._status(f"Recovered legacy GhostScripter snapshot and provenance: {manifest}")
            return str(manifest)
        except Exception as exc:
            self._fail(exc)
            return ""

    def open_legacy_quest_history(self, record_id: str) -> bool:
        """Publish one immutable legacy quest snapshot to the Quest Builder."""

        if self.project is None:
            self._fail("Open a migrated narrative project before opening legacy quest history.")
            return False
        try:
            record = next(
                (row for row in LegacyNarrativeHistoryStore(self.project).list() if row.record_id == str(record_id)),
                None,
            )
            if record is None:
                raise KeyError(f"Unknown legacy GhostScripter history record: {record_id}")
            if record.kind.casefold() != "quest":
                raise ValueError("Only preserved quest records can open in the Quest Builder.")
            self.legacyQuestOpened.emit(
                {
                    "record_id": record.record_id,
                    "identity": record.identity,
                    "content": record.content,
                    "source": record.content_source,
                }
            )
            self._status(f"Opened preserved quest in Quest Builder: {record.identity}")
            return True
        except Exception as exc:
            self._fail(exc)
            return False

    def _record_distribution_history(
        self,
        operation: str,
        *,
        inputs: Iterable[object] = (),
        destination: str | Path = "",
        result: object | None = None,
        summary: str = "",
        issues: Sequence[object] = (),
        backup_path: str | Path = "",
        receipt_path: str | Path = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> object | None:
        """Persist an operation receipt without changing the operation result."""

        if self.project is None:
            return None
        result_issues = tuple(getattr(result, "issues", ()) or ()) if result is not None else ()
        all_issues = tuple(issues) + result_issues
        ok = bool(getattr(result, "ok", False)) if result is not None else False
        committed = bool(getattr(result, "committed", False)) if result is not None else False
        effective_backup = str(backup_path or getattr(result, "backup_path", "") or "")
        effective_receipt = str(receipt_path or getattr(result, "receipt_path", "") or "")
        details = dict(metadata or {})
        details.setdefault("committed", committed)
        game = str(getattr(result, "game", "") or "") if result is not None else ""
        if game:
            details.setdefault("game", game)
        try:
            record = NarrativeExportHistoryStore(self.project).record(
                operation=operation,
                outcome="succeeded" if ok else "failed",
                destination=destination,
                inputs=tuple(inputs),
                backup_path=effective_backup,
                receipt_path=effective_receipt,
                summary=summary,
                issues=tuple(_issue_row(row) for row in all_issues),
                engine_proof="not_recorded",
                metadata=details,
            )
            self._present_export_history()
            return record
        except Exception as exc:
            # A secondary audit-write failure must be visible in logs but must
            # never misreport or roll back an already completed game operation.
            log.error(
                "Could not record narrative distribution history: %s",
                exc,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return None

    def forget_recent(self, project_id: str) -> None:
        try:
            self.recent_store.forget(project_id)
            self._present_recents()
        except Exception as exc:
            self._fail(exc)

    # Resource activation -----------------------------------------------

    def activate_asset(self, row: Mapping[str, Any] | object) -> str:
        values = dict(row) if isinstance(row, Mapping) else {}
        if self.project is None or not values.get("path"):
            return ""
        path = str((Path(self.project.root_path) / str(values["path"])).resolve())
        self.assetActivationRequested.emit(path, values)
        if self.asset_activator is not None:
            try:
                self.asset_activator(path, values)
            except Exception as exc:
                self._fail(exc)
                return ""
        return path

    def activate_package_resource(self, row: Mapping[str, Any] | object) -> str:
        values = dict(row) if isinstance(row, Mapping) else {}
        path = str(values.get("source_path") or "")
        if not path and values.get("asset_id") and self.project is not None:
            asset = self.project.asset_by_id(str(values["asset_id"]))
            path = str(Path(self.project.root_path) / asset.path) if asset is not None else ""
        if path:
            self.assetActivationRequested.emit(path, values)
            if self.asset_activator is not None:
                try:
                    self.asset_activator(path, values)
                except Exception as exc:
                    self._fail(exc)
                    return ""
        return path

    # Packaging ---------------------------------------------------------

    def add_package_files(self, paths: Sequence[str | Path] | None = None) -> tuple[PackageResource, ...]:
        selected = tuple(paths or ())
        if not selected:
            filenames, _filter = QtWidgets.QFileDialog.getOpenFileNames(
                self._dialog_parent(),
                "Add Resources to Package",
                "",
                "KOTOR resources (*.*)",
            )
            selected = tuple(filenames)
        try:
            rows = NarrativePackagingService.resources_from_paths(selected) if selected else ()
            source_by_identity = {
                (Path(path).stem.casefold(), Path(path).suffix.lower().lstrip(".")): str(Path(path).resolve())
                for path in selected
            }
            for resource in rows:
                role = "source" if resource.restype == "nss" else (
                    "global_install" if resource.restype in _GLOBAL_INSTALL_TYPES else "runtime"
                )
                self._loose_resources[resource.identity] = _PackageEntry(
                    resource,
                    role,
                    source_by_identity.get(resource.identity, ""),
                )
            self.refresh_package_readiness()
            return tuple(rows)
        except Exception as exc:
            self._fail(exc)
            return ()

    def _package_entries(self) -> tuple[tuple[_PackageEntry, ...], tuple[NarrativePackageIssue, ...]]:
        issues: list[NarrativePackageIssue] = []
        entries: "OrderedDict[tuple[str, str], _PackageEntry]" = OrderedDict()
        if self.project is not None:
            root = Path(self.project.root_path).resolve()
            for asset in self.project.assets:
                source = (root / asset.path).resolve()
                if not source.is_file() or source.is_symlink():
                    continue
                resource = PackageResource(asset.resref, asset.restype, source.read_bytes(), asset.asset_id)
                entries[resource.identity] = _PackageEntry(resource, asset.role, str(source))
        for identity, loose in self._loose_resources.items():
            prior = entries.get(identity)
            if prior is not None and prior.resource.data != loose.resource.data:
                issues.append(
                    NarrativePackageIssue(
                        "blocking",
                        "narrative_package.resource_conflict",
                        f"Project and added file provide different bytes for {loose.resource.filename}.",
                        loose.resource.filename,
                    )
                )
                continue
            entries.setdefault(identity, loose)
        return tuple(entries.values()), tuple(issues)

    @staticmethod
    def _eligible_resources(entries: Iterable[_PackageEntry], *, include_source: bool) -> tuple[PackageResource, ...]:
        return tuple(
            row.resource
            for row in entries
            if row.role != "global_install" and row.resource.restype not in _GLOBAL_INSTALL_TYPES
            and (include_source or row.role != "source")
        )

    def refresh_package_readiness(self) -> bool:
        entries, package_issues = self._package_entries()
        issues: list[dict[str, Any]] = []
        if self.project is not None:
            issues.extend(_issue_row(row) for row in NarrativeProjectService.validate_project(self.project))
        issues.extend(_issue_row(row) for row in package_issues)
        for entry in entries:
            if entry.role == "global_install" or entry.resource.restype in _GLOBAL_INSTALL_TYPES:
                issues.append(
                    {
                        "severity": "warning",
                        "code": "narrative_package.global_resource_excluded",
                        "resource": entry.resource.filename,
                        "message": "Global game-root resources are tracked by the project but excluded from MOD/ERF and Override output.",
                    }
                )
        eligible = self._eligible_resources(entries, include_source=False)
        if not eligible:
            issues.append(
                {
                    "severity": "blocking",
                    "code": "narrative_package.no_runtime_resources",
                    "resource": "",
                    "message": "Add at least one runtime resource before packaging.",
                }
            )
        ready = bool(eligible) and not any(str(row.get("severity", "")).lower() in {"blocking", "error"} for row in issues)
        rows = [
            {
                "resref": entry.resource.resref,
                "restype": entry.resource.restype,
                "filename": entry.resource.filename,
                "byte_count": len(entry.resource.data),
                "role": entry.role,
                "status": "excluded (global install)" if entry.role == "global_install" else "ready",
                "asset_id": entry.resource.source_asset_id,
                "source_asset_id": entry.resource.source_asset_id,
                "source_path": entry.source_path,
            }
            for entry in entries
        ]
        if self.package_page is not None:
            self.package_page.set_package_resources(rows)
            self.package_page.set_readiness(
                {"ready": ready, "summary": "Ready to package" if ready else "Resolve package readiness issues"},
                issues=issues,
            )
        self.packageResourcesChanged.emit(rows)
        return ready

    def build_package(self, request: Mapping[str, Any] | object) -> object | None:
        values = dict(request) if isinstance(request, Mapping) else {}
        entries, conflicts = self._package_entries()
        resources = self._eligible_resources(entries, include_source=bool(values.get("include_source")))
        output_path = str(values.get("output_path") or "").strip()
        if conflicts or not resources:
            self.refresh_package_readiness()
            self._record_distribution_history(
                "package",
                inputs=resources,
                destination=output_path,
                summary="Package build was rejected before archive creation.",
                issues=tuple(conflicts) + (
                    NarrativePackageIssue(
                        "blocking",
                        "narrative_package.no_runtime_resources",
                        "Resolve package resource conflicts and add runtime resources before building.",
                    ),
                ),
                metadata={"archive_type": str(values.get("archive_type") or "MOD").upper()},
            )
            self._fail("Resolve package resource conflicts and add runtime resources before building.")
            return None
        if not output_path:
            self._record_distribution_history(
                "package",
                inputs=resources,
                summary="Package build was rejected because no output path was selected.",
                issues=(
                    NarrativePackageIssue(
                        "blocking",
                        "narrative_package.output_required",
                        "Choose an archive output path before building.",
                    ),
                ),
                metadata={"archive_type": str(values.get("archive_type") or "MOD").upper()},
            )
            self._fail("Choose an archive output path before building.")
            return None
        result = NarrativePackagingService.build_archive(
            resources,
            output_path,
            archive_type=str(values.get("archive_type") or "MOD"),
            overwrite=bool(values.get("overwrite")),
        )
        self._record_distribution_history(
            "package",
            inputs=result.resources,
            destination=result.output_path,
            result=result,
            summary=(
                f"Archive was structurally read back with {len(result.resources)} exact resource(s)."
                if result.ok else "Archive build did not commit."
            ),
            receipt_path=result.manifest_path,
            metadata={
                "archive_type": result.archive_type,
                "structural_readback": bool(result.ok),
            },
        )
        if self.package_page is not None:
            self.package_page.set_archive_result(
                {
                    "committed": result.committed,
                    "output_path": result.output_path,
                    "summary": (
                        f"Verified archive: {result.output_path}" if result.ok
                        else "Archive build did not commit: " + "; ".join(row.message for row in result.issues)
                    ),
                }
            )
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        self._status(
            f"Built and read back {len(result.resources)} resources in {result.output_path}."
            if result.ok else "Archive build was blocked."
        )
        return result

    def stage_override(self, request: Mapping[str, Any] | object) -> object | None:
        values = dict(request) if isinstance(request, Mapping) else {}
        entries, conflicts = self._package_entries()
        resources = self._eligible_resources(entries, include_source=bool(values.get("include_source")))
        output_dir = str(values.get("output_dir") or "").strip()
        if conflicts or not resources or not output_dir:
            self.refresh_package_readiness()
            self._record_distribution_history(
                "stage_override",
                inputs=resources,
                destination=output_dir,
                summary="Override staging was rejected before files were written.",
                issues=tuple(conflicts) + (
                    NarrativePackageIssue(
                        "blocking",
                        "override_stage.not_ready",
                        "Choose a stage folder and resolve package readiness issues first.",
                    ),
                ),
            )
            self._fail("Choose a stage folder and resolve package readiness issues first.")
            return None
        game = self.project.game if self.project is not None else "K2"
        result = NarrativePackagingService.stage_override(
            resources,
            output_dir,
            game=game,
            replace_owned=bool(values.get("replace_owned")),
        )
        self._record_distribution_history(
            "stage_override",
            inputs=result.resources,
            destination=result.stage_path,
            result=result,
            summary=(
                f"Override stage was read back with {len(result.resources)} exact resource(s)."
                if result.ok else "Override staging did not commit."
            ),
            receipt_path=result.manifest_path,
            metadata={"structural_readback": bool(result.ok)},
        )
        self._last_stage_path = result.stage_path if result.ok else ""
        if self.package_page is not None:
            self.package_page.set_override_stage_result(
                {
                    "committed": result.committed,
                    "stage_path": result.stage_path,
                    "summary": (
                        f"Verified Override stage: {result.stage_path}" if result.ok
                        else "Override staging was blocked: " + "; ".join(row.message for row in result.issues)
                    ),
                }
            )
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        self._status("Override resources staged and verified." if result.ok else "Override staging was blocked.")
        return result

    def inspect_stage(self, stage_path: str | Path) -> object:
        result = NarrativePackagingService.inspect_override_stage(stage_path)
        self._last_stage_path = result.stage_path if result.ok else ""
        if self.package_page is not None:
            self.package_page.set_override_stage_result(
                {
                    "committed": result.committed,
                    "stage_path": result.stage_path,
                    "summary": (
                        f"Verified existing stage with {len(result.resources)} resource(s)."
                        if result.ok else "Existing stage is invalid."
                    ),
                }
            )
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        return result

    def install_override(self, request: Mapping[str, Any] | object) -> object | None:
        values = dict(request) if isinstance(request, Mapping) else {}
        stage_path = str(values.get("stage_path") or self._last_stage_path).strip()
        game_root = str(values.get("game_root") or "").strip()
        if not stage_path or not game_root:
            self._record_distribution_history(
                "install_override",
                destination=str(Path(game_root).resolve() / "Override") if game_root else "",
                summary="Override install was rejected before preflight.",
                issues=(
                    NarrativePackageIssue(
                        "blocking",
                        "override_install.paths_required",
                        "Choose a verified stage and a game folder before installing.",
                    ),
                ),
                metadata={"stage_path": stage_path},
            )
            self._fail("Choose a verified stage and a game folder before installing.")
            return None
        inspected_stage = NarrativePackagingService.inspect_override_stage(stage_path)
        result = NarrativePackagingService.install_override(
            stage_path,
            game_root,
            on_conflict=str(values.get("on_conflict") or "block"),
        )
        self._record_distribution_history(
            "install_override",
            inputs=inspected_stage.resources,
            destination=str(Path(game_root).resolve() / "Override"),
            result=result,
            summary=(
                f"Installed {len(result.installed)} resource(s); "
                f"{len(result.skipped_identical)} were already byte-identical."
                if result.ok else "Override install failed or was blocked."
            ),
            metadata={
                "stage_path": str(Path(stage_path).resolve()),
                "conflict_policy": str(values.get("on_conflict") or "block"),
                "stage_verified": bool(inspected_stage.ok),
            },
        )
        if self.package_page is not None:
            self.package_page.set_install_result(
                {
                    "committed": result.committed,
                    "installed": result.installed,
                    "backup_path": result.backup_path,
                    "summary": (
                        f"Installed {len(result.installed)} file(s); {len(result.skipped_identical)} were already identical."
                        if result.ok else "Install was blocked: " + "; ".join(row.message for row in result.issues)
                    ),
                }
            )
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        self._status("Installed the verified Override stage." if result.ok else "Override install was blocked.")
        return result

    def install_global_tlk(self, request: Mapping[str, Any] | object) -> object | None:
        """Install the tracked TLK through the dedicated backup/receipt path."""

        values = dict(request) if isinstance(request, Mapping) else {}
        game_root = str(values.get("game_root") or "").strip()
        if not game_root:
            self._record_distribution_history(
                "install_global_tlk",
                summary="Global talk-table install was rejected before preflight.",
                issues=(
                    NarrativePackageIssue(
                        "blocking",
                        "global_tlk.game_root_required",
                        "Choose a game folder before installing the global talk table.",
                    ),
                ),
            )
            self._fail("Choose a game folder before installing the global talk table.")
            return None
        entries, _issues = self._package_entries()
        requested = str(values.get("resref") or "dialog").casefold()
        matches = [
            entry.resource
            for entry in entries
            if entry.resource.restype == "tlk" and entry.resource.resref.casefold() == requested
        ]
        if len(matches) != 1:
            self._record_distribution_history(
                "install_global_tlk",
                inputs=matches,
                destination=str(Path(game_root).resolve() / "dialog.tlk"),
                summary="Global talk-table install was rejected because the project selection was ambiguous.",
                issues=(
                    NarrativePackageIssue(
                        "blocking",
                        "global_tlk.resource_required",
                        f"The project must contain exactly one {requested}.tlk resource to install.",
                    ),
                ),
            )
            self._fail(f"The project must contain exactly one {requested}.tlk resource to install.")
            return None
        game = str(values.get("game") or (self.project.game if self.project is not None else "K2"))
        result = NarrativePackagingService.install_global_tlk(matches[0].data, game_root, game=game)
        self._record_distribution_history(
            "install_global_tlk",
            inputs=matches,
            destination=str(Path(game_root).resolve() / "dialog.tlk"),
            result=result,
            summary=(
                "Installed the game-global talk table with an exact permanent backup."
                if result.ok else "Global talk-table install failed or was blocked."
            ),
            metadata={"game": game},
        )
        self.globalTlkResultChanged.emit(asdict(result))
        if self.package_page is not None:
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        self._status(
            f"Installed dialog.tlk with a permanent backup at {result.backup_path}."
            if result.ok else "Global talk-table install was blocked."
        )
        return result

    def restore_global_tlk(self, request: Mapping[str, Any] | object) -> object | None:
        """Restore a prior TLK receipt while preserving the current live bytes."""

        values = dict(request) if isinstance(request, Mapping) else {}
        receipt = str(values.get("receipt_path") or "").strip()
        game_root = str(values.get("game_root") or "").strip()
        if not receipt or not game_root:
            self._record_distribution_history(
                "restore_global_tlk",
                destination=str(Path(game_root).resolve() / "dialog.tlk") if game_root else "",
                summary="Talk-table restore was rejected before preflight.",
                issues=(
                    NarrativePackageIssue(
                        "blocking",
                        "global_tlk.restore_paths_required",
                        "Choose both a TLK install receipt and its game folder before restoring.",
                    ),
                ),
                metadata={"source_receipt": receipt},
            )
            self._fail("Choose both a TLK install receipt and its game folder before restoring.")
            return None
        restore_inputs: list[dict[str, Any]] = []
        receipt_path = Path(receipt).resolve()
        if receipt_path.is_dir():
            receipt_path = receipt_path / "install-receipt.json"
        if receipt_path.is_file() and not receipt_path.is_symlink():
            restore_inputs.append({"filename": receipt_path.name, "data": receipt_path.read_bytes()})
        live_tlk = Path(game_root).resolve() / "dialog.tlk"
        if live_tlk.is_file() and not live_tlk.is_symlink():
            restore_inputs.append({"filename": "live-dialog.tlk", "data": live_tlk.read_bytes()})
        result = NarrativePackagingService.restore_global_tlk(receipt, game_root)
        self._record_distribution_history(
            "restore_global_tlk",
            inputs=restore_inputs,
            destination=str(live_tlk),
            result=result,
            summary=(
                "Restored the receipted talk table while preserving the pre-restore bytes."
                if result.ok else "Global talk-table restore failed or was blocked."
            ),
            metadata={"source_receipt": str(receipt_path)},
        )
        self.globalTlkResultChanged.emit(asdict(result))
        if self.package_page is not None:
            self.package_page.set_issues([_issue_row(row) for row in result.issues])
        self._status(
            f"Restored the prior dialog.tlk; pre-restore bytes are at {result.backup_path}."
            if result.ok else "Global talk-table restore was blocked."
        )
        return result

    # Dialog routing ----------------------------------------------------

    def browse_package_output(self, archive_type: str = "MOD") -> str:
        kind = str(archive_type or "MOD").upper()
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self._dialog_parent(), f"Build {kind} Archive", f"narrative.{kind.lower()}", f"{kind} archive (*.{kind.lower()})"
        )
        if path and self.package_page is not None:
            self.package_page.package_output_edit.setText(path)
        return path

    def browse_stage_output(self, current: str = "") -> str:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self._dialog_parent(), "Choose Override Staging Folder", str(current or "")
        )
        if path and self.package_page is not None:
            self.package_page.stage_output_edit.setText(path)
        return path

    def browse_game_root(self, current: str = "") -> str:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self._dialog_parent(), "Choose KOTOR Installation Folder", str(current or "")
        )
        if path and self.package_page is not None:
            self.package_page.game_root_edit.setText(path)
        return path

    # Presentation ------------------------------------------------------

    @staticmethod
    def _project_row(project: NarrativeProject) -> dict[str, Any]:
        issues = NarrativeProjectService.validate_project(project)
        return {
            "project_id": project.project_id,
            "name": project.name,
            "game": project.game,
            "revision": project.revision,
            "manifest_path": project.manifest_path,
            "status": "needs attention" if any(row.blocking for row in issues) else "ready",
        }

    def _present_project(self, issues: Sequence[object] | None = None) -> None:
        if self.project_page is None:
            return
        if self.project is None:
            self.project_page.set_project({})
            self.project_page.set_asset_rows([])
            self.project_page.set_revision_rows([])
            set_legacy_history = getattr(self.project_page, "set_legacy_history_rows", None)
            if callable(set_legacy_history):
                set_legacy_history([])
            set_export_history = getattr(self.project_page, "set_export_history_rows", None)
            if callable(set_export_history):
                set_export_history([])
            self.project_page.set_project_issues([], summary="No project open")
            return
        project_issues = tuple(issues) if issues is not None else NarrativeProjectService.validate_project(self.project)
        issue_by_asset: dict[str, list[object]] = {}
        for issue in project_issues:
            issue_by_asset.setdefault(str(getattr(issue, "asset_id", "")), []).append(issue)
        asset_rows = []
        for asset in self.project.assets:
            rows = issue_by_asset.get(asset.asset_id, ())
            asset_rows.append(
                {
                    "asset_id": asset.asset_id,
                    "resref": asset.resref,
                    "restype": asset.restype,
                    "role": asset.role,
                    "path": asset.path,
                    "dependencies": [row.to_dict() for row in asset.dependencies],
                    "dependency_summary": ", ".join(f"{row.resref}.{row.restype}" for row in asset.dependencies),
                    "status": "blocked" if any(getattr(row, "blocking", False) for row in rows) else (
                        "review" if rows else "tracked"
                    ),
                }
            )
        revisions = [asdict(row) for row in NarrativeRevisionStore(self.project).list()]
        blocking = sum(bool(getattr(row, "blocking", False)) for row in project_issues)
        self.project_page.set_project(self._project_row(self.project))
        self.project_page.set_asset_rows(asset_rows)
        self.project_page.set_revision_rows(revisions)
        self.project_page.set_project_issues(
            [_issue_row(row) for row in project_issues],
            summary=f"{blocking} blocking issue(s), {len(project_issues) - blocking} review note(s)",
        )
        self._present_legacy_history()
        self._present_export_history()

    def _present_legacy_history(self) -> None:
        if self.project_page is None:
            return
        setter = getattr(self.project_page, "set_legacy_history_rows", None)
        if not callable(setter):
            return
        if self.project is None:
            setter([])
            return
        try:
            setter([row.to_dict(include_content=False) for row in LegacyNarrativeHistoryStore(self.project).list()])
        except Exception as exc:
            log.warning("Could not read imported GhostScripter history: %s", exc)
            setter([])

    def _present_export_history(self) -> None:
        if self.project_page is None:
            return
        setter = getattr(self.project_page, "set_export_history_rows", None)
        if not callable(setter):
            return
        if self.project is None:
            setter([])
            return
        try:
            setter([row.to_dict() for row in NarrativeExportHistoryStore(self.project).list()])
        except Exception as exc:
            log.warning("Could not read narrative export history: %s", exc)
            setter([])

    def _present_recents(self) -> None:
        if self.project_page is None:
            return
        try:
            rows = [row.to_dict() for row in self.recent_store.list()]
        except Exception as exc:
            log.warning("Could not read recent narrative projects: %s", exc)
            rows = []
        self.project_page.set_recent_rows(rows)

    def _present_all(self) -> None:
        self._present_project()
        self._present_recents()
        self.refresh_package_readiness()


__all__ = ["ProjectResourceSnapshot", "ScriptingProjectController"]
