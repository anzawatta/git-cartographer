"""
踏破録の記録・減衰・上位抽出。

ファイル: .cartographer_traverse_log.yml
フォーマット:
  entries:
    "path/to/file.py":
      score: 1.5
      last_hash: "abc123..."
      accessed_at: "2026-04-12T00:00:00+00:00"
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

# @see EARS-002#REQ-U002
TRAVERSE_LOG_FILE = ".cartographer_traverse_log.yml"

# @see EARS-002#REQ-U001
HALF_LIFE_COMMITS = 20
DECAY_BASE = 0.5

# @see EARS-002#REQ-W001
DECAY_THRESHOLD = 0.1


def _traverse_log_path(repo_path: str) -> str:
    return os.path.join(repo_path, TRAVERSE_LOG_FILE)


# @see EARS-002#REQ-U002
def load(repo_path: str) -> dict[str, dict]:
    """
    踏破録を読み込む。

    Returns:
        {filepath: {score, last_hash, accessed_at}}
    """
    path = _traverse_log_path(repo_path)
    if not os.path.isfile(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("entries", {}) or {}
    except (OSError, yaml.YAMLError):
        return {}
    except ImportError:
        return {}


def save(repo_path: str, entries: dict[str, dict]) -> None:
    """踏破録をファイルに書き込む。"""
    path = _traverse_log_path(repo_path)
    try:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump({"entries": entries}, f, default_flow_style=False, allow_unicode=True)
    except ImportError as e:
        raise RuntimeError("PyYAML is required for traverse_log storage. Install with: pip install PyYAML") from e
    except OSError as e:
        raise RuntimeError(f"Failed to save traverse_log file: {path}") from e


# @see EARS-002#REQ-E001
def record(repo_path: str, file_path: str, current_hash: str) -> None:
    """
    ファイルアクセスを踏破録に記録する。
    既存エントリは score += 1.0 してリセット（last_hash を更新）。
    新規エントリは score = 1.0 で追加。
    """
    entries = load(repo_path)
    now = datetime.now(timezone.utc).isoformat()

    if file_path in entries:
        entry = entries[file_path]
        entry["score"] = float(entry.get("score", 0.0)) + 1.0
        entry["last_hash"] = current_hash
        entry["accessed_at"] = now
    else:
        entries[file_path] = {
            "score": 1.0,
            "last_hash": current_hash,
            "accessed_at": now,
        }

    save(repo_path, entries)


# @see EARS-002#REQ-U001
# @see EARS-002#REQ-W001
def decay_all(repo_path: str, current_hash: str) -> None:
    """
    全エントリに減衰式を適用し、閾値未満のエントリを削除する。

    減衰式: score × (0.5 ^ (commits_elapsed / 20))
    """
    from src.git_scanner import count_commits_between

    entries = load(repo_path)
    if not entries:
        return

    surviving: dict[str, dict] = {}
    for file_path, entry in entries.items():
        last_hash = entry.get("last_hash", "")
        score = float(entry.get("score", 0.0))

        # コミット数を計算
        commits_elapsed = 0
        if last_hash and last_hash != current_hash:
            try:
                commits_elapsed = count_commits_between(repo_path, last_hash, current_hash)
            except RuntimeError:
                # git コマンド失敗時はコミット数不明 → 減衰なし
                commits_elapsed = 0

        # @see EARS-002#REQ-U001
        decayed_score = score * (DECAY_BASE ** (commits_elapsed / HALF_LIFE_COMMITS))

        # @see EARS-002#REQ-W001
        if decayed_score < DECAY_THRESHOLD:
            continue  # エントリ削除

        surviving[file_path] = {
            **entry,
            "score": round(decayed_score, 6),
        }

    save(repo_path, surviving)


# @see EARS-002#REQ-E002
def top_files(repo_path: str, n: int = 10) -> list[tuple[str, float]]:
    """
    踏破録スコア上位 N ファイルを返す。

    Returns:
        [(file_path, score), ...]
    """
    entries = load(repo_path)
    sorted_entries = sorted(
        entries.items(),
        key=lambda x: float(x[1].get("score", 0.0)),
        reverse=True,
    )
    return [(path, float(entry.get("score", 0.0))) for path, entry in sorted_entries[:n]]
