"""Read a scenario file without running it: only top-level assignments of Python literals are accepted.

A held-out scenario is model-written text. Loading it with `exec` would run whatever code it holds in the process
that loads it (an author could print into a tool's output, write files, or plant text an `atexit` hook prints).
This reader parses the file with `ast` and evaluates each value with `ast.literal_eval`, so nothing in the file is
ever executed. A module docstring is allowed; anything else (an import, a function, a call, an f-string, a name
used as a value, `**` unpacking) is refused with a fixed code, never with text from the file.

  read(path) -> types.SimpleNamespace of the assigned names
Raises NotLiteral(code) with code one of: "unreadable", "syntax", "statement", "target", "value", "duplicate".
Standard library only.
"""
from __future__ import annotations

import ast
import types
from pathlib import Path

CODES = ("unreadable", "syntax", "statement", "target", "value", "duplicate")


class NotLiteral(ValueError):
    """A scenario file that is not only top-level literal assignments; ``code`` is one of CODES."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def read(path) -> types.SimpleNamespace:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise NotLiteral("unreadable") from None
    try:
        tree = ast.parse(source, filename="scenario")
    except (SyntaxError, ValueError):
        raise NotLiteral("syntax") from None
    values = {}
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue  # The module docstring.
        if not isinstance(node, ast.Assign):
            raise NotLiteral("statement")
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise NotLiteral("target")
        name = node.targets[0].id
        if name in values:
            raise NotLiteral("duplicate")
        try:
            values[name] = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            raise NotLiteral("value") from None
    return types.SimpleNamespace(**values)


def is_literal(path) -> bool:
    try:
        read(path)
    except NotLiteral:
        return False
    return True
