# create subcommand — Create Flutter project

Creates Flutter project scaffolding via the `flutter create` command: project name validation + platform selection + organization name + pubspec initialization + platform directory generation.

> 🔴 **CHECKPOINT**: This script depends on the `flutter` CLI. If `flutter` is unavailable in the environment (`flutter --version` fails), stop immediately and inform the user that execution is not possible; do not degrade to a "model copies files one by one" mode.

## Required parameters

The following parameters must be confirmed before execution. When values are missing, ask the user via `AskUserQuestion`; the agent must not fabricate values:

| Parameter | Required | Default | Example |
| ---- | ---- | ---- | ---- |
| `projectPath` | Yes | — | `/Users/yellow/Desktop/projects` |
| `projectName` | Yes | — | `hello_world` |
| `orgName` | No | `com.example` | `com.yellow.app` |
| `platforms` | No | All platforms `ios,android,web,macos,windows,linux` | `ios,android` |

### projectName rules

`projectName` must match `^[a-z][a-z0-9_]*$` (snake_case, all lowercase). **Uppercase / Chinese / non-ASCII names are all rejected** — `flutter create` itself will error.

When user provides an uppercase or non-ASCII name, the agent **MUST**:

1. Provide 2-3 snake_case ASCII candidates based on meaning (e.g., `购物车` → `shopping_cart` / `shop_cart` / `cart`; `天气预报` → `weather_forecast` / `weather` / `forecast`).
2. Use `AskUserQuestion` to let user select; **the agent must not decide on their behalf**.
3. Never pass the original non-ASCII name to `flutter create`.

### Directory conflict

If `{projectPath}/{projectName}` already exists and is non-empty, `flutter create` will error or require `--project-name`. When this error is seen, use `AskUserQuestion` to ask user whether to overwrite, rename, or cancel — **the agent must not delete the directory or silently re-run on their own**.

### Platform selection

- Default is all platforms (Flutter 3.x supports ios / android / web / macos / windows / linux).
- When user explicitly wants only certain platforms, use `--platforms=ios,android` to limit.
- Do not guess platforms based on model; if user has not specified, use default all platforms or `--platforms=all`.

## Execution flow (6 steps)

### Step 1: Confirm environment

```bash
flutter --version
```

`flutter` not in PATH → stop immediately, inform user to install Flutter SDK and retry. **Do not** degrade to manually creating files.

### Step 2: Run flutter create

```bash
cd "{projectPath}" && \
flutter create \
  --project-name "{projectName}" \
  --org "{orgName}" \
  --platforms "{platforms}" \
  "{projectName}"
```

When user has not specified `--org` / `--platforms`, omit the corresponding parameters and let `flutter create` use defaults.

Execution constraints:

- Do not manually create template files one by one.
- Recursive copy, platform directory generation, and pubspec initialization are all handled by `flutter create`.
- Non-zero exit code from script → report error to user and stop, do not continue to subsequent steps.

### Step 3: Verify results

Verify at least the following files exist:

- `{projectPath}/{projectName}/pubspec.yaml`
- `{projectPath}/{projectName}/lib/main.dart`

Missing files → treat as creation failure, **do not** proceed to subsequent compilation or page generation steps.

### Step 4: Switch session project context (mandatory)

After successful creation, call `switch_cwd` with the target path set to the generated project root `{projectPath}/{projectName}`.

Rationale:

- `flutter run` / `flutter test` only work correctly when the current session context directory is the real project root.
- This subcommand generates a complete project under the current path; without switching context, subsequent build/run may fail or operate in the wrong directory.

`switch_cwd` failure → report context switch failure and stop, **do not** proceed to feature implementation / `flutter run` / `flutter test`.

### Step 5: Continue feature work in the generated project

Only execute when user has provided application behavior / UI / page / business requirements beyond the creation request, and only after `switch_cwd` succeeds.

Before implementing:

- Read `{projectPath}/{projectName}/lib/main.dart` to confirm the entry point.
- Default entry point is `void main() => runApp(MyApp());` in `main.dart`.
- Modify `MyApp` or add new pages, ensuring requested features are reachable from the first screen.

After feature implementation, run `flutter analyze` + `flutter run`; deliver only after success.

### Step 6: Report to user

All requested creation / implementation / compilation / run / verification work is complete, or report immediately upon encountering a blocking failure.

Report contents:

- Absolute path of the project
- projectName / orgName / platforms
- `flutter create` exit status
- Whether `switch_cwd` succeeded
- When feature work was done: analyze / run / verification status

## Edge cases

| Scenario | Handling |
| ---- | ---- |
| `flutter` unavailable in environment | Stop immediately and inform user; do not degrade to model copying files one by one |
| `projectName` contains uppercase / non-ASCII | Use `AskUserQuestion` to propose 2-3 snake_case candidates; call `flutter create` after user selects |
| Target directory already exists and is non-empty | `flutter create` errors; use `AskUserQuestion` to ask user to overwrite / rename / cancel |
| `pubspec.yaml` / `lib/main.dart` missing | Treat as creation failure, stop subsequent steps |
| `switch_cwd` fails | Stop, do not proceed to feature implementation / run / test |
| User specifies unsupported `--platforms` | `flutter create` errors; indicate valid platform list |
| User has already approved Plan | Do not create new plan, do not `plan_enter` / `plan_write`, do not request approval again; proceed with existing plan |

## Delivery checklist

- [ ] Required parameters complete; `projectName` passes regex; non-ASCII name selected by user from candidates
- [ ] `flutter create` runs with correct parameters, exit code 0
- [ ] `{projectPath}/{projectName}/pubspec.yaml` and `lib/main.dart` exist
- [ ] `switch_cwd` successfully switches to project root
- [ ] (When feature work exists) `flutter analyze` passes; `flutter run` starts successfully
- [ ] Report includes path / projectName / orgName / platforms / `switch_cwd` status / analyze+run status
