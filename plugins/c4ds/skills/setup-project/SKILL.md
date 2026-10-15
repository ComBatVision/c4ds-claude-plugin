---
name: setup-project
description: Set up a repository for developing ComBat 4 DS (C4DS) external tools - Gradle wrapper, Nexus SDK repository, version pins, AGENTS.md and docs for agents - then scaffold the first tool and build it. Use when the user wants to start C4DS plugin or tool development in a new or empty repo, add C4DS tool development to an existing Gradle project or Android app, or asks how to set up the C4DS development environment.
argument-hint: [--module name --package com.example.x] [--tool Name] [--label "App label"] [--minimal]
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py *)
---

# Set up a C4DS tool project

The build setup, version pins and docs are copied from the public samples repo
(https://github.com/ComBatVision/c4ds-tool-samples) at one git ref, so the new project starts
from a state that is known to build. The ref and commit are recorded in `.c4ds-source.json`;
the `update-sdk` skill uses it later.

## 1. Check the machine

Run the `doctor` checks first:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py doctor
```

Fix failures before setup. The usual ones:

- **Nexus credentials missing.** The developer requests them at support@combat.vision, then
  adds them to `~/.gradle/gradle.properties`:

  ```properties
  c4ds_sdk_username=<username>
  c4ds_sdk_password=<password>
  ```

  Never ask for the values, never write them yourself, and never put them in the project.
- **JDK** older than 17, or **Android SDK** not found: point the developer to Android Studio,
  which installs both.

A missing device or host app is only a warning: it matters for running the tool, not building.

## 2. Decide the inputs

- **Directory:** the current repo root, unless the user names another one. It must not have
  a Gradle settings file yet; for that case see "Existing project" below.
- **First tool:** module name and base package (`com.example.weather`). The module is the
  project's plugin APK and later tools join it, so name it after the product, not the first
  tool (`weather` holds Weather, Radar, ...). Ask for the package
  if the user did not give one; it becomes the APK's `applicationId`.
- **Ref:** `main` by default. Pass `--ref <branch-or-tag>` only when the user needs an older
  SDK line.

## 3. Run setup

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py setup --module <module> --package <package> [--tool Name] [--label "App label"] [--minimal]
```

Run the script as a command of its own, not chained with other commands: the plugin's
permission rule allows only the script.

Options: `--dir <path>` (default: current directory), `--name <rootProject.name>` (default:
directory name). It creates:

| Path                                        | From                                          |
|---------------------------------------------|-----------------------------------------------|
| `gradlew`, `gradlew.bat`, `gradle/wrapper/` | samples repo                                  |
| `gradle/libs.versions.toml`                 | samples repo (SDK, AGP, Kotlin pins)          |
| `settings.gradle.kts`                       | samples repo, renamed, sample modules removed |
| `build.gradle.kts`, `gradle.properties`     | samples repo                                  |
| `.gitignore`                                | samples repo                                  |
| `AGENTS.md`, `CLAUDE.md`, `docs/`           | samples repo (agent guidance)                 |
| `local.properties`                          | `sdk.dir`, when the Android SDK is found      |
| `.c4ds-source.json`                         | ref + commit the files came from              |
| `<module>/`                                 | the `new-tool` template                       |

It runs `git init` when the directory is not a repository yet.

## 4. Build

```bash
./gradlew :<module>:assembleDebug
```

The first build downloads Gradle, the SDK and the conventions plugin, so it takes a few
minutes. A Nexus 401 here means wrong credentials; run `doctor`.

## 5. Hand over

Tell the developer:

- `AGENTS.md` and `docs/` are the rules for this project; agents read them first.
- `/c4ds:new-tool` adds tools, `/c4ds:doctor` checks the environment, `/c4ds:update-sdk`
  moves to a newer SDK and refreshes the docs.
- Further tools go into the same module, so the project stays one APK: every extra plugin APK
  makes the host app slower to start.
- Nothing is committed. Suggest a first commit of the generated files; `local.properties` is
  ignored.

## Existing project

When the repo already has a Gradle build, `setup` refuses. Use `adopt` from the project root:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/c4ds.py adopt
```

It adds what is missing and leaves the rest alone:

- `gradlew`, `gradlew.bat`, `gradle/wrapper/`: copied when missing.
- `gradle.properties`, `.gitignore`: lines the project lacks are appended.
- `gradle/libs.versions.toml`: copied when missing; otherwise the `combat-ds-sdk`, `agp` and
  `kotlin` versions are set and the `android-application` and `combat-plugin` aliases that the
  `new-tool` template uses are added.
- `build.gradle.kts`: copied when missing.
- `AGENTS.md`, `CLAUDE.md`, `docs/`: copied. Existing `AGENTS.md` and `CLAUDE.md` are
  overwritten; restore project-specific content from `git diff`.

Files it cannot merge safely are listed at the end, with the samples version saved in
`.c4ds-reference/`. Usually that is `settings.gradle.kts` (the `pluginManagement` repositories:
google, mavenCentral, gradlePluginPortal and the Nexus `maven-sdk` repository with its
credentials properties) and the root `build.gradle.kts` (the `maven-sdk` repository for
subprojects). Merge those by hand, delete `.c4ds-reference/`, then run doctor and continue with
the `new-tool` skill.

## Existing Android app

When the repo is an Android app that should also offer a tool in ComBat 4 DS, do not make the
app's own APK the plugin. Add a companion plugin module next to it:

```
<app>/          the existing application: launcher Activity, its own libraries (unchanged)
<app>-shared/   optional Android library: models, API client, IPC contract with the app
<app>-c4ds/     the plugin APK: the vision.combat.c4.ds plugin and the tools
```

Why, in short for the user:

- The host loads tool code into its own process. It cannot read the app's private files or
  database either way, so tools talk to the app through IPC (a `ContentProvider` or a bound
  service) or through the C4DS model; one APK gains nothing.
- The SDK Gradle plugin removes the libraries the host ships from the plugin APK, which a
  standalone app needs, and the host loads its own copy of any class name the APK shares with it.
  Inside one APK the app's library versions would have to follow the host's.
- A thin plugin APK is much smaller for the host to load than the whole app.

Steps:

1. Run `adopt` from the project root (see "Existing project"). It keeps the app's AGP version and
   reuses the app's AGP plugin alias, since one build applies one AGP. When that AGP is older than
   the samples' version, tell the user: the host is built with the samples' AGP.
2. **Kotlin is shared by the whole build.** A tool must compile with the host's Kotlin version
   (`kotlin` in the catalog), so the app compiles with it too. `adopt` adds a `kotlin-android`
   plugin alias and lists the root `build.gradle.kts` line to add
   (`alias(libs.plugins.kotlin.android) apply false`). Without it AGP's built-in Kotlin compiles the
   tool and the build fails with `Class 'kotlin.Unit' was compiled with an incompatible version of
   Kotlin`. Tell the user the app moves to that Kotlin version. If the app cannot, put the plugin
   in a separate Gradle build in the same repo instead (run `setup --dir c4ds` there) and share
   code through a published or included library.
3. Review the `gradle.properties` lines `adopt` appended: they apply to the app too. Remove any
   that change the app's build.
4. Create the plugin module with the `new-tool` skill: module `<app>-c4ds`, package
   `<app applicationId>.c4ds`. `new-tool` refuses the app module itself.
5. Move code both APKs need into a library module, which the plugin depends on with
   `implementation`. Keep SDK types out of it: the app does not ship the SDK.
6. Build both: `./gradlew :<app>:assembleDebug :<app>-c4ds:assembleDebug`. Users install both
   APKs; the host loads only the plugin.

