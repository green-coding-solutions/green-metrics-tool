import ast
import sys
from pathlib import Path

GMT_DIR = Path(__file__).resolve().parent.parent


def _get_imported_modules(path):
    """Return the set of top-level module names imported anywhere in *path*."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # absolute imports only
                modules.add(node.module.split('.')[0])
    return modules


def _assert_stdlib_only(path):
    non_stdlib = _get_imported_modules(path) - sys.stdlib_module_names
    assert not non_stdlib, (
        f"{path.name} imports non-stdlib packages: {sorted(non_stdlib)}. "
        "Root-owned scripts must only use stdlib so that all dependencies "
        "are owned by root and cannot be tampered with via the venv."
    )


def test_system_checks_root_stdlib_only():
    _assert_stdlib_only(GMT_DIR / 'lib' / 'system_checks_root.py')


def test_hardware_info_root_original_stdlib_only():
    _assert_stdlib_only(GMT_DIR / 'lib' / 'hardware_info_root_original.py')


def test_maintenance_original_stdlib_only():
    _assert_stdlib_only(GMT_DIR / 'tools' / 'cluster' / 'maintenance_original.py')
