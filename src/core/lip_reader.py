"""
lip_reader.py – GhostRigger-K1-K2  LIP (Lip Sync) File Reader/Writer
=====================================================================
Cross-referenced from:
  - PyKotor: Libraries/PyKotor/src/pykotor/resource/formats/lip/lip_data.py
  - KotOR.js: src/resource/LIPObject.ts

Binary Format (KotOR LIP V1.0):
  Header (16 bytes):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | char[] | File Type ("LIP ")
    0x04   | 4    | char[] | File Version ("V1.0")
    0x08   | 4    | float  | Sound Length (duration in seconds)
    0x0C   | 4    | uint32 | Entry Count (number of keyframes)

  Keyframe Entry (5 bytes each):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | float  | Time Stamp (seconds from start)
    0x04   | 1    | uint8  | Shape (mouth shape index, 0-15)

Lip Shapes (16 visemes – Preston Blair phoneme series):
  0  = NEUTRAL (rest)
  1  = EE (teeth slightly apart, "see")
  2  = EH (mouth relaxed, "bet")
  3  = AH (mouth open, "father")
  4  = OH (rounded lips, "boat")
  5  = OOH (pursed lips, "blue")
  6  = Y (slight smile, "you")
  7  = STS (teeth together, "stop")
  8  = FV (lower lip on upper teeth, "five")
  9  = NG (back of tongue up, "ring")
  10 = TH (tongue between teeth, "thin")
  11 = MPB (lips pressed, "bump")
  12 = TD (tongue up, "top")
  13 = SH (rounded relaxed, "measure")
  14 = L (tongue forward, "lip")
  15 = KG (back of tongue raised, "kick")

Usage:
  lip = LIPFile.from_file("path/to/file.lip")
  print(lip.duration, lip.keyframes)
  lip.to_file("output.lip")

  # Get interpolated shape at a specific time
  shape_data = lip.get_shapes(0.35)  # returns (left_shape, right_shape, factor)
"""

import struct
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import IntEnum

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
#  LIP Shape Enum (cross-ref: PyKotor LIPShape, KotOR.js GetLIPShapeLabels)
# ────────────────────────────────────────────────────────────────────

class LIPShape(IntEnum):
    """16 mouth shapes (visemes) for KotOR lip sync animation."""
    NEUTRAL = 0   # Rest position
    EE      = 1   # "see" – teeth apart, wide corners
    EH      = 2   # "bet" – relaxed, slightly open
    AH      = 3   # "father" – mouth open
    OH      = 4   # "boat" – rounded lips
    OOH     = 5   # "blue" – pursed lips
    Y       = 6   # "you" – slight smile
    STS     = 7   # "stop" – teeth together
    FV      = 8   # "five" – lower lip on upper teeth
    NG      = 9   # "ring" – back of tongue up
    TH      = 10  # "thin" – tongue between teeth
    MPB     = 11  # "bump" – lips pressed
    TD      = 12  # "top" – tongue up
    SH      = 13  # "measure" – rounded relaxed
    L       = 14  # "lip" – tongue forward
    KG      = 15  # "kick" – back of tongue raised

    @classmethod
    def label(cls, shape_id: int) -> str:
        """Return human-readable label for a shape index.
        Cross-ref: KotOR.js LIPObject.GetLIPShapeLabels()"""
        _LABELS = [
            "ee (teeth)",      "eh (bet, red)",    "schwa (sofa)",
            "ah (bat, cat)",   "oh (or, boat)",    "oo (blue) wh",
            "y (you)",         "s, ts",            "f, v",
            "n, ng",           "th",               "m, p, b",
            "t, d",            "j, sh",            "l, r",
            "k, g",
        ]
        if 0 <= shape_id < len(_LABELS):
            return _LABELS[shape_id]
        return f"shape_{shape_id}"

    @classmethod
    def from_phoneme(cls, phoneme: str) -> 'LIPShape':
        """Convert a phoneme string to its lip shape.
        Cross-ref: PyKotor lip_data.py LIPShape.from_phoneme()"""
        _MAP = {
            "AA": cls.AH,  "AE": cls.AH,  "AH": cls.AH,
            "AO": cls.OH,  "AW": cls.AH,  "AY": cls.AH,
            "B":  cls.MPB, "CH": cls.SH,  "D":  cls.TD,
            "DH": cls.TH,  "EH": cls.EH,  "ER": cls.EH,
            "EY": cls.EE,  "F":  cls.FV,  "G":  cls.KG,
            "HH": cls.KG,  "IH": cls.EE,  "IY": cls.EE,
            "JH": cls.SH,  "K":  cls.KG,  "L":  cls.L,
            "M":  cls.MPB, "N":  cls.NG,  "NG": cls.NG,
            "OW": cls.OH,  "OY": cls.OH,  "P":  cls.MPB,
            "R":  cls.L,   "S":  cls.STS, "SH": cls.SH,
            "T":  cls.TD,  "TH": cls.TH,  "UH": cls.OOH,
            "UW": cls.OOH, "V":  cls.FV,  "W":  cls.OOH,
            "Y":  cls.Y,   "Z":  cls.STS, "ZH": cls.SH,
            " ":  cls.NEUTRAL, "-": cls.NEUTRAL,
        }
        return _MAP.get(phoneme.upper(), cls.NEUTRAL)


