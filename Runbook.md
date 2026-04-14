# git-cartographer Runbook

コードベースの地図を自動生成する測量機械のセットアップ・操作ガイド。

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd /path/to/git-cartographer
uv sync
```

tree-sitter および各言語パーサー（Python / JS / TS / Go）が自動インストールされる。

### 2. 動作確認

```bash
uv run python -m src.cartographer --help
```

---

## 地図生成の実行方法

### 基本実行（カレントディレクトリのリポジトリを解析）

```bash
uv run python -m src.cartographer .
```

### リポジトリパスを明示的に指定

```bash
uv run python -m src.cartographer /path/to/your/repo
```

### オプション

```bash
uv run python -m src.cartographer /path/to/repo \
  --output-dir output \          # 出力先ディレクトリ（リポジトリ相対）
  --output-dir /absolute/path \  # 絶対パス指定も可（リポジトリ外に出力）
  --window 100                   # フルスキャン時に参照するコミット数
```

### 複数リポジトリをまとめて解析する例

```bash
for repo in repositories/*/; do
  uv run python -m src.cartographer "$repo" \
    --output-dir "$(realpath $repo)/output"
done
```

### 出力ファイル

実行後、`output/` 配下に以下の Markdown ファイルが生成される：

| ファイル | 内容 |
|---------|------|
| `output/stable.md` | 変更頻度ゼロの安定ファイル一覧 |
| `output/structure.md` | co-change ペア・import グラフ・ハブファイル |
| `output/hotspots.md` | churn 上位ファイル（変更頻度ランキング） |

---

## Claude Code Hooks の設定方法

PostToolUse / PreToolUse フックを `.claude/settings.json` に登録することで、
踏破録の自動記録とコンテキスト注入が有効になる。

### settings.json サンプル

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/git-cartographer && uv run python -m src.hooks.post_tool_use"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/git-cartographer && uv run python -m src.hooks.pre_tool_use"
          }
        ]
      }
    ]
  }
}
```

> **注意**: `cd /path/to/git-cartographer` の部分は実際のパスに置き換えること。

---

## `.cartographer_state` のリセット方法

差分モードをリセットし、次回実行時にフルスキャンを強制する：

```bash
rm /path/to/repo/.cartographer_state
```

ファイルを削除した状態で `cartographer` を実行すると、リポジトリ全体が再スキャンされる。

---

## `.cartographer_traverse_log.yml` の見方

踏破録は YAML 形式で保存される：

```yaml
entries:
  src/main.py:
    score: 2.847
    last_hash: abc123def456...
    accessed_at: "2026-04-12T10:30:00+00:00"
  src/utils.py:
    score: 1.0
    last_hash: abc123def456...
    accessed_at: "2026-04-12T09:15:00+00:00"
```

| フィールド | 説明 |
|-----------|------|
| `score` | アクセス頻度スコア（20コミット経過で半減、0.1未満で自動削除） |
| `last_hash` | スコアが最後に更新されたときのコミットハッシュ |
| `accessed_at` | 最終アクセス日時（ISO 8601） |

### スコアの解釈

- **高スコア（2.0+）**: 最近頻繁にアクセスされている重要ファイル
- **中スコア（0.5〜2.0）**: 数コミット前に活発だったファイル
- **低スコア（0.1〜0.5）**: 遠い過去にアクセスされたが今は静かなファイル
- **0.1未満**: 次回 `cartographer` 実行時に自動削除

### git 管理について

踏破録はデフォルトで git 管理対象となる。
アクセスパターンを git 履歴に残したくない場合は `.gitignore` に追加する：

```
.cartographer_traverse_log.yml
```

---

## トラブルシューティング

### `git command failed` エラー

- カレントディレクトリが git リポジトリかを確認する
- `git log` が実行できる状態かを確認する

### TreeSitter 関連エラー

- `uv sync` で依存パッケージを再インストールする
- 未対応の言語ファイルは自動的にスキップされる（エラーにならない）

### フックが動作しない

- `settings.json` のパスが正しいかを確認する
- `uv run python -m src.hooks.post_tool_use` を直接実行してエラーがないかを確認する
