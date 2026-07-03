---
name: dart-migrate-to-checks-package
description: |-
  Replace the usage of `expect` and similar functions from `package:matcher`
  to `package:checks` equivalents.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Tue, 09 Jun 2026 19:30:00 GMT
---
# Migrating Dart Tests to Package Checks

Use this skill when you need to migrate a Dart test suite from the legacy
`package:matcher` (which is exported by default from `package:test/test.dart`)
to the modern, type-safe, and literate `package:checks` assertion library.

## When to Use This Skill
- When asked to "migrate tests to checks", "use package:checks", or
  "modernize test assertions".
- When updating legacy test suites where static type safety, better
  autocomplete in IDEs, and highly detailed failure diagnostics are desired.

---

## How to Use This Skill (The Workflow)

### 1. Dependency Setup
- Add `package:checks` as a `dev_dependency`:
  ```bash
  dart pub add dev:checks
  ```
- Remove explicit `package:matcher` from `dev_dependencies` if listed (it's transitively included by `package:test`).

### 2. Migrating a File
1. **Update Imports** — Replace `import 'package:test/test.dart';` with:
   ```dart
   import 'package:test/scaffolding.dart';
   import 'package:checks/checks.dart';
   ```
   For incremental migration, temporarily add `import 'package:test/expect.dart';` to allow legacy `expect()`.
2. **Translate Assertions** — Rewrite `expect`/`expectLater` calls to `check` syntax (see sections below).
3. **Verify via Compiler** — Remove the temporary `expect.dart` import. Remaining `expect` calls will surface as compile errors.

### 3. Verification
- **Static Analysis**: `dart analyze` — watch generic type params on `.isA<Type>()` and `unawaited_futures` warnings.
- **Run Tests**: `dart test` — leverage `package:checks`' detailed failure output to diagnose incorrect translations.

---

## Key Syntax Differences and Pitfalls

> [!IMPORTANT]
> A line-for-line translation can introduce subtle bugs. Review these key differences:

### 1. Collection Equality (`deepEquals` vs `equals`)
Legacy `expect(actual, expected)` did deep equality for collections. In checks, `.equals()` uses strict `operator ==` (identity for collections). **Always use `.deepEquals(expected)` for collections.**
```dart
// BEFORE: expect(myList, [1, 2, 3]);
// AFTER:  check(myList).deepEquals([1, 2, 3]);
```

### 2. `reason` → `because`
The explanation parameter `reason` becomes `because`, passed *before* the subject:
```dart
check(because: 'Explanation', actual).expectation();
```

### 3. Regex Matching (`matches` → `matchesPattern`)
`matchesPattern` treats String args as literal patterns. Pass a `RegExp` explicitly:
```dart
check(someString).matchesPattern(RegExp(r'\d+'));
```

### 4. Property Extraction (`TypeMatcher.having` → `.has`)
`.has(feature, description)` returns a new `Subject` for chaining:
```dart
check(actual).isA<Person>().has((p) => p.name, 'name').startsWith('A');
```

### 5. Sync vs. Async `throws<E>()`
- **Sync** (`Subject<T Function()>`): returns `Subject<E>`, chain directly (no callback):
  ```dart
  check(() => triggerSyncError()).throws<ArgumentError>()
    ..has((e) => e.message, 'message').equals('invalid input');
  ```
- **Async** (`Subject<Future<T>>`): returns `Future<void>`, **requires** an inspection callback:
  ```dart
  await check(triggerAsyncError()).throws<ArgumentError>((it) => it
    ..has((e) => e.message, 'message').equals('invalid input'));
  ```

### 6. Nullable `bool?` (`isTrue`/`isFalse`)
`.isTrue()` / `.isFalse()` only work on non-nullable `Subject<bool>`. For `bool?`, refine (`.isNotNull().isTrue()`) or use `.equals(true)`:
```dart
check(options.flagOutdated).equals(true);
```

### 7. Map Key Containment (`contains` → `containsKey`)
`.contains(...)` on `Subject<Map>` is undefined. Use `.containsKey(key)`:
```dart
check(myMap).containsKey('my_key');
```

### 8. RegExp Equality
Separate `RegExp` instances don't satisfy `==`. Use `.isA<RegExp>()` with cascades:
```dart
check(myPattern).isA<RegExp>()
  ..has((r) => r.pattern, 'pattern').equals('Hello');
```

### 9. Extension Types & Dynamic Casts
- For extension types implementing primitives, use explicit generic: `check<int>(QrEciValue.iso8859_1).equals(3);`
- For dynamic JSON lookups in `.deepEquals(...)`, cast explicitly: `check(myIterable).deepEquals(json['data']['items'] as List);`

---

## Matcher-to-Checks Mapping Table

Use this table as a quick reference for direct matcher replacements:

| Legacy Matcher | Package Checks Equivalent | Notes |
| :--- | :--- | :--- |
| `expect(actual, expected)` | `check(actual).equals(expected)` | Use `.deepEquals` for collections! |
| `expect(actual, equals(expected))` | `check(actual).equals(expected)` | Use `.deepEquals` for collections! |
| `isA<T>()` | `check(actual).isA<T>()` | Chaining is supported directly |
| `same(expected)` | `check(actual).identicalTo(expected)` | Verifies identity |
| `anyElement(matcher)` | `check(iterable).any(conditionCallback)` | E.g. `check(list).any((e) => e.equals(1))` |
| `everyElement(matcher)` | `check(iterable).every(conditionCallback)` | E.g. `check(list).every((e) => e.isGreaterThan(0))` |
| `hasLength(expected)` | `check(actual).length.equals(expected)` | Works on String, Map, Iterable, etc. |
| `isNot(matcher)` | `check(actual).not(conditionCallback)` | E.g. `check(val).not((it) => it.equals(5))` |
| `contains(element)` | `check(actual).contains(element)` | Works on String, Iterable (use `containsKey` for Map!) |
| `contains(key)` (on a Map) | `check(map).containsKey(key)` | Map key containment |
| `startsWith(prefix)` | `check(string).startsWith(prefix)` | String only |
| `endsWith(suffix)` | `check(string).endsWith(suffix)` | String only |
| `isEmpty` | `check(actual).isEmpty()` | Works on String, Map, Iterable |
| `isNotEmpty` | `check(actual).isNotEmpty()` | Works on String, Map, Iterable |
| `isNull` | `check(actual).isNull()` | |
| `isNotNull` | `check(actual).isNotNull()` | |
| `isTrue` / `true` | `check(actual).isTrue()` | Works on non-nullable `bool` only |
| `isFalse` / `false` | `check(actual).isFalse()` | Works on non-nullable `bool` only |
| `completion(matcher)` | `await check(future).completes(conditionCallback)` | Must be awaited! |
| `throwsA(matcher)` | `await check(future).throws<Type>()` | Must be awaited! |
| `emits(value)` | `await check(streamQueue).emits(conditionCallback)` | Must be awaited! |
| `emitsThrough(value)` | `await check(streamQueue).emitsThrough(conditionCallback)` | Must be awaited! |
| `stringContainsInOrder(list)` | `check(string).containsInOrder(list)` | String only |
| `pairwiseCompare(...)` | `check(actual).pairwiseMatches(...)` | |

---

## Matchers with No Direct Replacements

- **Specific error matchers** (`throwsArgumentError`, `throwsStateError`, etc.): Use `.throws<T>()`:
  ```dart
  await check(triggerError()).throws<ArgumentError>();
  ```
- **`anything`**: Pass an empty callback `(_) {}` when a condition is syntactically required:
  ```dart
  await check(someFuture).completes((_) {});
  ```
- **Numeric toggles** (`isPositive`, `isNegative`, `isZero`, `isNonNegative`): Use comparative expectations (`isGreaterThan(0)`, `isLessThan(0)`, `equals(0)`, `isGreaterOrEqual(0)`).
- **Numeric ranges** (`inClosedOpenRange`, `inInclusiveRange`): Chain boundaries via cascade:
  ```dart
  check(actualValue)
    ..isGreaterOrEqual(min)
    ..isLessThan(max);
  ```

---

## Writing Custom Expectations (Replacing Custom Matchers)

Custom assertions are `extension` methods on `Subject<T>`. Import the context API:
```dart
import 'package:checks/context.dart';
```

### Simple Custom Expectations (`context.expect`)
```dart
extension CustomPersonChecks on Subject<Person> {
  void isAdult() {
    context.expect(
      () => ['is an adult (age >= 18)'],
      (actual) => actual.age >= 18
        ? null
        : Rejection(which: ['is only ${actual.age} years old']),
    );
  }
}
```

### Nested Property Extraction
- **`has`** (simple, non-failing field access): `Subject<Address> get address => has((p) => p.address, 'address');`
- **`nest`** (can fail/reject): use `context.nest(...)` returning `Extracted.rejection(...)` or `Extracted.value(...)`.

### Asynchronous Custom Expectations
Use `context.expectAsync` (or `context.nestAsync`) and return the `Future`:
```dart
extension CustomFutureChecks<T> on Subject<Future<T>> {
  Future<void> completesNormally() => context.expectAsync(
    () => ['completes without throwing'],
    (actual) async {
      try { await actual; return null; }
      catch (e) { return Rejection(which: ['threw $e']); }
    },
  );
}
```

---

## Strategies for Discovery

```bash
# Find legacy expect() / expectLater() calls
grep -rn "expect(" test/
grep -rn "expectLater(" test/

# Find potential collection equality pitfalls (literal lists/maps)
grep -rn "expect(.*, \[" test/
grep -rn "expect(.*, {" test/

# Find matches() calls (need RegExp + matchesPattern)
grep -rn "matches(" test/

# Find legacy TypeMatcher.having() calls (convert to .has())
grep -rn "having(" test/
```

---

## Examples

### Basic Assertions
```dart
// BEFORE: expect(someValue, isNotNull);
// AFTER:  check(someValue).isNotNull();

// BEFORE: expect(result, isTrue, reason: 'should be successful');
// AFTER:  check(because: 'should be successful', result).isTrue();
```

### Collections & Cascades
```dart
check(items).deepEquals([1, 2, 3]);
check(someString)
  ..startsWith('a')
  ..contains('b')
  ..endsWith('c');
```

### Complex Property Matching
```dart
check(response).isA<Response>()
  ..has((r) => r.statusCode, 'statusCode').equals(200)
  ..has((r) => r.body, 'body').contains('success');
```

### Async Futures & Streams
```dart
await check(fetchData()).completes((it) => it.equals('data'));
await check(failingCall()).throws<StateError>();

var queue = StreamQueue(Stream.fromIterable([1, 2, 3]));
await check(queue).inOrder([
  (s) => s.emits((e) => e.equals(1)),
  (s) => s.emits((e) => e.equals(2)),
]);
```
