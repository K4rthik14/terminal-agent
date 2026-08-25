"""Packaging regression checks: wheel metadata must match real runtime packages."""

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every first-party package the installed application can import at runtime,
# including library components shipped intentionally (orchestration, memory)
# and the evaluation harness entry point (evals).
EXPECTED_PACKAGES = {
    "agent",
    "cli",
    "config",
    "context",
    "evals",
    "llm",
    "memory",
    "orchestration",
    "rlm",
    "tools",
    "utils",
    "verification",
}


def load_pyproject() -> dict[str, Any]:
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def test_wheel_packages_list_matches_real_runtime_packages() -> None:
    pyproject = load_pyproject()
    packages = set(pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])

    assert packages == EXPECTED_PACKAGES


def test_every_listed_package_exists_on_disk() -> None:
    pyproject = load_pyproject()
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]

    for name in packages:
        assert (REPO_ROOT / name).is_dir(), f"listed package does not exist: {name}"


def test_console_scripts_preserve_reflex_and_legacy_aliases() -> None:
    scripts = load_pyproject()["project"]["scripts"]

    assert scripts["reflex"] == "cli.main:main"
    # Intentional legacy aliases kept for backward compatibility.
    for alias in ("trace", "nanocode", "agent"):
        assert scripts[alias] == "cli.main:main"


def test_cli_entry_module_imports_only_listed_packages() -> None:
    """Guard against new top-level imports being missed in wheel metadata."""
    entry = (REPO_ROOT / "cli" / "main.py").read_text(encoding="utf-8")
    pyproject = load_pyproject()
    packages = set(pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])

    for line in entry.splitlines():
        root = _import_root(line)
        if root in EXPECTED_PACKAGES:
            assert root in packages, f"runtime import of unshipped package: {root}"


def _import_root(line: str) -> str:
    stripped = line.strip()
    parts = stripped.split()
    if len(parts) >= 2 and parts[0] in {"from", "import"}:
        return parts[1].split(".")[0]
    return ""
