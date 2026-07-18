# kb subcommand — Local Qdrant knowledge base

Local Qdrant knowledge base, stored by sidebar document categories, with vector embeddings + bm25 keyword indexing + optional reranking. `description` lazy filling + vector backfill + bidirectional links.

> 🔴 **CHECKPOINT**: All paths / model names / endpoints are read from `config.json`; hardcoding is prohibited.

## Sub-action routing table

Command format: `python3 -m scripts.kb.cli <action> [args]`

| Sub-action | Purpose | Key parameters |
| ---- | ---- | ---- |
| `query` (default) | Hybrid vector+BM25 retrieval | `--question` `--top-k` `--doc-type` `--rerank` |
| `build` | Parse sidebars and build index | `--sidebars-dir` |
| `merge` | Merge two databases into a new one | `--db-a` `--db-b` `--out` |
| `reindex` | Recompute vectors | `--force` |
| `update-description` | Backfill single document description | `--id` `--description` |
| `update-links` | Extract and write bidirectional links | `--id` `--content` |
| `config` | Print currently active configuration | (none) |

`--config <path>` is globally optional, overriding the default `config.json` load path.

## doc_type and sidebar mapping

Flutter sidebars (located in `sidebars/` directory):

| doc_type | sidebar file | Content |
| ---- | ---- | ---- |
| `flutter-docs` | `flutter-docs.md` | Flutter official documentation (guides / tutorials) |
| `flutter-api` | `flutter-api.md` | Flutter API reference (Widget / class / method) |
| `flutter-ai-docs` | `flutter-ai-docs.md` | Flutter AI-assisted development documentation |

`query --doc-type` only accepts one of the above types; if not specified, searches the full library.

## config.json field descriptions

| Field | Default | Description |
| ---- | ---- | ---- |
| `embed_model` | Embedding model name | `openai://` prefix uses cloud |
| `embed_dim` | Embedding dimension | Must match the model |
| `embed_source` | `modelscope` / `local` / `openai` | Model source |
| `rerank_model` | Reranking model; `none` disables | |
| `db_path` | Qdrant local storage path | |
| `collection` | Collection name | |
| `sidebars_dir` | `sidebars` | Sidebar source directory |
| `query.default_top_k` | `5` | Default top-k for `query` |

## Main workflows

### 1. query (default sub-action)

```bash
python3 -m scripts.kb.cli query \
  --question "How to implement a login page in Flutter" \
  [--top-k 5] \
  [--doc-type flutter-docs] \
  [--rerank]
```

When `--top-k` is not provided, uses `config.json`'s `query.default_top_k` (default 5).

Outputs a JSON array, each item containing `id` / `title` / `url` / `score` / `doc_type` / `description` / `needs_description` and other fields.

#### Hit `needs_description=True` → triggers lazy filling

When the `description` field is empty or "无描述", `needs_description=True`. The agent **MUST** execute lazy filling:

1. Retrieve `id` (i.e., `object_id`) and `doc_type` from the matched document.
2. Call `search detail` to fetch body content:
   ```bash
   python3 scripts/search/detail.py <object_id> <doc_type>
   ```
3. Agent generates a **≤200 character** description based on the body content.
4. Backfill and recompute vector:
   ```bash
   python3 -m scripts.kb.cli update-description \
     --id <id> \
     --description "<description no more than 200 characters>"
   ```
5. Trigger the link extraction workflow (see below).

### 2. update-links (bidirectional link extraction)

```bash
python3 -m scripts.kb.cli update-links \
  --id <id> \
  --content "<markdown body>"
```

`--content` also accepts a file path (the script reads the file if the path exists).

Script behavior:

- Parses the "Related recommendations" block in the body content.
- Maps recommended link URLs → ids.
- **Bidirectional write**: Document A's `related_ids` adds B, and document B's `related_ids` also adds A.

> 🔴 **CHECKPOINT**: Bidirectional links must be truly written in both directions; single-direction writes are not permitted.

### 3. build (build index)

```bash
python3 -m scripts.kb.cli build [--sidebars-dir <dir>]
```

