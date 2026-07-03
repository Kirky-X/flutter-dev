# Dart Restrictions

This file summarizes Dart-specific restrictions and sharp edges that are especially useful in code review and runtime troubleshooting.

## Null safety

- Sound null safety is the default (Dart 2.12+). A variable of type `T` cannot hold `null`; use `T?` for nullable.
- `late` variables must be assigned before first read; otherwise `LateInitializationError` is thrown at runtime.
- `late final` allows one-time delayed initialization; reading before assignment throws.
- `!` (null check operator) throws `TypeError` if the value is `null`. Avoid as a routine pattern.
- `Null` is a type that has exactly one value: `null`. `Null` is a subtype of every nullable type but NOT of non-nullable types.
- `Never` is the bottom type (subtype of everything). A function returning `Never` never returns (always throws or loops).
- Flow analysis: `if (x != null)` promotes `x` from `T?` to `T` within the branch; `return` / `throw` in the negative branch promotes after.

## Type inference and `dynamic`

- `var` infers a non-nullable type from the initializer: `var x = 1;` → `int`, not `int?` or `dynamic`.
- `dynamic` disables static checks entirely; runtime behaves like `Object?` but allows any member access (throws `NoSuchMethodError` if missing).
- `Object` requires explicit casts / `is` checks before accessing non-`Object` members.
- `Object?` accepts everything including `null`; use `is` to narrow.
- Function return type inference is limited: a function with no return type and a `return foo();` to an untyped `foo` may fail to infer. Prefer explicit return types on public APIs.

## Mixin restrictions

- Mixins cannot declare constructors.
- Mixins cannot be instantiated directly.
- `mixin M on Base {}` requires the mixin to be applied to a class that extends / implements `Base`.
- A class can mix in multiple mixins (`class C extends Base with A, B {}`); order matters — later mixins override earlier ones.
- Mixins cannot use `with` to mix in other mixins; use `on` to compose via inheritance.

## Class restrictions

- A class can extend at most ONE class (single inheritance).
- A class can implement multiple interfaces (`implements A, B`), but must override every member of every interface (including fields).
- `interface` keyword does not exist; `implements SomeClass` treats `SomeClass` as an interface — you must reimplement all instance members, even if they have implementations in the source class.
- To mark a class as only extendable (not implementable), use `interface class` (Dart 3.0+ class modifiers).
- `base class` (Dart 3.0+) allows only `extends`, not `implements`.
- `final class` (Dart 3.0+) disallows both extending and implementing outside the library.
- `sealed class` (Dart 3.0+) requires all subtypes in the same library and enables exhaustive `switch`.

## Const restrictions

- `const` variables and fields must be initialized with a compile-time constant expression.
- `const` constructors require all fields to be `final` and initialized with constant values.
- A `const` list / map / set literal is deeply immutable: `const [1, 2, 3]`.
- `const` widgets are canonicalized at compile time; identical `const` widgets share one instance.
- `const` cannot reference runtime values (function params, `DateTime.now()`, random numbers).

## Async restrictions

- An `async` function always returns a `Future`; the body is wrapped.
- An `async` function cannot return a non-`Future` value directly; `return x;` becomes `return Future.value(x);`.
- `await` is only valid inside `async` / `async*` functions.
- `yield` / `yield*` are only valid inside `sync*` / `async*` generators.
- A `Future` cannot be cancelled; use `CancelableOperation` from `package:async` or close a `StreamSubscription`.
- `StreamSubscription` must be `cancel()`ed; failing to do so leaks resources.

## Switch and exhaustiveness

- Dart 3.0+ enforces exhaustiveness for `switch` expressions over sealed types and enums.
- A `switch` statement without a default falls through unless `break` is present; Dart disallows implicit fall-through.
- Empty `case` bodies share the next case's body (allowed for grouping).
- `_` matches anything in patterns; `default` is the legacy fallback in statements.

## Number types

- `int` and `double` are subtypes of `num`.
- `int` is 64-bit on native, arbitrary precision on web for literals but 64-bit for arithmetic.
- `1 / 2` returns a `double` (`0.5`), not an `int`. Use `1 ~/ 2` for integer division.
- `int.parse('x')` throws `FormatException` on invalid input; use `int.tryParse` to get `null`.

## String restrictions

- Strings are immutable UTF-16 sequences.
- `'x'` and `"x"` are equivalent; use `'''triple'''` for multi-line.
- String interpolation `'$x'` / `'${expr}'` is the idiomatic formatter.
- Adjacent string literals do NOT auto-concatenate (`'a' 'b'` is a syntax error, unlike C).

## How to cite this file

When using this file, cite the specific restriction (e.g. "Dart mixin restriction: mixins cannot have constructors"). For null safety rules, also reference the official Dart null safety documentation. For class modifiers (base / interface / final / sealed), reference the Dart 3.0 class modifiers feature.
