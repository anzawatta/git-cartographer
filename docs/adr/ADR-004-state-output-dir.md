# ADR-004: `.cartographer_state` への output_dir フィールド追加

**Status:** Accepted
**Date:** 2026-05-31
**Related EARS:** EARS-001 (REQ-S005), EARS-002 (REQ-E003)

## Context

安定層 Read-hook（EARS-002 REQ-E003）は、エージェントが Read するファイルの ward を解決し `stable.json` および `co-change.jsonl` を取得する必要がある。

`.cartographer_state` はリポジトリルートに配置され、cartographer が「最後にこのリポジトリでスキャンした」ことを示す唯一のシグナルである。hook がファイルパスから上方探索することで「このリポジトリは cartographer で管理されているか？」と「出力ディレクトリはどこか？」の両方を1ファイルで解決できる。

## Decision

`.cartographer_state` のフォーマットを以下のように拡張する:

**従来**: `<hash> <iso_timestamp>`
**新規**: `<hash> <iso_timestamp> <output_dir_abs>`

- 第3フィールドは `output/` ディレクトリの**絶対パス**とする
- 読み取り側は `content.split(maxsplit=2)` で分割し、第3フィールドの有無でバージョンを判別する
- 第3フィールドが存在しない（旧フォーマット）場合は `.cartographer_state` と同じディレクトリの `output/` サブディレクトリを fallback とする

## PRINCIPLE §1 との関係

PRINCIPLE §1 は `.cartographer_state` を「HEAD 未変更時のスキップ最適化としてのみ使用する」と定める。本 ADR はその "のみ" を意図的に拡張する。

**根拠**: hook が ward を解決するための別ファイルを新設する（例: `.cartographer_output`）より、既存ファイルに1フィールド追加する方が「忘れられる構造（PRINCIPLE §1）」に沿う。管理ファイル数を増やさない判断を優先する。

**結果**: PRINCIPLE §1 の記述をこの ADR をもって更新されたものとみなす。`.cartographer_state` は (1) スキップ最適化 と (2) 出力先記録 の2目的を持つ。

## Backward Compatibility

- **読み取り**: 既存の `get_last_hash` は `parts[0]` のみ使用 → 変更不要
- **書き込み**: `set_last_hash` に `output_dir` 引数を追加（デフォルト `None` → フィールド省略で旧互換）
- **hook fallback**: 第3フィールドなし → `{repo_root}/output/` を仮定 → 旧形式のリポジトリでも動作

## Consequences

- `src/state.py` の `set_last_hash` シグネチャ変更
- `src/cartographer.py` の `set_last_hash` 呼び出し側更新
- hook の ward 解決が `.cartographer_state` に依存するため、cartographer 未実行リポジトリでは安定層注入がスキップされる（正しい挙動）
