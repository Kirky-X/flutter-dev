# Flutter Widget Cookbook

This file keeps high-frequency Flutter patterns close to the skill. Prefer project-local code style, but use these shapes to avoid common API mistakes.

## Row and Column

Use `Row` / `Column` for linear layouts. Set spacing with `SizedBox` or `Spacer`.

```dart
Row(
  children: [
    const Icon(Icons.star),
    const SizedBox(width: 8),
    const Expanded(child: Text('Title')),
    const SizedBox(width: 8),
    IconButton(onPressed: () {}, icon: const Icon(Icons.more)),
  ],
)
```

Key rules:

- `MainAxisAlignment` controls main axis; `CrossAxisAlignment` controls cross axis.
- `Expanded` / `Flexible` wraps children to fill / share remaining space.
- Avoid unbounded `Row` inside horizontal scroll — children need bounded width.

## Stack and Positioned

Use `Stack` for overlay layouts.

```dart
Stack(
  alignment: Alignment.center,
  children: [
    Image.network(url),
    const Positioned(
      bottom: 8,
      left: 8,
      child: Text('Caption'),
    ),
  ],
)
```

Key rules:

- `Positioned` requires `Stack` ancestor; non-positioned children use `alignment`.
- `Stack` sizes to largest non-positioned child unless `sized` / constraints given.

## ListView and GridView

Use `ListView.builder` for long lists; `ListView(children: [...])` for short ones.

```dart
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, index) {
    final item = items[index];
    return ListTile(
      key: ValueKey(item.id),
      title: Text(item.title),
      onTap: () {},
    );
  },
)
```

```dart
GridView.builder(
  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
    crossAxisCount: 2,
    mainAxisSpacing: 8,
    crossAxisSpacing: 8,
    childAspectRatio: 1.0,
  ),
  itemCount: items.length,
  itemBuilder: (context, index) => Card(child: Text(items[index].title)),
)
```

Key rules:

- Always pass a stable `key` (e.g. `ValueKey(item.id)`); never use index as key for mutable lists.
- `ListView.separated` adds dividers; `ListView.custom` accepts a custom delegate.

## CustomScrollView and Slivers

Use `CustomScrollView` for mixed scroll effects; slivers compose headers, lists, grids.

```dart
CustomScrollView(
  slivers: [
    const SliverAppBar(title: Text('Profile'), pinned: true),
    SliverToBoxAdapter(child: profileHeader),
    SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) => ListTile(title: Text(items[index].title)),
        childCount: items.length,
      ),
    ),
    SliverFillRemaining(
      hasScrollBody: false,
      child: footer,
    ),
  ],
)
```

Key rules:

- `SliverAppBar` with `pinned: true` / `floating: true` / `snap: true` for sticky / floating / snap headers.
- `SliverList` + `SliverChildBuilderDelegate` is the lazy equivalent of `ListView.builder`.
- `SliverGrid` / `SliverFixedExtentList` for grid / fixed-height rows.

## StatefulWidget with TextEditingController

```dart
class LoginForm extends StatefulWidget {
  const LoginForm({super.key});
  @override
  State<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<LoginForm> {
  final _controller = TextEditingController();
  String _error = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        TextField(
          controller: _controller,
          decoration: InputDecoration(hintText: 'Username', errorText: _error.isEmpty ? null : _error),
        ),
        ElevatedButton(
          onPressed: () {
            setState(() {
              _error = _controller.text.isEmpty ? 'Required' : '';
            });
          },
          child: const Text('Submit'),
        ),
      ],
    );
  }
}
```

Key rules:

- `TextEditingController` MUST be disposed in `dispose()`.
- Validation messages must render in the widget tree, not only be logged.

## Dialog and SnackBar

```dart
showDialog<void>(
  context: context,
  builder: (context) => AlertDialog(
    title: const Text('Confirm'),
    content: const Text('Delete this item?'),
    actions: [
      TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
      TextButton(
        onPressed: () {
          Navigator.pop(context);
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Deleted')));
        },
        child: const Text('OK'),
      ),
    ],
  ),
);
```

Key rules:

- Use `showDialog` for modals; `ScaffoldMessenger.of(context)` for `SnackBar` (not `Scaffold.of`).
- Capture `context` only if `mounted` is checked after async gaps.

## Navigation

Use the project's existing router; do not introduce a new routing package just for one page.

```dart
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const DetailPage()),
).then((result) {
  if (result == true) {/* refresh */}
});
```

Key rules:

- `Navigator.push` returns a `Future<T?>`; pop with `Navigator.pop(context, true)`.
- For `go_router`, follow the existing route configuration and `context.go` / `context.push`.
