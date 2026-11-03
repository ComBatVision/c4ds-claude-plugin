#!/usr/bin/env python3
"""Check a plugin folder against the Claude plugin directory's validation rules.

The rules follow the plugin pre-submission checklist
(https://claude.com/docs/plugins/pre-submission-checklist), which describes what the developer
portal's Validate button checks. The portal's code is not public, so this is a copy of the
documented rules, not the portal itself. Checks the portal makes against its own data (name taken
or confusable with another listing, known brands) cannot run here. The credential and
download-and-run checks are heuristics that match what the portal reported for this plugin.

Results use the portal's levels: BLOCKS (cannot submit), HOLD (a reviewer reads the version),
WARN and NOTE. Exits 1 when anything blocks.

Usage: check_directory.py [plugin-dir]   (default plugins/c4ds; needs PyYAML)
"""

from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path

import yaml

KIB = 1024
TEXT_LIMIT = 256 * KIB
FILE_LIMIT = 512
REPO_FILE_LIMIT = 5 * KIB * KIB
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
BINARY_EXT = {".ico", ".pdf", ".zip", ".jar", ".apk", ".exe", ".dll", ".so", ".dylib", ".class",
              ".mcpb", ".dxt", ".tar", ".gz", ".bin"}
JUNK = {".ds_store", "thumbs.db", "desktop.ini"}
DEVICE_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
RESERVED_NAMES = {"claude", "anthropic", "official", "plugin", "mcp", "test"}
NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
COMPONENT_KEYS = {"commands", "agents", "skills", "hooks", "mcpServers", "lspServers",
                  "outputStyles"}
LAUNCHERS = re.compile(r"\b(npx|bunx|pnpm dlx|yarn dlx|uvx|pipx run|uv run)\b")
PACKAGE_SOURCE_FILES = {".npmrc", "bunfig.toml", "uv.toml", "pip.conf", ".yarnrc", ".yarnrc.yml"}
SECRET_NAME = r"[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|CREDENTIAL)[A-Za-z0-9_]*"
CREDENTIAL_READS = [
    re.compile(r"os\.environ(?:\.get)?\s*[\[(]\s*f?[\"'][^\"']*(?:token|secret|password|key|"
               r"credential)", re.I),
    re.compile(r"process\.env\.\s*" + SECRET_NAME, re.I),
    re.compile(r"\$\{?" + SECRET_NAME + r"\}?"),
    re.compile(r"(?:gradle\.properties|\.netrc|\.npmrc|\.pypirc|credentials\.json|\.git-credentials"
               r"|\.aws/credentials)"),
    re.compile(r"[\"'][a-z0-9_]*(?:password|passwd|token|secret)[\"']", re.I),
]
SENDS = re.compile(r"urlopen|requests\.(?:get|post|put)|fetch\(|curl\b|wget\b|Authorization|"
                   r"http\.client")
FETCHES = re.compile(r"\b(?:curl|wget|urlretrieve|urlopen|git[\"' ,]+clone|Invoke-WebRequest)\b"
                     r"|[\"']clone[\"']")
