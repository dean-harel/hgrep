---
name: recall
description: Use when the user wants to find or resume a past AI coding session across harnesses and directories - phrases like "find that thread about X", "which session did I do Y in", "resume the conversation where I...", "recall the session about...". Searches Claude Code and Pi history by keyword/time/project and resumes the chosen session.
---

# recall

Find and resume past sessions across harnesses (Claude Code and Pi) with the `hgrep` CLI.

## Steps

1. Run `hgrep search "<keywords>" --json`. Add filters from the user's hints:
   `--since 7d` (or `2w`), `--project <substr>`, `--harness pi|claude-code`, `--branch <name>`.
2. Parse the JSON array of results. Present the top candidates as a numbered list:
   `harness | title | last_activity_at | project[/branch] | snippet`.
3. Ask which one to resume (or proceed if there is a single clear match).
4. Run the chosen result's `resume_command` value verbatim. It cd's into the
   session's original directory and relaunches it in the right harness.

## Notes

- The index auto-refreshes before each search; no manual reindex is needed.
- Zero results: broaden the query (fewer/different keywords), drop `--since`, or remove filters.
- `hgrep stats` shows how many sessions are indexed per harness if results look incomplete.
- Full-text search covers conversation text (your messages and the assistant's
  replies), not tool output or file dumps.
