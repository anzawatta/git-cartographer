"""
PostToolUse Hook — アクセスされたファイルを踏破録に記録する。

stdin から JSON を受け取り、stdout に {"success": true} を返す。
エラーは握りつぶす（Claude Code の処理を止めない）。
"""

from __future__ import annotations

import json
import os
import sys


def _find_repo_root(start_path: str) -> str | None:
    """git リポジトリのルートディレクトリを探す。"""
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        # @see EARS-002#REQ-E001
        # 対象ツール: Read, Edit, Write のみ（Bash は パス不確定のため skip）
        if tool_name not in ("Read", "Edit", "Write"):
            print(json.dumps({"success": True}))
            return

        file_path = tool_input.get("file_path", "")
        if not file_path:
            print(json.dumps({"success": True}))
            return

        # リポジトリルートを特定
        repo_root = _find_repo_root(os.getcwd())
        if repo_root is None:
            print(json.dumps({"success": True}))
            return

        # @see EARS-002#REQ-E001
        # HEAD ハッシュを取得して踏破録に記録
        # ハッシュが取得できない場合は記録しない（decay 計算に無効値を混入させない）
        from src.git_scanner import get_head_hash
        from src.traverse_log import record

        try:
            current_hash = get_head_hash(repo_root)
        except RuntimeError:
            # git コマンド失敗時は記録を中断（無効なハッシュで踏破録を汚染しない）
            print(json.dumps({"success": True}))
            return

        # ファイルパスの安全性チェック: repo_root 配下のファイルのみ記録
        abs_file_path = os.path.realpath(os.path.abspath(file_path))
        abs_repo_root = os.path.realpath(repo_root)
        if not abs_file_path.startswith(abs_repo_root + os.sep) and abs_file_path != abs_repo_root:
            # リポジトリ外のパスは記録しない（Trust Boundary 保護）
            print(json.dumps({"success": True}))
            return

        # ファイルパスをリポジトリ相対パスに変換
        try:
            rel_path = os.path.relpath(file_path, repo_root)
        except ValueError:
            rel_path = file_path

        record(repo_root, rel_path, current_hash)

    except Exception:
        # エラーは全て握りつぶす
        pass

    print(json.dumps({"success": True}))


if __name__ == "__main__":
    main()
