"""Qt signal adapter for the headless Placeable Builder tool service."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.project.placeable_asset import PlaceableAsset
from src.core.resources.game_resource_provider import GameResourceQuery
from src.core.tools.placeable_builder_tool_service import PlaceableBuilderToolService


class QtPlaceableBuilderController(QtCore.QObject):
    """Connect a presentation-only workbench to real library/UTP operations."""

    def __init__(
        self,
        window: Any,
        *,
        library_root: str | Path,
        provider: Any = None,
        resource_manager: Any = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent or window)
        self.window = window
        self.service = PlaceableBuilderToolService(library_root, provider=provider)
        self.resource_manager = resource_manager
        self._preview_key: tuple[str, str] = ("", "")
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(180)
        self._refresh_timer.timeout.connect(self._refresh_document_feedback)
        self._connect()
        self.window.set_library_root(library_root)
        self.refresh_library()
        self.new_document(initial=True)

    def _connect(self) -> None:
        self.window.newRequested.connect(self.new_document)
        self.window.cloneRequested.connect(self.clone_document)
        self.window.openRequested.connect(self.choose_open)
        self.window.saveToLibraryRequested.connect(self.save_document)
        self.window.exportUtpRequested.connect(self.choose_export)
        self.window.validateRequested.connect(self.validate_document)
        self.window.refreshLibraryRequested.connect(self.refresh_library)
        self.window.libraryAssetActivated.connect(self.open_library_row)
        self.window.openLibraryFolderRequested.connect(self.open_library_folder)
        self.window.documentChanged.connect(lambda _document: self._refresh_timer.start())

    def set_library_root(self, root: str | Path) -> None:
        self.service.set_library_root(root)
        self.window.set_library_root(root)
        self.refresh_library()

    def set_provider(self, provider: Any = None, *, resource_manager: Any = None) -> None:
        self.service.set_provider(provider)
        if resource_manager is not None:
            self.resource_manager = resource_manager
        self.refresh_library()
        self._preview_key = ("", "")
        self._refresh_document_feedback()

    def refresh_library(self) -> None:
        try:
            rows = self.service.rows()
        except Exception as exc:
            self.window.statusBar().showMessage(f"Placeable Library refresh failed: {exc}", 7000)
            rows = ()
        self.window.set_library_rows(rows)

    def new_document(self, initial: bool = False) -> None:
        game = str(getattr(self.window, "game_combo", None).currentText() or "K2") if hasattr(self.window, "game_combo") else "K2"
        asset = self.service.new_asset(game=game)
        self.window.set_document(asset, mark_clean=bool(initial))
        self.validate_document(asset.to_dict())
        self._preview_key = ("", "")
        self._update_preview(asset)

    def clone_document(self, document: Mapping[str, Any]) -> None:
        try:
            asset = self.service.clone_asset(document)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self.window, "Clone Placeable", str(exc))
            return
        self.window.set_document(asset, mark_clean=False)
        self.validate_document(asset.to_dict())
        self._preview_key = ("", "")
        self._update_preview(asset)

    def choose_open(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Open Placeable Library Asset",
            str(self.service.library_root),
            "GhostStudio Placeables (*.ghostplaceable.json);;JSON (*.json)",
        )
        if path:
            self.open_library_row({"source": "placeable_builder", "path": path})

    def open_library_row(self, row: Mapping[str, Any]) -> None:
        try:
            asset = self.service.load_row(row)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self.window, "Open Placeable", str(exc))
            return
        self.window.set_document(asset, mark_clean=True)
        self.validate_document(asset.to_dict())
        self._preview_key = ("", "")
        self._update_preview(asset)

    def validate_document(self, document: Mapping[str, Any]) -> Any:
        try:
            validation = self.service.validate(document)
        except Exception as exc:
            self.window.set_readiness(
                {
                    "issues": ({"severity": "blocking", "code": "placeable_document_invalid", "message": str(exc)},),
                    "document_valid": False,
                    "utp_export_ready": False,
                    "structural_evidence_ready": False,
                    "engine_ready": False,
                }
            )
            return None
        self.window.set_readiness(validation)
        try:
            asset = PlaceableAsset.from_dict(dict(document))
            self.window.set_resource_rows(self._resource_rows(asset))
        except Exception:
            pass
        return validation

    def save_document(self, document: Mapping[str, Any]) -> Any:
        result = self.service.save(document)
        self.window.set_readiness(result.validation)
        if not result.ok:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Save Placeable",
                "\n".join(result.messages) or "The placeable is not ready to save.",
            )
            return result
        self.window.accept_library_save(result.asset)
        self.refresh_library()
        self.window.statusBar().showMessage(
            f"Saved {Path(result.sidecar_path).name} and {Path(result.utp_path).name}. Manual KOTOR proof is still required.",
            7000,
        )
        return result

    def choose_export(self, document: Mapping[str, Any]) -> None:
        resref = str(document.get("template_resref") or "placeable").strip().lower()
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self.window,
            "Export KOTOR Placeable UTP",
            str(self.service.library_root / f"{resref}.utp"),
            "KOTOR Placeable Template (*.utp)",
        )
        if path:
            self.export_document(document, path)

    def export_document(self, document: Mapping[str, Any], output_path: str | Path) -> Any:
        result = self.service.export_utp(document, output_path)
        self.window.set_readiness(result.validation)
        if not result.ok:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Export Placeable UTP",
                "\n".join(result.messages) or "The placeable is not ready for UTP export.",
            )
            return result
        self.window.statusBar().showMessage(
            f"Exported {Path(result.utp_path).name}; UTP readback passed, manual KOTOR proof remains.",
            7000,
        )
        return result

    def open_library_folder(self, path: str) -> None:
        root = Path(path or self.service.library_root)
        root.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(root.resolve())))

    def _refresh_document_feedback(self) -> None:
        document = self.window.current_document()
        self.validate_document(document)
        try:
            self._update_preview(PlaceableAsset.from_dict(document))
        except Exception:
            pass

    def _update_preview(self, asset: PlaceableAsset) -> None:
        game = str(asset.game or "K2").upper()
        model_resref = self.service.preview_model_resref(asset)
        key = (game, model_resref)
        if key == self._preview_key:
            return
        self._preview_key = key
        if not model_resref or self.resource_manager is None:
            self.window.set_preview_model(
                None,
                resource_manager=self.resource_manager,
                game=game,
                message=(
                    "No model preview resolves yet. Choose a stock Appearance row or paired custom MDL/MDX resources."
                    if not model_resref
                    else f"Model {model_resref} resolves, but no KOTOR ResourceManager is connected."
                ),
            )
            return
        try:
            model = self.resource_manager.load_model(model_resref, game)
        except Exception as exc:
            model = None
            message = f"Could not load {game}:{model_resref}: {exc}"
        else:
            message = (
                f"Previewing {game}:{model_resref}. Editor rendering is not an in-game proof."
                if model is not None
                else f"{game}:{model_resref} did not resolve to an MDL/MDX pair."
            )
        self.window.set_preview_model(
            model,
            resource_manager=self.resource_manager,
            game=game,
            message=message,
        )

    def _resource_rows(self, asset: PlaceableAsset) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []

        def append(label: str, resref: str, restype: str, address: Any = None) -> None:
            if not resref:
                return
            resolved = False
            if self.service.provider is not None:
                try:
                    query = address or GameResourceQuery(game=asset.game, resref=resref, restype=restype)
                    resolved = bool(self.service.provider.exists(query))
                except Exception:
                    resolved = False
            rows.append(
                {
                    "label": label,
                    "resref": resref,
                    "restype": restype,
                    "source": getattr(address, "layer", "") if address is not None else "template reference",
                    "resolved": resolved,
                    "status": "Resolved" if resolved else "Needs target-game or packaged resource",
                }
            )

        if asset.base_template is not None:
            append("Base UTP", asset.base_template.resref or "", "UTP", asset.base_template)
        for label, address in (
            ("Model", asset.resources.mdl),
            ("Model data", asset.resources.mdx),
            ("Placeable walkmesh", asset.resources.pwk),
        ):
            if address is not None:
                append(label, address.resref or "", address.restype or "", address)
        for address in asset.resources.textures:
            append("Texture", address.resref or "", address.restype or "", address)
        for hook, resref in sorted(asset.scripts.items()):
            append(f"Script: {hook}", resref, "NCS")
        append("Conversation", asset.gameplay.conversation_resref, "DLG")
        for resref in asset.gameplay.inventory_items:
            append("Inventory item", resref, "UTI")
        return tuple(rows)

__all__ = ["QtPlaceableBuilderController"]
