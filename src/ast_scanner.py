"""
TreeSitter AST 解析（依存関係・インターフェース面積）。

対応言語: Python, JavaScript, TypeScript, Go
未対応言語は graceful skip（空結果を返す）。
"""

from __future__ import annotations

import os
import sys
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


# --- extract_symbol_digest helpers ---

DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def _find_child_of_type(node, node_type: str):
    """Return the first direct child of node whose type matches node_type, or None."""
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _get_node_name(node, source: bytes) -> str | None:
    """Extract the identifier text from a function_definition or class_definition node."""
    id_node = _find_child_of_type(node, "identifier")
    if id_node is None:
        return None
    return _extract_text(id_node, source)


def _py_extract_symbols(parent_node, source: bytes, class_context: str | None = None) -> list[dict]:
    """
    Extract symbols from a module or class body node.

    Recurses into class bodies to collect methods (dotted ClassName.method notation).
    Does NOT recurse into function bodies — nested functions are out of MVP scope.

    class_context: if set, method names are prefixed as "ClassName.method".
    """
    results = []
    for child in parent_node.children:
        node_type = child.type

        # Handle decorated definitions: use outer node's line range, unwrap inner def/class
        if node_type == "decorated_definition":
            inner = _find_child_of_type(child, "function_definition") or \
                    _find_child_of_type(child, "async_function_definition") or \
                    _find_child_of_type(child, "class_definition")
            if inner is None:
                continue
            name = _get_node_name(inner, source)
            if name is None:
                continue
            # Line range comes from the outer decorated_definition (includes decorators)
            line_start = child.start_point[0] + 1
            line_end = child.end_point[0] + 1
            if inner.type == "class_definition":
                results.append({"name": name, "kind": "class",
                                 "line_start": line_start, "line_end": line_end})
                # Recurse into class body
                body = _find_child_of_type(inner, "block")
                if body is not None:
                    results.extend(_py_extract_symbols(body, source, class_context=name))
            else:
                kind = "method" if class_context is not None else "function"
                full_name = f"{class_context}.{name}" if class_context is not None else name
                results.append({"name": full_name, "kind": kind,
                                 "line_start": line_start, "line_end": line_end})
            continue

        # Regular function (sync or async)
        if node_type in ("function_definition", "async_function_definition"):
            name = _get_node_name(child, source)
            if name is None:
                continue
            kind = "method" if class_context is not None else "function"
            full_name = f"{class_context}.{name}" if class_context is not None else name
            line_start = child.start_point[0] + 1
            line_end = child.end_point[0] + 1
            results.append({"name": full_name, "kind": kind,
                             "line_start": line_start, "line_end": line_end})
            continue

        # Class definition
        if node_type == "class_definition":
            name = _get_node_name(child, source)
            if name is None:
                continue
            line_start = child.start_point[0] + 1
            line_end = child.end_point[0] + 1
            results.append({"name": name, "kind": "class",
                             "line_start": line_start, "line_end": line_end})
            # Recurse into class body to extract methods
            body = _find_child_of_type(child, "block")
            if body is not None:
                results.extend(_py_extract_symbols(body, source, class_context=name))
            continue

        # Module-level variable: expression_statement > assignment where LHS is a single identifier
        # Only collect at module/top level (not inside a class body)
        if node_type == "expression_statement" and class_context is None:
            assign = _find_child_of_type(child, "assignment")
            if assign is not None:
                lhs = assign.children[0] if assign.children else None
                if lhs is not None and lhs.type == "identifier":
                    name = _extract_text(lhs, source)
                    line_start = child.start_point[0] + 1
                    line_end = child.end_point[0] + 1
                    results.append({"name": name, "kind": "variable",
                                    "line_start": line_start, "line_end": line_end})
            continue

    return results


# Why: GZ-8
# parse_status uses sub-classifications (skipped_language / skipped_size / failed)
# rather than a single skipped value so that consumers can distinguish:
#   - skipped_language: expected behaviour (language not supported, no action needed)
#   - skipped_size:     recoverable config issue (raise max_file_size or split the file)
#   - failed:           potential bug or malformed input (worth investigating)
# A single "skipped" would collapse all three into an opaque result.

# Why: GZ-5
# extract_symbol_digest() does NOT filter out "_"-prefixed names, unlike interface_area()
# which excludes them when counting public symbols for Python.
# Reason: PRINCIPLE §2 "Surveyor, Not Interpreter" — this function records all symbols
# as structural fact without interpretation. interface_area() was designed for a different
# purpose (estimating public API surface); that filtering reflects an intentional semantic
# choice inappropriate here.
def extract_symbol_digest(path: str, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> dict:
    """
    Return a per-file symbol digest for the given path.

    Output schema:
        {
            "parse_status": "ok" | "skipped_language" | "skipped_size" | "failed",
            "symbols": [
                {"name": str, "kind": "function"|"class"|"method"|"variable",
                 "line_start": int, "line_end": int},
                ...
            ]
        }

    Only Python is supported for MVP. All other extensions return parse_status="skipped_language".
    """
    ext = os.path.splitext(path)[1].lower()

    # Non-Python extensions: graceful skip, no stderr
    if ext != ".py":
        return {"parse_status": "skipped_language", "symbols": []}

    # Size check before reading full content
    try:
        file_size = os.path.getsize(path)
    except OSError:
        # File not found or inaccessible
        print(f"warning: AST parse failed: {path} (file not found or inaccessible)",
              file=sys.stderr)
        return {"parse_status": "failed", "symbols": []}

    if file_size > max_file_size:
        print(
            f"warning: AST parse skipped (size): {path} ({file_size} bytes > {max_file_size})",
            file=sys.stderr,
        )
        return {"parse_status": "skipped_size", "symbols": []}

    source = _read_file_bytes(path)
    if source is None:
        print(f"warning: AST parse failed: {path} (could not read file)", file=sys.stderr)
        return {"parse_status": "failed", "symbols": []}

    parser, _lang = _get_parser(ext)
    if parser is None:
        print(f"warning: AST parse failed: {path} (parser unavailable)", file=sys.stderr)
        return {"parse_status": "failed", "symbols": []}

    try:
        tree = parser.parse(source)
        root = tree.root_node
        symbols = _py_extract_symbols(root, source, class_context=None)
        return {"parse_status": "ok", "symbols": symbols}
    except Exception as exc:
        print(f"warning: AST parse failed: {path} ({exc})", file=sys.stderr)
        return {"parse_status": "failed", "symbols": []}
