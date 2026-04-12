"""
PreToolUse Hook — 踏破録スコア上位ファイルをコンテキストとして注入する。

stdin から JSON を受け取り、stdout に {"decision": "allow", "reason": "<context>"} を返す。
エラー時は {"decision": "allow", "reason": ""} を返す。
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


def _build_context(top: list[tuple[str, float]]) -> str:
    """踏破録上位ファイルを Markdown 形式のコンテキスト文字列に変換する。"""
    if not top:
        return ""

    lines = [
        "## Traverse Context",
        "",
        "最近アクセス頻度の高いファイル（踏破録上位）:",
        "",
        "| Score | File |",
        "|-------|------|",
    ]
    for path, score in top:
        lines.append(f"| {score:.3f} | `{path}` |")

    lines += [
        "",
        "_このリストは git-cartographer の踏破録から自動生成されています。_",
    ]
    return "\n".join(lines)


def main() -> None:
    try:
        raw = sys.stdin.read()
        # JSON パースのみ実施（tool_name等は現状では使用しない）
        json.loads(raw)

        repo_root = _find_repo_root(os.getcwd())
        if repo_root is None:
            print(json.dumps({"decision": "allow", "reason": ""}))
            return

        # @see EARS-002#REQ-E002
        from src.traverse_log import top_files

        top = top_files(repo_root, n=10)
        context = _build_context(top)

        print(json.dumps({"decision": "allow", "reason": context}))
        return

    except Exception:
        pass

    # @see EARS-002#REQ-E002
    # エラー時は allow で返す（Claude Code の処理を止めない）
    print(json.dumps({"decision": "allow", "reason": ""}))


if __name__ == "__main__":
    main()
