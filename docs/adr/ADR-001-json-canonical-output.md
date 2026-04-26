# ADR-001: JSON Canonical Output

**Status:** Accepted
**Date:** 2026-04-26

---

## Context

git-cartographer は当初 Markdown ファイルのみを出力していた。
しかしエージェントが地図データを機械的に処理する際、
Markdown のパースが必要になり、構造的な取り回しが困難だった。

下流の skeleton.json 合成（Phase 2）や外部ツールとの連携を見据え、
**機械可読な canonical フォーマット**が必要になった。

---

## Decision

`output/` 配下に JSON / JSONL 形式の canonical データファイルを追加する。

| ファイル | 形式 | 内容 |
|---------|------|------|
| `co-change.jsonl` | NDJSON（1行1エッジ） | co-change ペア |
| `hotspot.json` | JSON | hotspot ランキング |
| `stable.json` | JSON | 安定ファイル一覧 |

Markdown ファイル（`stable.md`, `structure.md`, `hotspots.md`）は引き続き並行生成する。
JSON が canonical であり、Markdown は人間向け閲覧用の派生フォーマットと位置づける。

---

## Rationale

### なぜ JSON canonical か

- **機械可読性**: エージェントが skeleton.json を合成する際に Markdown のパースが不要になる
- **型安全**: フィールド名・型が明示的に定義される
- **拡張容易性**: フィールド追加が Markdown レイアウトに影響しない
- **既存出力との共存**: Markdown を削除しないため、既存の利用パターンは壊れない

### Markdown との並行運用

| 観点 | JSON | Markdown |
|------|------|----------|
| 役割 | canonical データ | 人間向け閲覧 |
| 機械処理 | 直接パース可能 | 不可 |
| 読みやすさ | 低 | 高 |
| 生成コスト | 同等 | 同等 |

---

## Phase 1 スコープ

本 ADR の Phase 1 では以下を実装する：

1. `layers.py` に JSON/JSONL 出力関数を追加（既存 render_* 関数は変更しない）
2. `cartographer.py` の `run()` で JSON ファイルを Markdown と並行生成
3. Cold start（Git 履歴ゼロ）時の適切な空出力

**Phase 2（skeleton.json 合成）は on-demand のみ**:
- `src/skeleton.py` に `synthesize_skeleton(seed, policy)` を実装
- `run()` から自動呼び出しはしない（エージェントが明示的に呼び出す）
- cartographer はデフォルト seed を自分で決定しない

---

## Consequences

- `output/*` は既に `.gitignore` で除外済み。JSON ファイルも自動的に除外される
- `output/skeleton.json` は on-demand 生成のため、設計意図を明示するコメントを `.gitignore` に追記する
- 計算不能なフィールド（`decay_factor`, `trend`, `stability_score` 等）は `null` とする
- 将来フィールドを追加する際は EARS-001 を更新する

---

## Rejected Alternatives

**A. Markdown のみを継続する**
- 理由: 下流エージェントが Markdown パースを余儀なくされる。構造的に不安定

**B. Markdown を廃止して JSON のみにする**
- 理由: 人間が地図を直接読む際に不便。既存の利用パターンを壊す。並行運用のコストは低い

**C. SQLite などの専用 DB を使う**
- 理由: 軽量スタック原則（PRINCIPLE.md）に反する。ファイルベースのシンプルさを維持する
