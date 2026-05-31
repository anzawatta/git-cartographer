"""
PreToolUse Hook — 踏破録スコア上位ファイルおよび安定層警告をコンテキストとして注入する。

stdin から JSON を受け取り、stdout に hookSpecificOutput 形式で additionalContext を返す。
エラー時は {"decision": "allow"} を返す（コンテキスト注入なし）。
"""

from __future__ import annotations

import json
import os
import sys

# @see ADR-004 §Backward Compatibility
_AGENT_ALLOWLIST = frozenset(["general-purpose", "critic"])
# Why: PATH_MAX is 4096 on Linux/macOS; guard against path traversal via oversized paths.
_PATH_MAX = 4096


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


# @see EARS-002#REQ-W004
def _validate_file_path(file_path: str) -> bool:
    """
    ファイルパスが安定層チェック対象として有効かを検証する。
    条件: 絶対パス・NUL バイトなし・PATH_MAX 以下。
    """
    if not os.path.isabs(file_path):
        return False
    if "\x00" in file_path:
        return False
    if len(file_path) > _PATH_MAX:
        return False
    return True


# @see EARS-002#REQ-E003
def _find_cartographer_state(start_dir: str) -> tuple[str, str] | None:
    """
    start_dir から上方に .cartographer_state を探索する。
    見つかった場合 (repo_root, output_dir) を返す。
    .cartographer_state が見つからない場合は None を返す。
    """
    current = os.path.abspath(start_dir)
    while True:
        state_path = os.path.join(current, ".cartographer_state")
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                # @see ADR-004 — maxsplit=2 で output_dir にスペースが含まれても安全に読む
                parts = content.split(maxsplit=2)
                if len(parts) >= 3:
                    output_dir = parts[2]
                else:
                    # @see ADR-004 §Backward Compatibility — 旧フォーマット fallback
                    output_dir = os.path.join(current, "output")
            except OSError:
                output_dir = os.path.join(current, "output")
            return current, output_dir
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# @see EARS-002#REQ-U003
def _compute_cochange_degree(cochange_jsonl_path: str, rel_path: str) -> int:
    """
    co-change.jsonl から対象ファイルの co-change 次数（distinct partner 数）を計算する。
    ファイルが存在しない・読み取れない場合は 0 を返す。
    """
    if not os.path.isfile(cochange_jsonl_path):
        return 0
    try:
        partners: set[str] = set()
        with open(cochange_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # スキップ: meta 行
                if record.get("_type") == "meta":
                    continue
                pair = record.get("pair", [])
                if len(pair) != 2:
                    continue
                if pair[0] == rel_path:
                    partners.add(pair[1])
                elif pair[1] == rel_path:
                    partners.add(pair[0])
        return len(partners)
    except OSError:
        return 0


# @see EARS-002#REQ-E004
def _build_ast_context(file_path: str) -> str | None:
    """
    file_path に対応する AST symbol digest を Markdown テーブルとして返す。
    エントリが存在しない・parse_status が ok でない・symbols が空の場合は None を返す。
    """
    if not _validate_file_path(file_path):
        return None

    state_result = _find_cartographer_state(os.path.dirname(file_path))
    if state_result is None:
        return None

    repo_root, output_dir = state_result

    # @see EARS-004
    # @see EARS-002#REQ-W005
    ast_digest_path = os.path.join(output_dir, "ast-digest.json")
    if not os.path.isfile(ast_digest_path):
        print(
            f"warning: ast-digest.json not found at {ast_digest_path};"
            " symbol resolution disabled."
            " → Fix: run cartographer first",
            file=sys.stderr,
        )
        return None

    try:
        with open(ast_digest_path, "r", encoding="utf-8") as f:
            digest_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    files = digest_data.get("files", [])
    if not files:
        return None

    try:
        rel_path = os.path.relpath(file_path, repo_root)
    except ValueError:
        return None

    # @see EARS-002#REQ-E004 — ファイル判定
    matched_entry = None
    for entry in files:
        if entry.get("path") == rel_path:
            matched_entry = entry
            break

    if matched_entry is None:
        return None

    # @see EARS-002#REQ-W006 — parse_status が ok でない場合、または symbols が空の場合はスキップ
    if matched_entry.get("parse_status") != "ok":
        return None

    symbols = matched_entry.get("symbols", [])
    if not symbols:
        return None

    # @see EARS-002#REQ-E004 — Markdown テーブル生成
    lines = [
        f"## Symbol Digest: {rel_path}",
        "",
        "| Name | Kind | Lines |",
        "|------|------|-------|",
    ]
    for sym in symbols:
        name = sym.get("name", "")
        kind = sym.get("kind", "")
        line_start = sym.get("line_start", "?")
        line_end = sym.get("line_end", "?")
        # Why: em-dash (–) matches the spec format; avoids confusion with hyphen ranges.
        lines.append(f"| `{name}` | {kind} | {line_start}–{line_end} |")

    lines += [
        "",
        "_このシンボルリストは git-cartographer の ast-digest.json から自動生成されています。_",
    ]
    return "\n".join(lines)


# @see EARS-002#REQ-E003
def _build_stable_warning(file_path: str) -> str | None:
    """
    file_path が安定層ファイルならば警告文字列を返す。それ以外は None を返す。
    """
    if not _validate_file_path(file_path):
        return None

    state_result = _find_cartographer_state(os.path.dirname(file_path))
    if state_result is None:
        return None

    repo_root, output_dir = state_result

    stable_json_path = os.path.join(output_dir, "stable.json")
    if not os.path.isfile(stable_json_path):
        return None

    try:
        with open(stable_json_path, "r", encoding="utf-8") as f:
            stable_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    load_bearing = stable_data.get("load_bearing", [])
    if not load_bearing:
        return None

    # file_path の repo_root からの相対パスを計算
    try:
        rel_path = os.path.relpath(file_path, repo_root)
    except ValueError:
        # Windows でドライブが異なる場合など
        return None

    # load_bearing に一致するエントリを探す
    matched_entry = None
    for entry in load_bearing:
        if entry.get("path") == rel_path:
            matched_entry = entry
            break

    if matched_entry is None:
        return None

    # @see EARS-002#REQ-U003 — co-change 次数計算
    cochange_jsonl_path = os.path.join(output_dir, "co-change.jsonl")
    degree = _compute_cochange_degree(cochange_jsonl_path, rel_path)

    # @see EARS-002#REQ-E003 — stability_score の null 対応
    raw_score = matched_entry.get("stability_score")
    score_str = f"{raw_score:.3f}" if raw_score is not None else "N/A"

    # @see EARS-002#REQ-E003 — カテゴリ判定と注入文言
    if degree >= 3:
        return (
            f"⚠️ 安定層: {rel_path} (stability_score: {score_str}, co-change: {degree})\n"
            f"荷重基盤 — 高結合。変更前に依存を確認。"
        )
    elif degree == 0:
        return (
            f"⚠️ 安定層: {rel_path} (stability_score: {score_str}, co-change: 0)\n"
            f"孤立安定 — 削除前に理由を確認。"
        )
    else:
        return f"⚠️ 安定層: {rel_path} (stability_score: {score_str}, co-change: {degree})"


def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)

        tool_name = event.get("tool_name", "")
        agent_type = event.get("agent_type", "")

        repo_root = _find_repo_root(os.getcwd())
        if repo_root is None:
            print(json.dumps({"decision": "allow"}))
            return

        # @see EARS-002#REQ-E002
        from src.traverse_log import top_files

        top = top_files(repo_root, n=10)
        traverse_context = _build_context(top)

        # @see EARS-002#REQ-E003 — stable layer warning (Read のみ、allowlist agent のみ)
        # @see EARS-002#REQ-E004 — AST symbol digest 注入 (Read のみ、allowlist agent のみ)
        # @see EARS-002#REQ-W003
        stable_warning = None
        ast_context = None
        if tool_name == "Read" and agent_type in _AGENT_ALLOWLIST:
            tool_input = event.get("tool_input", {})
            file_path = tool_input.get("file_path", "")
            if file_path:
                stable_warning = _build_stable_warning(file_path)
                ast_context = _build_ast_context(file_path)

        # コンテキスト合成: stable_warning → ast_context → traverse_context
        parts = []
        if stable_warning:
            parts.append(stable_warning)
        if ast_context:
            parts.append(ast_context)
        if traverse_context:
            parts.append(traverse_context)

        context = "\n\n".join(parts)
        # Why: additionalContext must be nested in hookSpecificOutput to inject into Claude's context window.
        # Top-level additionalContext is silently ignored. permissionDecision replaces the simple `decision` key.
        # @see https://docs.anthropic.com/en/docs/claude-code/hooks
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": context,
            }
        }))
        return

    except Exception:
        pass

    # @see EARS-002#REQ-S001
    # エラー時は allow で返す（Claude Code の処理を止めない）
    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
# DEBUG REMOVED
