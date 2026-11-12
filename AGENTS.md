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

## Writing style

Applies to all text you write: replies, docs, tickets, commit messages, PR descriptions and code comments. Replies matter most. I must follow how each thing works while we solve a problem.

- Use ASD-STE100 Simplified Technical English.
- Write one fact or one instruction per sentence.
- Use active voice. Use commands for instructions ("Run the tests").
- Use common words. Explain each technical term in plain words the first time you use it.
- Use one word for one idea. Do not switch between synonyms.
- Give the answer first. Then give only the reasons I need to follow it.
- Cut filler, hedging and repetition.
- Explain hard topics fully. Being clear matters more than being short.
- Do not change code names, paths, commands or error text. These rules do not apply to them.

## Commits

Author every commit in this repo as `rjdiips <rjdiips@gmail.com>` (set in the repo's local git config). Each commit message names only that author. Leave out any AI attribution: no `Co-Authored-By` trailer, no "Generated with" line, in commits and PR descriptions alike.
