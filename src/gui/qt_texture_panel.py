"""Qt texture conversion panel for GhostRigger."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from .qt_common_panels import QtToolPanel


class QtTexturePanel(QtToolPanel):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Texture Converter", parent)
        self._build()

    def _build(self) -> None:
        _group, layout = self.add_group("TGA to TPC")
        tga_buttons = self.add_buttons(layout, ["TGA to TPC (single)", "TGA to TPC (batch folder)"])
        tga_buttons[0].clicked.disconnect()
        tga_buttons[0].clicked.connect(self._tga_to_tpc_single)
        tga_buttons[1].clicked.disconnect()
        tga_buttons[1].clicked.connect(self._tga_to_tpc_batch)

        _group, layout = self.add_group("TPC to TGA")
        tpc_buttons = self.add_buttons(layout, ["TPC to TGA (single)", "TPC to TGA (batch folder)"])
        tpc_buttons[0].clicked.disconnect()
        tpc_buttons[0].clicked.connect(self._tpc_to_tga_single)
        tpc_buttons[1].clicked.disconnect()
        tpc_buttons[1].clicked.connect(self._tpc_to_tga_batch)

        _group, layout = self.add_group("TXI Metadata")
        layout.addWidget(QtWidgets.QLabel("TXI string appended to TPC:"))
        self.txi_text = QtWidgets.QPlainTextEdit()
        self.txi_text.setPlainText("# Examples:\n# bumpmap texture_n\n# envmaptexture CM_Baremetal\n")
        self.txi_text.setMaximumHeight(110)
        layout.addWidget(self.txi_text)

        self.mipmap_check = QtWidgets.QCheckBox("Generate Mipmaps")
        self.mipmap_check.setChecked(True)
        self.root.addWidget(self.mipmap_check)
        self.add_status("")

    def txi(self) -> str:
        return self.txi_text.toPlainText().strip()

    def _tga_to_tpc_single(self) -> None:
        src, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select TGA", "", "TGA files (*.tga)")
        if not src:
            return
        dst, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save TPC", str(Path(src).with_suffix(".tpc")), "TPC files (*.tpc)"
        )
        if not dst:
            return
        from src.converters.mesh_converter import tga_to_tpc

        ok = tga_to_tpc(src, dst, self.txi(), self.mipmap_check.isChecked())
        self.set_status("Done" if ok else "Failed")

    def _tga_to_tpc_batch(self) -> None:
        src_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder with TGA files")
        if not src_dir:
            return
        dst_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder for TPC files")
        if not dst_dir:
            return
        from src.converters.mesh_converter import tga_to_tpc

        ok = bad = 0
        for path in Path(src_dir).glob("*.tga"):
            out = Path(dst_dir) / f"{path.stem}.tpc"
            if tga_to_tpc(str(path), str(out), self.txi(), self.mipmap_check.isChecked()):
                ok += 1
            else:
                bad += 1
        self.set_status(f"{ok} converted, {bad} failed")

    def _tpc_to_tga_single(self) -> None:
        src, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select TPC", "", "TPC files (*.tpc)")
        if not src:
            return
        dst, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save TGA", str(Path(src).with_suffix(".tga")), "TGA files (*.tga)"
        )
        if not dst:
            return
        from src.converters.mesh_converter import tpc_to_tga

        ok = tpc_to_tga(src, dst)
        self.set_status("Done" if ok else "Failed")

    def _tpc_to_tga_batch(self) -> None:
        src_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder with TPC files")
        if not src_dir:
            return
        dst_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder for TGA files")
        if not dst_dir:
            return
        from src.converters.mesh_converter import tpc_to_tga

        ok = bad = 0
        for path in Path(src_dir).glob("*.tpc"):
            out = Path(dst_dir) / f"{path.stem}.tga"
            if tpc_to_tga(str(path), str(out)):
                ok += 1
            else:
                bad += 1
        self.set_status(f"{ok} converted, {bad} failed")
