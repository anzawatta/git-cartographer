# git-cartographer

コードベースの時空間的地図を継続生成する**測量機械**。

git churn × AST依存解析（静的測量）と Claude Code の踏破軌跡（動的測量）を統合し、
LLM ゼロ・統計処理のみで地図が自律的に重要地点を学習する。

> **地図製作者は現地を解釈しない。測量して記録するだけ。**

---

## 出力される地図（3層）

JSON / JSONL が canonical 出力。Markdown は `--markdown` フラグ指定時のみ生成される。

| ファイル | 形式 | 内容 |
|---------|------|------|
| `output/hotspot.json` | JSON | churn 上位ファイル（変更頻度ランキング） |
| `output/co-change.jsonl` | NDJSON | co-change ペア（1行1エッジ） |
| `output/stable.json` | JSON | 変更頻度ゼロの安定ファイル一覧 |
| `output/hotspot.md` | Markdown | hotspot の人間向け閲覧用（opt-in） |
| `output/co-change.md` | Markdown | co-change の人間向け閲覧用（opt-in） |
| `output/stable.md` | Markdown | stable の人間向け閲覧用（opt-in） |

---

## クイックスタート

```bash
uv sync
uv run python -m src.cartographer /path/to/your/repo
```

毎回、最新 `window`（デフォルト100）コミットをスキャンして地図を生成する。
HEAD が変わっていない場合は `.cartographer_state` によりスキップされる。

Markdown 出力も必要な場合は `--markdown` フラグを追加する：

```bash
uv run python -m src.cartographer /path/to/your/repo --markdown
```

スキップ最適化をリセットしたい場合は `.cartographer_state` を削除すれば次回実行時に再スキャンが走る。

---

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [PRINCIPLE.md](PRINCIPLE.md) | 設計思想・原則・Non-Goals |
| [Runbook.md](Runbook.md) | セットアップ・操作・トラブルシューティング |
| [docs/adr/](docs/adr/) | 設計決定記録（ADR） |
