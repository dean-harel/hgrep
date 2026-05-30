# hgrep

Harness-agnostic search and resume across AI coding CLI sessions. Indexes
Claude Code and Pi session transcripts into a local SQLite FTS5 store and
searches them by keyword, time, project, and branch, returning a ready-to-run
resume command per hit.

## Run

    hgrep "keywords"          # table in a terminal, JSON when piped
    hgrep "x" --json | jq .   # force JSON
    hgrep reindex [--rebuild]
    hgrep stats

From a checkout without installing, use `python3 -m hgrep.cli ...` (the runtime
is standard library only).

## Dev gates (all must pass before commit)

    python3 -m pytest      # full suite
    python3 -m pyright     # strict mode, 0 errors
    python3 -m mypy        # strict mode, no issues

The runtime is standard library only: never add a runtime dependency. The test
and type tools are dev-only (`[project.optional-dependencies].dev`).

## Architecture

Per-harness adapters live in `hgrep/harness/` behind the `Adapter` protocol
(`name`, `is_available`, `iter_sessions`, `parse`, `resume_command`). Adding a
harness is one new module plus one line in `hgrep/registry.py`; nothing outside
`hgrep/harness/` knows any on-disk format. Index only conversation text (user
and assistant text), never tool output. The index lives at `~/.cache/hgrep`
(override with `$HGREP_DB`) and auto-refreshes before each search.

## Conventions

Personal repo: author is `dean-harel <anichego@gmail.com>`, SSH remote, and no
`Co-Authored-By` or attribution trailers in commits. The `/recall` Agent Skill
in `skills/recall` is shared verbatim by Claude Code and Pi.
