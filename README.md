# hgrep

Harness-agnostic search and resume across AI coding CLI sessions. One full-text
index over every harness you use (Claude Code and Pi today), searchable by
keyword, time, project, and branch, with a ready-to-run resume command per hit.

## Why

`claude --resume` and `pi --resume` only show sessions started in the current
directory. When you do not remember which directory, or even which harness, a
past thread lived in, it is hard to find. `hgrep` searches across all of them.

## Install

Native command (recommended, zsh). hgrep is standard-library only, so it runs
straight from the repo with no pip install. Clone, then source the launcher:

    git clone git@github.com:dean-harel/hgrep.git ~/Developer/hgrep
    echo 'source ~/Developer/hgrep/lib/hgrep.zsh' >> ~/.zshrc
    exec zsh   # or open a new terminal

Now `hgrep ...` works from any directory. Alternatively, install as a package:

    python3 -m pip install -e .

## Use

    hgrep "renewals retry"                 # search across all harnesses
    hgrep "deploy" --harness pi            # restrict to one harness
    hgrep "auth" --since 7d --project api  # filter by recency and project
    hgrep "x" --json | jq .                # force JSON for scripting
    hgrep reindex                          # refresh the index (also runs automatically)
    hgrep reindex --rebuild                # wipe and rebuild
    hgrep stats                            # what is indexed

Search prints a readable table in a terminal and JSON when piped; force either
with `--pretty` or `--json`. Run `hgrep --help` (or `hgrep search --help`) for
the full surface.

The index lives at `~/.cache/hgrep/index.db` (override with `$HGREP_DB`). Only
conversation text is indexed; tool output and file dumps are skipped.

## /recall skill

`skills/recall/` is an Agent Skills `SKILL.md` shared by Claude Code and Pi.

- Claude Code: `ln -s ~/Developer/hgrep/skills/recall ~/.claude/skills/recall`
- Pi: `ln -s ~/Developer/hgrep/skills/recall ~/.pi/agent/skills/recall`
  (or add the skills dir to the `skills` array in `~/.pi/agent/settings.json`)

## Adding a harness

Add one module under `hgrep/harness/` implementing the `Adapter` interface
(`name`, `is_available`, `iter_sessions`, `parse`, `resume_command`) and register
it in `hgrep/registry.py`. Nothing else needs to change.

## Development

The runtime is standard library only. Types are enforced strictly at dev time
(no runtime cost): pyright in `strict` mode and mypy `--strict`, both configured
in `pyproject.toml`.

    python3 -m pip install -e ".[dev]"
    python3 -m pyright      # strict, must report 0 errors
    python3 -m mypy         # strict, must report no issues
    python3 -m pytest       # full test suite
