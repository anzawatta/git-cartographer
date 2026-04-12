"""
.cartographer_state の読み書き。

フォーマット: "<commit_hash> <iso_timestamp>"
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

STATE_FILE = ".cartographer_state"


def _state_path(repo_path: str) -> str:
    return os.path.join(repo_path, STATE_FILE)


# @see EARS-001#REQ-S001
def get_last_hash(repo_path: str) -> str | None:
    """
    .cartographer_state からコミットハッシュを返す。
    ファイルが存在しない、または読み取れない場合は None を返す。
    """
    path = _state_path(repo_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return None
        parts = content.split()
        return parts[0] if parts else None
    except OSError:
        return None


# @see EARS-001#REQ-S001
# @see EARS-001#REQ-S002
def set_last_hash(hash: str, repo_path: str) -> None:
    """
    .cartographer_state にコミットハッシュと現在時刻を書き込む。
    """
    path = _state_path(repo_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{hash} {timestamp}\n")
    except OSError as e:
        raise RuntimeError(f"Failed to write state file: {path}") from e
