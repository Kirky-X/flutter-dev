# create 子命令 —— 创建 Flutter 工程

经 `flutter create` 命令创建 Flutter 工程脚手架：项目名规则校验 + 平台选择 + 组织名 + pubspec 初始化 + 平台目录生成。

> 🔴 **CHECKPOINT**：脚本依赖 `flutter` CLI。若环境无 `flutter`（`flutter --version` 不可用），立即停止并向用户说明无法执行；不要退化为"模型逐文件复制"模式。

## 必填参数

执行前必须确认下表参数。缺值时经 `AskUserQuestion` 向用户询问，禁止 agent 凭空捏造：

| 参数 | 必填 | 默认 | 示例 |
| ---- | ---- | ---- | ---- |
| `projectPath` | 是 | — | `/Users/yellow/Desktop/projects` |
| `projectName` | 是 | — | `hello_world` |
| `orgName` | 否 | `com.example` | `com.yellow.app` |
| `platforms` | 否 | 全平台 `ios,android,web,macos,windows,linux` | `ios,android` |

### projectName 规则

`projectName` 必须匹配 `^[a-z][a-z0-9_]*$`（snake_case，全小写）。**大写 / 中文 / 非 ASCII 名一律拒绝**——`flutter create` 自身会报错。

当用户提供大写或非 ASCII 名时，agent **MUST**：

1. 按含义给出 2-3 个 snake_case ASCII 候选（例：`购物车` → `shopping_cart` / `shop_cart` / `cart`；`天气预报` → `weather_forecast` / `weather` / `forecast`）。
2. 经 `AskUserQuestion` 让用户选择，**禁止 agent 代为决定**。
3. 永不将原始非 ASCII 名传给 `flutter create`。

### 目录冲突

若 `{projectPath}/{projectName}` 已存在且非空，`flutter create` 会报错或要求 `--project-name`。看到此错误时，经 `AskUserQuestion` 询问用户是否覆盖、改名或取消——**禁止 agent 自行删除目录或静默重跑**。

### 平台选择

- 默认全平台（Flutter 3.x 支持 ios / android / web / macos / windows / linux）。
- 用户明确只要部分平台时，用 `--platforms=ios,android` 限定。
- 不要凭模型猜平台；用户未指定就用默认全平台或 `--platforms=all`。

## 执行流程（5 步）

### Step 1：确认环境

```bash
flutter --version
```

`flutter` 不在 PATH → 立即停止，告知用户安装 Flutter SDK 后重试。**不**退化为手动创建文件。

### Step 2：运行 flutter create

```bash
cd "{projectPath}" && \
flutter create \
  --project-name "{projectName}" \
  --org "{orgName}" \
  --platforms "{platforms}" \
  "{projectName}"
```

用户未指定 `--org` / `--platforms` 时可省略对应参数，让 `flutter create` 用默认值。

执行约束：

- 不手动逐文件创建模板。
- 递归复制、平台目录生成、pubspec 初始化全部由 `flutter create` 完成。
- 脚本非零退出码 → 向用户报告错误并停止，不继续后续步骤。

### Step 3：验证结果

至少验证下列文件存在：

- `{projectPath}/{projectName}/pubspec.yaml`
- `{projectPath}/{projectName}/lib/main.dart`

文件缺失 → 视为创建失败，**不**进入后续编译或页面生成步骤。

### Step 4：切换会话工程上下文（必做）

创建成功后调用 `switch_cwd`，目标路径为生成的工程根 `{projectPath}/{projectName}`。

理由：

- `flutter run` / `flutter test` 只有在当前会话上下文目录为真实工程根时才正确工作。
- 本子命令在当前路径下生成完整工程；不切换上下文则后续 build/run 可能失败或落到错误目录。

`switch_cwd` 失败 → 报告上下文切换失败并停止，**不**进入特性实现 / `flutter run` / `flutter test`。

### Step 5：在生成工程内继续特性工作

仅当用户在创建请求之外还提了应用行为 / UI / 页面 / 业务需求时执行，且必须 `switch_cwd` 成功之后。

实现前：

- 读 `{projectPath}/{projectName}/lib/main.dart` 确认入口。
- 默认入口是 `main.dart` 的 `void main() => runApp(MyApp());`。
- 修改 `MyApp` 或新增页面，确保所求特性从首屏可达。

特性实现完毕后运行 `flutter analyze` + `flutter run`；成功后再交付。

### Step 6：向用户回报

所有请求的创建 / 实现 / 编译 / 运行 / 验证工作完成，或遇到阻塞失败立即回报。

回报内容：

- 工程绝对路径
- projectName / orgName / platforms
- `flutter create` 退出状态
- `switch_cwd` 是否成功
- 有特性工作时，analyze / run / 验证状态

## 边界情形

| 情形 | 处理 |
| ---- | ---- |
| 环境 `flutter` 不可用 | 立即停止并告知用户；不退化为模型逐文件复制 |
| `projectName` 含大写 / 非 ASCII | 经 `AskUserQuestion` 提 2-3 snake_case 候选，用户选后再调 `flutter create` |
| 目标目录已存在非空 | `flutter create` 报错；经 `AskUserQuestion` 询问覆盖 / 改名 / 取消 |
| `pubspec.yaml` / `lib/main.dart` 缺失 | 视为创建失败，停止后续步骤 |
| `switch_cwd` 失败 | 停止，不进入特性实现 / run / test |
| 用户指定不支持的 `--platforms` | `flutter create` 报错；提示合法平台列表 |
| 用户已批准 Plan | 不要新建 plan、不要 `plan_enter` / `plan_write`、不要再次请求批准；以现有 plan 为准 |

## 交付核对清单

- [ ] 必填参数齐全；`projectName` 通过正则；非 ASCII 名已经用户从候选中选定
- [ ] `flutter create` 以正确参数运行，退出码 0
- [ ] `{projectPath}/{projectName}/pubspec.yaml` 与 `lib/main.dart` 存在
- [ ] `switch_cwd` 成功切到工程根
- [ ] （有特性工作时）`flutter analyze` 通过；`flutter run` 启动成功
- [ ] 回报包含路径 / projectName / orgName / platforms / `switch_cwd` 状态 / analyze+run 状态
