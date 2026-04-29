"""
.cartographer.toml 設定ファイルの読み込み。

- 設定が存在しない場合は組込デフォルトを返す（「忘れられる構造」原則）。
- TOML を採用し、外部依存を増やさない（Python 3.11+ 標準の tomllib のみ）。
- 設定スキーマは [components] テーブルに集約する。

スキーマ:

    [components]
    scan_dirs = ["src", "lib", "lambda", "packages", "apps", "services", "functions"]
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field

CONFIG_FILE = ".cartographer.toml"

# 組込デフォルト: 多くのリポジトリでノーアクションで動くよう、典型的なソース境界を網羅する
DEFAULT_SCAN_DIRS: list[str] = [
    "src",
    "lib",
    "lambda",
    "packages",
    "apps",
    "services",
    "functions",
]


@dataclass(frozen=True)
class CartographerConfig:
    """cartographer 設定値の集約点。"""

    # @see ADR-003
    scan_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SCAN_DIRS))


def _default_config() -> CartographerConfig:
    return CartographerConfig(scan_dirs=list(DEFAULT_SCAN_DIRS))


def _validate_scan_dirs(raw: object, source: str) -> list[str]:
    """`scan_dirs` 値の最小バリデーション（型・要素型のみ）。"""
    if not isinstance(raw, list):
        raise ValueError(
            f"{source}: [components].scan_dirs must be a list of strings"
        )
    result: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str):
            raise ValueError(
                f"{source}: [components].scan_dirs[{i}] must be a string"
            )
        # 末尾スラッシュは正規化（`src/` も `src` も等価扱い）
        normalized = item.strip().rstrip("/")
        if normalized:
            result.append(normalized)
    return result


def load_config(repo_path: str, config_path: str | None = None) -> CartographerConfig:
    """
    設定ファイルを読み込んで CartographerConfig を返す。

    優先順位:
    1. `config_path` が明示指定されている → そのファイルを読む（無ければエラー）
    2. リポジトリルートの `.cartographer.toml` が存在する → それを読む
    3. どちらも無い → 組込デフォルトを返す

    解析失敗（TOML 構文エラー・型エラー）は stderr に warning を出して
    組込デフォルトにフォールバックする（fail-loud / continue）。

    @see EARS-003#REQ-U004
    @see EARS-003#REQ-E001
    @see EARS-003#REQ-E002
    @see EARS-003#REQ-E003
    @see EARS-003#REQ-E004
    """
    # 1. 明示指定パス
    if config_path is not None:
        if not os.path.isfile(config_path):
            print(
                f"[cartographer] WARNING: --config path not found: {config_path}. "
                f"Falling back to built-in defaults.",
                file=sys.stderr,
            )
            return _default_config()
        return _load_from_file(config_path)

    # 2. リポジトリルートの .cartographer.toml
    default_path = os.path.join(repo_path, CONFIG_FILE)
    if os.path.isfile(default_path):
        return _load_from_file(default_path)

    # 3. 組込デフォルト
    return _default_config()


def _load_from_file(path: str) -> CartographerConfig:
    """指定された TOML ファイルから設定を読む。失敗時は default にフォールバック。"""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except OSError as e:
        print(
            f"[cartographer] WARNING: failed to read config {path}: {e}. "
            f"Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _default_config()
    except tomllib.TOMLDecodeError as e:
        print(
            f"[cartographer] WARNING: failed to parse config {path}: {e}. "
            f"Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _default_config()

    components_section = data.get("components", {})
    if not isinstance(components_section, dict):
        print(
            f"[cartographer] WARNING: {path}: [components] must be a table. "
            f"Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _default_config()

    if "scan_dirs" not in components_section:
        # [components] テーブルはあるが scan_dirs が無い場合もデフォルトで補完
        return _default_config()

    try:
        scan_dirs = _validate_scan_dirs(components_section["scan_dirs"], path)
    except ValueError as e:
        print(
            f"[cartographer] WARNING: {e}. Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _default_config()

    if not scan_dirs:
        # 空リスト指定は意図的に「全てを components 対象から外す」ケースもあり得るが、
        # 設定ミスの可能性が高いためデフォルトにフォールバック
        print(
            f"[cartographer] WARNING: {path}: [components].scan_dirs is empty. "
            f"Falling back to built-in defaults.",
            file=sys.stderr,
        )
        return _default_config()

    return CartographerConfig(scan_dirs=scan_dirs)
