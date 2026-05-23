"""Structural guards for the refactored modules.

These replace a lot of manual click-testing: they fail if a module no longer
imports, or if any function body references a name that isn't imported/defined
(the kind of bug that only shows up at runtime, e.g. the missing
`config`/`analyzer as AN` imports caught while splitting modes/).
"""
import ast
import builtins
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

MODULES = [
    "app_context", "game_loop_common", "state", "menu_helpers",
    "save_load", "learningbase_admin", "chessMain",
    "modes.common", "modes.play_game", "modes.brainmaster",
    "modes.replay", "modes.models",
]


@pytest.mark.parametrize("mod", MODULES)
def test_module_imports(mod):
    importlib.import_module(mod)


def _undefined_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    defined = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                defined.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        elif isinstance(n, ast.arg):
            defined.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            defined.add(n.id)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            defined.update(n.names)
    used = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in defined:
            used.setdefault(n.id, n.lineno)
    return used


@pytest.mark.parametrize("mod", MODULES)
def test_no_undefined_names(mod):
    path = ROOT / (mod.replace(".", "/") + ".py")
    undefined = _undefined_names(path)
    assert not undefined, f"undefined names in {path.name}: {undefined}"
