"""
git log churn 分析 + co-change 抽出。

git コマンドのみを使用し、外部ライブラリに依存しない。
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from itertools import combinations


def _run_git(args: list[str], repo_path: str) -> str:
    """git コマンドを実行して stdout を返す。失敗時は RuntimeError を送出する。"""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git command failed: git {' '.join(args)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout


# @see EARS-001#REQ-U004
def get_head_hash(repo_path: str) -> str:
    """HEAD のコミットハッシュを返す。"""
    return _run_git(["rev-parse", "HEAD"], repo_path).strip()


def count_commits_between(repo_path: str, hash_a: str, hash_b: str) -> int:
    """hash_a..hash_b の間のコミット数を返す。"""
    output = _run_git(
        ["rev-list", "--count", f"{hash_a}..{hash_b}"],
        repo_path,
    )
    try:
        return int(output.strip())
    except ValueError:
        return 0


# @see EARS-001#REQ-U004
# @see EARS-001#REQ-S002
def diff_files(
    repo_path: str,
    since_hash: str,
    until_hash: str = "HEAD",
) -> list[str]:
    """
    since_hash..until_hash の間で変更されたファイル一覧を返す。
    削除済みファイルは含まない（存在するファイルのみ）。
    """
    output = _run_git(
        ["diff", "--name-only", "--diff-filter=AM", f"{since_hash}..{until_hash}"],
        repo_path,
    )
    return [line for line in output.splitlines() if line.strip()]


# @see EARS-001#REQ-U004
def churn_counts(
    repo_path: str,
    since_hash: str | None = None,
    until_hash: str = "HEAD",
    window: int = 100,
) -> dict[str, int]:
    """
    ファイルごとのチャーン数（変更コミット数）を返す。

    since_hash が指定された場合は since_hash..until_hash の範囲を解析する。
    指定されない場合は最新 window コミットを解析する。
    """
    log_args = ["log", "--numstat", "--format=COMMIT:%H"]

    if since_hash:
        log_args += [f"{since_hash}..{until_hash}"]
    else:
        log_args += [f"-{window}", until_hash]

    output = _run_git(log_args, repo_path)

    counts: dict[str, int] = defaultdict(int)
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("COMMIT:"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        # numstat 形式: added deleted filename
        file_path = parts[2]
        # リネーム形式 "old => new" は skip（簡易実装）
        if " => " in file_path:
            continue
        counts[file_path] += 1

    return dict(counts)


# @see EARS-001#REQ-U004
def cochange_pairs(
    repo_path: str,
    since_hash: str | None = None,
    until_hash: str = "HEAD",
    window: int = 100,
) -> dict[tuple[str, str], dict]:
    """
    同一コミットで同時変更されたファイルペアとその頻度・最終共変コミットを返す。
    ペアは (小さい方, 大きい方) でソートされたタプル。

    since_hash が指定された場合は since_hash..until_hash の範囲を解析する。
    指定されない場合は最新 window コミットを解析する。

    Returns:
        dict[tuple[str, str], dict]: キーはペア、値は {"count": int, "last_hash": str}
        git log は新しい順に出力されるため、ペアが最初に登場したコミットハッシュ = 最新の co-change コミット。
    """
    log_args = ["log", "--name-only", "--format=COMMIT:%H"]

    if since_hash:
        log_args += [f"{since_hash}..{until_hash}"]
    else:
        log_args += [f"-{window}", until_hash]

    output = _run_git(log_args, repo_path)

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    pair_last_hash: dict[tuple[str, str], str] = {}
    current_files: list[str] = []
    current_hash: str = ""

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("COMMIT:"):
            # 前のコミットのペアを集計
            if len(current_files) > 1:
                for a, b in combinations(sorted(current_files), 2):
                    pair_counts[(a, b)] += 1
                    # git log は新しい順なので、ペア初出現 = 最新の co-change コミット
                    if (a, b) not in pair_last_hash:
                        pair_last_hash[(a, b)] = current_hash
            current_hash = line[len("COMMIT:"):]
            current_files = []
        elif line:
            current_files.append(line)

    # 最後のコミット分
    if len(current_files) > 1:
        for a, b in combinations(sorted(current_files), 2):
            pair_counts[(a, b)] += 1
            if (a, b) not in pair_last_hash:
                pair_last_hash[(a, b)] = current_hash

    return {
        pair: {"count": count, "last_hash": pair_last_hash.get(pair, "")}
        for pair, count in pair_counts.items()
    }
