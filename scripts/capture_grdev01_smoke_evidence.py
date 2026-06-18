"""Capture screenshot evidence for the grdev01 in-game smoke test.

Run this after KOTOR is showing the `warp grdev01` result.  By default it only
captures a BMP screenshot.  Use `--record-proof` plus the explicit acceptance
flags after verifying the module loads, the player stands on the generated
floor, the test placeable is visible, and walking works.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROOF_MANIFEST = (
    ROOT
    / "artifacts"
    / "map_studio"
    / "grdev01_authored_smoke_installed"
    / "grdev01_authored_module_game_manifest.json"
)
PAYLOAD_PATHS = (
    "native/GhostRigger.Domain.Core.Modules/Python",
    "native/GhostRigger.Domain.Core.Game/Python",
    "native/GhostRigger.Domain.Core.Scene/Python",
    "native/GhostRigger.Domain.Core.Walkmesh/Python",
    "native/GhostRigger.Domain.Core.Geometry/Python",
    "native/GhostRigger.Domain.Core.Camera/Python",
    "native/GhostRigger.Domain.Core.Math/Python",
    "native/GhostRigger.Domain.Core.Lighting/Python",
    ".",
)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        default=DEFAULT_PROOF_MANIFEST,
        help="Proof manifest written by the grdev01 prepare/install helper.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional BMP evidence path. Defaults to <manifest-dir>/evidence/grdev01_smoke_<timestamp>.bmp.",
    )
    parser.add_argument("--tester", default="", help="Name or handle of the tester recording proof.")
    parser.add_argument("--notes", default="", help="Optional notes about the KOTOR build, install path, or result.")
    parser.add_argument("--record-proof", action="store_true", help="Record the captured evidence into the proof manifest.")
    parser.add_argument("--module-loads-in-game", action="store_true", help="Confirm `warp grdev01` loads the generated module.")
    parser.add_argument("--player-spawns-on-floor", action="store_true", help="Confirm the player appears on the generated floor.")
    parser.add_argument("--test-placeable-visible", action="store_true", help="Confirm the smoke-test placeable appears.")
    parser.add_argument("--player-can-walk-on-floor", action="store_true", help="Confirm the player can walk across the generated floor.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _load_proof(proof_manifest: Path) -> dict[str, Any]:
    try:
        proof = json.loads(proof_manifest.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return proof if isinstance(proof, dict) else {}


def _default_output_path(proof_manifest: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return proof_manifest.parent / "evidence" / f"grdev01_smoke_{timestamp}.bmp"


def _capture_screen_bmp(output_path: Path) -> dict[str, Any]:
    if sys.platform != "win32":
        return {
            "ok": False,
            "message": "Screenshot capture is currently implemented for Windows only.",
            "blocking_issues": ["Run this helper on the Windows machine where KOTOR is visible."],
        }

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    x = user32.GetSystemMetrics(76)
    y = user32.GetSystemMetrics(77)
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    if width <= 0 or height <= 0:
        return {
            "ok": False,
            "message": "Could not determine the virtual screen bounds.",
            "blocking_issues": ["No screen bounds were available for evidence capture."],
        }

    screen_dc = user32.GetDC(0)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, x, y, 0x00CC0020):
            raise OSError("BitBlt failed while capturing the screen.")

        row_size = ((width * 24 + 31) // 32) * 4
        image_size = row_size * height
        pixels = ctypes.create_string_buffer(image_size)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 24
        info.bmiHeader.biCompression = 0
        info.bmiHeader.biSizeImage = image_size
        if not gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixels, ctypes.byref(info), 0):
            raise OSError("GetDIBits failed while reading the screenshot bitmap.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_header_size = 14
        dib_header_size = 40
        pixel_offset = file_header_size + dib_header_size
        file_size = pixel_offset + image_size
        with output_path.open("wb") as handle:
            handle.write(struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset))
            handle.write(
                struct.pack(
                    "<IiiHHIIiiII",
                    dib_header_size,
                    width,
                    height,
                    1,
                    24,
                    0,
                    image_size,
                    0,
                    0,
                    0,
                    0,
                )
            )
            handle.write(pixels.raw)
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Screenshot capture failed: {exc}",
            "blocking_issues": [str(exc)],
        }
    finally:
        gdi32.SelectObject(memory_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(0, screen_dc)

    return {
        "ok": True,
        "message": "Screenshot evidence captured.",
        "width": width,
        "height": height,
        "blocking_issues": [],
    }


def _record_proof(
    *,
    proof_manifest: Path,
    evidence_path: Path,
    tester: str,
    notes: str,
    module_loads_in_game: bool,
    player_spawns_on_floor: bool,
    test_placeable_visible: bool,
    player_can_walk_on_floor: bool,
) -> dict[str, Any]:
    _install_payload_paths()
    proof = _load_proof(proof_manifest)
    task = str(proof.get("task") or "").upper()
    if task == "T2601":
        from src.core.modules.dev_module_smoke import DevModuleGameProofRequest, record_dev_module_game_proof  # noqa: WPS433

        result = record_dev_module_game_proof(
            DevModuleGameProofRequest(
                proof_manifest_path=str(proof_manifest),
                evidence_path=str(evidence_path),
                tester=tester,
                notes=notes,
                module_loads_in_game=module_loads_in_game,
                player_spawns_on_floor=player_spawns_on_floor,
                test_placeable_visible=test_placeable_visible,
                player_can_walk_on_floor=player_can_walk_on_floor,
            )
        )
    else:
        from src.core.modules.authored_module_export import AuthoredModuleGameProofRequest, record_authored_module_game_proof  # noqa: WPS433

        result = record_authored_module_game_proof(
            AuthoredModuleGameProofRequest(
                proof_manifest_path=str(proof_manifest),
                evidence_path=str(evidence_path),
                tester=tester,
                notes=notes,
                module_loads_in_game=module_loads_in_game,
                player_spawns_on_floor=player_spawns_on_floor,
                test_placeable_visible=test_placeable_visible,
                player_can_walk_on_floor=player_can_walk_on_floor,
            )
        )

    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "proof_manifest_path": result.proof_manifest_path,
        "pack_manifest_path": result.pack_manifest_path,
        "evidence_path": result.evidence_path,
        "missing_checks": list(result.missing_checks),
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
    }


def _summary(
    *,
    proof_manifest: Path,
    output_path: Path,
    capture: dict[str, Any],
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    ok = bool(capture.get("ok")) and (record is None or bool(record.get("ok")))
    next_action = (
        "Review the screenshot, verify the smoke-test checklist in-game, then rerun with "
        "`--record-proof --module-loads-in-game --player-spawns-on-floor --test-placeable-visible "
        "--player-can-walk-on-floor` to mark the package game-tested."
    )
    if record is not None and record.get("ok"):
        next_action = "Proof manifest updated; run the status checker to confirm the package is game-tested."
    return {
        "ok": ok,
        "code": "captured" if record is None else str(record.get("code") or "recorded"),
        "message": str(capture.get("message") or ""),
        "proof_manifest_path": str(proof_manifest),
        "evidence_path": str(output_path),
        "capture": capture,
        "record": record,
        "next_action": next_action,
        "blocking_issues": list(capture.get("blocking_issues", [])) + ([] if record is None else list(record.get("blocking_issues", []))),
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "INCOMPLETE"
    print(f"grdev01 evidence capture: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Proof manifest: {summary['proof_manifest_path']}")
    print(f"Evidence: {summary['evidence_path']}")
    record = summary.get("record")
    if isinstance(record, dict):
        print(f"Proof record: {record['code']}")
        if record.get("missing_checks"):
            print("Missing checks:")
            for check in record["missing_checks"]:
                print(f"- {check}")
    if summary["next_action"]:
        print(f"Next action: {summary['next_action']}")
    if summary["blocking_issues"]:
        print("Blocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    proof_manifest = args.proof_manifest
    output_path = args.output or _default_output_path(proof_manifest)
    capture = _capture_screen_bmp(output_path)
    record = None
    if capture.get("ok") and args.record_proof:
        record = _record_proof(
            proof_manifest=proof_manifest,
            evidence_path=output_path,
            tester=str(args.tester),
            notes=str(args.notes),
            module_loads_in_game=bool(args.module_loads_in_game),
            player_spawns_on_floor=bool(args.player_spawns_on_floor),
            test_placeable_visible=bool(args.test_placeable_visible),
            player_can_walk_on_floor=bool(args.player_can_walk_on_floor),
        )
    summary = _summary(proof_manifest=proof_manifest, output_path=output_path, capture=capture, record=record)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
