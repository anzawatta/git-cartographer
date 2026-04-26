"""
config モジュールの単体テスト。

@see ADR-003
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

# tests/ から src/ をインポートできるよう、リポジトリルートを sys.path に追加
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src import config  # noqa: E402


class TestLoadConfigDefaults(unittest.TestCase):
    """設定ファイルが無い場合は組込デフォルトを返す。"""

    def test_no_config_file_returns_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_default_includes_typical_source_dirs(self) -> None:
        # 仕様: src / lib / lambda / packages / apps / services / functions
        for d in ["src", "lib", "lambda", "packages", "apps", "services", "functions"]:
            self.assertIn(d, config.DEFAULT_SCAN_DIRS)


class TestLoadConfigFromFile(unittest.TestCase):
    """`.cartographer.toml` がある場合は読み込む。"""

    def test_repo_root_toml_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write('[components]\nscan_dirs = ["src", "lambda"]\n')
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, ["src", "lambda"])

    def test_explicit_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, "custom.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write('[components]\nscan_dirs = ["packages"]\n')
            # repo_path は別ディレクトリでも config_path を優先する
            with tempfile.TemporaryDirectory() as repo_tmp:
                cfg = config.load_config(repo_tmp, config_path=toml_path)
        self.assertEqual(cfg.scan_dirs, ["packages"])

    def test_explicit_config_path_missing_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config.load_config(
                tmp, config_path=os.path.join(tmp, "no-such.toml")
            )
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_invalid_toml_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write("this is = not valid = toml\n")
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_components_table_without_scan_dirs_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write("[components]\n# scan_dirs intentionally absent\n")
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_scan_dirs_wrong_type_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write('[components]\nscan_dirs = "src"\n')
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_scan_dirs_empty_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write("[components]\nscan_dirs = []\n")
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, config.DEFAULT_SCAN_DIRS)

    def test_scan_dirs_normalizes_trailing_slash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            toml_path = os.path.join(tmp, ".cartographer.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write('[components]\nscan_dirs = ["src/", "lib"]\n')
            cfg = config.load_config(tmp)
        self.assertEqual(cfg.scan_dirs, ["src", "lib"])


if __name__ == "__main__":
    unittest.main()
