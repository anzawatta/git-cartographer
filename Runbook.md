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
  --output-dir output \          # 出力先ディレクトリ（リポジトリ相対、デフォルト: output）
  --output-dir /absolute/path \  # 絶対パス指定も可（リポジトリ外に出力）
  --window 100 \                 # スキャンする最新コミット数（デフォルト: 100）
  --markdown \                   # Markdown ファイルも生成する（デフォルト: 生成しない）
  --halflife-commits 90          # co-change の半減期（コミット数、デフォルト: 90）
```

### 複数リポジトリをまとめて解析する例

```bash
for repo in repositories/*/; do
  uv run python -m src.cartographer "$repo" \
    --output-dir "$(realpath $repo)/output"
done
```

### 出力ファイル

実行後、`output/` 配下に以下のファイルが生成される：

JSON / JSONL が canonical 出力。Markdown は `--markdown` 指定時のみ生成される。

| ファイル | 形式 | 内容 |
|---------|------|------|
| `output/hotspot.json` | JSON | churn 上位ファイル（変更頻度ランキング） |
| `output/co-change.jsonl` | NDJSON | co-change ペア（1行1エッジ） |
| `output/stable.json` | JSON | 変更頻度ゼロの安定ファイル一覧 |
| `output/hotspot.md` | Markdown | hotspot の人間向け閲覧用（`--markdown` opt-in） |
| `output/co-change.md` | Markdown | co-change の人間向け閲覧用（`--markdown` opt-in） |
| `output/stable.md` | Markdown | stable の人間向け閲覧用（`--markdown` opt-in） |

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

## `.cartographer.toml` の設定方法

### サンプルファイルをコピーして使う

リポジトリルートにサンプルをコピーし、必要に応じて編集する：

```bash
cp /path/to/git-cartographer/.cartographer.toml.sample /path/to/your/repo/.cartographer.toml
```

設定ファイルがない場合は組込デフォルトが使われるため、必須ではない。

### ネストパスの指定

`scan_dirs` にはネストしたパス（例: `"packages/shared"`）も指定可能で、各エントリの直下サブディレクトリがコンポーネントとして認識される。`"src"` と `"src/modules"` のように深いパスと浅いパスが両方含まれる場合は、深いパスが優先される。

```toml
[components]
scan_dirs = [
    "src",
    "packages",
    "packages/shared",   # src/modules/foo は src より packages/shared が優先される
]
```

---

## `.cartographer_state` のリセット方法

`.cartographer_state` は HEAD 未変更時のスキップ最適化に使われる。
削除すると、次回実行時に最新 `window` コミットの再スキャンが強制される。

```bash
rm /path/to/repo/.cartographer_state
```

> `window` の値を変更しても次コミット時に自動的に再スキャンされるため、
> 通常は手動削除は不要。

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
