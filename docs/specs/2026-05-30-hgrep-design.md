# hgrep design

Status: approved design, ready for implementation plan
Date: 2026-05-30

## Problem

AI coding harnesses scope session resume to the working directory. `claude --resume` and `pi --resume` only surface sessions started in the current directory. When you can't remember which directory a past thread lived in, it is effectively lost.

Claude Code added a partial native fix: in the `/resume` picker, `Ctrl+A` widens to all projects on the machine, `Ctrl+W` to all worktrees of the repo, `Ctrl+B` filters to the current branch, and `/` filters live. That filter matches the session name, summary, or first prompt only, not message body. It also only sees Claude Code's own sessions.

The gap that justifies building anything is therefore not single-harness discovery (native Ctrl+A handles that for Claude Code). It is cross-harness discovery: searching past sessions across more than one harness from one place, by keyword, when you don't remember the harness, the directory, or the exact title.

This user runs both Claude Code and Pi (Mario Zechner / badlogic, `@earendil-works/pi-coding-agent`). No existing CLI unifies search and resume across multiple harnesses' session stores. Community tools that index Claude Code sessions into SQLite FTS5 exist (`lee-fuhr/claude-session-index`, `kuroko1t/claude-vault`, `raine/claude-history`), but each is single-harness; the only multi-harness tool found (`JosephYaduvanshi/claude-history-manager`, "Chronicle") is a macOS GUI, not a CLI.

## Goal

A harness-agnostic CLI, `hgrep` ("harness grep"), that maintains one local full-text index over the session transcripts of every installed harness and lets you search across all of them by keyword plus metadata filters, then resume the matching session in its original harness and directory.

v1 ships two adapters: Claude Code and Pi. The architecture treats "how a harness stores sessions" as a pluggable adapter so a third harness is a new file, not a rewrite.

## Non-goals (v1)

- Indexing tool/bash output (reserved behind a future `--deep` flag; see Indexing).
- A standalone interactive TUI/fzf picker. The harness drives selection through the `/recall` skill; the CLI itself is non-interactive.
- Semantic / embedding search. v1 is lexical (FTS5 bm25 + recency).
- Cross-machine sync. The index is local.
- A git branch filter for harnesses that do not record a branch (Pi does not; the filter is best-effort per adapter).

## Concepts and on-disk facts

Both target harnesses store sessions as one JSONL file per session, with the working directory encoded in the directory name and a session id available. This similarity is what makes a clean adapter seam possible; the differences are what the adapter absorbs.

