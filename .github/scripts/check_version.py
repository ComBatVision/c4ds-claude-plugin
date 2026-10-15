#!/usr/bin/env python3
"""Fail when a change under plugins/ does not raise the plugin version and add a changelog entry.

Users only get a plugin update when the version in plugin.json goes up, so a change that forgets
the bump never reaches them.

Usage: check_version.py <base-ref>   (for example origin/main)
"""

import json
import re
import subprocess
import sys

MANIFEST = "plugins/c4ds/.claude-plugin/plugin.json"
CHANGELOG = "CHANGELOG.md"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def semver(version: str) -> tuple:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        sys.exit(f"error: {MANIFEST} version {version!r} is not MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def main() -> None:
    base = sys.argv[1]
    changed = git("diff", "--name-only", f"{base}...HEAD").stdout.split()
    plugin_changes = [path for path in changed if path.startswith("plugins/")]
    if not plugin_changes:
        print("No changes under plugins/; no version bump needed.")
        return

    head = json.load(open(MANIFEST)).get("version")
    if not head:
        sys.exit(f"error: {MANIFEST} has no version")
    old = git("show", f"{base}:{MANIFEST}")
    base_version = json.loads(old.stdout).get("version", "0.0.0") if old.returncode == 0 else "0.0.0"

    errors = []
    if semver(head) <= semver(base_version):
        errors.append(f"plugins/ changed ({len(plugin_changes)} files) but the version is {head}, "
                      f"not higher than {base_version} on {base}. Raise it in {MANIFEST}.")
    if not re.search(rf"^## {re.escape(head)}\s*$", open(CHANGELOG).read(), re.MULTILINE):
        errors.append(f"{CHANGELOG} has no `## {head}` entry.")
    if errors:
        sys.exit("error: " + "\nerror: ".join(errors))
    print(f"Version {base_version} -> {head}, changelog entry present.")


if __name__ == "__main__":
    main()
