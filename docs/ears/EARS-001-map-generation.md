# EARS-001: Map Generation

**Status:** Draft
**Date:** 2026-04-12
**Related ADR:** -

## 不変条件

1. REQ-U001: System は、出力を `output/` 配下の Markdown ファイルのみとしなければならない
2. REQ-U002: System は、地図を stable / structure / hotspots の3層に分離して管理しなければならない
3. REQ-U003: System は、AST 解析に TreeSitter のみを使用しなければならない
4. REQ-U004: System は、コードベース解析に git コマンドと TreeSitter のみを使用しなければならない（embedding・専用DB等の重量依存を持ち込まない）

## 敵対条件

1. REQ-W001: System は、コードの自動修正・リファクタリング提案を行ってはならない
2. REQ-W002: System は、UI（Markdown 以外の出力形式）を提供してはならない
3. REQ-W003: System は、複数リポジトリの横断解析を行ってはならない
4. REQ-W004: System は、Claude Code 以外のエージェントに対応する機能を持ってはならない

## 状態駆動条件

1. REQ-S001: `.cartographer_state` が存在しない場合、System はリポジトリ全体のフルスキャンを実行し、完了後に HEAD のコミットハッシュを `.cartographer_state` に記録しなければならない
2. REQ-S002: `.cartographer_state` が存在する場合、System は記録済みハッシュから HEAD までの差分ファイルのみを再解析しなければならない
3. REQ-S003: stable 層は、churn 頻度が低い（過去 N コミットで変更なし）ファイルのみを含まなければならない
