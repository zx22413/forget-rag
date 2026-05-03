# mem-broom CLI Walkthrough

> A 5-minute tour of every `mem-broom` subcommand, from an empty database
> to a tidy one. Bilingual: English first, 繁體中文 below.

## Setup

```bash
# Install the workspace (forget-rag + mem-broom).
uv sync

# Pick a DB path. Anything mem-broom does is scoped to this file.
export FR_DB=/tmp/walkthrough.db
```

If you skip `export FR_DB`, every command below works with `--db PATH`.

---

## 1. `add` — insert chunks

Two modes: positional argument or stdin pipe.

```bash
mem-broom add "alpha — first note about Python typing" \
  --db "$FR_DB" --tag python --tag dev --json

cat <<'EOF' | mem-broom add --db "$FR_DB" --tag rust
beta — note about ownership in Rust
EOF
```

Each `add` returns a JSON envelope with the new chunk id:

```json
{ "ok": true, "data": { "id": "...", "tags": ["python", "dev"] }, "error": null }
```

## 2. `stats` — overview

```bash
mem-broom stats --db "$FR_DB"
```

Shows the chunk count, the L1/L2/L3 tier distribution, and the three
hottest and coldest chunks. Add `--json` to consume from a script.

## 3. `search` — BM25 + heat ranking

```bash
mem-broom search "python" --db "$FR_DB" --limit 3
mem-broom search "rust"   --db "$FR_DB" --json
```

Each search refreshes the matched chunks' last-access timestamp, so
repeating the query keeps those chunks hot.

## 4. `health` — surface forget candidates

```bash
mem-broom health --db "$FR_DB" --forget-heat-floor 0.05
```

Lists chunks whose heat has decayed below the floor and stale chunks
that haven't been touched recently. Non-destructive — pure suggestions.

## 5. `maintain` — recompute tiers

```bash
mem-broom maintain --db "$FR_DB" --json
```

Runs `ForgettingMemory.maintenance()`: re-scores every alive chunk and
re-assigns tiers based on the configured capacities. Idempotent.

## 6. `forget` — soft-delete

```bash
# Pick an id from any earlier command, e.g. from `stats --json`.
mem-broom forget <chunk-id> --db "$FR_DB"          # prompts y/N
mem-broom forget <chunk-id> --db "$FR_DB" --yes    # skip the prompt
```

`forget` is a soft-delete: rows stay in the DB with `forgotten_at` set,
which keeps the door open for a future `restore` subcommand (Week 4+).

---

## Common flags

| Flag           | Default            | Notes                              |
|----------------|--------------------|------------------------------------|
| `--db`         | `forget_rag.db`    | SQLite file path.                  |
| `--namespace`  | `default`          | Logical partition inside the DB.   |
| `--halflife`   | `30.0`             | Heat decay halflife in days.       |
| `--json`       | off                | Switch to machine-readable output. |
| `--version`    | —                  | Prints version and exits.          |

## Error envelope

When `--json` is set, errors share one shape:

```json
{ "ok": false, "data": null, "error": "database not found at /tmp/walkthrough.db. ..." }
```

Read commands (`stats`, `health`, `search`, `forget`, `maintain`) refuse
to silently create an empty DB — pass `--db` pointing to an existing
file or run `mem-broom add` first.

---

## 中文版

### 設定

```bash
uv sync
export FR_DB=/tmp/walkthrough.db
```

### 1. `add`：寫入

兩種模式 — positional argument 或 stdin pipe：

```bash
mem-broom add "alpha — Python typing 筆記" \
  --db "$FR_DB" --tag python --tag dev --json

echo "beta — Rust ownership 筆記" | mem-broom add --db "$FR_DB" --tag rust
```

### 2. `stats`：總覽

```bash
mem-broom stats --db "$FR_DB"
```

印 chunk 數、tier 分布、最熱/最冷三筆。加 `--json` 給管道用。

### 3. `search`：BM25 + heat 排序

```bash
mem-broom search "python" --db "$FR_DB" --limit 3
```

每次搜到的 chunk 會被「碰一下」（last_access 更新），重複搜會讓它更熱。

### 4. `health`：建議遺忘清單

```bash
mem-broom health --db "$FR_DB" --forget-heat-floor 0.05
```

純建議，不會動到資料。

### 5. `maintain`：重算 tier

```bash
mem-broom maintain --db "$FR_DB" --json
```

跑 `ForgettingMemory.maintenance()`，把 chunks 重新分到 L1/L2/L3。

### 6. `forget`：軟刪除

```bash
mem-broom forget <chunk-id> --db "$FR_DB"          # 預設要 y/N 確認
mem-broom forget <chunk-id> --db "$FR_DB" --yes    # 跳過確認
```

是 soft-delete — `forgotten_at` 被填，列還在，留給未來 `restore`。

### JSON envelope

成功：`{"ok": true, "data": {...}, "error": null}`
失敗：`{"ok": false, "data": null, "error": "..."}`

讀指令（stats / health / search / forget / maintain）遇到 `--db` 路徑不存在
會直接報錯，不會偷偷建空檔——避免 typo 看起來像「沒資料」。
