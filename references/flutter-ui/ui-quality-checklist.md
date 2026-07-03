# Flutter UI Quality Checklist

Use this checklist before finalizing Flutter UI changes.

## Requirement visibility

- Required labels, button text, tab labels, card titles, and dialog text appear on the target screen.
- Text is not hidden by overlays, zero-size containers, off-screen placement, or low contrast.
- The first screen remains reachable from the app launch path.
- Long text wraps or truncates with an explicit `maxLines` and `overflow` (e.g. `TextOverflow.ellipsis`).

## Interaction

- Required buttons use `ElevatedButton` / `TextButton` / `FilledButton` (Material) or `CupertinoButton` when the requirement asks for a button; do not fake clicks on `Text`.
- Click handlers update visible state, switch tabs, open dialogs, navigate, or show the requested response.
- Cancel and close actions do not perform extra business actions.
- Required click targets are at least 48×48 dp and visually clear.
- Disabled buttons visibly differ from enabled ones (`onPressed: null`).

## Layout quality

- New UI follows nearby spacing, color, typography, density, and component style (read `Theme.of` values).
- Layout nesting is only deep enough to express the UI; flatten `Column` / `Row` chains where a single flex layout works.
- Dynamic text, lists, and images have bounded width / height where needed to avoid `RenderFlex overflow`.
- New elements do not overlap existing banners, cards, bottom bars, or system safe areas (`MediaQuery.padding` / `SafeArea`).
- `const` is used wherever the widget tree is compile-time constant.

## State and rendering

- UI-driving state lives in the right owner widget; `setState` is scoped to the smallest subtree that needs to rebuild.
- Lists and grids render stable `ValueKey`s for items whose identity matters.
- Conditional UI still leaves required content reachable; `if` branches do not hide required elements permanently.
- Async results drive UI via `FutureBuilder` / `StreamBuilder` or `setState` after `if (!mounted) return;`.
- Validation errors render in the widget tree (e.g. `InputDecoration.errorText`), not only in logs.

## Lifecycle and resource cleanup

- `AnimationController`, `TextEditingController`, `ScrollController`, `FocusNode`, `PageController`, `TabController`, `StreamSubscription`, `Timer` are disposed in `State.dispose`.
- `super.initState()` is the first call in `initState`; `super.dispose()` is the last call in `dispose`.
- Async work started in `initState` does not `await` directly; it is scheduled via `addPostFrameCallback` or a microtask.
- After every `await` in a `State`, `if (!mounted) return;` is checked before using `context` or `setState`.

## Theme and platform

- Colors come from `Theme.of(context).colorScheme`; text styles from `Theme.of(context).textTheme`; do not hardcode hex colors except for one-off decoration.
- Material 3 is enabled (`useMaterial3: true`) unless the project deliberately pins Material 2.
- Cupertino components are used only when the app targets iOS-style UI; do not mix Material and Cupertino in the same screen unless doing platform adaptation.
- Safe area is respected (`SafeArea` / `MediaQuery.padding`) so content is not clipped by notches or status bars.

## Accessibility

- `Semantics(label: ...)` is set on icons, image-only buttons, and custom interactive widgets.
- Decorative images and containers use `ExcludeSemantics` to avoid noise.
- Tap targets meet the 48×48 dp minimum.
- Text scales with `MediaQuery.textScaleFactor` / `textScaler`; layouts do not break at large font sizes.

## Performance

- Long lists use `ListView.builder` / `GridView.builder`, not `ListView(children: [...])`.
- `Opacity` is avoided in favor of `AnimatedOpacity` / `Visibility` / `Opacity` with `alwaysIncludeSemantics` only when needed.
- Heavy work is not done in `build`; computations are cached or moved out of the build phase.
- `const` widgets are used to skip rebuilds of static subtrees.

## Change scope

- Only files required by the UI task are modified.
- Existing business flow, route configuration, theme, and state-management architecture are preserved.
- No state-management migration, navigation rewrite, or broad refactor is introduced without an explicit request.
- New widgets match the existing naming and folder conventions of nearby code.
