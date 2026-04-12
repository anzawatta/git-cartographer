"""
git-cartographer エントリーポイント。

フルスキャン / 差分スキャンを判定し、3層地図を生成する。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from src import ast_scanner, git_scanner, layers, traverse_log, state


def _resolve_output_dir(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _write_markdown(output_dir: str, filename: str, content: str) -> None:
    # @see EARS-001#REQ-U001
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Written: {path}")


def _build_import_graph(
    repo_path: str,
    file_list: list[str],
) -> dict[str, list[str]]:
    """ファイルリストから import グラフを構築する。"""
    graph: dict[str, list[str]] = {}
    for rel_path in file_list:
        abs_path = os.path.join(repo_path, rel_path)
        if os.path.isfile(abs_path):
            imports = ast_scanner.extract_imports(abs_path)
            if imports:
                graph[rel_path] = imports
    return graph


def _load_previous_stable(output_dir: str) -> list[str]:
    """
    前回生成した stable.md から安定ファイルリストを読み込む。

    stable.md 内の `- \`filepath\`` 形式の行を解析する。
    ファイルが存在しない場合は空リストを返す。
    """
    stable_path = os.path.join(output_dir, "stable.md")
    if not os.path.isfile(stable_path):
        return []
    files: list[str] = []
    with open(stable_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # "- `filepath`" パターンを抽出
            if line.startswith("- `") and line.endswith("`"):
                files.append(line[3:-1])
    return files


def _all_tracked_files(repo_path: str) -> list[str]:
    """git 管理下の全ファイルを返す。"""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


# @see EARS-001#REQ-S001
# @see EARS-001#REQ-S002
def run(
    repo_path: str,
    output_dir: str,
    window: int = 100,
) -> None:
    """
    地図生成のメインロジック。

    1. state.get_last_hash() で差分/フルスキャン判定
    2. git_scanner でチャーン・co-change 取得
    3. ast_scanner で依存・面積取得
    4. layers で3層地図生成
    5. traverse_log.decay_all で踏破録更新
    6. output/ に Markdown 書き出し
    7. state.set_last_hash() 更新
    """
    repo_path = os.path.abspath(repo_path)
    output_dir = _resolve_output_dir(os.path.join(repo_path, output_dir))

    print(f"[cartographer] repo: {repo_path}")

    # HEAD ハッシュを取得
    try:
        head_hash = git_scanner.get_head_hash(repo_path)
    except RuntimeError as e:
        print(f"[ERROR] git rev-parse failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[cartographer] HEAD: {head_hash[:12]}")

    # スキャンモード判定
    last_hash = state.get_last_hash(repo_path)

    # @see EARS-001#REQ-S001
    if last_hash is None:
        print("[cartographer] Mode: FULL SCAN (no state file)")
        scan_mode = "full"
        since_hash = None
    # @see EARS-001#REQ-S002
    else:
        print(f"[cartographer] Mode: INCREMENTAL (since {last_hash[:12]})")
        scan_mode = "incremental"
        since_hash = last_hash

    generated_at = datetime.now(timezone.utc).isoformat()
    scan_info = {
        "mode": scan_mode,
        "head_hash": head_hash,
        "generated_at": generated_at,
    }

    # git churn 分析
    print("[cartographer] Analyzing churn...")
    try:
        churn = git_scanner.churn_counts(
            repo_path,
            since_hash=since_hash,
            until_hash="HEAD",
            window=window,
        )
    except RuntimeError as e:
        print(f"[ERROR] churn analysis failed: {e}", file=sys.stderr)
        churn = {}

    # co-change 分析
    print("[cartographer] Analyzing co-change pairs...")
    try:
        cochange = git_scanner.cochange_pairs(
            repo_path,
            since_hash=since_hash,
            until_hash="HEAD",
        )
    except RuntimeError as e:
        print(f"[WARNING] co-change analysis failed: {e}", file=sys.stderr)
        cochange = {}

    # 解析対象ファイルリストを構築
    if scan_mode == "full":
        file_list = _all_tracked_files(repo_path)
    else:
        try:
            file_list = git_scanner.diff_files(repo_path, since_hash, "HEAD")
        except RuntimeError as e:
            print(f"[WARNING] diff_files failed: {e}", file=sys.stderr)
            file_list = []

    # @see EARS-001#REQ-S003
    # フルスキャン時: 全追跡ファイルのうち churn=0 のものを stable 候補として補完
    # incremental 時: 既存 stable リストから今回変更されたファイルを除外して引き継ぐ
    if scan_mode == "full":
        for f in file_list:
            if f not in churn:
                churn[f] = 0
    else:
        # 前回の stable.md から既存の stable ファイルリストを読み込む
        previous_stable = _load_previous_stable(output_dir)
        # 今回変更されたファイルを stable から除外（0 超の churn を持つ）
        changed_files = set(f for f, cnt in churn.items() if cnt > 0)
        surviving_stable = [f for f in previous_stable if f not in changed_files]
        # surviving_stable を churn dict に churn=0 として登録（build_stable が認識できるよう）
        for f in surviving_stable:
            if f not in churn:
                churn[f] = 0

    # AST 依存グラフ構築
    print(f"[cartographer] Building import graph ({len(file_list)} files)...")
    import_graph = _build_import_graph(repo_path, file_list)

    # 3層地図生成
    print("[cartographer] Building layers...")

    # @see EARS-001#REQ-S003
    stable_files = layers.build_stable(churn, threshold=0)
    structure_data = layers.build_structure(churn, cochange, import_graph)
    hotspots_data = layers.build_hotspots(churn, top_n=20)

    # Markdown 書き出し
    print("[cartographer] Writing output...")

    # @see EARS-001#REQ-U001
    _write_markdown(output_dir, "stable.md", layers.render_stable(stable_files, scan_info))
    _write_markdown(output_dir, "structure.md", layers.render_structure(structure_data, scan_info))
    _write_markdown(output_dir, "hotspots.md", layers.render_hotspots(hotspots_data, scan_info))

    # 踏破録の減衰更新
    print("[cartographer] Decaying traverse_log entries...")
    try:
        traverse_log.decay_all(repo_path, head_hash)
    except Exception as e:
        print(f"[WARNING] traverse_log decay failed: {e}", file=sys.stderr)

    # ステートファイル更新
    # @see EARS-001#REQ-S001
    state.set_last_hash(head_hash, repo_path)
    print(f"[cartographer] State updated: {head_hash[:12]}")
    print("[cartographer] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="git-cartographer: コードベースの地図を自動生成する測量機械"
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="解析対象のリポジトリパス（デフォルト: カレントディレクトリ）",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="出力ディレクトリ（リポジトリ相対、デフォルト: output）",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=100,
        help="フルスキャン時に参照するコミット数（デフォルト: 100）",
    )

    args = parser.parse_args()
    run(args.repo_path, args.output_dir, args.window)


if __name__ == "__main__":
    main()
