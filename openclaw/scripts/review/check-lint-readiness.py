#!/usr/bin/env python3
"""Check root Biome metadata/config without running pnpm or the linter.

Supports pnpm-v9's generated block-YAML root devDependencies stanza only.
Exit 0: metadata checks passed, NOT lint passed. Exit 2: blocked/unknown.
Does not verify executable provenance, extended configs, runtime or lint results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


class ReadinessError(ValueError):
    pass


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReadinessError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def metadata(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ReadinessError(f"{path.name} must contain an object")
    return data


def field(lines: list[str], key: str, indent: int) -> tuple[int, str]:
    name = re.escape(key)
    pattern = re.compile(rf' {{{indent}}}(?:{name}|\'{name}\'|"{name}") *:(.*)')
    matches = [(i, m[1].strip()) for i, line in enumerate(lines)
               if (m := pattern.fullmatch(line))]
    if len(matches) != 1:
        raise ReadinessError(f"expected exactly one {key} at indentation {indent}")
    return matches[0]


def block(lines: list[str], key: str, indent: int) -> list[str]:
    index, tail = field(lines, key, indent)
    if tail:
        raise ReadinessError(f"unsupported block syntax for {key}")
    end = index + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.lstrip().startswith("#"):
            if len(line) - len(line.lstrip(" ")) <= indent:
                break
        end += 1
    return lines[index + 1:end]


def scalar(lines: list[str], key: str, indent: int) -> str:
    _, value = field(lines, key, indent)
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    if not re.fullmatch(r"[~^]?[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.+-]+)?", value):
        raise ReadinessError(f"unsupported scalar for {key}")
    return value


def locked_biome(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if "\t" in text or any(line in {"---", "..."} for line in lines):
        raise ReadinessError("unsupported lockfile syntax")
    _, version = field(lines, "lockfileVersion", 0)
    if version not in {"'9.0'", '"9.0"', "9.0"}:
        raise ReadinessError("only pnpm lockfile version 9.0 is supported")
    root = block(block(lines, "importers", 0), ".", 2)
    stanza = block(block(root, "devDependencies", 4), "@biomejs/biome", 6)
    # Extra/continued fields may change YAML meaning; inspect instead of guessing.
    meaningful = [line for line in stanza if line.strip() and not line.lstrip().startswith("#")]
    if len(meaningful) != 2:
        raise ReadinessError("unsupported Biome lock stanza")
    specifier = scalar(stanza, "specifier", 8)
    exact = scalar(stanza, "version", 8)
    if exact.startswith(("~", "^")):
        raise ReadinessError("locked Biome version is not exact")
    return specifier, exact


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=10
    ).stdout


def check_readiness(repo: Path) -> dict:
    repo = repo.expanduser().resolve(strict=True)
    if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
        raise ReadinessError("--repo must identify the Git worktree root")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    package = metadata(repo / "package.json")
    dev = package.get("devDependencies")
    if not isinstance(dev, dict) or not isinstance(dev.get("@biomejs/biome"), str):
        raise ReadinessError("missing root Biome devDependency")
    specifier, locked = locked_biome((repo / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    installed = metadata(repo / "node_modules/@biomejs/biome/package.json")
    if installed.get("name") != "@biomejs/biome" or not isinstance(installed.get("version"), str):
        raise ReadinessError("invalid installed Biome package metadata")
    configs = [repo / name for name in ("biome.json", "biome.jsonc")
               if (repo / name).exists() or (repo / name).is_symlink()]
    if len(configs) != 1:
        raise ReadinessError("expected exactly one root biome.json or biome.jsonc")
    config = configs[0]
    current = config.read_bytes()
    baseline = git(repo, "show", f"{head}:{config.name}")
    checks = {
        "declaredMatchesLock": dev["@biomejs/biome"] == specifier,
        "installedMatchesLock": installed["version"] == locked,
        "rootConfigMatchesHead": current == baseline,
    }
    return {
        "ok": all(checks.values()),
        "status": "metadata_checks_passed" if all(checks.values()) else "blocked",
        "headSha": head,
        "declaredSpecifier": dev["@biomejs/biome"],
        "lockSpecifier": specifier,
        "lockedVersion": locked,
        "installedVersion": installed["version"],
        "config": config.name,
        "configSha256": hashlib.sha256(current).hexdigest(),
        "headConfigSha256": hashlib.sha256(baseline).hexdigest(),
        "checks": checks,
        "lintExecuted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="Git worktree root")
    args = parser.parse_args()
    try:
        result = check_readiness(args.repo)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Git stderr can contain unrelated source content; do not echo it.
        error = "Git metadata/config unavailable" if isinstance(exc, subprocess.SubprocessError) else str(exc)
        result = {"ok": False, "status": "blocked", "error": error, "lintExecuted": False}
    result["scope"] = "Root metadata/config only; not lint, executable or extended-config verification."
    result["nextStep"] = (
        "Run repository lint after the separate dependency-containment check."
        if result["ok"] else
        "Inspect stale/unsupported metadata or review intentional config edits; do not substitute a trimmed config or claim repository lint passed."
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
