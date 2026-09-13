# test subcommand — Flutter testing and verification

Runs unit / widget tests via `flutter test`, performs end-to-end verification via `flutter run` + integration tests (`integration_test`). **Test passing is a necessary but not sufficient condition** — weak tests must be identified.

> **确定性检查优先走 scripts/**：环境检测与测试执行优先用 `scripts.test.cli`（cwd=skill 根目录），本节的裸 `flutter test` 步骤是手动兜底。

## Three actions overview

`scripts.test.cli` 真实子动作（对齐 `python3 -m scripts.test.cli --help`）：

| Action | Script command | Purpose |
| ---- | ---- | ---- |
| `check` | `python3 -m scripts.test.cli check` | 检测 Flutter SDK / Dart SDK / 平台 |
| `config` | `python3 -m scripts.test.cli config --project-path <dir> [--coverage] [--integration-test-dir <dir>]` | 生成 flutter test 测试配置 JSON |
| `run`（unit/widget） | `python3 -m scripts.test.cli run --project-path <dir>` | Run unit / widget tests |
| `run`（integration） | `python3 -m scripts.test.cli run --project-path <dir> --integration` | Run integration_test end-to-end tests |
| `run`（单文件） | `python3 -m scripts.test.cli run --project-path <dir> --test-file test/foo_test.dart` | 指定单个测试文件 |
| `run`（覆盖率） | `python3 -m scripts.test.cli run --project-path <dir> --coverage` | 启用 --coverage |

`run` 另支持 `--extra-args`（透传 flutter test 参数，如 `--name MyTest`）与 `--dry-run`（仅输出计划 JSON 不执行）。

> 🔴 **CHECKPOINT**: This subcommand **does not** automatically install the Flutter SDK. When the agent detects `flutter` is unavailable, it only prompts the user to install it, never installs on their behalf.

## Test types

| Type | Directory | Dependency | Purpose |
| ---- | ---- | ---- | ---- |
| Unit test | `test/` | `package:test` | Pure Dart logic (no widgets) |
| Widget test | `test/` | `package:flutter_test` | Single widget rendering / interaction |
| Integration test | `integration_test/` | `package:integration_test` | Cross-page / real device / emulator end-to-end |

## Execution flow

### Step 1: Confirm environment

```bash
flutter --version
```

`flutter` not in PATH → stop immediately, inform user to install Flutter SDK.

### Step 2: Run flutter analyze

```bash
flutter analyze
```

- Exit code 0 = no issues; non-zero = issues exist.
- **`flutter analyze` reports errors → stop the flow**, do not continue to `flutter test`. Prompt user to use the **analyzer track** of the `fix` subcommand to fix, then re-run.
- `flutter analyze` passes → proceed to testing.

### Step 3: Run unit / widget tests

```bash
flutter test
```

Or narrow the scope:

```bash
flutter test test/widget_test.dart
flutter test --name "renders login"
```

- Full test suite: `flutter test` (scans `test/` directory by default).
- Single file: `flutter test test/foo_test.dart`.
- Filter by name: `flutter test --name "pattern"`.

**Test failure handling**:

- Test fails → read the failure reason, determine whether it is a test assertion error or code-under-test error.
- Code-under-test error → call `fix` subcommand (route by symptom to analyzer / runtime / layout track).
- Test itself is wrong (incorrect assertion, broken mock) → fix the test, **do not** delete the test or weaken the assertion.
- After fixing, re-run `flutter test` until all green.

### Step 4: Integration tests (optional)

Only execute when user needs end-to-end verification, or the project already has an `integration_test/` directory.

```bash
flutter test integration_test/
```

Or run on device:

```bash
flutter run integration_test/app_test.dart -d <device-id>
```

**Dependencies**:

- `pubspec.yaml`'s `dev_dependencies` must include `integration_test: sdk: flutter`.
- Test files under `integration_test/` import `package:integration_test/integration_test.dart`.

**Multi-device selection**:

- `flutter devices` lists available devices.
- Multiple devices → use `AskUserQuestion` to let user select; **do not** run before user selects.
- 0 devices → report inability to run integration tests, request user to connect a device or start an emulator.

### Step 5: Test quality check

After tests pass, the agent **MUST** check test quality (Rule 9):

- Do tests verify meaningful properties (values, structures, side effects, error types), or only check "function has a return value" or "does not throw"?
- Are assertions strong enough (e.g., `expect(result, expected)` rather than `expect(result, isNotNull)`)?
- Are edge cases covered (empty input, null, out-of-bounds, error paths)?
- When tests are too weak, **must explicitly identify** and suggest strengthening assertions or adding edge case tests.

### Step 6: Report to user

Report contents:

- `flutter analyze` status (pass / failure reason)
- `flutter test` status (passed count / failed count / skipped count)
- Integration test status (if run)
- Test quality assessment (strong / weak / needs strengthening)
- Fix actions taken (if any, which `fix` track was called)

## Test writing conventions

### Unit tests

```dart
import 'package:test/test.dart';
import 'package:my_app/calc.dart';

void main() {
  group('Calculator', () {
    test('adds two numbers', () {
      expect(add(1, 2), 3);
    });
    test('handles negative', () {
      expect(add(-1, -2), -3);
    });
  });
}
```

### Widget tests

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/login_form.dart';

void main() {
  testWidgets('shows error when empty', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginForm()));
    await tester.tap(find.text('Submit'));
    await tester.pump();
    expect(find.text('Required'), findsOneWidget);
  });
}
```

Key rules:

- Wrap `pumpWidget` with `MaterialApp` / `Scaffold` to provide ancestors.
- `pump()` triggers one frame; `pumpAndSettle()` waits for animations to complete.
- `find.byType` / `find.byKey` / `find.text` to locate widgets.
- Use `tester.tap` / `tester.enterText` for interactions, followed by `await tester.pump()`.

### Integration tests

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:my_app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('login flow', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('username')), 'alice');
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome'), findsOneWidget);
  });
}
```

## Edge cases

| Scenario | Handling |
| ---- | ---- |
| `flutter` unavailable | Prompt user to install Flutter SDK; agent does not install |
| `flutter analyze` reports errors | Stop the flow, call `fix` analyzer track |
| `flutter test` fails | Distinguish test error / code error; code error calls `fix`, test error fixes the test |
| Multiple devices connected | `flutter devices` lists them; use `AskUserQuestion` to let user select |
| 0 devices | Report inability to run integration tests; suggest starting an emulator |
| `integration_test/` missing | Skip integration tests; inform user they can create one if end-to-end is needed |
| Tests too weak | Explicitly identify weaknesses; suggest strengthening assertions or adding edge case tests |

## Delivery checklist

- [ ] `flutter analyze` passes; if not, has been routed to `fix` for repair and test stopped
- [ ] `flutter test` all green; if not, root cause identified (code error → `fix`, test error → fix test)
- [ ] Integration tests (if run) pass; multi-device scenario uses `AskUserQuestion` for user selection
- [ ] Test quality assessed; weak tests explicitly identified with suggestions for improvement
- [ ] Report includes analyze status / test pass count / integration test status / quality assessment
