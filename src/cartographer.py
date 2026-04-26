"""
git-cartographer エントリーポイント。

常に最新 window コミットをスキャンし、3層地図を生成する。
.cartographer_state は HEAD 未変更時のスキップ最適化としてのみ使用する。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from src import ast_scanner, components as components_axis, config as config_module, git_scanner, layers, traverse_log, state


def _resolve_output_dir(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _write_file(output_dir: str, filename: str, content: str) -> None:
    # @see EARS-001#REQ-U001
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Written: {path}")


# Alias for backward compatibility and clarity
_write_markdown = _write_file


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
    include_stdlib: bool = False,
    markdown: bool = False,
    halflife_commits: int = 90,
    config_path: str | None = None,
) -> None:
    """
    地図生成のメインロジック。

    1. state.get_last_hash() で差分/フルスキャン判定
    2. git_scanner でチャーン・co-change 取得
    3. ast_scanner で依存・面積取得
    4. layers で3層地図生成
    5. traverse_log.decay_all で踏破録更新
    6. output/ に JSON 書き出し（常時）、Markdown 書き出し（markdown=True 時のみ）
    7. state.set_last_hash() 更新
    """
    repo_path = os.path.abspath(repo_path)
    if os.path.isabs(output_dir):
        output_dir = _resolve_output_dir(output_dir)
    else:
        output_dir = _resolve_output_dir(os.path.join(repo_path, output_dir))

    print(f"[cartographer] repo: {repo_path}")

    # 設定ファイル読み込み（components 軸用 / scan_dirs 取得）
    # @see ADR-003
    cfg = config_module.load_config(repo_path, config_path=config_path)
    print(f"[cartographer] scan_dirs: {cfg.scan_dirs}")

    # HEAD ハッシュを取得
    # @see EARS-001#REQ-C001
    # @see EARS-001#REQ-C002
    # @see EARS-001#REQ-C003
    try:
        head_hash = git_scanner.get_head_hash(repo_path)
    except RuntimeError as e:
        print(f"[WARNING] git rev-parse failed (no history?): {e}", file=sys.stderr)
        print("[cartographer] Cold start: no git history detected. Writing empty JSON outputs.")
        generated_at = datetime.now(timezone.utc).isoformat()
        _write_file(output_dir, "co-change.jsonl", "")
        _write_file(output_dir, "hotspot.json", json.dumps(
            {"status": "no_history", "generated_at": generated_at, "ranking": []},
            ensure_ascii=False, indent=2,
        ))
        _write_file(output_dir, "stable.json", json.dumps(
            {"status": "no_history", "generated_at": generated_at, "load_bearing": []},
            ensure_ascii=False, indent=2,
        ))
        # @see ADR-003 — components 軸も cold start で空出力を保証
        _write_file(output_dir, "components.json", json.dumps(
            {
                "status": "no_history",
                "generated_at": generated_at,
                "scan_dirs": list(cfg.scan_dirs),
                "components": [],
            },
            ensure_ascii=False, indent=2,
        ))
        print("[cartographer] Done (cold start).")
        return

    print(f"[cartographer] HEAD: {head_hash[:12]}")

    # スキップ判定: HEAD が前回と同じなら何もしない
    # @see EARS-001#REQ-S001
    last_hash = state.get_last_hash(repo_path)
    if last_hash == head_hash:
        print("[cartographer] HEAD unchanged. Skipping.")
        return

    # 常に window ベースのスキャン
    # @see EARS-001#REQ-S002
    print(f"[cartographer] Scanning last {window} commits (HEAD: {head_hash[:12]})")

    generated_at = datetime.now(timezone.utc).isoformat()
    scan_info = {
        "window": window,
        "head_hash": head_hash,
        "generated_at": generated_at,
        "halflife_commits": halflife_commits,
    }

    # git churn 分析（since_hash=None で常に window ベース）
    print("[cartographer] Analyzing churn...")
    try:
        churn = git_scanner.churn_counts(
            repo_path,
            since_hash=None,
            until_hash="HEAD",
            window=window,
        )
    except RuntimeError as e:
        print(f"[ERROR] churn analysis failed: {e}", file=sys.stderr)
        churn = {}

    # co-change 分析（window パラメータを渡す）
    print("[cartographer] Analyzing co-change pairs...")
    try:
        cochange = git_scanner.cochange_pairs(
            repo_path,
            since_hash=None,
            until_hash="HEAD",
            window=window,
        )
    except RuntimeError as e:
        print(f"[WARNING] co-change analysis failed: {e}", file=sys.stderr)
        cochange = {}

    # 全追跡ファイルを対象に、churn=0 を補完（安定ファイル検出のため）
    # @see EARS-001#REQ-S003
    file_list = _all_tracked_files(repo_path)
    for f in file_list:
        if f not in churn:
            churn[f] = 0

    # AST 依存グラフ構築
    print(f"[cartographer] Building import graph ({len(file_list)} files)...")
    import_graph = _build_import_graph(repo_path, file_list)

    # 3層地図生成
    print("[cartographer] Building layers...")

    # @see EARS-001#REQ-S003
    stable_files = layers.build_stable(churn, threshold=0)
    structure_data = layers.build_structure(churn, cochange, import_graph, include_stdlib=include_stdlib)
    hotspots_data = layers.build_hotspots(churn, top_n=20)

    # components 軸（第4軸）: scan_dirs 配下の直下サブディレクトリ一覧
    # @see ADR-003
    components_data = components_axis.build_components(repo_path, cfg.scan_dirs)
    if len(components_data) > components_axis.COMPONENT_WARN_THRESHOLD:
        print(
            f"[cartographer] WARNING: components count ({len(components_data)}) "
            f"exceeds threshold ({components_axis.COMPONENT_WARN_THRESHOLD}). "
            f"Consider narrowing scan_dirs in .cartographer.toml.",
            file=sys.stderr,
        )

    # effective_weight 計算（top20 ペア分）
    print("[cartographer] Computing effective_weight for co-change pairs...")
    cochange_top = structure_data.get("cochange_top", [])
    cochange_weight_map: dict[tuple[str, str], dict] = {}
    for a, b, cnt, last_hash in cochange_top:
        try:
            commits_elapsed = git_scanner.count_commits_between(repo_path, last_hash, head_hash)
            ew = cnt * (0.5 ** (commits_elapsed / halflife_commits))
        except Exception as e:
            print(f"[cartographer] effective_weight計算失敗 ({a}, {b}): {e}", file=sys.stderr)
            ew = None
        cochange_weight_map[(a, b)] = {
            "effective_weight": ew,
            "last_cochange_hash": last_hash if last_hash else None,
        }

    # 出力書き出し
    print("[cartographer] Writing output...")

    # JSON canonical 出力（常時生成）
    # @see EARS-001#REQ-U001
    _write_file(output_dir, "co-change.jsonl", layers.render_cochange_jsonl(structure_data, scan_info, cochange_weight_map))
    _write_file(output_dir, "hotspot.json", layers.render_hotspot_json(hotspots_data, scan_info))
    _write_file(output_dir, "stable.json", layers.render_stable_json(stable_files, scan_info))
    # @see ADR-003
    _write_file(
        output_dir,
        "components.json",
        components_axis.render_components_json(components_data, scan_info, cfg.scan_dirs),
    )

    # Markdown 出力（--markdown フラグ指定時のみ）
    if markdown:
        # @see EARS-001#REQ-U001
        _write_markdown(output_dir, "stable.md", layers.render_stable(stable_files, scan_info))
        _write_markdown(output_dir, "co-change.md", layers.render_structure(structure_data, scan_info))
        _write_markdown(output_dir, "hotspot.md", layers.render_hotspots(hotspots_data, scan_info))

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
        help="スキャンする最新コミット数（デフォルト: 100）",
    )
    parser.add_argument(
        "--include-stdlib",
        action="store_true",
        default=False,
        help="Hub Files に標準ライブラリを含める（デフォルト: 除外）",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        default=False,
        help="Markdown ファイル（stable.md, co-change.md, hotspot.md）を生成する（デフォルト: 生成しない）",
    )
    parser.add_argument(
        "--halflife-commits",
        type=int,
        default=90,
        help="co-change の半減期（コミット数、デフォルト: 90）",
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "cartographer 設定 TOML のパス（デフォルト: <repo>/.cartographer.toml、"
            "存在しない場合は組込デフォルトを使用）"
        ),
    )

    args = parser.parse_args()
    run(
        args.repo_path,
        args.output_dir,
        args.window,
        include_stdlib=args.include_stdlib,
        markdown=args.markdown,
        halflife_commits=args.halflife_commits,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
