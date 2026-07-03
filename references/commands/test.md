# test 子命令 —— Flutter 测试与验证

经 `flutter test` 运行单元 / widget 测试，经 `flutter run` + 集成测试 (`integration_test`) 做端到端验证。**测试通过是必要条件但非充分条件**——测试太弱时必须指出。

> 🔴 **CHECKPOINT**：本子命令**不**自动安装 Flutter SDK。agent 检测到 `flutter` 不可用时仅提示用户安装，不代为执行。

## 三动作总览

| 动作 | 命令 | 用途 |
| ---- | ---- | ---- |
| `analyze` | `flutter analyze [lib/]` | Dart 静态分析（语法 / 类型 / lint） |
| `test` | `flutter test [test/] [--name pattern]` | 运行单元 / widget 测试 |
| `integration` | `flutter test integration_test/` | 运行 integration_test 端到端测试 |

## 测试类型

| 类型 | 目录 | 依赖 | 用途 |
| ---- | ---- | ---- | ---- |
| 单元测试 | `test/` | `package:test` | 纯 Dart 逻辑（无 widget） |
| Widget 测试 | `test/` | `package:flutter_test` | 单 widget 渲染 / 交互 |
| 集成测试 | `integration_test/` | `package:integration_test` | 跨页面 / 真机 / 模拟器端到端 |

## 执行流程

### Step 1：确认环境

```bash
flutter --version
```

`flutter` 不在 PATH → 立即停止，告知用户安装 Flutter SDK。

### Step 2：运行 flutter analyze

```bash
flutter analyze
```

- 退出码 0 = 无问题；非零 = 有问题。
- **`flutter analyze` 报错 → 停止流程**，不继续 `flutter test`。提示用户调 `fix` 子命令的 **analyzer 轨道** 修复后重跑。
- `flutter analyze` 通过 → 进入测试。

### Step 3：运行单元 / widget 测试

```bash
flutter test
```

或限定范围：

```bash
flutter test test/widget_test.dart
flutter test --name "renders login"
```

- 全量测试：`flutter test`（默认扫 `test/` 目录）。
- 单文件：`flutter test test/foo_test.dart`。
- 按名过滤：`flutter test --name "pattern"`。

**测试失败处理**：

- 测试失败 → 读失败原因，定位是测试断言错还是被测代码错。
- 被测代码错 → 调 `fix` 子命令（按症状路由到 analyzer / runtime / layout 轨道）。
- 测试本身错（断言写错、mock 失效）→ 修测试，**不** 删测试或弱化断言。
- 修后重跑 `flutter test` 直至全绿。

### Step 4：集成测试（可选）

仅当用户需要端到端验证，或工程已有 `integration_test/` 目录时执行。

```bash
flutter test integration_test/
```

或在设备上运行：

```bash
flutter run integration_test/app_test.dart -d <device-id>
```

**依赖**：

- `pubspec.yaml` 的 `dev_dependencies` 必须含 `integration_test: sdk: flutter`。
- `integration_test/` 目录下的测试文件 import `package:integration_test/integration_test.dart`。

**多设备选择**：

- `flutter devices` 列出可用设备。
- 多台设备 → 经 `AskUserQuestion` 让用户选，**禁止** 在用户选定前运行。
- 0 台设备 → 报告无法运行集成测试，请求用户连接设备或启动模拟器。

### Step 5：测试质量检查

测试通过后，agent **MUST** 检查测试质量（Rule 9）：

- 测试是否验证有意义的属性（值、结构、副作用、错误类型），而非仅"函数有返回值"或"不报错"。
- 断言是否足够强（如 `expect(result, expected)` 而非 `expect(result, isNotNull)`）。
- 是否覆盖边界情况（空输入、null、越界、错误路径）。
- 测试太弱时**必须明确指出**，并建议补强断言或加边界用例。

### Step 6：向用户回报

回报内容：

- `flutter analyze` 状态（通过 / 失败原因）
- `flutter test` 状态（通过数 / 失败数 / 跳过数）
- 集成测试状态（如运行）
- 测试质量评估（强 / 弱 / 需补强）
- 修复动作（如有，调用了哪个 `fix` 轨道）

## 测试编写规范

### 单元测试

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

### Widget 测试

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

关键规则：

- `pumpWidget` 包 `MaterialApp` / `Scaffold` 提供 ancestor。
- `pump()` 触发一帧；`pumpAndSettle()` 等待动画完成。
- `find.byType` / `find.byKey` / `find.text` 定位 widget。
- 交互用 `tester.tap` / `tester.enterText`，之后 `await tester.pump()`。

### 集成测试

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

## 边界情形

| 情形 | 处理 |
| ---- | ---- |
| `flutter` 不可用 | 提示用户安装 Flutter SDK，agent 不代装 |
| `flutter analyze` 报错 | 停止流程，调 `fix` analyzer 轨道 |
| `flutter test` 失败 | 区分测试错 / 代码错；代码错调 `fix`，测试错修测试 |
| 多设备连接 | `flutter devices` 列出；经 `AskUserQuestion` 让用户选 |
| 0 台设备 | 报告无法运行集成测试；建议启动模拟器 |
| `integration_test/` 缺失 | 跳过集成测试；提示用户如需端到端可创建 |
| 测试太弱 | 明确指出弱项；建议补强断言或边界用例 |

## 交付核对清单

- [ ] `flutter analyze` 通过；未通过则已转 `fix` 修复并停止 test
- [ ] `flutter test` 全绿；未通过则已定位原因（代码错转 `fix`，测试错修测试）
- [ ] 集成测试（如运行）通过；多设备场景下经 `AskUserQuestion` 让用户选
- [ ] 测试质量已评估；弱测试已明确指出并建议补强
- [ ] 回报包含 analyze 状态 / test 通过数 / 集成测试状态 / 质量评估
