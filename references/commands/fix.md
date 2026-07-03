# fix 子命令 —— 错误修复（症状路由 + 三轨道）

按用户症状路由到三条修复轨道之一：analyzer 错误（analyzer-errors）/ 运行时崩溃（runtime-errors）/ 布局问题（layout-errors）。**先按症状路由表选轨道，再进入轨道执行**。

> 🔴 **CHECKPOINT**：症状歧义时按 **analyzer → runtime → layout** 顺序 fallback。禁止凭模型直觉挑轨道。

## 症状路由表

| 用户症状 | 路由轨道 | 入口 |
| ---- | ---- | ---- |
| 有 `flutter analyze` / 编译失败日志或类型错误，**无** 运行时崩溃 | analyzer | [`references/error-fixes/analyzer-errors.md`](../error-fixes/analyzer-errors.md) |
| 有运行时崩溃栈 / 异常 / 闪退，**或** build 成功但运行即崩 | runtime | [`references/error-fixes/runtime-errors.md`](../error-fixes/runtime-errors.md) + [`null-safety-errors.md`](../error-fixes/null-safety-errors.md) |
| 有 RenderFlex overflow / 黄黑条纹 / 布局断言 / missing ancestor | layout | [`references/error-fixes/layout-errors.md`](../error-fixes/layout-errors.md) |
| 纯语法咨询 / TS→Dart 差异 / "某语法是否允许" | grammar | [`references/grammar/`](../grammar/) |
| `flutter build` 失败（Gradle / Xcode / CocoaPods / pub） | build | [`references/error-fixes/build-errors.md`](../error-fixes/build-errors.md) |
| 症状不明 | fallback：analyzer → runtime → layout | 见下文"症状歧义处理" |

### 症状歧义处理

按 `analyzer → runtime → layout` 顺序尝试：编译 / 类型错误信号（`error:`、`A value of type 'X'`、`The method 'foo' isn't defined`）→ analyzer；运行时崩溃信号（`NoSuchMethodError`、`TypeError`、`LateInitializationError`、闪退、build 成功后崩溃）→ runtime；布局断言信号（`RenderFlex overflowed`、`No Material widget found`、黄黑条纹）→ layout；仍不明确 → 经 `AskUserQuestion` 让用户提供更明确症状，不强行猜测。

---

## 轨道一：analyzer（编译 / 类型错误）

适用：`flutter analyze` 报错、类型不匹配、编译失败。**无** 运行时崩溃证据。

### 执行流程

1. 收集 analyzer 错误原文（来自用户或 `flutter analyze` 输出）。
2. 提取错误关键词（错误消息中的类型名、API 名、错误码），对照 [`analyzer-errors.md`](../error-fixes/analyzer-errors.md) 定位类别。
3. 按"Fix"方向做最小修改，**不重构无关代码**。
4. 修改后跑 `flutter analyze` 验证；仍报错回到步骤 2 重新定位。
5. `flutter analyze` 通过后，若有运行时嫌疑，建议跑 `flutter run` 或 `flutter test` 验证。

### 边界情形

| 情形 | 处理 |
| ---- | ---- |
| 错误不在 analyzer-errors.md 覆盖范围内 | 调 `search` 子命令在线查官方文档；找不到则 fallback 到 grammar 轨道审查语法 |
| 错误同时涉及多个类别 | 逐类修复，先修最先报的错；每次修后重新跑 `flutter analyze` |
| 涉及陌生 `package:` API | 调 `search` 查 API 约束，**不** 凭模型记忆瞎改 |

---

## 轨道二：runtime（运行时崩溃 / 异常）

适用：运行时异常、闪退、build 成功但运行即崩。

> 🔴 **核心约束**：在拿到具体崩溃锚点前，**禁止**对工程做大规模 `Read` / `Glob` / `Explore`。锚点包括异常类型 / 异常消息 / 文件名 / 栈顶帧或用户明确指出的崩溃页面 / 模块。

### 收集崩溃证据

**Case A：用户已提供原始异常文本**

直接解析异常类型 + 消息 + 栈顶帧，定位到具体文件 / 行。

**Case B：用户提供日志文件路径**

读日志，提取首个应用栈帧（`.dart` 文件路径 + 行号）作为起点。

