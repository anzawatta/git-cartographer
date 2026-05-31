---
provides:
  - REQ-E001
  - REQ-E002
  - REQ-E003
  - REQ-U001
  - REQ-U002
  - REQ-U003
  - REQ-W001
  - REQ-W002
  - REQ-W003
  - REQ-W004
  - REQ-S001
---
# EARS-002: Hook Context Injection

**Status:** Draft
**Date:** 2026-04-12
**Updated:** 2026-05-31
**Related ADR:** ADR-004

---

## 踏破録コンテキスト注入（既存）

### 不変条件

1. REQ-U001: System は、踏破録を `score × (0.5 ^ (commits_elapsed / 20))` の式で減衰させなければならない
2. REQ-U002: 踏破録は、git 管理対象のリポジトリ内に配置しなければならない（`.gitignore` による除外は利用者判断で許容）

### 敵対条件

1. REQ-W001: System は、スコアが 0.1 未満になったエントリを踏破録に保持してはならない
2. REQ-W002: System は、踏破録の手動操作インターフェースを提供してはならない（忘却は自動のみ）

### イベント駆動条件

1. REQ-E001: PostToolUse Hook が発火したとき、System はアクセスされたファイルパスとそのタイミングのコミットハッシュを踏破録に追記しなければならない
2. REQ-E002: PreToolUse Hook が発火したとき、System は踏破録スコア上位のファイルリストをコンテキストとして Claude Code に注入しなければならない

---

## 安定層警告コンテキスト注入（新規）

### 不変条件

3. REQ-U003: **co-change 次数の定義**: あるファイル F の co-change 次数は、`co-change.jsonl`（全ペア出力）から F を含む全ペアを抽出し、F 以外のファイルのユニーク数として定義する。`effective_weight` および `sample_size` は次数定義に用いない

### 敵対条件

3. REQ-W003: System は、`agent_type` が `["general-purpose", "critic"]` に含まれない PreToolUse イベントに対して安定層警告を注入してはならない
4. REQ-W004: System は、`tool_input.file_path` が以下の条件を満たさない場合、安定層チェックをスキップしなければならない: (a) 絶対パスであること、(b) NUL バイト（`\x00`）を含まないこと、(c) OS の PATH_MAX（通常 4096）以下の長さであること

### イベント駆動条件

3. REQ-E003: PreToolUse Hook が発火し、`tool_name == "Read"` かつ `agent_type` が REQ-W003 の allowlist に含まれるとき、System は以下の手順で安定層コンテキストを生成し、フック応答の `reason` フィールド（`{"decision": "allow", "reason": "<context>"}` 形式）に追加しなければならない:

   a. **ward 解決**: `tool_input.file_path` から親ディレクトリを順に探索し、`.cartographer_state` ファイルを見つける。見つかった場合、第3フィールド（`output_dir`）を `maxsplit=2` で取得する。フォールバック: `.cartographer_state` が存在しない、または第3フィールドが存在しない場合は、`.cartographer_state` が存在するディレクトリの `output/` サブディレクトリを `output_dir` として使用する。`.cartographer_state` 自体が見つからない場合は注入をスキップする

   b. **stable.json 参照**: `{output_dir}/stable.json` を読み込み、`load_bearing[].path` 一覧を取得する。`load_bearing` が空またはファイルが存在しない場合は注入をスキップする

   c. **ファイル判定**: `tool_input.file_path` の `.cartographer_state` ディレクトリからの相対パスが `load_bearing[].path` のいずれかと一致する場合、そのエントリを取得する。一致しない場合は注入をスキップする

   d. **co-change 次数計算**: `{output_dir}/co-change.jsonl` を読み込み、対象ファイルの co-change 次数（REQ-U003）を計算する。`co-change.jsonl` が存在しない場合は次数=0 として扱う

   e. **カテゴリ判定と注入文言**:
      - 高次数（次数 ≥ 3）: `⚠️ 安定層: {rel_path} (stability_score: {score}, co-change: {degree})\n荷重基盤 — 高結合。変更前に依存を確認。`
      - 低次数（次数 = 0）: `⚠️ 安定層: {rel_path} (stability_score: {score}, co-change: 0)\n孤立安定 — 削除前に理由を確認。`
      - 中次数（次数 1–2）: `⚠️ 安定層: {rel_path} (stability_score: {score}, co-change: {degree})`

   f. `stability_score` が `null` の場合は `stability_score: N/A` と表示する

### 状態駆動条件

1. REQ-S001: 例外（ファイル読み取りエラー・JSON パースエラー等）が発生した場合、System は `{"decision": "allow", "reason": ""}` を返し Claude Code の処理を継続しなければならない（安定層チェックの失敗は Read を止めない）
