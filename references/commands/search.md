# search 子命令 —— 在线文档搜索

本地 sidebars 匹配 + URL 内容抓取。优先匹配本地 sidebars（快速、离线），命中后可选抓取 URL 正文（HTML→Markdown 清洗）。

> 🔴 **端点来源**：Flutter 文档主域 `docs.flutter.dev` / `api.flutter.dev`；sidebars 列表从 `sidebars/` 目录读。

## 两阶段搜索

| 阶段 | 用途 | 数据源 |
| ---- | ---- | ---- |
| 1. 本地 sidebars 匹配 | 快速定位文档 URL / 标题 | `sidebars/*.md`（已索引到 kb） |
| 2. URL 内容抓取 | 取完整正文 | `docs.flutter.dev` / `api.flutter.dev` / `dart.dev` |

优先走阶段 1（kb 已索引）；需要正文时走阶段 2 抓取 URL。

## sidebar 路由（按查询意图）

| 用户查询意图 | sidebar | 说明 |
| ---- | ---- | ---- |
| Flutter 教程 / 指南 / 步骤 | `flutter-docs.md` | 操作指南、cookbook、教程 |
| Flutter API / Widget / 类 / 方法 | `flutter-api.md` | API 参考 |
| Flutter AI 辅助开发 | `flutter-ai-docs.md` | AI 工具链文档 |
| Dart 语言 / SDK | （调 kb 全库） | `dart.dev` 也可直访 |
| 不确定 / 综合 | 不指定 `--doc-type` | 全库检索 |

## 命令格式

### 本地匹配（经 kb）

```bash
python3 -m scripts.kb.cli query \
  --question "<keyword>" \
  [--doc-type flutter-docs|flutter-api|flutter-ai-docs] \
  [--top-k 5]
```

详见 [`kb.md`](kb.md)。

### URL 内容抓取

```bash
python3 scripts/search/detail.py <object_id> <doc_type>
```

参数：

| 参数 | 必填 | 说明 |
| ---- | ---- | ---- |
| `object_id` | 是 | 文档 URL 末段或 kb 命中的 `id` |
| `doc_type` | 是 | sidebar 类型之一 |

> 🔴 **detail 是 search 子命令的正文获取通道**：`detail.py` 负责 HTML→Markdown 清洗与 anchors 提取，kb 的 description/links 回填都走此通道。

## 输出格式

### kb query 输出

JSON 数组，每项含 `id` / `title` / `url` / `score` / `doc_type` / `description` / `needs_description`。

### detail 输出

```json
{
  "title": "文档标题",
  "object_id": "xxx",
  "doc_type": "flutter-docs",
  "anchors": [{"id": "锚点ID", "title": "章节标题"}],
  "content": "Markdown 格式正文，保留标题/代码块/列表/链接/表格/引用结构"
}
```

`content` 为完整 Markdown 正文，可直接向用户呈现。

## 锚点导航

`detail` 输出含 `anchors` 字段（`[{id, title}]`）。

`detail` 返回的 `content` > 3000 字时，**先** 展示 `anchors` 目录让用户选章节，再按选定锚点截取相关段落。**不** 自动堆全部内容。

| 场景 | 处理 |
| ---- | ---- |
| 用户问特定章节 | 利用 `anchors` 定位，截取相关段落 |
| 内容很长（>3000 字） | 先展示 `anchors` 目录让用户选 |
| 用户需要完整文档 | 直接输出全部 `content` |
| 用户需要代码示例 | 重点展示代码块部分 |

## 错误处理

| 场景 | 现象 | 处理 |
| ---- | ---- | ---- |
| 本地无结果 | kb query 返回空 | agent 层换关键词重试（**最多 2 次**）；建议缩短关键词、换英文术语；仍为 0 转 URL 抓取 |
| URL 详情获取失败 | detail 返回 `error` 字段 | 提示文档可能下线，提供 search 结果中的 `url` 供直接访问 |
| 网络错误 | HTTPError / 连接失败 | **显式报告**，不静默；建议稍后重试 |
| `doc_type` 参数错误 | argparse 校验失败 | 退出码 2；提示合法 doc_type |
| 内容为空 | `content: ""` | 文档可能更新中；提供 `url` 让用户直接查看 |
| `object_id` 不存在 | detail API error | 确认 `object_id` 拼写；或重新 search 获取最新结果 |

