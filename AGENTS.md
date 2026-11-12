# Agent instructions

## Agent skills

### Issue tracker

Local markdown: issues live as files in `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Coding style

Always use the ponytail skill (full level) for coding tasks.

### Commits

Author every commit in this repo as `rjdiips <rjdiips@gmail.com>` (set in the repo's local git config). Each commit message names only that author. Leave out any AI attribution: no `Co-Authored-By` trailer, no "Generated with" line, in commits and PR descriptions alike.
