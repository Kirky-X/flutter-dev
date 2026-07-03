# Dart Analyzer Errors

Common `flutter analyze` / `dart analyze` errors, warnings, and infos with one-line fixes. Run `flutter analyze` to surface these before runtime.

## Error: A value of type 'X' can't be assigned to a variable of type 'Y'

```
error: A value of type 'String?' can't be assigned to a variable of type 'String'
```

Cause: assigning a nullable or wider type to a non-null / narrower type without an explicit conversion.

Fix:

```dart
// ❌ Wrong
String name = maybeNull();

// ✅ Correct — null check or default
String name = maybeNull() ?? 'default';
// or
final maybe = maybeNull();
if (maybe != null) {
  String name = maybe;
}
```

## Error: The method 'foo' isn't defined for the type 'X'

```
error: The method 'foo' isn't defined for the type 'Widget'
```

Cause: the method does not exist on the static type — typo, missing import, or wrong type assumed.

Fix:

- Check spelling and the API docs for the type.
- If the runtime type is a subtype, narrow with `is` first: `if (obj is SubType) obj.foo();`.
- If using a package, ensure `import 'package:foo/bar.dart';` is present and version is up to date.

## Error: The argument type 'X' can't be assigned to the parameter type 'Y'

Cause: passing a mismatched type to a function parameter.

Fix:

```dart
// ❌ Wrong
Text(123)

// ✅ Correct
Text(123.toString())
Text('$count')
```

## Error: Undefined name 'X'

Cause: the identifier is not in scope — missing import, wrong variable name, or not declared.

Fix: add the import (`import 'dart:math';`), correct the spelling, or declare the variable.

## Error: The named parameter 'foo' isn't defined

Cause: the constructor / method does not accept a parameter named `foo`.

Fix:

- Check the widget API for the correct parameter name (e.g. `child` vs `children`).
- For renamed APIs, see the package changelog.

## Error: Required named parameter 'foo' must be provided

Cause: a `required` named parameter was omitted.

Fix:

```dart
// ❌ Wrong
greet();

// ✅ Correct
greet(name: 'Alice');
```

## Error: 'X' isn't a type

Cause: a non-type identifier is used in a type annotation — often a typo or a missing import of the type.

Fix: import the type, or correct the spelling. Check capitalization (types are UpperCamelCase).

## Error: The return type 'Null' isn't a 'X'

Cause: a function declared to return `X` has a code path that returns `null` (or implicitly returns `null`).

Fix: return a value of `X`, or change the return type to `X?` and adjust callers.

## Warning: Prefer const with constant constructors

```
info: Prefer const with constant constructors
```

Cause: a widget constructor supports `const` but the call omits `const`.

Fix:

```dart
// ❌ Warning
SizedBox(height: 8)

// ✅ Correct
const SizedBox(height: 8)
```

## Warning: The value of the local variable 'x' isn't used

```
warning: The value of the local variable 'x' isn't used
```

Cause: a declared variable is never read.

Fix: remove it, or prefix with `_` if intentionally unused, or actually use it.

## Warning: 'X' is deprecated and shouldn't be used

Cause: the API is marked `@Deprecated`; will be removed in a future version.

Fix: migrate to the replacement noted in the deprecation message (e.g. `Scaffold.of(context).showSnackBar` → `ScaffoldMessenger.of(context).showSnackBar`).

## Warning: Unnecessary import

Cause: a duplicate or unused import directive.

Fix: remove the redundant `import` line.

## Info: Avoid using unnecessary braces in string interpolation

```
info: Avoid using braces in string interpolation when not needed
```

Cause: `'${x}'` where `'x'` would do.

Fix: use `'$x'` for simple identifiers; keep `'${expr}'` only for expressions.

## Info: Always specify control flow column

Common lint about `if` / `for` collection elements — use the collection-if / collection-for syntax.

## Error: The non-nullable local variable 'x' must be assigned before it's used

Cause: a non-null variable is read before assignment on some code path.

Fix: initialize it, make it nullable, or ensure all paths assign before read.

## Error: A non-null value must be returned

Cause: a function declared to return a non-null `T` has a code path that falls off the end.

Fix: add a `return` on every path, or change the return type to `T?`.

## Running the analyzer

```bash
flutter analyze            # in a Flutter project
dart analyze               # in a Dart-only package
dart analyze lib/          # scope to a directory
```

Exit code 0 = no issues; non-zero = issues found. CI should fail the build on any `error`.

## Suppression (last resort)

```dart
// ignore: unused_local_variable
var x = 1;

// ignore_for_file: avoid_print
```

Prefer fixing the issue; suppression hides real problems and rots over time.
