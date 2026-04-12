# EARS-002: Traverse log Layer

**Status:** Draft
**Date:** 2026-04-12
**Related ADR:** -

## 不変条件

1. REQ-U001: System は、踏破録を `score × (0.5 ^ (commits_elapsed / 20))` の式で減衰させなければならない
2. REQ-U002: 踏破録は、git 管理対象のリポジトリ内に配置しなければならない（`.gitignore` による除外は利用者判断で許容）

## 敵対条件

1. REQ-W001: System は、スコアが 0.1 未満になったエントリを踏破録に保持してはならない
2. REQ-W002: System は、踏破録の手動操作インターフェースを提供してはならない（忘却は自動のみ）

## イベント駆動条件

1. REQ-E001: PostToolUse Hook が発火したとき、System はアクセスされたファイルパスとそのタイミングのコミットハッシュを踏破録に追記しなければならない
2. REQ-E002: PreToolUse Hook が発火したとき、System は踏破録スコア上位のファイルリストをコンテキストとして Claude Code に注入しなければならない
