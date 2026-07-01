#!/usr/bin/env python3
"""Generate docs/COMMANDS.md from cog source without importing Red."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
COG_DIRS = (
    "imperialsetup",
    "developmentops",
    "botops",
    "imperialautomation",
    "studyops",
    "musicstatus",
)
OUTPUT = ROOT / "docs" / "COMMANDS.md"


@dataclass(order=True)
class CommandInfo:
    cog: str
    qualified_name: str
    function_name: str
    kind: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    checks: tuple[str, ...] = field(default_factory=tuple)
    docstring: str = ""
    source: str = ""
    line: int = 0


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    return ""


def literal_string(node: ast.AST) -> str | None:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, str) else None


def literal_string_list(node: ast.AST) -> tuple[str, ...]:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def decorator_call(decorator: ast.AST) -> tuple[str, ast.Call | None]:
    if isinstance(decorator, ast.Call):
        return dotted_name(decorator.func), decorator
    return dotted_name(decorator), None


def command_name(function: ast.AsyncFunctionDef | ast.FunctionDef, call: ast.Call | None) -> str:
    if call is None:
        return function.name
    for keyword in call.keywords:
        if keyword.arg == "name":
            value = literal_string(keyword.value)
            if value:
                return value
    if call.args:
        value = literal_string(call.args[0])
        if value:
            return value
    return function.name


def command_aliases(call: ast.Call | None) -> tuple[str, ...]:
    if call is None:
        return ()
    for keyword in call.keywords:
        if keyword.arg == "aliases":
            return literal_string_list(keyword.value)
    return ()


def check_name(name: str) -> str | None:
    mapping = {
        "commands.guild_only": "guild only",
        "commands.is_owner": "owner only",
        "commands.admin": "admin",
        "commands.admin_or_permissions": "admin/manage guild",
        "commands.guildowner_or_permissions": "guild owner/admin",
        "commands.bot_has_permissions": "bot permissions",
    }
    if name in mapping:
        return mapping[name]
    if name.endswith(".guild_only"):
        return "guild only"
    if name.endswith(".is_owner"):
        return "owner only"
    if name.endswith(".admin_or_permissions"):
        return "admin/manage guild"
    return None


def render_docstring(node: ast.AsyncFunctionDef | ast.FunctionDef) -> str:
    doc = ast.get_docstring(node) or ""
    return " ".join(line.strip() for line in doc.splitlines() if line.strip())


class CommandVisitor(ast.NodeVisitor):
    def __init__(self, cog: str, source_path: Path):
        self.cog = cog
        self.source_path = source_path
        self.commands: list[CommandInfo] = []
        self.command_functions: dict[str, str] = {}

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.AsyncFunctionDef | ast.FunctionDef) -> None:
        checks: list[str] = []
        command_decorator: tuple[str, ast.Call | None] | None = None

        for decorator in node.decorator_list:
            name, call = decorator_call(decorator)
            check = check_name(name)
            if check:
                checks.append(check)
            if name in {"commands.command", "commands.group"}:
                command_decorator = (name, call)
            elif name.endswith(".command") or name.endswith(".group"):
                command_decorator = (name, call)

        if command_decorator is not None:
            decorator_name, call = command_decorator
            kind = "group" if decorator_name.endswith(".group") else "command"
            name = command_name(node, call)
            parent = ""
            if "." in decorator_name and not decorator_name.startswith("commands."):
                parent = decorator_name.rsplit(".", 1)[0]
            qualified = f"{self.command_functions.get(parent, parent)} {name}".strip()
            info = CommandInfo(
                cog=self.cog,
                qualified_name=qualified,
                function_name=node.name,
                kind=kind,
                aliases=command_aliases(call),
                checks=tuple(dict.fromkeys(checks)),
                docstring=render_docstring(node),
                source=str(self.source_path.relative_to(ROOT)).replace("\\", "/"),
                line=node.lineno,
            )
            self.commands.append(info)
            self.command_functions[node.name] = qualified

        self.generic_visit(node)


def discover_commands() -> list[CommandInfo]:
    commands: list[CommandInfo] = []
    for cog in COG_DIRS:
        for path in sorted((ROOT / cog).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            visitor = CommandVisitor(cog, path)
            visitor.visit(tree)
            commands.extend(visitor.commands)
    return sorted(commands)


def markdown_table(commands: Iterable[CommandInfo]) -> str:
    lines = [
        "# Command Reference",
        "",
        "Generated from source by `python scripts/generate_command_reference.py`.",
        "Do not edit command rows by hand.",
        "",
        "| Cog | Command | Type | Function | Aliases | Checks | Source | Description |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in commands:
        aliases = ", ".join(f"`{alias}`" for alias in item.aliases) or "-"
        checks = ", ".join(item.checks) or "-"
        description = item.docstring.replace("|", "\\|") or "-"
        lines.append(
            "| "
            f"{item.cog} | "
            f"`[p]{item.qualified_name}` | "
            f"{item.kind} | "
            f"`{item.function_name}` | "
            f"{aliases} | "
            f"{checks} | "
            f"`{item.source}:{item.line}` | "
            f"{description} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(markdown_table(discover_commands()), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
