#!/usr/bin/env python3
"""Inspect installed pnpm directory containment without running a package manager."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


class LayoutError(ValueError):
    pass


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LayoutError(f"duplicate metadata key: {key}")
        result[key] = value
    return result


def virtual_store_value(text: str) -> str:
    """Read JSON or pnpm's simple block-YAML path; reject unfamiliar syntax."""
    if text.lstrip().startswith("{"):
        data = json.loads(text, object_pairs_hook=unique_object)
        value = data.get("virtualStoreDir")
    else:
        values = []
        in_store_scalar = False
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith((" ", "\t")):
                if in_store_scalar:
                    raise LayoutError("multiline YAML virtualStoreDir needs manual inspection")
                continue
            if line == "---":
                raise LayoutError("YAML document markers need manual inspection")
            match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*):(?:[ \t]+(.*))?", line)
            if not match:
                raise LayoutError("unsupported top-level YAML syntax; inspect metadata manually")
            in_store_scalar = match[1] == "virtualStoreDir"
            if in_store_scalar:
                values.append(match[2] or "")
        if len(values) != 1:
            raise LayoutError("metadata must define exactly one virtualStoreDir")
        value = values[0]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not re.fullmatch(r"[A-Za-z0-9_./@+\-]+", value):
            raise LayoutError("unsupported YAML virtualStoreDir scalar; inspect metadata manually")
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise LayoutError("metadata virtualStoreDir must be a nonempty path string")
    return value


def contained(path: Path, repo: Path, *, directory: bool) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(repo):
        raise LayoutError(f"{path.name} resolves outside the worktree")
    if directory and not resolved.is_dir():
        raise LayoutError(f"{path.name} is not a directory")
    if not directory and not resolved.is_file():
        raise LayoutError(f"{path.name} is not a regular file")
    return resolved


def check_layout(repo: Path) -> None:
    repo = repo.expanduser().resolve(strict=True)
    if not repo.is_dir():
        raise LayoutError("worktree path is not a directory")
    modules = contained(repo / "node_modules", repo, directory=True)
    metadata = contained(modules / ".modules.yaml", repo, directory=False)
    store = Path(virtual_store_value(metadata.read_text(encoding="utf-8")))
    if ".." in store.parts:
        raise LayoutError("parent traversal in virtualStoreDir needs manual inspection")
    contained(modules / store, repo, directory=True)
    conventional = modules / ".pnpm"
    if conventional.exists() or conventional.is_symlink():
        contained(conventional, repo, directory=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only installed pnpm directory-containment check; never runs pnpm. "
        "Does not validate dependency versions, package symlinks, hardlinks or future pnpm config."
    )
    parser.add_argument("--repo", required=True, type=Path, help="Worktree root to inspect")
    args = parser.parse_args(argv)
    try:
        check_layout(args.repo)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"BLOCKED: {exc}. Do not run pnpm against shared or unverified installed directories.", file=sys.stderr)
        return 2
    print("Installed pnpm root/virtual-store containment OK; dependency readiness is not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
