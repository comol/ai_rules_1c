# Runtime selection — Windows / Linux / macOS

Each tool of this skill ships as a PowerShell script (`*.ps1`). Some tools additionally ship a **Python entry point** (`*.py`) next to it, with the same parameter names and the same contract:

**Nine commands have a Python entry point today.** These are the only shipped Python commands; `tools/_common/dev_env.py` and `tools/1c-web-ops/scripts/web_common.py` are shared helpers. No tool outside this table may be assumed to work on Linux.

| Tool directory | PowerShell | Python | Notes |
|---|---|---|---|
| `1c-form-scaffold/scripts/` | `form-add.ps1` | `form-add.py` | creates a managed form (scalar registration + descriptor + `Ext/Form.xml` + module) |
| `1c-form-scaffold/scripts/` | `remove-form.ps1` | `remove-form.py` | `-DryRun` first, a real deletion needs `-Force`; references from other files need `-CleanReferences` too |
| `1c-form-compile/scripts/` | `form-compile.ps1` | `form-compile.py` | form DSL → `Form.xml` |
| `1c-meta-edit/scripts/` | `meta-edit.ps1` | `meta-edit.py` | `add-form` is refused in both runtimes — use `form-add` |
| `1c-meta-validate/scripts/` | `meta-validate.ps1` | `meta-validate.py` | also the mandatory post-edit check `meta-edit` runs |
| `1c-web-ops/scripts/` | `web-publish.ps1` | `web-publish.py` | local Apache publication; Python requires a preinstalled compatible Apache and 1C web extension |
| `1c-web-ops/scripts/` | `web-info.ps1` | `web-info.py` | publication and managed-process status |
| `1c-web-ops/scripts/` | `web-stop.ps1` | `web-stop.py` | stops only a verified Python-managed Apache process |
| `1c-web-ops/scripts/` | `web-unpublish.ps1` | `web-unpublish.py` | `-DryRun` first, `-Force` for removal; scoped publications only |
| **every other tool under `tools/`** | `*.ps1` | **none** | **not ported** — needs Windows or `pwsh`; there is no `.py` peer to call |

Rules:

- **Windows** — run the `.ps1` (`powershell -NoProfile -File <script> …`). This is the reference runtime; the PowerShell scripts are the complete toolchain.
- **Linux / macOS** — run the available `.py` with `python3`, using the documented switches. The five metadata ports need `lxml`; the four web ports use the standard library but require compatible external Apache/1C binaries. Their operational differences and prerequisites are in [web-manage.md](web-manage.md). A Python entry point is not a claim that the platform web extension works on every OS. Installing `pwsh` likewise does not make Windows-specific PowerShell code portable.
- `tools/tests/python-ports-regression.py` checks the metadata ports' parity, command inventory and installer packaging. `tools/tests/web-python-regression.py` checks web operations with isolated fixtures and mocked process calls; it does not certify a live Apache/1C deployment. CI runs both Python suites on Windows and Linux.

**Upstream ships Python variants of commands that this package does not.** They live in `Nikolay-Shirokov/cc-1c-skills` at the pinned commit `2e75b0f483eb020e9f09562d1a7be1982bc5ac6e` — immutable tree: <https://github.com/Nikolay-Shirokov/cc-1c-skills/tree/2e75b0f483eb020e9f09562d1a7be1982bc5ac6e/.claude/skills> (for example the `cf-*`, `cfe-*` and `db-*` skills); attribution and local deltas: [`NOTICE.md`](../NOTICE.md). Those files are **not installed and not managed by this package's manifest**, and **not covered by our parity tests or by the local hardening** the shipped entry points above went through. They are therefore not a claim of full Linux / macOS support: do not install them automatically, and do not copy them over the patched `.py` scripts here, which carry local fixes and would be silently overwritten. If you use one, take it from upstream deliberately, keep it outside the installed skill tree, and follow the platform instructions upstream gives for that specific tool. Their existence never makes hand-editing metadata XML acceptable.

**A missing runtime does not unlock hand-editing.** When a task needs a tool that has no Python entry point yet and no PowerShell host is available, that is a blocked task, not an exception to the Hard rule above — say so in one line and stop, or install `pwsh`. Silently hand-writing metadata XML because "the script would not run here" is the same defect as hand-editing with the tool available.
