# ADR-003: Components Measurement Axis（第4軸 components.json）

**Status:** Proposed
**Date:** 2026-04-26

---

## Context

cartographer agent / Explorer は ward 構造を毎回フルスキャンしており、
コンポーネント境界（`src/`, `lib/`, `lambda/...` などの構造的事実）が
測量パイプラインに結晶化されていない。

その結果、L2（agent）はタスクごとに同じ構造調査を繰り返し、
トークン・実時間ともにムダが生じている。

既存 3 軸（stable / hotspot / co-change）はいずれも **git churn ベースの時系列統計**を
扱うが、コードベースを「どこで切られているか」という構造的事実は別軸で必要となる。

これは PRINCIPLE 2「測量に徹する（Surveyor, Not Interpreter）」を侵さない
範囲で、解釈を含まない事実のみを記録する第 4 軸として定義できる。

意味判断（type 判定・edges 推定・Component Card 最終形成）は agent 側責務として残し、
cartographer は **「scan_dirs 配下の直下サブディレクトリ一覧」** のみを出力する。

---

## Decision

`output/` 配下に第 4 測量軸 `components.json` を canonical 出力として追加する。

| 項目 | 内容 |
|------|------|
| 軸名 | `components`（第 4 軸） |
| 出力ファイル | `output/components.json`（canonical） |
| 検出方式 | **許可リスト方式**（`scan_dirs` 配下の直下サブディレクトリのみ） |
| 設定ファイル | `.cartographer.toml`（リポジトリルート、Optional） |
| 設定形式 | TOML（`tomllib` 標準ライブラリで読む） |
| 組込デフォルト | `["src", "lib", "lambda", "packages", "apps", "services", "functions"]` |
| 設定上書き | `--config <path>` で別パス指定可能 |
| 除外ロジック | **`.gitignore` のみ**（許可リスト一本化） |
| トリガー | 既存 3 軸と同一（HEAD ベーススキップを共有、4 ファイル一括生成） |
| 警告条件 | components 数が 150 を超えた場合 stderr に warning（fail-loud） |
| 初期動作確認言語 | Python / TypeScript（tree-sitter 既対応の範囲内） |

`components.json` のスキーマは既存 3 軸と統一する：

```json
{
  "head": "<commit_hash>",
  "generated_at": "<ISO8601>",
  "scan_dirs": ["src", "lib", ...],
  "components": [
    {
      "path": "src/cartographer",
      "scan_dir": "src",
      "name": "cartographer"
    },
    ...
  ]
}
```

---

## Rationale

### なぜ第 4 軸として cartographer に組み込むか

- **L2 探索コスト削減**: agent が毎回フルスキャンする代わりに、canonical `components.json` を読むだけで済む
- **canonical 永続化**: 構造的事実は git churn と同様、長寿命の測量データである
- **既存パイプラインへの自然な追加**: HEAD ベーススキップ・出力フォーマットを共有でき、追加コストが最小

### なぜ TOML を採用するか

| 観点 | 採用 | 却下 |
|------|------|------|
| 形式 | **TOML** | YAML / JSON |

- **外部依存ゼロ**: Python 3.11+ 標準の `tomllib` のみで読める。`pyyaml` を新規依存に追加しない
- **人間編集向き**: コメント可、ネスト浅め、output JSON との視覚的区別が明確
- **設定 vs データの分離**: 入力（TOML）と出力（JSON）の取り違えが起きにくい

### なぜ「組込デフォルト + 単一オーバーライド」方式か

- **忘れられる構造（PRINCIPLE 1）**: 多くの ward は `.cartographer.toml` を置かなくても動く
- **同梱 toml を ward 側に配る方式は却下**: ward 側に余計なファイルを増やす運用が「忘れられる構造」を破壊する
- **必須宣言方式は却下**: 設定がないと動かない設計は L2 探索コスト削減という目的と矛盾する

### なぜ「許可リスト一本」で `tests/`, `_test` 等の除外ロジックを実装しないか

- **スキーマ単純化**: 許可リストと除外リストの併用はルール優先度の議論を生む
- **ハードコード除外の禁止**: `tests/`、`_test` などをコード側で特別扱いすると、
  「意味判断（型推論）を測量側に持ち込む」という PRINCIPLE 2 違反に直結する
- **必要な除外は `.gitignore` で表現する**: 単一の境界ファイルに集約し、`git ls-files` 起点に統一する

### なぜステム共通性集約を実装しないか

- **解釈責務（PRINCIPLE 2 整合）**: 「どのステムが意味を持つコンポーネントか」は agent 側の判断
- **canonical 単一化**: 集約・分割を cartographer 側で行うと canonical が複数候補に分裂する
- **YAGNI**: 集約パターンは agent 側で必要になった時点で生やせる

### なぜ初期スコープを Python / TypeScript に絞るか

- **tree-sitter 採用 ADR との整合**: 既存対応言語（Python / JS / TS / Go）の段階的導入と揃える
- ※ Phase 1〜4 では AST 解析を必須としない（ディレクトリ走査・サブディレクトリ抽出のみで完結）。
  AST が必要になった場合のみ既存パターンに従う

---

## Consequences

- `output/components.json` が新規 canonical 出力として追加される（既存 3 軸の出力フォーマットは変更しない）
- `.cartographer.toml` がリポジトリルートにあれば優先、なければ組込デフォルトを使う
- `--config <path>` CLI オプションが追加され、別パスの toml を指定可能
- HEAD ベーススキップは 4 ファイル（stable / hotspot / co-change / components）を一括スキップする
- components 数が 150 を超えた場合は stderr に warning を出す（fail-loud）。`scan_dirs` の絞り込みを利用者に促す
- 既存 EARS-001 への影響評価は別途行う（components 軸の機械可読要件は別 EARS とすることを想定）

---

## Rejected Alternatives

**A. agent 側合成のみで完結させる（cartographer に組み込まない）**
- 理由: 同じ構造的事実を agent が毎回再構築するのはトークン浪費。canonical 永続化の利益を捨てる

**B. YAML を設定形式に採用する（pyyaml 追加）**
- 理由: 軽量スタック原則違反。tomllib で十分な目的に対し、外部依存を追加するメリットが乏しい

**C. ward 側に同梱 `.cartographer.toml` を必須化する**
- 理由: 「忘れられる構造」を破壊する。多くの ward でノーアクションで動く設計を優先する

**D. `tests/`、`_test` 等のハードコード除外を入れる**
- 理由: 解釈の混入。許可リスト一本化（`.gitignore` のみ）に揃える

**E. ステム共通性集約を cartographer 側で実装する**
- 理由: 解釈責務（PRINCIPLE 2 違反）。canonical 単一化原則と矛盾する

**F. 初期から全言語対応する**
- 理由: YAGNI。tree-sitter ADR の段階的導入と整合させる
