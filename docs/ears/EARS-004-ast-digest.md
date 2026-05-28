---
provides:
  - REQ-U001
  - REQ-U002
  - REQ-U003
  - REQ-U004
  - REQ-W001
  - REQ-S001
  - REQ-C001
requires:
  - EARS-001#REQ-S001
---
# EARS-004: AST Digest Canonical Output

**Status:** Draft
**Date:** 2026-05-28
**Related ADR:** —

## 不変条件

1. REQ-U001: System は、`scan_dirs` 配下の `.py` / `.js` / `.ts` / `.go` ファイル全てを対象に、ファイルごとのシンボルダイジェストを `output/ast-digest.json` として出力しなければならない
2. REQ-U002: System は、シンボル抽出エンジンとして `ast_scanner.extract_symbol_digest()` のみを使用しなければならない（他の AST ライブラリへの依存を追加してはならない）
3. REQ-U003: MVP において、Python ファイルは完全なシンボルリストを生成し、`.js` / `.ts` / `.go` ファイルは `parse_status: "skipped_language"` かつ `symbols: []` を返さなければならない
4. REQ-U004: System は `output/ast-digest.json` を tmpfile + `os.replace` によりアトミックに書き込まなければならない（部分書き込みがコンシューマーに到達してはならない）

## 敵対条件

1. REQ-W001: System は、シンボル名のフィルタリングや解釈を行ってはならない（アンダースコアプレフィックス除外、ALL_CAPS フィルタリング等を実装してはならない） — PRINCIPLE §2「Surveyor, Not Interpreter」

## 状態駆動条件

1. REQ-S001: HEAD が `.cartographer_state` に記録されたハッシュと一致する場合、System は `ast-digest.json` の再生成をスキップしなければならない（他軸との一括スキップ）

## コールドスタート条件

1. REQ-C001: git history が存在しない場合、System は `{"status": "no_history", "generated_at": "...", "files": []}` を内容とする `ast-digest.json` を出力しなければならない

## [ADV] 既知の制限・トレードオフ

- `name` フィールドのシンボルエントリはパスプレフィックス付きドット記法（例: `src/foo.py:ClassName.method`）を使用する。コンシューマーはこの文字列を不透明な値として扱わなければならない — ファイルのリネームにより、そのファイルの全エントリが無効化される（リネームをまたぐ安定識別子は存在しない）。これは grep-friendliness のためのトレードオフとして受け入れられている。(GZ-6, GZ-7)
- `ast-digest.json` が存在しない場合（例: コンシューマーが cartographer より先に実行された場合）、コンシューマーは graceful fallback すべきである: `symbol` を `null` として扱い、一度だけ stderr に `"warning: ast-digest.json not found at {path}; symbol resolution disabled. → Fix: run cartographer first"` を出力する。(GZ-9)
- stderr の頻度: 失敗ファイルごとに1行/ラン。重複排除なし。変更頻度の高いリポジトリでは多数の warning が出力される可能性がある — fail-loud 動作を維持するためこれは受け入れられている。(GZ-10, GZ-12)
- `parse_status: "skipped_language"` は意図的であり、stderr は出力しない。stderr を出力するのは `"failed"` と `"skipped_size"` のみ。(GZ-12)

## [INV] アトミック書き込みの不変条件

`output/ast-digest.json` は必ず `tmpfile + os.replace` によりアトミックに書き込まれなければならない。書き込み中のクラッシュにより、正規パスに部分的な JSON ファイルが残ってはならない。(GZ-11)

## 出力 JSON スキーマ

```json
{
  "generated_at": "<ISO-8601>",
  "head_hash": "<sha>",
  "files": [
    {
      "path": "src/cartographer.py",
      "parse_status": "ok",
      "symbols": [
        {"name": "Cartographer", "kind": "class", "line_start": 25, "line_end": 180},
        {"name": "Cartographer.run", "kind": "method", "line_start": 42, "line_end": 95},
        {"name": "main", "kind": "function", "line_start": 200, "line_end": 215},
        {"name": "supported_extensions", "kind": "variable", "line_start": 14, "line_end": 14}
      ]
    },
    {
      "path": "src/something.ts",
      "parse_status": "skipped_language",
      "symbols": []
    }
  ]
}
```

| フィールド | 値 |
|-----------|-----|
| `parse_status` | `"ok"` / `"skipped_language"` / `"skipped_size"` / `"failed"` |
| `kind` | `"function"` / `"class"` / `"method"` / `"variable"` |
| `name` | モジュールレベルはプレーン名、メソッドはドット記法 `Class.method` |
