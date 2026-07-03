---
name: dart-setup-ffi-assets
description: "Guides agents in compiling and packaging C/C++ source code into dynamic or static libraries (Code Assets) using Dart's Native Assets hook system (via hook/build.dart and hook/link.dart utilizing package:hooks and package:native_toolchain_c). Use when a user asks to: 'setup native assets', 'compile C/C++ source code', 'bundle dynamic libraries', 'build native C code', 'link native assets', 'implement build.dart or link.dart hooks', or 'integrate C/C++ interop in Dart/Flutter'. Helps agents avoid manual toolchain orchestration and configures secure hash-validated binary downloads or advanced linker tree-shaking with package:record_use mapping."
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Fri, 29 May 2026 09:10:00 GMT
---
# Compiling C Code into Code Assets with Native Assets Hooks

Integrate and automate the compilation and packaging of native C/C++ source code into **Code Assets** under Dart's overarching **Native Assets** feature using build and link hooks.

## Introduction

Under Dart's **Native Assets** feature, packages bundle native code (e.g. C/C++ libraries) as **Code Assets** automatically during standard dev cycles (`dart run`, `dart test`, `dart build`, `flutter run`). Packaging is driven by two hook scripts in `hook/`:

1.  `hook/build.dart`: Compiles local C sources to machine code or bundles prebuilt binaries for a specific host/target architecture.
2.  `hook/link.dart`: Links built code assets, applying tree-shaking to strip unused native symbols and compress binary size.

---

## Constraints

> [!IMPORTANT]
> Keep all file resolving platform-independent. Never hardcode absolute target paths, shell scripts, or system command variables. Always use `Platform.script.resolve()` or `Uri`-based resolution.

*   **Hook Locations**: Hooks must reside strictly inside `hook/` at the package root (`hook/build.dart`, `hook/link.dart` optional).
*   **Compile Toolchain Standard**: Use `package:native_toolchain_c` APIs (`CBuilder`, `CLibrary`). Never invoke raw `gcc`/`clang`/`msvc` via shell.
*   **Preamble & License Headers**: Every handcrafted/generated source file must contain the package's copyright and licensing header.
*   **Tree Shaking Mapping**: Map Dart method names to raw native C symbol names via FFIgen record-use mapping, stored under `lib/src/third_party/` with `.g.dart` extension (e.g., `sqlite3.record_use_mapping.g.dart`).
*   **Integrity Safeguards (Precompiled Libraries)**:
    *   **Cryptographic Verification**: Downloaded binaries must be checked against preconfigured MD5/SHA-256 hash lookup tables.
    *   **Graceful Recovery**: Provide offline fallbacks (e.g., local compiler execution via `local_build` flag).

---

## Native Interop Packages

Three specialized packages power Code Assets hooks:

| Dependency | Purpose | Key API Abstractions |
| :--- | :--- | :--- |
| **`package:hooks`** | Main orchestrator defining execution bounds. | `build(args, callback)`, `link(args, callback)` |
| **`package:native_toolchain_c`** | Detects local compilers (MSVC, Xcode/Clang, GCC) and runs toolchains. | `CLibrary`, `CBuilder`, `LinkerOptions.treeshake` |
| **`package:code_assets`** | Models code metadata records for dynamic loaders. | `CodeAsset`, `DynamicLoadingBundled` |

---

## Step-by-Step Workflow

### Step 1: Add Dependencies
Fetch from **pub.dev** (CLI or manual):
```bash
dart pub add code_assets hooks native_toolchain_c record_use dev:ffigen
```
```yaml
dependencies:
  code_assets: ^1.0.0
  hooks: ^0.1.0
  native_toolchain_c: ^0.1.0
  record_use: ^0.6.0
dev_dependencies:
  ffigen: ^20.1.1
```

### Step 2: Define C Specifications
Define C library compilation metadata in `lib/src/c_library.dart` (shared source of truth for build & link hooks).

### Step 3: Implement Build and Link Hooks
Write compilation orchestration in `hook/build.dart` and dead-code elimination in `hook/link.dart`.

### Step 4: Run the Hook Cycle
Standard test/run commands launch the hook lifecycle automatically:
```bash
dart test
```

---

## Choosing an Integration Approach

