"""Safe patching helpers for the Lila CLI.

Never searches for "the first )" — that broke ``main.py`` when a comment
contained ``(None para desactivar)``. This module scans the real ``App(...)``
call with a small state machine that respects strings, comments and brackets.
"""

from typing import Optional


def find_matching_paren(text: str, open_index: int) -> int:
    """Returns the index after the matching ``)`` for the ``(`` at open_index."""
    depth = 0
    i = open_index
    length = len(text)
    in_single = False
    in_double = False
    in_triple_single = False
    in_triple_double = False
    in_comment = False

    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""
        prev = text[i - 1] if i > 0 else ""

        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue

        if in_triple_single:
            if ch == "'" and text[i:i + 3] == "'''":
                in_triple_single = False
                i += 3
                continue
            i += 1
            continue
        if in_triple_double:
            if ch == '"' and text[i:i + 3] == '"""':
                in_triple_double = False
                i += 3
                continue
            i += 1
            continue

        if in_single:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "#":
            in_comment = True
            i += 1
            continue
        if text[i:i + 3] == "'''":
            in_triple_single = True
            i += 3
            continue
        if text[i:i + 3] == '"""':
            in_triple_double = True
            i += 3
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            i += 1
            continue

        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def add_import(main_content: str, import_stmt: str, anchor: str = "app = App(") -> str:
    if import_stmt.strip() in main_content:
        return main_content
    marker = "# lila:imports"
    if marker in main_content:
        return main_content.replace(marker, f"{marker}\n{import_stmt}", 1)
    idx = main_content.find(anchor)
    if idx == -1:
        return f"{import_stmt}\n{main_content}"
    return main_content[:idx] + f"{import_stmt}\n\n" + main_content[idx:]


def add_includes(main_content: str, include_stmt: str, anchor: str = "app = App(") -> str:
    if include_stmt.strip() in main_content:
        return main_content

    start_marker = "# lila:includes:start"
    end_marker = "# lila:includes:end"
    if start_marker in main_content and end_marker in main_content:
        start = main_content.index(start_marker) + len(start_marker)
        end = main_content.index(end_marker)
        block = main_content[start:end]
        if include_stmt.strip() in block:
            return main_content
        return main_content[:end] + f"\n{include_stmt}\n" + main_content[end:]

    idx = main_content.find(anchor)
    if idx == -1:
        return f"{main_content.rstrip()}\n\n{include_stmt}\n"
    paren = main_content.find("(", idx)
    end = find_matching_paren(main_content, paren)
    if end == -1:
        return f"{main_content.rstrip()}\n\n{include_stmt}\n"

    # Insert after the closing parenthesis, on its own line.
    line_end = main_content.find("\n", end)
    if line_end == -1:
        return f"{main_content}\n{include_stmt}\n"
    return f"{main_content[:line_end + 1]}{include_stmt}\n{main_content[line_end + 1:]}"


def patch_main(main_path: str, import_stmt: str, include_stmt: str) -> bool:
    """Patches main.py safely. Returns True when the file changed."""
    try:
        with open(main_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except Exception:
        return False

    updated = add_import(content, import_stmt)
    updated = add_includes(updated, include_stmt)
    if updated == content:
        return False
    try:
        compile(updated, main_path, "exec")
    except SyntaxError:
        # Never write a broken main.py. Leave the project untouched.
        return False
    with open(main_path, "w", encoding="utf-8") as fh:
        fh.write(updated)
    return True
