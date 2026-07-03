# Flutter Build Errors

`flutter build` / `flutter run` failures across dependency, Gradle (Android), Xcode (iOS), and CocoaPods layers.

## Dependency resolution

### Error: Incompatible version constraints on 'package'

```
Because app depends on foo ^1.0.0 which doesn't match any versions, version solving failed.
```

Cause: pubspec constraints are unsatisfiable across the dependency graph.

Fix:

- Run `flutter pub outdated` to see available versions.
- Loosen or align the version constraint in `pubspec.yaml`.
- Run `flutter pub upgrade --major-versions` to try resolving with latest majors.
- If a transitive dep conflicts, add an override:

```yaml
dependency_overrides:
  foo: ^2.0.0
```

> `dependency_overrides` is a last resort; it can mask real incompatibilities. Remove once the upstream fix lands.

### Error: Get dependencies failed

Cause: no `pubspec.yaml` in cwd, or network / pub mirror unreachable.

Fix:

- Run from the project root.
- Set `PUB_HOSTED_URL` / `FLUTTER_STORAGE_BASE_URL` for mirrors if behind a firewall.
- Run `flutter clean && flutter pub get`.

## Gradle (Android) errors

### Error: Minimum supported Gradle version is X. The current version is Y

Cause: project's Gradle wrapper is older than the Flutter / Android Gradle Plugin requires.

Fix:

- Update `android/gradle/wrapper/gradle-wrapper.properties` `distributionUrl` to the required Gradle version.
- Run `flutter clean` then rebuild.

### Error: SDK location not found. Define location with an ANDROID_HOME environment variable

Cause: Android SDK not detected.

Fix: set `ANDROID_HOME` to the SDK root, or run through Android Studio's Flutter plugin which sets it automatically.

### Error: Manifest merger failed: uses-sdk:minSdkVersion X cannot be smaller than Y

Cause: a dependency requires a higher `minSdkVersion` than the app declares.

Fix: raise `minSdkVersion` in `android/app/build.gradle`:

```gradle
android {
  defaultConfig {
    minSdkVersion 21  // or higher
  }
}
```

### Error: Could not resolve all files for configuration ':classpath'

Cause: Gradle cannot fetch Android Gradle Plugin or Kotlin plugin from repositories.

Fix:

- Check `android/build.gradle` `buildscript.repositories` includes `google()` and `mavenCentral()`.
- Retry with a clean cache: `rm -rf ~/.gradle/caches && flutter clean`.

### Error: Execution failed for task ':app:mergeDebugResources'

Cause: a resource conflict (duplicate names, malformed XML) in `android/app/src/main/res`.

Fix: search for the duplicate resource name; rename or remove. Read the full Gradle log for the offending file path.

## Xcode (iOS) errors

### Error: CocoaPods not installed or not in PATH

Fix: `sudo gem install cocoapods` or `brew install cocoapods`; ensure `pod --version` works.

### Error: Xcode build is slow / hangs on CocoaPods

Fix:

```bash
cd ios
pod repo update
pod install
cd ..
flutter clean
```

### Error: No profiles for 'com.example.app' were found

Cause: signing not configured for the bundle id.

Fix: open `ios/Runner.xcworkspace` in Xcode → Signing & Capabilities → select a team → set a unique bundle id. Do NOT commit personal signing data.

### Error: Module 'foo' not found

Cause: a Pod dependency missing from `Podfile` or not installed.

Fix: ensure the package is in `pubspec.yaml`, run `flutter pub get`, then `cd ios && pod install`.

### Error: The iOS deployment target is set below 11

Cause: a plugin requires iOS 11+ but `IPHONEOS_DEPLOYMENT_TARGET` is lower.

Fix: in `ios/Podfile`, set `platform :ios, '12.0'` (or higher per plugin requirements), then `pod install`.

## Web / Desktop errors

### Error: Target of URI doesn't exist: 'package:flutter/material.dart'

Cause: web / desktop not enabled, or running outside a Flutter project.

Fix: `flutter create .` to fill in missing platform folders; `flutter config --enable-web` / `--enable-macos-desktop` etc.

## General diagnostic flow

1. Read the FULL build log from the top — the first error usually causes cascading failures.
2. Identify the layer: pub / Gradle / Xcode / CocoaPods / Dart compile.
3. Run `flutter doctor -v` to confirm toolchain versions.
4. Try `flutter clean && flutter pub get` before deeper fixes — clears stale caches.
5. For platform-specific failures, build the platform project directly (`open ios/Runner.xcworkspace` / `cd android && ./gradlew build`) to get native logs.

> Never silence a build error by deleting code without understanding the cause. Native build errors usually point to a real configuration or version mismatch.