| Aspect | Method 1: Local Compilation & Tree-Shaking | Method 2: Precompiled Downloads |
| :--- | :--- | :--- |
| **Use Case** | C/C++ source included in package; want max size optimization. | Compiling locally is slow/complex; avoid host toolchain requirements. |
| **Host Toolchain** | Requires pre-installed C compiler (Xcode, MSVC, GCC). | Zero compiler setup on dev/user machines. |
| **Binary Optimization** | Premium — unused symbols tree-shaken. | Standard — compiled binaries shipped as-is. |
| **Offline Setup** | Fully compliant. | Requires network, with offline fallback. |

---

## Method 1: Local Compilation with Linker Tree-Shaking (Recommended)

The build hook invokes local toolchains (GCC, Clang, MSVC) to compile sources directly. The link hook filters output symbols via compiler options, retaining only methods invoked in user code. This is the standard SQLite pattern (`pkgs/code_assets/example/sqlite`).

### Prerequisite Host Compiler Toolchains
The dev machine must have a C compiler pre-installed:
- **macOS**: Xcode Command Line Tools — `xcode-select --install`
- **Linux**: GCC or Clang — `sudo apt install build-essential`
- **Windows**: MSVC — install Visual Studio with the **Desktop development with C++** workload.

*If no toolchain is discovered, the build hook throws a compilation exception. Use Method 2 if toolchains can't be guaranteed.*

### C Source and Bindings Setup
Assume C source at `third_party/sqlite/sqlite3.c` with header `third_party/sqlite/sqlite3.h`. Use FFIgen (`tool/ffigen.dart`) to generate bindings in `lib/src/third_party/sqlite3.g.dart` and the record-use mapping in `lib/src/third_party/sqlite3.record_use_mapping.g.dart`:

```dart
// AUTO-GENERATED FILE - DO NOT MODIFY. Generated via ffigen.
const recordUseMapping = {
  'sqlite3_libversion': 'sqlite3_libversion',
};
```

### Defining the C Library Build Spec
Define the centralized library spec in `lib/src/c_library.dart`:
```dart
import 'package:native_toolchain_c/native_toolchain_c.dart';

final cLibrary = CLibrary(
  name: 'sqlite3',
  assetName: 'src/third_party/sqlite3.g.dart',
  sources: ['third_party/sqlite/sqlite3.c'],
);
```

### Implementing `hook/build.dart`
Use `CLibrary.build` to compile to a dynamic library (`.so`/`.dylib`/`.dll`) in the hook's target directory:
```dart
import 'package:code_assets/code_assets.dart';
import 'package:hooks/hooks.dart';
import 'package:sqlite/src/c_library.dart';

void main(List<String> args) async {
  await build(args, (input, output) async {
    if (input.config.buildCodeAssets) {
      await cLibrary.build(
        input: input,
        output: output,
        defines: {
          if (input.config.code.targetOS == OS.windows)
            'SQLITE_API': '__declspec(dllexport)', // Export in Windows DLL
        },
      );
    }
  });
}
```

### Implementing `hook/link.dart`
Use `LinkerOptions.treeshake` to compile a minimized, dead-code-eliminated binary based on symbol usage records:
```dart
import 'package:hooks/hooks.dart';
import 'package:native_toolchain_c/native_toolchain_c.dart';
import 'package:record_use/record_use.dart';
import 'package:sqlite/src/c_library.dart';
import 'package:sqlite/src/third_party/sqlite3.record_use_mapping.g.dart';

void main(List<String> arguments) async {
  await link(arguments, (input, output) async {
    await cLibrary.link(
      input: input,
      output: output,
      linkerOptions: LinkerOptions.treeshake(
        symbolsToKeep: input.recordedUses?.calls.keys.cast<Method>().map(
          (e) => recordUseMapping[e.name]!,
        ),
      ),
    );
  });
}
```

---

## Method 2: Downloading Precompiled Dynamic Libraries

Pre-compile binaries on a central build machine, then download the target binary during the build hook. Useful when host toolchains are unavailable, compile times are long, or cross-compilation is needed (matches the `download_asset` hook package paradigm).

### Implementing Precompiled Dynamic Downloads

The build hook detects `local_build` flag; if absent, it downloads platform-specific libraries via `HttpClient`, verifies MD5 hash against a lookup table, and registers the binary as a `CodeAsset`.

#### 1. Target Hashes (`lib/src/hook_helpers/hashes.dart`)
```dart
const assetHashes = {
  'libnative_add_macos_arm64.dylib': '4a88f50438a98402db2dbd47b59eb412',
  'libnative_add_linux_x64.so': '9f5e15043aa98402dcdbbd47b59ea520',
  'native_add_windows_x64.dll': 'a881e5043ba98402acdebd47b59fa321',
};
```

