"""Patch viewport.py to use pykotor for TPC loading."""
import re

with open('src/gui/viewport.py', 'r') as f:
    content = f.read()

# ── 1. Find boundaries ────────────────────────────────────────────────────────
old_load_start = content.index('\ndef _load_tpc_bytes(data: bytes)')
old_load_end_marker = '\n\ndef _extract_txi_from_tpc'
old_load_end = content.index(old_load_end_marker, old_load_start)

old_ext_start = old_load_end
old_ext_end_marker = '\n\n\n# ─────────────────────────────────────────────────────────────────────\n#  TXI Metadata Parser'
old_ext_end = content.index(old_ext_end_marker, old_ext_start)

old_load = content[old_load_start:old_load_end]
old_ext  = content[old_ext_start:old_ext_end]

print(f"_load_tpc_bytes: {old_load_start}-{old_load_end} ({len(old_load)} chars)")
print(f"_extract_txi_from_tpc: {old_ext_start}-{old_ext_end} ({len(old_ext)} chars)")

# ── 2. New pykotor-backed functions ───────────────────────────────────────────
NEW_LOAD_TPC = '''
def _load_tpc_bytes(data: bytes) -> Optional['Image.Image']:
    """Load a KotOR TPC image from raw bytes using pykotor's battle-tested reader.

    pykotor.read_tpc handles DXT1/DXT3/DXT5 decompression, greyscale, RGB/RGBA,
    cubemap slicing, and TXI extraction correctly across K1 and K2 content.
    Falls back to the legacy software decompressor if pykotor is unavailable.

    Returns a PIL RGBA Image (top-down orientation) or None on failure.
    """
    if not _PIL or not data or len(data) < 128:
        return None
    try:
        from pykotor.resource.formats.tpc.tpc_auto import read_tpc as _pk_read_tpc
        from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
        import io as _io
        tpc = _pk_read_tpc(_io.BytesIO(data))
        tpc.convert(TPCTextureFormat.RGBA)
        mip = tpc.get(0, 0)          # first layer, first (largest) mipmap
        img = mip.to_pil_image()
        if img is None:
            raise ValueError("pykotor returned None image")
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img
    except ImportError:
        pass  # pykotor not installed — fall through to legacy decoder
    except Exception as e:
        log.debug(f"pykotor TPC load failed ({e}), trying legacy decoder")
    # ── Legacy software decoder (fallback when pykotor is unavailable) ────────
    return _load_tpc_bytes_legacy(data)
'''

NEW_EXTRACT_TXI = '''

def _extract_txi_from_tpc(data: bytes) -> str:
    """Extract TXI metadata string from TPC binary data.

    Uses pykotor.read_tpc() which correctly parses the TXI trailer embedded
    after all mipmap pixel data.  Falls back to manual extraction if pykotor
    is unavailable.

    Returns the TXI string (may be empty if none present).
    """
    if not data or len(data) < 128:
        return ''
    try:
        from pykotor.resource.formats.tpc.tpc_auto import read_tpc as _pk_read_tpc
        import io as _io
        tpc = _pk_read_tpc(_io.BytesIO(data))
        txi = tpc.txi or ''
        return txi.strip() if isinstance(txi, str) else ''
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"pykotor TXI extraction error: {e}")
    # Fallback: manual TXI extraction (legacy method)
    return _extract_txi_from_tpc_legacy(data)
'''

# ── 3. Rename old functions to _legacy variants ───────────────────────────────
old_load_renamed = old_load.replace(
    "def _load_tpc_bytes(data: bytes) -> Optional['Image.Image']:",
    "def _load_tpc_bytes_legacy(data: bytes) -> Optional['Image.Image']:\n"
    "    # Legacy software TPC decoder — used as fallback when pykotor unavailable."
)

old_ext_renamed = old_ext.replace(
    "def _extract_txi_from_tpc(data: bytes) -> str:",
    "def _extract_txi_from_tpc_legacy(data: bytes) -> str:\n"
    "    # Legacy manual TXI extraction — fallback when pykotor unavailable."
)

# ── 4. Assemble and write ─────────────────────────────────────────────────────
new_block = NEW_LOAD_TPC + NEW_EXTRACT_TXI + '\n' + old_load_renamed + old_ext_renamed
new_content = content[:old_load_start] + new_block + content[old_ext_end:]

with open('src/gui/viewport.py', 'w') as f:
    f.write(new_content)

print(f"Done. Old: {len(content)} chars -> New: {len(new_content)} chars")
print(f"Delta: {len(new_content)-len(content):+d} chars")