Script: Parses sidebar files → generates document records → embeds → writes to Qdrant. Outputs `{built, counts}`.

### 4. reindex (recompute vectors)

```bash
python3 -m scripts.kb.cli reindex [--force]
```

Without `--force` → only recomputes documents where `content_hash` and `title+url+doc_type` are inconsistent.
With `--force` → full recomputation of all document vectors.

### 5. merge (merge two databases)

```bash
python3 -m scripts.kb.cli merge \
  --db-a <pathA> \
  --db-b <pathB> \
  --out <new_path>
```

Script behavior:

1. Creates a new database at `<new_path>`.
2. Renames both old databases A and B to `<old>.bak.<timestamp>` (backup).
3. Field-level `updated_at` comparison: for the same document (by `id`), takes the one with the newer `updated_at`.
4. Outputs JSON `{merged, needs_reindex_count, ...}`.
5. When `needs_reindex_count > 0` → script prompts on stderr to run `reindex --force` on the new database.

### 6. update-description (single document description backfill)

```bash
python3 -m scripts.kb.cli update-description \
  --id <id> \
  --description "<no more than 200 characters>"
```

Script: Writes description → recomputes the document vector → updates `updated_at`. Outputs `{updated: <id>}`.

### 7. config (print active configuration)

```bash
python3 -m scripts.kb.cli config
```

## Flutter references collaboration

When querying Flutter issues (widget / layout / state management / Dart code), **also** consult `references/`:

| File | Purpose |
| ---- | ---- |
| `references/flutter-ui/widget-cookbook.md` | Widget cookbook |
| `references/flutter-ui/api-guardrails.md` | API usage guardrails |
| `references/flutter-ui/common-mistakes.md` | Common mistakes |
| `references/flutter-ui/ui-quality-checklist.md` | UI quality checklist |
| `references/grammar/dart-syntax.md` | Dart syntax |
| `references/dev-rules.md` | Development rules |

After `kb query` hits Flutter topic documents, the agent should **also** consult the above references to avoid giving suggestions that conflict with project style.

## Failure modes and fallbacks

| Trigger condition | First-line fix | Fallback |
| ---- | ---- | ---- |
| `config.json` missing | Agent asks via `AskUserQuestion`; if user selects default, generate default config | If user declines, stop |
| Pre-built database does not exist | Call `kb build` to rebuild from `sidebars/` | If `sidebars/` is missing, prompt user |
| `kb query` returns no results | Change keywords or call `search` for online search | If `search` also returns no results, suggest visiting `docs.flutter.dev` directly |
| Model download fails | Retry + mirror source configuration | Prompt user to download manually or switch to cloud model |

## Edge cases

| Scenario | Handling |
| ---- | ---- |
| `--doc-type` is not a valid value | argparse validation fails, exit code 2; indicate valid values |
| `query` hits but `needs_description=True` | Must execute description lazy filling workflow; not filling is a violation |
| `update-links` only writes one direction | Prohibited; script must bidirectionally write `related_ids` |
| After `merge`, `needs_reindex_count > 0` | Run `reindex --force` on new database to refresh vectors |
| Dimension mismatch after switching models | Update `embed_dim` accordingly, then `reindex --force` |

## Delivery checklist

### query workflow
- [ ] `--question` provided; `--doc-type` (if any) is a valid value
- [ ] When hitting `needs_description=True` documents, lazy filling executed (fetch body → generate ≤200 chars → update-description)
- [ ] After lazy filling, update-links bidirectional linking executed
- [ ] Flutter topic queries also consulted `references/`

### build / reindex workflow
- [ ] `sidebars_dir` comes from `config.json` or `--sidebars-dir`, not hardcoded
- [ ] After switching models, `reindex --force` full recomputation performed
- [ ] `embed_dim` matches the new model

### merge workflow
- [ ] `--db-a` `--db-b` `--out` all three parameters present
- [ ] Old databases automatically backed up as `.bak.<timestamp>`
- [ ] When `needs_reindex_count > 0`, `reindex --force` run on new database