> 🔴 **CHECKPOINT**：脚本层**不重试**零结果响应（重试逻辑归 agent 层）。脚本只把错误显式写入 `errors` 字段。

## 工作流

```
1. kb query(keyword, doc_type?) — 本地匹配
   ├─ 命中 → 展示结果列表，询问用户想查看哪个文档
   └─ 无结果 → 换关键词重试（最多 2 次）→ 仍无 → 转 URL 抓取
2. detail(object_id, doc_type) — 抓取 URL 正文
   ├─ content 非空 → 输出 Markdown（长文档先给 anchors 目录）
   └─ content 为空 → 告知用户并提供 url
3. kb 协同（如 needs_description=True）：
   ├─ 回填 description（≤200 字）
   └─ update-links 双向链接
```

文字步骤速查：

1. `kb query(keyword)` 选 doc_type → 2. 展示列表让用户选 → 3. `detail(object_id, doc_type)` 取正文 → 4. 输出 Markdown（长文档先给 anchors 目录）→ 5. kb 协同回填 description + update-links 双向链接。

## 关键词选择策略

- 优先用文档中可能出现的精确术语（如 `ListView`、`SliverAppBar`、`StatefulWidget`）。
- 中英文均可；中文偏指南，英文偏 API 参考。
- Widget 名直接作为关键词（如 `CustomScrollView`）。
- 搜索无结果时：缩短关键词、换英文术语、去掉版本号重试。
- Dart 语言问题可直访 `dart.dev/language`。

## 与 kb 协同

`search detail` 是 `kb` 子命令 `description` 懒填充与链接提取的**唯一合法正文来源**：

- `kb query` 命中 `needs_description=True` 文档 → agent 调 `search detail <object_id> <doc_type>` 取正文 → 生成 ≤200 字 description → `kb update-description` 回填。
- 同一正文 → `kb update-links --id <id> --content "<markdown>"` 提取双向链接。

详见 [`kb.md`](kb.md) 的"懒填充流程"与"update-links"章节。

## 与 fix 协同

`fix` 子命令遇到陌生 `package:` API 或不在 error-fixes 覆盖表内的错误时：

- 调 `search` 在线查官方文档 → 补充修复依据。
- 不要凭模型记忆下结论。

## 边界情形

| 情形 | 处理 |
| ---- | ---- |
| 本地无结果，URL 也抓取失败 | 告知用户；建议直访 `docs.flutter.dev` |
| `--doc-type` 非合法值 | argparse 报错，退出码 2 |
| 用户未指定意图 | 不传 `--doc-type`，全库检索 |
| 结果过多 | 建议用户缩小范围或指定 `--doc-type` |
| `keyword` 为空 | argparse 报错，退出码 2 |
| 网络超时 | 显式 `errors` 上报，不静默 |

## 交付核对清单

### search 流程
- [ ] `keyword` 非空
- [ ] `--doc-type`（若有）属于合法值
- [ ] 本地无结果时 agent 层换关键词重试（最多 2 次），仍无转 URL 抓取
- [ ] 结果展示后**不自动取详情**，等用户选

### detail 流程
- [ ] `object_id` 来自 search 结果（非手动编造）
- [ ] `doc_type` 属于合法值
- [ ] `content` 为空时提供 `url` 让用户直访
- [ ] `content > 3000` 字时先展示 `anchors` 目录

### 与 kb 协同
- [ ] `kb query` 命中 `needs_description=True` 时已调 `search detail` 取正文
- [ ] 取正文后已用 `kb update-description` 回填 + `kb update-links` 提取双向链接

### 错误处理
- [ ] 网络错误 / `errors` 非空时已显式上报，未静默吞错
