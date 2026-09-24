"""Architecture tests using AST analysis.

Ensures that vendor SDKs are only imported in app/providers/ and that all
modules under app/ import without error.
"""

import ast
import importlib
import sys
from pathlib import Path


# Vendor SDK packages that must ONLY be imported in app/providers/
VENDOR_PACKAGES = {
    "google": "google-genai (Gemini)",
    "openai": "openai",
    "groq": "groq",
    "pipecat": "pipecat",
    "chatterbox": "chatterbox",
    "kaggle": "kaggle",
    "torch": "torch",
}

APP_ROOT = Path(__file__).parent.parent / "app"


def get_all_app_modules() -> list[Path]:
    """Get all .py files under app/ (excluding __pycache__)."""
    return sorted(APP_ROOT.glob("**/*.py"))


def extract_imports(file_path: Path) -> set[str]:
    """Extract top-level module names imported in a file using AST."""
    imports = set()

    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError as e:
        raise SyntaxError(f"Failed to parse {file_path}: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Get the top-level package name
                pkg = alias.name.split(".")[0]
                imports.add(pkg)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Get the top-level package name
                pkg = node.module.split(".")[0]
                imports.add(pkg)

    return imports


def is_in_providers(file_path: Path) -> bool:
    """Check if a file is in app/providers/."""
    try:
        file_path.relative_to(APP_ROOT / "providers")
        return True
    except ValueError:
        return False


def test_no_vendor_imports_outside_providers():
    """Vendor SDK imports must be contained in app/providers/ only."""
    violations = []

    for module_path in get_all_app_modules():
        if module_path.name == "__init__.py":
            continue

        imports = extract_imports(module_path)
        vendored = imports & set(VENDOR_PACKAGES.keys())

        if vendored and not is_in_providers(module_path):
            rel_path = module_path.relative_to(APP_ROOT)
            for pkg in sorted(vendored):
                violations.append(f"{rel_path}: imports {pkg} ({VENDOR_PACKAGES[pkg]})")

    assert not violations, (
        "Vendor SDK imports must be contained in app/providers/.\n" + "\n".join(violations)
    )


def test_all_app_modules_import_without_error():
    """All modules under app/ must import without error.

    This catches syntax errors, missing dependencies, and circular imports.
    """
    # Get all Python modules under backend/app
    backend_root = APP_ROOT.parent
    sys.path.insert(0, str(backend_root))

    import_errors = []

    for module_path in get_all_app_modules():
        if module_path.name == "__init__.py":
            continue

        # Convert file path to module name
        # e.g., backend/app/people/models.py -> app.people.models
        try:
            rel_path = module_path.relative_to(backend_root)
            # Remove .py and convert / to .
            module_name = str(rel_path)[:-3].replace("\\", ".").replace("/", ".")

            # Skip importing providers that need API keys
            if "providers/llm_" in str(module_path) or "providers/stt_" in str(module_path):
                continue

            try:
                importlib.import_module(module_name)
            except ImportError as e:
                import_errors.append(f"{module_name}: {e}")
            except Exception as e:
                import_errors.append(f"{module_name}: {type(e).__name__}: {e}")
        except ValueError:
            pass

    assert not import_errors, (
        "Some app modules failed to import:\n" + "\n".join(import_errors)
    )
