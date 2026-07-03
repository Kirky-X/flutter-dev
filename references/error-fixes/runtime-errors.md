# Flutter Runtime Errors

Runtime exceptions thrown after the app starts: `NoSuchMethodError`, `TypeError`, `StackOverflowError`, `StateError`, and related. These are not analyzer errors — they crash the running app.

## NoSuchMethodError: tried to call a non-member

```
NoSuchMethodError: The method 'foo' was called on null.
NoSuchMethodError: Class 'String' has no instance method 'foo'.
```

Cause: calling a method on `null`, or on an object whose runtime type does not have the method. Common with `dynamic` values from JSON.

Fix:

- If the receiver is nullable, null-check first: `if (obj != null) obj.foo();`.
- If the receiver is `dynamic` from JSON, parse into a typed model with a `fromJson` factory; do not call methods on `dynamic` blindly.
- If the method was renamed / removed, update the call site to the current API.

```dart
// ❌ Wrong — dynamic field access
final json = jsonDecode(str);     // Map<String, dynamic>
json.foo();                       // NoSuchMethodError

// ✅ Correct — typed access
final obj = jsonDecode(str) as Map<String, dynamic>;
final name = obj['name'] as String?;
```

## TypeError: type 'X' is not a subtype of type 'Y'

```
type 'String' is not a subtype of type 'int' in type cast
type 'List<dynamic>' is not a subtype of type 'List<int>'
```

Cause: a failed `as` cast, or assigning a value whose runtime type is not a subtype of the declared type. Common with JSON lists.

Fix:

```dart
// ❌ Wrong — List<dynamic> is not List<int>
final xs = json['xs'] as List<int>;

// ✅ Correct — cast element-by-element
final xs = (json['xs'] as List).cast<int>();
// or
final xs = (json['xs'] as List).map((e) => e as int).toList();
```

For `as` casts on nullable receivers, prefer `is` checks:

```dart
if (value is int) {
  int x = value;
}
```

## StackOverflowError

Cause: unbounded recursion — a method calls itself (directly or indirectly) without a base case.

Common in Flutter:

- `build` calling another `build` that rebuilds the same widget.
- A `setState` in a listener that triggers another listener.
- Recursive widget construction (`Widget` that returns itself in `build`).

Fix:

- Add a base case to the recursion.
- Break the rebuild loop: do not `setState` inside `build` or inside a listener that fires on every frame.
- For deep data structures, convert recursion to iteration or raise the stack via `dart --enable-asserts` debugging.

## StateError: Bad state: ...

```
StateError: Bad state: Future already completed
StateError: Bad state: Cannot call dispose() while a tree is being built
```

Cause: an operation invoked in an invalid state.

Common cases:

- `Completer.complete()` called twice.
- `StreamController.add()` after `close()`.
- `setState` / `dispose` at the wrong lifecycle point.

Fix:

- Track completion state; guard with `if (!_completer.isCompleted) _completer.complete(...)`.
- Move lifecycle-sensitive calls to the correct `State` callback (`initState` / `dispose`).

## Concurrent modification during iteration

```
Concurrent modification during iteration: {0: 'a'}.
```

Cause: modifying a `Map` / `List` / `Set` while iterating it with `for-in`.

Fix:

- Iterate over a copy: `for (final key in keys.toList()) { map.remove(key); }`.
- Collect changes and apply after the loop.

## RangeError: Invalid value / Index out of range

```
RangeError (index): Index out of range: index should be less than 3: 5
RangeError (start): Invalid value: Not in inclusive range
```

Cause: array index out of bounds, or a `start` / `end` argument outside the valid range.

Fix:

- Check `index < list.length` before access.
- Use `list.elementAtOrNull(index)` (Dart 3.0+) for safe access returning `null`.
- For `substring` / `skip` / `take`, validate the range.

## ArgumentError: Invalid argument(s)

Cause: an argument violates a precondition (e.g. negative `Duration`, empty string where non-empty required).

Fix: validate before calling; surface a clear error to the caller / user instead of letting the framework throw.

## FormatException: ...

```
FormatException: Invalid double
FormatException: Could not find an option named "foo".
```

Cause: parsing a malformed string (`double.parse('x')`), bad URI, bad JSON.

Fix: use `tryParse` variants (`double.tryParse`, `int.tryParse`, `Uri.tryParse`) and handle `null`; wrap `jsonDecode` in `try/catch`.

## Diagnostic flow

1. Read the stack trace — the top app frame names the file and line.
2. Identify the exception type: `NoSuchMethodError` → null/dynamic misuse; `TypeError` → bad cast; `StateError` → wrong lifecycle; `RangeError` → bounds.
3. Reproduce with the minimal input that triggers it.
4. Add a guard / typed model / range check at the source; do not catch-and-ignore.
5. Verify the fix with a test that reproduces the original input.
