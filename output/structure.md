# Structure Layer

依存関係・co-change 構造の地図。

## Scan Info

- **Mode**: full
- **HEAD**: `fe376f0aab80`
- **Generated**: 2026-04-14T12:55:47.275517+00:00

## Co-change Top Pairs

同一コミットで頻繁に同時変更されるファイルペア。

| File A | File B | Count |
|--------|--------|-------|
| `Runbook.md` | `src/cartographer.py` | 2 |
| `Runbook.md` | `docs/ears/EARS-002-pheromone.md` | 2 |
| `.gitignore` | `Runbook.md` | 1 |
| `.gitignore` | `docs/ears/EARS-002-pheromone.md` | 1 |
| `.gitignore` | `output/.gitkeep` | 1 |
| `.gitignore` | `pyproject.toml` | 1 |
| `.gitignore` | `src/__init__.py` | 1 |
| `.gitignore` | `src/ast_scanner.py` | 1 |
| `.gitignore` | `src/cartographer.py` | 1 |
| `.gitignore` | `src/git_scanner.py` | 1 |
| `.gitignore` | `src/hooks/__init__.py` | 1 |
| `.gitignore` | `src/hooks/post_tool_use.py` | 1 |
| `.gitignore` | `src/hooks/pre_tool_use.py` | 1 |
| `.gitignore` | `src/layers.py` | 1 |
| `.gitignore` | `src/state.py` | 1 |
| `.gitignore` | `src/traverse_log.py` | 1 |
| `Runbook.md` | `output/.gitkeep` | 1 |
| `Runbook.md` | `pyproject.toml` | 1 |
| `Runbook.md` | `src/__init__.py` | 1 |
| `Runbook.md` | `src/ast_scanner.py` | 1 |

## Hub Files

多数のファイルから import されているハブファイル。

| File | Referenced By |
|------|--------------|
| `tree_sitter` | 5 |
| `src.git_scanner` | 2 |
| `src.traverse_log` | 2 |
| `yaml` | 2 |
| `tree_sitter_python` | 1 |
| `tree_sitter_javascript` | 1 |
| `tree_sitter_typescript` | 1 |
| `tree_sitter_go` | 1 |
| `src` | 1 |

## Import Graph (抜粋)

ファイルごとの import 依存先（上位 20 ファイル）。

- `src/ast_scanner.py` → `os`, `functools`, `typing`, `tree_sitter_python`, `tree_sitter`, ... (+7)
- `src/cartographer.py` → `argparse`, `os`, `sys`, `datetime`, `src`, ... (+1)
- `src/git_scanner.py` → `subprocess`, `collections`, `itertools`
- `src/hooks/post_tool_use.py` → `json`, `os`, `sys`, `src.git_scanner`, `src.traverse_log`
- `src/hooks/pre_tool_use.py` → `json`, `os`, `sys`, `src.traverse_log`
- `src/layers.py` → `sys`, `datetime`
- `src/state.py` → `os`, `datetime`
- `src/traverse_log.py` → `os`, `datetime`, `yaml`, `yaml`, `src.git_scanner`
