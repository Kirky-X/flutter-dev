# fix subcommand — Error fixing (symptom routing + three tracks)

Routes user symptoms to one of three fix tracks: analyzer errors (analyzer-errors) / runtime crashes (runtime-errors) / layout issues (layout-errors). **First route by symptom table to select a track, then enter the track to execute**.

> 🔴 **CHECKPOINT**: When symptoms are ambiguous, fall back in the order of **analyzer → runtime → layout**. Do not pick a track based on model intuition.

## Symptom routing table

| User symptom | Route track | Entry |
| ---- | ---- | ---- |
| Has `flutter analyze` / compilation failure logs or type errors, **no** runtime crash | analyzer | [`references/error-fixes/analyzer-errors.md`](../error-fixes/analyzer-errors.md) |
| Has runtime crash stack / exception / crash-to-desktop, **or** build succeeds but crashes on run | runtime | [`references/error-fixes/runtime-errors.md`](../error-fixes/runtime-errors.md) + [`null-safety-errors.md`](../error-fixes/null-safety-errors.md) |
| Has RenderFlex overflow / yellow-black stripes / layout assertions / missing ancestor | layout | [`references/error-fixes/layout-errors.md`](../error-fixes/layout-errors.md) |
| Pure syntax inquiry / TS→Dart differences / "is certain syntax allowed" | grammar | [`references/grammar/`](../grammar/) |
| `flutter build` fails (Gradle / Xcode / CocoaPods / pub) | build | [`references/error-fixes/build-errors.md`](../error-fixes/build-errors.md) |
| Symptom unclear | fallback: analyzer → runtime → layout | See "Ambiguous symptom handling" below |

### Ambiguous symptom handling

Try in order of `analyzer → runtime → layout`: compilation / type error signals (`error:`, `A value of type 'X'`, `The method 'foo' isn't defined`) → analyzer; runtime crash signals (`NoSuchMethodError`, `TypeError`, `LateInitializationError`, crash-to-desktop, build succeeds but crashes) → runtime; layout assertion signals (`RenderFlex overflowed`, `No Material widget found`, yellow-black stripes) → layout; still unclear → use `AskUserQuestion` to ask user for more specific symptoms; do not force guess.

---

## Track one: analyzer (compilation / type errors)

Applicable: `flutter analyze` errors, type mismatches, compilation failures. **No** runtime crash evidence.

### Execution flow

1. Collect original analyzer error text (from user or `flutter analyze` output).
2. Extract error keywords (type names, API names, error codes from the error message), cross-reference [`analyzer-errors.md`](../error-fixes/analyzer-errors.md) to locate the category.
3. Apply minimal fix following the "Fix" direction, **do not refactor unrelated code**.
4. After modification, run `flutter analyze` to verify; if errors persist, return to step 2 to re-locate.
5. After `flutter analyze` passes, if there are runtime suspicions, suggest running `flutter run` or `flutter test` to verify.

### Edge cases

| Scenario | Handling |
| ---- | ---- |
| Error not covered in analyzer-errors.md | Call `search` subcommand to look up official documentation online; if not found, fall back to grammar track to review syntax |
| Error spans multiple categories | Fix category by category, fix the earliest-reported error first; re-run `flutter analyze` after each fix |
| Involves unfamiliar `package:` API | Call `search` to look up API constraints, **do not** modify blindly based on model memory |

---

## Track two: runtime (runtime crashes / exceptions)

Applicable: Runtime exceptions, crash-to-desktop, build succeeds but crashes on run.

> 🔴 **Core constraint**: Before obtaining a specific crash anchor, **do not** perform large-scale `Read` / `Glob` / `Explore` on the project. Anchors include exception type / exception message / filename / top stack frame or user-identified crash page / module.

### Collecting crash evidence

**Case A: User has provided raw exception text**

Parse exception type + message + top stack frame directly, locate to specific file / line.

**Case B: User provided log file path**

Read the log, extract the first application stack frame (`.dart` file path + line number) as the starting point.