EXECUTES = re.compile(r"\|\s*(?:ba|z)?sh\b|chmod\s*\+x|\.chmod\(\s*0o7|os\.chmod\(|\bexec\(|"
                      r"\beval\b|iex\b")


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, level: str, where: str, message: str) -> None:
        self.items.append((level, where, message))

    def print(self) -> int:
        order = {"BLOCKS": 0, "HOLD": 1, "WARN": 2, "NOTE": 3}
        for level, where, message in sorted(self.items, key=lambda item: order[item[0]]):
            print(f"{level:6} {where}: {message}")
        counts = {level: sum(1 for item in self.items if item[0] == level) for level in order}
        print(f"\n{counts['BLOCKS']} blocking, {counts['WARN']} warnings, "
              f"{counts['HOLD']} policy holds, {counts['NOTE']} notes")
        return 1 if counts["BLOCKS"] else 0


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate keys and YAML tags, as the portal does."""


def _mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    keys = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in keys:
            raise yaml.YAMLError(f"key {key!r} appears twice (line {key_node.start_mark.line + 1})")
        keys.add(key)
    return loader.construct_mapping(node, deep=deep)


def _tag(loader: StrictLoader, suffix: str, node: yaml.Node) -> None:
    raise yaml.YAMLError(f"YAML tag !{suffix} (line {node.start_mark.line + 1})")


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
StrictLoader.add_multi_constructor("!", _tag)
StrictLoader.add_multi_constructor("tag:yaml.org,2002:binary", _tag)


def plugin_files(root: Path) -> list[Path]:
    """Files git would hand the directory: tracked plus new, not ignored ones."""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                              "--", "."], cwd=root, capture_output=True, text=True, check=True)
        return sorted(root / name for name in out.stdout.split("\0")
                      if name and (root / name).exists())
    except (FileNotFoundError, subprocess.CalledProcessError):
        return sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())


def check_layout(root: Path, files: list[Path], report: Report) -> None:
    if not (root / ".claude-plugin/plugin.json").is_file():
        report.add("BLOCKS", str(root), "no .claude-plugin/plugin.json")
    for part in root.resolve().parts[-3:]:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", part):
            report.add("BLOCKS", str(root), f"folder name {part!r} stops validation")
    lowered: dict[str, Path] = {}
    for path in files:
        rel = path.relative_to(root)
        for part in rel.parts:
            stem = part.split(".")[0].lower()
            if part.lower() in JUNK or part == "__MACOSX":
                report.add("BLOCKS", str(rel), "macOS or Windows system file")
            if ":" in part or part.endswith((".", " ")) or stem in DEVICE_NAMES:
                report.add("BLOCKS", str(rel), "name not valid on Windows; validation stops")
        key = str(rel).lower()
        if key in lowered:
            report.add("BLOCKS", str(rel), f"differs only by case from {lowered[key]}")
        lowered[key] = rel
        if path.is_symlink():
            report.add("BLOCKS", str(rel), "symbolic link")
        elif path.stat().st_size < 200 and path.read_bytes().startswith(
                b"version https://git-lfs"):
            report.add("BLOCKS", str(rel), "Git LFS pointer file")
        elif path.stat().st_size > REPO_FILE_LIMIT:
            report.add("BLOCKS", str(rel), "over 5 MiB; repository too large to validate")
    for attributes in [*root.resolve().parents, root.resolve()]:
        gitattributes = attributes / ".gitattributes"
        if gitattributes.is_file() and re.search(r"export-ignore|export-subst|\bfilter=",
                                                 gitattributes.read_text()):
            report.add("BLOCKS", str(gitattributes), "export-ignore, export-subst or filter")


def check_manifest(root: Path, report: Report) -> dict:
    path = root / ".claude-plugin/plugin.json"
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        report.add("BLOCKS", "plugin.json", f"not valid JSON: {error}")
        return {}
    name = manifest.get("name", "")
    if not name.isascii():
        report.add("BLOCKS", "plugin.json name", "non-ASCII identifier")
    elif not NAME.fullmatch(name):
        report.add("WARN", "plugin.json name", "use lowercase letters, digits and hyphens, max 64")
    if name in RESERVED_NAMES:
        report.add("BLOCKS", "plugin.json name", f"{name!r} is reserved")
    for key in ("description", "version"):
        if not manifest.get(key):
            report.add("WARN", "plugin.json", f"{key} not set")
    if not (manifest.get("author") or {}).get("name"):
        report.add("WARN", "plugin.json", "author not set")
    for key, value in (("displayName", manifest.get("displayName")),
                       ("author.name", (manifest.get("author") or {}).get("name"))):
        if value and any(unicodedata.category(char) in {"Cf", "Mn"} for char in value):
            report.add("BLOCKS", f"plugin.json {key}", "invisible or combining characters")
        if value and len({unicodedata.name(c, "").split()[0] for c in value if c.isalpha()}) > 1:
            report.add("BLOCKS", f"plugin.json {key}", "mixes writing systems")
    for key, value in manifest.items():
        paths = value if isinstance(value, list) else [value]
        if key in COMPONENT_KEYS:
            for item in paths:
                if isinstance(item, str) and not (root / item).resolve().is_relative_to(
                        root.resolve()):
                    report.add("BLOCKS", f"plugin.json {key}", f"{item} points outside the plugin")
            if key == "hooks" and "hooks/hooks.json" in str(value):
                report.add("WARN", "plugin.json hooks", "hooks/hooks.json loads automatically")
    if set(manifest.get("experimental") or {}) & COMPONENT_KEYS:
        report.add("BLOCKS", "plugin.json experimental", "component keys belong at the top level")
    report.add("NOTE", "plugin.json name", "taken / look-alike / brand checks run only in the portal")
    return manifest


def png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        index = 2
        while index < len(data) - 9:
            marker, length = data[index + 1], struct.unpack(">H", data[index + 2:index + 4])[0]
            if 0xC0 <= marker <= 0xC3:
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return width, height
            index += 2 + length
    return None


def check_icon(root: Path, manifest: dict, report: Report) -> None:
    icon = root / (manifest.get("icon") or ".claude-plugin/icon.png")
    if not icon.is_file():
        report.add("WARN", "plugin.json icon", "no icon; it is taken only on the first save")
        return
    size = png_size(icon.read_bytes())
    if not size or size[0] != size[1] or not 512 <= size[0] <= 2048 \
            or icon.stat().st_size >= 2 * KIB * KIB:
        report.add("WARN", str(icon.relative_to(root)),
                   f"needs a square PNG or JPEG, 512-2048 px, under 2 MB (got {size})")


def words_outside_code(text: str) -> int:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    return len(re.findall(r"[A-Za-z0-9][\w'.-]*", text))


def check_readme_license(root: Path, manifest: dict, report: Report) -> None:
    readmes = [path for path in root.iterdir() if path.name.lower().startswith("readme")]
    if not readmes:
        # The checklist says this blocks, but the portal accepted the repository's README for
        # fb7b8f9, which had none in the plugin folder.
        repo = next((parent for parent in root.resolve().parents
                     if (parent / ".claude-plugin/marketplace.json").exists()), None)
        readmes = [path for path in (repo.iterdir() if repo else [])
                   if path.name.lower().startswith("readme")]
        if readmes:
            report.add("NOTE", "README", "none in the plugin folder; the repository's is used")
    if not readmes:
        report.add("BLOCKS", "README", "README missing")
    elif words_outside_code(readmes[0].read_text()) < 40:
        report.add("BLOCKS", readmes[0].name, "README too short (40 words outside code blocks)")
    licenses = [path for path in root.iterdir()
                if path.name.upper().startswith(("LICENSE", "LICENCE", "COPYING"))]
    if not licenses and not manifest.get("license"):
        report.add("BLOCKS", "LICENSE", "license missing")


def check_files(root: Path, files: list[Path], report: Report) -> None:
    if len(files) > FILE_LIMIT:
        report.add("HOLD", str(root), f"{len(files)} files, over {FILE_LIMIT}")
    for path in files:
        rel, ext = path.relative_to(root), path.suffix.lower()
        if ext in IMAGE_EXT | FONT_EXT:
            continue
        data = path.read_bytes()
        if ext in BINARY_EXT or b"\0" in data[:8000]:
            report.add("HOLD", str(rel), "binary file the validator can't inspect")
        elif len(data) > TEXT_LIMIT:
            report.add("HOLD", str(rel), "over 256 KiB")
        if path.name in PACKAGE_SOURCE_FILES:
            report.add("HOLD", str(rel), "package-manager source configuration")


def frontmatter(text: str) -> str | None:
    match = re.match(r"---\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", text, re.S)
    return match.group(1) if match else None


def check_components(root: Path, report: Report) -> None:
    documents = [*root.glob("skills/*/SKILL.md"), *root.glob("commands/**/*.md"),
                 *root.glob("agents/**/*.md")]
    for path in sorted(documents):
        rel = str(path.relative_to(root))
        block = frontmatter(path.read_text())
        if block is None:
            report.add("WARN", rel, "no front matter")
            continue
        try:
            data = yaml.load(block, Loader=StrictLoader) or {}
        except yaml.YAMLError as error:
            report.add("BLOCKS", rel, f"front matter couldn't be parsed: {error}".replace("\n", " "))
            continue
        if not isinstance(data, dict):
            report.add("BLOCKS", rel, "front matter is not a mapping")
        elif "description" not in data:
            report.add("WARN", rel, "no description")
        elif not isinstance(data["description"], str):
            report.add("BLOCKS", rel, "description is not text")
        elif isinstance(data.get("argument-hint"), (list, dict)):
            report.add("NOTE", rel, "argument-hint parses as a list; quote it")
    for folder in root.iterdir():
        expected = {"skills", "commands", "agents", "hooks"}
        if folder.is_dir() and folder.name.lower() in expected and folder.name not in expected:
            report.add("BLOCKS", folder.name, "component folder must be lowercase")
    for skill in root.glob("skills/*/"):
        if not (skill / "SKILL.md").exists() and any(p.name.lower() == "skill.md"
                                                     for p in skill.iterdir()):
            report.add("BLOCKS", str(skill.relative_to(root)), "name the file SKILL.md")
    check_json_components(root, report)


def check_json_components(root: Path, report: Report) -> None:
    hooks = root / "hooks/hooks.json"
    if hooks.exists():
        try:
            data = json.loads(hooks.read_text())
            if "hooks" not in data and "modules" not in data:
                report.add("BLOCKS", "hooks/hooks.json", "needs a top-level hooks object")
        except json.JSONDecodeError as error:
            report.add("BLOCKS", "hooks/hooks.json", f"hooks.json is invalid: {error}")
    mcp = root / ".mcp.json"
    if mcp.exists():
        try:
            servers = json.loads(mcp.read_text()).get("mcpServers", {})
        except json.JSONDecodeError as error:
            report.add("BLOCKS", ".mcp.json", f".mcp.json can't be parsed: {error}")
            return
        for name, server in servers.items():
            url = server.get("url")
            if url and not re.match(r"(https|wss)://|\$\{user_config\.", url):
                report.add("BLOCKS", f".mcp.json {name}", "MCP server URL is not https")
            command = " ".join([server.get("command", ""), *server.get("args", [])])
            if re.search(r"\.(mcpb|dxt)\b", command):
                report.add("HOLD", f".mcp.json {name}", "bundled MCP server not inspected")
            for header, value in (server.get("headers") or {}).items():
                if value and "${user_config." not in value:
                    report.add("BLOCKS", f".mcp.json {name}", f"secret in MCP header {header}")


def check_runtime(root: Path, files: list[Path], report: Report) -> None:
    launches = False
    for path in files:
        if path.suffix.lower() in IMAGE_EXT | FONT_EXT or path.stat().st_size > TEXT_LIMIT:
            continue
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for match in LAUNCHERS.finditer(text):
            launches = True
            rest = text[match.end():match.end() + 120].split("\n")[0]
            if match.group(1) in {"npx", "bunx", "pnpm dlx", "yarn dlx"} and not re.search(
                    r"@\d+\.\d+\.\d+\b", rest):
                report.add("BLOCKS", rel, f"unpinned {match.group(1)} launcher")
            elif match.group(1) in {"uvx", "pipx run"} and "==" not in rest:
                report.add("BLOCKS", rel, f"unpinned {match.group(1)} launcher")
            elif match.group(1) == "uv run" and not re.search(r"--(locked|frozen)", rest):
                report.add("BLOCKS", rel, "uv run without --locked or --frozen")
            else:
                report.add("HOLD", rel, "runs a pinned package")
        if path.suffix in {".md"}:
            continue
        reads = sum(1 for pattern in CREDENTIAL_READS if pattern.search(text))
        if reads and SENDS.search(text):
            report.add("HOLD", rel, f"uses a credential from the user's machine ({reads} findings)")
        if FETCHES.search(text) and EXECUTES.search(text):
            report.add("WARN", rel, "contains a download-and-run command")
    if launches and any(path.name in PACKAGE_SOURCE_FILES for path in files):
        report.add("BLOCKS", str(root), "launcher with a custom package source")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "plugins/c4ds")
    report = Report()
    files = plugin_files(root)
    check_layout(root, files, report)
    manifest = check_manifest(root, report)
    check_icon(root, manifest, report)
    check_readme_license(root, manifest, report)
    check_files(root, files, report)
    check_components(root, report)
    check_runtime(root, files, report)
    return report.print()


if __name__ == "__main__":
    sys.exit(main())
