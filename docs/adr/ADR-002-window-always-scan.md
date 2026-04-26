# ADR-002: Window-Always Scan（インクリメンタルモード廃止）

**Status:** Accepted
**Date:** 2026-04-26

---

## Context

当初の設計では `.cartographer_state` に前回スキャン時の HEAD ハッシュを記録し、
次回実行時はそのハッシュ以降の差分（delta）のみを解析する「インクリメンタルモード」を採用していた。

しかしこの設計には根本的な矛盾があった。

- `--window 100` は「最新100コミットの地図」を意味する
- インクリメンタルモードは「前回以降の差分」を地図として出力する

コミットを重ねるたびに hotspot・co-change は delta しか反映しなくなり、
`window` の持つ意味（「最新N件に基づく地図」）が失われていく。
初回フルスキャン後にインクリメンタルを数回繰り返すと、
ほぼ空に近いマップが canonical 出力として残り続けた。

---

## Decision

インクリメンタルモードを廃止し、**常に最新 `window` コミットをスキャン**する。

`.cartographer_state` の役割を「HEAD 未変更時のスキップ最適化」に限定する。

| 状態 | 動作 |
|------|------|
| HEAD が state と一致 | 実行スキップ（`HEAD unchanged. Skipping.`） |
| HEAD が state と不一致 / state なし | 最新 `window` コミットをフルスキャン → state 更新 |

---

## Rationale

### なぜ window-always か

- **正確性**: 毎回同じ時間軸（最新N件）で地図を生成するため、出力が一貫する
- **シンプルさ**: スキャンモードが1つになり、コードの分岐が消える
- **パフォーマンス**: `git log -100` は高速（< 1秒）。incremental の恩恵が薄い

### `.cartographer_state` を残す理由

Hooks 経由で頻繁に呼ばれる環境では、同じ HEAD に対して何度も実行される。
スキップ最適化として state ファイルを残すことで、不要なスキャンを防ぐ。

### インクリメンタルが有効だった唯一のケース

stable 層の引き継ぎロジック（前回 stable から変更ファイルを除外）は
近似的に動いていたが、window 範囲外のファイルが stable に残留するケースがあり、
厳密には正確でなかった。window-always では全追跡ファイルを毎回評価するため、
stable 層も常に正確になる。

---

## Consequences

- `scan_info` の `mode` / `since_hash` フィールドを廃止し `window` フィールドを追加
- `co-change.jsonl` メタ行の `"range"` を `"window"` に変更（破壊的変更）
- `window` を変えても state を手動削除する必要がなくなった（次コミット時に自動再スキャン）

---

## Rejected Alternatives

**A. インクリメンタルを維持してチャーンを累積する**
- 理由: 「window 外に出たコミットをどう引き算するか」の設計が複雑になる。軽量スタック原則に反する

**B. `.cartographer_state` を廃止する**
- 理由: Hooks 経由の頻繁呼び出し環境でムダなスキャンが増える。ファイルの存在コストは無視できる
