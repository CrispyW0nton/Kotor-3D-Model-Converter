from __future__ import annotations

import pathlib
import sys
import unittest

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    import charset_normalizer

THIS_SCRIPT_PATH = pathlib.Path(__file__).resolve()
PYKOTOR_PATH = THIS_SCRIPT_PATH.parents[3].joinpath("src")
UTILITY_PATH = THIS_SCRIPT_PATH.parents[5].joinpath("Libraries", "Utility", "src")


def add_sys_path(p: pathlib.Path):
    working_dir = str(p)
    if working_dir not in sys.path:
        sys.path.append(working_dir)


if PYKOTOR_PATH.joinpath("pykotor").exists():
    add_sys_path(PYKOTOR_PATH)
if UTILITY_PATH.joinpath("utility").exists():
    add_sys_path(UTILITY_PATH)

from pykotor.common.language import Language  # noqa: E402
from pykotor.tools.encoding import decode_bytes_with_fallbacks  # noqa: E402

charset_normalizer: None | ModuleType
try:
    import charset_normalizer
except ImportError:
    charset_normalizer = None



class TestDecodeBytes(unittest.TestCase):
    def test_basic(self):
        byte_str = b"hello world"
        result = decode_bytes_with_fallbacks(byte_str)
        assert result == "hello world"

    def test_non_ascii(self):
        byte_str = b"h\xc3\xa9llo w\xc3\xb6rld"
        result = decode_bytes_with_fallbacks(byte_str)
        assert result == "héllo wörld"

    def test_unknown_encoding(self):
        byte_str = b"\x80\x81\x82"
        with self.assertRaises(UnicodeDecodeError):
            byte_str.decode()
        result = byte_str.decode(errors="replace")
        assert result == "���"
        result = decode_bytes_with_fallbacks(byte_str, errors="replace")
        assert result == "Øab"

    def test_bom(self):
        byte_str = b"\xef\xbb\xbfhello world"
        result = byte_str.decode("utf-8-sig")
        assert result == "hello world"
        result = decode_bytes_with_fallbacks(byte_str)
        assert result == "hello world"

    def test_errors_replace(self):
        byte_str = b"h\xc3\xa9llo"
        # self.assertEqual(byte_str.decode(errors="replace"), "h?llo")
        assert byte_str.decode(errors="replace") == "héllo"

        result = decode_bytes_with_fallbacks(byte_str, errors="replace")
        assert result == "héllo"

    def test_known_encoding(self):
        byte_content = b"Hello, World!"
        errors = "strict"
        encoding = "utf-8"
        lang = None
        only_8bit_encodings = False
        expected_result = "Hello, World!"

        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result

    def test_language_provided(self):
        byte_content = b"Bonjour le monde!"
        errors = "strict"
        encoding = None
        lang = Language.FRENCH
        only_8bit_encodings = False
        expected_result = "Bonjour le monde!"

        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result

    def test_language_detect(self):
        byte_content = b"Bonjour le monde!"
        errors = "strict"
        encoding = None
        lang = None
        only_8bit_encodings = False
        expected_result = "Bonjour le monde!"

        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result

    def test_invalid_bytes_for_encoding(self):
        byte_content = b"\xff\xfe\x00"
        errors = "replace"
        encoding = "utf-8"
        lang = None
        only_8bit_encodings = False
        expected_result = "\ufffd\ufffd"
        result = byte_content.decode(encoding, errors)
        assert result == "��\x00"

        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result in {"��\x00", "ÿþ\x00"}

    @unittest.skip("skipped - not ready for full test execution")
    def test_fallback_to_detected_encoding(self):
        byte_content = b"\xc2\xa1Hola!"
        errors = "strict"
        encoding = None
        lang = None
        only_8bit_encodings = False
        expected_result = "¡Hola!"
        exp = "癒Hola!"
        exp2 = "Â¡Hola!"

        result = byte_content.decode(errors=errors)
        assert result == expected_result
        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == (exp2 if charset_normalizer is None else exp)

    def test_8bit_encoding_only(self):
        byte_content = b"\xe4\xf6\xfc"
        errors = "strict"
        encoding = None
        lang = None
        only_8bit_encodings = True
        expected_result = "���"
        exp = "U6Ü"
        exp2 = "дць"

        result = byte_content.decode(errors="replace")
        assert result == expected_result
        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == (exp2 if charset_normalizer is None else exp)

    def test_with_BOM_included(self):
        byte_content = b"\xef\xbb\xbfTest"
        errors = "strict"
        encoding = None
        lang = None
        only_8bit_encodings = False
        expected_result = "Test"

        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result

    def test_undetectable_encoding_replace_errors(self):
        byte_content = b"\x80\x81\x82"
        errors = "replace"
        encoding = None
        lang = None
        only_8bit_encodings = False
        expected_result = "\ufffd\ufffd\ufffd"
        exp = "Øab"

        result = byte_content.decode(errors=errors)
        assert result == expected_result
        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == exp

    def test_strict_error_handling_decoding_failure(self):
        byte_content = b"\x80\x81\x82"
        errors = "strict"
        encoding = "ascii"
        lang = None
        only_8bit_encodings = False
        expected_result = "Øab"
        with self.assertRaises(UnicodeDecodeError):
            decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
            byte_content.decode(errors=errors)
        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result

    def test_no_valid_encoding_found_strict_errors(self):
        byte_content = b"\x80\x81\x82"
        errors = "strict"
        encoding = None
        lang = None
        only_8bit_encodings = False
        expected_result = "Øab"
        with self.assertRaises(UnicodeDecodeError):
            byte_content.decode(errors=errors)
        result = decode_bytes_with_fallbacks(byte_content, errors, encoding, lang, only_8bit_encodings)
        assert result == expected_result