**Case C：用户仅描述症状，无日志**

- 请求用户复现并采集日志：`flutter run` 时控制台输出，或 `flutter logs` 抓取设备日志。
- 多设备连接时经 `AskUserQuestion` 让用户选设备。
- 0 台设备 → 报告无法采集设备证据，请求用户提供本地崩溃日志。

### 常见运行时错误特征

| 异常类型 | 典型原因 | 一线修复方向 |
| ---- | ---- | ---- |
| `NoSuchMethodError` | 调用 null / dynamic 上的不存在方法 | null 守卫、typed model、修 API 调用 |
| `TypeError` (`type 'X' is not a subtype`) | `as` 转型失败、`List<dynamic>` 当 `List<T>` | 用 `is` 检查、元素级 cast、改 typed model |
| `LateInitializationError` | `late` 字段在赋值前被读 | 改 `T?` + null 检查，或确保 `initState` 先赋值 |
| `Null check operator used on a null value` | `!` 用在 null 上 | 改 `??` 默认值或显式 null 检查 |
| `StackOverflowError` | 无界递归 / build 调 build | 加递归 base case、断重建循环 |
| `StateError` | 生命周期错位（Completer 重复 complete 等） | 加状态守卫、移到正确生命周期 |
| `RangeError` | 数组越界 / 范围非法 | 加边界检查、用 `elementAtOrNull` |

### 解释规则

- 优先看应用栈帧（`.dart` 文件），过滤框架噪声；第一个具体 `.dart` 路径作为起点，**不** 作为最终结论。
- 用户给了复现步骤 → 信任用户步骤胜于纯栈猜；栈指向非入口页 → 假定交互触发。
- **不** 大范围重构；先修崩溃路径。

### 约束

- **禁止** 仅凭 prompt 推理就声称修好了崩溃。
- **禁止** 用 try/catch 吞错替代根因修复。
- 涉及陌生 `package:` API → 先查约束再改。
- 本子命令**不** 决定最终编译 / 运行 / 验证次序，那是 `test` 子命令的事。

---

## 轨道三：layout（布局问题）

适用：RenderFlex overflow、unbounded constraints、missing ancestor、setState during build 等布局断言。

### 执行流程

1. 读断言消息——它会指出违规 widget 和轴向（`on the right` = 水平溢出）。
2. 对照 [`layout-errors.md`](../error-fixes/layout-errors.md) 定位错误类别。
3. 应用最小修复（`Expanded` / `SizedBox` / `Material` 包裹 / `Directionality` 等）。
4. 重新 `flutter run` 验证黄黑条纹消失。

### 边界情形

| 情形 | 处理 |
| ---- | ---- |
| 断言消息未明确 widget | 从栈帧定位 build 调用链；找最近一个 `Flex` / `Viewport` |
| 修复后仍有溢出 | 检查父级约束链；可能需要多层 `Expanded` / `ConstrainedBox` |
| `setState during build` | 改用 `addPostFrameCallback` 延迟状态变更 |

---

## 跨轨道协同

| 场景 | 协同 |
| ---- | ---- |
| analyzer 遇到陌生 `package:` API 错误 | 调 `search` 子命令在线查官方文档 |
| runtime 涉及未知 API 约束 | 调 `search` 子命令在线查 |
| layout 修复后仍有运行时崩溃 | 转 runtime 轨道 |
| test 子命令运行时崩溃 | test 输出栈 → 喂给 runtime 轨道 |
| grammar 不确定某限制 | 看 [`restrictions.md`](../grammar/restrictions.md)；仍不确定调 `search` |

## 交付核对清单

### analyzer 轨道
- [ ] analyzer 错误原文已收集；错误类别已在 `analyzer-errors.md` 内定位（或确认表外并调 search）
- [ ] 修改最小化，不重构无关代码；修改后 `flutter analyze` 通过

### runtime 轨道
- [ ] 拿到具体异常锚点后才进入定向代码读取；无锚点时不大规模读代码
- [ ] 修复后跑 `flutter run` 或 `flutter test` 验证

### layout 轨道
- [ ] 断言消息已读取；错误类别已定位
- [ ] 修复后 `flutter run` 验证溢出 / 断言消失
