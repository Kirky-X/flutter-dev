# Flutter Development Rules (Dart / Flutter API / Flutter UI)

> This file consolidates three categories of mandatory rules for Flutter app development. **Code that violates Dart syntax constraints or null safety rules will fail to compile or crash at runtime.** The `fix` subcommand's analyzer track and the `create` subcommand's project generation MUST follow this file. The `test` subcommand's `flutter analyze` catches some violations.

## I. Dart Language Spec (violation → compile failure / runtime crash)

### Type System and Null Safety

- Dart is a strongly typed language; with sound null safety enabled, type `T` no longer accepts `null` — use `T?` explicitly for nullable.
- Never nullable: `int x = 0;` not `int? x = 0;`; nullable type members must be null-checked before access, or use `?.` / `??`.
- `late` modifier means "non-null initialization later": must be assigned before access, otherwise `LateInitializationError` is thrown; do not use `late` as a substitute for nullable types.
- `late final` is for delayed constant initialization (e.g. `late final controller = AnimationController(...);`).
- Do NOT use `!` (null check operator) as a routine pattern; only use it when 100% certain of non-null, otherwise guard with `if (x != null)`.
- `Null` is a subtype of all types, but only `Never` is a subtype of all classes; do not pass `null` as a "default" to non-null parameters.
- Type inference: local variables can omit type annotations (`var x = 1;`), but public APIs, fields, and parameters should have explicit type annotations.
- `dynamic` skips static checks and behaves like `Object?` at runtime; do NOT use `dynamic` as a substitute for explicit types, except for JS interop or JSON parsing.
- `Object` vs `Object?`: the former is non-null, the latter is nullable; `is` / `as` for type narrowing, `as` throws `TypeError` on type mismatch.
- After an `is` check the compiler performs type promotion; `is!` for negative checks.

### Variables and Declarations

- Prefer `final` (non-reassignable) and `const` (compile-time constant); `const` is stricter than `final`.
- `const` constructors create compile-time constant instances (e.g. `const EdgeInsets.all(8)`), reducing runtime allocations.
- Top-level variables, static fields, and instance fields can all be `final`; `static const` inside a class is for shared constants.
- Do NOT use `var` to declare nullable types and rely on implicit `null` (sound null safety defaults to non-null; must be explicitly initialized or declared `T?`).

### Functions and Closures

- Functions are first-class citizens; can be passed as parameters, return values, or assigned to variables.
- Arrow functions `=>` for single expressions; multi-statement bodies use `{ ... }`.
- Named parameters wrapped in `{}` (`void foo({required int x, int? y})`); optional positional parameters use `[]`.
- `required` marks named parameters as mandatory; named parameters without `required` are nullable or have defaults.
- Default values are only allowed on optional parameters (`{int x = 0}` or `[int x = 0]`) and must be compile-time constants.
- Closures capture variables by reference; in for loops, closures may capture the index — Dart 2.15+ fixed loop variable capture.

### Async

- `Future<T>` represents an async result; `async` functions return a `Future`, `await` waits for completion.
- `async`/`await` is preferred over `.then()` chaining; catch exceptions with `try/catch`.
- `Stream<T>` represents an async event sequence; consume with `await for` or `listen`.
- `Future` cannot be cancelled; use `CancelableOperation` or `StreamSubscription.cancel()` for cancellation.
- `Stream` subscriptions must be `cancel()`ed when done to avoid memory leaks; cancel all subscriptions in `State.dispose`.
- In `async` functions, `return x;` is equivalent to `return Future.value(x);`; `return await x;` adds an extra event loop cycle.
- `Future.wait` executes multiple Futures concurrently; `Future.any` completes with the first one.
- Do NOT `await` directly inside `build` methods; async logic goes in `initState` / event callbacks / `FutureBuilder`.

### Classes, Mixins, Enums

- Classes support single inheritance (`extends`), multiple interface implementation (`implements`), and mixin inclusion (`with`).
- Constructors: default, named (`Foo.fromJson(...)`), factory (`factory`), and const (`const`).
- `this.x` parameter initialization: `Foo(this.x, {this.y});` is the idiomatic pattern.
- Named constructors + initializer lists: `Foo.fromJson(Map m) : x = m['x'], super.parent();`, initializer lists execute before the constructor body.
- `factory` constructors can return cached instances or subclass instances; used for singletons, caching, JSON deserialization.
- `abstract class` cannot be instantiated, only subclassed; `abstract method` declares a signature only, subclasses must implement.
- `interface` (implicit): every class implicitly defines an interface, implementable via `implements`; implementing classes must override all instance members (including fields).
- `mixin` declared with `mixin M {}`, included with `with M`; `on` constrains the mixin to specific classes (`mixin M on SomeClass {}`).
- `mixin` cannot have constructors; stateful mixins require `on` constraints to access host fields.
- Enums `enum Color { red, green, blue }` are singletons; Dart 3+ supports enhanced enums (with fields, methods, constructors).
- When using `switch` on enum values, Dart 3+ enforces exhaustiveness; missing cases cause compile errors.

### Pattern Matching and Switch

