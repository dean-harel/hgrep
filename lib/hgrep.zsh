#!/usr/bin/env zsh
# hgrep: cross-harness session search and resume. Source this from ~/.zshrc:
#   source ~/Developer/hgrep/lib/hgrep.zsh
#
# Runs straight from the repo via PYTHONPATH. hgrep is standard-library only,
# so this works with any python3 >= 3.10 and needs no pip install.

# Repo root, resolved at source time (this file lives at <root>/lib/hgrep.zsh).
_HGREP_ROOT="${0:A:h:h}"

hgrep() {
  PYTHONPATH="${_HGREP_ROOT}${PYTHONPATH:+:$PYTHONPATH}" python3 -m hgrep.cli "$@"
}
