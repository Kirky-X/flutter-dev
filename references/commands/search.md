# search subcommand — Online documentation search

Local sidebars matching + URL content fetching. Prioritizes matching local sidebars (fast, offline), and optionally fetches URL body (HTML→Markdown cleanup) upon hit.

> 🔴 **Endpoint source**: Flutter documentation main domain `docs.flutter.dev` / `api.flutter.dev`; sidebars list read from `sidebars/` directory.

## Two-phase search

| Phase | Purpose | Data source |
| ---- | ---- | ---- |
| 1. Local sidebars matching | Quickly locate document URL / title | `sidebars/*.md` (already indexed into kb) |
| 2. URL content fetching | Retrieve full body content | `docs.flutter.dev` / `api.flutter.dev` / `dart.dev` |

Prioritize phase 1 (kb already indexed); fetch URL via phase 2 when body content is needed.

## Sidebar routing (by query intent)

| User query intent | sidebar | Description |
| ---- | ---- | ---- |
| Flutter tutorials / guides / steps | `flutter-docs.md` | How-to guides, cookbook, tutorials |
| Flutter API / Widget / class / method | `flutter-api.md` | API reference |
| Flutter AI-assisted development | `flutter-ai-docs.md` | AI toolchain documentation |
| Dart language / SDK | (query kb full library) | `dart.dev` also directly accessible |
| Uncertain / comprehensive | Do not specify `--doc-type` | Full library search |

## Command format

### Local matching (via kb)

```bash
python3 -m scripts.kb.cli query \
  --question "<keyword>" \
  [--doc-type flutter-docs|flutter-api|flutter-ai-docs] \
  [--top-k 5]
```

See [`kb.md`](kb.md) for details.

### URL content fetching

```bash
python3 scripts/search/detail.py <object_id> <doc_type>
```

Parameters:

| Parameter | Required | Description |
| ---- | ---- | ---- |
| `object_id` | Yes | Last segment of document URL or `id` from kb hit |
| `doc_type` | Yes | One of the sidebar types |

> 🔴 **detail is the body fetching channel for the search subcommand**: `detail.py` handles HTML→Markdown cleanup and anchor extraction; kb's description/links backfill all go through this channel.

## Output format

### kb query output

JSON array, each item contains `id` / `title` / `url` / `score` / `doc_type` / `description` / `needs_description`.

### detail output

```json
{
  "title": "Document title",
  "object_id": "xxx",
  "doc_type": "flutter-docs",
  "anchors": [{"id": "anchor_id", "title": "Section title"}],
  "content": "Markdown body preserving headings/code blocks/lists/links/tables/blockquotes"
}
```

`content` is the complete Markdown body, ready to present directly to the user.

## Anchor navigation

`detail` output includes an `anchors` field (`[{id, title}]`).

When `detail` returns `content` > 3000 characters, **first** display the `anchors` directory for the user to select a section, then extract the relevant paragraphs by the chosen anchor. **Do not** automatically dump all content.

| Scenario | Handling |
| ---- | ---- |
| User asks about a specific section | Use `anchors` to locate and extract relevant paragraphs |
| Content is long (>3000 chars) | Show `anchors` directory first for user to select |
| User needs the full document | Output all `content` directly |
| User needs code examples | Focus on displaying code block sections |

## Error handling

| Scenario | Symptom | Handling |
| ---- | ---- | ---- |
| No local results | kb query returns empty | Agent layer retries with different keywords (**up to 2 times**); suggest shortening keywords or switching to English terms; if still 0, fall back to URL fetching |
| URL detail fetch failure | detail returns `error` field | Indicate document may be offline; provide `url` from search results for direct access |
| Network error | HTTPError / connection failure | **Explicitly report**, never silently swallow; suggest retrying later |
| `doc_type` parameter error | argparse validation fails | Exit code 2; indicate valid doc_type values |
| Empty content | `content: ""` | Document may be updating; provide `url` for user to view directly |
| `object_id` does not exist | detail API error | Verify `object_id` spelling; or re-search to get latest results |

> 🔴 **CHECKPOINT**: The script layer **does not retry** zero-result responses (retry logic belongs to the agent layer). Scripts only explicitly write errors into the `errors` field.

## Workflow

```
1. kb query(keyword, doc_type?) — local matching
   ├─ Hit → display result list, ask user which document to view
   └─ No results → retry with different keywords (up to 2 times) → still none → fall back to URL fetching
2. detail(object_id, doc_type) — fetch URL body
   ├─ content non-empty → output Markdown (for long documents, show anchors directory first)
   └─ content empty → inform user and provide url
3. kb collaboration (if needs_description=True):
   ├─ Backfill description (≤200 chars)
   └─ update-links bidirectional linking
```

Quick reference text steps:

1. `kb query(keyword)` select doc_type → 2. Display list for user to select → 3. `detail(object_id, doc_type)` fetch body → 4. Output Markdown (for long documents, show anchors directory first) → 5. kb collaboration: backfill description + update-links bidirectional linking.

## Keyword selection strategy

- Prefer exact terms that may appear in documentation (e.g., `ListView`, `SliverAppBar`, `StatefulWidget`).
- Both Chinese and English are acceptable; Chinese偏向 guides, English偏向 API reference.
- Use Widget names directly as keywords (e.g., `CustomScrollView`).
- When search returns no results: shorten keywords, switch to English terms, remove version numbers and retry.
- Dart language questions can directly visit `dart.dev/language`.

## Collaboration with kb

`search detail` is the **sole legitimate body source** for `kb` subcommand's `description` lazy filling and link extraction:

- `kb query` hits `needs_description=True` document → agent calls `search detail <object_id> <doc_type>` to fetch body → generates ≤200 char description → `kb update-description` backfills.
- Same body → `kb update-links --id <id> --content "<markdown>"` extracts bidirectional links.

See "Lazy filling workflow" and "update-links" sections in [`kb.md`](kb.md).

## Collaboration with fix

When the `fix` subcommand encounters an unfamiliar `package:` API or an error not covered by the error-fixes table:

- Call `search` to look up official documentation online → supplement fix rationale.
- Do not rely on model memory to draw conclusions.

## Edge cases

| Scenario | Handling |
| ---- | ---- |
| No local results, URL fetch also fails | Inform user; suggest visiting `docs.flutter.dev` directly |
| `--doc-type` is not a valid value | argparse error, exit code 2 |
| User did not specify intent | Do not pass `--doc-type`, search full library |
| Too many results | Suggest user narrow scope or specify `--doc-type` |
| `keyword` is empty | argparse error, exit code 2 |
| Network timeout | Explicitly report in `errors`, never silently swallow |

## Delivery checklist

### search workflow
- [ ] `keyword` is non-empty
- [ ] `--doc-type` (if provided) is a valid value
- [ ] When no local results, agent layer retries with different keywords (up to 2 times); still none falls back to URL fetching
- [ ] After displaying results, **do not automatically fetch details**; wait for user selection

### detail workflow
- [ ] `object_id` comes from search results (not manually fabricated)
- [ ] `doc_type` is a valid value
- [ ] When `content` is empty, provide `url` for user to visit directly
- [ ] When `content > 3000` chars, show `anchors` directory first

### kb collaboration
- [ ] When `kb query` hits `needs_description=True`, `search detail` has been called to fetch body
- [ ] After fetching body, `kb update-description` backfill + `kb update-links` bidirectional link extraction have been performed

### Error handling
- [ ] Network errors / non-empty `errors` have been explicitly reported, not silently swallowed
