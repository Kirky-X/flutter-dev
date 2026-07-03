# Flutter 开发规则（Dart / Flutter API / Flutter UI）

> 本文件汇总 Flutter 应用开发的三类强制规则。**违反 Dart 语法约束或空安全规则的代码将无法编译通过或运行时崩溃**。`fix` 子命令的 analyzer 轨道与 `create` 子命令的工程生成都 MUST 遵循本文件。`test` 子命令的 `flutter analyze` 会拦截部分违规。

## 一、Dart 语言规范（违反 → 编译失败 / 运行时崩溃）

### 类型系统与空安全

- Dart 是强类型语言；启用空安全（sound null safety）后，类型 `T` 不再接受 `null`，必须显式用 `T?` 表示可空。
- 永不为空：`int x = 0;` 而非 `int? x = 0;`；可空类型访问成员前必须先做 null 检查或用 `?.` / `??`。
- `late` 修饰符表示"稍后非空初始化"：访问前必须赋值，否则抛 `LateInitializationError`；不要用 `late` 替代可空类型。
- `late final` 用于延迟常量初始化（如 `late final controller = AnimationController(...);`）。
- 禁止用 `!`（null check operator）作为常规写法；仅在你 100% 确定非空时使用，否则用 `if (x != null)` 守卫。
- `Null` 类型是所有类型的子类，但只有 `Never` 是所有类的子类；不要把 `null` 当作"缺省值"传递给非空参数。
- 类型推断：局部变量可省略类型注解（`var x = 1;`），但公共 API、字段、参数应显式标注类型。
- `dynamic` 跳过静态检查，运行时行为与 `Object?` 类似；禁止用 `dynamic` 替代显式类型，除非与 JS 互操作或解析 JSON。
- `Object` 与 `Object?` 区别：前者非空，后者可空；`is` / `as` 用于类型收窄，`as` 在类型不匹配时抛 `TypeError`。
- `is` 检查后编译器自动做类型提升（type promotion）；`is!` 用于否定检查。

### 变量与声明

- 优先 `final`（不可重新赋值）和 `const`（编译时常量）；`const` 比 `final` 更严格。
- `const` 构造函数用于创建编译时常量实例（如 `const EdgeInsets.all(8)`），可减少运行时分配。
- 顶层变量、静态字段、实例字段都可 `final`；类内 `static const` 用于共享常量。
- 禁止用 `var` 声明可空类型并依赖隐式 `null`（空安全下默认非空，必须显式初始化或声明 `T?`）。

### 函数与闭包

- 函数是一等公民；可作为参数、返回值、赋值给变量。
- 箭头函数 `=>` 用于单表达式；多语句用 `{ ... }`。
- 命名参数用 `{}` 包裹（`void foo({required int x, int? y})`）；可选位置参数用 `[]`。
- `required` 修饰命名参数为必填；未标注 `required` 的命名参数默认可空或有默认值。
- 默认值仅能用于可选参数（`{int x = 0}` 或 `[int x = 0]`），且必须是编译时常量。
- 闭包捕获变量按引用捕获；for 循环中创建闭包注意 `index` 的捕获行为（Dart 2.15+ 已修复循环变量捕获）。

### 异步

- `Future<T>` 表示异步结果；`async` 函数返回 `Future`，`await` 等待其完成。
- `async`/`await` 优于 `.then()` 链式调用；异常用 `try/catch` 捕获。
- `Stream<T>` 表示异步事件序列；用 `await for` 或 `listen` 消费。
- `Future` 不 cancel；需要取消用 `CancelableOperation` 或 `StreamSubscription.cancel()`。
- `Stream` 用完必须 `cancel()` 订阅，否则内存泄漏；`State.dispose` 中取消所有订阅。
- `async` 函数中 `return x;` 等价于 `return Future.value(x);`；`return await x;` 会多等一轮事件循环。
- `Future.wait` 并发执行多个 Future；`Future.any` 取首个完成。
- 禁止在 build 方法中直接 `await`；异步逻辑放 `initState` / 事件回调 / `FutureBuilder`。

### 类、mixin、枚举

- 类支持单继承（`extends`）、多接口实现（`implements`）、mixin 混入（`with`）。
- 构造函数：默认构造、命名构造（`Foo.fromJson(...)`）、工厂构造（`factory`）、常量构造（`const`）。
- `this.x` 参数初始化：`Foo(this.x, {this.y});` 是惯用写法。
- 命名构造 + 初始化列表：`Foo.fromJson(Map m) : x = m['x'], super.parent();`，初始化列表在构造体前执行。
- `factory` 构造可返回缓存实例或子类实例；用于单例、缓存、JSON 反序列化。
- `abstract class` 不能实例化，只能被继承；`abstract method` 仅声明签名，子类必须实现。
- `interface`（隐式）：所有类都隐式定义接口，可用 `implements` 实现；实现类必须重写所有实例成员（含字段）。
- `mixin` 用 `mixin M {}` 声明，用 `with M` 混入；`on` 限定 mixin 只能用于特定类（`mixin M on SomeClass {}`）。
- `mixin` 不能有构造函数；有状态的 mixin 需通过 `on` 约束访问宿主字段。
- 枚举 `enum Color { red, green, blue }` 是单例；Dart 3+ 支持增强枚举（带字段、方法、构造函数）。
- 枚举值用 `switch` 时，Dart 3+ 强制穷尽检查（exhaustiveness），缺 case 编译报错。

### 模式匹配与 switch

