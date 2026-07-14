from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from src.core.assets.resource_manager import (
    EXT_TO_TYPE,
    TYPE_TO_EXT,
    RES_MP3,
    RES_WAV,
    _GameInstall,
    _key,
)


def _bare_install(game_dir: Path, tag: str) -> _GameInstall:
    install = _GameInstall.__new__(_GameInstall)
    install.game_dir = str(game_dir)
    install.tag = tag
    install._key_map = {}
    install._bif_index = {}
    install._tex_erfs = []
    install._mod_erfs = []
    install._override = {}
    install._loose_audio = {}
    return install


def test_game_install_defers_loose_audio_scan_until_audio_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scans: list[str] = []
    monkeypatch.setattr(
        _GameInstall,
        "_scan_loose_audio",
        lambda install: scans.append(install.tag),
    )

    install = _GameInstall(str(tmp_path), "K2")
    assert scans == []
    assert not install._loose_audio_indexed

    assert not install.has("missing_voice", RES_WAV)
    assert scans == ["K2"]
    assert install._loose_audio_indexed


@pytest.mark.parametrize(
    ("tag", "canonical_directory", "expected"),
    (
        ("K1", "sTrEaMwAvEs", b"k1-voice"),
        ("K2", "sTrEaMvOiCe", b"k2-voice"),
    ),
)
def test_case_insensitive_audio_directories_follow_target_game_precedence(
    tmp_path: Path,
    tag: str,
    canonical_directory: str,
    expected: bytes,
) -> None:
    voice = tmp_path / canonical_directory / "Module" / "Speaker"
    alternate_name = "StReAmVoIcE" if tag == "K1" else "StReAmWaVeS"
    alternate = tmp_path / alternate_name / "Fallback"
    sounds = tmp_path / "sTrEaMsOuNdS"
    voice.mkdir(parents=True)
    alternate.mkdir(parents=True)
    sounds.mkdir()

    (voice / "Shared_Line.WaV").write_bytes(expected)
    (alternate / "shared_line.wav").write_bytes(b"alternate-voice")
    (sounds / "SHARED_LINE.WAV").write_bytes(b"ambient-sound")
    (sounds / "ambient_only.wav").write_bytes(b"ambient-only")

    install = _bare_install(tmp_path, tag)

    class _Bif:
        def read(self, _index: int) -> bytes:
            return b"bif"

    shared_key = _key("shared_line", RES_WAV)
    ambient_key = _key("ambient_only", RES_WAV)
    install._key_map[shared_key] = (0, 1)
    install._key_map[ambient_key] = (0, 2)
    install._bif_index[0] = _Bif()
    install._index_loose_audio()

    # The target game's VO directory wins over the alternate directory,
    # StreamSounds, and BIF. StreamSounds still resolves unique ambient clips.
    assert install.get("SHARED_LINE", RES_WAV) == expected
    assert install.get("ambient_only", RES_WAV) == b"ambient-only"

    class _Module:
        def has(self, name: str, res_type: int) -> bool:
            return _key(name, res_type) == shared_key

        def read(self, name: str, res_type: int) -> bytes | None:
            return b"module" if self.has(name, res_type) else None

        def list_type(self, _res_type: int) -> list[str]:
            return []

    install._mod_erfs = [_Module()]
    assert install.get("shared_line", RES_WAV) == b"module"

    override = tmp_path / "override.wav"
    override.write_bytes(b"override")
    install._override[shared_key] = str(override)
    assert install.get("shared_line", RES_WAV) == b"override"


def test_loose_audio_index_is_path_only_and_keeps_mp3_resource_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    voice = tmp_path / "STREAMVOICE" / "003" / "PCDEAD"
    voice.mkdir(parents=True)
    wav_path = voice / "Mixed_Clip.WAV"
    mp3_path = voice / "Mixed_Clip.Mp3"
    mp3_only_path = voice / "MP3_Only.MP3"
    wav_path.write_bytes(b"wav-v1")
    mp3_path.write_bytes(b"mp3-v1")
    mp3_only_path.write_bytes(b"mp3-only")

    install = _bare_install(tmp_path, "K2")
    real_open = builtins.open
    monkeypatch.setattr(
        builtins,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("audio bytes must not be opened while indexing")
        ),
    )
    install._index_loose_audio()
    monkeypatch.setattr(builtins, "open", real_open)

    wav_key = _key("mixed_clip", RES_WAV)
    mp3_key = _key("mixed_clip", RES_MP3)
    assert EXT_TO_TYPE["mp3"] == RES_MP3
    assert TYPE_TO_EXT[RES_MP3] == "mp3"
    indexed_wav_path, indexed_wav_type = install._loose_audio[wav_key]
    indexed_mp3_path, indexed_mp3_type = install._loose_audio[mp3_key]
    assert Path(indexed_wav_path).samefile(wav_path)
    assert indexed_wav_type == RES_WAV
    assert Path(indexed_mp3_path).samefile(mp3_path)
    assert indexed_mp3_type == RES_MP3
    assert install.has("MIXED_CLIP", RES_WAV)
    assert install.has("MIXED_CLIP", RES_MP3)
    assert "mixed_clip" in install.list_resrefs(RES_WAV)
    assert "mixed_clip" in install.list_resrefs(RES_MP3)

    # WAV and MP3 never shadow each other, and bytes remain lazy after the scan.
    wav_path.write_bytes(b"wav-v2")
    mp3_path.write_bytes(b"mp3-v2")
    assert install.get("mixed_clip", RES_WAV) == b"wav-v2"
    assert install.get("mixed_clip", RES_MP3) == b"mp3-v2"
    assert install.get("mp3_only", RES_WAV) is None
    assert install.get("mp3_only", RES_MP3) == b"mp3-only"
