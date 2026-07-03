# kb 子命令 —— 本地 Qdrant 知识库

本地 Qdrant 知识库，按 sidebar 文档分类存储，向量嵌入 + bm25 关键词索引 + 可选重排。`description` 懒填充 + 向量回填 + 双向链接。

> 🔴 **CHECKPOINT**：所有路径 / 模型名 / 端点都从 `config.json` 读，禁止硬编码。

## 子动作路由表

命令格式：`python3 -m scripts.kb.cli <action> [args]`

| 子动作 | 用途 | 关键参数 |
| ---- | ---- | ---- |
| `query`（默认） | 混合向量+BM25 检索 | `--question` `--top-k` `--doc-type` `--rerank` |
| `build` | 解析 sidebars 构建索引 | `--sidebars-dir` |
| `merge` | 合并两个库为新库 | `--db-a` `--db-b` `--out` |
| `reindex` | 重算向量 | `--force` |
| `update-description` | 回填单文档 description | `--id` `--description` |
| `update-links` | 提取并写入双向链接 | `--id` `--content` |
| `config` | 打印当前生效配置 | （无） |

`--config <path>` 全局可选，覆盖默认 `config.json` 加载路径。

## doc_type 与 sidebar 映射

Flutter sidebars（位于 `sidebars/` 目录）：

| doc_type | sidebar 文件 | 内容 |
| ---- | ---- | ---- |
| `flutter-docs` | `flutter-docs.md` | Flutter 官方文档（指南 / 教程） |
| `flutter-api` | `flutter-api.md` | Flutter API 参考（Widget / 类 / 方法） |
| `flutter-ai-docs` | `flutter-ai-docs.md` | Flutter AI 辅助开发文档 |

`query --doc-type` 只接受上述类型之一；不指定则全库检索。

## config.json 字段说明

| 字段 | 默认值 | 说明 |
| ---- | ---- | ---- |
| `embed_model` | 嵌入模型名 | `openai://` 前缀走云端 |
| `embed_dim` | 嵌入维度 | 必须与模型匹配 |
| `embed_source` | `modelscope` / `local` / `openai` | 模型来源 |
| `rerank_model` | 重排模型；`none` 禁用 | |
| `db_path` | Qdrant 本地存储路径 | |
| `collection` | 集合名 | |
| `sidebars_dir` | `sidebars` | sidebar 源目录 |
| `query.default_top_k` | `5` | `query` 默认 top-k |

## 主要流程

### 1. query（默认子动作）

```bash
python3 -m scripts.kb.cli query \
  --question "如何在 Flutter 里实现一个登录页" \
  [--top-k 5] \
  [--doc-type flutter-docs] \
  [--rerank]
```

未传 `--top-k` → 用 `config.json` 的 `query.default_top_k`（默认 5）。

输出 JSON 数组，每项含 `id` / `title` / `url` / `score` / `doc_type` / `description` / `needs_description` 等字段。

#### 命中 `needs_description=True` → 触发懒填充

`description` 字段为空或为 "无描述" 时，`needs_description=True`。agent **MUST** 执行懒填充：

1. 从命中文档取 `id`（即 `object_id`）与 `doc_type`。
2. 调 `search detail` 取正文：
   ```bash
   python3 scripts/search/detail.py <object_id> <doc_type>
   ```
3. agent 基于正文生成 **≤200 字** description。
4. 回填并重算向量：
   ```bash
   python3 -m scripts.kb.cli update-description \
     --id <id> \
     --description "<不超 200 字的描述>"
   ```
5. 触发链接提取流程（见下文）。

### 2. update-links（双向链接提取）

```bash
python3 -m scripts.kb.cli update-links \
  --id <id> \
  --content "<markdown 正文>"
```

`--content` 也支持传文件路径（脚本检测到路径存在则读文件）。

脚本行为：

- 解析正文中的"相关推荐"区块。
- 把推荐链接的 URL → id 映射。
- **双向写入**：A 文档的 `related_ids` 加 B，B 文档的 `related_ids` 也加 A。

> 🔴 **CHECKPOINT**：双向链接必须真正双向写入；不允许只写单向。

### 3. build（构建索引）

```bash
python3 -m scripts.kb.cli build [--sidebars-dir <dir>]
```