- Dart 3.0+ 引入模式匹配（patterns）：变量声明模式、赋值模式、switch 表达式、if-case。
- `switch` 表达式 `=>` 返回值：`final color = switch (x) { 1 => Color.red, _ => Color.blue };`。
- 解构模式：`var (a, b) = point;`（record）/ `final (x: px, y: py) = record;`（named field）。
- 类型模式：`if (obj case int i) print(i);` 做类型收窄。
- `switch` 语句 Dart 3+ 自动穷尽检查（对枚举、sealed 类型）；`default` 或 `_` 作为兜底。
- `sealed` 类用于穷尽模式匹配：所有子类在同一文件，switch 可保证穷尽。

### 泛型

- 泛型类、泛型方法、泛型类型别名都支持；`List<T>` / `Map<K, V>` / `T identity<T>(T x) => x;`。
- 泛型在 Dart 中是 reified（具体化）：运行时可获取类型参数（`list.runtimeType`）。
- 泛型约束：`<T extends num>` 限定上界；`<T extends Comparable<T>>` 自限定。
- `void` 作为类型参数表示"忽略返回值"：`Future<void>` 表示不返回值的异步操作。

## 二、Flutter API 使用规范（必读）

- `build` 方法必须纯净：不触发副作用、不发起异步、不修改状态；只根据当前 `widget` / `state` 返回 Widget 树。
- `BuildContext` 只在 `build` / 事件回调内同步使用；禁止跨异步边界保存 `context` 后异步访问（`Navigator.of(context)` 在 widget 卸载后会抛错）。
- `BuildContext.mounted` 在异步 `await` 后必须检查：`if (!context.mounted) return;` 再访问 context 或调用 `setState`。
- `State` 生命周期：`initState` → `build`（可重复）→ `dispose`；`didUpdateWidget` 在 widget 重建时触发；`setState` 触发 rebuild。
- `State.dispose` 必须释放：`AnimationController`、`TextEditingController`、`ScrollController`、`FocusNode`、`StreamSubscription`、`Timer`、`GlobalKey`（视情况）。
- `initState` 中不能 `await`；需要异步初始化用 `WidgetsBinding.instance.addPostFrameCallback` 或 `Future.microtask`。
- 路由优先用项目已有方案（`Navigator 1.0` 命名路由 / `go_router` 等声明式路由）；不要为一个页面引入新路由框架。
- `Navigator.push` 返回 `Future<T?>`；目标页 `Navigator.pop(context, result)` 回传结果。
- 主题：用 `Theme.of(context)` 读取颜色 / 字体 / 间距；不要硬编码颜色，优先 `colorScheme` / `textTheme`。
- `MediaQuery.of(context)` 用于屏幕尺寸、方向、padding；`LayoutBuilder` 用于父级约束自适应。
- `InheritedWidget` / `Provider` / `Riverpod` / `Bloc` 任选其一并遵循项目已有方案；不要在 widget 树里手动传 callback 传递深层状态。
- `const` Widget：能 `const` 的一律 `const`（如 `const SizedBox(height: 8)`），减少 rebuild。
- `Key`：列表项用 `ValueKey(id)`；动态增删的 `StatefulWidget` 必须给稳定 key；不要用 `UniqueKey()` / 数组索引作 key。
- `ListView.builder` / `GridView.builder` 用于长列表，按需构建；全量列表用 `ListView(children: [...])`。
- `GlobalKey` 跨树复用 state 时必须确保同一时刻只挂载一个；跨页面复用易抛 `Multiple widgets used the same GlobalKey`。

## 三、Flutter UI 规范（Material 3 / Cupertino / 响应式 / 无障碍 / 性能）

- Material 3 是默认主题（Flutter 3.16+）；`useMaterial3: true`（默认开），用 `ColorScheme.fromSeed(seedColor: ...)` 生成配色。
- Cupertino 组件（`CupertinoApp` / `CupertinoNavigationBar` / `CupertinoButton`）用于 iOS 风格；同一应用不要 Material 与 Cupertino 混用，除非明确做平台自适应。
- 平台自适应：`Platform.isIOS` / `Theme.of(context).platform` 选择组件；`CupertinoPageTransitionsBuilder` 用于 iOS 路由过渡。
- 响应式布局：`LayoutBuilder` 按断点切换布局；`MediaQuery.sizeOf(context)` 取屏幕尺寸；不要硬编码像素尺寸。
- 无障碍：文本用 `Semantics(label: ...)` 标注语义；可点击区域至少 48×48 dp；图片提供 `Semantics`；`ExcludeSemantics` 用于装饰性元素。
- 性能：避免 `Opacity` widget（用 `AnimatedOpacity` 或 `Visibility`）；`ClipRRect` 慎用；长列表用 `ListView.builder`。
- 重建范围最小化：把会变的状态下沉到叶子 `StatefulWidget`；顶层 widget 用 `const`；`Selector` / `Consumer` 缩小 Provider 监听范围。
- 动画优先 `AnimatedWidget` / `AnimatedBuilder` / `ImplicitlyAnimatedWidget`（`AnimatedContainer` / `AnimatedOpacity`）；复杂动画用 `AnimationController` + `Tween`，dispose 中释放。
- 平台通道 / FFI：原生交互走 `MethodChannel` / `Pigeon`；FFI 用 `dart:ffi`；平台代码改动需重建原生工程。
- 国际化：用 `flutter gen-l10n` + `AppLocalizations.of(context)!.hello`；不要硬编码用户可见文本。
