# Flutter API Guardrails

Use these rules before writing Flutter widget constructors, lifecycle overrides, or context-dependent calls.

## BuildContext usage

- `BuildContext` is only valid while the widget is mounted. Do not capture `context` in a field or pass it to a long-lived object.
- After any `await` in a `State`, check `if (!mounted) return;` (or `if (!context.mounted) return;`) before using `context` or calling `setState`.
- `Navigator.of(context)`, `Theme.of(context)`, `MediaQuery.of(context)`, `ScaffoldMessenger.of(context)` all require an ancestor of the right type; wrap in `Builder` if the current widget lacks the ancestor.
- Prefer `context.mounted` (Flutter 3.7+) over the deprecated `mounted` field on `State` for asynchronous checks inside `StatelessWidget.build` closures.

## Lifecycle and dispose

- `initState` cannot be `async` and cannot `await`. Trigger async work via `WidgetsBinding.instance.addPostFrameCallback` or a microtask.
- `dispose` MUST release every disposable resource created in the state: `AnimationController`, `TextEditingController`, `ScrollController`, `FocusNode`, `PageController`, `TabController`, `StreamSubscription`, `Timer`.
- Call `super.dispose()` at the end of `dispose`; call `super.initState()` at the start of `initState`.
- `didUpdateWidget` receives the old widget; compare `oldWidget.field != widget.field` before restarting listeners.

## const Widget usage

- Mark widgets `const` whenever all their arguments are compile-time constants: `const SizedBox(height: 8)`, `const Padding(padding: EdgeInsets.all(16), child: Text('hi'))`.
- `const` widgets are canonicalized; they skip rebuilds entirely, improving performance.
- `const` requires a `const` constructor on the widget class; Flutter widgets like `SizedBox`, `Padding`, `Text`, `Icon` support it.
- A `const` widget nested inside a non-`const` parent still benefits if the subtree is `const`.

## Key usage

- Use stable keys for list items whose identity persists across rebuilds: `ValueKey(item.id)`.
- Do NOT use `UniqueKey()` inside `build` — it forces rebuild every frame.
- Do NOT use array index as key for mutable lists (insert / delete / reorder breaks state).
- `GlobalKey` is for cross-widget state access or reparenting; ensure only one instance is mounted at a time.
- `ValueKey` / `ObjectKey` / `UniqueKey` cover most cases; `PageStorageKey` preserves scroll state across navigations.

## setState rules

- `setState` must be called from `State` after `initState` and before `dispose`.
- `setState` body should only mutate state fields, not run heavy work or async calls; do the work first, then `setState(() { _result = ...; })`.
- Calling `setState` after `dispose` throws; guard with `if (!mounted) return;` after async gaps.
- `setState` during `build` throws `setState() called during build`.

## InheritedWidget / Provider lookups

- `Theme.of(context)`, `MediaQuery.of(context)`, `Provider.of<T>(context)` register a dependency that rebuilds the caller when the inherited value changes.
- Use `context.read<T>()` for one-shot reads inside event handlers (no rebuild registration); `context.watch<T>()` / `Consumer<T>` for reactive rebuilds.
- `Selector<T, S>` narrows the listenable slice — rebuild only when the selected slice changes.

## Async in widgets

- `FutureBuilder` / `StreamBuilder` rebuild on data; do not store the future in a field that changes every build (cache it in `initState` or use a `late final` field).
- Pass a stable `future` instance to `FutureBuilder` to avoid re-running on every rebuild.

```dart
class _MyState extends State<MyWidget> {
  late final Future<String> _data = _loadData();

  Future<String> _loadData() async { /* ... */ }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: _data,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const CircularProgressIndicator();
        if (snapshot.hasError) return Text('Error: ${snapshot.error}');
        return Text(snapshot.data ?? '');
      },
    );
  }
}
```

## Theme and color

- Read colors via `Theme.of(context).colorScheme` and text styles via `Theme.of(context).textTheme`.
- Do not hardcode `Color(0xFF112233)` in widget trees except for one-off decorative constants.
- `CupertinoApp` uses `CupertinoTheme`; `MaterialApp` uses `ThemeData`. Match the app's theme source.

## MediaQuery and layout

- Use `MediaQuery.sizeOf(context)` (Flutter 3.10+) for size-only reads — cheaper than `MediaQuery.of(context)` which rebuilds on any MediaQuery change.
- `LayoutBuilder` gives the parent's `BoxConstraints`; prefer it over `MediaQuery` for responsive child layouts.
- `OrientationBuilder` for portrait/landscape branching.
