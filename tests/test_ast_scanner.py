"""
Unit tests for ast_scanner.extract_symbol_digest().
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src import ast_scanner  # noqa: E402


def _write_tmp(suffix: str, content: str, dir_: str) -> str:
    """Write content to a named temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix, dir=dir_)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestExtractSymbolDigest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # 1. Python function detection
    # ------------------------------------------------------------------
    def test_top_level_function(self) -> None:
        src = "def hello():\n    pass\n"
        path = _write_tmp(".py", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        symbols = result["symbols"]
        self.assertEqual(len(symbols), 1)
        sym = symbols[0]
        self.assertEqual(sym["name"], "hello")
        self.assertEqual(sym["kind"], "function")
        self.assertEqual(sym["line_start"], 1)
        self.assertEqual(sym["line_end"], 2)

    # ------------------------------------------------------------------
    # 2. Python class + method detection
    # ------------------------------------------------------------------
    def test_class_and_methods(self) -> None:
        src = (
            "class Foo:\n"
            "    def bar(self):\n"
            "        pass\n"
            "    def baz(self):\n"
            "        pass\n"
        )
        path = _write_tmp(".py", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        names = {s["name"]: s for s in result["symbols"]}

        self.assertIn("Foo", names)
        self.assertEqual(names["Foo"]["kind"], "class")

        self.assertIn("Foo.bar", names)
        self.assertEqual(names["Foo.bar"]["kind"], "method")

        self.assertIn("Foo.baz", names)
        self.assertEqual(names["Foo.baz"]["kind"], "method")

    # ------------------------------------------------------------------
    # 3. Module variable detection
    # ------------------------------------------------------------------
    def test_module_variable(self) -> None:
        src = "MY_VAR = 42\n"
        path = _write_tmp(".py", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        symbols = result["symbols"]
        self.assertEqual(len(symbols), 1)
        sym = symbols[0]
        self.assertEqual(sym["name"], "MY_VAR")
        self.assertEqual(sym["kind"], "variable")
        self.assertEqual(sym["line_start"], 1)
        self.assertEqual(sym["line_end"], 1)

    # ------------------------------------------------------------------
    # 4. Decorated function
    # ------------------------------------------------------------------
    def test_decorated_function(self) -> None:
        src = "@some_decorator\ndef foo():\n    pass\n"
        path = _write_tmp(".py", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        symbols = result["symbols"]
        self.assertEqual(len(symbols), 1)
        sym = symbols[0]
        self.assertEqual(sym["name"], "foo")
        self.assertEqual(sym["kind"], "function")
        # line_start must include the decorator (line 1)
        self.assertEqual(sym["line_start"], 1)
        self.assertEqual(sym["line_end"], 3)

    # ------------------------------------------------------------------
    # 5. _-prefix not filtered
    # ------------------------------------------------------------------
    def test_underscore_prefix_not_filtered(self) -> None:
        src = "def _private_func():\n    pass\n"
        path = _write_tmp(".py", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        names = [s["name"] for s in result["symbols"]]
        self.assertIn("_private_func", names)

    # ------------------------------------------------------------------
    # 6. Other language → skipped_language
    # ------------------------------------------------------------------
    def test_typescript_skipped_language(self) -> None:
        src = "export function hello(): void {}\n"
        path = _write_tmp(".ts", src, self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "skipped_language")
        self.assertEqual(result["symbols"], [])

    # ------------------------------------------------------------------
    # 7. Size limit exceeded → skipped_size
    # ------------------------------------------------------------------
    def test_size_limit_exceeded(self) -> None:
        src = "x = 1\n"
        path = _write_tmp(".py", src, self.tmpdir)
        # Pass max_file_size=0 to force the size check to trigger
        result = ast_scanner.extract_symbol_digest(path, max_file_size=0)

        self.assertEqual(result["parse_status"], "skipped_size")
        self.assertEqual(result["symbols"], [])

    # ------------------------------------------------------------------
    # 8. Nonexistent file → failed
    # ------------------------------------------------------------------
    def test_nonexistent_file_failed(self) -> None:
        path = os.path.join(self.tmpdir, "does_not_exist.py")
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "failed")
        self.assertEqual(result["symbols"], [])

    # ------------------------------------------------------------------
    # 9. Empty file → ok, no symbols
    # ------------------------------------------------------------------
    def test_empty_file_ok_no_symbols(self) -> None:
        path = _write_tmp(".py", "", self.tmpdir)
        result = ast_scanner.extract_symbol_digest(path)

        self.assertEqual(result["parse_status"], "ok")
        self.assertEqual(result["symbols"], [])


if __name__ == "__main__":
    unittest.main()
