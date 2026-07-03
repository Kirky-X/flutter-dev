# Dart Basic Syntax

This file summarizes high-value Dart syntax guidance for common authoring and review questions. Dart 3.0+ with sound null safety is assumed.

## Variables

- Use `var` for local variables when the type is obvious from the initializer.
- Use `final` for variables that will not be reassigned.
- Use `const` for compile-time constant values.
- Use explicit type annotations for public APIs, fields, and parameters.

```dart
var count = 1;            // inferred int
final name = 'Alice';     // runtime constant
const pi = 3.14;          // compile-time constant
List<int> items = [];     // explicit type
```

Reference: Dart language tour — Variables.

## Types and null safety

- `T` is non-null; `T?` is nullable. Access members of `T?` only after a null check.
- `??` provides a default: `int x = maybeNull ?? 0;`.
- `?.` is null-aware access: `person?.name`.
- `!` asserts non-null (throws if null); use sparingly.
- `late` defers initialization of a non-null field; access before assignment throws `LateInitializationError`.

```dart
int? maybeNull;
int safe = maybeNull ?? 0;
String? name = person?.name;
late final controller = TextEditingController();
```

Reference: Dart language tour — Null safety.

## Functions

- Arrow functions `=>` for single expressions.
- Named parameters with `{}`; optional positional with `[]`.
- `required` marks a named parameter as mandatory.
- Default values must be compile-time constants.

```dart
int square(int x) => x * x;

void greet({required String name, String greeting = 'Hello'}) {
  print('$greeting, $name');
}

String fmt([String? prefix]) => '${prefix ?? ''}value';
```

Reference: Dart language tour — Functions.

## Classes and constructors

- Default, named, factory, and const constructors.
- `this.x` parameter initializes a field directly.
- Initializer list runs before the constructor body.
- `abstract class` cannot be instantiated; subclasses implement abstract members.

```dart
class Point {
  final double x;
  final double y;
  const Point(this.x, this.y);
  const Point.origin() : x = 0, y = 0;

  double get distance => sqrt(x * x + y * y);
}

abstract class Shape {
  double area();
}
class Circle extends Shape {
  final double r;
  Circle(this.r);
  @override
  double area() => pi * r * r;
}
```

Reference: Dart language tour — Classes.

## Async

- `Future<T>` is an async result; `Stream<T>` is an async sequence.
- `async` marks a function returning `Future`; `await` suspends until the future completes.
- `async*` marks a generator returning `Stream`; `yield` emits a value.
- Errors propagate through futures and streams; catch with `try/on/catch`.

```dart
Future<String> fetchName() async {
  final resp = await http.get(uri);
  return resp.body;
}

Stream<int> counter() async* {
  for (var i = 0; i < 5; i++) {
    await Future.delayed(Duration(seconds: 1));
    yield i;
  }
}

try {
  final name = await fetchName();
} on FormatException catch (e) {
  print('bad format: $e');
} catch (e, st) {
  print('error: $e\n$st');
}
```

Reference: Dart language tour — Asynchronous programming.

## Enums

- Plain enums: `enum Color { red, green, blue }`.
- Enhanced enums (Dart 2.17+): fields, methods, const constructors.

```dart
enum HttpStatus {
  ok(200, 'OK'),
  notFound(404, 'Not Found');

  const HttpStatus(this.code, this.label);
  final int code;
  final String label;
  bool get isError => code >= 400;
}
```

Reference: Dart language tour — Enums.

## Pattern matching (Dart 3.0+)

- Switch expressions return a value.
- Destructuring for records and objects.
- `if-case` combines a condition with a pattern.
- `sealed` classes enable exhaustive switching.

```dart
final desc = switch (status) {
  HttpStatus.ok => 'success',
  HttpStatus.notFound => 'missing',
  _ => 'other',
};

var (a, b) = (1, 2);
final (x: px, y: py) = (x: 3, y: 4);

if (obj case int i) print('int $i');

sealed class Result {}
class Success extends Result {}
class Failure extends Result {}

String msg(Result r) => switch (r) {
  Success() => 'ok',
  Failure() => 'err',
};
```

Reference: Dart language tour — Patterns.

## Mixins

- `mixin M {}` declares a reusable unit mixed in with `with`.
- `mixin M on Base {}` constrains the mixin to types extending `Base`.
- Mixins cannot have constructors.

```dart
mixin Logging {
  void log(String msg) => print('[$runtimeType] $msg');
}

class Service with Logging {
  void run() => log('running');
}
```

Reference: Dart language tour — Mixins.

## Generics

- Generic classes, methods, and typedefs.
- Reified generics: type arguments are available at runtime.
- Bounds with `extends`.

```dart
class Stack<T> {
  final List<T> _items = [];
  void push(T x) => _items.add(x);
  T pop() => _items.removeLast();
}

T first<T extends Comparable<T>>(List<T> xs) => xs.first;

typedef IntList = List<int>;
```

Reference: Dart language tour — Generics.