Claude Code:
- Store: `~/.claude/projects/<slugified-cwd>/<session-id>.jsonl`, where the slug is the absolute cwd with `/` replaced by `-`.
- Per-record fields seen: `type`, `cwd`, `gitBranch`, `agentName`, `customTitle`, `aiTitle`, `lastPrompt`, `timestamp`, `message` (with `role` and `content`), tool-use/tool-result records, snapshots, attachments.
- Session id: the filename stem (a UUID), also present in records as `sessionId`.
- Title resolution: `customTitle` then `aiTitle` then first user message.
- Records a `gitBranch`.
- Resume: `claude --resume <session-id>` (directory-scoped, so run it from the session's cwd).

Pi:
- Store: `~/.pi/agent/sessions/--<cwd-with-slashes-as-dashes>--/<ISO-timestamp>_<uuid>.jsonl`.
- First line is a header record: `{ "type":"session", "version":<1|2|3>, "id":"<uuid>", "timestamp":"<ISO>", "cwd":"<abs path>", "parentSession?":"<path>" }`.
- Subsequent records share `{ type, id, parentId, timestamp }` and form a tree via `parentId`. Record types include `message` (role one of `user | assistant | toolResult | bashExecution | custom`, content items typed `text | image | thinking | toolCall`), `model_change`, `thinking_level_change`, `session_info` (holds the display `name` set via `/name`), `label`, `compaction`, `branch_summary`, `custom`/`custom_message`.
- Session id: the header `id` (UUID), also embedded in the filename.
- Title resolution: latest `session_info.name` then first user message.
- No git branch field.
- Resume: `pi --session <id>` (accepts id or file path), or `pi --resume` for the picker.

## Architecture

Five units, each with one job, communicating through small interfaces.

### 1. Harness adapters

One module per harness under `hgrep/harness/` (`claude_code.py`, `pi.py`). Each implements:

- `name` -> a stable string identifier (`"claude-code"`, `"pi"`).
- `is_available() -> bool` -> whether this harness's store directory exists on the machine. An unavailable harness contributes zero sessions and never errors the run.
- `iter_sessions() -> Iterable[(path, mtime, size)]` -> globs the store and yields one entry per session file with cheap stat data (no parsing). Globs: `~/.claude/projects/**/*.jsonl`; `~/.pi/agent/sessions/**/*.jsonl`.
- `parse(path) -> SessionRecord` -> reads one file and returns the normalized record. Malformed lines are skipped, not fatal.
- `resume_command(record) -> str` -> the exact shell string to relaunch the session in its directory: `(cd <cwd> && claude --resume <id>)` or `(cd <cwd> && pi --session <id>)`.

The adapter is the only code that knows file formats, paths, slug encodings, title-resolution rules, and resume syntax. Adding a harness later means adding one module that satisfies this interface and registering it.

A registry module lists the active adapters. The indexer iterates the registry; nothing downstream of the adapter is harness-aware beyond carrying the `harness` label.

### 2. SessionRecord

The normalized unit passed from adapter to indexer:

```
harness: str            # "claude-code" | "pi"
session_id: str         # UUID
cwd: str                # absolute path the session ran in
project: str            # display label derived from cwd (e.g. basename or short path)
git_branch: str | None  # Claude Code has it; Pi is None
title: str              # resolved per adapter's rules
first_user_msg: str     # first human message text (may equal title's fallback)
content_text: str       # concatenated user + assistant text only (see Indexing)
started_at: str         # ISO-8601, earliest record timestamp
last_activity_at: str   # ISO-8601, latest record timestamp
msg_count: int          # number of message records
file_path: str          # absolute path to the .jsonl
file_mtime: float        # for incremental indexing
file_size: int          # for incremental indexing
```

### 3. Indexer

Maintains a SQLite database at `~/.cache/hgrep/index.db`, overridable via `$HGREP_DB`. Uses WAL mode and a busy timeout so concurrent runs (a search auto-refresh while another is open) do not collide.

Schema:
- `sessions` table: one row per session keyed by `(harness, session_id)`, holding all `SessionRecord` scalar fields plus `file_path`, `file_mtime`, `file_size`.
- `sessions_fts`: an FTS5 virtual table over `title`, `first_user_msg`, and `content`, linked to `sessions` by rowid. `content` holds conversation text only.

Incremental refresh algorithm:
1. For each registered, available adapter, call `iter_sessions()` to get the current `(path, mtime, size)` set.
2. Compare against the stored `file_mtime`/`file_size` per `file_path`. Parse only new or changed files; reuse existing rows otherwise.
3. Delete rows (and their FTS entries) for `file_path`s that no longer exist.
4. Wrap the batch in a transaction.

`reindex --rebuild` drops and recreates the database from scratch (recovery from corruption or schema change).

Indexing scope (the `content` column): conversation text only. For each session, `content_text` is the concatenation of user message text and assistant text replies. Tool calls, tool results, bash execution output, file snapshots, attachments, and thinking blocks are not indexed. Rationale: those blobs are the bulk of the corpus (hundreds of MB) and are machine output; indexing them bloats the database, slows reindex, and buries topical matches under incidental hits inside pasted logs and file dumps.

`--deep` is reserved, not built: `parse()` already separates conversation text from tool/output text, so a future `hgrep reindex --deep` can feed the output into a separate FTS column (searchable and scopable independently) without a redesign. v1 does not implement it.

### 4. Search

Input: a query string plus optional filters:
- `--since` / `--until` (date or relative like `7d`, matched against `last_activity_at`)
- `--project <substr>`
- `--branch <name>` (matches Claude Code sessions; Pi sessions have no branch and are excluded when this filter is set)
- `--harness <name>` (restrict to one harness)
- `--limit <n>` (default e.g. 20)

Ranking: FTS5 `MATCH` scored by bm25, blended with a mild recency boost so recent sessions edge out equally-relevant older ones. Filters are applied as SQL `WHERE` clauses on the `sessions` join.

Output:
- JSON by default (one object per result), for harness consumption. Each object includes: `harness`, `session_id`, `title`, `project`, `cwd`, `git_branch`, `last_activity_at`, `msg_count`, a short `snippet` (FTS5 `snippet()` around the match), and `resume_command`.
- `--pretty` renders a human-readable table (harness, title, when, project/branch, snippet).

### 5. CLI entrypoint

`hgrep` with subcommands:
- `search <query> [filters]` (the default; runs an incremental refresh first unless `--no-refresh`).
- `reindex [--rebuild]`.
- `stats` (counts per harness, index size, last refresh).

### 6. /recall skill

A single canonical Agent Skills `SKILL.md` folder at `~/Developer/hgrep/skills/recall/`, shared verbatim across harnesses (Pi implements the agentskills.io standard and is byte-compatible with Claude Code skills; it follows symlinks and does not enforce the name-equals-directory rule, explicitly to support shared cross-harness skill directories).

Install:
- Claude Code: symlink `~/.claude/skills/recall` -> `~/Developer/hgrep/skills/recall`.
- Pi: symlink into `~/.pi/agent/skills/`, or add the repo skills dir to the `skills` array in `~/.pi/agent/settings.json`.

Behavior: the skill calls `hgrep search "<query>" --json`, presents ranked candidates (harness, title, when, project/branch, snippet), and on the user's pick runs that result's `resume_command`.

## Data flow

```
query
  -> CLI search
  -> ensure index fresh (incremental refresh across all available adapters)
  -> FTS5 MATCH + filters + bm25/recency rank
  -> JSON results (each with resume_command)
  -> /recall skill formats candidates
  -> user picks
  -> resume_command runs (cd into cwd, relaunch in the original harness)
```

## Error handling

- Malformed JSONL lines are skipped per-file; a bad line never aborts a session parse, and a bad file never aborts a refresh.
- A harness whose store directory is absent contributes zero sessions (graceful: works on a machine with only one harness installed).
- SQLite runs in WAL mode with a busy timeout to tolerate concurrent refresh/search.
- `reindex --rebuild` recovers from a corrupt or schema-stale index.
- A session whose `cwd` no longer exists on disk still appears in results; the `resume_command` is emitted as-is (the harness will report the missing directory).

## Testing

Fixture `.jsonl` files for both formats (a small Claude Code session and a small Pi session, including edge cases: a malformed line, a session with no explicit title, a Pi session with a `session_info` rename) drive:
- Adapter parsing: correct `SessionRecord` for each format, title-resolution fallbacks, malformed-line tolerance, correct `resume_command`.
- Indexer: incremental refresh detects an mtime/size change and reparses only the changed file; deletion of a file removes its rows and FTS entries; `--rebuild` produces a clean index.
- Search: bm25 ordering, recency tiebreak, each filter (`--since/--until`, `--project`, `--branch` excluding Pi, `--harness`, `--limit`), JSON shape, and `snippet` presence.

## Layout

```
~/Developer/hgrep/
  hgrep/
    __init__.py
    cli.py              # argument parsing, subcommands
    record.py           # SessionRecord
    index.py            # SQLite schema, incremental refresh
    search.py           # FTS query, ranking, output formatting
    registry.py         # active adapters
    harness/
      __init__.py
      base.py           # adapter interface
      claude_code.py
      pi.py
  skills/
    recall/
      SKILL.md
  tests/
    fixtures/
    ...
  docs/specs/2026-05-30-hgrep-design.md
  pyproject.toml        # stdlib-only runtime; console_script entry point `hgrep`
  README.md
```

## Runtime

Python, standard library only at runtime (`sqlite3` with FTS5, `json`, `argparse`, `glob`, `os`, `datetime`). No third-party runtime dependencies. Packaged with a `pyproject.toml` exposing an `hgrep` console script. Test/dev dependencies (e.g. pytest) are dev-only.
