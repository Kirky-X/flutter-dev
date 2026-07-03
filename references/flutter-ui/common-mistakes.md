# Flutter Common Mistakes

Check this file before implementing Flutter layouts, lists, state, dialogs, or navigation.

## RenderFlex overflow (yellow-black stripes)

Avoid: unbounded child inside `Row` / `Column` without `Expanded` / `Flexible`.

```dart
// ❌ Wrong — Text overflows horizontally
Row(children: [Text('A very long title that does not fit...')])

// ✅ Correct
Row(children: [Expanded(child: Text('A very long title that does not fit...'))])
```

Rules:

- `Row` children with unbounded width (text, images) must be wrapped in `Expanded` or `Flexible`.
- `Column` inside vertical scroll needs bounded height; wrap with `SizedBox(height: ...)` or use `ListView`.
- Debug stripes show the overflowing axis and pixel amount — fix the constraint, not the symptom.

## Unbounded constraints

Avoid: nesting an unbounded-size widget inside another unbounded parent.

```dart
// ❌ Wrong — Column inside Row with no width constraint
Row(children: [Column(children: [Text('a'), Text('b')])])

// ✅ Correct — give the Column a bounded width
Row(children: [Expanded(child: Column(children: [Text('a'), Text('b')]))])
```

Rules:

- `ListView` inside `Column` must be wrapped in `Expanded` or given a fixed height (`SizedBox(height: 200)`).
- `IntrinsicHeight` / `IntrinsicWidth` are expensive; avoid unless truly needed.
- Horizontal `ListView` inside `Row` and vertical `ListView` inside `Column` both need bounded main-axis size.

## Missing Material / Directionality / MediaQuery ancestor

Avoid: using Material widgets without a `MaterialApp` / `Scaffold` ancestor.

```dart
// ❌ Wrong — no Scaffold ancestor, no Directionality
void main() => runApp(const Text('Hello')) // throws: No Directionality widget found

// ✅ Correct
void main() => runApp(
  MaterialApp(home: Scaffold(body: const Center(child: Text('Hello')))),
);
```

Rules:

- `Text` requires a `Directionality` (provided by `MaterialApp` / `CupertinoApp`).
- `Scaffold` provides `SnackBar` host via `ScaffoldMessenger`; `AppBar` / `Drawer` require `Scaffold`.
- `Theme.of(context)` requires a `Theme` ancestor (provided by `MaterialApp`).

## Excessive rebuilds

Avoid: creating new objects inside `build` that break `==`.

```dart
// ❌ Wrong — new closure each build, defeats const / equality
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, i) => ItemTile(
    onTap: () => doSomething(items[i].id), // new closure every build
  ),
)

// ✅ Correct — stable closure or pass the id
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, i) => ItemTile(
    item: items[i],
    onTap: doSomething, // ItemTile calls back with item.id internally
  ),
)
```

Rules:

- Lift state up; only the widget owning the state should rebuild.
- Mark widgets `const` where possible.
- Use `Selector` / `Consumer` to scope Provider rebuilds; avoid `context.watch<T>()` at the top of a large `build`.
- `AnimatedBuilder` / `ListenableBuilder` limit rebuild scope to the animation's child subtree.

## Stateful widget misuse

Avoid: storing derived data in `State` and forgetting to update it.

```dart
// ❌ Wrong — _uppercase not updated when text changes
class _BadState extends State<Bad> {
  String _text = '';
  String _uppercase = '';

  @override
  void initState() {
    super.initState();
    _text = widget.initial;
    _uppercase = _text.toUpperCase();
  }
  // _uppercase is stale after widget.initial changes
}

// ✅ Correct — derive in build, or update in didUpdateWidget
@override
Widget build(BuildContext context) {
  final uppercase = widget.initial.toUpperCase();
  return Text(uppercase);
}
```

Rules:

- Derive view-only values inside `build`, not in `State` fields.
- Override `didUpdateWidget` to react to `widget` field changes and restart side effects.

## setState after dispose / async gaps

Avoid: calling `setState` after an `await` without checking `mounted`.

```dart
// ❌ Wrong — may crash after the widget is disposed
Future<void> _load() async {
  final data = await api.fetch();
  setState(() => _data = data); // throws if disposed during await
}

// ✅ Correct
Future<void> _load() async {
  final data = await api.fetch();
  if (!mounted) return;
  setState(() => _data = data);
}
```

Rules:

- After every `await` in a `State`, check `if (!mounted) return;` before `setState` / `context` use.
- Cancel `StreamSubscription` / `Timer` in `dispose`; ignore events arriving after dispose.

## GlobalKey reuse

Avoid: using the same `GlobalKey` instance across two simultaneously mounted widgets.

```dart
// ❌ Wrong — two widgets share a key, throws Multiple widgets used the same GlobalKey
final key = GlobalKey();
return Column(children: [Foo(key: key), Foo(key: key)]);

// ✅ Correct — separate keys, or no key
return Column(children: [Foo(), Foo()]);
```

Rules:

- `GlobalKey` must be unique among mounted widgets.
- For state preservation during reorder, use `ValueKey` (not `GlobalKey`) on the reordered children.

## Using Scaffold.of(context) for SnackBar

Avoid: `Scaffold.of(context).showSnackBar(...)` is removed; use `ScaffoldMessenger`.

```dart
// ❌ Wrong (removed API)
Scaffold.of(context).showSnackBar(const SnackBar(content: Text('hi')));

// ✅ Correct
ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('hi')));
```

Rules:

- `ScaffoldMessenger` is the post-Flutter 2.0 host for snack bars, material banners, and persistent / ephemeral bottom sheets.
