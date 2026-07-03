# Null Safety Errors

Runtime exceptions from Dart's sound null safety: `Null check operator used on a null value`, `LateInitializationError`, and type-promotion gaps.

## Null check operator used on a null value

```
_Null check operator used on a null value_
```

Cause: the `!` operator was applied to a `null` value. The static type was non-null (or nullable with `!`), but the runtime value was `null`.

Common sources:

- A nullable field accessed with `!` before assignment.
- A `widget.foo!` where `foo` is `null` at build time.
- A `Map<String, dynamic>` lookup: `json['key']!` when the key is missing.
- A `Future` / `Stream` result assumed non-null.

Fix:

```dart
// ❌ Wrong — ! on a possibly-missing map value
final name = json['name']!;

// ✅ Correct — null-safe access with default
final name = json['name'] as String? ?? 'unknown';
// or explicit check
final raw = json['name'];
if (raw == null) throw StateError('missing name');
final name = raw as String;
```

Prefer `??` for defaults, `if (x != null)` for guards, and typed `fromJson` factories that surface missing fields explicitly.

## LateInitializationError: Field 'x' has not been initialized

```
LateInitializationError: Field '_controller' has not been initialized.
```

Cause: a `late` field was read before its first assignment.

Common sources:

- `late` field assigned in `initState` but read in `build` before `initState` runs (rare, but possible in mixed widget trees).
- `late` field assigned conditionally; an early code path reads it.
- `late final` field whose initialization depends on a value not yet available.

Fix:

```dart
// ❌ Wrong — late read before assignment on some path
class _State extends State<Foo> {
  late final AnimationController _controller;

  @override
  Widget build(BuildContext context) {
    return FadeTransition(opacity: _controller, child: ...); // throws if initState hasn't run
  }
}

// ✅ Correct — assign in initState (guaranteed before build)
@override
void initState() {
  super.initState();
  _controller = AnimationController(vsync: this, duration: const Duration(seconds: 1));
}
```

If the value may genuinely be unavailable, switch from `late` to a nullable `T?` and null-check at use sites.

## Type promotion failures

```
error: The method 'foo' can't be unconditionally invoked because the receiver can be 'null'.
```

Cause: the compiler cannot promote a nullable type to non-null because the value could change between the check and the use (e.g. a field accessed via `this.` or a property getter).

Fix:

```dart
// ❌ Wrong — promotion fails on fields (could change between check and use)
class Foo {
  String? _name;
  void upper() {
    if (_name != null) {
      print(_name.toUpperCase()); // error: _name could be null
    }
  }
}

// ✅ Correct — copy to a local variable
void upper() {
  final name = _name;
  if (name != null) {
    print(name.toUpperCase()); // promoted
  }
}
```

For local variables, promotion works directly:

```dart
String? name = maybeNull();
if (name != null) {
  print(name.toUpperCase()); // OK — local promotion
}
```

## A value of type 'X?' can't be assigned to a variable of type 'X'

```
error: A value of type 'String?' can't be assigned to a variable of type 'String'
```

Cause: assigning a nullable result to a non-null variable without handling the null case.

Fix:

```dart
// ❌ Wrong
String name = maybeNull();

// ✅ Correct
String name = maybeNull() ?? 'default';
String? nullable = maybeNull();        // accept null
```

## The non-nullable variable 'x' must be assigned before it's used

Cause: a non-null local variable is read on a path where it hasn't been assigned.

Fix: initialize at declaration, or ensure every code path assigns before read, or make it nullable.

## The parameter 'x' can't have a value of 'null' because of its type

Cause: passing `null` to a non-null parameter.

Fix:

- Change the parameter type to `T?` if null is a valid input.
- Provide a non-null value.
- Use a default: `void foo({String name = 'default'})`.

## Flow analysis gap: null check in a closure

Promotion does NOT apply across closures if the variable is captured:

```dart
String? name = maybeNull();
final callback = () {
  if (name != null) {
    print(name.toUpperCase()); // may still error if name is a field
  }
};
```

For local variables this is usually fine; for fields, copy to a local first.

## Diagnostic flow

1. Read the exception name: `LateInitializationError` → late field read early; `Null check operator` → `!` on null; `TypeError` → bad cast.
2. Locate the field / expression in the stack trace's top app frame.
3. Trace the assignment: is it conditional? In `initState`? From a `Map` lookup?
4. Replace `!` with `??` / explicit null check; switch `late` to `T?` if assignment timing is uncertain.
5. Add a test that exercises the null path (missing JSON key, early read) to prevent regression.
