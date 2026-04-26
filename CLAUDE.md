# git-cartographer

コードベースの時空間的地図を継続生成する測量ツール。

git churn × AST依存解析（静的測量）と Claude Code の踏破軌跡（動的測量）を統合する。


## Locale

### Landmarks
- `PRINCIPLE.md`           — 設計原則・衝突ルール・Non-Goals（設計判断の必読文書）
- `src/cartographer.py`    — エントリポイント。全体フロー制御（`run()` メソッド）
- `src/layers.py`          — 3層地図生成エンジン（stable / hotspot / co-change）
- `src/components.py`      — 第4軸 components 測量モジュール（scan_dirs 直下サブディレクトリ抽出）
- `src/config.py`          — `.cartographer.toml` パーサ（tomllib、組込デフォルト管理）
- `docs/ears/EARS-001.md`  — 地図生成の機械可読要件定義
- `docs/adr/ADR-003-components-axis.md` — 第4軸 components 採用根拠（許可リスト方式 / TOML 採用 / 解釈分離）

### Districts
- `src/`       — 実装本体（測量・合成・状態管理・統制）
- `src/hooks/` — Claude Code Hooks 統合（PostToolUse + PreToolUse）
- `tests/`     — 単体テスト（unittest 直接駆動。`python3 -m unittest tests.<...>` で実行）
- `output/`    — 生成物（JSON / JSONL / Markdown）。
- `docs/`      — 設計ドキュメント（ADR・EARS）

### Edges
- `git CLI`           — read-only（log / diff / rev-parse / ls-files）。リポジトリ変更なし
- `Claude Code Hooks` — stdin/stdout の JSON I/O。PreToolUse で踏破録をコンテキスト注入
- `output/`           — 書き込み境界（4 canonical: hotspot / co-change / stable / components × JSON/JSONL、+ `--markdown` で 3 MD）
- `.cartographer.toml` — リポジトリルートの設定境界（components 軸 scan_dirs オーバーライド、Optional）
- `.cartographer_traverse_log.yml` — Hooks が副作用を持つ唯一のファイル（スコア記録・減衰）

### Components
<!-- 機械検出結果は logs/maps/git-cartographer/map.md の「コンポーネント」セクション参照 -->
- `Measurement` — git churn × AST 依存解析 + 構造的境界抽出。LLM ゼロ、副作用なし（git_scanner, ast_scanner, components）
- `Synthesis`   — 3層地図合成 + skeleton.json 生成（layers, skeleton）
- `Config`      — TOML 読み込み + 組込デフォルト管理（config）
- `State`       — スキップ最適化（.cartographer_state）+ 踏破録 YAML 管理（state, traverse_log）
- `Hooks`       — 唯一の観測点。PostToolUse（アクセス記録）/ PreToolUse（踏破録注入）

<!-- last-verified: 2026-04-26 -->
