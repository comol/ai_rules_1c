---
description: "Git safety and 1C repository hygiene — no AI attribution, secret protection, destructive command confirmation, .gitattributes EOL policy for EDT/Configurator."
alwaysApply: false
category: workflow
---

# Git Safety and 1C Repository Hygiene

Load before committing, pushing, rebasing, resetting, configuring `.gitattributes`, or resolving mass EOL diffs in a 1C repository.

## Commits and Attribution

- **No AI attribution:** never add AI trailers (`Co-Authored-By`, `Signed-off-by` for an AI tool) to commit messages, and never add "Generated with …" banners to PR titles or bodies unless explicitly requested by the user.
- **No secrets:** never stage or commit `.dev.env`, `.env`, `credentials.json`, `*.key`, `*.pem`, `config.local.*`, tokens, or passwords. Keep secrets in `.gitignore` and use `.dev.env.example` for templates.
- **Dangling commits persist on GitHub:** `git push --force` does not erase previously pushed commits from object storage or forks. Get commit metadata and secret hygiene right on the first commit.

## Destructive Commands and Hooks

Never execute without an explicit user request and a concrete summary of what will be lost:

- `git push --force` / `--force-with-lease` (to `main` / `master`: refuse by default, propose `git revert`)
- `git reset --hard`, `git checkout .`, `git restore .`, `git clean -f` / `-fd`
- `git branch -D`, `git rebase --skip` / `--abort`
- `git commit --no-verify` / `-n`, `git push --no-verify`, `git commit --no-gpg-sign`

Before any reset or discard on dirty files, show `git status`, warn what is lost, and offer `git stash` or a backup branch first.

**`git commit --amend`:** allowed only when (1) explicitly requested or a pre-commit hook auto-formatted files, (2) HEAD was created in the current session, and (3) the commit has not been pushed. Never amend after a rejected hook or on a pushed commit.

## 1C Line Endings (EOL) and `.gitattributes`

EDT often writes `.bsl` / `.mdo` files with LF while Configurator / infobase dumps expect CRLF. A mixed EOL causes 1C compare/merge tools to flag every line of identical modules as changed.

- Check for `.gitattributes` in any 1C Git repository; when missing and EOL diffs appear, propose adding one (store LF in index, check out CRLF for 1C sources, keep LF for `.sh`/`.py`, mark 1C binaries as `binary`):

```gitattributes
* text=auto eol=crlf

*.bsl text eol=crlf
*.os text eol=crlf
*.mdo text eol=crlf
*.xml text eol=crlf
*.dcs text eol=crlf
*.form text eol=crlf
*.cmi text eol=crlf
*.rights text eol=crlf
*.json text eol=crlf
*.md text eol=crlf

*.sh text eol=lf
*.py text eol=lf

*.cf binary
*.cfe binary
*.epf binary
*.erf binary
*.ert binary
*.dt binary
*.1cd binary
*.mxl binary
*.bin binary
```

- **Mass false diff after 1C repository import / DB load:** do not review line-by-line immediately. Verify `.gitattributes`, run `git ls-files --eol <file>` (or inspect `git diff -w`), and renormalize (`git add --renormalize .`) only after confirming real edits are safely committed on a WIP commit first.
- **Generated XML / MDO text hygiene:** avoid typographic em-dashes (`—`), curly quotes, and the letter `ё` inside generated 1C metadata XML / MDO / identifiers — Configurator and EDT normalize or strip them inconsistently across saves.
