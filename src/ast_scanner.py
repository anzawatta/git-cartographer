"""
TreeSitter AST 解析（依存関係・インターフェース面積）。

対応言語: Python, JavaScript, TypeScript, Go
未対応言語は graceful skip（空結果を返す）。
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

# @see EARS-001#REQ-U003
supported_extensions = {".py", ".js", ".ts", ".go"}

# 言語ごとの import ノードタイプ定義
_IMPORT_QUERY: dict[str, dict[str, Any]] = {
    ".py": {
        "node_types": ["import_statement", "import_from_statement"],
    },
    ".js": {
        "node_types": ["import_statement", "call_expression"],
    },
    ".ts": {
        "node_types": ["import_statement", "call_expression"],
    },
    ".go": {
        "node_types": ["import_declaration", "import_spec"],
    },
}

# 言語ごとの公開シンボルノードタイプ定義
_PUBLIC_SYMBOL_TYPES: dict[str, list[str]] = {
    ".py": ["function_definition", "class_definition"],
    ".js": [
        "function_declaration",
        "class_declaration",
        "export_statement",
        "method_definition",
    ],
    ".ts": [
        "function_declaration",
        "class_declaration",
        "export_statement",
        "method_definition",
        "interface_declaration",
        "type_alias_declaration",
    ],
    ".go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
}


@lru_cache(maxsize=None)
def _get_language(ext: str):
    """TreeSitter 言語オブジェクトをキャッシュ付きで返す。未対応は None。"""
    try:
        if ext == ".py":
            import tree_sitter_python as tspython
            from tree_sitter import Language
            return Language(tspython.language())
        elif ext in (".js",):
            import tree_sitter_javascript as tsjavascript
            from tree_sitter import Language
            return Language(tsjavascript.language())
        elif ext == ".ts":
            import tree_sitter_typescript as tstypescript
            from tree_sitter import Language
            return Language(tstypescript.language_typescript())
        elif ext == ".go":
            import tree_sitter_go as tsgo
            from tree_sitter import Language
            return Language(tsgo.language())
    except Exception:
        return None
    return None


def _get_parser(ext: str):
    """TreeSitter パーサーを返す。未対応・失敗時は None。"""
    lang = _get_language(ext)
    if lang is None:
        return None, None
    try:
        from tree_sitter import Parser
        parser = Parser(lang)
        return parser, lang
    except Exception:
        return None, None


def _read_file_bytes(file_path: str) -> bytes | None:
    """ファイルをバイト列で読む。失敗時は None。"""
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _collect_nodes_by_type(node, target_types: list[str]) -> list:
    """指定ノードタイプを再帰的に収集する。"""
    results = []
    if node.type in target_types:
        results.append(node)
    for child in node.children:
        results.extend(_collect_nodes_by_type(child, target_types))
    return results


def _extract_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _py_imports_from_tree(root_node, source: bytes) -> list[str]:
    """Python の import 文から参照モジュール名を抽出する。"""
    imports = []
    nodes = _collect_nodes_by_type(
        root_node, ["import_statement", "import_from_statement"]
    )
    for node in nodes:
        text = _extract_text(node, source).strip()
        # 単純抽出: "from X import Y" -> "X", "import X" -> "X"
        if text.startswith("from "):
            parts = text.split()
            if len(parts) >= 2:
                imports.append(parts[1])
        elif text.startswith("import "):
            parts = text.replace(",", " ").split()
            for p in parts[1:]:
                if p and p != "as":
                    imports.append(p)
                    break
    return imports


def _js_imports_from_tree(root_node, source: bytes) -> list[str]:
    """JS/TS の import 文から参照モジュール名を抽出する。"""
    imports = []
    nodes = _collect_nodes_by_type(root_node, ["import_statement"])
    for node in nodes:
        # 'from "path"' or 'from \'path\''
        for child in node.children:
            if child.type == "string":
                text = _extract_text(child, source).strip("\"'")
                imports.append(text)
    # require() 呼び出しも収集
    call_nodes = _collect_nodes_by_type(root_node, ["call_expression"])
    for node in call_nodes:
        children = list(node.children)
        if children and _extract_text(children[0], source) == "require":
            for child in node.children:
                if child.type == "arguments":
                    for arg in child.children:
                        if arg.type == "string":
                            text = _extract_text(arg, source).strip("\"'")
                            imports.append(text)
    return imports


def _go_imports_from_tree(root_node, source: bytes) -> list[str]:
    """Go の import 文から参照パスを抽出する。"""
    imports = []
    nodes = _collect_nodes_by_type(root_node, ["import_spec"])
    for node in nodes:
        for child in node.children:
            if child.type == "interpreted_string_literal":
                text = _extract_text(child, source).strip("\"")
                imports.append(text)
    return imports


# @see EARS-001#REQ-U003
def extract_imports(file_path: str) -> list[str]:
    """
    ファイルの import 文から依存ファイル（モジュール名）を推定して返す。
    未対応言語・解析失敗時は空リストを返す（graceful skip）。
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in supported_extensions:
        return []

    source = _read_file_bytes(file_path)
    if source is None:
        return []

    parser, lang = _get_parser(ext)
    if parser is None:
        return []

    try:
        tree = parser.parse(source)
        root = tree.root_node

        if ext == ".py":
            return _py_imports_from_tree(root, source)
        elif ext in (".js", ".ts"):
            return _js_imports_from_tree(root, source)
        elif ext == ".go":
            return _go_imports_from_tree(root, source)
    except Exception:
        pass

    return []


# @see EARS-001#REQ-U003
def interface_area(file_path: str) -> int:
    """
    公開関数・クラス数（インターフェース面積の代理指標）を返す。
    未対応言語・解析失敗時は 0 を返す（graceful skip）。

    Python: def / class のトップレベル定義数
    JS/TS: export された宣言数 + function/class 宣言数
    Go: 大文字で始まる function/type 宣言数
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in supported_extensions:
        return 0

    source = _read_file_bytes(file_path)
    if source is None:
        return 0

    parser, lang = _get_parser(ext)
    if parser is None:
        return 0

    try:
        tree = parser.parse(source)
        root = tree.root_node
        symbol_types = _PUBLIC_SYMBOL_TYPES.get(ext, [])
        nodes = _collect_nodes_by_type(root, symbol_types)

        if ext == ".py":
            # トップレベルの定義のみカウント（インデントなし）
            top_level = [
                n for n in nodes if n.parent is not None and n.parent.type == "module"
            ]
            # アンダースコア始まりは非公開
            count = 0
            for n in top_level:
                for child in n.children:
                    if child.type == "identifier":
                        name = _extract_text(child, source)
                        if not name.startswith("_"):
                            count += 1
                        break
            return count

        elif ext in (".js", ".ts"):
            # export_statement をカウント
            export_nodes = [n for n in nodes if n.type == "export_statement"]
            return len(export_nodes)

        elif ext == ".go":
            # 大文字で始まる関数・型をカウント
            count = 0
            for n in nodes:
                for child in n.children:
                    if child.type == "identifier":
                        name = _extract_text(child, source)
                        if name and name[0].isupper():
                            count += 1
                        break
            return count

    except Exception:
        pass

    return 0