- Dart 3.0+ introduces patterns: variable declaration patterns, assignment patterns, switch expressions, if-case.
- `switch` expression `=>` returns a value: `final color = switch (x) { 1 => Color.red, _ => Color.blue };`.
- Destructuring patterns: `var (a, b) = point;` (record) / `final (x: px, y: py) = record;` (named field).
- Type patterns: `if (obj case int i) print(i);` for type narrowing.
- `switch` statements in Dart 3+ auto-check exhaustiveness (for enums, sealed types); `default` or `_` as fallback.
- `sealed` classes enable exhaustive pattern matching: all subtypes in the same file, switch guarantees exhaustiveness.

### Generics

- Generic classes, methods, and typedefs are all supported; `List<T>` / `Map<K, V>` / `T identity<T>(T x) => x;`.
- Generics in Dart are reified: type parameters are available at runtime (`list.runtimeType`).
- Generic bounds: `<T extends num>` for upper bounds; `<T extends Comparable<T>>` for self-bounds.
- `void` as a type parameter means "ignore return value": `Future<void>` represents an async operation with no return value.

## II. Flutter API Usage Rules (Required Reading)

- The `build` method must be pure: no side effects, no async calls, no state mutation; return a Widget tree based solely on the current `widget` / `state`.
- `BuildContext` must only be used synchronously within `build` / event callbacks; do NOT capture `context` in a field and access it asynchronously (`Navigator.of(context)` throws after widget unmount).
- `BuildContext.mounted` must be checked after any async `await`: `if (!context.mounted) return;` before using context or calling `setState`.
- `State` lifecycle: `initState` → `build` (repeatable) → `dispose`; `didUpdateWidget` fires when the widget rebuilds; `setState` triggers rebuild.
- `State.dispose` MUST release: `AnimationController`, `TextEditingController`, `ScrollController`, `FocusNode`, `StreamSubscription`, `Timer`, `GlobalKey` (as applicable).
- Do NOT `await` inside `initState`; for async initialization use `WidgetsBinding.instance.addPostFrameCallback` or `Future.microtask`.
- Routing: prefer the project's existing solution (`Navigator 1.0` named routes / `go_router` or other declarative routing); do NOT introduce a new routing framework for a single page.
- `Navigator.push` returns `Future<T?>`; the target page uses `Navigator.pop(context, result)` to return results.
- Theme: use `Theme.of(context)` to read colors / fonts / spacing; do not hardcode colors; prefer `colorScheme` / `textTheme`.
- `MediaQuery.of(context)` for screen size, orientation, padding; `LayoutBuilder` for parent-constrained adaptive layouts.
- `InheritedWidget` / `Provider` / `Riverpod` / `Bloc` — pick one and follow the project's existing pattern; do NOT pass callbacks manually through the widget tree for deep state.
- `const` Widgets: use `const` wherever possible (e.g. `const SizedBox(height: 8)`), to reduce rebuilds.
- `Key`: use `ValueKey(id)` for list items; dynamic add/remove `StatefulWidget`s MUST have stable keys; do NOT use `UniqueKey()` / array index as key.
- `ListView.builder` / `GridView.builder` for long lists, building on demand; short lists use `ListView(children: [...])`.
- `GlobalKey` for cross-tree state reuse must ensure only one instance is mounted at a time; cross-page reuse frequently throws `Multiple widgets used the same GlobalKey`.

## III. Flutter UI Rules (Material 3 / Cupertino / Responsive / Accessibility / Performance)

- Material 3 is the default theme (Flutter 3.16+); `useMaterial3: true` (enabled by default), use `ColorScheme.fromSeed(seedColor: ...)` to generate palettes.
- Cupertino components (`CupertinoApp` / `CupertinoNavigationBar` / `CupertinoButton`) for iOS-style UI; do NOT mix Material and Cupertino in the same app unless explicitly doing platform adaptation.
- Platform adaptation: `Platform.isIOS` / `Theme.of(context).platform` to choose components; `CupertinoPageTransitionsBuilder` for iOS route transitions.
- Responsive layout: `LayoutBuilder` to switch layouts at breakpoints; `MediaQuery.sizeOf(context)` for screen size; do NOT hardcode pixel dimensions.
- Accessibility: use `Semantics(label: ...)` on text for semantic labeling; tap targets at least 48x48 dp; provide `Semantics` for images; `ExcludeSemantics` for decorative elements.
- Performance: avoid `Opacity` widget (use `AnimatedOpacity` or `Visibility`); use `ClipRRect` sparingly; long lists use `ListView.builder`.
- Minimize rebuild scope: push mutable state down to leaf `StatefulWidget`s; top-level widgets use `const`; `Selector` / `Consumer` to narrow Provider listen scope.
- Animation: prefer `AnimatedWidget` / `AnimatedBuilder` / `ImplicitlyAnimatedWidget` (`AnimatedContainer` / `AnimatedOpacity`); complex animations use `AnimationController` + `Tween`, disposed in `dispose`.
- Platform channels / FFI: native interop via `MethodChannel` / `Pigeon`; FFI via `dart:ffi`; platform code changes require rebuilding native projects.
- Internationalization: use `flutter gen-l10n` + `AppLocalizations.of(context)!.hello`; do NOT hardcode user-visible text.
