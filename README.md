# git-cartographer

コードベースの時空間的地図を継続生成する**測量機械**。

git churn × AST依存解析（静的測量）と Claude Code の踏破軌跡（動的測量）を統合し、
LLM ゼロ・統計処理のみで地図が自律的に重要地点を学習する。

> **地図製作者は現地を解釈しない。測量して記録するだけ。**

---

## 出力される地図（3層）

| ファイル | 内容 |
|---------|------|
| `output/stable.md` | 変更頻度ゼロの安定ファイル一覧 |
| `output/structure.md` | co-change ペア・import グラフ・ハブファイル |
| `output/hotspots.md` | churn 上位ファイル（変更頻度ランキング） |

---

## クイックスタート

```bash
uv sync
uv run python -m src.cartographer /path/to/your/repo
```

初回はフルスキャン、2回目以降は `.cartographer_state` を参照して差分のみ更新する。
リセットしたい場合は `.cartographer_state` を削除すれば次回フルスキャンが走る。

---

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [PRINCIPLE.md](PRINCIPLE.md) | 設計思想・原則・Non-Goals |
| [Runbook.md](Runbook.md) | セットアップ・操作・トラブルシューティング |
