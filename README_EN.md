# flutter-dev — Flutter/Dart Application Development Skill

> A Flutter/Dart application development skill for AI agents: create (scaffold a project) → fix (resolve errors) → test (run tests) covers the development lifecycle, with kb (local Qdrant knowledge base) and search (online documentation search) providing knowledge support. Cross-platform across Linux / Windows / macOS; the five subcommand scripts require no MCP.

English | [中文](README.md)

[![GitHub Release](https://img.shields.io/github/v/release/Kirky-X/flutter-dev?style=flat-square)](https://github.com/Kirky-X/flutter-dev/releases)
[![License](https://img.shields.io/github/license/Kirky-X/flutter-dev?style=flat-square)](LICENSE)

## ✨ Features

| Subcommand | Description | Main script |
| ------ | ---- | ------ |
| `create` | Calls `flutter create` via Python subprocess, with project-name/org/platform parameter validation (`--name/--org/--platforms/--force`) | `scripts/create/create_project.py` |
| `fix` | Three symptom-routed tracks: analyzer (`dart analyze` JSON parsing) / runtime (Dart stack-trace parsing) / layout (RenderFlex overflow and other layout diagnostics) | `scripts/fix/{run_analyzer,parse_stack_trace,diagnose_layout}.py` |
| `test` | Platform detection + Flutter/Dart SDK detection + `flutter test` (unit/widget) + integration_test | `scripts/test/{platform,cli}.py` |
| `kb` | Local Qdrant knowledge base, **14 sub-actions** (measured via `--help`): query / build / merge / reindex / update-description / update-links / link-auto / migrate-embed-model / config / fetch-content / update-content / fetch-and-update / migrate-context / refresh-expired | `scripts/kb/` |
| `search` | Local sidebars keyword matching + URL body fetching (docs.flutter.cn / api.flutter-io.cn / pub.dev), HTML→Markdown cleaning | `scripts/search/{_http,search,detail}.py` |

**Knowledge base build**: `data/flutter.qdrant/` (384 dims, collection `flutter_docs`) is a runtime-derived artifact and is **NOT committed** (see `.gitignore`; the repo only ships the `data/flutter.qdrant.meta.json` metadata) — run `python3 scripts/kb/build_db.py` for a full build on first use. The data source, 3 sidebar files (docs / api / ai-docs) under `sidebars/`, ships with the repo.

**config.example.json initialization flow**: `config.json` contains API keys and is not committed. When it is missing, scripts fall back to built-in defaults (with a stderr notice); to customize a cloud model/key, run `cp config.example.json config.json` and edit. When embed_model is the default and the pre-built database exists → use the pre-built database directly, without recomputing vectors.

**Collaboration loop**: when kb query hits a document without a description → `search detail <url>` fetches the body → `kb update-description` fills it in and recomputes vectors; when fix hits an unknown API → search the official docs; test failure → error log → fix-track diagnosis. create output is not considered done until validated by fix/test.

```mermaid
flowchart LR
    create[create<br/>scaffold] --> fix[fix<br/>resolve errors] --> test[test<br/>run tests]
    kb[(kb local knowledge base)] -.-> create
    kb -.-> fix
    kb -.-> test
    search[(search online docs)] -.-> create
    search -.-> fix
    search -.-> test
```

## 📦 Installation

```bash
# First-run prerequisite: Python dependencies for kb / search / test
pip install -r requirements.txt   # qdrant-client / rank-bm25 / httpx / sentence-transformers / modelscope
# Or: remote install (GitHub repo)
npx skills add Kirky-X/flutter-dev --agent claude-code -y
```

create / fix / test additionally require the [Flutter SDK](https://docs.flutter.dev/get-started/install) (Dart included); after installation, verify with `python3 -m scripts.test.cli check`. After changing `embed_model` / `embed_dim`, a full rebuild with `python3 scripts/kb/build_db.py` is mandatory, otherwise a dimension-mismatch error is raised.

## 🚀 Quick Start

All commands assume cwd = the skill root (`python3 -m` needs it to locate the `scripts` package).

```bash
# fix — paste a Dart stack trace to locate the error (measured: NoSuchMethodError resolved to file and line)
python3 -m scripts.fix.parse_stack_trace --log-text "<stack trace text>"   # or --log-file <path>
python3 -m scripts.fix.run_analyzer <project_dir>                  # dart analyze entry for all three tracks
python3 -m scripts.fix.diagnose_layout --log-text "<layout error log>"

# test — environment self-check (measured output fields: platform/enabled_tools/flutter_installed)
python3 -m scripts.test.cli check
python3 -m scripts.test.cli run --project-path <project_dir>       # flutter test
python3 -m scripts.test.cli run --project-path <project_dir> --integration

# kb — local semantic query (on a fresh clone, run python3 scripts/kb/build_db.py first to build the DB)
python3 -m scripts.kb.cli query --question "<keyword>" [--top-k 5] [--doc-type docs|api|ai-docs] [--rerank]

# search — local sidebar matching (measured offline hit: 'Widget lifecycle' → 6 results)
python3 -m scripts.search.search "<keyword>" [--doc-type docs|api|ai-docs] [--top-k 10]
python3 -m scripts.search.detail <url>
```

For the subcommand routing table and trigger words see [SKILL.md](SKILL.md); for each subcommand's complete workflow see `references/commands/{create,fix,test,kb,search}.md`.

## ✅ Tests & Verification

Measured `python3 -m pytest scripts/ -q`: **144 passed** (test files ship with the repo; `FakeEmbedder` derives vectors from Python's built-in `hash()`, deterministic within one process, so the suite runs offline). Also measured passing: `create_project --help`, `fix.parse_stack_trace` parsing a real log, `test.cli check` (honestly reports `flutter_installed: false` when the machine has no Flutter SDK), and local `search` matching.

## 📁 Directory Structure

```
flutter-dev/
├── SKILL.md                    # 5 subcommand routing + failure-mode table + anti-patterns
├── config.example.json         # config template (cp to config.json and edit)
├── requirements.txt            # Python dependencies
├── skill.json                  # skill metadata (version/trigger tags)
├── sidebars/                   # flutter-docs.md / flutter-api.md / flutter-ai-docs.md
├── data/
│   ├── flutter.qdrant/               # Qdrant DB (generated by kb build, not committed)
│   └── flutter.qdrant.meta.json      # DB metadata (doc_count/embed_model, committed)
├── references/
│   ├── commands/               # 5 subcommand workflow docs
│   ├── dev-rules.md            # three categories of mandatory rules: Dart / Flutter API / UI
│   ├── flutter-skills/ dart-skills/ flutter-ui/ grammar/ error-fixes/
└── scripts/
    ├── create/  fix/  test/    # create_project / run_analyzer etc. / platform+cli
    ├── kb/                     # cli.py (14 sub-actions) + build_db.py
    └── search/                 # _http.py + search.py + detail.py
```

## 🔮 Boundaries

- HarmonyOS / ArkTS belongs to **hap-dev**; Element Plus / Vue belongs to **element-dev**; this skill does not trigger for either
- Development rules: code produced by create, the fix analyzer track, and `flutter analyze` must follow [`references/dev-rules.md`](references/dev-rules.md) (three categories of mandatory rules: Dart language / Flutter API / UI)
- No hardcoded model names/paths (always read config.json); vector spaces of different embed_model values are incompatible even at the same dimension — the query/merge/reindex entry points enforce validation and fail loudly on mismatch; bidirectional links must genuinely be written on both sides; errors must never be silently swallowed (non-zero exit code / errors field / exception)

## 📄 License & Attribution

[MIT](LICENSE) © Flutter-DEV Contributors. For the complete failure-mode and fallback table, see [SKILL.md](SKILL.md).
