"""
components 軸の単体テスト。

@see ADR-003
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src import components  # noqa: E402


_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
    )


def _init_repo_with_files(repo: str, files: list[str]) -> None:
    """テスト用ミニ git リポジトリを作成し、files を tracked にする。

    `git config` はサンドボックス環境でブロックされるため、
    identity は GIT_AUTHOR_* / GIT_COMMITTER_* 環境変数で渡す。
    """
    _git(repo, "init", "-q")
    for f in files:
        full = os.path.join(repo, f)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as out:
            out.write("# placeholder\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init", "--no-gpg-sign")


class TestExtractComponentsPure(unittest.TestCase):
    """`_extract_components` の純粋関数テスト（git に依存しない）。"""

    def test_subdirectory_under_scan_dir_is_detected(self) -> None:
        files = ["src/foo/main.py", "src/bar/util.py"]
        result = components._extract_components(files, ["src"])
        self.assertEqual(
            result,
            [
                {"path": "src/bar", "scan_dir": "src", "name": "bar"},
                {"path": "src/foo", "scan_dir": "src", "name": "foo"},
            ],
        )

    def test_file_directly_under_scan_dir_is_skipped(self) -> None:
        # 直下ファイルはコンポーネントとしてカウントされない
        files = ["src/foo.py", "lib/index.ts"]
        result = components._extract_components(files, ["src", "lib"])
        self.assertEqual(result, [])

    def test_dir_outside_scan_dirs_is_skipped(self) -> None:
        files = ["docs/guide/intro.md", "src/foo/main.py"]
        result = components._extract_components(files, ["src"])
        self.assertEqual(
            result,
            [{"path": "src/foo", "scan_dir": "src", "name": "foo"}],
        )

    def test_cdk_pattern_lambda_dir_is_detected(self) -> None:
        # CDK 例: lib/foo-stack.ts は直下ファイルなので component ではない
        # lambda/foo/index.ts は components の対象
        files = [
            "lib/foo-stack.ts",
            "lib/bar-stack.ts",
            "lambda/foo/index.ts",
            "lambda/bar/handler.ts",
        ]
        result = components._extract_components(
            files, ["lib", "lambda"]
        )
        self.assertEqual(
            result,
            [
                {"path": "lambda/bar", "scan_dir": "lambda", "name": "bar"},
                {"path": "lambda/foo", "scan_dir": "lambda", "name": "foo"},
            ],
        )

    def test_duplicates_are_deduplicated(self) -> None:
        files = [
            "src/foo/a.py",
            "src/foo/b.py",
            "src/foo/sub/c.py",
        ]
        result = components._extract_components(files, ["src"])
        self.assertEqual(
            result,
            [{"path": "src/foo", "scan_dir": "src", "name": "foo"}],
        )

    def test_results_are_sorted(self) -> None:
        files = [
            "src/zeta/a.py",
            "src/alpha/a.py",
            "src/beta/a.py",
        ]
        result = components._extract_components(files, ["src"])
        names = [c["name"] for c in result]
        self.assertEqual(names, ["alpha", "beta", "zeta"])

    def test_multiple_scan_dirs(self) -> None:
        files = [
            "src/foo/a.py",
            "lib/bar/b.ts",
            "packages/baz/c.ts",
        ]
        result = components._extract_components(
            files, ["src", "lib", "packages"]
        )
        names = sorted(c["name"] for c in result)
        self.assertEqual(names, ["bar", "baz", "foo"])

    def test_normalized_scan_dir_with_trailing_slash(self) -> None:
        files = ["src/foo/a.py"]
        result = components._extract_components(files, ["src/"])
        self.assertEqual(
            result,
            [{"path": "src/foo", "scan_dir": "src", "name": "foo"}],
        )


class TestExtractComponentsNestedPaths(unittest.TestCase):
    """`_extract_components` のネストパス対応テスト。"""

    def test_nested_scan_dir_detects_component(self) -> None:
        """scan_dirs=["src/modules"] でネストパス内のコンポーネントが取れる。"""
        files = [
            "src/modules/my-component/index.ts",
            "src/modules/other/util.py",
        ]
        result = components._extract_components(files, ["src/modules"])
        self.assertEqual(
            sorted(result, key=lambda c: c["name"]),
            [
                {"path": "src/modules/my-component", "scan_dir": "src/modules", "name": "my-component"},
                {"path": "src/modules/other", "scan_dir": "src/modules", "name": "other"},
            ],
        )

    def test_deep_path_takes_priority_over_shallow(self) -> None:
        """scan_dirs=["src", "src/modules"] で深いパスが優先される。

        "src/modules/foo/bar.ts" は "src" ではなく "src/modules" に属する。
        """
        files = [
            "src/modules/foo/bar.ts",
            "src/other/main.py",
        ]
        result = components._extract_components(files, ["src", "src/modules"])
        # src/modules/foo は src/modules に属する（"src" ではない）
        foo_entry = next(c for c in result if c["name"] == "foo")
        self.assertEqual(foo_entry["scan_dir"], "src/modules")
        self.assertEqual(foo_entry["path"], "src/modules/foo")
        # src/other は "src" に属する（"src/modules" にはマッチしない）
        other_entry = next(c for c in result if c["name"] == "other")
        self.assertEqual(other_entry["scan_dir"], "src")

    def test_single_level_scan_dir_still_works(self) -> None:
        """単一レベル（"src"）は後方互換を保つ回帰テスト。"""
        files = [
            "src/foo/main.py",
            "src/bar/util.py",
            "lib/baz/index.ts",
        ]
        result = components._extract_components(files, ["src", "lib"])
        self.assertEqual(
            sorted(result, key=lambda c: c["path"]),
            [
                {"path": "lib/baz", "scan_dir": "lib", "name": "baz"},
                {"path": "src/bar", "scan_dir": "src", "name": "bar"},
                {"path": "src/foo", "scan_dir": "src", "name": "foo"},
            ],
        )

    def test_deeply_nested_scan_dir(self) -> None:
        """a/b/c のような深さ3以上のネストパスも有効。"""
        files = [
            "packages/shared/utils/index.ts",
            "packages/shared/helpers/format.ts",
            "packages/other/main.ts",
        ]
        result = components._extract_components(
            files, ["packages/shared", "packages"]
        )
        # packages/shared/utils → scan_dir=packages/shared
        utils_entry = next(c for c in result if c["name"] == "utils")
        self.assertEqual(utils_entry["scan_dir"], "packages/shared")
        # packages/other → scan_dir=packages
        other_entry = next(c for c in result if c["name"] == "other")
        self.assertEqual(other_entry["scan_dir"], "packages")


class TestBuildComponentsWithGit(unittest.TestCase):
    """`build_components` の統合テスト（実 git ls-files 経由）。"""

    def test_basic_detection_via_git_ls_files(self) -> None:
        with tempfile.TemporaryDirectory() as repo:
            _init_repo_with_files(
                repo,
                [
                    "src/foo/main.py",
                    "src/bar/util.py",
                    "docs/intro.md",
                    "README.md",
                ],
            )
            result = components.build_components(repo, ["src"])
        names = sorted(c["name"] for c in result)
        self.assertEqual(names, ["bar", "foo"])

    def test_gitignore_filters_subdirectory(self) -> None:
        """`.gitignore` で除外されたサブディレクトリは検出されない。"""
        with tempfile.TemporaryDirectory() as repo:
            # .gitignore で src/secret を除外
            os.makedirs(os.path.join(repo, "src", "secret"))
            os.makedirs(os.path.join(repo, "src", "ok"))
            with open(os.path.join(repo, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("src/secret/\n")
            with open(
                os.path.join(repo, "src", "secret", "key.py"), "w", encoding="utf-8"
            ) as f:
                f.write("KEY=1\n")
            with open(
                os.path.join(repo, "src", "ok", "main.py"), "w", encoding="utf-8"
            ) as f:
                f.write("# ok\n")
            _git(repo, "init", "-q")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "init", "--no-gpg-sign")

            result = components.build_components(repo, ["src"])
        names = [c["name"] for c in result]
        self.assertIn("ok", names)
        self.assertNotIn("secret", names)

    def test_empty_scan_dirs_yields_no_components(self) -> None:
        with tempfile.TemporaryDirectory() as repo:
            _init_repo_with_files(repo, ["src/foo/a.py"])
            result = components.build_components(repo, [])
        self.assertEqual(result, [])

    def test_scan_dirs_with_no_match_yields_no_components(self) -> None:
        with tempfile.TemporaryDirectory() as repo:
            _init_repo_with_files(repo, ["src/foo/a.py"])
            result = components.build_components(repo, ["nonexistent"])
        self.assertEqual(result, [])


class TestRenderComponentsJson(unittest.TestCase):
    """`render_components_json` の出力形式テスト。"""

    def test_payload_shape(self) -> None:
        scan_info = {
            "head_hash": "abc123",
            "generated_at": "2026-04-26T00:00:00+00:00",
        }
        comps = [{"path": "src/foo", "scan_dir": "src", "name": "foo"}]
        out = components.render_components_json(comps, scan_info, ["src"])
        parsed = json.loads(out)
        self.assertEqual(parsed["head"], "abc123")
        self.assertEqual(parsed["generated_at"], "2026-04-26T00:00:00+00:00")
        self.assertEqual(parsed["scan_dirs"], ["src"])
        self.assertEqual(parsed["components"], comps)


if __name__ == "__main__":
    unittest.main()
