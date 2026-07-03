# Flutter Layout Errors

RenderFlex overflow, unbounded constraints, and missing ancestor widget errors. These surface at runtime with a red/yellow stripe banner or a console assertion.

## RenderFlex overflowed (yellow-black stripes)

```
══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══════════════════════════════════════════════════════
The following assertion was thrown during layout:
A RenderFlex overflowed by 34 pixels on the right.
```

Cause: a `Row` / `Column` child has unbounded size along the main axis and the parent cannot accommodate it.

Fix:

```dart
// ❌ Wrong — Text overflows
Row(children: [Text('A very long title that does not fit on one line')])

// ✅ Correct — Expanded lets the Text wrap / truncate
Row(children: [Expanded(child: Text('A very long title'))])

// ✅ Or fix the size
Row(children: [SizedBox(width: 100, child: Text('hi'))])
```

Also: set `maxLines` and `overflow` on `Text` to truncate gracefully:

```dart
Text('...', maxLines: 1, overflow: TextOverflow.ellipsis)
```

## RenderBox was not laid out

```
RenderBox was not laid out: RenderViewport#... NEEDS-LAYOUT NEEDS-PAINT
```

Cause: a scrollable inside a parent with unbounded main-axis size (e.g. `ListView` inside `Column` without height bound).

Fix:

```dart
// ❌ Wrong — Column gives unbounded height to ListView
Column(children: [ListView(children: [...])])

// ✅ Correct — wrap with Expanded
Column(children: [Expanded(child: ListView(children: [...]))])

// ✅ Or fix the height
SizedBox(height: 200, child: ListView(children: [...]))
```

## An InputDecorator was used without being wrapped in a Material widget

```
══╡ EXCEPTION CAUGHT BY SCHEDULER LIBRARY ╞════
No Material widget found.
TextField widgets require a Material widget ancestor.
```

Cause: a `TextField` / `InputDecoration` / `ListTile` used without a `Material` / `Scaffold` ancestor.

Fix:

```dart
// ❌ Wrong — no Material ancestor
runApp(const Center(child: TextField()));

// ✅ Correct
runApp(
  MaterialApp(
    home: Scaffold(body: Center(child: TextField())),
  ),
);
```

For custom widget trees, wrap with `Material` directly:

```dart
Material(child: TextField())
```

## No Directionality widget found

```
No Directionality widget found.
RichText widgets require a Directionality widget ancestor.
```

Cause: `Text` / `RichText` used without a `Directionality` ancestor (normally provided by `MaterialApp` / `CupertinoApp`).

Fix: ensure the root widget is `MaterialApp` / `CupertinoApp`, or wrap with `Directionality(text: TextDirection.ltr, child: ...)`.

## Incorrect use of ParentData widget

```
Incorrect use of ParentData widget.
A Flexible widget must be placed directly inside a Flex widget.
```

Cause: a `Flexible` / `Expanded` / `Positioned` used outside its required parent (`Row` / `Column` / `Stack`).

Fix:

```dart
// ❌ Wrong — Expanded outside Flex
Container(child: Expanded(child: Text('hi')))

// ✅ Correct
Row(children: [Expanded(child: Text('hi'))])
```

`Positioned` must be a direct child of `Stack`. `Flexible` / `Expanded` must be direct children of `Row` / `Column` / `Flex`.

## setState() called during build

```
setState() called during build.
```

Cause: `setState` invoked synchronously inside a `build` method (often via a callback that runs immediately).

Fix: defer with `addPostFrameCallback`:

```dart
WidgetsBinding.instance.addPostFrameCallback((_) {
  setState(() => ...);
});
```

Or move the state change to an event handler / `initState`.

## Looking up a deactivated widget's ancestor

```
Looking up a deactivated widget's ancestor is unsafe.
```

Cause: `BuildContext` used after the widget was removed from the tree (e.g. after `Navigator.pop` or in a post-async callback).

Fix:

```dart
Future<void> _save() async {
  await api.save();
  if (!mounted) return;          // guard
  if (!context.mounted) return;  // Flutter 3.7+
  Navigator.pop(context);
}
```

## RenderViewport does not support returning intrinsic dimensions

Cause: a `ListView` / `GridView` / `CustomScrollView` placed inside a parent that queries intrinsic size (`IntrinsicHeight` / `Row` with `crossAxisAlignment: stretch` and unbounded height).

Fix: give the scrollable a bounded size (`SizedBox`, `Expanded`, `Flexible`), or replace with a non-scrollable `Column` for short content.

## Diagnostic flow

1. Read the assertion message — it names the offending widget and the axis (`on the right` = horizontal overflow).
2. Trace the parent chain: which `Flex` / `Viewport` is unbounded?
3. Apply the smallest fix that bounds the child (`Expanded` / `SizedBox` / `ConstrainedBox`).
4. Re-run; overflow stripes should disappear. Do NOT mask by reducing font size or hiding content.
