"""
3層地図生成（stable / structure / hotspots）。

各層を Markdown 文字列として生成する。
"""

from __future__ import annotations

from datetime import datetime, timezone


# @see EARS-001#REQ-U002
# @see EARS-001#REQ-S003
def build_stable(churn_counts: dict[str, int], threshold: int = 0) -> list[str]:
    """
    churn 頻度が threshold 以下のファイルを stable 層として返す。
    threshold=0 の場合、変更ゼロのファイルのみを対象とする。
    """
    return sorted(
        [path for path, count in churn_counts.items() if count <= threshold]
    )


# @see EARS-001#REQ-U002
def build_structure(
    churn_counts: dict[str, int],
    cochange_pairs: dict[tuple[str, str], int],
    import_graph: dict[str, list[str]],
) -> dict:
    """
    依存関係サマリを構築する。

    Returns:
        {
            "cochange_top": [(file_a, file_b, count), ...],  # 上位 co-change ペア
            "import_graph": {file: [deps, ...]},             # import 依存グラフ
            "hub_files": [(file, dep_count), ...],           # 被参照数上位ファイル
        }
    """
    # co-change 上位 20 ペアを抽出
    sorted_pairs = sorted(cochange_pairs.items(), key=lambda x: x[1], reverse=True)
    cochange_top = [(a, b, cnt) for (a, b), cnt in sorted_pairs[:20]]

    # 被参照数（どのファイルから import されているか）を集計
    in_degree: dict[str, int] = {}
    for deps in import_graph.values():
        for dep in deps:
            in_degree[dep] = in_degree.get(dep, 0) + 1

    hub_files = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "cochange_top": cochange_top,
        "import_graph": import_graph,
        "hub_files": hub_files,
    }


# @see EARS-001#REQ-U002
def build_hotspots(
    churn_counts: dict[str, int],
    top_n: int = 20,
) -> list[tuple[str, int]]:
    """
    churn 上位 N ファイルを hotspots として返す。
    Returns: [(file_path, churn_count), ...]
    """
    sorted_files = sorted(churn_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_files[:top_n]


def _scan_info_header(scan_info: dict) -> str:
    """スキャン情報ヘッダーを生成する。"""
    lines = []
    mode = scan_info.get("mode", "unknown")
    head_hash = scan_info.get("head_hash", "unknown")
    generated_at = scan_info.get("generated_at", datetime.now(timezone.utc).isoformat())
    lines.append(f"- **Mode**: {mode}")
    lines.append(f"- **HEAD**: `{head_hash[:12] if len(head_hash) > 12 else head_hash}`")
    lines.append(f"- **Generated**: {generated_at}")
    return "\n".join(lines)


# @see EARS-001#REQ-U001
# @see EARS-001#REQ-U002
def render_stable(files: list[str], scan_info: dict) -> str:
    """stable 層を Markdown 文字列として返す。"""
    lines = [
        "# Stable Layer",
        "",
        "変更頻度ゼロ（安定）のファイル一覧。",
        "",
        "## Scan Info",
        "",
        _scan_info_header(scan_info),
        "",
        "## Files",
        "",
    ]

    if not files:
        lines.append("_安定ファイルは検出されませんでした。_")
    else:
        lines.append(f"**合計: {len(files)} ファイル**")
        lines.append("")
        for f in files:
            lines.append(f"- `{f}`")

    lines.append("")
    return "\n".join(lines)


# @see EARS-001#REQ-U001
# @see EARS-001#REQ-U002
def render_structure(structure_data: dict, scan_info: dict) -> str:
    """structure 層を Markdown 文字列として返す。"""
    lines = [
        "# Structure Layer",
        "",
        "依存関係・co-change 構造の地図。",
        "",
        "## Scan Info",
        "",
        _scan_info_header(scan_info),
        "",
    ]

    # Co-change ペア
    lines += [
        "## Co-change Top Pairs",
        "",
        "同一コミットで頻繁に同時変更されるファイルペア。",
        "",
    ]
    cochange_top = structure_data.get("cochange_top", [])
    if not cochange_top:
        lines.append("_データなし_")
    else:
        lines.append("| File A | File B | Count |")
        lines.append("|--------|--------|-------|")
        for a, b, cnt in cochange_top:
            lines.append(f"| `{a}` | `{b}` | {cnt} |")
    lines.append("")

    # Hub ファイル（被参照数上位）
    lines += [
        "## Hub Files",
        "",
        "多数のファイルから import されているハブファイル。",
        "",
    ]
    hub_files = structure_data.get("hub_files", [])
    if not hub_files:
        lines.append("_データなし_")
    else:
        lines.append("| File | Referenced By |")
        lines.append("|------|--------------|")
        for f, cnt in hub_files:
            lines.append(f"| `{f}` | {cnt} |")
    lines.append("")

    # Import グラフ（上位20ファイルのみ抜粋）
    import_graph = structure_data.get("import_graph", {})
    if import_graph:
        lines += [
            "## Import Graph (抜粋)",
            "",
            "ファイルごとの import 依存先（上位 20 ファイル）。",
            "",
        ]
        for i, (src, deps) in enumerate(list(import_graph.items())[:20]):
            if deps:
                dep_str = ", ".join(f"`{d}`" for d in deps[:5])
                if len(deps) > 5:
                    dep_str += f", ... (+{len(deps) - 5})"
                lines.append(f"- `{src}` → {dep_str}")
        lines.append("")

    return "\n".join(lines)


# @see EARS-001#REQ-U001
# @see EARS-001#REQ-U002
def render_hotspots(hotspots_data: list[tuple[str, int]], scan_info: dict) -> str:
    """hotspots 層を Markdown 文字列として返す。"""
    lines = [
        "# Hotspots Layer",
        "",
        "変更頻度（churn）の高いファイル上位。",
        "",
        "## Scan Info",
        "",
        _scan_info_header(scan_info),
        "",
        "## Hotspot Files",
        "",
    ]

    if not hotspots_data:
        lines.append("_データなし_")
    else:
        lines.append("| Rank | File | Churn |")
        lines.append("|------|------|-------|")
        for i, (path, count) in enumerate(hotspots_data, 1):
            lines.append(f"| {i} | `{path}` | {count} |")

    lines.append("")
    return "\n".join(lines)
