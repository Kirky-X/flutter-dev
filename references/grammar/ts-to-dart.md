# TypeScript to Dart Syntax Differences

This file highlights TypeScript patterns that often need rewriting in Dart. Aimed at developers with a TS background.

## Type system shape

- TS is structurally typed; Dart is nominally typed. Two classes with identical fields are NOT interchangeable in Dart.
- TS `interface` is structural; Dart has no standalone `interface` keyword — every class implicitly defines an interface you can `implements`.
- TS `type` aliases and union types (`string | number`) have no direct Dart equivalent. Use a sealed class hierarchy or `Object?` with type checks.

TypeScript style:

```ts
interface Point { x: number; y: number }
type Result = string | number
function print(p: Point) {}
```

Dart style:

```dart
class Point {
  final double x;
  final double y;
  const Point(this.x, this.y);
}

sealed class Result {}
class StringResult extends Result { final String value; StringResult(this.value); }
class NumberResult extends Result { final num value; NumberResult(this.value); }

void printPoint(Point p) {}
```

## Null vs undefined

- TS has both `null` and `undefined`; Dart has only `null`.
- TS optional `x?: T` becomes Dart `T? x` (nullable, defaults to `null`).
- TS `!` (non-null assertion) and `??` (nullish coalescing) exist in Dart with the same syntax but `??` only catches `null`, not `undefined`.

```ts
// TS
let name: string | null = maybeNull();
let safe = name ?? 'default';
let upper = name!.toUpperCase();
```

```dart
// Dart
String? name = maybeNull();
String safe = name ?? 'default';
String upper = name!.toUpperCase();
```

## Variable declarations

- TS `let` / `const` map to Dart `var` / `final`.
- Dart `const` is stronger than TS `const`: it means the value is a compile-time constant (deeply immutable), not just a non-reassigned binding.
- TS `var` should be avoided; Dart has no `var` hoisting problem, but `var` infers a non-nullable type from the initializer.

```ts
// TS
const config = { host: 'localhost' };  // non-reassigned, still mutable fields
```

```dart
// Dart
final config = {'host': 'localhost'};  // non-reassigned, still mutable map
const timeout = Duration(seconds: 30); // compile-time constant
```

## Classes and constructors

- TS constructor parameter properties (`constructor(public x: number)`) have a Dart equivalent: `Point(this.x)`.
- TS abstract classes and interfaces map to Dart `abstract class` and `implements`.
- TS does not support mixins directly; Dart has first-class `mixin`.

```ts
// TS
class Point {
  constructor(public x: number, public y: number) {}
}
```

```dart
// Dart
class Point {
  final double x;
  final double y;
  const Point(this.x, this.y);
}
```

## Async

- TS `Promise<T>` → Dart `Future<T>`.
- TS `async`/`await` syntax is identical in Dart.
- TS `AsyncIterator` / `for await` → Dart `Stream<T>` / `await for`.
- TS `Promise.all` → Dart `Future.wait`; TS `Promise.race` → Dart `Future.any`.
- Dart `async*` generators have no direct TS equivalent (use `AsyncGenerator`).

```ts
// TS
async function fetch(): Promise<string> { return 'hi'; }
for await (const x of stream()) {}
```

```dart
// Dart
Future<String> fetch() async => 'hi';
await for (final x in stream()) {}
```

## Union types and exhaustive switches

- TS union types (`A | B`) are structural; Dart uses `sealed` classes for exhaustive pattern matching.
- TS `switch (true)` patterns map to Dart switch expressions with type patterns.

```ts
// TS
type Shape = Circle | Square;
function area(s: Shape) {
  switch (s.kind) {
    case 'circle': return Math.PI * s.r ** 2;
    case 'square': return s.side ** 2;
  }
}
```

```dart
// Dart
sealed class Shape {}
class Circle extends Shape { final double r; Circle(this.r); }
class Square extends Shape { final double side; Square(this.side); }

double area(Shape s) => switch (s) {
  Circle(:final r) => 3.14 * r * r,
  Square(:final side) => side * side,
};
```

## Collections

- TS `Array<T>` → Dart `List<T>`; TS `Map<K,V>` → Dart `Map<K,V>`; TS `Set<T>` → Dart `Set<T>`.
- TS array spread `[...xs]` works in Dart; TS object spread `{...obj}` is `...obj` in Dart maps and records.
- TS `.map().filter()` chains work in Dart; `.map` returns a lazy `Iterable` — call `.toList()` to materialize.

```ts
// TS
const xs = [1, 2, 3].filter(x => x > 1).map(x => x * 2);
```

```dart
// Dart
final xs = [1, 2, 3].where((x) => x > 1).map((x) => x * 2).toList();
```

## Modules and imports

- TS `export`/`import` map to Dart `export`/`import`.
- Dart imports use `package:` (own package) or `dart:` (SDK) URIs.
- Dart has no default exports; every import names the symbol: `import 'package:foo/bar.dart';` brings in all public symbols, or use `show` / `hide` to filter.

```ts
// TS
import { foo } from './bar';
import * as baz from './baz';
```

```dart
// Dart
import 'package:my_app/bar.dart' show foo;
import 'package:my_app/baz.dart' as baz;
```

## Type assertions

- TS `x as T` (assertion) has a Dart equivalent `x as T`, but Dart `as` throws `TypeError` if the cast fails — it is not a hint.
- TS `x as unknown as T` (double cast) is an anti-pattern in Dart; redesign with proper types instead.

```ts
// TS
const n = (x as unknown) as number;
```

```dart
// Dart — prefer fixing the type rather than casting
final n = x as num;  // throws at runtime if x is not a num
```

## JSON

- TS `JSON.parse` returns `any`; Dart `jsonDecode` returns `dynamic`.
- Dart requires explicit field access or `fromJson` factories; do not rely on `dynamic` field access.

```ts
// TS
const obj = JSON.parse(str) as { name: string };
console.log(obj.name);
```

```dart
// Dart
final obj = jsonDecode(str) as Map<String, dynamic>;
print(obj['name'] as String);
// or: a fromJson factory
```
