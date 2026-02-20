import ast
from pathlib import Path


def _defined_state_classes(states_file: Path) -> set[str]:
    tree = ast.parse(states_file.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def test_handlers_import_existing_states_only():
    repo_root = Path(__file__).resolve().parents[1]
    states_file = repo_root / "rabanok_bot" / "utils" / "states.py"
    handlers_dir = repo_root / "rabanok_bot" / "handlers"

    known_states = _defined_state_classes(states_file)
    missing: list[tuple[str, str]] = []

    for handler_file in handlers_dir.glob("*.py"):
        tree = ast.parse(handler_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "utils.states":
                continue
            for alias in node.names:
                if alias.name not in known_states:
                    missing.append((handler_file.name, alias.name))

    assert not missing, f"Unknown state imports in handlers: {missing}"
