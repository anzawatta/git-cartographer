# EARS-003: Components Measurement Axis

**Status:** Draft
**Date:** 2026-04-29
**Related ADR:** ADR-003

## 不変条件

1. REQ-U001: System は、`scan_dirs` 配下の直下サブディレクトリ一覧を `output/components.json` として出力しなければならない
2. REQ-U002: System は、コンポーネント検出に許可リスト方式のみを使用しなければならない（`scan_dirs` 配下の直下サブディレクトリのみを component とする）
3. REQ-U003: System は、コンポーネント検出の除外ロジックに `.gitignore` のみを使用しなければならない（`tests/`、`_test` 等のハードコード除外を実装してはならない）
4. REQ-U004: System は、`.cartographer.toml` の解析に Python 標準の `tomllib` のみを使用しなければならない（外部 TOML パーサー依存を追加してはならない）
5. REQ-U005: ファイルがある `scan_dir` の prefix にマッチしたとき、System はより浅い `scan_dir` にフォールスルーさせてはならない（claim セマンティクス）
6. REQ-U006: `scan_dirs` に深いパスと浅いパスが重複して含まれる場合、System は深いパスを優先しなければならない

## 敵対条件

1. REQ-W001: System は、component の type 判定（意味カテゴリ推定）を行ってはならない
2. REQ-W002: System は、component 間の edges 推定を行ってはならない
3. REQ-W003: System は、Component Card YAML の生成を行ってはならない
4. REQ-W004: System は、ステム共通性集約（共通プレフィックスによる component グルーピング）を行ってはならない

## 状態駆動条件

1. REQ-S001: HEAD が `.cartographer_state` に記録されたハッシュと一致する場合、System は `components.json` の再生成をスキップしなければならない（既存 3 軸と一括スキップ）
2. REQ-S002: components 数が 150 を超えた場合、System は stderr に warning を出力しなければならない（fail-loud、`scan_dirs` の絞り込みを利用者に促す）

## イベント駆動条件

1. REQ-E001: `--config <path>` が指定されたとき、System はそのパスから設定を読み込まなければならない
2. REQ-E002: `--config` が指定されておらず、リポジトリルートに `.cartographer.toml` が存在するとき、System はそれを読み込まなければならない
3. REQ-E003: 設定ファイルが存在しないとき、System は組込デフォルト `["src", "lib", "lambda", "packages", "apps", "services", "functions"]` を `scan_dirs` として使用しなければならない
4. REQ-E004: 設定ファイルのパース・型バリデーションに失敗したとき、System は組込デフォルトにフォールバックし、stderr に warning を出力しなければならない
