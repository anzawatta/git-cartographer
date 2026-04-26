"""
skeleton.json 合成モジュール。

on-demand のみ呼び出す（cartographer の run() からは自動呼び出ししない）。
steward が seed と policy を必ず渡すこと。
cartographer はデフォルト seed を自分で決定しない。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


def _load_json(path: str) -> dict:
    """JSON ファイルを読み込む。ファイルが存在しない場合は空 dict を返す。"""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: str) -> list[dict]:
    """NDJSON ファイルを読み込む。ファイルが存在しない場合は空リストを返す。"""
    if not os.path.isfile(path):
        return []
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _file_hash(path: str) -> str:
    """ファイル内容の SHA-256 ハッシュ（16進 12文字）を返す。ファイルが存在しない場合は 'missing'。"""
    if not os.path.isfile(path):
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


# @see EARS-001#REQ-U001
def synthesize_skeleton(
    seed: list[str],
    policy: dict[str, Any],
    output_dir: str = "output",
) -> dict:
    """
    seed ファイル一覧と policy に基づいて skeleton.json を合成して返す。

    呼び出し側（steward）が seed と policy を必ず渡す。
    cartographer はデフォルト seed を決定しない。

    Parameters
    ----------
    seed : list[str]
        起点となるファイルパス一覧。steward が決定する。
    policy : dict
        合成ポリシー。以下のキーを受け付ける:
          cochange_threshold : float  co-change effective_weight の閾値（未満は除外）
          max_depth          : int    展開深度（0 = seed のみ）
          default_excludes   : list[str]  除外パターン（fnmatch 形式）
    output_dir : str
        co-change.jsonl / hotspot.json / stable.json が存在するディレクトリ。

    Returns
    -------
    dict
        skeleton.json の内容。output_dir/skeleton.json にも書き出す。
        hotspot_source_hash, stable_source_hash, cochange_source_hash を含む。
    """
    cochange_path = os.path.join(output_dir, "co-change.jsonl")
    hotspot_path = os.path.join(output_dir, "hotspot.json")
    stable_path = os.path.join(output_dir, "stable.json")

    # ソースファイルのハッシュ（追跡可能性）
    cochange_source_hash = _file_hash(cochange_path)
    hotspot_source_hash = _file_hash(hotspot_path)
    stable_source_hash = _file_hash(stable_path)

    # ポリシーパラメータを取り出す（デフォルト値付き）
    cochange_threshold: float = float(policy.get("cochange_threshold", 0.0))
    max_depth: int = int(policy.get("max_depth", 0))
    default_excludes: list[str] = list(policy.get("default_excludes", []))

    # データ読み込み
    cochange_records = _load_jsonl(cochange_path)
    hotspot_data = _load_json(hotspot_path)
    stable_data = _load_json(stable_path)

    # co-change エッジを閾値でフィルタリング
    # effective_weight が null の場合は閾値フィルタをスキップ（null は「不明」として保持）
    filtered_cochange = [
        r for r in cochange_records
        if r.get("effective_weight") is None
        or r.get("effective_weight", 0.0) >= cochange_threshold
    ]

    # seed ファイルに関係するエッジのみ抽出（max_depth=0 の場合は seed のみ）
    relevant_files: set[str] = set(seed)

    if max_depth > 0:
        # 深さ優先で co-change 隣接ファイルを展開
        frontier = set(seed)
        for _depth in range(max_depth):
            next_frontier: set[str] = set()
            for edge in filtered_cochange:
                pair = edge.get("pair", [])
                if len(pair) == 2:
                    a, b = pair[0], pair[1]
                    if a in frontier and b not in relevant_files:
                        next_frontier.add(b)
                    elif b in frontier and a not in relevant_files:
                        next_frontier.add(a)
            relevant_files |= next_frontier
            frontier = next_frontier
            if not frontier:
                break

    # 除外パターン適用
    import fnmatch

    def _is_excluded(path: str) -> bool:
        return any(fnmatch.fnmatch(path, pat) for pat in default_excludes)

    relevant_files = {f for f in relevant_files if not _is_excluded(f)}

    # seed に関連する co-change エッジを抽出
    skeleton_edges = [
        edge for edge in filtered_cochange
        if len(edge.get("pair", [])) == 2
        and (edge["pair"][0] in relevant_files or edge["pair"][1] in relevant_files)
        and not _is_excluded(edge["pair"][0])
        and not _is_excluded(edge["pair"][1])
    ]

    # hotspot から seed 関連ファイルを抽出
    hotspot_ranking = hotspot_data.get("ranking", [])
    relevant_hotspots = [
        entry for entry in hotspot_ranking
        if entry.get("path") in relevant_files
    ]

    # stable から seed 関連ファイルを抽出
    stable_load_bearing = stable_data.get("load_bearing", [])
    relevant_stable = [
        entry for entry in stable_load_bearing
        if entry.get("path") in relevant_files
    ]

    generated_at = datetime.now(timezone.utc).isoformat()

    skeleton: dict[str, Any] = {
        "generated_at": generated_at,
        "seed": sorted(seed),
        "policy": policy,
        "hotspot_source_hash": hotspot_source_hash,
        "stable_source_hash": stable_source_hash,
        "cochange_source_hash": cochange_source_hash,
        "relevant_files": sorted(relevant_files),
        "cochange_edges": skeleton_edges,
        "hotspots": relevant_hotspots,
        "stable": relevant_stable,
    }

    # output/skeleton.json に書き出す
    skeleton_path = os.path.join(output_dir, "skeleton.json")
    with open(skeleton_path, "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)

    return skeleton
