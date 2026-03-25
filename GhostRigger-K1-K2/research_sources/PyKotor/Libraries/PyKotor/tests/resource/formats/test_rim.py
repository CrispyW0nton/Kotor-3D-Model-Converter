from __future__ import annotations

import os
import pathlib
import sys
import unittest

THIS_SCRIPT_PATH: pathlib.Path = pathlib.Path(__file__).resolve()
PYKOTOR_PATH: pathlib.Path = THIS_SCRIPT_PATH.parents[4].joinpath("src")
UTILITY_PATH: pathlib.Path = THIS_SCRIPT_PATH.parents[6].joinpath("Libraries", "Utility", "src")


def add_sys_path(p: pathlib.Path):
    working_dir = str(p)
    if working_dir not in sys.path:
        sys.path.append(working_dir)


if PYKOTOR_PATH.joinpath("pykotor").exists():
    add_sys_path(PYKOTOR_PATH)
if UTILITY_PATH.joinpath("utility").exists():
    add_sys_path(UTILITY_PATH)

from pykotor.resource.formats.rim import RIM, RIMBinaryReader, read_rim, write_rim
from pykotor.resource.type import ResourceType

# Inlined test.rim binary content
BINARY_TEST_DATA = b"RIM V1.0\x00\x00\x00\x00\x03\x00\x00\x00x\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x001\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x00\x00\x00\x00\xd8\x00\x00\x00\x03\x00\x00\x002\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\xdb\x00\x00\x00\x03\x00\x00\x003\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x02\x00\x00\x00\xde\x00\x00\x00\x03\x00\x00\x00abcdefghi"

# Inlined vanilla.rim binary content (Implicit 0 offsets)
VANILLA_BINARY_TEST_DATA = b"RIM V1.0\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x001\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x00\x00\x00\x00\xd8\x00\x00\x00\x03\x00\x00\x002\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\xdb\x00\x00\x00\x03\x00\x00\x003\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x02\x00\x00\x00\xde\x00\x00\x00\x03\x00\x00\x00abcdefghi"

# Inlined test_corrupted.rim binary content
CORRUPT_BINARY_TEST_DATA = b"RIM V1.0\x00\x00\x00\x00dgfgdfgfddg\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x001\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x00\x00\x00\x00\xd8\x00\x00\x00\x03\x00\x00\x002\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x01\x00\x00\x00\xdb\x00\x00\x00\x03\x00\x00\x003\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\x00\x00\x00\x02\x00\x00\x00\xde\x00\x00\x00\x03\x00\x00\x00abcdefghi"

DOES_NOT_EXIST_FILE = "./thisfiledoesnotexist"


class TestRIM(unittest.TestCase):
    def test_binary_io(self):
        """Test both standard and vanilla-compliant binary data through a full round-trip."""
        common_expected = {"1": b"abc", "2": b"def", "3": b"ghi"}
        scenarios = [
            ("Specified Offsets", BINARY_TEST_DATA, common_expected),
            ("Implicit Offsets", VANILLA_BINARY_TEST_DATA, common_expected),
        ]

        for name, data, expected in scenarios:
            with self.subTest(scenario=name):
                # Phase 1: Load and Validate
                rim: RIM = RIMBinaryReader(data).load()
                self.validate_io(rim, expected)

                # Phase 2: Save and Reload
                buffer: bytearray = bytearray()
                write_rim(rim, buffer)
                reloaded = read_rim(buffer)

                # Phase 3: Validate Reloaded
                self.validate_io(reloaded, expected)

    def test_file_io(self):
        """Test reading from a temporary file to ensure file-based reading still works."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".rim", delete=False) as tmp:
            tmp.write(BINARY_TEST_DATA)
            tmp_path = tmp.name

        try:
            rim: RIM = RIMBinaryReader(tmp_path).load()
            self.validate_io(rim, {"1": b"abc", "2": b"def", "3": b"ghi"})
        finally:
            os.unlink(tmp_path)

    def validate_io(self, rim: RIM, expected_content: dict[str, bytes]):
        """Helper to validate that a RIM object contains the expected resources and data."""
        self.assertEqual(len(rim), len(expected_content))
        for resref, data in expected_content.items():
            self.assertEqual(rim.get(resref, ResourceType.TXT), data)

    def test_read_raises(self):
        if os.name == "nt":
            self.assertRaises(PermissionError, read_rim, ".")
        else:
            self.assertRaises(IsADirectoryError, read_rim, ".")
        self.assertRaises(FileNotFoundError, read_rim, DOES_NOT_EXIST_FILE)
        self.assertRaises(ValueError, read_rim, CORRUPT_BINARY_TEST_DATA)

    def test_write_raises(self):
        if os.name == "nt":
            self.assertRaises(PermissionError, write_rim, RIM(), ".", ResourceType.RIM)
        else:
            self.assertRaises(IsADirectoryError, write_rim, RIM(), ".", ResourceType.RIM)
        self.assertRaises(ValueError, write_rim, RIM(), ".", ResourceType.INVALID)

    def test_malformed_header(self):
        """Test that malformed headers (entry count > 0, offset out of bounds) raise ValueError."""
        import struct

        # RIM (4) + V1.0 (4) + 0 (4) + 1 (4) + 1000 (4)
        header = b"RIM V1.0" + struct.pack("<I", 0) + struct.pack("<I", 1) + struct.pack("<I", 1000)
        header += b"\0" * (150 - len(header))
        self.assertRaises(ValueError, read_rim, header)


if __name__ == "__main__":
    unittest.main()
