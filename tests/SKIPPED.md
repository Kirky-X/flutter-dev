# flutter-dev 冒烟测试跳过说明

本目录测试全部离线可跑（`python3 -m pytest tests -q`，无网络、不装依赖）。
以下场景依赖真实工具链或外网，按"不写假测试"原则未编写，仅说明原因。
对应逻辑已通过 mock / 纯函数路径覆盖。

## 跳过项

| 脚本 | 跳过场景 | 原因 | 已覆盖的替代路径 |
| --- | --- | --- | --- |
| `scripts/fix/run_analyzer.py` | 真实 `dart analyze --format=json` 调用 | 需安装 Flutter/Dart SDK 并有真实工程 | mock subprocess 覆盖 JSON 解析、severity 分类、退出码 0/1/2/3、工具失败显性化；`dart` 不存在的 FileNotFoundError 用真实路径触发 |
| `scripts/create/create_project.py` | 真实 `flutter create` 工程生成 | 需 Flutter SDK，且会真实创建工程目录 | mock subprocess 覆盖命令拼装、非零退出/超时的 RuntimeError；名称/组织/平台校验与输出目录预检查为纯逻辑真实测试 |
| `scripts/test/platform.py` | 真实 `flutter --version` / `dart --version` 探测 | 需 Flutter SDK 在 PATH | mock 版本命令输出覆盖 Flutter/Dart 版本与 channel 解析、SDK 未安装错误路径 |
| `scripts/test/cli.py` | `run` 动作真实执行 `flutter test` | 需 Flutter SDK 与真实工程 | `--dry-run` 计划生成真实测试；执行路径 mock subprocess 覆盖退出码透传（0/5/127） |
| `scripts/search/detail.py` | 真实 HTTP 抓取 docs.flutter.cn 等页面 | 离线原则，不出网 | `http_get` 用 mock httpx 客户端覆盖成功/HTTP 错误/空 body；SSRF 域名白名单、标题提取、HTML→Markdown 为真实离线路径测试 |
| `scripts/search/search.py` | 对仓内真实 sidebars 全量检索 | 真实 sidebars 内容随上游变动，断言会漂移 | 用临时 sidebars fixture 覆盖打分、过滤、排序、错误显性化与 CLI 退出码 |

## 运行方式

```bash
cd flutter-dev && python3 -m pytest tests -q
```

依赖：仅 Python 3 标准库 + pytest（httpx 需已安装，`scripts/search/_http.py` 导入期依赖；测试内不发真实请求）。
