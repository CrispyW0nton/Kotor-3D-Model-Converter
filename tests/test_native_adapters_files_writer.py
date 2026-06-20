from __future__ import annotations

import ctypes
import json
import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Adapters.Files.dll"


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_adapters_files_capabilities_json.argtypes = []
    dll.gr_adapters_files_capabilities_json.restype = ctypes.c_char_p
    dll.gr_adapters_files_write_bytes.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_size_t,
    ]
    dll.gr_adapters_files_write_bytes.restype = ctypes.c_int
    dll.gr_adapters_files_write_text_utf8.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    dll.gr_adapters_files_write_text_utf8.restype = ctypes.c_int
    write_text_fn = getattr(dll, "gr_adapters_files_write_text", None)
    if write_text_fn is not None:
        write_text_fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        write_text_fn.restype = ctypes.c_int
        dll.gr_adapters_files_write_text = write_text_fn
    return dll


def test_native_local_file_writer_writes_bytes_and_creates_parents(tmp_path: Path) -> None:
    dll = _load_dll()
    target = tmp_path / "nested" / "binary.bin"
    payload = b"\x00GhostRigger\xff"
    native_payload = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)

    assert dll.gr_adapters_files_write_bytes(str(target).encode("utf-8"), native_payload, len(payload)) == 1

    assert target.read_bytes() == payload


def test_native_local_file_writer_writes_utf8_text(tmp_path: Path) -> None:
    dll = _load_dll()
    target = tmp_path / "logs" / "message.txt"
    text = "GhostRigger native writer\n"

    assert dll.gr_adapters_files_write_text_utf8(str(target).encode("utf-8"), text.encode("utf-8")) == 1

    assert target.read_text(encoding="utf-8") == text


def test_native_local_file_writer_respects_encoding_argument(tmp_path: Path) -> None:
    dll = _load_dll()
    if not hasattr(dll, "gr_adapters_files_write_text"):
        pytest.skip("gr_adapters_files_write_text is not available in this build")
    target = tmp_path / "logs" / "message.txt"
    text = "GhostRigger encoding-aware writer\n"

    assert (
        dll.gr_adapters_files_write_text(str(target).encode("utf-8"), text.encode("utf-8"), b"utf-8") == 1
    )
    assert target.read_text(encoding="utf-8") == text
    assert (
        dll.gr_adapters_files_write_text(str(target).encode("utf-8"), text.encode("utf-8"), b"ascii") == 0
    )


def test_native_adapters_files_capabilities_document_writer_scope() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_adapters_files_capabilities_json().decode("utf-8"))
    assert capabilities["local_file_writer_native"] is True
    assert capabilities["local_file_writer_utf8_only"] is True
    assert capabilities["python_fallback_required"] is True