#### 2. Hook Downloader Helper (`lib/src/hook_helpers/download.dart`)
```dart
import 'dart:io';
import 'package:code_assets/code_assets.dart';
import 'package:crypto/crypto.dart';

const version = '1.0.0';
Uri downloadUri(String target) => Uri.parse(
  'https://github.com/my-org/my-native-repo/releases/download/$version/$target',
);

Future<File> downloadAsset(OS targetOS, Architecture targetArch, Directory outputDir) async {
  final fileName = targetOS.dylibFileName('native_add_${targetOS.name}_${targetArch.name}');
  final client = HttpClient()..findProxy = HttpClient.findProxyFromEnvironment;
  final response = await (await client.getUrl(downloadUri(fileName))).close();
  if (response.statusCode != 200) {
    throw ArgumentError('Download ${downloadUri(fileName)} failed: Code ${response.statusCode}');
  }
  final targetFile = File.fromUri(outputDir.uri.resolve(fileName));
  await targetFile.create(recursive: true);
  await response.pipe(targetFile.openWrite());
  return targetFile;
}

Future<String> hashAsset(File file) async => md5.convert(await file.readAsBytes()).toString();
```

#### 3. `hook/build.dart` (with local fallback)
```dart
import 'dart:io';
import 'package:code_assets/code_assets.dart';
import 'package:hooks/hooks.dart';
import 'package:my_download_package/src/hook_helpers/hashes.dart';
import 'package:my_download_package/src/hook_helpers/download.dart';
import 'package:native_toolchain_c/native_toolchain_c.dart';

void main(List<String> args) async {
  await build(args, (input, output) async {
    final localBuild = input.userDefines['local_build'] as bool? ?? false;
    if (localBuild) {
      final name = 'native_add_${input.config.code.targetOS.name}_${input.config.code.targetArchitecture.name}';
      final builder = CBuilder.library(
        name: name, assetName: 'native_add.dart', sources: ['src/native_add.c'],
      );
      await builder.run(input: input, output: output);
    } else {
      final targetOS = input.config.code.targetOS;
      final targetArch = input.config.code.targetArchitecture;
      final outputDir = Directory.fromUri(input.outputDirectory);
      final file = await downloadAsset(targetOS, targetArch, outputDir);
      final fileHash = await hashAsset(file);
      final expectedFileName = targetOS.dylibFileName('native_add_${targetOS.name}_${targetArch.name}');
      final expectedHash = assetHashes[expectedFileName];

      if (fileHash != expectedHash) {
        throw Exception(
          'Security Mismatch: File $expectedFileName hash verification failed! '
          'Found hash: $fileHash, expected: $expectedHash.'
        );
      }

      output.assets.code.add(
        CodeAsset(
          package: input.packageName,
          name: 'native_add.dart',
          linkMode: DynamicLoadingBundled(),
          file: file.uri,
        ),
      );
    }
  });
}
```

---

## Verification Checklist

### 1. Local Execution Sandbox
Run unit tests; confirm native assets compile/link with no exceptions:
```bash
dart test
```

### 2. Verify Target Outputs
Verify dynamic binary assets are created in `.dart_tool/resources/` (or target directories):
- **macOS**: `.dylib` files
- **Linux**: `.so` files
- **Windows**: `.dll` files

### 3. Verify Tree-Shaking Stripping
1. Build a production bundle: `dart build cli bin/main.dart`
2. Query exported dynamic symbol tables:
   - **macOS**: `nm -gU build/cli/lib/libsqlite3.dylib`
   - **Linux**: `nm -D build/cli/lib/libsqlite3.so`
   - **Windows**: `dumpbin /EXPORTS build\cli\lib\sqlite3.dll`
3. Confirm outputs contain **only** explicitly kept entry points (e.g. `sqlite3_libversion`), not stripped symbols.
4. **No-bundle scenario**: If the app doesn't invoke any native methods, verify the link hook logs `Skipping linking as no symbols are to be kept.` and no library file is generated.

### 4. Verify Offline Compliance (User Defines)
1. Configure `local_build: true` in `pubspec.yaml`:
   ```yaml
   hooks:
     user_defines:
       <your_package_name>:
         local_build: true
   ```
2. Disable network or run in an offline sandbox.
3. Run `dart test` — verify local source compilation succeeds with no network download attempts.