# ────────────────────────────────────────────────────────────────────
#  LIP Keyframe + File structures
# ────────────────────────────────────────────────────────────────────

@dataclass
class LIPKeyFrame:
    """Single keyframe: timestamp + mouth shape.
    Binary: 4 bytes float + 1 byte uint8 = 5 bytes per entry."""
    time: float   # seconds from start of audio
    shape: int    # 0-15 (LIPShape enum value)

    def __lt__(self, other: 'LIPKeyFrame') -> bool:
        return self.time < other.time


@dataclass
class LIPFile:
    """KotOR LIP (Lip Sync) file container.

    Cross-ref:
      - PyKotor: LIP class in lip_data.py
      - KotOR.js: LIPObject class in LIPObject.ts
    """
    FILE_TYPE    = "LIP "
    FILE_VERSION = "V1.0"
    HEADER_SIZE  = 16
    MAX_SHAPES   = 16

    duration: float = 0.0
    keyframes: List[LIPKeyFrame] = field(default_factory=list)
    source_path: Optional[str] = None

    # ── Read ───────────────────────────────────────────────────────

    @classmethod
    def from_bytes(cls, data: bytes, source_path: str = None) -> 'LIPFile':
        """Parse LIP binary data.
        Cross-ref: KotOR.js LIPObject.readBinary() lines 99-125."""
        if len(data) < cls.HEADER_SIZE:
            log.warning(f"LIP data too short ({len(data)} bytes)")
            return cls(source_path=source_path)

        file_type = data[0:4].decode('ascii', errors='replace')
        file_ver  = data[4:8].decode('ascii', errors='replace')

        if file_type != cls.FILE_TYPE:
            log.warning(f"LIP: unexpected file type '{file_type}' (expected '{cls.FILE_TYPE}')")
        if file_ver != cls.FILE_VERSION:
            log.warning(f"LIP: unexpected version '{file_ver}' (expected '{cls.FILE_VERSION}')")

        duration, entry_count = struct.unpack_from('<fI', data, 8)

        keyframes = []
        offset = cls.HEADER_SIZE
        for i in range(entry_count):
            if offset + 5 > len(data):
                log.warning(f"LIP: truncated at keyframe {i}/{entry_count}")
                break
            time_stamp = struct.unpack_from('<f', data, offset)[0]
            shape      = data[offset + 4]  # uint8
            keyframes.append(LIPKeyFrame(time=time_stamp, shape=min(shape, 15)))
            offset += 5

        keyframes.sort()  # ensure time ordering
        lip = cls(duration=duration, keyframes=keyframes, source_path=source_path)
        log.debug(f"LIP: loaded {len(keyframes)} keyframes, duration={duration:.3f}s"
                  f" from {'bytes' if not source_path else source_path}")
        return lip

    @classmethod
    def from_file(cls, path: str) -> 'LIPFile':
        """Read a LIP file from disk."""
        with open(path, 'rb') as f:
            data = f.read()
        return cls.from_bytes(data, source_path=path)

    # ── Write ──────────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        """Serialize to LIP binary format.
        Cross-ref: KotOR.js LIPObject.toExportBuffer() lines 283-298."""
        self.keyframes.sort()  # ensure time ordering
        parts = [
            self.FILE_TYPE.encode('ascii'),
            self.FILE_VERSION.encode('ascii'),
            struct.pack('<f', self.duration),
            struct.pack('<I', len(self.keyframes)),
        ]
        for kf in self.keyframes:
            parts.append(struct.pack('<f', kf.time))
            parts.append(struct.pack('<B', min(kf.shape, 15)))
        return b''.join(parts)

    def to_file(self, path: str) -> None:
        """Write LIP file to disk."""
        data = self.to_bytes()
        with open(path, 'wb') as f:
            f.write(data)
        log.info(f"LIP: wrote {len(self.keyframes)} keyframes to {path}")

    # ── Interpolation (runtime playback) ───────────────────────────

    def get_shapes(self, time: float) -> Optional[Tuple[int, int, float]]:
        """Get interpolated shape data at a given time.
        Returns (left_shape, right_shape, interpolation_factor) or None.

        Cross-ref: KotOR.js LIPObject.update() lines 146-277
        Cross-ref: PyKotor LIP.get_shapes()

        The interpolation algorithm matches KotOR.js:
          1. Find the last keyframe at or before `time`
          2. Find the next keyframe after `time`
          3. Compute linear interpolation factor
        """
        if not self.keyframes:
            return None

        # Before first keyframe
        if time <= self.keyframes[0].time:
            s = self.keyframes[0].shape
            return (s, s, 0.0)

        # After last keyframe
        if time >= self.keyframes[-1].time:
            s = self.keyframes[-1].shape
            return (s, s, 0.0)

        # Find surrounding keyframes
        last_idx = 0
        for i, kf in enumerate(self.keyframes):
            if kf.time <= time:
                last_idx = i

        left  = self.keyframes[last_idx]
        right = self.keyframes[min(last_idx + 1, len(self.keyframes) - 1)]

        # Compute factor (matching KotOR.js line 192)
        dt = right.time - left.time
        if dt < 1e-6:
            factor = 0.0
        else:
            factor = (time - left.time) / dt
            factor = max(0.0, min(1.0, factor))

        return (left.shape, right.shape, factor)

    def get_shape_at_time(self, time: float) -> int:
        """Convenience: get single nearest shape at time."""
        result = self.get_shapes(time)
        if result is None:
            return LIPShape.NEUTRAL
        left, right, factor = result
        return right if factor > 0.5 else left

    # ── Editing ────────────────────────────────────────────────────

    def add_keyframe(self, time: float, shape: int) -> LIPKeyFrame:
        """Add a keyframe and maintain time ordering."""
        kf = LIPKeyFrame(time=time, shape=min(shape, 15))
        self.keyframes.append(kf)
        self.keyframes.sort()
        self.duration = max(self.duration, time)
        return kf

    def remove_keyframe(self, index: int) -> bool:
        """Remove keyframe at index."""
        if 0 <= index < len(self.keyframes):
            del self.keyframes[index]
            if self.keyframes:
                self.duration = max(kf.time for kf in self.keyframes)
            else:
                self.duration = 0.0
            return True
        return False

    def validate(self) -> List[str]:
        """Validate LIP data for common issues."""
        errors = []
        if not self.keyframes:
            errors.append("No keyframes defined")
            return errors
        for kf in self.keyframes:
            if kf.time < 0:
                errors.append(f"Negative time value: {kf.time}")
            if kf.shape < 0 or kf.shape > 15:
                errors.append(f"Shape out of range: {kf.shape}")
        prev_time = -1.0
        for kf in self.keyframes:
            if kf.time < prev_time:
                errors.append(f"Keyframes out of order: {kf.time} after {prev_time}")
            prev_time = kf.time
        return errors
