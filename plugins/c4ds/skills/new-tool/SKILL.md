---
name: new-tool
description: Scaffold a new external C4DS tool, by default as another tool in the project's existing plugin APK (a new APK only when one is required), from a fixed template that follows the C4DS docs, then build it. Use when the user asks to create, start, scaffold or add a C4DS tool, plugin or sample in an existing C4DS tool project.
argument-hint: <module> [--tool Name] [--package com.example.x] [--label "App label"] [--minimal] [--new-apk]
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py *)
---

# New C4DS tool

Generates a working tool skeleton, then adapts it to the request. The template holds the
boilerplate; the rules live in the project's `AGENTS.md` and `docs/`. Do not restate those
rules here or in generated code comments.

The project must already be set up (it has `settings.gradle.kts` and the `vision.combat.c4.ds`
plugin in `gradle/libs.versions.toml`). If it is not, use the `setup-project` skill first.

## 1. Decide the inputs

| Input       | Meaning                                                                                  |
|-------------|------------------------------------------------------------------------------------------|
| `module`    | Gradle module dir. Existing dir = add a tool to that APK (the default choice).           |
| `--tool`    | PascalCase tool name, no `Tool` suffix. Default: from the module name (`weather-radar`). |
| `--package` | Base package, needed for a new module (`com.example.weather`). Ask the user if unknown.  |
| `--label`   | App label for a new module. Default `ComBat <Tool>`.                                     |
| `--minimal` | Window + ViewModel only. Use when the tool has no persistence or SDK interactor.         |
| `--new-apk` | Allow a new module when the project already has a tool APK. Only with a reason below.    |

### One APK for all tools

Put new tools into the project's existing tool module. The host loads every plugin APK
separately (its own class loader, resources and startup work), so each extra APK makes the host
app slower to start. One APK can hold any number of tools: each is one more `<tool-descriptor>`
line in `res/xml/combat_tools.xml`.

To find the module, look for `src/main/res/xml/combat_tools.xml` under the project's modules. If
there are several, pick the one whose tools are closest to the new one.

Create a new module only when the tool cannot share the APK, and say which reason applies:

- native libraries (`.so`) that conflict with ones already in the APK
- manifest entries or permissions that must not apply to the other tools
- a different release cycle or owner, so the APK must ship on its own
- a dependency the host does not provide that is too large to add to every user of the APK

Without one of these, keep the tool in the existing APK even when the user names a new module;
explain why and ask before using `--new-apk`. The script refuses a second tool module without
that flag.

In the `c4ds-tool-samples` repo itself: one-feature samples go into `gallery`, and new modules
use the package `vision.combat.c4.ds.sample.<module>`.

## 2. Run the scaffold

From the project root:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py new-tool <module> [--tool Name] [--package pkg] [--label "App label"] [--minimal]
```

Run the script as a command of its own, not chained with other commands: the plugin's
permission rule allows only the script.

It refuses to overwrite files. For a new module it adds `include(":<module>")` to
`settings.gradle.kts`.

Output, under `<module>/src/main/kotlin/<package>/`:

- `<Tool>ToolDescriptor.kt`, `<Tool>Tool.kt`: identity and component wiring
- `ui/<Tool>Window.kt`, `ui/<Tool>ViewModel.kt`: MVI counter screen
- without `--minimal`: `di/`, `domain/`, `domain/repository/`, `data/`, an interactor and a
  repository over plugin-isolated `SharedPreferences`
- `res/drawable/ic_<tool>.xml` (placeholder icon), strings, and a `<tool-descriptor>` line in
  `res/xml/combat_tools.xml`

A tool added to an existing module goes into a subpackage named after the tool.

## 3. Build before changing anything

```bash
./gradlew :<module>:assembleDebug
```

A green build proves the skeleton; later failures come from your changes. If the build cannot
resolve the SDK, run the `doctor` skill.

## 4. Turn the counter into the real tool

Read only the docs the change needs; the "Where to look" table in `AGENTS.md` maps tasks to
docs:

- Other screen regions (`mapWindow`, `overlay`, `status`, `underlay`), `AbstractMapTool`,
  services: `docs/reference/tool-lifecycle-and-setup.md`
- More screens, navigation: `docs/architecture/ui-layer-conventions.md`
- Room, files, network: `docs/architecture/data-and-domain.md`
- Assets, native libs: `docs/reference/resource-and-isolation.md`
- Whether the host already provides a library: `docs/reference/host-provided-libraries.md`

For working examples of a feature, read the matching sample in
https://github.com/ComBatVision/c4ds-tool-samples (`gallery/`) rather than inventing a new
pattern. Replace the placeholder icon and strings.

## 5. Finish

- `./gradlew :<module>:assembleDebug` again.
- Check the change against `docs/review-rules.md`.
- To try it, install the APK on a device that has ComBat 4 DS
  (`adb install -r <module>/build/outputs/apk/debug/<module>-debug.apk`), then open the tool
  from the host's Tools list. Do this only when the user asks.