脚本：解析 sidebar 文件 → 生成文档记录 → 嵌入 → 写入 Qdrant。输出 `{built, counts}`。

### 4. reindex（重算向量）

```bash
python3 -m scripts.kb.cli reindex [--force]
```

不带 `--force` → 仅对 `content_hash` 与 `title+url+doc_type` 不一致的文档重算。
带 `--force` → 全量重算所有文档向量。

### 5. merge（合并两个库）

```bash
python3 -m scripts.kb.cli merge \
  --db-a <pathA> \
  --db-b <pathB> \
  --out <new_path>
```

脚本行为：

1. 创建新库 `<new_path>`。
2. 把 A、B 两个旧库改名为 `<old>.bak.<timestamp>`（备份）。
3. 字段级 `updated_at` 比较：同一文档（按 `id`）取 `updated_at` 较新的一方。
4. 输出 JSON `{merged, needs_reindex_count, ...}`。
5. `needs_reindex_count > 0` → 脚本在 stderr 提示在新库跑 `reindex --force`。

### 6. update-description（单文档 description 回填）

```bash
python3 -m scripts.kb.cli update-description \
  --id <id> \
  --description "<不超 200 字>"
```

脚本：写入 description → 重算该文档向量 → 更新 `updated_at`。输出 `{updated: <id>}`。

### 7. config（打印生效配置）

```bash
python3 -m scripts.kb.cli config
```

## Flutter references 协同

查询 Flutter 问题（widget / 布局 / 状态管理 / Dart 代码）时，**同时**参考 `references/`：

| 文件 | 用途 |
| ---- | ---- |
| `references/flutter-ui/widget-cookbook.md` | Widget cookbook |
| `references/flutter-ui/api-guardrails.md` | API 使用护栏 |
| `references/flutter-ui/common-mistakes.md` | 常见错误 |
| `references/flutter-ui/ui-quality-checklist.md` | UI 质量检查清单 |
| `references/grammar/dart-syntax.md` | Dart 语法 |
| `references/dev-rules.md` | 开发规则 |

`kb query` 命中 Flutter 主题文档后，agent 应**同时**查阅上述 references，避免给出与项目风格冲突的建议。

## 失败模式与 fallback

| 触发条件 | 一线修复 | 兜底 |
| ---- | ---- | ---- |
| `config.json` 缺失 | agent 经 `AskUserQuestion` 询问，选默认则生成默认配置 | 用户拒绝则停止 |
| 预构建库不存在 | 调 `kb build` 从 `sidebars/` 重建 | `sidebars/` 缺失则提示用户 |
| `kb query` 无结果 | 换关键词或调 `search` 在线搜索 | `search` 也无结果则建议直访 `docs.flutter.dev` |
| 模型下载失败 | 重试 + 镜像源配置 | 提示用户手动下载或切云端模型 |

## 边界情形

| 情形 | 处理 |
| ---- | ---- |
| `--doc-type` 非合法值 | argparse 校验失败，退出码 2；提示合法值 |
| `query` 命中但 `needs_description=True` | 必须执行 description 懒填充流程；不填充算违规 |
| `update-links` 仅单向写 | 禁止；脚本必须双向写 `related_ids` |
| `merge` 后 `needs_reindex_count > 0` | 在新库跑 `reindex --force` 刷新向量 |
| 切换模型后维度不匹配 | 同步改 `embed_dim`，再 `reindex --force` |

## 交付核对清单

### query 流程
- [ ] `--question` 已传；`--doc-type`（如有）属于合法值
- [ ] 命中 `needs_description=True` 文档时已执行懒填充（取正文 → 生成 ≤200 字 → update-description）
- [ ] 懒填充后已执行 update-links 双向链接
- [ ] Flutter 主题查询同时参考了 `references/`

### build / reindex 流程
- [ ] `sidebars_dir` 来自 `config.json` 或 `--sidebars-dir`，未硬编码
- [ ] 切换模型后已 `reindex --force` 全量重算
- [ ] 维度 `embed_dim` 与新模型匹配

### merge 流程
- [ ] `--db-a` `--db-b` `--out` 三参数齐全
- [ ] 旧库已自动备份为 `.bak.<timestamp>`
- [ ] `needs_reindex_count > 0` 时已在新库跑 `reindex --force`