**Case C: User only describes symptoms, no logs**

- Request user to reproduce and collect logs: console output during `flutter run`, or `flutter logs` to capture device logs.
- When multiple devices are connected, use `AskUserQuestion` to let user select a device.
- 0 devices → report inability to collect device evidence, request user to provide local crash logs.

### Common runtime error characteristics

| Exception type | Typical cause | First-line fix direction |
| ---- | ---- | ---- |
| `NoSuchMethodError` | Calling non-existent method on null / dynamic | null guard, typed model, fix API call |
| `TypeError` (`type 'X' is not a subtype`) | `as` cast failure, `List<dynamic>` used as `List<T>` | Use `is` check, element-level cast, switch to typed model |
| `LateInitializationError` | `late` field read before assignment | Change to `T?` + null check, or ensure `initState` assigns first |
| `Null check operator used on a null value` | `!` used on null | Change to `??` default or explicit null check |
| `StackOverflowError` | Unbounded recursion / build calls build | Add recursion base case, break rebuild loop |
| `StateError` | Lifecycle mismatch (e.g., Completer completed twice) | Add state guard, move to correct lifecycle |
| `RangeError` | Array out of bounds / illegal range | Add boundary check, use `elementAtOrNull` |

### Interpretation rules

- Prioritize application stack frames (`.dart` files), filter framework noise; the first concrete `.dart` path is used as the starting point, **not** as the final conclusion.
- User provided reproduction steps → trust user steps over pure stack guessing; stack points to non-entry page → assume interaction trigger.
- **Do not** do large-scale refactoring; fix the crash path first.

### Constraints

- **Do not** claim a crash is fixed based solely on prompt reasoning.
- **Do not** use try/catch to swallow errors as a substitute for root cause fixing.
- Involves unfamiliar `package:` API → look up constraints before modifying.
- This subcommand **does not** determine the final compile / run / verification order — that is the `test` subcommand's responsibility.

---

## Track three: layout (layout issues)

Applicable: RenderFlex overflow, unbounded constraints, missing ancestor, setState during build, and other layout assertions.

### Execution flow

1. Read the assertion message — it will identify the violating widget and axis (`on the right` = horizontal overflow).
2. Cross-reference [`layout-errors.md`](../error-fixes/layout-errors.md) to locate the error category.
3. Apply minimal fix (`Expanded` / `SizedBox` / `Material` wrapping / `Directionality` etc.).
4. Re-run `flutter run` to verify yellow-black stripes have disappeared.

### Edge cases

| Scenario | Handling |
| ---- | ---- |
| Assertion message does not clearly identify widget | Locate the build call chain from stack frames; find the nearest `Flex` / `Viewport` |
| Overflow persists after fix | Check parent constraint chain; may need multiple levels of `Expanded` / `ConstrainedBox` |
| `setState during build` | Use `addPostFrameCallback` to defer state changes |

---

## Cross-track collaboration

| Scenario | Collaboration |
| ---- | ---- |
| analyzer encounters unfamiliar `package:` API error | Call `search` subcommand to look up official documentation online |
| runtime involves unknown API constraints | Call `search` subcommand to look up online |
| layout fix still results in runtime crash | Route to runtime track |
| test subcommand encounters runtime crash | Feed test output stack → to runtime track |
| grammar unsure about certain restriction | Check [`restrictions.md`](../grammar/restrictions.md); if still unsure, call `search` |

## Delivery checklist

### analyzer track
- [ ] Original analyzer error text collected; error category located within `analyzer-errors.md` (or confirmed outside the table and search called)
- [ ] Fix is minimal, no refactoring of unrelated code; `flutter analyze` passes after fix

### runtime track
- [ ] Directed code reading only begins after obtaining a specific exception anchor; no large-scale code reading without anchor
- [ ] `flutter run` or `flutter test` run to verify after fix

### layout track
- [ ] Assertion message read; error category located
- [ ] `flutter run` verifies overflow / assertion disappears after fix
