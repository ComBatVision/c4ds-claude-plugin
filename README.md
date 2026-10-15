# C4DS Claude Code plugin

A [Claude Code](https://claude.com/claude-code) plugin for building external tools (plugin APKs)
for ComBat 4 Dismounted Soldier (C4DS) in your own repository.

## Install

```bash
claude plugin marketplace add ComBatVision/c4ds-claude-plugin
claude plugin install c4ds@c4ds-claude-plugin
```

Update to the latest version:

```bash
claude plugin marketplace update c4ds-claude-plugin
```

## Skills

| Skill                 | What it does                                                                                           |
|-----------------------|--------------------------------------------------------------------------------------------------------|
| `/c4ds:setup-project` | Sets up a repo: Gradle wrapper, Nexus repository, SDK/AGP/Kotlin pins, `AGENTS.md` + `docs/`, a first tool |
| `/c4ds:new-tool`      | Adds a tool, as a new plugin APK module or into an existing module                                     |
| `/c4ds:doctor`        | Checks JDK, Android SDK, device, host app, Nexus credentials and access, and the SDK pin               |
| `/c4ds:update-sdk`    | Moves the SDK, AGP, Kotlin and Gradle versions to the latest samples, refreshes the docs                |

Type `/c4ds` in Claude Code to list them, or describe the task ("set up a C4DS tool project here")
and Claude picks the skill.

## Requirements

- JDK 17 or newer and the Android SDK (Android Studio installs both)
- Python 3.9 or newer and git
- Credentials for the C4DS Maven SDK repository, in `~/.gradle/gradle.properties` as
  `c4ds_sdk_username` and `c4ds_sdk_password`. Request them at
  [support@combat.vision](mailto:support@combat.vision).
- To run a tool: a device or emulator with
  [ComBat 4 DS](https://play.google.com/store/apps/details?id=vision.combat.c4.ds)

## How it works

[`plugins/c4ds/scripts/c4ds.py`](plugins/c4ds/scripts/c4ds.py) does the work; the skills tell
Claude when to run it and what to check afterwards.

The build setup, version pins and docs are not kept here. `setup` and `sync` copy them from the
public [samples repo](https://github.com/ComBatVision/c4ds-tool-samples) at a git ref (default
`main`), with a shallow, sparse fetch of only `docs/` and `gradle/`. A new project therefore starts
from a state that builds, and the docs have one source. The ref and commit are recorded in the
project's `.c4ds-source.json`.

Tool code comes from the templates in [`plugins/c4ds/templates`](plugins/c4ds/templates), which
follow the samples repo's `docs/architecture`.

## Development

Try local changes without installing from GitHub:

```bash
claude plugin marketplace add /path/to/c4ds-claude-plugin
claude plugin install c4ds@c4ds-claude-plugin
```

Validate before pushing:

```bash
claude plugin validate .
```

### CI

`.github/workflows/template-drift.yml` runs on pull requests, pushes to `main` and every Monday. It
validates the plugin, scaffolds a project with `setup` and two `new-tool` calls against the samples
repo `main`, builds both modules, and checks that `adopt` works on a bare Gradle project. The weekly
run catches SDK pin changes in the samples repo that break the templates.

The Gradle build needs Nexus access. The secrets are ComBatVision organization secrets (org
Settings > Secrets and variables > Actions), with this repository in their access list; the
workflow passes them to Gradle as `c4ds_sdk_username` and `c4ds_sdk_password`. A repository
secret with the same name would override them, so do not add one:

| Secret              | Value                     |
|---------------------|---------------------------|
| `C4DS_SDK_USERNAME` | Nexus `maven-sdk` user    |
| `C4DS_SDK_PASSWORD` | Password of that user     |

Without them, pull requests (including ones from forks) skip the build with a warning; pushes and
scheduled runs fail.

## License

[Apache License 2.0](LICENSE)
