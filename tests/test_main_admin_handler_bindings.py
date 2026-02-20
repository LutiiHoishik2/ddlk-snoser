import ast
from pathlib import Path


def _admin_handler_method_names(admin_handlers_path: Path) -> set[str]:
    tree = ast.parse(admin_handlers_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "AdminHandlers":
            return {
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def test_main_registers_existing_admin_handler_methods_only():
    root = Path(__file__).resolve().parents[1]
    main_path = root / "rabanok_bot" / "main.py"
    admin_handlers_path = root / "rabanok_bot" / "handlers" / "admin_handlers.py"

    existing_methods = _admin_handler_method_names(admin_handlers_path)
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "register"):
            continue
        if not node.args:
            continue

        handler_expr = node.args[0]
        if not isinstance(handler_expr, ast.Attribute):
            continue
        parent = handler_expr.value
        if not (isinstance(parent, ast.Attribute) and parent.attr == "admin_handlers"):
            continue
        if not (isinstance(parent.value, ast.Name) and parent.value.id == "self"):
            continue

        method_name = handler_expr.attr
        if method_name not in existing_methods:
            missing.append(method_name)

    assert not missing, f"main.py registers unknown AdminHandlers methods: {sorted(set(missing))}"
