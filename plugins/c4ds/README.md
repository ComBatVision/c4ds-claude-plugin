# C4DS

Build external tools (plugin APKs) for ComBat 4 Dismounted Soldier (C4DS), the Android tactical
app by ComBatVision, in your own repository. The plugin sets up a Gradle project for C4DS tool
development, scaffolds tools from templates that follow the C4DS docs, checks the development
environment, and moves a project to a newer C4DS SDK.

## Skills

| Skill                 | What it does                                                                                               |
|-----------------------|------------------------------------------------------------------------------------------------------------|
| `/c4ds:setup-project` | Sets up a repo: Gradle wrapper, Nexus repository, SDK/AGP/Kotlin pins, `AGENTS.md` + `docs/`, a first tool |
| `/c4ds:new-tool`      | Adds a tool: into the APK it ships with, or its own APK when users install it separately                   |
| `/c4ds:doctor`        | Checks JDK, Android SDK, device, host app, Nexus credentials and access, and the SDK pin                   |
| `/c4ds:update-sdk`    | Moves the SDK, AGP, Kotlin and Gradle versions to the latest samples, refreshes the docs                   |

Describe the task ("set up a C4DS tool project here") and Claude picks the skill, or type `/c4ds`
to list them.

## Requirements

- JDK 17 or newer and the Android SDK (Android Studio installs both)
- Python 3.9 or newer and git
- Credentials for the C4DS Maven SDK repository, in `~/.gradle/gradle.properties` as
  `c4ds_sdk_username` and `c4ds_sdk_password`. Request them at
  [support@combat.vision](mailto:support@combat.vision).
- To run a tool: a device or emulator with
  [ComBat 4 DS](https://play.google.com/store/apps/details?id=vision.combat.c4.ds)

## What the plugin runs and connects to

The skills run one readable Python script, `scripts/c4ds.py`, with the Python standard library
only. It installs no packages. It does the following:

- **Fetches the public samples repo.** `setup-project`, `new-tool` and `update-sdk` run `git clone`
  (shallow and sparse, `docs/` and `gradle/` only) of
  [ComBatVision/c4ds-tool-samples](https://github.com/ComBatVision/c4ds-tool-samples) from GitHub
  into a temporary folder. They copy the Gradle wrapper (`gradlew`, `gradle/wrapper`), version pins
  and docs from it into your project, and mark `gradlew` executable. Claude then runs that Gradle
  wrapper to build, which downloads Gradle, the Android Gradle plugin and the C4DS SDK.
- **Checks Nexus access.** `doctor` reads `c4ds_sdk_username` and `c4ds_sdk_password` from your
  project's `gradle.properties`, `~/.gradle/gradle.properties` or the matching
  `ORG_GRADLE_PROJECT_*` environment variables. It sends them only to the C4DS SDK repository,
  `https://nexus.combat.vision/repository/maven-sdk`, with one request that reads the latest SDK
  version. It never prints or stores them. `doctor --offline` skips the request. Gradle sends the
  same credentials to the same repository on every build.
- **Runs local tools.** `doctor` runs `java -version`, `adb devices` and `adb shell pm list
  packages` to check the JDK, the connected device and whether ComBat 4 DS is installed.
- **Writes only to your project.** Generated files go into the current repository (`setup-project`
  runs `git init` in a new one); the plugin keeps no data of its own and sends no data anywhere
  else.

## License

[Apache License 2.0](LICENSE)
