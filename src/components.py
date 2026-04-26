"""
Components 測量（第 4 軸）。

`scan_dirs` 配下の直下サブディレクトリ一覧を構造的事実として記録する。
`.gitignore` フィルタリングは `git ls-files` 起点で自動的に適用される。

PRINCIPLE 2「測量に徹する」を侵さないため、以下は実装しない:
- type 判定 / edges 推定 / Component Card YAML 生成（agent 側責務）
- ステム共通性集約（解釈責務、agent 側担当）
- `tests/`, `_test` 等の除外ロジック（許可リスト一本化原則違反、`.gitignore` で表現すること）
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

# components 数の警告閾値（fail-loud）。150 を超えたら scan_dirs の絞り込みを促す。
COMPONENT_WARN_THRESHOLD: int = 150


def _git_tracked_files(repo_path: str) -> list[str]:
    """
    `git ls-files` で git 管理下の全ファイル相対パスを返す。

    .gitignore フィルタリングは git 側で自動適用される。
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _extract_components(
    tracked_files: list[str],
    scan_dirs: list[str],
) -> list[dict[str, str]]:
    """
    tracked_files から `scan_dirs` 配下の直下サブディレクトリを抽出する。

    例: scan_dirs=["src", "lib"] のとき
      - "src/cartographer/main.py" → ("src", "cartographer", "src/cartographer")
      - "lib/foo-stack.ts"          → 直下ファイルなのでスキップ
      - "lambda/handler/index.ts"   → scan_dirs に "lambda" がなければスキップ

    Returns: 重複除去後、(scan_dir, name) でソートされた dict 一覧
    """
    # path 正規化: TOML の `src/` も `src` も等価扱い
    normalized_scan_dirs = [d.strip("/").rstrip("/") for d in scan_dirs if d.strip("/")]

    seen: set[tuple[str, str]] = set()
    for rel_path in tracked_files:
        # POSIX 区切りで分解（git ls-files は常に "/" を返す）
        parts = rel_path.split("/")
        if len(parts) < 3:
            # scan_dir 直下のファイル（例: src/foo.py）は components ではない
            continue
        scan_dir = parts[0]
        if scan_dir not in normalized_scan_dirs:
            continue
        name = parts[1]
        if not name:
            continue
        seen.add((scan_dir, name))

    components: list[dict[str, str]] = []
    for scan_dir, name in sorted(seen):
        components.append(
            {
                "path": f"{scan_dir}/{name}",
                "scan_dir": scan_dir,
                "name": name,
            }
        )
    return components


def build_components(
    repo_path: str,
    scan_dirs: list[str],
) -> list[dict[str, str]]:
    """
    Components 軸の測量を実行する。

    Args:
        repo_path: 解析対象のリポジトリルート絶対パス
        scan_dirs: 許可リスト（例: ["src", "lib", "lambda", ...]）

    Returns:
        components のリスト（path / scan_dir / name のソート済み dict）
    """
    tracked_files = _git_tracked_files(repo_path)
    return _extract_components(tracked_files, scan_dirs)


def render_components_json(
    components: list[dict[str, str]],
    scan_info: dict,
    scan_dirs: list[str],
) -> str:
    """
    components.json の JSON 文字列を返す。

    {
      "head": "<commit_hash>",
      "generated_at": "<ISO8601>",
      "scan_dirs": [...],
      "components": [
        {"path": "src/cartographer", "scan_dir": "src", "name": "cartographer"},
        ...
      ]
    }
    """
    head_hash = scan_info.get("head_hash", "unknown")
    generated_at = scan_info.get(
        "generated_at", datetime.now(timezone.utc).isoformat()
    )

    payload = {
        "head": head_hash,
        "generated_at": generated_at,
        "scan_dirs": list(scan_dirs),
        "components": components,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
