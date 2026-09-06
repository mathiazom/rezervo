#!/usr/bin/env python3
"""Upgrade uv-managed dependencies to the latest version within their
existing pyproject.toml specifier, skipping releases newer than 2 days.

Usage: uv run poe bump-deps
"""

import re
import subprocess
import sys
import tomllib
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_AGE = timedelta(days=2)

VersionTuple = tuple[int, ...]


def parse_version(v: str) -> VersionTuple | None:
    if not re.fullmatch(r"\d+(\.\d+)*", v):
        return None
    return tuple(int(p) for p in v.split("."))


def parse_requirement(req: str) -> tuple[str, list[tuple[str, VersionTuple]]]:
    name, _, spec = req.partition(">=")
    # requirement strings in this repo are always "name>=x,<y" or "name>=x,<y # comment"
    spec = spec.split("#", 1)[0].strip()
    name = name.strip()
    clauses: list[tuple[str, VersionTuple]] = [(">=", parse_version(spec.split(",")[0]))]  # type: ignore[list-item]
    for part in spec.split(",")[1:]:
        part = part.strip()
        m = re.match(r"(>=|<=|==|!=|>|<)(.+)", part)
        if not m:
            continue
        op, ver = m.groups()
        parsed = parse_version(ver)
        if parsed is not None:
            clauses.append((op, parsed))
    return name, clauses


def satisfies(version: VersionTuple, clauses: list[tuple[str, VersionTuple]]) -> bool:
    for op, bound in clauses:
        if op == ">=" and not version >= bound:
            return False
        if op == "<=" and not version <= bound:
            return False
        if op == ">" and not version > bound:
            return False
        if op == "<" and not version < bound:
            return False
        if op == "==" and not version == bound:
            return False
        if op == "!=" and not version != bound:
            return False
    return True


def format_spec(clauses: list[tuple[str, VersionTuple]]) -> str:
    return ",".join(f"{op}{'.'.join(map(str, v))}" for op, v in clauses)


def fetch_pypi_releases(name: str) -> dict[VersionTuple, datetime]:
    url = f"https://pypi.org/pypi/{name}/json"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = __import__("json").load(resp)
    releases: dict[VersionTuple, datetime] = {}
    for ver_str, files in data.get("releases", {}).items():
        if not files or all(f.get("yanked") for f in files):
            continue
        version = parse_version(ver_str)
        if version is None:
            continue
        upload_time = min(
            datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00"))
            for f in files
        )
        releases[version] = upload_time
    return releases


def load_dependencies() -> list[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = list(pyproject["project"]["dependencies"])
    for group in pyproject.get("dependency-groups", {}).values():
        deps.extend(g for g in group if isinstance(g, str))
    return deps


def load_locked_versions() -> dict[str, VersionTuple]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return {
        pkg["name"]: parse_version(pkg["version"])
        for pkg in lock["package"]
        if parse_version(pkg["version"]) is not None
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    locked = load_locked_versions()

    updated: list[str] = []
    skipped_too_new: list[str] = []
    skipped_major: list[str] = []
    to_upgrade: list[str] = []

    for req in load_dependencies():
        name, clauses = parse_requirement(req)
        current = locked.get(name)
        if current is None:
            continue
        try:
            releases = fetch_pypi_releases(name)
        except Exception as e:
            print(f"warning: failed to fetch {name} from PyPI: {e}", file=sys.stderr)
            continue
        if not releases:
            continue

        allowed = {v: t for v, t in releases.items() if satisfies(v, clauses)}
        absolute_latest = max(releases)

        if absolute_latest not in allowed and absolute_latest > max(allowed, default=current):
            skipped_major.append(
                f"{name} {'.'.join(map(str, absolute_latest))} available, "
                f"constrained to {format_spec(clauses)}"
            )

        old_enough = {v: t for v, t in allowed.items() if now - t > MIN_AGE}
        best_allowed = max(old_enough, default=current)

        if best_allowed > current:
            to_upgrade.append(name)
            updated.append(
                f"{name} {'.'.join(map(str, current))} -> {'.'.join(map(str, best_allowed))}"
            )
        elif max(allowed, default=current) > current:
            newest = max(allowed)
            skipped_too_new.append(
                f"{name} {'.'.join(map(str, newest))} available, "
                f"released {now - releases[newest]} ago"
            )

    if to_upgrade:
        args = ["uv", "lock"]
        for name in to_upgrade:
            args += ["--upgrade-package", name]
        subprocess.run(args, cwd=ROOT, check=True)

    print("Updated:")
    for line in updated:
        print(f"  {line}")
    if not updated:
        print("  (none)")

    print("Skipped (too new, <2 days old):")
    for line in skipped_too_new:
        print(f"  {line}")
    if not skipped_too_new:
        print("  (none)")

    print("Skipped (major version bump, outside pyproject ceiling):")
    for line in skipped_major:
        print(f"  {line}")
    if not skipped_major:
        print("  (none)")


if __name__ == "__main__":
    main()
