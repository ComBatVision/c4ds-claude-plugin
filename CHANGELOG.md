# Changelog

Versions of the `c4ds` plugin. Every change under `plugins/` raises the version in
`plugins/c4ds/.claude-plugin/plugin.json` and adds an entry here; users only get an update when
the version goes up. Versions follow [semver](https://semver.org): patch for fixes and wording,
minor for new behavior, major for removed or renamed commands, flags or skills.

The plugin version is independent of the C4DS SDK version: the plugin takes the SDK version from
the samples repo when it runs. An entry says so when a release needs a newer SDK.

## 0.2.0

- `new-tool` groups tools into APKs by distribution: tools that ship together share one APK,
  since every APK slows the host's start-up; a tool users install on its own gets its own APK.
  The script refuses a second tool module unless `--new-apk` is passed.
- Existing Android apps get a companion plugin module instead of becoming the plugin. `new-tool`
  refuses app and library modules; `adopt` keeps the project's AGP and Kotlin versions, reuses
  the app's AGP alias and asks for the host's Kotlin plugin at the root.
- `setup-project` asks to name the first module after the product.

## 0.1.0

First release, from the samples repo plus fixes from the acceptance test.

- Skills `setup-project`, `new-tool`, `doctor` and `update-sdk`, driven by
  `plugins/c4ds/scripts/c4ds.py`.
- `adopt` for existing Gradle projects; `sync --pins` skips the Gradle version when there is no
  wrapper; links to folders use `tree/` URLs; `doctor` checks the JDK from `JAVA_HOME` first.
