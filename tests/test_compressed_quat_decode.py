"""test_compressed_quat_decode.py — Phase G3 guard-rail
========================================================

Purpose
-------
Verifies the xoreos 11/11/10-bit packed quaternion decode formula produces
unit quaternions from known bit patterns.  This is the ``columnCount == 2``
branch of ``ModelNode_KotOR::readOrientationController`` in xoreos'
``model_kotor.cpp``:

    uint32_t temp = dataInt[dataIndex + r];
    q.x = 1.0f - float(temp        & 0x7FF) / 1023.0f;   // low  11 bits
    q.y = 1.0f - float((temp >> 11) & 0x7FF) / 1023.0f;   // mid  11 bits
    q.z = 1.0f - float((temp >> 22)       ) /  511.0f;    // high 10 bits
    float s = x*x + y*y + z*z;
    if (s < 1.0f)
        q.w = -sqrtf(1.0f - s);
    else {
        float m = sqrtf(s);
        q.x /= m; q.y /= m; q.z /= m;
        q.w  = 0.0f;
    }

Note: xoreos always emits **w <= 0**.  Per-rotation this is fine because q and
-q represent the same rotation.  Animation interpolation canonicalises the
sign via the ``if dot < 0: negate q2`` flip in the SLERP inner loop.

Why this test exists
--------------------
Compressed orientation keyframes are a known source of animation jitter when
the decode is subtly wrong (off-by-one bit shift, unsigned vs signed,
endianness, etc.).  We delegate the actual decode to PyKotor at runtime, but
this test locks in the **reference formula** so we can sanity-check any
future replacement (PyKotor update, custom reader, cross-validation against
KotorBlender) without requiring real MDL animation data on disk.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Reference decoder — mirrors xoreos model_kotor.cpp exactly
# ─────────────────────────────────────────────────────────────────────────────

def _decode_compressed_quat_xoreos(packed_u32: int):
    """Decode a 32-bit packed quaternion the way xoreos does.

    Parameters
    ----------
    packed_u32 : int
        Unsigned 32-bit integer holding 11|11|10 bits for (x, y, z).

    Returns
    -------
    tuple[float, float, float, float]
        (x, y, z, w) — a unit quaternion; ``w`` is always non-positive
        (xoreos convention).
    """
    packed_u32 &= 0xFFFFFFFF

    x = 1.0 - float(packed_u32 & 0x7FF) / 1023.0
    y = 1.0 - float((packed_u32 >> 11) & 0x7FF) / 1023.0
    z = 1.0 - float(packed_u32 >> 22) / 511.0

    s = x * x + y * y + z * z
    if s < 1.0:
        w = -math.sqrt(1.0 - s)
    else:
        m = math.sqrt(s)
        x /= m
        y /= m
        z /= m
        w = 0.0
    return (x, y, z, w)


def _pack_xyz_bits(bx: int, by: int, bz: int) -> int:
    """Pack 11|11|10 bits back into a uint32.  Inverse of the decoder above."""
    return (bx & 0x7FF) | ((by & 0x7FF) << 11) | ((bz & 0x3FF) << 22)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCompressedQuatDecode(unittest.TestCase):

    def test_identity_quaternion_decodes_to_neg_w(self):
        """Packed (bits_x=1023, bits_y=1023, bits_z=511) → (0, 0, 0, -1).

        That is the same rotation as the canonical identity (0, 0, 0, +1);
        the sign flip is a consequence of xoreos always taking
        ``w = -sqrt(...)``.  The animation system's SLERP sign canonicalisation
        handles the equivalence at interpolation time.
        """
        packed = _pack_xyz_bits(1023, 1023, 511)
        x, y, z, w = _decode_compressed_quat_xoreos(packed)
        self.assertAlmostEqual(x, 0.0, places=3)
        self.assertAlmostEqual(y, 0.0, places=3)
        self.assertAlmostEqual(z, 0.0, places=3)
        self.assertAlmostEqual(w, -1.0, places=3)

    def test_result_is_always_unit_quaternion(self):
        """Every decoded quaternion must have ‖q‖ ≈ 1."""
        test_patterns = [
            0x00000000,
            0x3FF7FE00,
            0x7FFFFFFF,
            0x1A2B3C4D,
            0x55555555,
            0xAAAAAAAA,
            0xFFFFFFFF,
            _pack_xyz_bits(0, 0, 0),
            _pack_xyz_bits(512, 512, 256),
            _pack_xyz_bits(1023, 0, 511),
        ]
        for packed in test_patterns:
            x, y, z, w = _decode_compressed_quat_xoreos(packed)
            mag = math.sqrt(x * x + y * y + z * z + w * w)
            self.assertAlmostEqual(
                mag, 1.0, places=3,
                msg=(
                    f"Packed 0x{packed:08X} decoded to "
                    f"({x:.4f}, {y:.4f}, {z:.4f}, {w:.4f}); "
                    f"magnitude = {mag:.6f}, expected ≈ 1."
                ),
            )

    def test_90deg_about_z_round_trip(self):
        """Encode the Z-axis 90° rotation, decode, verify the axis+angle.

        90° about Z is ``(0, 0, sin(45°), cos(45°)) = (0, 0, 0.7071, 0.7071)``.
        The encoder picks bits so decoded x and y are ≈ 0 and z is ≈ 0.7071.
        xoreos stores w as -sqrt(1 - x² - y² - z²) so the decoded w is
        ≈ -0.7071 — the antipodal of the canonical form but the same rotation.
        """
        bits_x = 1023                          # decoded x = 0
        bits_y = 1023                          # decoded y = 0
        bits_z = round((1.0 - 0.7071) * 511)   # decoded z ≈ 0.7071

        packed = _pack_xyz_bits(bits_x, bits_y, bits_z)
        x, y, z, w = _decode_compressed_quat_xoreos(packed)

        self.assertAlmostEqual(x, 0.0, places=2)
        self.assertAlmostEqual(y, 0.0, places=2)
        self.assertAlmostEqual(abs(z), 0.7071, places=2)
        self.assertAlmostEqual(abs(w), 0.7071, places=2)

        # Either (+z, -w) or (-z, +w) represents the same rotation.  xoreos
        # always picks w <= 0, so we expect z > 0 and w < 0 here.
        self.assertGreater(z, 0.0)
        self.assertLess(w, 0.0)

    def test_overflow_branch_produces_zero_w(self):
        """When x²+y²+z² >= 1, xoreos normalises (x,y,z) and sets w = 0.

        Pick ``bits = (0, 0, 0)`` → decoded (x, y, z) = (1, 1, 1), so
        s = 3 > 1 and the normalising branch fires.  Expected result:
        (x, y, z) scaled so x²+y²+z² = 1, and w = 0.
        """
        packed = _pack_xyz_bits(0, 0, 0)
        x, y, z, w = _decode_compressed_quat_xoreos(packed)

        inv3 = 1.0 / math.sqrt(3.0)
        self.assertAlmostEqual(x, inv3, places=4)
        self.assertAlmostEqual(y, inv3, places=4)
        self.assertAlmostEqual(z, inv3, places=4)
        self.assertEqual(w, 0.0)

    def test_bitfield_boundaries_are_independent(self):
        """Changing bits in one field must not leak into an adjacent field.

        Toggles the x-bits alone and confirms that y and z decode values
        remain pinned to their "zero-input" baseline.  This catches off-by-one
        shift errors like ``temp >> 10`` instead of ``temp >> 11``.
        """
        baseline = _pack_xyz_bits(1023, 1023, 511)       # decodes to (0,0,0,-1)
        perturbed = _pack_xyz_bits(0, 1023, 511)         # flips only x-bits

        bx, by, bz, _ = _decode_compressed_quat_xoreos(baseline)
        px, py, pz, _ = _decode_compressed_quat_xoreos(perturbed)

        self.assertAlmostEqual(bx, 0.0, places=4)
        self.assertAlmostEqual(px, 1.0, places=4)      # x changed
        self.assertAlmostEqual(by, py, places=4)       # y untouched
        self.assertAlmostEqual(bz, pz, places=4)       # z untouched


if __name__ == "__main__":
    unittest.main()
